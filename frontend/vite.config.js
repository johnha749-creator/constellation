import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // GitHub Pages serves the hosted demo from /constellation/ (see .github/workflows/pages.yml).
  base: process.env.VITE_BASE || "/",
  server: {
    port: 5173,
    // Forward API calls to the FastAPI backend so the browser sees one origin.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: {
    rollupOptions: {
      // Two pages: the app, and the pitch deck at /pitch.html.
      input: {
        main: fileURLToPath(new URL("index.html", import.meta.url)),
        pitch: fileURLToPath(new URL("pitch.html", import.meta.url)),
      },
    },
  },
});
