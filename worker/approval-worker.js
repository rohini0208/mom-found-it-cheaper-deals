/* Cloudflare Worker: approval + status bridge between the dashboard and n8n.
 * Free tier is plenty. Deploy with wrangler (see wrangler.toml). Bind a KV namespace named CCC.
 *
 *  POST /approve   {workflow,date,id,decision}     -> store a decision (dashboard calls this)
 *  GET  /approvals?workflow=mfic&date=2026-11-27   -> { approved:[id], rejected:[id] }   (n8n reads)
 *  POST /status    {workflow,date,id,status,error,at} -> store publish result (n8n writes)
 *  GET  /status?workflow=mfic&date=...             -> { items:{id:{status,error,at}} } (dashboard reads)
 *
 * Lock it down: set an APPROVE_TOKEN secret and require it on writes if this URL is public.
 */
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type,Authorization",
};
const j = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "Content-Type": "application/json", ...CORS } });

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
    const url = new URL(req.url);
    const p = url.pathname.replace(/\/$/, "");

    if (req.method === "POST" && p === "/approve") {
      const b = await req.json().catch(() => ({}));
      if (!b.workflow || !b.date || !b.id) return j({ error: "workflow,date,id required" }, 400);
      const key = `appr:${b.workflow}:${b.date}`;
      const cur = JSON.parse((await env.CCC.get(key)) || "{}");
      cur[b.id] = b.decision || "approve";
      await env.CCC.put(key, JSON.stringify(cur));
      return j({ ok: true });
    }

    if (req.method === "GET" && p === "/approvals") {
      const wf = url.searchParams.get("workflow"), date = url.searchParams.get("date");
      const cur = JSON.parse((await env.CCC.get(`appr:${wf}:${date}`)) || "{}");
      return j({
        approved: Object.keys(cur).filter((k) => cur[k] === "approve"),
        rejected: Object.keys(cur).filter((k) => cur[k] === "reject"),
      });
    }

    if (req.method === "POST" && p === "/status") {
      const b = await req.json().catch(() => ({}));
      if (!b.workflow || !b.date || !b.id) return j({ error: "workflow,date,id required" }, 400);
      const key = `stat:${b.workflow}:${b.date}`;
      const cur = JSON.parse((await env.CCC.get(key)) || "{}");
      cur[b.id] = { status: b.status || "published", error: b.error || "", at: b.at || new Date().toISOString() };
      await env.CCC.put(key, JSON.stringify(cur));
      return j({ ok: true });
    }

    if (req.method === "GET" && p === "/status") {
      const wf = url.searchParams.get("workflow"), date = url.searchParams.get("date");
      return j({ items: JSON.parse((await env.CCC.get(`stat:${wf}:${date}`)) || "{}") });
    }

    return j({ error: "not found" }, 404);
  },
};
