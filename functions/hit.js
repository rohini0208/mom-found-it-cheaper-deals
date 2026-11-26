// Cloudflare Pages Function: our own click/save counter (no third party, no cookies).
// POST /hit  {"k":"B0XXXX","t":"click"|"save"}  -> increments KV counter  hit:<t>:<k>
// GET  /hit?k=B0XXXX,B0YYYY                     -> {"B0XXXX":{"click":12,"save":3},...}
// Needs a KV namespace bound as COUNTS in Cloudflare Pages -> Settings -> Bindings. Without it, GET returns {}.
export async function onRequest({ request, env }) {
  const h = { "content-type": "application/json", "access-control-allow-origin": "*", "cache-control": "no-store" };
  if (!env.COUNTS) return new Response("{}", { headers: h });
  const url = new URL(request.url);
  if (request.method === "POST") {
    let b = {};
    try { b = await request.json(); } catch (e) { return new Response("{}", { status: 400, headers: h }); }
    const k = String(b.k || "").slice(0, 40).replace(/[^A-Za-z0-9_-]/g, "");
    const t = b.t === "save" ? "save" : "click";
    if (!k) return new Response("{}", { status: 400, headers: h });
    const key = `hit:${t}:${k}`;
    const n = parseInt((await env.COUNTS.get(key)) || "0", 10) + 1;
    await env.COUNTS.put(key, String(n));
    return new Response(JSON.stringify({ [k]: { [t]: n } }), { headers: h });
  }
  const ks = (url.searchParams.get("k") || "").split(",").map(s => s.replace(/[^A-Za-z0-9_-]/g, "")).filter(Boolean).slice(0, 120);
  const out = {};
  await Promise.all(ks.map(async k => {
    const [c, s] = await Promise.all([env.COUNTS.get(`hit:click:${k}`), env.COUNTS.get(`hit:save:${k}`)]);
    out[k] = { click: parseInt(c || "0", 10), save: parseInt(s || "0", 10) };
  }));
  return new Response(JSON.stringify(out), { headers: h });
}
