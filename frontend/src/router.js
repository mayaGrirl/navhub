import { createRouter, createWebHistory } from "vue-router";
import Home from "./views/Home.vue";
import PageView from "./views/PageView.vue";
import AuthView from "./views/AuthView.vue";
import SubmitView from "./views/SubmitView.vue";
import AdminView from "./views/AdminView.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: Home },
    { path: "/about", component: PageView, props: { pageKey: "about" } },
    { path: "/contact", component: PageView, props: { pageKey: "contact" } },
    { path: "/advertise", component: PageView, props: { pageKey: "advertise" } },
    { path: "/login", component: AuthView, props: { mode: "login" } },
    { path: "/register", component: AuthView, props: { mode: "register" } },
    { path: "/submit", component: SubmitView },
    { path: "/:gate", component: AdminView, props: true },
  ],
});
