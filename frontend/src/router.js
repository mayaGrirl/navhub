import { createRouter, createWebHistory } from "vue-router";
import Home from "./views/Home.vue";

const PageView = () => import("./views/PageView.vue");
const AuthView = () => import("./views/AuthView.vue");
const SubmitView = () => import("./views/SubmitView.vue");
const AdminView = () => import("./views/AdminView.vue");

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: Home },
    { path: "/about", component: AuthView, props: { mode: "login" } },
    { path: "/contact", component: PageView, props: { pageKey: "contact" } },
    { path: "/advertise", component: PageView, props: { pageKey: "advertise" } },
    { path: "/login", component: AuthView, props: { mode: "login" } },
    { path: "/register", component: AuthView, props: { mode: "register" } },
    { path: "/submit", component: SubmitView },
    { path: "/:gate", component: AdminView, props: true },
  ],
});
