// House of Desserts — minimal service worker.
// A no-op fetch listener is enough to make Android Chrome offer "Install app".
// We're not caching anything; the app runs on Tailscale and doesn't need offline.

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', () => {
    // Intentionally empty. Chrome requires a fetch listener to exist.
    // Requests pass through to the network normally.
});