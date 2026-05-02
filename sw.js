const CACHE_NAME = "neko-xiaojinku-v1";
const ASSETS = ["./", "./index.html", "./main.jsx", "./neko-xiao-jin-ku.jsx", "./manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)));
});

self.addEventListener("fetch", (event) => {
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
