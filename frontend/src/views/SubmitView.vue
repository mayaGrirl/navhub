<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import http from "../api";

const route = useRoute();
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
const logoPreview = ref("");
const description = ref("");
const categories = computed(() => tree.value.find((item) => item.id === tabId.value)?.categories || []);

const initial = computed(() => (name.value || user.value?.email || "?").slice(0, 1).toUpperCase());
const origin = computed(() => window.location.origin);
const proxyToken = ref("");
const levelInfo = ref(null);
const siteBoards = ref({ favorites: [], recommends: [] });
const myMarks = ref([]);
const submissions = ref([]);
const submissionPage = ref(1);
const submissionTotal = ref(0);
const showForm = ref(false);
const copied = ref("");
const proxyLink = computed(() => proxyToken.value ? `${origin.value}/api/proxy/acquire?token=${encodeURIComponent(proxyToken.value)}` : "");
const proxyText = computed(() => {
  if (!levelInfo.value) return "";
  if (levelInfo.value.proxy_unlimited) return locale.value === "zh" ? "白名单，不限次数" : "Unlimited";
  if (levelInfo.value.proxy_limit != null) return locale.value === "zh" ? `每分钟 ${levelInfo.value.proxy_limit} 次` : `${levelInfo.value.proxy_limit} per minute`;
  return locale.value === "zh" ? `按等级，每分钟 ${levelInfo.value.proxy_per_minute} 次` : `${levelInfo.value.proxy_per_minute} per minute by level`;
});

onMounted(async () => {
  try {
    const { data } = await http.get("/auth/me");
    user.value = data;
    name.value = data.display_name || "";
  } catch {
    router.replace("/login");
    return;
  }
  if (["proxy", "submit", "profile", "levels", "marks"].includes(route.query.tab)) tab.value = route.query.tab;
  const [tokenRes, levelRes, rankRes, markRes] = await Promise.all([
    http.get("/proxy/token"),
    http.get("/me/level"),
    http.get("/ranks", { params: { locale: locale.value } }),
    http.get("/me/marks", { params: { locale: locale.value } }),
  ]);
  levelInfo.value = levelRes.data;
  siteBoards.value = rankRes.data;
  myMarks.value = markRes.data.items;
  proxyToken.value = tokenRes.data.token || "";
  await loadSubmissions(1);
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

let holdTimer = 0;
function holdStart(event) {
  const chip = event.currentTarget;
  holdTimer = window.setTimeout(() => chip.classList.add("held"), 280);
}
function holdEnd(event) {
  window.clearTimeout(holdTimer);
  event.currentTarget.classList.remove("held");
}
function siteIcon(url) {
  try {
    const host = new URL(url).hostname;
    return host ? `https://www.google.com/s2/favicons?domain=${host}&sz=64` : "/favicon.svg";
  } catch {
    return "/favicon.svg";
  }
}
function logoOf(link) {
  const logo = link.logo_url || "";
  const placeholder = !logo || /empty\.png|google\.com\/s2\/favicons|opengraph|ogp|default_social/i.test(logo);
  return placeholder ? siteIcon(link.url) : logo;
}
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

async function copyText(value, key) {
  await navigator.clipboard.writeText(value);
  copied.value = key;
}

async function dropMark(item) {
  await http.post(`/links/${item.id}/mark`, { kind: item.kind });
  myMarks.value = myMarks.value.filter((row) => !(row.id === item.id && row.kind === item.kind));
  const { data } = await http.get("/ranks", { params: { locale: locale.value } });
  siteBoards.value = data;
}
async function makeProxyToken() {
  const { data } = await http.post("/proxy/token");
  proxyToken.value = data.token;
}

function rememberPreview(value) {
  if (logoPreview.value.startsWith("blob:")) URL.revokeObjectURL(logoPreview.value);
  logoPreview.value = value || "";
}

function onLogoTyping() {
  if (!logoPreview.value.startsWith("blob:")) logoPreview.value = logoUrl.value;
}

async function uploadLogo(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  const ok = ["image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"].includes(file.type) || /\.(png|jpe?g|gif|webp|svg)$/i.test(file.name);
  if (!ok) {
    notice.value = t("imageFormatsOnly");
    return;
  }
  notice.value = "";
  rememberPreview(URL.createObjectURL(file));
  const body = new FormData();
  body.append("file", file);
  try {
    const { data } = await http.post("/uploads", body);
    logoUrl.value = data.url;
  } catch (err) {
    rememberPreview("");
    const detail = err.response?.data?.detail;
    notice.value = detail ? t(detail) : t("authFailed");
  }
}

function reviewText(code) {
  const zh = locale.value === "zh";
  if (code === "duplicate") return zh ? "未通过：与站内已有链接重复，去掉协议和 www 后视为同一个网址" : "Rejected: this matches a link already in the directory, ignoring scheme and www.";
  if (code === "unreachable") return zh ? "未通过：网址无法打开" : "Rejected: the site could not be opened.";
  if (code === "opened") return zh ? "已通过：网址可以打开，已收录" : "Approved: the site opened and is now listed.";
  return zh ? "审核中" : "In review";
}

async function loadSubmissions(page = submissionPage.value) {
  const { data } = await http.get("/me/submissions", { params: { page, locale: locale.value } });
  submissions.value = data.items;
  submissionTotal.value = data.total;
  submissionPage.value = data.page;
}

function openOut(url) {
  const opened = window.open(url, "_blank", "noopener,noreferrer");
  if (opened) opened.opener = null;
}

function openHere(item) {
  router.push({ path: "/", query: { link: item.id, tab: item.tab_id, cat: item.category_id } });
}

function initialOf(name) {
  const text = (name || "").trim();
  return text ? text.slice(0, 1).toUpperCase() : "?";
}

async function send() {
  notice.value = "";
  if (!title.value.trim()) {
    notice.value = t("nameRequired");
    return;
  }
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
    rememberPreview("");
    description.value = "";
    notice.value = t("submitted");
    showForm.value = false;
    await loadSubmissions(1);
    window.setTimeout(() => loadSubmissions(submissionPage.value), 5000);
  } catch (err) {
    notice.value = err.response?.data?.detail || t("authFailed");
  }
}

async function logout() {
  await http.post("/auth/logout");
  router.push("/");
}
</script>

<template>
  <div v-if="ready" class="account has-ads">
    <aside class="account-side">
      <a class="side-brand" href="/"><img src="/logo.svg" alt="" />NEXA</a>
      <div class="account-who">
        <span class="avatar">{{ initial }}</span>
        <strong>{{ user.display_name || user.email }}</strong>
        <em>{{ user.email }}</em>
        <em v-if="levelInfo">Lv.{{ levelInfo.level }} · {{ levelInfo.points }} {{ locale === "zh" ? "积分" : "pts" }}</em>
      </div>
      <nav class="account-nav">
        <button type="button" :class="{ on: tab === 'profile' }" @click="tab = 'profile'">{{ t("profile") }}</button>
        <button type="button" :class="{ on: tab === 'levels' }" @click="tab = 'levels'">{{ locale === "zh" ? "等级规则" : "Levels" }}</button>
        <button type="button" :class="{ on: tab === 'marks' }" @click="tab = 'marks'">{{ locale === "zh" ? "收藏推荐" : "Saved" }}</button>
        <button type="button" :class="{ on: tab === 'submit' }" @click="tab = 'submit'">{{ t("submit") }}</button>
        <button type="button" :class="{ on: tab === 'proxy' }" @click="tab = 'proxy'">{{ t("proxyPool") }}</button>
        <a href="/">{{ locale === "zh" ? "返回主页" : "Back to home" }}</a>
        <button type="button" @click="logout">{{ t("logout") }}</button>
      </nav>
    </aside>
    <section class="page form" v-if="tab === 'profile'">
      <h1>{{ t("profile") }}</h1>
      <label>{{ t("email") }}</label>
      <input :value="user.email" readonly />
      <p class="meta" v-if="levelInfo">{{ locale === "zh" ? `Lv.${levelInfo.level} · ${levelInfo.points} 积分 · ${user.plan === "vip" ? "VIP" : "免费会员"}` : `Lv.${levelInfo.level} · ${levelInfo.points} pts · ${user.plan === "vip" ? "VIP" : "Free"}` }}</p>
      <p class="meta">{{ locale === "zh" ? `代理：${proxyText}` : `Proxy: ${proxyText}` }}</p>
      <p class="meta">{{ locale === "zh" ? `最近 IP：${user.last_ip || "还没有记录"}` : `Last IP: ${user.last_ip || "Not recorded yet"}` }}</p>
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
    <section v-else-if="tab === 'marks'" class="page form">
      <h1>{{ locale === "zh" ? "我的收藏和推荐" : "My saves" }}</h1>
      <h2><svg class="board-icon" viewBox="0 0 24 24"><path d="M12 21s-6.7-4.3-9.3-8.2C.6 10.1 1.2 6.6 4.2 5.2 6.3 4.2 8.6 4.8 10 6.4L12 8.7l2-2.3c1.4-1.6 3.7-2.2 5.8-1.2 3 1.4 3.6 4.9 1.5 7.6C18.7 16.7 12 21 12 21z"/></svg>{{ locale === "zh" ? "收藏" : "Favorites" }}</h2>
      <div class="mark-list">
        <div class="mine-row" v-for="(item, index) in myMarks.filter((row) => row.kind === 'favorite')" :key="'f' + item.id">
          <a class="mark-chip" :href="item.url" target="_blank" rel="noreferrer">
            <img :src="logoOf(item)" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="$event.target.src = siteIcon(item.url)" />
            <span class="name">{{ item.title }}</span>
            <b>{{ item.favorite_count }}</b>
          </a>
          <button type="button" @click="dropMark(item)">{{ locale === "zh" ? "取消" : "Remove" }}</button>
        </div>
      </div>
      <p v-if="!myMarks.some((row) => row.kind === 'favorite')" class="meta">{{ locale === "zh" ? "还没有收藏" : "No favorites yet" }}</p>
      <h2><svg class="board-icon" viewBox="0 0 24 24"><path d="M8 10V21H4V10h4zm2.2 11c-.7 0-1.3-.2-1.8-.7-.4-.4-.6-.9-.6-1.5V10.2c0-.3.1-.6.3-.9l4.6-5.8c.3-.4.8-.6 1.3-.5.6.1 1 .6 1 1.2v4.3h4.4c.8 0 1.5.6 1.6 1.4l.8 5.4c.1.8-.2 1.6-.8 2.1-.5.5-1.2.8-1.9.8H10.2z"/></svg>{{ locale === "zh" ? "推荐" : "Recommendations" }}</h2>
      <div class="mark-list">
        <div class="mine-row" v-for="(item, index) in myMarks.filter((row) => row.kind === 'recommend')" :key="'r' + item.id">
          <a class="mark-chip" :href="item.url" target="_blank" rel="noreferrer">
            <img :src="logoOf(item)" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="$event.target.src = siteIcon(item.url)" />
            <span class="name">{{ item.title }}</span>
            <b>{{ item.recommend_count }}</b>
          </a>
          <button type="button" @click="dropMark(item)">{{ locale === "zh" ? "取消" : "Remove" }}</button>
        </div>
      </div>
      <p v-if="!myMarks.some((row) => row.kind === 'recommend')" class="meta">{{ locale === "zh" ? "还没有推荐" : "No recommendations yet" }}</p>
    </section>
    <section v-else-if="tab === 'levels'" class="page form">
      <h1>{{ locale === "zh" ? "等级规则" : "Level rules" }}</h1>
      <p class="meta" v-if="levelInfo">{{ locale === "zh" ? `当前 Lv.${levelInfo.level}，${levelInfo.points} 积分。新注册默认 Lv.0。提交一条站内还没有的链接加 ${levelInfo.points_per_link} 分，积分达到下一档门槛会自动升级。代理池按当前等级限流，现在每分钟 ${levelInfo.proxy_per_minute} 次。` : `You are Lv.${levelInfo.level} with ${levelInfo.points} points. New accounts start at Lv.0. Each new directory link is worth ${levelInfo.points_per_link} point(s), and the level updates as soon as you reach the next threshold. The proxy pool follows your level: ${levelInfo.proxy_per_minute} calls per minute.` }}</p>
      <table v-if="levelInfo" class="level-table">
        <thead>
          <tr>
            <th>{{ locale === "zh" ? "等级" : "Level" }}</th>
            <th>{{ locale === "zh" ? "所需积分" : "Points" }}</th>
            <th>{{ locale === "zh" ? "获取" : "Earn" }}</th>
            <th>{{ locale === "zh" ? "代理 / 分钟" : "Proxy / min" }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in levelInfo.levels" :key="row.level" :class="{ on: row.level === levelInfo.level }">
            <td>Lv.{{ row.level }}</td>
            <td>{{ row.min_points }}</td>
            <td>+{{ levelInfo.points_per_link }} / {{ locale === "zh" ? "有效链接" : "link" }}</td>
            <td>{{ row.proxy_per_minute }}{{ locale === "zh" ? " 次" : "" }}</td>
          </tr>
        </tbody>
      </table>
    </section>
    <section v-else-if="tab === 'submit'" class="page form submit-panel">
      <div class="section-head">
        <div>
          <h1>{{ t("submit") }}</h1>
          <p class="meta">{{ locale === "zh" ? `共 ${submissionTotal} 条` : `${submissionTotal} total` }}</p>
        </div>
        <button type="button" class="primary" @click="showForm = !showForm">{{ showForm ? (locale === "zh" ? "收起" : "Close") : (locale === "zh" ? "提交链接" : "Submit a link") }}</button>
      </div>
      <form v-if="showForm" class="submit-form" @submit.prevent="send">
      <label>{{ locale === "zh" ? "一级栏目" : "Section" }}</label>
      <div class="pick-tabs">
        <button v-for="item in tree" :key="item.id" type="button" :class="{ on: item.id === tabId }" @click="pickTab(item.id)">{{ item.title }}</button>
      </div>
      <label>{{ locale === "zh" ? "二级分类" : "Category" }}</label>
      <div class="pick-cats">
        <button v-for="cat in categories" :key="cat.id" type="button" :class="{ on: cat.id === categoryId }" @click="categoryId = cat.id">{{ cat.title }}</button>
      </div>
      <input v-model="title" :placeholder="t('linkName')" required maxlength="160" />
      <input v-model="url" :placeholder="t('linkUrl')" required />
      <div class="logo-row">
        <img v-if="logoPreview || logoUrl" :src="logoPreview || logoUrl" alt="" />
        <input v-model="logoUrl" :placeholder="t('logoUrl')" @input="onLogoTyping" />
        <label class="upload-btn">{{ t("uploadIcon") }}<input type="file" accept=".png,.jpg,.jpeg,.gif,.webp,.svg,image/png,image/jpeg,image/gif,image/webp,image/svg+xml" @change="uploadLogo" /></label>
      </div>
      <p class="meta">{{ t("imageFormats") }}</p>
      <textarea v-model="description" rows="4" :placeholder="t('linkDesc')"></textarea>
      <button class="primary" type="submit">{{ t("submit") }}</button>
      </form>
      <p v-if="notice">{{ notice }}</p>
      <h2>{{ locale === "zh" ? "提交记录" : "Submissions" }}</h2>
      <p v-if="!submissions.length" class="meta">{{ locale === "zh" ? "还没有提交" : "No submissions yet" }}</p>
      <div class="submit-log" v-for="item in submissions" :key="item.id">
        <span class="submit-mark">
          <img v-if="item.logo_url && !item.logoOff" :src="item.logo_url" alt="" loading="lazy" decoding="async" @error="item.logoOff = true" />
          <b v-else>{{ initialOf(item.title) }}</b>
        </span>
        <div class="submit-top">
          <strong>{{ item.title }}</strong>
          <button type="button" class="text-btn" :disabled="item.status !== 'published'" @click="openHere(item)">{{ locale === "zh" ? "本站查看" : "View here" }}</button>
        </div>
        <em :class="item.status === 'published' ? 'opened' : item.status === 'rejected' ? 'rejected' : 'reviewing'">{{ reviewText(item.note) }}</em>
        <span class="submit-where">{{ item.tab }} · {{ item.category }}</span>
        <button type="button" class="submit-url" @click="openOut(item.url)">{{ item.url }}</button>
      </div>
      <div v-if="submissionTotal > 10" class="pager">
        <button type="button" :disabled="submissionPage <= 1" @click="loadSubmissions(submissionPage - 1)">{{ locale === "zh" ? "上一页" : "Prev" }}</button>
        <span>{{ submissionPage }} / {{ Math.ceil(submissionTotal / 10) }}</span>
        <button type="button" :disabled="submissionPage >= Math.ceil(submissionTotal / 10)" @click="loadSubmissions(submissionPage + 1)">{{ locale === "zh" ? "下一页" : "Next" }}</button>
      </div>
    </section>
    <section v-else-if="tab === 'proxy'" class="page form proxy-doc">
      <h1>{{ t("proxyPool") }}</h1>
      <p>{{ locale === "zh" ? `代理池是单独维护的服务。这里只给已登录用户发放调用令牌，令牌和登录会话无关。每次返回一个当前可用的 HTTP 代理。当前额度：${proxyText}。` : `The proxy pool is a separate service. This page only issues a call token for signed-in users. The token is not your login session. Each call returns one working HTTP proxy. Current allowance: ${proxyText}.` }}</p>
      <button class="primary" type="button" @click="makeProxyToken">{{ locale === "zh" ? "生成令牌" : "Generate token" }}</button>
      <div v-if="proxyToken" class="copy-row">
        <pre>{{ proxyToken }}</pre>
        <button type="button" @click="copyText(proxyToken, 'token')">{{ copied === "token" ? (locale === "zh" ? "已复制" : "Copied") : (locale === "zh" ? "复制" : "Copy") }}</button>
      </div>
      <p v-if="proxyLink">{{ locale === "zh" ? "下面的地址取自当前打开的域名，部署到正式域名后会自动换成那个域名。" : "The address below uses the domain you opened. It changes automatically after the site is deployed." }}</p>
      <div v-if="proxyLink" class="copy-row">
        <pre>{{ proxyLink }}</pre>
        <button type="button" @click="copyText(proxyLink, 'link')">{{ copied === "link" ? (locale === "zh" ? "已复制" : "Copied") : (locale === "zh" ? "复制" : "Copy") }}</button>
      </div>
      <h2>{{ locale === "zh" ? "请求" : "Request" }}</h2>
      <pre>GET /api/proxy/acquire
Authorization: Bearer 你的令牌</pre>
      <h2>{{ locale === "zh" ? "返回" : "Response" }}</h2>
      <pre>{ "proxy": "http://1.2.3.4:8080" }</pre>
      <p>{{ locale === "zh" ? "没有可用代理时 proxy 为 null。未带令牌会返回 401。" : "proxy is null when none are available. A missing token returns 401." }}</p>
      <h2>{{ locale === "zh" ? "示例" : "Example" }}</h2>
      <pre>curl -H "Authorization: Bearer {{ proxyToken || "你的令牌" }}" {{ origin }}/api/proxy/acquire
curl -x http://1.2.3.4:8080 https://example.com</pre>
      <p>{{ locale === "zh" ? "把 proxy 字段原样用作 HTTP 代理。再次点击生成会换掉旧令牌。定时抓取不使用这个令牌，它直接访问代理池。" : "Use the proxy field as an HTTP proxy. Generating again replaces the old token. Scheduled crawls do not use this token; they call the pool directly." }}</p>
    </section>
    <aside class="account-ads">
      <section>
        <h2><svg class="board-icon" viewBox="0 0 24 24"><path d="M12 21s-6.7-4.3-9.3-8.2C.6 10.1 1.2 6.6 4.2 5.2 6.3 4.2 8.6 4.8 10 6.4L12 8.7l2-2.3c1.4-1.6 3.7-2.2 5.8-1.2 3 1.4 3.6 4.9 1.5 7.6C18.7 16.7 12 21 12 21z"/></svg>{{ locale === "zh" ? "收藏榜" : "Favorites" }}</h2>
        <div class="mark-list">
          <a class="mark-chip" v-for="(item, index) in siteBoards.favorites" :key="'f' + item.id" :href="item.url" target="_blank" rel="noreferrer">
            <img :src="logoOf(item)" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="$event.target.src = siteIcon(item.url)" />
            <span class="name">{{ item.title }}</span>
            <b>{{ item.count }}</b>
          </a>
        </div>
        <p v-if="!siteBoards.favorites.length" class="meta">{{ locale === "zh" ? "还没有收藏" : "No favorites yet" }}</p>
      </section>
      <a v-if="ads[0]" :href="ads[0].link_url || undefined" target="_blank" rel="noopener">
        <img v-if="ads[0].image_url" :src="ads[0].image_url" :alt="ads[0].title" loading="lazy" decoding="async" />
        <span>{{ ads[0].title }}</span>
      </a>
      <section>
        <h2><svg class="board-icon" viewBox="0 0 24 24"><path d="M8 10V21H4V10h4zm2.2 11c-.7 0-1.3-.2-1.8-.7-.4-.4-.6-.9-.6-1.5V10.2c0-.3.1-.6.3-.9l4.6-5.8c.3-.4.8-.6 1.3-.5.6.1 1 .6 1 1.2v4.3h4.4c.8 0 1.5.6 1.6 1.4l.8 5.4c.1.8-.2 1.6-.8 2.1-.5.5-1.2.8-1.9.8H10.2z"/></svg>{{ locale === "zh" ? "推荐榜" : "Recommendations" }}</h2>
        <div class="mark-list">
          <a class="mark-chip" v-for="(item, index) in siteBoards.recommends" :key="'r' + item.id" :href="item.url" target="_blank" rel="noreferrer">
            <img :src="logoOf(item)" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="$event.target.src = siteIcon(item.url)" />
            <span class="name">{{ item.title }}</span>
            <b>{{ item.count }}</b>
          </a>
        </div>
        <p v-if="!siteBoards.recommends.length" class="meta">{{ locale === "zh" ? "还没有推荐" : "No recommendations yet" }}</p>
      </section>
      <a v-for="ad in ads.slice(1)" :key="ad.id" :href="ad.link_url || undefined" target="_blank" rel="noopener">
        <img v-if="ad.image_url" :src="ad.image_url" :alt="ad.title" loading="lazy" decoding="async" />
        <span>{{ ad.title }}</span>
      </a>
    </aside>
  </div>
</template>
