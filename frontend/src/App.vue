<template>
  <router-view />
  <button v-if="!isHome" class="phone-back" type="button" aria-label="back" @click="back">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 6 8.5 12l6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
  </button>
  <div class="global-menu">
    <button class="menu-btn" type="button" :aria-expanded="menuOpen" aria-label="menu" @click="menuOpen = !menuOpen">
      <span></span><span></span><span></span>
    </button>
    <div v-if="menuOpen" class="nav-links open">
      <a href="/" @click="menuOpen = false">{{ locale === "zh" ? "首页" : "Home" }}</a>
      <a v-if="user" href="/submit" @click="menuOpen = false">{{ t("submit") }}</a>
      <button class="text-btn" type="button" @click="setLocale(locale === 'en' ? 'zh' : 'en')">{{ locale === "en" ? "中文" : "EN" }}</button>
      <a v-if="!user" href="/login" @click="menuOpen = false">{{ t("login") }}</a>
      <button v-else class="text-btn" type="button" @click="logout">{{ t("logout") }}</button>
    </div>
  </div>
  <button class="to-top" type="button" aria-label="Back to top" @click="scrollTop">
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 14.5 12 8.5l6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import http from "./api";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const menuOpen = ref(false);
const user = ref(null);
const isHome = computed(() => route.path === "/");

watch(() => route.path, () => {
  menuOpen.value = false;
});

function back() {
  if (window.history.length > 1) router.back();
  else router.push("/");
}

function scrollTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setLocale(next) {
  locale.value = next;
  localStorage.setItem("locale", next);
  menuOpen.value = false;
}

async function logout() {
  await http.post("/auth/logout");
  user.value = null;
  menuOpen.value = false;
}

onMounted(async () => {
  try {
    user.value = (await http.get("/auth/me")).data;
  } catch {
    user.value = null;
  }
});
</script>
