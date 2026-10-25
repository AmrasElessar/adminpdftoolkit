import { mount } from "svelte";
import App from "./App.svelte";
import "./app.css";

export default mount(App, { target: document.getElementById("app")! });

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  // Served from the root so its scope covers the whole app.
  navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
}
