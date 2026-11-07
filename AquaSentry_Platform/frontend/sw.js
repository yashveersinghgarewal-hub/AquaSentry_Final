/* AquaSentry offline support (service worker).
   The dashboard keeps working without a connection: pages and assets are cached on first visit.
   - pages: network first, cached copy when offline (so a new version shows up as soon as you are online)
   - scripts, styles, fonts, images: cache first (they change only with a new version below)
   - /api/ and live events are never cached: readings must always be fresh. */
const VERSION = 'aquasentry-v5.4';
const PRECACHE = ['index.html', 'app.css', 'field.css', 'i18n.js', 'i18n-v5.js', 'shell.js', 'charts.js', 'neural.js', 'app.js',
  'logo.svg', 'manifest.json', 'fonts/anek-latin-wdth-wght.woff2', 'fonts/mukta-latin-400-normal.woff2', 'fonts/mukta-latin-600-normal.woff2'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/')) return;
  if (req.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname === '/') {
    e.respondWith(fetch(req).then((res) => {
      const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); return res;
    }).catch(() => caches.match(req).then((r) => r || caches.match('index.html'))));
    return;
  }
  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); }
    return res;
  })));
});
