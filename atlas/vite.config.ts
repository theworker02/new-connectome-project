import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const pagesBuild = process.env.npm_lifecycle_event === "build:pages";
const base = process.env.VITE_BASE ?? (pagesBuild ? "/new-connectome-project/" : "/");
const staticMode = process.env.VITE_STATIC ?? (pagesBuild ? "true" : "false");

export default defineConfig({
  base,
  plugins: [react()],
  define: {
    "import.meta.env.VITE_STATIC": JSON.stringify(staticMode),
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
