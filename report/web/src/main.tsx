/**
 * @file main.tsx
 * @description 应用程序入口文件
 * 使用 React 18 的 createRoot API 渲染应用程序
 * 包裹在 StrictMode 中以启用开发模式的严格检查
 */

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

/**
 * 渲染应用程序根组件
 */
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
