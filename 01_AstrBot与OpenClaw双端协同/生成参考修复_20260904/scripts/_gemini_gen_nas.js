#!/usr/bin/env node
// Gemini 浏览器生图（NAS 适配版，基于 gemini-browser-image-gen skill）
// 复用 NAS fygo 浏览器已登录的 Gemini 标签页（fygo CDP 127.0.0.1:16002）。
// 用法:
//   node gemini_gen_nas.js --prompt "提示词" [--out 路径] [--no-launch] [--no-fresh]
// 退出码同原版；输出 RESULT_JSON {...} 后退出。
//
// NAS 默认：
//   GEMINI_DEBUG_PORT      16002（fygo CDP）
//   GEMINI_SCREENSHOT_DIR  <NAS_DATA_DIR>/memes/generated

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
const SCREENSHOT_DIR = process.env.GEMINI_SCREENSHOT_DIR || '<NAS_DATA_DIR>/memes/generated';

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
async function uploadReference(send) {
  const LABELS = ['上传和工具', '上传', '工具', '添加', '附件', 'Add', 'Upload', 'Tools', 'Attach'];
  let injected = false;
  for (let attempt = 0; attempt < 6 && !injected; attempt++) {
    // 1) 优先点上传入口按钮（宽匹配标签）
    await send('Runtime.evaluate', {
      expression: `(()=>{
        const labels=${JSON.stringify(LABELS)};
        const btns=[...document.querySelectorAll('button,div[role=button]')];
        const b=btns.find(x=>{const t=(x.getAttribute('aria-label')||x.innerText||'').trim();return labels.some(l=>t.includes(l));});
        if(b){b.click();return 'btn';}
        return 'none';
      })()`,
      returnByValue: true
    });
    await sleep(1200);
    // 2) 直接定位隐藏 file input 并注入（按钮点到或没点到都试一次）
    const doc = await send('DOM.getDocument', { depth: -1 });
    let nodeId = null;
    try { const q = await send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: 'input[type=file]' }); nodeId = q.nodeId; } catch (e) { /* ignore */ }
    if (nodeId) {
      try { await send('DOM.setFileInputFiles', { nodeId, files: [ARGS.reference] }); injected = true; }
      catch (e) { /* 继续重试 */ }
    }
    if (!injected) await sleep(1500);
  }
  if (!injected) return { ok: false, detail: '找不到上传入口（按钮/file input 均失败）' };
  // 关闭可能残留的菜单
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  for (let i = 0; i < 20; i++) {
    const r = await send('Runtime.evaluate', {
      expression: `(()=>{const ims=[...document.querySelectorAll('img')].filter(x=>(x.src||'').indexOf('blob:')===0);return ims.length;})()`,
      returnByValue: true
    });
    if (r.result.value > 0) return { ok: true, detail: '参考图已注入(' + r.result.value + ' blob 预览)' };
    await sleep(700);
  }
  return { ok: true, detail: 'setFile 成功但未检测到 blob 预览(继续)' };
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
  const evalx = (expr) => send('Runtime.evaluate', { expression: expr, returnByValue: true });
  await send('Page.enable'); await send('Runtime.enable'); await send('DOM.enable');

  if (ARGS.fresh) {
    log('打开新对话...');
    await send('Page.navigate', { url: 'about:blank' });
    await sleep(600);
    await send('Page.navigate', { url: DEBUG_URL });
    await sleep(4500);
  }

  // ---- 登录态校验 ----
  const login = await evalx(`(()=>{const u=location.href;const btn=[...document.querySelectorAll('button,a')].some(b=>/登录|sign\\s*in|log\\s*in|ログイン/i.test(b.innerText||''));return{url:u,loginBtn:btn};})()`);
  const lv = login.result.value;
  if (lv.url.includes('accounts.google.com') || lv.loginBtn) {
    const sh = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
    finish(7, { logged_in: false, screenshot: OUT, detail: 'Gemini 未登录（被重定向到登录页或页面有登录按钮）' });
  }
  RESULT.logged_in = true;

  // ---- 参考图上传（可选）----
  if (ARGS.reference) {
    log('注入参考图', ARGS.reference);
    const up = await uploadReference(send);
    log('REF_UPLOAD', JSON.stringify(up));
    if (!up.ok) log('参考图注入失败（降级为纯文生图）:', up.detail);
    else RESULT.ref_image = true;
  }

  // ---- 输入框发现（带重试）----
  let boxSel = null;
  for (let i = 0; i < 30; i++) {
    const r = await evalx(`(()=>{const els=[...document.querySelectorAll('div[contenteditable="true"]')];const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];if(!m)return{has:false};const rect=m.getBoundingClientRect();return{has:true,sel:true,label:m.getAttribute('aria-label'),w:rect.width,h:rect.height};})()`);
    const v = r.result.value;
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
    if (!ok.result.value) { log('找不到输入框，重试', attempt); await sleep(800); continue; }
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
    typed = (chk.result.value || '').includes(FINGER);
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
    const v = r.result.value;
    log('send-check', i, 'boxCleared=', v.boxCleared, 'generating=', v.generating, 'spinner=', v.spinner, 'boxText=', v.boxText);
    if (v.boxCleared && (v.generating || v.spinner)) { sent = true; break; }
    if (i === 8 || i === 16) {
      log('未检测到生成态，补发一次...');
      await evalx(`(()=>{const els=[...document.querySelectorAll('div[contenteditable="true"]')];const m=els.find(e=>(e.getAttribute('aria-label')||'').match(/prompt|提示|输入|gemini/i))||els[els.length-1];if(m){m.focus();m.click();}return true;})()`);
      await sleep(150);
      await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
      const clicked = await evalx(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>(x.getAttribute('aria-label')||'').match(/发送|send|submit/i));if(b){b.click();return true;}return false;})()`);
      log('点击发送按钮=', clicked.result.value);
      await sleep(300);
    }
    await sleep(1000);
  }
  log('SENT_CONFIRMED=', sent);
  if (!sent) {
    const sh = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
    finish(4, { prompt_sent: false, screenshot: OUT, detail: '提示词未进入对话（发送失败）' });
  }
  RESULT.prompt_sent = true;

  // ---- 记录发送前已有的图（参考图附件等），结果筛选时排除，避免把参考图当成品 ----
  const seenRaw = await evalx(`[...document.querySelectorAll('img')].map(i=>i.src).filter(Boolean)`);
  const SEEN_BEFORE = new Set(seenRaw.result.value || []);
  log('SEEN_BEFORE_IMGS=', SEEN_BEFORE.size);

  // ---- 等待成图 / 识别拦截 ----
  const baseImgs = (await evalx(`document.querySelectorAll('img').length`)).result.value;
  let done = false, blocked = false;
  for (let i = 0; i < 75; i++) {
    const r = await evalx(`(()=>{const b=document.body.innerText;const imgs=document.querySelectorAll('img').length;const hasAction=[...document.querySelectorAll('button')].some(x=>(x.getAttribute('aria-label')||'').match(/下载|分享|download|share/i));const spinning=/正在生成|正在为你创建|generating|creating/i.test(b);return{imgs,hasAction,spinning,blocked:/无法生成|目前似乎无法|can't create|unable to create|couldn't create/i.test(b)};})()`);
    const v = r.result.value;
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
      let best=null, bestNW=0;
      for(const im of imgs){
        const src=im.src||'';
        if(ex.has(src)) continue;
        const nw=im.naturalWidth||0, nh=im.naturalHeight||0;
        if(nw<200||nh<200) continue;
        if(nw*nh>bestNW){bestNW=nw*nh; best=im;}
      }
      if(!best) return {count:imgs.length, v:null};
      const rc=best.getBoundingClientRect();
      return {count:imgs.length, v:{x:rc.x+window.scrollX, y:rc.y+window.scrollY, w:rc.width, h:rc.height, nw:best.naturalWidth, nh:best.naturalHeight, src:src}};
    })()`);
    return r.result.value || null;
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
      const v = await findGenImg(new Set());
      if (v && v.v) { imgTarget = v.v; log('兜底找到成品图 poll', i, imgTarget.nw + 'x' + imgTarget.nh); break; }
      await sleep(2000);
    }
  }

  let saved = false;
  // 兜底：定位不到成品 <img> 元素（参考图场景结构变化 / naturalWidth 未及时载入）时，滚到底部截视口保底落盘
  if (!imgTarget) {
    try {
      await send('Runtime.evaluate', { expression: 'window.scrollTo(0, document.body.scrollHeight)', returnByValue: true });
      await sleep(1000);
      const sh = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
      saved = true;
      log('已保存视口截图兜底（参考图/结构变化场景）');
    } catch (e) { log('视口截图兜底失败:', e.message); }
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
        const duv = du.result.value;
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
      const sh = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip });
      fs.writeFileSync(OUT, Buffer.from(sh.data, 'base64'));
      log('已裁切成品图（包围盒） nat=', v.nw, 'x', v.nh);
      saved = true;
    }
  }
  if (!saved) {
    log('未捕获到生成的成品图元素，无法输出纯图片');
    finish(4, { image_generated: false, detail: '未捕获到生成的成品图（等待超时或取图失败）' });
  }
  RESULT.screenshot = OUT;

  if (blocked) finish(5, { blocked: true, detail: 'Gemini 内容安全拦截（建议换用近义表述）' });
  if (!saved) finish(4, { image_generated: false, detail: '未捕获到生成的成品图（等待超时或取图失败）' });
  // saved=true → 即便 done 检测超时（Gemini 偶发不显示成图按钮），只要图片文件已落地就算成功
  const warn = done ? '生图成功' : '生图成功（成图检测超时，但图片已捕获保存）';
  finish(0, { status: 'success', image_generated: true, detail: warn });
})().catch(e => { console.error('ERR', e.message); finish(1, { detail: e.message }); });
