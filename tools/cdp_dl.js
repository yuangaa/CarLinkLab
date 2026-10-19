// Inspect / tap download buttons on a Chrome tab on the phone over CDP.
// usage: node cdp_dl.js <url-substring> [index-to-tap]
const CDP = "http://127.0.0.1:9222";
setTimeout(() => { console.log("TIMEOUT"); process.exit(2); }, 25000);

const urlPart = process.argv[2] || "";
const tapIndex = process.argv[3] !== undefined ? Number(process.argv[3]) : null;

const targets = await (await fetch(`${CDP}/json`)).json();
const matches = targets.filter(t => t.type === "page" && t.url.includes(urlPart));
const target = matches[matches.length - 1];
if (!target) { console.log("no target"); process.exit(1); }
console.log("target:", target.url);

const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
ws.addEventListener("message", ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
await new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", rej); });
const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Runtime.enable");
const ev = async expr => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result?.exceptionDetails ? "EXCEPTION " + r.result.exceptionDetails.text : r.result?.result?.value;
};

const list = await ev(`JSON.stringify(Array.from(document.querySelectorAll('a,button')).map((e,i)=>{
  const t=(e.innerText||e.value||'').trim().slice(0,40); const r=e.getBoundingClientRect();
  return {i, tag:e.tagName, t, h:(e.href||'').slice(0,120), x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2), w:Math.round(r.width)};
}).filter(o=>/download|apk|下/i.test(o.t+o.h) && o.w>0))`);
console.log("candidates:", list);

if (tapIndex !== null) {
  await ev(`(()=>{const e=document.querySelectorAll('a,button')[${tapIndex}]; e.scrollIntoView({block:'center'}); return 1})()`);
  await new Promise(r => setTimeout(r, 800));
  const rect = await ev(`(()=>{const e=document.querySelectorAll('a,button')[${tapIndex}]; const r=e.getBoundingClientRect(); return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)})})()`);
  console.log("tap at", rect, "->", await ev(`document.querySelectorAll('a,button')[${tapIndex}].innerText||document.querySelectorAll('a,button')[${tapIndex}].href`));
  const { x, y } = JSON.parse(rect);
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await new Promise(r => setTimeout(r, 120));
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  await new Promise(r => setTimeout(r, 5000));
  console.log("url after:", await ev("location.href"));
}
ws.close();
process.exit(0);
