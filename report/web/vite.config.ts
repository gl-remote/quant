import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: process.env.VITE_OUT_DIR || "dist",
    rollupOptions: {
      output: {
        // 输出单个文件，便于内联
        entryFileNames: "index.js",
        chunkFileNames: "index.js",
        assetFileNames: "index[extname]",
        // 禁用代码分割，打包为单文件
        manualChunks: undefined,
      },
    },
    // 启用 CSS 内联到 JS 中
    cssCodeSplit: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});