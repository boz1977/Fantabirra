// Service worker Fantabirra (PWA)
const CACHE = 'fantabirra-v1';
const ASSETS = [
  '/static/css/style.css',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                  // mai intercettare POST (offerte, login, ecc.)
  if (new URL(req.url).origin !== self.location.origin) return;
  // network-first: dati sempre aggiornati; fallback alla cache se offline
  e.respondWith(
    fetch(req)
      .then((resp) => {
        // aggiorna in cache solo asset statici
        if (req.url.includes('/static/')) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return resp;
      })
      .catch(() => caches.match(req))
  );
});
