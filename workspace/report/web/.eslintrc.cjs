/**
 * @file .eslintrc.cjs
 * @description ESLint 代码检查配置文件
 * 
 * 【核心规则】
 * - react-hooks/rules-of-hooks: 错误级别，防止 React Hooks 调用顺序问题
 * - react-hooks/exhaustive-deps: 警告级别，提示 useEffect 依赖项缺失
 * 
 * 【作用】
 * 在编码阶段就拦截常见错误，防止浏览器出现 React Error #310 等问题
 */

module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  plugins: ["@typescript-eslint", "react-hooks"],
  rules: {
    // 核心规则：hooks 必须在组件顶层按相同顺序调用
    // 这条规则可以在编码阶段就拦住 React Error #310（hooks 调用数量不一致）
    "react-hooks/rules-of-hooks": "error",

    // 辅助规则：useEffect 依赖项缺失警告
    "react-hooks/exhaustive-deps": "warn",

    // 宽松模式 - 不强制检查未使用变量
    "@typescript-eslint/no-unused-vars": "off",
  },
};