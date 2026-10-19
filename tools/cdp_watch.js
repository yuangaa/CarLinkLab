// Watch network + console while clicking the Uptodown download button (CDP event level).
const CDP = "http://127.0.0.1:9222";
setTimeout(() => { console.log("TIMEOUT"); process.exit(2); }, 45000);

const targets = await (await fetch(`${CDP}/json`)).json();
const matches = targets.filter(t => t.type === "page" && t.url.includes("uptodown"));
const target = matches[matches.length - 1];
if (!target) { console.log("no target"); process.exit(1); }
console.log("target:", target.url);

const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
const events = [];
ws.addEventListener("message", e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === "Network.requestWillBeSent") events.push({ k: "req", url: (m.params.request.url || "").slice(0, 180), method: m.params.request.method });
  if (m.method === "Network.responseReceived") events.push({ k: "res", url: (m.params.response.url || "").slice(0, 180), status: m.params.response.status });
  if (m.method === "Runtime.consoleAPICalled") events.push({ k: "console", t: m.params.type, a: (m.params.args || []).map(x => String(x.value || x.description || "").slice(0, 120)).join(" | ") });
  if (m.method === "Runtime.exceptionThrown") events.push({ k: "exc", t: (m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text || "").slice(0, 200) });
  if (m.method === "Log.entryAdded") events.push({ k: "log", t: (m.params.entry.text || "").slice(0, 160), lvl: m.params.entry.level });
});
await new Promise(r => ws.addEventListener("open", r));
const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Runtime.enable"); await send("Network.enable"); await send("Log.enable");
const ev = async expr => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result?.exceptionDetails ? "EXCEPTION " + r.result.exceptionDetails.text : r.result?.result?.value;
};

console.log("readyState:", await ev("document.readyState"), "| jq:", await ev("typeof window.jQuery"), "| btn:", await ev("!!document.getElementById('detail-download-button')"));
events.length = 0;
console.log("click ->", await ev("document.getElementById('detail-download-button').click(), 'clicked'"));
await new Promise(r => setTimeout(r, 12000));
console.log("events:", JSON.stringify(events.slice(-25), null, 1));
console.log("href:", await ev("location.href"));
ws.close();
process.exit(0);
