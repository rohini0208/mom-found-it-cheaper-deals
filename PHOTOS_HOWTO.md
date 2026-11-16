# Product photos, no tokens needed

1. Run the "Photos needed" list: `python need_photos.py` (or open PHOTOS_NEEDED.md in the repo).
2. On your Lenovo, signed in to Amazon Associates, open each product link.
3. Click this bookmarklet (create a bookmark whose URL is the line below). It saves the main photo as `<ASIN>.jpg`:

```
javascript:(async()=>{const a=(location.pathname.match(/\/dp\/([A-Z0-9]{10})/)||[])[1];const s=document.querySelector('#landingImage');if(!a||!s){alert('Open a product page first');return}const u=(s.getAttribute('data-old-hires')||s.src).replace(/\._[^.]*_\./,'._SL600_.');const b=await (await fetch(u)).blob();const l=document.createElement('a');l.href=URL.createObjectURL(b);l.download=a+'.jpg';l.click()})()
```

4. Upload the downloaded files to the `photos/` folder in the GitHub repo (Add file, Upload files).
5. The next run uses them automatically in posts and Reels.

Use photos only for products you are promoting with your own Associates link. Do one page at a time yourself; do not automate this.
