// Hook fetch/XHR in the phone's Chrome tab, tap the download button, and report the network calls.
// usage: node cdp_hook.js <url-substring>
const CDP = "http://127.0.0.1:9222";
setTimeout(() => { console.log("TIMEOUT"); process.exit(2); }, 40000);
const urlPart = process.argv[2] || "uptodown";

const targets = await (await fetch(`${CDP}/json`)).json();
const matches = targets.filter(t => t.type === "page" && t.url.includes(urlPart));
const target = matches[matches.length - 1];
if (!target) { console.log("no target"); process.exit(1); }
console.log("target:", target.url);

const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
ws.addEventListener("message", e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
await new Promise(r => ws.addEventListener("open", r));
const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Runtime.enable");
const ev = async expr => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result?.exceptionDetails ? "EXCEPTION " + r.result.exceptionDetails.text : r.result?.result?.value;
};

// install hooks
await ev(`(() => {
  window.__log = [];
  if (!window.__hooked) {
    window.__hooked = 1;
    const of = window.fetch;
    window.fetch = function(...a) {
      const url = (a[0] && a[0].url) || a[0];
      return of.apply(this, a).then(async r => {
        let body = ''; try { body = (await r.clone().text()).slice(0, 400); } catch (e) {}
        window.__log.push({ t: 'fetch', url: String(url).slice(0, 200), status: r.status, body });
        return r;
      });
    };
    const oo = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(m, u, ...rest) {
      this.__u = u; this.__m = m;
      this.addEventListener('load', () => {
        window.__log.push({ t: 'xhr', m: this.__m, url: String(this.__u).slice(0, 200), status: this.status, body: String(this.responseText || '').slice(0, 400) });
      });
      return oo.call(this, m, u, ...rest);
    };
  }
  return 'hooked';
})()`);

const rect = await ev(`(() => { const b = document.getElementById('detail-download-button'); if (!b) return null; b.scrollIntoView({block:'center'}); const r = b.getBoundingClientRect(); return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}); })()`);
console.log("button center:", rect);
if (rect) {
  const { x, y } = JSON.parse(rect);
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await new Promise(r => setTimeout(r, 150));
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  await new Promise(r => setTimeout(r, 9000));
}
console.log("log:", await ev("JSON.stringify(window.__log)"));
console.log("href:", await ev("location.href"));
ws.close();
process.exit(0);
