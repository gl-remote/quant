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
    // —— 这条规则可以在编码阶段就拦住 error #310
    "react-hooks/rules-of-hooks": "error",

    // 辅助规则：useEffect 依赖项缺失警告
    "react-hooks/exhaustive-deps": "warn",

    // 宽松模式 —— 不强制检查未使用变量
    "@typescript-eslint/no-unused-vars": "off",
  },
};