// Session 52: React 根入口
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles/global.css";
import "./styles/components.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("#root element missing in index.html");
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
