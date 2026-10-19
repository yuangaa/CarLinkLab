// Evaluate JS in a Chrome tab on the phone over CDP.
// usage: node cdp_eval.js <url-substring> '<expression>'
const CDP = "http://127.0.0.1:9222";
const [, , urlPart, expr] = process.argv;
const targets = await (await fetch(`${CDP}/json`)).json();
const target = targets.find(t => t.type === "page" && (!urlPart || t.url.includes(urlPart)));
if (!target) {
  console.log("no target matched; pages:\n" + targets.filter(t => t.type === "page").map(t => t.url).join("\n"));
  process.exit(1);
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
ws.addEventListener("message", ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
await new Promise(r => ws.addEventListener("open", r));
const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Runtime.enable");
const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
const out = r.result?.exceptionDetails ? "EXCEPTION: " + r.result.exceptionDetails.text : r.result?.result?.value;
console.log(typeof out === "string" ? out : JSON.stringify(out, null, 1));
ws.close();
