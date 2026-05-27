import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

const globalCSS = `
@keyframes ql-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
`;

const styleEl = document.createElement("style");
styleEl.textContent = globalCSS;
document.head.appendChild(styleEl);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);