<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import http from "../api";

const router = useRouter();
const { locale, t } = useI18n();
const ready = ref(false);
const tab = ref("profile");
const user = ref(null);
const name = ref("");
const notice = ref("");
const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");

const ads = ref([]);
const tree = ref([]);
const tabId = ref("");
const categoryId = ref("");
const title = ref("");
const url = ref("");
const logoUrl = ref("");
const description = ref("");
const categories = computed(() => tree.value.find((item) => item.id === tabId.value)?.categories || []);

const initial = computed(() => (name.value || user.value?.email || "?").slice(0, 1).toUpperCase());

onMounted(async () => {
  try {
    const { data } = await http.get("/auth/me");
    user.value = data;
    name.value = data.display_name || "";
  } catch {
    router.replace("/login");
    return;
  }
  ready.value = true;
  const [treeRes, adRes] = await Promise.all([
    http.get("/tree", { params: { locale: locale.value } }),
    http.get("/ads", { params: { locale: locale.value } }),
  ]);
  const data = treeRes.data;
  ads.value = adRes.data.filter((item) => item.slot === "account-1" || item.slot === "account-2");
  tree.value = data.filter((item) => item.kind === "links");
  tabId.value = tree.value[0]?.id || "";
  categoryId.value = tree.value[0]?.categories[0]?.id || "";
});

function pickTab(id) {
  tabId.value = id;
  const next = tree.value.find((item) => item.id === id);
  categoryId.value = next?.categories[0]?.id || "";
}

async function saveProfile() {
  notice.value = "";
  const { data } = await http.patch("/auth/profile", { display_name: name.value });
  user.value.display_name = data.display_name;
  notice.value = t("saved");
}

async function savePassword() {
  notice.value = "";
  if (newPassword.value !== confirmPassword.value) {
    notice.value = t("passwordMismatch");
    return;
  }
  try {
    await http.post("/auth/password", { current_password: currentPassword.value, new_password: newPassword.value });
    currentPassword.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
    notice.value = t("passwordChanged");
  } catch (err) {
    const detail = err.response?.data?.detail;
    notice.value = detail ? t(detail) : t("authFailed");
  }
}

async function uploadLogo(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  notice.value = "";
  const body = new FormData();
  body.append("file", file);
  try {
    const { data } = await http.post("/uploads", body);
    logoUrl.value = data.url;
  } catch (err) {
    const detail = err.response?.data?.detail;
    notice.value = detail ? t(detail) : t("authFailed");
  }
}

async function send() {
  notice.value = "";
  try {
    await http.post("/submissions", {
      category_id: categoryId.value,
      title: title.value,
      title_en: title.value,
      title_zh: title.value,
      url: url.value,
      logo_url: logoUrl.value,
      description_en: description.value,
      description_zh: description.value,
    });
    title.value = "";
    url.value = "";
    logoUrl.value = "";
    description.value = "";
    notice.value = t("submitted");
  } catch (err) {
    notice.value = err.response?.data?.detail || t("authFailed");
  }
}
</script>

<template>
  <div v-if="ready" class="account" :class="{ 'has-ads': ads.length }">
    <aside class="account-side">
      <div class="account-who">
        <span class="avatar">{{ initial }}</span>
        <strong>{{ user.display_name || user.email }}</strong>
        <em>{{ user.email }}</em>
      </div>
      <button type="button" :class="{ on: tab === 'profile' }" @click="tab = 'profile'">{{ t("profile") }}</button>
      <button type="button" :class="{ on: tab === 'submit' }" @click="tab = 'submit'">{{ t("submit") }}</button>
      <a href="/">NEXA</a>
    </aside>
    <section class="page form" v-if="tab === 'profile'">
      <h1>{{ t("profile") }}</h1>
      <label>{{ t("email") }}</label>
      <input :value="user.email" readonly />
      <label>{{ t("nickname") }}</label>
      <input v-model="name" maxlength="40" :placeholder="t('nickname')" />
      <button class="primary" type="button" @click="saveProfile">{{ t("save") }}</button>
      <h2>{{ t("password") }}</h2>
      <input v-model="currentPassword" type="password" :placeholder="t('currentPassword')" autocomplete="current-password" />
      <input v-model="newPassword" type="password" :placeholder="t('newPassword')" autocomplete="new-password" />
      <input v-model="confirmPassword" type="password" :placeholder="t('confirmPassword')" autocomplete="new-password" />
      <button class="primary" type="button" @click="savePassword">{{ t("save") }}</button>
      <p v-if="notice">{{ notice }}</p>
    </section>
    <form v-else class="page form" @submit.prevent="send">
      <h1>{{ t("submit") }}</h1>
      <label>{{ t("category") }}</label>
      <div class="pick-tabs">
        <button v-for="item in tree" :key="item.id" type="button" :class="{ on: item.id === tabId }" @click="pickTab(item.id)">{{ item.title }}</button>
      </div>
      <div class="pick-cats">
        <button v-for="cat in categories" :key="cat.id" type="button" :class="{ on: cat.id === categoryId }" @click="categoryId = cat.id">{{ cat.title }}</button>
      </div>
      <input v-model="title" :placeholder="t('linkName')" required />
      <input v-model="url" :placeholder="t('linkUrl')" required />
      <div class="logo-row">
        <img v-if="logoUrl" :src="logoUrl" alt="" referrerpolicy="no-referrer" />
        <input v-model="logoUrl" :placeholder="t('logoUrl')" />
        <label class="upload-btn">{{ t("uploadIcon") }}<input type="file" accept="image/*" @change="uploadLogo" /></label>
      </div>
      <textarea v-model="description" rows="4" :placeholder="t('linkDesc')"></textarea>
      <button class="primary" type="submit">{{ t("submit") }}</button>
      <p v-if="notice">{{ notice }}</p>
    </form>
    <aside v-if="ads.length" class="account-ads">
      <a v-for="ad in ads" :key="ad.id" :href="ad.link_url || undefined" target="_blank" rel="noopener">
        <img v-if="ad.image_url" :src="ad.image_url" :alt="ad.title" />
        <span>{{ ad.title }}</span>
      </a>
    </aside>
  </div>
</template>
