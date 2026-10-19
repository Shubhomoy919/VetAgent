import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** Preload the few font files every page uses, so text does not reflow when they arrive (CLS). */
function preloadCriticalFonts(): Plugin {
  const critical = [
    /instrument-serif-latin-400-normal-[\w-]+\.woff2$/,
    /instrument-serif-latin-400-italic-[\w-]+\.woff2$/,
    /ibm-plex-sans-latin-400-normal-[\w-]+\.woff2$/,
    /ibm-plex-sans-latin-500-normal-[\w-]+\.woff2$/,
    /ibm-plex-mono-latin-400-normal-[\w-]+\.woff2$/,
  ];
  return {
    name: "preload-critical-fonts",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, ctx) {
        const files = Object.keys(ctx.bundle ?? {}).filter((f) => critical.some((re) => re.test(f)));
        return files.map((f) => ({
          tag: "link",
          attrs: { rel: "preload", href: `/${f}`, as: "font", type: "font/woff2", crossorigin: "" },
          injectTo: "head" as const,
        }));
      },
    },
  };
}

export default defineConfig({
  plugins: [react(), preloadCriticalFonts()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8010", changeOrigin: true },
    },
  },
});
