import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/plus-jakarta-sans";
import App from "./App";
import { Toaster } from "sonner";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
    <Toaster richColors position="top-right" closeButton />
  </React.StrictMode>
);
