/**
 * 应用根组件
 * 
 * 【功能说明】
 * - 配置 HashRouter 路由（支持 file:// 协议）
 * - 定义两个主要路由：
 *   1. "/" → 导航页面（显示所有回测记录）
 *   2. "/run/:id" → 回测详情页面
 * - ConfigProvider 统一 AntD 主题，与 Tailwind 共享 CSS 变量
 */

import { ConfigProvider } from "antd";
import { HashRouter, Routes, Route } from "react-router-dom";
import NavPage from "@/pages/NavPage";
import RunPage from "@/pages/run";
import Layout from "@/components/layout/Layout";

/** 从 CSS 变量读取 AntD token，确保与 Tailwind 共用一套主题色 */
function antdTokens() {
  // 仅在浏览器环境读取 CSS 变量
  if (typeof document === "undefined") return {};
  const s = getComputedStyle(document.documentElement);
  const v = (name: string) => s.getPropertyValue(name).trim();
  return {
    colorPrimary: v("--color-primary"),
    colorSuccess: v("--color-success"),
    colorWarning: v("--color-warning"),
    colorError: v("--color-danger"),
    colorBgContainer: v("--color-surface"),
    colorText: v("--color-text"),
    colorTextSecondary: v("--color-text-secondary"),
    colorBorder: v("--color-border"),
    borderRadius: 8,
    borderRadiusLG: 12,
  };
}

export default function App() {
  return (
    <ConfigProvider theme={{ token: antdTokens() }}>
      <HashRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<NavPage />} />
            <Route path="/run/:id" element={<RunPage />} />
          </Routes>
        </Layout>
      </HashRouter>
    </ConfigProvider>
  );
}