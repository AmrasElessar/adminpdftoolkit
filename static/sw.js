// Admin PDF Toolkit — service worker
//
// Caching policy:
//   - Static immutable assets (icons, manifest, versioned JS) → cache-first
//   - HTML page itself ("/") → NETWORK-FIRST so server-side template changes
//     (new buttons, i18n updates, header layout, etc.) show up on the next
//     reload instead of being shadowed by a stale cached copy.
//   - API endpoints → never cached.
//
// Cache busting: bump APP_VERSION on every release. The activate handler
// purges any cache whose name does not match the current key, forcing the
// browser to refetch every static asset under the new namespace.
const APP_VERSION = "1.0.6";
const CACHE = `ht-pdf-${APP_VERSION}`;

// Pre-cache a tiny set of icons / manifest. NOT the HTML — see fetch handler.
const STATIC_ASSETS = [
  "/static/manifest.json",
  "/static/icon-192.svg",
  "/static/icon-512.svg",
  `/static/i18n.js?v=${APP_VERSION}`,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(STATIC_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    Promise.all([
      caches.keys().then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      ),
      self.clients.claim(),
    ])
  );
});

const API_PREFIXES = [
  "/convert", "/batch", "/ocr", "/preview", "/history", "/admin", "/events",
];

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  // API endpoints are dynamic — always go to the network so the user never
  // sees a stale job state.
  if (API_PREFIXES.some((p) => url.pathname.startsWith(p))) return;

  // The HTML page: NETWORK-FIRST. Fall back to a cached copy only when
  // offline so the PWA shell still loads. This is what was wrong in v1.0.0:
  // we used cache-first here, which silently froze the UI when the server
  // shipped a new template.
  if (url.pathname === "/" || url.pathname.endsWith(".html")) {
    event.respondWith(
      fetch(event.request).then((res) => {
        // Refresh the cached copy in the background.
        const clone = res.clone();
        caches.open(CACHE).then((c) => c.put(event.request, clone)).catch(() => {});
        return res;
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  // Static assets under /static/ → cache-first (versioned URLs handle busting).
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then((hit) =>
        hit || fetch(event.request).then((res) => {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, clone)).catch(() => {});
          return res;
        }).catch(() => hit)
      )
    );
  }
});
