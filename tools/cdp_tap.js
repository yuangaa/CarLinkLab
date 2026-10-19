// Drive the phone's Chrome over CDP: find the Uptodown download button and tap it for real.
const CDP = "http://127.0.0.1:9222";
const targets = await (await fetch(`${CDP}/json`)).json();
const target = targets.find(t => t.type === "page" && t.url.includes("uptodown.com/android/download"));
if (!target) {
  console.log("no uptodown page target; pages:", targets.map(t => t.url).join(" | "));
  process.exit(1);
}
console.log("target:", target.url);

const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
ws.addEventListener("message", ev => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
});
await new Promise(res => ws.addEventListener("open", res));
const send = (method, params = {}) => new Promise(res => {
  const myId = ++id;
  pending.set(myId, res);
  ws.send(JSON.stringify({ id: myId, method, params }));
});

await send("Runtime.enable");
const evaluate = async expr => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { error: r.result.exceptionDetails.text };
  return r.result?.result?.value;
};

console.log("title:", await evaluate("document.title"));
console.log("url:", await evaluate("location.href"));
console.log("btn exists:", await evaluate("!!document.getElementById('detail-download-button')"));

await evaluate("document.getElementById('detail-download-button')?.scrollIntoView({block:'center'})");
await new Promise(r => setTimeout(r, 1200));
const rect = await evaluate(`(() => { const b = document.getElementById('detail-download-button'); if(!b) return null; const r = b.getBoundingClientRect(); return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height,cls:b.className}); })()`);
console.log("rect:", rect);
if (rect) {
  const { x, y, w, h } = JSON.parse(rect);
  const cx = Math.round(x + w / 2), cy = Math.round(y + h / 2);
  console.log("tapping at", cx, cy);
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: cx, y: cy, button: "left", clickCount: 1 });
  await new Promise(r => setTimeout(r, 120));
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: cx, y: cy, button: "left", clickCount: 1 });
  await new Promise(r => setTimeout(r, 4000));
  console.log("after click url:", await evaluate("location.href"));
}
ws.close();
