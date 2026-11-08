/* AquaSentry offline support (service worker).
   The dashboard keeps working without a connection: pages and assets are cached on first visit.
   - pages: network first, cached copy when offline (so a new version shows up as soon as you are online)
   - scripts, styles, fonts, images: cache first (they change only with a new version below)
   - /api/ and live events are never cached: readings must always be fresh. */
const VERSION = 'aquasentry-v5.6';
// The 3D model, the map library and the extra languages are cached the first time they are used.
const PRECACHE = ['index.html', 'device.html', 'app.css', 'field.css', 'device.css', 'i18n.js', 'i18n-v5.js', 'shell.js', 'charts.js',
  'neural.js', 'app.js', 'field-ui.js', 'device.js', 'vendor/qrcode.js', 'logo.svg', 'manifest.json', 'fonts/anek-latin-wdth-wght.woff2', 'fonts/mukta-latin-400-normal.woff2', 'fonts/mukta-latin-600-normal.woff2'];

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

/* Alerts pushed by the server (v5.6). Every push shows a notification: iOS cancels subscriptions that don't. */
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'AquaSentry', {
    body: d.body || 'New water-safety alert', tag: d.tag || 'aquasentry', renotify: true,
    icon: 'logo.svg', badge: 'logo.svg', data: { url: d.url || 'index.html' },
  }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || 'index.html', self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
    const w = wins.find((c) => c.url === url);
    return w ? w.focus() : self.clients.openWindow(url);
  }));
});
