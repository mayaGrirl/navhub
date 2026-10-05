<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import http from "../api";

const props = defineProps({ mode: String });
const router = useRouter();
const email = ref("");
const password = ref("");
const totp = ref("");
const error = ref("");
const { locale } = useI18n();
const contact = ref(null);
const ads = ref([]);
const index = ref(0);
const dragX = ref(0);

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

function move(step) {
  const count = ads.value.length;
  if (!count) return;
  index.value = (index.value + step + count) % count;
}

function onDown(event) {
  dragX.value = event.clientX;
}

function onUp(event) {
  if (!dragX.value) return;
  const delta = event.clientX - dragX.value;
  dragX.value = 0;
  if (delta > 40) move(-1);
  else if (delta < -40) move(1);
}

onMounted(async () => {
  const [page, adRes] = await Promise.all([
    http.get("/pages/contact", { params: { locale: locale.value } }),
    http.get("/ads", { params: { locale: locale.value } }),
  ]);
  contact.value = page.data;
  ads.value = adRes.data.filter((item) => ["auth-1", "auth-2", "auth-3"].includes(item.slot));
});

const timer = setInterval(() => move(1), 4000);
onUnmounted(() => clearInterval(timer));

async function send() {
  error.value = "";
  try {
    const path = props.mode === "register" ? "/auth/register" : "/auth/login";
    await http.post(path, { email: email.value, password: password.value, totp: totp.value });
    router.push("/");
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}
</script>

<template>
  <div class="auth-board">
    <aside v-if="ads.length" class="auth-carousel" @pointerdown="onDown" @pointerup="onUp">
      <a
        v-for="(ad, i) in ads"
        :key="ad.id"
        class="slide"
        :class="{ on: i === index }"
        :href="ad.link_url || undefined"
        target="_blank"
        rel="noopener"
      >
        <img v-if="ad.image_url" :src="ad.image_url" :alt="ad.title" />
        <span>{{ ad.title }}</span>
      </a>
      <div v-if="ads.length > 1" class="dots">
        <button v-for="(ad, i) in ads" :key="ad.id" type="button" :class="{ on: i === index }" @click="index = i"></button>
      </div>
    </aside>
    <form class="page form" @submit.prevent="send">
      <a class="brand" href="/"><img src="/logo.svg" alt="" />NEXA</a>
      <h1>{{ mode === "register" ? (locale === "zh" ? "注册" : "Register") : (locale === "zh" ? "登录" : "Log in") }}</h1>
      <input v-model="email" type="email" placeholder="Email" required />
      <input v-model="password" type="password" placeholder="Password" required />
      <input v-if="mode === 'login'" v-model="totp" :placeholder="locale === 'zh' ? '验证器验证码，未开启可留空' : 'Authenticator code, if enabled'" />
      <button class="primary" type="submit">{{ mode === "register" ? (locale === "zh" ? "创建账号" : "Create account") : (locale === "zh" ? "登录" : "Log in") }}</button>
      <p v-if="error">{{ error }}</p>
      <p><a class="auth-switch" :href="mode === 'register' ? '/login' : '/register'">{{ mode === "register" ? (locale === "zh" ? "已有账号，去登录" : "Already have an account") : (locale === "zh" ? "没有账号，去注册" : "Create an account") }}</a></p>
      <p v-if="telegram" class="tg"><a :href="telegram.href" target="_blank" rel="noopener">Telegram {{ telegram.label }}</a></p>
    </form>
  </div>
</template>
