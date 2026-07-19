"use strict";

const CACHE_NAME = "paperagent-shell-v1.0.0-workbench";
const SHELL_ASSETS = [
  "/app",
  "/app/manifest.webmanifest",
  "/app-static/icon.svg",
  "/app-static/css/tokens.css",
  "/app-static/css/base.css",
  "/app-static/css/components.css",
  "/app-static/css/pages.css",
  "/app-static/js/data.js",
  "/app-static/js/ui.js",
  "/app-static/js/views/core.js",
  "/app-static/js/views/research.js",
  "/app-static/js/views/design.js",
  "/app-static/js/views/review.js",
  "/app-static/js/app.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const isShell = url.pathname === "/app" || url.pathname.startsWith("/app/");
  const isAsset = url.pathname.startsWith("/app-static/");
  if (!isShell && !isAsset) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached || caches.match("/app"));
      return cached || network;
    }),
  );
});
