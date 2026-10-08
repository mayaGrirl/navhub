import axios from "axios";

const http = axios.create({ baseURL: "/api", withCredentials: true });
const guardReady = axios.get("/api/guard", { withCredentials: true, timeout: 8000 }).catch(() => null);
http.interceptors.request.use(async (config) => {
  if (!String(config.url || "").includes("guard")) await guardReady;
  return config;
});

export function track(action, detail = "") {
  http.post("/track", { action, detail: String(detail || "").slice(0, 300) }).catch(() => {});
}

export function installTrack(router) {
  const named = new Set(["/about", "/contact", "/advertise", "/login", "/register"]);
  router.afterEach((to) => {
    if (named.has(to.path)) track("view", to.path);
  });
}

export function setGate(gate) {
  if (gate) http.defaults.headers.common["X-Admin-Gate"] = gate;
  else delete http.defaults.headers.common["X-Admin-Gate"];
}

export default http;
