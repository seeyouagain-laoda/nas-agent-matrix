const http = require('http');
const WebSocket = globalThis.WebSocket;
const PORT = 16002;
const REF = process.env.REF || '<NAS_DATA_DIR>/memes/generated/20260904_203714_g_25904.png';
function getJSON(p) { return new Promise((res, rej) => { const req = http.get({ host: '127.0.0.1', port: PORT, path: p, timeout: 5000 }, (r) => { let d = ''; r.on('data', c => d += c); r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } }); }); req.on('error', rej); req.on('timeout', () => { req.destroy(); rej(new Error('to ' + p)); }); }); }
function connect(wsUrl) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(wsUrl); const pending = new Map(); let id = 0;
    const send = (m, p = {}) => new Promise((r, j) => { const i = ++id; pending.set(i, { r, j }); ws.send(JSON.stringify({ id: i, method: m, params: p })); setTimeout(() => { if (pending.has(i)) { pending.delete(i); j(new Error('to ' + m)); } }, 20000); });
    ws.addEventListener('open', () => res({ ws, send }));
    ws.addEventListener('error', () => rej(new Error('ws err')));
    ws.addEventListener('message', (e) => { const m = JSON.parse(e.data.toString()); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.j(new Error(JSON.stringify(m.error))) : p.r(m.result); } });
  });
}
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const tabs = await getJSON('/json');
  const t = tabs.find(x => (x.url || '').includes('gemini.google.com')) || tabs.find(x => x.type === 'page');
  if (!t) { console.log('NO_TAB'); process.exit(1); }
  console.log('TAB', t.url);
  const { send } = await connect(t.webSocketDebuggerUrl);
  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.navigate', { url: 'about:blank' }); await sleep(500);
  await send('Page.navigate', { url: 'https://gemini.google.com/app' }); await sleep(11000);
  // 点击 上传和工具
  const clicked = await send('Runtime.evaluate', { expression: `(()=>{const b=[...document.querySelectorAll('button')].find(x=>(x.getAttribute('aria-label')||'')==='上传和工具');if(b){b.click();return true;}return false;})()`, returnByValue: true });
  console.log('CLICK_UPLOAD_BTN=', clicked.result.value);
  await sleep(1800);
  // 取 file input nodeId
  const doc = await send('DOM.getDocument', { depth: -1 });
  const root = doc.root.nodeId;
  let nodeId = null;
  try { const q = await send('DOM.querySelector', { nodeId: root, selector: 'input[type=file]' }); nodeId = q.nodeId; } catch (e) { console.log('query file input err', e.message); }
  console.log('FILE_INPUT_NODEID=', nodeId);
  if (nodeId) {
    try { await send('DOM.setFileInputFiles', { nodeId, files: [REF] }); console.log('SET_FILE_OK', REF); }
    catch (e) { console.log('SET_FILE_ERR', e.message); }
  }
  await sleep(3500);
  const check = await send('Runtime.evaluate', { expression: `(()=>{
    const composer=document.querySelector('div[contenteditable=true]');
    const imgsInComposer=composer?composer.querySelectorAll('img').length:0;
    const chips=[...document.querySelectorAll('*')].filter(e=>(e.innerText||'').trim()===''&&false);
    const anyImgAttach=[...document.querySelectorAll('img')].filter(im=>{const r=im.getBoundingClientRect();return r.width>20&&r.height>20&&im.src&&!im.src.startsWith('data:')&&/blob:|googleusercontent|lh3|gstatic/.test(im.src)}).length;
    const bodyHasImg=document.querySelectorAll('img').length;
    return {imgsInComposer, anyImgAttach, bodyHasImg, composerText:(composer?composer.innerText:'').slice(0,80)};
  })()`, returnByValue: true });
  console.log('AFTER_UPLOAD ' + JSON.stringify(check.result.value, null, 2));
  process.exit(0);
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
