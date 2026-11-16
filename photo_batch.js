// Run on any www.amazon.com page (console, bookmarklet or Claude): fetches product photos + ratings for a list
// of ASINs from inside your own browser, then saves ONE photos.zip (Chrome allows one download per page).
// Set window.ASINS = ["B0...", ...] first (max ~8 per run), then run this file.
(async () => {
  const asins = window.ASINS || [];
  const crcT = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc = (u8) => { let c = 0xFFFFFFFF; for (const b of u8) c = crcT[(c ^ b) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  const enc = new TextEncoder(), files = [], meta = {}, log = [];
  for (const a of asins) {
    try {
      const html = await (await fetch("/dp/" + a, { credentials: "same-origin" })).text();
      if (/captcha|robot check/i.test(html) && !html.includes("landingImage")) { log.push(a + ": captcha, stopped"); break; }
      const doc = new DOMParser().parseFromString(html, "text/html");
      const rt = (doc.querySelector("#acrPopover")?.getAttribute("title") || "").match(/([\d.]+) out of 5/);
      const rc = (doc.querySelector("#acrCustomerReviewText")?.textContent || "").match(/([\d,]+)/);
      const lp = (doc.querySelector(".basisPrice .a-offscreen, [data-a-strike='true'] .a-offscreen")?.textContent || "").match(/\$[\d,.]+/);
      meta[a] = { rating: rt ? +rt[1] : null, reviews: rc ? +rc[1].replace(/,/g, "") : null, list: lp ? lp[0] : null };
      const m = html.match(/"hiRes":"(https:[^"]+)"/) || html.match(/data-old-hires="([^"]+)"/);
      if (!m) { log.push(a + ": no photo"); continue; }
      const buf = new Uint8Array(await (await fetch(m[1].replace(/\._[^.]*_\./, "._SL600_."))).arrayBuffer());
      files.push({ name: a + ".jpg", data: buf }); log.push(a + ": ok " + buf.length);
    } catch (e) { log.push(a + ": " + e); }
    await new Promise((r) => setTimeout(r, 1200));
  }
  const parts = [], central = []; let off = 0;
  for (const f of files) {
    const n = enc.encode(f.name), c = crc(f.data);
    const h = new DataView(new ArrayBuffer(30)); h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint32(14, c, true);
    h.setUint32(18, f.data.length, true); h.setUint32(22, f.data.length, true); h.setUint16(26, n.length, true);
    parts.push(h.buffer, n, f.data);
    const g = new DataView(new ArrayBuffer(46)); g.setUint32(0, 0x02014b50, true); g.setUint16(4, 20, true); g.setUint16(6, 20, true);
    g.setUint32(16, c, true); g.setUint32(20, f.data.length, true); g.setUint32(24, f.data.length, true); g.setUint16(28, n.length, true); g.setUint32(42, off, true);
    central.push(g.buffer, n); off += 30 + n.length + f.data.length;
  }
  const csize = central.reduce((s, p) => s + (p.byteLength ?? p.length), 0);
  const e = new DataView(new ArrayBuffer(22)); e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true); e.setUint32(12, csize, true); e.setUint32(16, off, true);
  const blob = new Blob([...parts, ...central, e.buffer], { type: "application/zip" });
  const l = document.createElement("a"); l.href = URL.createObjectURL(blob); l.download = "photos.zip"; document.body.appendChild(l); l.click();
  window.__result = JSON.stringify({ log, meta });
})();
