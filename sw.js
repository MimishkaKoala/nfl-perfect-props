/* NFL Perfect Props — network-first updates, offline fallback */
const CACHE_NAME = 'nfl-perfect-props-v2';
const APP_SHELL = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.allSettled(APP_SHELL.map(url => cache.add(url)));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Always attempt the network first for pages and statistics, then use the
  // last successfully cached response if the device is offline.
  const isData = url.pathname.endsWith('/data.json');
  const isPage = request.mode === 'navigate' || url.pathname.endsWith('/index.html');
  if (isData || isPage) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      // Ignore cache-busting query strings when storing or finding data.json.
      const cacheKey = isData ? new URL('data.json', self.registration.scope).href : request;
      try {
        const response = await fetch(request, { cache: 'no-store' });
        if (response.ok) await cache.put(cacheKey, response.clone());
        return response;
      } catch (error) {
        const cached = await cache.match(cacheKey);
        if (cached) return cached;
        throw error;
      }
    })());
    return;
  }

  // Static assets: network first, cache as fallback.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    try {
      const response = await fetch(request);
      if (response.ok) await cache.put(request, response.clone());
      return response;
    } catch (error) {
      const cached = await cache.match(request);
      if (cached) return cached;
      throw error;
    }
  })());
});
