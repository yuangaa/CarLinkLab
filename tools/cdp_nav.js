// Open a URL in a new Chrome tab on the phone via CDP, wait, then evaluate an expression.
// usage: node cdp_nav.js <url> [waitMs] [expression]
const CDP = "http://127.0.0.1:9222";
const url = process.argv[2];
const waitMs = Number(process.argv[3] || 8000);
const expr = process.argv[4] || "JSON.stringify({title:document.title,url:location.href,ready:document.readyState})";
setTimeout(() => { console.log("TIMEOUT"); process.exit(2); }, waitMs + 30000);

const ver = await (await fetch(`${CDP}/json/version`)).json();
const ws = new WebSocket(ver.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
ws.addEventListener("message", e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
await new Promise(r => ws.addEventListener("open", r));
const send = (method, params = {}, sessionId) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params, sessionId })); });

const created = await send("Target.createTarget", { url });
const targetId = created.result.targetId;
console.log("targetId:", targetId);
await new Promise(r => setTimeout(r, waitMs));
const att = await send("Target.attachToTarget", { targetId, flatten: true });
const sid = att.result.sessionId;
await send("Runtime.enable", {}, sid);
const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, sid);
console.log("result:", r.result?.exceptionDetails ? "EXCEPTION " + JSON.stringify(r.result.exceptionDetails).slice(0, 300) : JSON.stringify(r.result?.result?.value).slice(0, 4000));
ws.close();
process.exit(0);
