// Cloudflare Pages Function: our own click/save counter (no third party, no cookies).
// POST /hit  {"k":"B0XXXX"}  -> increments KV counter hit:click:<k> (same-site origin only)
// GET  /hit?k=B0XXXX,B0YYYY                     -> {"B0XXXX":{"click":12,"save":3},...}
// Add a Cloudflare rate-limit rule on /hit (e.g. 20 req/min per IP). Needs a KV namespace bound as COUNTS in Cloudflare Pages -> Settings -> Bindings. Without it, GET returns {}.
const OK_HOSTS = new Set(["momfounditcheaper.com", "www.momfounditcheaper.com", "mom-found-it-cheaper-deals.pages.dev"]);
const KEY = /^(?:[A-Z0-9]{10}|[0-9a-f]{10})$/;   // ASIN or our 10-hex deal id, nothing else
export async function onRequest({ request, env }) {
  const h = { "content-type": "application/json", "cache-control": "no-store" };
  if (!env.COUNTS) return new Response("{}", { headers: h });
  if (request.method !== "GET" && request.method !== "POST") return new Response("", { status: 405 });
  const url = new URL(request.url);
  const origin = request.headers.get("Origin") || request.headers.get("Referer") || "";
  let ohost = ""; try { ohost = new URL(origin).hostname; } catch (e) {}
  if (request.method === "POST" && !OK_HOSTS.has(ohost)) return new Response("{}", { status: 403, headers: h });
  if (request.method === "POST") {
    let b = {};
    try { b = await request.json(); } catch (e) { return new Response("{}", { status: 400, headers: h }); }
    const k = String(b.k || "");
    const t = "click";
    if (!KEY.test(k)) return new Response("{}", { status: 400, headers: h });
    const key = `hit:${t}:${k}`;
    const n = parseInt((await env.COUNTS.get(key)) || "0", 10) + 1;
    await env.COUNTS.put(key, String(n));
    return new Response(JSON.stringify({ [k]: { [t]: n } }), { headers: h });
  }
  const ks = (url.searchParams.get("k") || "").split(",").filter(k => KEY.test(k)).slice(0, 120);
  const out = {};
  await Promise.all(ks.map(async k => {
    const [c, s] = await Promise.all([env.COUNTS.get(`hit:click:${k}`), env.COUNTS.get(`hit:save:${k}`)]);
    out[k] = { click: parseInt(c || "0", 10), save: parseInt(s || "0", 10) };
  }));
  return new Response(JSON.stringify(out), { headers: h });
}
