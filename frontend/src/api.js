import axios from "axios";

const http = axios.create({ baseURL: "/api", withCredentials: true });

export function setGate(gate) {
  if (gate) http.defaults.headers.common["X-Admin-Gate"] = gate;
  else delete http.defaults.headers.common["X-Admin-Gate"];
}

export default http;
