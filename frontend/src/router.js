import { createRouter, createWebHistory } from "vue-router";
import Home from "./views/Home.vue";

const PageView = () => import("./views/PageView.vue");
const AuthView = () => import("./views/AuthView.vue");
const SubmitView = () => import("./views/SubmitView.vue");
const AdminView = () => import("./views/AdminView.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: Home, meta: { title: "NEXA — AI tools, news, and rankings", description: "NEXA is a bilingual directory of AI tools, cross-border tools, news, Telegram channels, and GitHub rankings.", index: true } },
    { path: "/about", component: AuthView, props: { mode: "login" }, meta: { title: "About — NEXA", index: false } },
    { path: "/contact", component: PageView, props: { pageKey: "contact" }, meta: { title: "Contact — NEXA", description: "Contact NEXA.", index: true } },
    { path: "/advertise", component: PageView, props: { pageKey: "advertise" }, meta: { title: "Advertise — NEXA", description: "Advertise on NEXA.", index: true } },
    { path: "/login", component: AuthView, props: { mode: "login" }, meta: { title: "Log in — NEXA", index: false } },
    { path: "/register", component: AuthView, props: { mode: "register" }, meta: { title: "Register — NEXA", index: false } },
    { path: "/submit", component: SubmitView, meta: { title: "Account — NEXA", index: false } },
    { path: "/:gate", component: AdminView, props: true, meta: { title: "Console — NEXA", index: false } },
  ],
});

export default router;
