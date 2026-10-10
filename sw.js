const CACHE='catalyst-radar-v9-offhours-news-health';
const STATIC=['./','./index.html','./styles.css','./app.js','./manifest.webmanifest','./assets/icon.svg','./assets/icon-192.png','./assets/icon-512.png'];
self.addEventListener('install',e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(STATIC)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',e=>{
  e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',e=>{
  const u=new URL(e.request.url);
  // TradingView e tutte le richieste a terzi sono gestite dal browser, non dalla cache PWA.
  if(u.origin!==self.location.origin)return;
  if(e.request.method!=='GET')return;
  if((u.pathname.endsWith('/data/latest.json')||u.pathname.endsWith('/data/history.json'))){
    e.respondWith(fetch(e.request,{cache:'no-store'}).catch(()=>caches.match(e.request)));
    return;
  }
  if(e.request.mode==='navigate'||u.pathname.endsWith('/app.js')||u.pathname.endsWith('/styles.css')){
    e.respondWith(fetch(e.request).then(resp=>{
      if(resp.ok){
        const copy=resp.clone();
        e.waitUntil(caches.open(CACHE).then(c=>c.put(e.request,copy)));
      }
      return resp;
    }).catch(()=>caches.match(e.request)));
    return;
  }
  e.respondWith(caches.match(e.request).then(cached=>cached||fetch(e.request).then(resp=>{
    if(resp.ok){
      const copy=resp.clone();
      e.waitUntil(caches.open(CACHE).then(c=>c.put(e.request,copy)));
    }
    return resp;
  })));
});
