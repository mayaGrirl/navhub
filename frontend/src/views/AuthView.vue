<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import http from "../api";

const props = defineProps({ mode: String });
const route = useRoute();
const router = useRouter();
const email = ref("");
const password = ref("");
const totp = ref("");
const error = ref("");
const { locale, t } = useI18n();
const contact = ref(null);
const about = ref(null);
const ads = ref([]);
const mode = computed(() => (route.path === "/register" || props.mode === "register" ? "register" : "login"));

const telegram = computed(() => {
  const raw = (contact.value?.im || "").trim();
  if (!raw) return null;
  if (raw.includes("t.me/")) {
    const href = raw.startsWith("http") ? raw : `https://${raw.replace(/^\/+/, "")}`;
    return { href, label: raw.split("t.me/").pop() };
  }
  const name = raw.replace(/^telegram\s*/i, "").replace(/^@/, "").trim();
  if (!name) return null;
  return { href: `https://t.me/${name}`, label: `@${name}` };
});

async function load() {
  const [aboutRes, page, adRes] = await Promise.all([
    http.get("/pages/about", { params: { locale: locale.value } }),
    http.get("/pages/contact", { params: { locale: locale.value } }),
    http.get("/ads", { params: { locale: locale.value } }),
  ]);
  about.value = aboutRes.data;
  contact.value = page.data;
  const slots = ["about-1", "about-2", "about-3", "auth-1", "auth-2", "auth-3"];
  ads.value = adRes.data.filter((item) => slots.includes(item.slot));
}

watch(locale, load);
onMounted(load);

async function send() {
  error.value = "";
  try {
    const path = mode.value === "register" ? "/auth/register" : "/auth/login";
    await http.post(path, { email: email.value, password: password.value, totp: totp.value });
    router.push("/");
  } catch (err) {
    const detail = err.response?.data?.detail;
    error.value = detail ? t(detail) : t("authFailed");
  }
}
</script>

<template>
  <div class="auth-board">
    <article class="page" v-if="about">
      <a class="brand" href="/"><img src="/logo.svg" alt="" />NEXA</a>
      <h1>{{ about.title }}</h1>
      <p class="prose">{{ about.body }}</p>
    </article>
    <form class="page form" @submit.prevent="send">
      <h1>{{ mode === "register" ? t("register") : t("login") }}</h1>
      <input v-model="email" type="email" :placeholder="t('email')" required />
      <input v-model="password" type="password" :placeholder="t('password')" required />
      <input v-if="mode === 'login'" v-model="totp" :placeholder="t('totp')" />
      <button class="primary" type="submit">{{ mode === "register" ? t("createAccount") : t("login") }}</button>
      <p v-if="error">{{ error }}</p>
      <p><a class="auth-switch" :href="mode === 'register' ? '/login' : '/register'">{{ mode === "register" ? t("haveAccount") : t("noAccount") }}</a></p>
      <p v-if="telegram" class="tg"><a :href="telegram.href" target="_blank" rel="noopener">Telegram {{ telegram.label }}</a></p>
    </form>
    <div v-if="ads.length" class="auth-ads">
      <a v-for="ad in ads" :key="ad.id" :href="ad.link_url || undefined" target="_blank" rel="noopener">
        <img v-if="ad.image_url" :src="ad.image_url" :alt="ad.title" />
        <span>{{ ad.title }}</span>
      </a>
    </div>
  </div>
</template>
