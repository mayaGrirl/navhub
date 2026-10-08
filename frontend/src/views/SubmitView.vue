<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import http from "../api";
import FeedbackBox from "../components/FeedbackBox.vue";

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
  if (["proxy", "submit", "profile", "levels", "marks", "video", "feedback"].includes(route.query.tab)) tab.value = route.query.tab;
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
  loadParsers();
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
  const ok = ["image/png", "image/jpeg", "image/gif", "image/webp"].includes(file.type) || /\.(png|jpe?g|gif|webp)$/i.test(file.name);
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

// ---- 视频播放 ----
const videoUrl = ref("");           // 要播放的视频 / 网页地址
const parserUrl = ref("");          // 解析源地址（可空，可从下拉选）
const parsers = ref([]);            // 数据库里收录的解析站 [{id,title,url}]
const videoLoading = ref(false);
const videoError = ref("");
const videoCurrent = ref(null);     // 直链 { url, kind, title }
const frameUrl = ref("");           // iframe 要加载的最终地址
const videoStage = ref(null);
const frameStage = ref(null);
const videoEl = ref(null);
let hls = null;
let flvPlayer = null;
const HLS_CDN = "https://cdn.jsdelivr.net/npm/hls.js@1/dist/hls.min.js";
const FLV_CDN = "https://cdn.jsdelivr.net/npm/flv.js@1.6.2/dist/flv.min.js";

function isParserTemplate(url) {
  const value = String(url || "").trim();
  return /\{url\}/i.test(value) || /[?&]url=$/i.test(value);
}

async function loadParsers() {
  try {
    const { data } = await http.get("/video/parsers", { params: { locale: locale.value } });
    parsers.value = data || [];
  } catch {
    parsers.value = [];
  }
}

// select 当前显示的值：匹配到某个解析源就显示它，否则空（未选）或自定义
const selectedParser = computed(() => {
  const current = parserUrl.value.trim();
  if (!current) return "";
  if (parsers.value.some((p) => p.url === current)) return current;
  return "__custom__";
});

function onParserSelect(value) {
  if (value === "__custom__") {
    parserUrl.value = "";
    return;
  }
  parserUrl.value = value || "";
}

// 把解析源和视频地址拼成最终地址：解析源形如 https://x/?url= 直接拼接；
// 若解析源不以 =、?、/ 结尾则补一个 = 分隔（覆盖常见写法），用户也可自行把完整地址填进解析源框。
function buildFrameUrl() {
  const parser = parserUrl.value.trim();
  const video = videoUrl.value.trim();
  if (!parser || !video || !isParserTemplate(parser)) return "";
  if (/\{url\}/i.test(parser)) return parser.replace(/\{url\}/gi, encodeURIComponent(video));
  return parser + encodeURIComponent(video);
}

function teardownVideo() {
  if (hls) {
    try { hls.destroy(); } catch { /* ignore */ }
    hls = null;
  }
  if (flvPlayer) {
    try { flvPlayer.destroy(); } catch { /* ignore */ }
    flvPlayer = null;
  }
  const el = videoEl.value;
  if (el) {
    try {
      el.pause();
      el.removeAttribute("src");
      el.load();
    } catch { /* ignore */ }
  }
}

function clearVideo() {
  teardownVideo();
  videoCurrent.value = null;
  frameUrl.value = "";
  videoError.value = "";
}

function loadPlayerScript(src, mark) {
  return new Promise((resolve, reject) => {
    const ready = mark === "hls" ? window.Hls : window.flvjs;
    if (ready) return resolve();
    const existing = document.querySelector(`script[data-player="${mark}"]`);
    if (existing) {
      if (existing.dataset.loaded === "1") return resolve();
      if (existing.dataset.failed === "1") existing.remove();
      else {
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener("error", () => reject(new Error(mark)), { once: true });
        return;
      }
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.dataset.player = mark;
    script.onload = () => { script.dataset.loaded = "1"; resolve(); };
    script.onerror = () => { script.dataset.failed = "1"; reject(new Error(mark)); };
    document.head.appendChild(script);
  });
}

function loadHlsScript() {
  return loadPlayerScript(HLS_CDN, "hls");
}

async function playHls(src) {
  const el = videoEl.value;
  if (!el) return;
  if (el.canPlayType("application/vnd.apple.mpegurl")) {
    el.src = src;
    return;
  }
  try {
    await loadHlsScript();
  } catch {
    videoError.value = t("videoStreamFailed");
    return;
  }
  if (!window.Hls || !window.Hls.isSupported()) {
    videoError.value = t("videoStreamFailed");
    return;
  }
  hls = new window.Hls({ enableWorker: true });
  hls.loadSource(src);
  hls.attachMedia(el);
  hls.on(window.Hls.Events.ERROR, (_evt, data) => {
    if (data && data.fatal) videoError.value = t("videoStreamFailed");
  });
}

async function playFlv(src) {
  const el = videoEl.value;
  if (!el) return;
  try {
    await loadPlayerScript(FLV_CDN, "flv");
  } catch {
    videoError.value = t("videoStreamFailed");
    return;
  }
  if (!window.flvjs || !window.flvjs.isSupported()) {
    videoError.value = t("videoStreamFailed");
    return;
  }
  flvPlayer = window.flvjs.createPlayer({ type: "flv", url: src });
  flvPlayer.attachMediaElement(el);
  flvPlayer.load();
  flvPlayer.on(window.flvjs.Events.ERROR, () => {
    videoError.value = t("videoStreamFailed");
  });
}

async function startVideo(result) {
  teardownVideo();
  videoCurrent.value = result;
  await Promise.resolve();
  const el = videoEl.value;
  if (!el) return;
  if (result.kind === "hls") await playHls(result.url);
  else if (result.kind === "flv") await playFlv(result.url);
  else el.src = result.url;
  try { await el.play(); } catch { /* 自动播放可能被拦，用户可手动点 */ }
}

async function resolveVideo() {
  if (videoLoading.value) return;
  videoError.value = "";

  // 有解析源：走 iframe 嵌入模式，加载用户选/填的最终地址
  if (parserUrl.value.trim()) {
    const target = buildFrameUrl();
    if (!target) {
      videoError.value = t("videoParserInvalid");
      return;
    }
    teardownVideo();
    videoCurrent.value = null;
    frameUrl.value = target;
    return;
  }

  // 无解析源：按直链解析在站内原生播放
  const value = videoUrl.value.trim();
  if (!value) {
    videoError.value = t("video_empty");
    return;
  }
  videoLoading.value = true;
  frameUrl.value = "";
  try {
    const { data } = await http.post("/video/resolve", { url: value });
    await startVideo(data);
  } catch (err) {
    const detail = err.response?.data?.detail;
    videoError.value = detail ? t(detail) : t("videoPlayFailed");
    videoCurrent.value = null;
  } finally {
    videoLoading.value = false;
  }
}

function toggleFrameFullscreen() {
  const target = frameStage.value;
  if (!target) return;
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
  } else if (target.requestFullscreen) {
    target.requestFullscreen();
  }
}

function onVideoError() {
  if (!videoError.value) videoError.value = t("videoPlayFailed");
}

function toggleVideoFullscreen() {
  const target = videoStage.value || videoEl.value;
  if (!target) return;
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
  } else if (target.requestFullscreen) {
    target.requestFullscreen();
  } else if (videoEl.value?.webkitEnterFullscreen) {
    // iOS Safari 只支持 video 元素原生全屏
    videoEl.value.webkitEnterFullscreen();
  }
}

watch(tab, (value) => {
  if (value === "video") loadParsers();
}, { immediate: true });

onBeforeUnmount(teardownVideo);

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
        <button type="button" :class="{ on: tab === 'video' }" @click="tab = 'video'">{{ t("videoPlayer") }}</button>
        <button type="button" :class="{ on: tab === 'feedback' }" @click="tab = 'feedback'">{{ locale === "zh" ? "网站反馈" : "Feedback" }}</button>
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
        <label class="upload-btn">{{ t("uploadIcon") }}<input type="file" accept=".png,.jpg,.jpeg,.gif,.webp,image/png,image/jpeg,image/gif,image/webp" @change="uploadLogo" /></label>
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
    <section v-else-if="tab === 'video'" class="page form video-panel">
      <h1>{{ t("videoPlayer") }}</h1>
      <p class="meta">{{ t("videoLead") }}</p>

      <label>{{ t("videoParserLabel") }}</label>
      <select class="video-select" :value="selectedParser" @change="onParserSelect($event.target.value)">
        <option value="">{{ t("videoNoParser") }}</option>
        <option v-for="p in parsers" :key="p.id" :value="p.url">{{ p.title }}</option>
        <option value="__custom__">{{ t("videoParserCustom") }}</option>
      </select>
      <p v-if="!parsers.length" class="meta">{{ t("videoParserEmpty") }}</p>
      <input v-model="parserUrl" type="text" :placeholder="t('videoParserPlaceholder')" />
      <p class="meta">{{ t("videoParserHint") }}</p>

      <label>{{ t("videoUrlLabel") }}</label>
      <form class="video-form" @submit.prevent="resolveVideo">
        <input v-model="videoUrl" type="url" :placeholder="t('videoPlaceholder')" />
        <button class="primary" type="submit" :disabled="videoLoading">{{ videoLoading ? t("videoResolving") : t("videoPlay") }}</button>
      </form>
      <p v-if="videoError" class="video-error">{{ videoError }}</p>

      <!-- 直链：站内 HTML5 原生播放 -->
      <div v-if="videoCurrent" ref="videoStage" class="video-stage">
        <video ref="videoEl" controls playsinline preload="metadata" @error="onVideoError"></video>
        <div class="video-bar">
          <button type="button" @click="toggleVideoFullscreen">{{ t("videoFullscreen") }}</button>
          <button type="button" @click="clearVideo">{{ t("videoClose") }}</button>
          <span v-if="videoCurrent.title" class="video-name">{{ videoCurrent.title }}</span>
        </div>
        <p class="video-src">{{ videoCurrent.url }}</p>
      </div>

      <!-- 解析源：iframe 嵌入用户选/填的地址，可拖拽改大小、全屏 -->
      <div v-if="frameUrl" class="frame-block">
        <p class="meta frame-note">{{ t("videoFrameNote") }}</p>
        <div ref="frameStage" class="frame-stage">
          <iframe
            :src="frameUrl"
            class="frame-player"
            allow="autoplay; fullscreen; encrypted-media; picture-in-picture"
            allowfullscreen
            referrerpolicy="no-referrer"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-presentation"
          ></iframe>
        </div>
        <div class="video-bar">
          <button type="button" @click="toggleFrameFullscreen">{{ t("videoFullscreen") }}</button>
          <button type="button" @click="clearVideo">{{ t("videoClose") }}</button>
          <span class="video-drag-hint">{{ t("videoDragHint") }}</span>
        </div>
        <p class="video-src">{{ frameUrl }}</p>
      </div>
    </section>
    <section v-else-if="tab === 'feedback'" class="page feedback-page">
      <FeedbackBox inline :logged-in="true" />
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
        <b v-if="!ads[0].image_url || ads[0].image_url.endsWith('ad-placeholder.svg')" class="ad-no">{{ ads[0].no }}</b>
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
        <b v-if="!ad.image_url || ad.image_url.endsWith('ad-placeholder.svg')" class="ad-no">{{ ad.no }}</b>
        <span>{{ ad.title }}</span>
      </a>
    </aside>
  </div>
</template>

<style scoped>
.video-form {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}
.video-form input {
  flex: 1;
  min-width: 0;
}
.video-select {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid var(--line, #d1d5db);
  border-radius: 10px;
  font-size: 0.95rem;
  background: #fff;
  cursor: pointer;
}
.video-error {
  margin: 12px 0 0;
  color: #dc2626;
  font-size: 0.92rem;
}
.video-stage {
  margin-top: 18px;
  background: #000;
  border-radius: 12px;
  padding: 8px;
}
.video-stage video {
  width: 100%;
  max-height: 70vh;
  aspect-ratio: 16 / 9;
  background: #000;
  border-radius: 8px;
  display: block;
}
.video-stage:fullscreen {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0;
  border-radius: 0;
}
.video-stage:fullscreen video {
  max-height: 100vh;
  height: 100vh;
  aspect-ratio: auto;
  border-radius: 0;
}
.video-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  padding: 0 2px;
}
.video-bar button {
  border: 1px solid rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
}
.video-bar button:hover {
  background: rgba(255, 255, 255, 0.2);
}
.video-stage:fullscreen .video-bar {
  position: fixed;
  bottom: 16px;
  left: 16px;
  z-index: 2;
}
.video-name {
  color: #fff;
  font-size: 0.88rem;
}
.video-src {
  margin: 6px 2px 0;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.78rem;
  word-break: break-all;
}
.video-stage:fullscreen .video-src {
  display: none;
}

/* iframe 嵌入播放器：可拖拽改变大小 */
.frame-block {
  margin-top: 18px;
}
.frame-note {
  margin: 0 0 8px;
}
.frame-stage {
  position: relative;
  width: 100%;
  height: 56.25vw;
  max-height: 70vh;
  min-height: 220px;
  min-width: 280px;
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  resize: both;
}
.frame-player {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
}
/* 右下角拖拽提示角标，配合 CSS resize */
.frame-stage::after {
  content: "";
  position: absolute;
  right: 2px;
  bottom: 2px;
  width: 14px;
  height: 14px;
  pointer-events: none;
  background: linear-gradient(135deg, transparent 50%, rgba(255, 255, 255, 0.5) 50%, rgba(255, 255, 255, 0.5) 60%, transparent 60%, transparent 72%, rgba(255, 255, 255, 0.5) 72%, rgba(255, 255, 255, 0.5) 82%, transparent 82%);
  z-index: 1;
}
.frame-stage:fullscreen {
  width: 100vw;
  height: 100vh;
  max-height: none;
  border-radius: 0;
  resize: none;
}
.video-drag-hint {
  color: var(--muted, #6b7280);
  font-size: 0.8rem;
}
@media (max-width: 860px) {
  .video-panel { overflow-x: hidden; }
  .video-form { flex-direction: column; }
  .video-form .primary { width: 100%; min-height: 44px; }
  .video-select, .video-panel input { font-size: 16px; }
  .video-bar { flex-wrap: wrap; gap: 8px; }
  .video-bar button { min-height: 40px; }
  .video-stage video { max-height: 56vw; }
  .frame-stage {
    min-width: 0;
    width: 100%;
    height: auto;
    aspect-ratio: 16 / 9;
    max-height: 70vh;
    resize: none;
  }
  .frame-stage::after, .video-drag-hint { display: none; }
  .video-stage:fullscreen .video-bar,
  .frame-stage:fullscreen + .video-bar {
    left: max(12px, env(safe-area-inset-left));
    right: max(12px, env(safe-area-inset-right));
    bottom: max(12px, env(safe-area-inset-bottom));
  }
}
</style>
