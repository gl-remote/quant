/**
 * @file vite.config.ts
 * @description Vite 构建配置文件
 * 
 * 【核心配置】
 * - 禁用代码分割，打包为单文件（便于内联到 HTML）
 * - CSS 内联到 JS 中，避免外部 CSS 文件
 * - 别名配置，支持 @/ 开头的路径导入
 * - 相对路径 base，支持 file:// 协议访问
 * 
 * 【数据流】
 * 源代码 → TypeScript 编译 → Vite 构建 → 单文件 index.js → 内联到 HTML
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

/**
 * 计算当前文件目录路径
 * 用于解决 ESM 模块中 __dirname 的兼容性问题
 */
const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Vite 构建配置
 * 
 * @returns {import('vite').UserConfig} Vite 配置对象
 */
export default defineConfig({
  plugins: [react()],
  base: "./", // 使用相对路径，支持 file:// 协议访问
  build: {
    outDir: process.env.VITE_OUT_DIR || "dist", // 输出目录，支持环境变量配置
    rollupOptions: {
      output: {
        // 输出单个文件，便于内联到 HTML
        entryFileNames: "index.js",
        chunkFileNames: "index.js",
        assetFileNames: "index[extname]",
        // 禁用代码分割，强制打包为单文件
        manualChunks: undefined,
      },
    },
    // 启用 CSS 内联到 JS 中，避免外部 CSS 文件依赖
    cssCodeSplit: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"), // 路径别名，@ 指向 src 目录
    },
  },
});