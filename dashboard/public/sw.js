// FedStrip service worker: app shell cache-first, data network-first, offline fallback to cache.
const VERSION = 'fedstrip-v1';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

const isData = (url) => url.pathname.includes('/api/data') || url.hostname === 'raw.githubusercontent.com';

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Live data: always try the network, fall back to the last copy when offline.
  if (isData(url)) {
    e.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          if (res.ok) caches.open(VERSION).then((c) => c.put(stripBust(req), copy));
          return res;
        })
        .catch(() => caches.match(stripBust(req))),
    );
    return;
  }
  if (url.origin !== self.location.origin) return;

  // Navigations: network first so new deploys show up, cached shell when offline.
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match('./index.html')));
    return;
  }

  // Hashed build assets and icons: cache first.
  e.respondWith(
    caches.match(req).then(
      (hit) =>
        hit ||
        fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(req, copy));
          }
          return res;
        }),
    ),
  );
});

// The app adds ?t=<minute> to data URLs; cache them under one key.
function stripBust(req) {
  const u = new URL(req.url);
  u.searchParams.delete('t');
  return u.toString();
}
