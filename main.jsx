import React from "react";
import { createRoot } from "react-dom/client";
import NekoXiaoJinKu from "./neko-xiao-jin-ku.jsx";

createRoot(document.getElementById("root")).render(<NekoXiaoJinKu />);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  });
}
