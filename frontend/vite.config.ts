import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(() => ({
  envDir: "..",
  server: {
    host: "::",
    port: 8080,
    watch: {
      usePolling: !!process.env.VITE_USE_POLLING,
    },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      workbox: {
        // Cache app shell (HTML, CSS, JS, fonts)
        globPatterns: ["**/*.{js,css,html,ico,svg,png,woff2}"],
        // Don't cache API calls — only static assets
        navigateFallback: "/index.html",
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/.*\/api\//,
            handler: "NetworkOnly",
          },
        ],
      },
      manifest: false, // We already have manifest.json in public/
    }),
  ],
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          markdown: ['react-markdown', 'remark-gfm', 'remark-breaks'],
          syntax: ['react-syntax-highlighter'],
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
