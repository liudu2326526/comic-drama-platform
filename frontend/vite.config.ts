import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) }
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/static": { target: "http://127.0.0.1:8000", changeOrigin: true }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vue-vendor": ["vue", "vue-router", "pinia"],
          axios: ["axios"]
        }
      }
    }
  },
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["tests/setup.ts"]
  }
});
