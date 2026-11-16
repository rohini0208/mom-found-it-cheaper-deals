// ==UserScript==
// @name         Mom Found It Cheaper - photo fetcher
// @match        https://www.amazon.com/dp/*
// @match        https://www.amazon.com/*autophoto*
// @grant        none
// ==/UserScript==
// Runs in YOUR signed-in Chrome (Tampermonkey). No Claude, no tokens. Temporary helper until the Creators API is available.
// Use: open the first link from PHOTOS_NEEDED.md and add  #autophoto=<ASIN1>,<ASIN2>,...  to the URL
//      e.g. https://www.amazon.com/dp/B0HFWY2LQT#autophoto=B0HFWY2LQT,B09H7C4NPV,B0FJDS4V86
// It saves each main photo as <ASIN>.jpg to Downloads, then opens the next product. It stops by itself
// on a captcha, sign-in or error page (it never tries to get past them) and after 30 products.
(async () => {
  const m = location.hash.match(/autophoto=([A-Z0-9,]+)/);
  if (!m) return;
  const list = m[1].split(",").filter(Boolean).slice(0, 30);
  const here = (location.pathname.match(/\/dp\/([A-Z0-9]{10})/) || [])[1];
  const stop = (why) => { console.log("[photo fetcher] stopped:", why); document.title = "STOPPED: " + why; };
  if (!here || list[0] !== here) return stop("link does not match list");
  const page = document.body.innerText.toLowerCase();
  if (/captcha|enter the characters|robot check|sign in/.test(page) && !document.querySelector("#landingImage"))
    return stop("captcha or sign-in page, do it by hand");
  await new Promise((r) => setTimeout(r, 4000));
  const img = document.querySelector("#landingImage");
  if (!img) return stop("no photo on page " + here);
  const url = (img.getAttribute("data-old-hires") || img.src).replace(/\._[^.]*_\./, "._SL600_.");
  try {
    const blob = await (await fetch(url)).blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = here + ".jpg";
    a.click();
  } catch (e) { return stop("download failed " + e); }
  const rest = list.slice(1);
  if (!rest.length) return stop("done, all photos saved to Downloads");
  await new Promise((r) => setTimeout(r, 8000));          // fixed 8 s pause between products
  location.href = "https://www.amazon.com/dp/" + rest[0] + "#autophoto=" + rest.join(",");
})();
