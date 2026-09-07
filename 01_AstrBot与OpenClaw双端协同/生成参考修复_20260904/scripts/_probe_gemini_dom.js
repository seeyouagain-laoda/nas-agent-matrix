const http = require('http');
const WebSocket = globalThis.WebSocket;
const PORT = 16002;
function getJSON(p) {
  return new Promise((res, rej) => {
    const req = http.get({ host: '127.0.0.1', port: PORT, path: p, timeout: 5000 }, (r) => {
      let d = ''; r.on('data', c => d += c);
      r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } });
    });
    req.on('error', rej); req.on('timeout', () => { req.destroy(); rej(new Error('to ' + p)); });
  });
}
function connect(wsUrl) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(wsUrl); const pending = new Map(); let id = 0;
    const send = (m, p = {}) => new Promise((r, j) => {
      const i = ++id; pending.set(i, { r, j });
      ws.send(JSON.stringify({ id: i, method: m, params: p }));
      setTimeout(() => { if (pending.has(i)) { pending.delete(i); j(new Error('to ' + m)); } }, 20000);
    });
    ws.addEventListener('open', () => res({ ws, send }));
    ws.addEventListener('error', () => rej(new Error('ws err')));
    ws.addEventListener('message', (e) => {
      const m = JSON.parse(e.data.toString());
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.j(new Error(JSON.stringify(m.error))) : p.r(m.result); }
    });
  });
}
(async () => {
  const tabs = await getJSON('/json');
  const t = tabs.find(x => (x.url || '').includes('gemini.google.com')) || tabs.find(x => x.type === 'page');
  if (!t) { console.log('NO_TAB'); return; }
  console.log('TAB', t.url);
  const { send } = await connect(t.webSocketDebuggerUrl);
  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.navigate', { url: 'about:blank' });
  await new Promise(r => setTimeout(r, 500));
  await send('Page.navigate', { url: 'https://gemini.google.com/app' });
  await new Promise(r => setTimeout(r, 11000));
  // 点击 "上传和工具" 按钮
  await send('Runtime.evaluate', { expression: `(()=>{const b=[...document.querySelectorAll('button')].find(x=>(x.getAttribute('aria-label')||'')==='上传和工具');if(b){b.click();return true;}return false;})()`, returnByValue: true });
  await new Promise(r => setTimeout(r, 2000));
  const r = await send('Runtime.evaluate', {
    expression: `(()=>{
      const menuItems=[...document.querySelectorAll('[role=menuitem],[role=menuitembutton],button')].map(b=>({label:b.getAttribute('aria-label'),txt:(b.innerText||'').trim().slice(0,30)})).filter(b=>(b.label||b.txt)&&/upload|image|\\u4e0a\\u4f20|\\u56fe|\\u7247|\\u7167|\\u6587\\u4ef6|file|photo|picture|import|add/i.test((b.label||'')+' '+(b.txt||'')));
      const fileAfter=[...document.querySelectorAll('input[type=file]')].map(i=>({accept:i.getAttribute('accept'),hidden:(i.offsetParent===null)}));
      return {menuItems, fileAfter};
    })()`, returnByValue: true
  });
  console.log('RESULT ' + JSON.stringify(r.result.value, null, 2));
  process.exit(0);
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
