import { createApp } from "vue";
import { createPinia } from "pinia";
import { createI18n } from "vue-i18n";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import App from "./App.vue";
import router from "./router";
import "./style.css";

const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem("locale") || "en",
  messages: {
    en: {
      about: "About",
      ads: "Advertise",
      contact: "Contact",
      login: "Log in",
      register: "Register",
      logout: "Log out",
      submit: "Submit a link",
      search: "Search this section",
      free: "FREE",
      hot: "HOT",
      adultTitle: "Adult links",
      adultBody: "This section is for adults. Confirm you are 18 or older.",
      enter: "Continue",
      back: "Go back",
      empty: "Nothing in this section yet.",
    },
    zh: {
      about: "关于我们",
      ads: "广告合作",
      contact: "联系方式",
      login: "登录",
      register: "注册",
      logout: "退出",
      submit: "提交链接",
      search: "搜索当前分类",
      free: "免费",
      hot: "热门",
      adultTitle: "成人链接",
      adultBody: "此分区仅面向成年人。请确认你已年满 18 岁。",
      enter: "继续",
      back: "返回",
      empty: "这个分类还没有内容。",
    },
  },
});

createApp(App).use(createPinia()).use(router).use(i18n).use(ElementPlus).mount("#app");
