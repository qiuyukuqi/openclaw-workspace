const CACHE_NAME='tsp-v1';
self.addEventListener('install',e=>{self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(clients.claim())});
self.addEventListener('fetch',e=>{
  if(e.request.url.includes('/api/'))return;
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{
    if(res.ok){const c=res.clone();caches.open(CACHE_NAME).then(cache=>cache.put(e.request,c))}
    return res;
  }).catch(()=>new Response('离线',{status:503}))));
});
self.addEventListener('notificationclick',e=>{
  e.notification.close();
  e.waitUntil(clients.matchAll({type:'window'}).then(cs=>{if(cs.length)cs[0].focus();else clients.openWindow('/')}));
});
