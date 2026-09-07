#!/usr/bin/env node
// Gemini 浏览器生图（NAS 适配版，基于 gemini-browser-image-gen skill）
// 复用 NAS fygo 浏览器已登录的 Gemini 标签页（fygo CDP 127.0.0.1:16002）。
// 用法:
//   node gemini_gen_nas.js --prompt "提示词" [--out 路径] [--no-launch] [--no-fresh]
// 退出码同原版；输出 RESULT_JSON {...} 后退出。
//
// NAS 默认：
//   GEMINI_DEBUG_PORT      16002（fygo CDP）
//   GEMINI_SCREENSHOT_DIR  /vol4/qq-whale/memes/generated

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn } = require('child_process');

const WebSocket = globalThis.WebSocket;

// ---- NAS 适配默认值 ----
const HOME = os.homedir();
const CHROME_EXE = process.env.GEMINI_CHROME_EXE || '/vol1/@appcenter/fygo-browser/app/vendor/runtime/usr/bin/chrome';
const USER_DATA_DIR = process.env.GEMINI_USER_DATA_DIR || '/vol1/@appdata/fygo-browser/profile';
const PORT = parseInt(process.env.GEMINI_DEBUG_PORT || '16002', 10);
const DEBUG_URL = 'https://gemini.google.com/app';
const SCREENSHOT_DIR = process.env.GEMINI_SCREENSHOT_DIR || '/vol4/qq-whale/memes/generated';

// ---- 参数解析 ----
function parseArgs(argv) {
  const o = { prompt: null, out: null, launch: true, fresh: true, reference: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--prompt') o.prompt = argv[++i];
    else if (a === '--out') o.out = argv[++i];
    else if (a === '--reference') o.reference = argv[++i];
    else if (a === '--no-launch') o.launch = false;
    else if (a === '--no-fresh') o.fresh = false;
    else if (!a.startsWith('--') && o.prompt === null) o.prompt = a;
  }
  if (!o.prompt) o.prompt = '画一幅父母和儿子三人在游乐场玩耍的图片。';
  if (!o.out) o.out = path.join(SCREENSHOT_DIR, `gemini_${Date.now()}.png`);
  return o;
}

const ARGS = parseArgs(process.argv.slice(2));
const PROMPT = ARGS.prompt;
const FINGER = PROMPT.slice(0, 16);
const OUT = ARGS.out;

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const log = (...a) => console.log('[gemini]', ...a);

function getJSON(p) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port: PORT, path: p, timeout: 5000 }, (res) => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(new Error('json parse ' + p)); } });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout ' + p)); });
  });
}

// 加固：安全读取 CDP 求值结果；页面未就绪/异常时回退缺省值，杜绝 undefined 崩溃
function vget(r, fb) {
  try {
    const v = r && r.result ? r.result.value : undefined;
    return (v === undefined || v === null) ? fb : v;
  } catch (e) { return fb; }
}

async function portUp() { try { await getJSON('/json/version'); return true; } catch { return false; } }

async function launchChrome() {
  if (await portUp()) { log('调试端口已存在，复用现有 Chrome'); return true; }
  log('拉起调试版 Chrome（' + USER_DATA_DIR + ' 配置）...');
  const child = spawn(CHROME_EXE, [
    '--user-data-dir=' + USER_DATA_DIR,
    '--remote-debugging-port=' + PORT,
    '--remote-allow-origins=*',
    DEBUG_URL
  ], { detached: true, stdio: 'ignore' });
  child.unref();
  for (let i = 0; i < 40; i++) {
    if (await portUp()) { log('调试端口已就绪'); return true; }
    await sleep(1000);
  }
  return false;
}

// ---- CDP 连接 ----
function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const pending = new Map();
    let id = 0;
    const send = (method, params = {}) => new Promise((res, rej) => {
      const i = ++id; pending.set(i, { res, rej });
      ws.send(JSON.stringify({ id: i, method, params }));
      setTimeout(() => { if (pending.has(i)) { pending.delete(i); rej(new Error('send timeout ' + method)); } }, 25000);
    });
    ws.addEventListener('open', () => resolve({ ws, send }));
    ws.addEventListener('error', () => reject(new Error('ws connect error')));
    ws.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data.toString());
      if (m.id && pending.has(m.id)) {
        const p = pending.get(m.id); pending.delete(m.id);
        m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result);
      }
    });
  });
}

const RESULT = { status: 'error', logged_in: null, prompt_sent: false, image_generated: false, blocked: false, screenshot: null, detail: '', ref_image: false };

// 把参考图注入 Gemini composer：点"上传和工具/添加/上传"等入口→隐藏 input[type=file]→DOM.setFileInputFiles
// 多次重试以应对 Gemini UI 渲染时序；找不到按钮时直接尝试隐藏 file input
async function uploadReference(send, evalx) {
  // 精确上传入口标签（优先）；宽匹配仅作降级
  const EXACT = ['\u4e0a\u4f20\u548c\u5de5\u5177', '\u4e0a\u4f20\u6587\u4ef6', '\u6dfb\u52a0\u6587\u4ef6', '\u4e0a\u4f20\u56fe\u7247',
                 'Upload files', 'Add files', 'Upload & tools', 'Upload and tools', 'Upload image'];
  const WIDE = ['\u4e0a\u4f20\u548c\u5de5\u5177', '\u4e0a\u4f20', '\u5de5\u5177', '\u6dfb\u52a0', '\u9644\u4ef6',
                'Add', 'Upload', 'Tools', 'Attach'];
  // 排除历史对话里的 "…的更多选项" 按钮（aria-label 形如 "「xxx」的更多选项"），点了不产生 file input
  const EXCLUDE_RE = /(\u7684\u66f4\u591a\u9009\u9879|more options|More options|more_vert)/i;

  const collect = async () => await evalx(`(()=>{
    const exact=${JSON.stringify(EXACT)};
    const wide=${JSON.stringify(WIDE)};
    const ex=/(\\u7684\\u66f4\\u591a\\u9009\\u9879|more options|More options|more_vert)/i;
    const out=[];
    document.querySelectorAll('button,div[role=button],span[role=button],mat-icon-button').forEach(function(b){
      const al=(b.getAttribute('aria-label')||'').trim();
      const tx=(b.innerText||'').trim();
      if(!al && !tx) return;
      if(ex.test(al) || ex.test(tx)) return;            // 排除历史对话的"更多选项"
      const rc=b.getBoundingClientRect();
      if(rc.width<3||rc.height<3) return;               // 不可见
      const t=al+' '+tx;
      let pri=-1;
      if(exact.some(function(l){return t.indexOf(l)>=0;})) pri=0;
      else if(wide.some(function(l){return t.indexOf(l)>=0;})) pri=1;
      if(pri<0) return;
      out.push({al:al, tx:tx.slice(0,24), pri:pri,
                x:Math.round(rc.x+rc.width/2), y:Math.round(rc.y+rc.height/2)});
    });
    out.sort(function(a,b){return a.pri-b.pri;});
    return out.slice(0, 6);
  })()`);

  const fileInputs = async () => {
    // evalx 返回 CDP 响应对象 {result:{value:N}}，必须用 vget 解包
    const n = vget(await evalx(`document.querySelectorAll('input[type=file]').length`), 0);
    return (typeof n === 'number') ? n : 0;
  };
  // 真实鼠标点击（Angular Material 按钮有时不吃 JS click()）
  const realClick = async (x, y) => {
    try {
      await send('Input.dispatchMouseEvent', {type:'mousePressed', x:x, y:y, button:'left', clickCount:1});
      await send('Input.dispatchMouseEvent', {type:'mouseReleased', x:x, y:y, button:'left', clickCount:1});
    } catch (e) { /* ignore */ }
  };
  const jsClick = async (al) => await evalx(`(()=>{
    const al=${JSON.stringify(al)};
    const b=[...document.querySelectorAll('button,div[role=button],span[role=button]')].find(function(x){return (x.getAttribute('aria-label')||'').trim()===al;});
    if(b){b.click();return true;}
    return false;
  })()`);
  // 轮询等 file input 出现（每 600ms 一次，最多 3s）
  const waitFileInput = async () => {
    for (let k = 0; k < 5; k++) {
      if (await fileInputs() > 0) return true;
      await sleep(600);
    }
    return false;
  };
  const inject = async () => {
    const doc = await send('DOM.getDocument', { depth: -1 });
    const q = await send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: 'input[type=file]' });
    if (!q || !q.nodeId) return false;
    try { await send('DOM.setFileInputFiles', { nodeId: q.nodeId, files: [ARGS.reference] }); return true; }
    catch (e) { return false; }
  };

  let injected = false;
  for (let attempt = 0; attempt < 3 && !injected; attempt++) {
    const cands = vget(await collect(), []);
    log('上传入口候选 attempt', attempt, JSON.stringify(cands));
    if (!cands.length) { await sleep(1500); continue; }
    for (const c of cands) {
      // 1) JS click
      await jsClick(c.al);
      if (await waitFileInput()) { log('JS click 打开上传入口:', c.al); injected = await inject(); }
      // 2) 真实鼠标点击兜底
      if (!injected && c.x > 0 && c.y > 0) {
        await realClick(c.x, c.y);
        if (await waitFileInput()) { log('真实点击打开上传入口:', c.al, c.x, c.y); injected = await inject(); }
      }
      if (injected) break;
      // 点错了（可能是别的按钮）→ 收起可能弹出的菜单，继续下一个候选
      await send('Input.dispatchKeyEvent', { type:'keyDown', key:'Escape', code:'Escape', windowsVirtualKeyCode:27 });
      await sleep(500);
    }
    if (!injected) await sleep(1500);
  }
  if (!injected) return { ok: false, detail: '\u627e\u4e0d\u5230\u4e0a\u4f20\u5165\u53e3\uff08\u6309\u94ae/file input \u5747\u5931\u8d25\uff09' };
  // 关闭可能残留的菜单
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  for (let i = 0; i < 20; i++) {
    const r = await send('Runtime.evaluate', {
      expression: `(()=>{const ims=[...document.querySelectorAll('img')].filter(x=>(x.src||'').indexOf('blob:')===0);return ims.length;})()`,
      returnByValue: true
    });
    const _n = vget(r, 0);
    if (_n > 0) return { ok: true, detail: '\u53c2\u8003\u56fe\u5df2\u6ce8\u5165(' + _n + ' blob \u9884\u89c8)' };
    await sleep(700);
  }
  return { ok: true, detail: 'setFile \u6210\u529f\u4f46\u672a\u68c0\u6d4b\u5230 blob \u9884\u89c8(\u7ee7\u7eed)' };
}

function finish(code, extra = {}) {
  Object.assign(RESULT, extra);
  console.log('RESULT_JSON ' + JSON.stringify(RESULT));
  process.exit(code);
}

(async () => {
  if (ARGS.launch) {
    const ok = await launchChrome();
    if (!ok) finish(6, { detail: 'Chrome 调试端口无法拉起（检查调试版 Chrome 配置/端口占用）' });
  } else if (!(await portUp())) {
    finish(6, { detail: '端口未开启且未启用 --launch' });
  }

  const tabs = await getJSON('/json');
  let target = tabs.find(t => (t.url || '').includes('gemini.google.com')) || tabs.find(t => t.type === 'page');
  if (!target) finish(1, { detail: '找不到页面标签页' });
  log('TAB', target.url);

  const { ws, send } = await connect(target.webSocketDebuggerUrl);
  // 加固：导航后页面未就绪时 CDP 求值会返回 undefined，原实现会让调用方读属性直接 TypeError 秒崩
  const evalx = async (expr) => {
    try {
      const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
      if (r && r.result) return r;
    } catch (e) {
      log('evalx err', String((e && e.message) || e).slice(0, 120));
    }
    return { result: { value: null } };
  };
  await send('Page.enable'); await send('Runtime.enable'); await send('DOM.enable');

  if (ARGS.fresh) {
    log('打开新对话...');
    try { await send('Page.navigate', { url: 'about:blank' }); }
    catch (e) { log('nav blank err', String((e && e.message) || e).slice(0, 80)); }
    await sleep(600);
    try { await send('Page.navigate', { url: DEBUG_URL }); }
    catch (e) { log('nav app err', String((e && e.message) || e).slice(0, 80)); }
    // 加固：轮询等页面真正就绪，替代原来的固定 4.5s 睡眠
    let ready = false;
    for (let i = 0; i < 40; i++) {
      await sleep(1000);
      const r = await evalx(`(()=>{try{return{ok:!!document.body,u:location.href,n:document.querySelectorAll('div[contenteditable=\"true\"]').length};}catch(e){return{ok:false};}})()`);
      const v = vget(r, null);
      if (v && v.ok && String(v.u || '').indexOf('gemini.google.com') >= 0) {
        ready = true; log('页面就绪', i, 'inputBox=', v.n); break;
      }
      if (i % 5 === 0) log('等待页面就绪...', i);
    }
    if (!ready) log('页面 40s 内未就绪，继续尝试（可能仍可用）');
  }

  // ---- 登录态校验 ----
  const login = await evalx(`(()=>{const u=location.href;const btn=[...document.querySelectorAll('button,a')].some(b=>/登录|sign\\s*in|log\\s*in|ログイン/i.test(b.innerText||''));return{url:u,loginBtn:btn};})()`);
  const lv = vget(login, {});
  if (lv.url && (lv.url.includes('accounts.google.com') || lv.loginBtn)) {
    const sh = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
    finish(7, { logged_in: false, screenshot: OUT, detail: 'Gemini 未登录（被重定向到登录页或页面有登录按钮）' });
  }
  RESULT.logged_in = true;

  // ---- 参考图上传（可选）----
  if (ARGS.reference) {
    // 前置：等 composer 真正渲染出来（上传入口 / file input / 输入框），避免页面刚加载完就急着上传导致失败
    let composerReady = false;
    for (let i = 0; i < 20; i++) {
      const cr = await evalx(`(()=>{
        const labels=['\u4e0a\u4f20\u548c\u5de5\u5177','\u4e0a\u4f20','\u5de5\u5177','\u6dfb\u52a0','\u9644\u4ef6','Add','Upload','Tools','Attach'];
        const btns=[...document.querySelectorAll('button,div[role=button]')];
        const hasBtn=btns.some(function(x){const t=(x.getAttribute('aria-label')||x.innerText||'').trim();return labels.some(function(l){return t.indexOf(l)>=0;});});
        const hasFile=!!document.querySelector('input[type=file]');
        const hasBox=!!document.querySelector('div[contenteditable=\"true\"]');
        return {hasBtn:hasBtn, hasFile:hasFile, hasBox:hasBox};
      })()`);
      const cv = vget(cr, {});
      if ((cv.hasBtn || cv.hasFile) && cv.hasBox) { composerReady = true; log('composer 就绪, i=', i, JSON.stringify(cv)); break; }
      if (i % 3 === 0) log('等待 composer 就绪...', i, JSON.stringify(cv));
      await sleep(1000);
    }
    if (!composerReady) log('composer 等待超时，仍尝试上传（可能失败）');
    log('注入参考图', ARGS.reference);
    const up = await uploadReference(send, evalx);
    log('REF_UPLOAD', JSON.stringify(up));
    if (!up.ok) {
      log('参考图注入失败（降级为纯文生图）:', up.detail);
    } else {
      RESULT.ref_image = true;
      // ---- 等待参考图上传完成 ----
      // Gemini 上传附件期间发送按钮是 disabled 的，必须等它可用再发，否则点了没反应 / 只发文字不带图
      // 策略：每 2 秒检测一次发送按钮状态；至少等满 5 秒；最多等 32 秒后强制放行
      const t0 = Date.now();
      let ready = false;
      for (let i = 0; i < 16; i++) {
        await sleep(2000);
        const st = await evalx(`(()=>{
          const btns=[...document.querySelectorAll('button')];
          const b=btns.find(function(x){
            const a=(x.getAttribute('aria-label')||'').toLowerCase();
            const t=(x.getAttribute('data-tooltip')||'').toLowerCase();
            const mt=(x.getAttribute('mattooltip')||'').toLowerCase();
            return a.indexOf('send')>=0 || a.indexOf('\u53d1\u9001')>=0 || a.indexOf('submit')>=0
                || t.indexOf('send')>=0 || t.indexOf('\u53d1\u9001')>=0
                || mt.indexOf('send')>=0 || mt.indexOf('\u53d1\u9001')>=0;
          });
          // 上传完成的正面证据：composer 里出现 blob: 预览缩略图
          const blobImgs=[...document.querySelectorAll('img')].filter(function(x){return (x.src||'').indexOf('blob:')===0;}).length;
          // 上传中的标志：进度条 / spinner
          const busy=!!document.querySelector('mat-progress-bar, mat-spinner, [class*=\"progress-bar\"], [aria-label*=\"\u4e0a\u4f20\u4e2d\"], [aria-label*=\"Uploading\"]');
          return {
            hasSend: !!b,
            disabled: b ? (!!b.disabled || b.getAttribute('aria-disabled')==='true') : null,
            blob: blobImgs,
            busy: busy
          };
        })()`);
        const v = vget(st, {});
        const elapsed = Math.round((Date.now() - t0) / 1000);
        log('上传检测', i, 'elapsed=' + elapsed + 's', 'hasSend=', v.hasSend, 'disabled=', v.disabled, 'blob预览=', v.blob, 'busy=', v.busy);
        // 放行条件：已满 5s + 发送按钮可用 + 没有上传中标志（blob 预览仅作参考，不强制，避免卡死）
        if (elapsed >= 5 && v.hasSend && v.disabled === false && !v.busy) {
          ready = true;
          log('发送按钮已可用且无上传中标志，放行');
          break;
        }
        if (elapsed >= 20 && v.hasSend) {
          ready = true;
          log('上传等待超时（20s），强制放行发送');
          break;
        }
      }
      // 保底：确保从注入完成到点发送至少经过 5 秒
      const waitedMs = Date.now() - t0;
      if (waitedMs < 5000) {
        const extra = Math.ceil((5000 - waitedMs) / 1000);
        log('补足等待', extra, 's（保证至少 5s 上传时间）');
        await sleep(extra * 1000);
      }
      log('参考图上传等待结束, ready=', ready, 'waited=', Math.round((Date.now() - t0) / 1000) + 's');
      RESULT.ref_upload_ready = ready;
    }
  }

  // ---- 输入框发现（带重试）----
  let boxSel = null;
  for (let i = 0; i < 30; i++) {
    const r = await evalx(`(()=>{const els=[...document.querySelectorAll('div[contenteditable="true"]')];const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];if(!m)return{has:false};const rect=m.getBoundingClientRect();return{has:true,sel:true,label:m.getAttribute('aria-label'),w:rect.width,h:rect.height};})()`);
    const v = vget(r, {});
    if (v.has && v.w > 50) { boxSel = true; log('输入框就绪, label=', v.label); break; }
    if (i % 5 === 0) log('等待输入框...', i);
    await sleep(1000);
  }
  if (!boxSel) {
    const sh = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
    finish(3, { screenshot: OUT, detail: '找不到 Gemini 输入框' });
  }

  // ---- 键入提示词（带重试 + 校验）----
  let typed = false;
  for (let attempt = 1; attempt <= 3 && !typed; attempt++) {
    const ok = await evalx(`(()=>{
      const els=[...document.querySelectorAll('div[contenteditable="true"]')];
      const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];
      if(!m)return false;
      m.focus(); m.click();
      m.dispatchEvent(new InputEvent('input', {bubbles:true, composed:true, inputType:'insertText'}));
      m.dispatchEvent(new Event('change', {bubbles:true, composed:true}));
      return true;
    })()`);
    if (!vget(ok, false)) { log('找不到输入框，重试', attempt); await sleep(800); continue; }
    await sleep(200);
    await send('Input.insertText', { text: PROMPT });
    await sleep(300);
    const chk = await evalx(`(()=>{
      const els=[...document.querySelectorAll('div[contenteditable="true"]')];
      const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];
      if(m){
        m.dispatchEvent(new InputEvent('input', {bubbles:true, composed:true, inputType:'insertText'}));
        return m.innerText||m.textContent||'';
      }
      return '';
    })()`);
    typed = String(vget(chk, '')).includes(FINGER);
    if (!typed) { log('第', attempt, '次键入校验失败，重试'); await sleep(800); }
  }
  log('BOX_HAS_PROMPT=', typed);
  if (!typed) {
    const sh = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
    finish(8, { screenshot: OUT, detail: '提示词未能写入输入框（多次重试失败）' });
  }

  // ---- 发送（Enter，必要时点发送按钮）----
  await evalx(`(()=>{
    const els=[...document.querySelectorAll('div[contenteditable="true"]')];
    const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];
    if(m){m.focus(); m.click();}
  })()`);
  await sleep(150);
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'char', key: 'Enter', text: '\r', windowsVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await evalx(`(()=>{
    const els=[...document.querySelectorAll('div[contenteditable="true"]')];
    const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];
    if(m){
      m.dispatchEvent(new KeyboardEvent('keydown', {bubbles:true, composed:true, key:'Enter', code:'Enter', keyCode:13, which:13}));
      m.dispatchEvent(new KeyboardEvent('keypress', {bubbles:true, composed:true, key:'Enter', code:'Enter', keyCode:13, which:13}));
      m.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true, composed:true, key:'Enter', code:'Enter', keyCode:13, which:13}));
    }
  })()`);
  await sleep(1200);

  let sent = false;
  for (let i = 0; i < 25; i++) {
    const r = await evalx(`(()=>{
      const b = document.body.innerText || '';
      const els=[...document.querySelectorAll('div[contenteditable="true"]')];
      const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];
      const boxText=(m?m.innerText||m.textContent||'':'').trim();
      const boxCleared = !boxText.includes(${JSON.stringify(FINGER)});
      const generating = /正在生成|正在为你创建|正在思考|生成中|generating|creating|thinking/i.test(b);
      const spinner = !!document.querySelector('[role="progressbar"],[aria-busy="true"]') ||
        [...document.querySelectorAll('div')].some(d=>(/正在生成|Generating|Thinking/i.test(d.innerText||''))&&d.offsetWidth>0&&d.offsetHeight>0);
      return {boxCleared, generating, spinner, boxText: boxText.slice(0, 80)};
    })()`);
    const v = vget(r, {});
    log('send-check', i, 'boxCleared=', v.boxCleared, 'generating=', v.generating, 'spinner=', v.spinner, 'boxText=', v.boxText);
    if (v.boxCleared && (v.generating || v.spinner)) { sent = true; break; }
    if (i === 8 || i === 16) {
      log('未检测到生成态，补发一次...');
      await evalx(`(()=>{const els=[...document.querySelectorAll('div[contenteditable="true"]')];const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];if(m){m.focus();m.click();}return true;})()`);
      await sleep(150);
      await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
      const clicked = await evalx(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>(x.getAttribute('aria-label')||'').match(/发送|send|submit/i));if(b){b.click();return true;}return false;})()`);
      log('点击发送按钮=', vget(clicked, false));
      await sleep(300);
    }
    await sleep(1000);
  }
  log('SENT_CONFIRMED=', sent);
  if (!sent) {
    const sh = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
    finish(4, { prompt_sent: false, screenshot: OUT, detail: await finalDetail('提示词未进入对话（发送失败）') });
  }
  RESULT.prompt_sent = true;

  // ---- 记录发送前已有的图（参考图附件等），结果筛选时排除，避免把参考图当成品 ----
  const seenRaw = await evalx(`[...document.querySelectorAll('img')].map(i=>i.src).filter(Boolean)`);
  const SEEN_BEFORE = new Set(vget(seenRaw, []));
  log('SEEN_BEFORE_IMGS=', SEEN_BEFORE.size);

  // ---- 等待成图 / 识别拦截 ----
  const baseImgs = vget(await evalx(`document.querySelectorAll('img').length`), 0);
  let done = false, blocked = false;
  for (let i = 0; i < 75; i++) {
    const r = await evalx(`(()=>{const b=document.body.innerText;const imgs=document.querySelectorAll('img').length;const hasAction=[...document.querySelectorAll('button')].some(x=>(x.getAttribute('aria-label')||'').match(/下载|分享|download|share/i));const spinning=/正在生成|正在为你创建|generating|creating/i.test(b);return{imgs,hasAction,spinning,blocked:/无法生成|目前似乎无法|can't create|unable to create|couldn't create/i.test(b)};})()`);
    const v = vget(r, {});
    if (v.blocked) { blocked = true; log('被内容安全拦截 poll', i); break; }
    if (v.hasAction) { done = true; log('成图操作按钮出现 poll', i); break; }
    if (v.imgs > baseImgs + 0) { done = true; log('图片元素增加 poll', i, 'imgs', v.imgs); break; }
    if (i % 10 === 0) log('生成中...', i, 'imgs', v.imgs, 'spinning', v.spinning);
    await sleep(2000);
  }

  function downloadHttp(url, out) {
    return new Promise((res) => {
      try {
        const req = https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 20000 }, (r) => {
          if (r.statusCode >= 300 && r.statusCode < 400 && r.headers.location) {
            r.resume(); return res(downloadHttp(r.headers.location, out));
          }
          if (r.statusCode !== 200) { r.resume(); return res(false); }
          const f = fs.createWriteStream(out);
          r.pipe(f);
          f.on('finish', () => res(true));
        });
        req.on('error', () => res(false));
        req.setTimeout(20000, () => { req.destroy(); res(false); });
      } catch { res(false); }
    });
  }

  async function findGenImg(exclude) {
    const ex = JSON.stringify([...(exclude || [])]);
    const r = await evalx(`(()=>{
      const ex=new Set(${ex});
      const imgs=[...document.querySelectorAll('img')];
      const cand=[];
      let maxArea=0;
      for(const im of imgs){
        const src=im.src||'';
        if(ex.has(src)) continue;
        const nw=im.naturalWidth||0, nh=im.naturalHeight||0;
        if(nw<200||nh<200) continue;
        const area=nw*nh;
        if(area>maxArea) maxArea=area;
        cand.push({im:im, w:nw, h:nh, area:area});
      }
      if(cand.length===0) return {count:imgs.length, v:null};
      const big=cand.filter(function(c){ return c.area >= maxArea*0.8; });
      const best=(big.length? big[big.length-1] : cand[cand.length-1]).im;
      const rc=best.getBoundingClientRect();
      return {count:imgs.length, v:{x:rc.x+window.scrollX, y:rc.y+window.scrollY, w:rc.width, h:rc.height, nw:best.naturalWidth, nh:best.naturalHeight, src:best.src||''}};
    })()`);
    return vget(r, null);
  }

  // 兜底：取最后一个较大的 <img>（用户期望的"生成的最后一张图片"），不做排除
  async function findLastImg() {
    const r = await evalx(`(()=>{
      const imgs=[...document.querySelectorAll('img')];
      const cand=[];
      for(const im of imgs){
        const w=im.naturalWidth||im.width||0, h=im.naturalHeight||im.height||0;
        if(w>=50 && h>=50) cand.push({im, w, h});
      }
      if(cand.length===0) return null;
      const pick=cand[cand.length-1];
      const rc=pick.im.getBoundingClientRect();
      return {x:rc.x+window.scrollX, y:rc.y+window.scrollY, w:rc.width, h:rc.height, nw:pick.w, nh:pick.h, src:pick.im.src||''};
    })()`);
    return vget(r, null);
  }

  // 取 Gemini 最后一条助手纯文本回复（用于"它没听懂"或对话式拒绝时把原话透传给用户）
  async function findAssistantText() {
    const r = await evalx(`(()=>{
      const sels=[
        'model-response','message-content',
        '[data-test-id=\"model-response\"]',
        '.conversation-turn[data-turn-role=\"model\"] .markdown-main-panel',
        'message-content[class*=\"model\"]',
        '.model-response',
        '.conversation-container [class*=\"response\"]:not([class*=\"user\"])',
        '.markdown-main-panel','.conversation-turn'
      ];
      let nodes=[], hit='';
      for(const s of sels){
        const found=[...document.querySelectorAll(s)];
        if(found.length){ hit=s+'#'+found.length; nodes=found; break; }
      }
      if(!nodes.length) return {text:'', candidates:0, hit:'none'};
      const last=nodes[nodes.length-1];
      const txt=(last.innerText||last.textContent||'').replace(/\\s+/g,' ').trim();
      return {text:txt.slice(0, 400), candidates:nodes.length, hit:hit};
    })()`);
    return vget(r, {text:'', candidates:0, hit:'vget-fail'});
  }
  async function finalDetail(prefix) {
    try {
      const at = await findAssistantText();
      log('findAssistantText: hit=', at.hit, 'cand=', at.candidates, 'len=', (at.text||'').length, 'preview=', (at.text||'').slice(0, 80));
      if (at && at.text && at.text.length > 4) {
        return prefix + ' ｜ Gemini 说：「' + at.text.slice(0, 200) + '」';
      }
    } catch (e) { log('finalDetail err:', e.message); }
    return prefix;
  }

  let imgTarget = null;
  for (let i = 0; i < 20; i++) {
    const v = await findGenImg(SEEN_BEFORE);
    if (v && v.v) { imgTarget = v.v; log('找到成品图元素 poll', i, imgTarget.nw + 'x' + imgTarget.nh, 'src=', imgTarget.src.slice(0, 30)); break; }
    if (i % 4 === 0) log('等待成品图 <img> 出现...', i, 'imgs=', v ? v.count : '?');
    await sleep(2000);
  }
  // 兜底：若排除了参考图后仍找不到，放宽到全图（生成的图也可能以 blob 形式存在）
  if (!imgTarget) {
    for (let i = 0; i < 10; i++) {
      const v = await findLastImg();
      if (v && v.v) { imgTarget = v.v; log('兜底找到成品图 poll', i, imgTarget.nw + 'x' + imgTarget.nh); break; }
      await sleep(2000);
    }
  }

  let saved = false;
  // 兜底：定位不到参考图排除后的成品 <img> 时，用"最后一张大图"裁切截图（不再保存整页截图，避免把浏览器 UI 发给用户）
  if (!imgTarget) {
    const last = await findLastImg();
    if (last && last.src) {
      try {
        const clip = { x: Math.max(0, Math.round(last.x)), y: Math.max(0, Math.round(last.y)), width: Math.round(last.w), height: Math.round(last.h) };
        const sh = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: Object.assign({}, clip, { scale: 1 }) });
        fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
        saved = true;
        log('已裁切最后大图兜底 nat=', last.nw, 'x', last.nh);
      } catch (e) { log('裁切兜底失败:', e.message); }
    }
    if (!saved) {
      log('未捕获到任何生成的图片元素，放弃保存整页截图（避免发给用户）');
      finish(4, { image_generated: false, detail: await finalDetail('未找到生成的图片（建议重试或换表述）') });
    }
  }
  if (imgTarget && imgTarget.src) {
    const v = imgTarget;
    try {
      if (/^data:/i.test(v.src)) {
        const m = v.src.match(/^data:image\/\w+;base64,(.+)$/s);
        if (m) { fs.writeFileSync(OUT, Buffer.from(m[1], 'base64')); saved = true; log('已保存 data: 原始图片（纯图片）'); }
      } else if (/^blob:/i.test(v.src)) {
        const du = await evalx(`(()=>{
          const im=[...document.querySelectorAll('img')].find(x=>(x.src||'').indexOf(${JSON.stringify(v.src.slice(0, 50))})===0);
          if(!im) return null;
          try{ const c=document.createElement('canvas'); c.width=im.naturalWidth||im.width; c.height=im.naturalHeight||im.height;
            c.getContext('2d').drawImage(im,0,0); return c.toDataURL('image/png'); }
          catch(e){ return 'ERR:'+e.message; }
        })()`);
        const duv = vget(du, null);
        if (duv && duv.indexOf('data:image') === 0) {
          const m = duv.match(/^data:image\/\w+;base64,(.+)$/s);
          if (m) { fs.writeFileSync(OUT, Buffer.from(m[1], 'base64')); saved = true; log('已保存 blob 原始图片（纯图片，无 UI）'); }
        } else { log('blob canvas 取图失败:', duv ? String(duv).slice(0, 40) : 'null'); }
      } else if (/^https?:/i.test(v.src)) {
        if (await downloadHttp(v.src, OUT)) { saved = true; log('已下载原始图片（纯图片，无 UI）', v.src.slice(0, 64)); }
      }
    } catch (e) { log('成品图取图异常:', e.message); }
    if (!saved) {
      const clip = { x: Math.max(0, Math.round(v.x)), y: Math.max(0, Math.round(v.y)), width: Math.round(v.w), height: Math.round(v.h) };
      const sh = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: Object.assign({}, clip, { scale: 1 }) });
      fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
      log('已裁切成品图（包围盒） nat=', v.nw, 'x', v.nh);
      saved = true;
    }
  }
  if (!saved) {
    log('未捕获到生成的成品图元素，无法输出纯图片');
    finish(4, { image_generated: false, detail: await finalDetail('未捕获到生成的成品图（等待超时或取图失败）') });
  }
  RESULT.screenshot = OUT;

  if (blocked) finish(5, { blocked: true, detail: await finalDetail('Gemini 内容安全拦截（建议换用近义表述）') });
  if (!saved) finish(4, { image_generated: false, detail: '未捕获到生成的成品图（等待超时或取图失败）' });
  // saved=true → 即便 done 检测超时（Gemini 偶发不显示成图按钮），只要图片文件已落地就算成功
  const warn = done ? '生图成功' : '生图成功（成图检测超时，但图片已捕获保存）';
  finish(0, { status: 'success', image_generated: true, detail: warn });
})().catch(e => { console.error('ERR', e.message); finish(1, { detail: e.message }); });
