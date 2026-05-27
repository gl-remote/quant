/**
 * 应用根组件
 * 
 * 【功能说明】
 * - 配置 HashRouter 路由（支持 file:// 协议）
 * - 定义三个主要路由：
 *   1. "/" → 导航页面（显示所有回测记录）
 *   2. "/run/:id" → 回测详情页面（显示K线、资金曲线、指标等）
 *   3. "/run/:id/optuna" → 参数优化页面（显示Optuna优化结果）
 * 
 * 【技术选型】
 * - 使用 HashRouter 而非 BrowserRouter，避免 file:// 协议下的路由问题
 * - 所有页面使用统一的 Layout 布局组件
 * 
 * 【数据流】
 * - 用户访问路由 → Router 匹配 → 渲染对应页面 → 页面加载数据 → 展示结果
 */

import { HashRouter, Routes, Route } from "react-router-dom";
import NavPage from "@/pages/NavPage";
import RunPage from "@/pages/RunPage";
import OptunaPage from "@/pages/OptunaPage";
import Layout from "@/components/Layout";

/**
 * 应用根组件
 * 
 * @returns React 元素树
 */
export default function App() {
  return (
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<NavPage />} />
          <Route path="/run/:id" element={<RunPage />} />
          <Route path="/run/:id/optuna" element={<OptunaPage />} />
        </Routes>
      </Layout>
    </HashRouter>
  );
}