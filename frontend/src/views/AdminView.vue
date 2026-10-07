<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import http, { setGate } from "../api";

const { locale } = useI18n();
const zh = computed(() => String(locale.value).startsWith("zh"));
function tx(cn, en) {
  return zh.value ? cn : en;
}

const router = useRouter();

const props = defineProps({ gate: String });
const ready = ref(false);
const missing = ref(false);
const section = ref("overview");
const query = ref("");
const pageNo = ref(1);
const pageSize = ref(10);
const jumpNo = ref(1);
const picked = ref([]);
const editor = ref(null);
const notice = ref("");
const grain = ref("day");
const trendFocus = ref("");
function pickTrend(key) {
  trendFocus.value = trendFocus.value === key ? "" : key;
}
function trendOn(key) {
  return !trendFocus.value || trendFocus.value === key;
}
function emptyTrend(kind) {
  const labels = [];
  const now = new Date();
  if (kind === "month") {
    for (let i = 11; i >= 0; i -= 1) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
      labels.push(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`);
    }
  } else {
    for (let i = 13; i >= 0; i -= 1) {
      const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
      labels.push(`${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`);
    }
  }
  const zeros = labels.map(() => 0);
  return { labels, register: [...zeros], login: [...zeros], total: [...zeros] };
}
const trend = ref(emptyTrend("day"));
const sectionTitle = computed(() => ({
  overview: tx("概览", "Overview"),
  alerts: tx("报警", "Alerts"),
  links: tx("链接", "Links"),
  structure: tx("栏目", "Tabs"),
  categories: tx("分类", "Categories"),
  news: tx("资讯", "News"),
  pages: tx("单页", "Pages"),
  notes: tx("公告", "Notices"),
  ads: tx("广告", "Ads"),
  crawl: tx("采集", "Crawl"),
  users: tx("用户", "Users"),
  proxies: tx("代理", "Proxies"),
  levels: tx("等级", "Levels"),
  security: tx("账号安全", "Security"),
}[section.value] || ""));
watch(section, () => { query.value = ""; pageNo.value = 1; jumpNo.value = 1; picked.value = []; editor.value = null; notice.value = ""; });
watch(query, () => { pageNo.value = 1; jumpNo.value = 1; picked.value = []; });
function pageOf(rows, keys) {
  const text = query.value.trim().toLowerCase();
  const filtered = text ? rows.filter((row) => keys.some((key) => String(row[key] ?? "").toLowerCase().includes(text))) : rows.slice();
  const size = pageSize.value;
  const pages = Math.max(1, Math.ceil(filtered.length / size) || 1);
  const current = Math.min(pageNo.value, pages);
  return { rows: filtered.slice((current - 1) * size, current * size), total: filtered.length, pages, current };
}
function goPage(n) {
  const pages = activeView.value.pages || 1;
  pageNo.value = Math.max(1, Math.min(pages, Number(n) || 1));
  jumpNo.value = pageNo.value;
}
function changePageSize() {
  pageNo.value = 1;
  jumpNo.value = 1;
}
const linkView = computed(() => pageOf(links.value.map((row) => ({ ...row, name: row.title_zh || row.title_en })), ["name", "url", "status", "source"]));
const tabView = computed(() => pageOf(tabs.value, ["title_zh", "title_en", "slug"]));
const catView = computed(() => pageOf(categories.value, ["title_zh", "title_en", "slug"]));
const newsView = computed(() => pageOf(news.value, ["title", "source", "category"]));
const pageView = computed(() => pageOf(pages.value, ["key", "title_zh", "title_en"]));
const noteView = computed(() => pageOf(announcements.value, ["title_zh", "title_en", "body_zh"]));
const adView = computed(() => pageOf(ads.value.map((row) => ({ ...row, where: slotWhere(row.slot) })), ["where", "title_zh", "title_en"]));
const crawlView = computed(() => pageOf(items.value, ["title", "url"]));
const userKind = ref("member");
const memberView = computed(() => pageOf(users.value.filter((row) => row.role !== "admin"), ["email", "role", "last_ip", "plan"]));
const adminUserView = computed(() => pageOf(users.value.filter((row) => row.role === "admin"), ["email", "role", "last_ip"]));
const proxyView = computed(() => pageOf(proxies.value.items || [], ["url"]));
const sourceView = computed(() => pageOf(proxies.value.source_items || [], ["url"]));
const levelView = computed(() => pageOf(levels.value, ["level"]));
const alertView = computed(() => pageOf(alerts.value, ["email", "ip", "detail"]));
const banView = computed(() => pageOf(ipBans.value, ["ip"]));
const views = { links: linkView, structure: tabView, categories: catView, news: newsView, pages: pageView, notes: noteView, ads: adView, crawl: crawlView, proxies: proxyView, sources: sourceView, levels: levelView, alerts: alertView, bans: banView };
const proxyKind = ref("alive");
const activeView = computed(() => {
  if (section.value === "proxies" && proxyKind.value === "sources") return sourceView.value;
  if (section.value === "users") return userKind.value === "admin" ? adminUserView.value : memberView.value;
  return views[section.value] ? views[section.value].value : { rows: [], total: 0, pages: 1, current: 1 };
});
function togglePick(id, on) {
  picked.value = on ? [...picked.value, id] : picked.value.filter((item) => item !== id);
}
function togglePage(rows, on) {
  const ids = rows.map((row) => row.id);
  picked.value = on ? [...new Set([...picked.value, ...ids])] : picked.value.filter((id) => !ids.includes(id));
}
const linkStats = ref({ total: 0, user: 0, system: 0 });
const bars = computed(() => [
  { name: tx("链接", "Links"), n: linkStats.value.total, color: "#4c84f5" },
  { name: tx("资讯", "News"), n: news.value.length, color: "#36cfc9" },
  { name: tx("用户", "Users"), n: users.value.length, color: "#b7c3d0" },
  { name: tx("广告", "Ads"), n: ads.value.length, color: "#8aa4d6" },
  { name: tx("栏目", "Tabs"), n: tabs.value.length, color: "#d0d5dd" },
]);
const barScale = computed(() => {
  const peak = Math.max(0, ...bars.value.map((item) => item.n));
  return peak <= 4 ? 4 : Math.ceil(peak / 4) * 4;
});
const barTicks = computed(() => [0, 1, 2, 3, 4].map((step) => Math.round((barScale.value / 4) * step)));
const sourceParts = computed(() => [
  { name: tx("系统收录", "System"), n: linkStats.value.system, color: "#4c84f5" },
  { name: tx("用户提交", "Users"), n: linkStats.value.user, color: "#f5a524" },
]);
const piePaths = computed(() => {
  const parts = sourceParts.value.filter((item) => item.n > 0);
  const total = parts.reduce((sum, item) => sum + item.n, 0) || 1;
  const minShare = parts.length > 1 ? 0.045 : 0;
  const weights = parts.map((item) => Math.max(item.n / total, minShare));
  const weightSum = weights.reduce((sum, item) => sum + item, 0) || 1;
  let acc = 0;
  return parts.map((item, index) => {
    const share = weights[index] / weightSum;
    const start = acc;
    acc += share;
    const end = index === parts.length - 1 ? 1 : acc;
    if (share >= 0.999) return { ...item, d: "M 80 18 A 62 62 0 1 1 79.9 18 Z" };
    const a0 = start * Math.PI * 2 - Math.PI / 2;
    const a1 = end * Math.PI * 2 - Math.PI / 2;
    const x0 = 80 + Math.cos(a0) * 62;
    const y0 = 80 + Math.sin(a0) * 62;
    const x1 = 80 + Math.cos(a1) * 62;
    const y1 = 80 + Math.sin(a1) * 62;
    const large = end - start > 0.5 ? 1 : 0;
    return { ...item, d: `M 80 80 L ${x0} ${y0} A 62 62 0 ${large} 1 ${x1} ${y1} Z` };
  });
});
const tabs = ref([]);
const categories = ref([]);
const links = ref([]);
const pages = ref([]);
const ads = ref([]);
const users = ref([]);
const jobs = ref([]);
const levels = ref([]);
const pointsPerLink = ref(1);
const items = ref([]);
const alerts = ref([]);
const news = ref([]);
const announcements = ref([]);
const noteForm = ref({ title_en: "", title_zh: "", body_en: "", body_zh: "", enabled: true });
const adminForm = ref({ email: "", password: "" });
const ownPass = ref({ current_password: "", new_password: "" });
const ipBans = ref([]);
const banIp = ref("");
const askCode = ref(false);
const captchaId = ref("");
const captchaTarget = ref(70);
const captchaShape = ref("round");
const captchaProgress = ref(0);
const dragging = ref(false);
const matched = ref(false);
const switchCode = ref("");
const proxies = ref({ count: 0, sources: 0, items: [], source_items: [], note: "" });
const me = ref(null);
const totp = ref(null);
const code = ref("");
const linkForm = ref({ category_id: "", title_en: "", title_zh: "", url: "", description_en: "", description_zh: "", is_free: false, is_hot: false });
const tabForm = ref({ slug: "", title_en: "", title_zh: "", kind: "links", adult: false });
const catForm = ref({ tab_id: "", slug: "", title_en: "", title_zh: "" });
const crawlForm = ref({ url: "", category_id: "" });
const adForm = ref({ slot: "banner", title_zh: "广告位", title_en: "Ad slot", image_url: "/ad-placeholder.svg", link_url: "/contact", enabled: true, sort: 0 });
const slotGroups = [
  { page: "首页顶部右侧", items: [{ id: "banner", where: "搜索框右边轮播" }] },
  { page: "首页右侧 GitHub", items: [
    { id: "github-growth", where: "增量榜下面" },
    { id: "github-total", where: "总量榜下面" },
  ] },
  { page: "每日资讯内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-general-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "AI工具内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-ai-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "跨境电商内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-cross-border-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "午夜媒体内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-media-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "TG群内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-telegram-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "关于我们右侧", items: [1, 2, 3].map((n) => ({ id: `about-${n}`, where: `右侧第 ${n} 个` })) },
  { page: "联系方式右侧", items: [1, 2, 3].map((n) => ({ id: `contact-${n}`, where: `右侧第 ${n} 个` })) },
  { page: "登录 / 注册左侧", items: [1, 2, 3].map((n) => ({ id: `auth-${n}`, where: `左侧轮播第 ${n} 张` })) },
  { page: "个人中心右侧", items: [1, 2].map((n) => ({ id: `account-${n}`, where: `右侧第 ${n} 个` })) },
  { page: "页面底部", items: [{ id: "footer", where: "页脚右侧广告" }] },
];
function slotWhere(id) {
  for (const group of slotGroups) {
    const found = group.items.find((item) => item.id === id);
    if (found) return `${group.page} · ${found.where}`;
  }
  return id;
}
const error = ref("");
const consoleEmail = ref("");
const consolePassword = ref("");
const consoleCode = ref("");
const needConsole = ref(false);

async function load() {
  const [t, c, l, p, a, u, j, i, lv, al, nw, notes, bans] = await Promise.all([
    http.get("/manage/tabs"),
    http.get("/manage/categories"),
    http.get("/manage/links"),
    http.get("/manage/pages"),
    http.get("/manage/ads"),
    http.get("/manage/users"),
    http.get("/manage/crawl/jobs"),
    http.get("/manage/crawl/items"),
    http.get("/manage/levels"),
    http.get("/manage/alerts"),
    http.get("/manage/news"),
    http.get("/manage/announcements"),
    http.get("/manage/ip-bans"),
  ]);
  tabs.value = t.data;
  categories.value = c.data;
  links.value = l.data;
  linkStats.value = (await http.get("/manage/link-stats")).data;
  pages.value = p.data;
  ads.value = a.data;
  users.value = u.data;
  jobs.value = j.data;
  items.value = i.data;
  levels.value = lv.data.levels || [];
  pointsPerLink.value = lv.data.points_per_link || 1;
  alerts.value = al.data;
  news.value = nw.data;
  announcements.value = notes.data;
  ipBans.value = bans.data;
  if (!linkForm.value.category_id && categories.value[0]) linkForm.value.category_id = categories.value[0].id;
  if (!catForm.value.tab_id && tabs.value[0]) catForm.value.tab_id = tabs.value[0].id;
  try {
    proxies.value = (await http.get("/manage/proxies")).data;
  } catch {
    proxies.value = { count: 0, sources: 0, items: [], note: "unavailable" };
  }
  await loadTrend();
}
async function loadTrend() {
  const frame = emptyTrend(grain.value);
  trend.value = frame;
  try {
    const { data } = await http.get("/manage/user-trend", { params: { grain: grain.value } });
    if (data.labels?.length) trend.value = data;
  } catch {
    trend.value = frame;
  }
}
const plot = computed(() => {
  const current = trend.value.labels?.length ? trend.value : emptyTrend(grain.value);
  const n = current.labels.length;
  const peak = Math.max(0, ...current.register, ...current.login, ...current.total);
  const max = peak <= 4 ? 4 : Math.ceil(peak / 4) * 4;
  const left = 36;
  const right = 16;
  const top = 28;
  const width = 668;
  const height = 148;
  const xAt = (index) => left + (n === 1 ? width / 2 : (index * width) / (n - 1));
  const yAt = (value) => top + height - (Number(value) / max) * height;
  const dots = (values) => values.map((value, index) => ({ x: xAt(index), y: yAt(value) }));
  const line = (values) => dots(values).map((point) => `${point.x},${point.y}`).join(" ");
  const ticks = [0, 1, 2, 3, 4].map((step) => {
    const value = Math.round((max / 4) * step);
    return { value, y: yAt(value) };
  });
  return {
    register: line(current.register),
    login: line(current.login),
    total: line(current.total),
    registerDots: dots(current.register),
    loginDots: dots(current.login),
    totalDots: dots(current.total),
    labels: current.labels.map((label) => (grain.value === "month" ? label.slice(2) : label)),
    xAt,
    ticks,
    base: top + height,
    left,
    right: left + width,
  };
});

onMounted(async () => {
  setGate(props.gate);
  try {
    await http.get("/manage/ping");
    me.value = (await http.get("/auth/console/me")).data;
    ready.value = true;
    await load();
  } catch (err) {
    if (err.response?.status === 404) {
      missing.value = true;
      router.replace("/");
    }
    else {
      needConsole.value = true;
      error.value = "";
      loadMatch();
    }
  }
});

async function loadMatch() {
  matched.value = false;
  captchaProgress.value = 0;
  const { data } = await http.post("/auth/captcha/match");
  captchaId.value = data.id;
  captchaTarget.value = data.target;
  captchaShape.value = data.shape || "round";
}
function slideTo(event) {
  const track = event.currentTarget.parentElement.getBoundingClientRect();
  const piece = 36;
  const travel = Math.max(piece, track.width - piece);
  const x = event.clientX - track.left - piece / 2;
  captchaProgress.value = Math.max(0, Math.min(100, Math.round((x / travel) * 100)));
}
function dragStart(event) {
  if (matched.value) return;
  dragging.value = true;
  event.currentTarget.setPointerCapture(event.pointerId);
}
function dragMove(event) {
  if (!dragging.value || matched.value) return;
  slideTo(event);
}
function dragEnd() {
  dragging.value = false;
  if (Math.abs(captchaProgress.value - captchaTarget.value) <= 6) {
    captchaProgress.value = captchaTarget.value;
    matched.value = true;
  } else {
    captchaProgress.value = 0;
  }
}
async function consoleLogin() {
  error.value = "";
  if (!matched.value) {
    error.value = "captcha required";
    return;
  }
  try {
    await http.post("/auth/console", {
      email: consoleEmail.value,
      password: consolePassword.value,
      totp: consoleCode.value,
      captcha_id: captchaId.value,
      captcha_progress: captchaProgress.value,
    });
    me.value = (await http.get("/auth/console/me")).data;
    ready.value = true;
    needConsole.value = false;
    askCode.value = false;
    await load();
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
    if (error.value === "totp required") askCode.value = true;
    loadMatch();
  }
}

async function setupTotp() {
  error.value = "";
  try {
    totp.value = (await http.post("/auth/console/totp/setup")).data;
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}

async function confirmTotp() {
  error.value = "";
  try {
    await http.post("/auth/console/totp/confirm", { code: code.value });
    me.value = (await http.get("/auth/console/me")).data;
    code.value = "";
    totp.value = null;
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}
async function toggleTotp(enabled) {
  error.value = "";
  if (!switchCode.value.trim()) {
    error.value = "invalid code";
    return;
  }
  try {
    await http.post("/auth/console/totp/switch", { enabled, code: switchCode.value });
    me.value = (await http.get("/auth/console/me")).data;
    switchCode.value = "";
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}
async function dropNews(id) {
  await http.delete(`/manage/news/${id}`);
  await load();
}
async function saveNote() {
  await http.post("/manage/announcements", noteForm.value);
  noteForm.value = { title_en: "", title_zh: "", body_en: "", body_zh: "", enabled: true };
  await load();
}
async function dropNote(id) {
  await http.delete(`/manage/announcements/${id}`);
  await load();
}

async function saveLink() {
  await http.post("/manage/links", linkForm.value);
  await load();
}
async function saveTab() {
  await http.post("/manage/tabs", tabForm.value);
  await load();
}
async function saveCategory() {
  await http.post("/manage/categories", catForm.value);
  await load();
}
async function savePage(page) {
  await http.put(`/manage/pages/${page.id}`, page);
}
async function fetchCrawl() {
  await http.post("/manage/crawl/fetch", crawlForm.value);
  await load();
}
async function approve(id) {
  await http.post(`/manage/crawl/items/${id}/approve`);
  await load();
}
async function saveAd() {
  await http.post("/manage/ads", adForm.value);
  await load();
}
async function removeAd(id) {
  await http.delete(`/manage/ads/${id}`);
  await load();
}
async function saveCounts(link) {
  await http.put(`/manage/links/${link.id}`, { favorite_count: link.favorite_count, recommend_count: link.recommend_count });
}
async function savePointRule() {
  const { data } = await http.put("/manage/point-rule", { points_per_link: pointsPerLink.value });
  pointsPerLink.value = data.points_per_link;
}
async function saveLevel(row) {
  await http.put(`/manage/levels/${row.level}`, { min_points: row.min_points, proxy_per_minute: row.proxy_per_minute });
}
async function dropProxy(url) {
  await http.delete("/manage/proxies", { params: { url } });
  await load();
}
async function dropSource(url) {
  await http.delete("/manage/proxy-sources", { params: { url } });
  await load();
}
function sourceLabel(source) {
  if (source === "user") return "用户提交";
  return "系统";
}
function openNew(kind) {
  const blank = {
    link: { ...linkForm.value, id: null },
    tab: { slug: "", title_en: "", title_zh: "", kind: "links", sort: 0, visible: true, adult: false },
    category: { tab_id: tabs.value[0]?.id || "", slug: "", title_en: "", title_zh: "", sort: 0, visible: true },
    note: { title_en: "", title_zh: "", body_en: "", body_zh: "", enabled: true },
    ad: { ...adForm.value, id: null },
    crawl: { url: "", category_id: categories.value[0]?.id || "" },
    admin: { email: "", password: "" },
    ban: { ip: "" },
  };
  editor.value = { kind, row: blank[kind] };
}
function openEdit(kind, row) {
  editor.value = { kind, row: { ...row } };
}
async function bump(field) {
  if (!picked.value.length) return;
  await http.post("/manage/links/bump", { ids: picked.value, field });
  picked.value = [];
  notice.value = tx("已按随机数累加", "Counts increased");
  await load();
}
async function removeIds(path, ids) {
  for (const id of ids) await http.delete(`${path}/${id}`);
  picked.value = [];
  await load();
}
async function saveEditor() {
  const { kind, row } = editor.value;
  error.value = "";
  try {
    if (kind === "link") {
      if (row.id) await http.put(`/manage/links/${row.id}`, row);
      else await http.post("/manage/links", row);
    } else if (kind === "tab") {
      if (row.id) await http.put(`/manage/tabs/${row.id}`, row);
      else await http.post("/manage/tabs", row);
    } else if (kind === "category") {
      if (row.id) await http.put(`/manage/categories/${row.id}`, row);
      else await http.post("/manage/categories", row);
    } else if (kind === "page") {
      await http.put(`/manage/pages/${row.id}`, row);
    } else if (kind === "note") {
      if (row.id) await http.put(`/manage/announcements/${row.id}`, row);
      else await http.post("/manage/announcements", row);
    } else if (kind === "ad") {
      if (row.id) await http.put(`/manage/ads/${row.id}`, row);
      else await http.post("/manage/ads", row);
    } else if (kind === "crawl") {
      await http.post("/manage/crawl/fetch", row);
    } else if (kind === "admin") {
      await http.post("/manage/admins", row);
    } else if (kind === "ban") {
      await http.post("/manage/ip-bans", { ip: row.ip });
    }
    editor.value = null;
    await load();
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}
async function banAlert(id) {
  await http.post(`/manage/alerts/${id}/ban`);
  await load();
}
async function banUser(user) {
  await http.put(`/manage/users/${user.id}`, { banned: !user.banned });
  await load();
}
async function createAdmin() {
  error.value = "";
  try {
    await http.post("/manage/admins", adminForm.value);
    adminForm.value = { email: "", password: "" };
    await load();
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}
async function resetPassword(user) {
  const password = window.prompt(tx("新密码至少 8 位", "New password, at least 8 characters"));
  if (!password) return;
  await http.put(`/manage/users/${user.id}/password`, { password });
}
async function resetTotp(user) {
  await http.post(`/manage/users/${user.id}/reset-totp`);
  await load();
}
async function changeOwnPassword() {
  error.value = "";
  try {
    await http.post("/auth/console/password", ownPass.value);
    ownPass.value = { current_password: "", new_password: "" };
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}
async function addBan() {
  await http.post("/manage/ip-bans", { ip: banIp.value });
  banIp.value = "";
  await load();
}
async function liftBan(ip) {
  await http.delete("/manage/ip-bans", { params: { ip } });
  await load();
}
async function setPlan(user, plan) {
  await http.put(`/manage/users/${user.id}`, { plan, days: 30 });
  await load();
}
async function setProxy(user, payload) {
  await http.put(`/manage/users/${user.id}`, payload);
  await load();
}
</script>

<template>
  <p v-if="missing" class="page">Not found.</p>
  <div v-else-if="needConsole" class="console-login">
    <div class="console-copy">
      <a class="console-brand" href="/"><img src="/logo.svg" alt="" />NEXA</a>
      <h1>{{ tx("管理后台", "Admin") }}</h1>
      <p>{{ tx("栏目、链接、资讯、广告、等级和用户都在这里维护。", "Tabs, links, news, ads, levels, and users are managed here.") }}</p>
    </div>
    <form class="console-card" @submit.prevent="consoleLogin">
      <h2>{{ tx("登录", "Sign in") }}</h2>
      <input v-model="consoleEmail" type="email" :placeholder="tx('邮箱', 'Email')" required />
      <input v-model="consolePassword" type="password" :placeholder="tx('密码', 'Password')" required />
      <input v-if="askCode" v-model="consoleCode" :placeholder="tx('验证器验证码', 'Authenticator code')" required />
      <div class="match" :class="['shape-' + captchaShape, { ok: matched }]">
        <div class="match-track">
          <span class="match-gap" :style="{ left: 'calc((100% - 36px) * ' + captchaTarget + ' / 100)' }"></span>
          <button class="match-piece" type="button" :style="{ left: 'calc((100% - 36px) * ' + captchaProgress + ' / 100)' }" @pointerdown="dragStart" @pointermove="dragMove" @pointerup="dragEnd" @pointercancel="dragEnd">{{ matched ? "✓" : "" }}</button>
        </div>
        <em>{{ matched ? tx("验证通过", "Matched") : tx("拖动滑块，对齐缺口", "Drag the piece onto the gap") }}</em>
      </div>
      <button class="primary" type="submit" :disabled="!matched">{{ tx("登录后台", "Open console") }}</button>
      <p v-if="error === 'captcha required'">{{ tx("请先把滑块对齐缺口。", "Line the piece up with the gap first.") }}</p>
      <p v-else-if="error === 'totp required'">{{ tx("已开启两步验证，请填写验证码。", "Two-factor is on. Enter the code.") }}</p>
      <p v-else-if="error === 'invalid credentials'">{{ tx("邮箱或密码不正确。", "Email or password is wrong.") }}</p>
      <p v-else-if="error">{{ error }}</p>
    </form>
  </div>
  <div v-else-if="!ready" class="page">Checking the console address…</div>
  <div v-else class="console-shell">
    <aside class="console-side">
      <a class="console-brand" href="/"><img src="/logo.svg" alt="" />NEXA</a>
      <p class="console-kicker">{{ tx("管理后台", "Admin") }}</p>
      <nav>
        <button class="text-btn" :class="{ on: section === 'overview' }" @click="section = 'overview'">{{ tx("概览", "Overview") }}</button>
        <button class="text-btn" :class="{ on: section === 'alerts' }" @click="section = 'alerts'">{{ tx("报警", "Alerts") }} {{ alerts.filter((item) => !item.handled).length }}</button>
        <button class="text-btn" :class="{ on: section === 'links' }" @click="section = 'links'">{{ tx("链接", "Links") }}</button>
        <button class="text-btn" :class="{ on: section === 'structure' }" @click="section = 'structure'">{{ tx("栏目", "Tabs") }}</button>
        <button class="text-btn" :class="{ on: section === 'news' }" @click="section = 'news'">{{ tx("资讯", "News") }}</button>
        <button class="text-btn" :class="{ on: section === 'pages' }" @click="section = 'pages'">{{ tx("单页", "Pages") }}</button>
        <button class="text-btn" :class="{ on: section === 'notes' }" @click="section = 'notes'">{{ tx("公告", "Notices") }}</button>
        <button class="text-btn" :class="{ on: section === 'ads' }" @click="section = 'ads'">{{ tx("广告", "Ads") }}</button>
        <button class="text-btn" :class="{ on: section === 'crawl' }" @click="section = 'crawl'">{{ tx("采集", "Crawl") }}</button>
        <button class="text-btn" :class="{ on: section === 'users' }" @click="section = 'users'">{{ tx("用户", "Users") }}</button>
        <button class="text-btn" :class="{ on: section === 'proxies' }" @click="section = 'proxies'">{{ tx("代理", "Proxies") }}</button>
        <button class="text-btn" :class="{ on: section === 'levels' }" @click="section = 'levels'">{{ tx("等级", "Levels") }}</button>
        <button class="text-btn" :class="{ on: section === 'security' }" @click="section = 'security'">{{ tx("账号安全", "Security") }}</button>
      </nav>
    </aside>
    <div class="console-main">
    <header class="console-top"><strong>{{ sectionTitle }}</strong><em>{{ me.email }}</em></header>
    <div class="admin">
      <section v-if="section === 'overview'" class="form overview">
        <div class="stat-row">
          <div v-for="item in bars" :key="item.name"><b>{{ item.n }}</b><span>{{ item.name }}</span></div>
        </div>
        <div class="chart-card trend-card">
        <h3>{{ tx("用户趋势", "Users") }}</h3>
        <div class="trend-legend">
          <div class="grain">
            <button type="button" :class="{ on: grain === 'day' }" @click="grain = 'day'; loadTrend()">{{ tx("天", "Day") }}</button>
            <button type="button" :class="{ on: grain === 'month' }" @click="grain = 'month'; loadTrend()">{{ tx("月", "Month") }}</button>
          </div>
          <button type="button" :class="{ on: trendFocus === 'register', dim: trendFocus && trendFocus !== 'register' }" @click="pickTrend('register')"><i class="dot reg"></i>{{ tx("注册", "Sign-ups") }}</button>
          <button type="button" :class="{ on: trendFocus === 'login', dim: trendFocus && trendFocus !== 'login' }" @click="pickTrend('login')"><i class="dot log"></i>{{ tx("登录", "Sign-ins") }}</button>
          <button type="button" :class="{ on: trendFocus === 'total', dim: trendFocus && trendFocus !== 'total' }" @click="pickTrend('total')"><i class="dot tot"></i>{{ tx("总用户", "Total") }}</button>
        </div>
        <svg viewBox="0 0 720 214" class="chart trend">
          <g v-for="tick in plot.ticks" :key="tick.value">
            <line :x1="plot.left" :y1="tick.y" :x2="plot.right" :y2="tick.y" stroke="#eef1f4" />
            <text :x="plot.left - 8" :y="tick.y + 4" text-anchor="end" font-size="11" fill="#98a2b3">{{ tick.value }}</text>
          </g>
          <polyline :points="plot.total" fill="none" stroke="#b7c3d0" :stroke-width="trendOn('total') ? 2.4 : 1.4" stroke-dasharray="4 3" stroke-linejoin="round" stroke-linecap="round" :opacity="trendOn('total') ? 1 : 0.18" />
          <polyline :points="plot.login" fill="none" stroke="#36cfc9" :stroke-width="trendOn('login') ? 2.4 : 1.4" stroke-linejoin="round" stroke-linecap="round" :opacity="trendOn('login') ? 1 : 0.18" />
          <polyline :points="plot.register" fill="none" stroke="#4c84f5" :stroke-width="trendOn('register') ? 2.4 : 1.4" stroke-linejoin="round" stroke-linecap="round" :opacity="trendOn('register') ? 1 : 0.18" />
          <circle v-for="(point, index) in plot.totalDots" :key="'t' + index" :cx="point.x" :cy="point.y" r="3" fill="#fff" stroke="#b7c3d0" stroke-width="1.4" :opacity="trendOn('total') ? 1 : 0.18" />
          <circle v-for="(point, index) in plot.loginDots" :key="'l' + index" :cx="point.x" :cy="point.y" r="3" fill="#fff" stroke="#36cfc9" stroke-width="1.4" :opacity="trendOn('login') ? 1 : 0.18" />
          <circle v-for="(point, index) in plot.registerDots" :key="'r' + index" :cx="point.x" :cy="point.y" r="3.2" fill="#fff" stroke="#4c84f5" stroke-width="1.6" :opacity="trendOn('register') ? 1 : 0.18" />
          <text v-for="(label, index) in plot.labels" :key="label + index" :x="plot.xAt(index)" y="198" text-anchor="middle" font-size="11" fill="#98a2b3">{{ grain === "day" && index % 2 ? "" : label }}</text>
        </svg>
        </div>
        <div class="chart-row">
          <div class="chart-card">
            <h3>{{ tx("数量对比", "Totals") }}</h3>
            <svg viewBox="0 0 520 210" class="chart">
              <g v-for="tick in barTicks" :key="tick">
                <line x1="36" :y1="168 - (tick / barScale) * 140" x2="500" :y2="168 - (tick / barScale) * 140" stroke="#eef1f4" />
                <text x="30" :y="172 - (tick / barScale) * 140" text-anchor="end" font-size="11" fill="#98a2b3">{{ tick }}</text>
              </g>
              <g v-for="(item, index) in bars" :key="item.name">
                <rect :x="58 + index * 90" :y="168 - (item.n / barScale) * 140" width="42" :height="Math.max(item.n ? 2 : 0, (item.n / barScale) * 140)" :fill="item.color" rx="6" />
                <text :x="79 + index * 90" :y="160 - (item.n / barScale) * 140" text-anchor="middle" font-size="11" fill="#667085">{{ item.n }}</text>
                <text :x="79 + index * 90" y="190" text-anchor="middle" font-size="12" fill="#667085">{{ item.name }}</text>
              </g>
            </svg>
          </div>
          <div class="chart-card pie-card">
            <h3>{{ tx("链接来源", "Link sources") }}</h3>
            <div class="pie-body">
              <svg viewBox="0 0 160 160" class="chart pie">
                <circle cx="80" cy="80" r="62" fill="#f2f4f7" />
                <path v-for="item in piePaths" :key="item.name" :d="item.d" :fill="item.color" />
                <circle cx="80" cy="80" r="36" fill="#fff" />
                <text x="80" y="76" text-anchor="middle" font-size="13" fill="#98a2b3">{{ tx("合计", "Total") }}</text>
                <text x="80" y="96" text-anchor="middle" font-size="18" fill="#1f2937">{{ linkStats.total }}</text>
              </svg>
              <div>
                <p v-for="item in sourceParts" :key="item.name"><i :style="{ background: item.color }"></i>{{ item.name }} <b>{{ item.n }}</b></p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-else class="form list-page">
        <div v-if="section !== 'security'" class="list-bar">
          <input v-model="query" :placeholder="tx('搜索当前列表', 'Search this list')" />
          <button v-if="section === 'links'" class="primary" type="button" @click="openNew('link')">{{ tx("新增", "Add") }}</button>
          <button v-if="section === 'structure'" class="primary" type="button" @click="openNew('tab')">{{ tx("新增栏目", "Add tab") }}</button>
          <button v-if="section === 'structure'" type="button" @click="section = 'categories'">{{ tx("分类列表", "Categories") }}</button>
          <button v-if="section === 'categories'" class="primary" type="button" @click="openNew('category')">{{ tx("新增分类", "Add category") }}</button>
          <button v-if="section === 'categories'" type="button" @click="section = 'structure'">{{ tx("返回栏目", "Back to tabs") }}</button>
          <button v-if="section === 'notes'" class="primary" type="button" @click="openNew('note')">{{ tx("新增", "Add") }}</button>
          <button v-if="section === 'ads'" class="primary" type="button" @click="openNew('ad')">{{ tx("新增", "Add") }}</button>
          <button v-if="section === 'crawl'" class="primary" type="button" @click="openNew('crawl')">{{ tx("新增采集", "Fetch") }}</button>
          <template v-if="section === 'proxies'">
            <button type="button" :class="{ primary: proxyKind === 'alive' }" @click="proxyKind = 'alive'; pageNo = 1">{{ tx("有效代理", "Working") }} {{ proxies.count || 0 }}</button>
            <button type="button" :class="{ primary: proxyKind === 'sources' }" @click="proxyKind = 'sources'; pageNo = 1">{{ tx("开源代理池", "Source lists") }} {{ proxies.sources || 0 }}</button>
          </template>
          <template v-if="section === 'users'">
            <button type="button" :class="{ primary: userKind === 'member' }" @click="userKind = 'member'; pageNo = 1">{{ tx("前台会员", "Members") }}</button>
            <button type="button" :class="{ primary: userKind === 'admin' }" @click="userKind = 'admin'; pageNo = 1">{{ tx("管理员", "Admins") }}</button>
            <button v-if="userKind === 'admin'" class="primary" type="button" @click="openNew('admin')">{{ tx("新增管理员", "Add admin") }}</button>
          </template>
          <button v-if="section === 'alerts'" class="primary" type="button" @click="openNew('ban')">{{ tx("禁用 IP", "Block IP") }}</button>
          <template v-if="section === 'links'">
            <button type="button" :disabled="!picked.length" @click="bump('favorite_count')">{{ tx("收藏累加", "Add saves") }}</button>
            <button type="button" :disabled="!picked.length" @click="bump('recommend_count')">{{ tx("推荐累加", "Add picks") }}</button>
            <button type="button" :disabled="!picked.length" @click="bump('click_count')">{{ tx("点击累加", "Add clicks") }}</button>
            <button type="button" :disabled="!picked.length" @click="removeIds('/manage/links', picked)">{{ tx("批量删除", "Delete selected") }}</button>
          </template>
          <button v-if="section === 'news'" type="button" :disabled="!picked.length" @click="removeIds('/manage/news', picked)">{{ tx("批量删除", "Delete selected") }}</button>
          <button v-if="section === 'ads'" type="button" :disabled="!picked.length" @click="removeIds('/manage/ads', picked)">{{ tx("批量删除", "Delete selected") }}</button>
          <button v-if="section === 'notes'" type="button" :disabled="!picked.length" @click="removeIds('/manage/announcements', picked)">{{ tx("批量删除", "Delete selected") }}</button>
          <span v-if="notice">{{ notice }}</span>
        </div>
        <p v-if="section === 'levels'">{{ tx("积分门槛和每分钟代理次数可以改。等级本身固定为 0 到 10。", "Point thresholds and proxy limits can be edited. Levels stay 0 to 10.") }}</p>
        <p v-if="section === 'proxies'">{{ proxies.note || tx("每 3 分钟检测一次，打不开的代理会删掉。", "Checked every 3 minutes. Unusable proxies are removed.") }}</p>
        <div v-if="section === 'security'" class="security-page">
          <article class="security-card">
            <header>
              <h3>{{ tx("验证器", "Authenticator") }}</h3>
              <span class="pill" :class="{ on: me.totp_enabled }">{{ me.totp_enabled ? tx("登录需要验证码", "Required at sign-in") : me.totp_bound ? tx("已绑定", "Bound") : tx("未绑定", "Not bound") }}</span>
            </header>
            <p>{{ tx("用手机验证器扫码绑定。不绑定也可以登录；绑定后可以打开登录验证。", "Scan with a phone authenticator. Sign-in still works without it. After binding, you can require a code.") }}</p>
            <template v-if="totp">
              <div class="qr" v-html="totp.svg"></div>
              <p class="secret">{{ totp.secret }}</p>
              <div class="bind-row">
                <input v-model="code" inputmode="numeric" maxlength="6" :placeholder="tx('App 里的 6 位验证码', '6-digit code from the app')" />
                <button class="primary" type="button" @click="confirmTotp">{{ tx("完成绑定", "Finish") }}</button>
              </div>
            </template>
            <template v-else-if="!me.totp_bound">
              <button class="primary" type="button" @click="setupTotp">{{ tx("扫码绑定", "Scan to bind") }}</button>
            </template>
            <template v-else>
              <input v-model="switchCode" inputmode="numeric" maxlength="6" :placeholder="tx('先填 6 位验证码，再拨开关', 'Enter the 6-digit code, then use the switch')" />
              <label class="switch" :class="{ locked: switchCode.trim().length < 6 }">
                <input :key="String(me.totp_enabled) + error" type="checkbox" :checked="me.totp_enabled" :disabled="switchCode.trim().length < 6" @change="toggleTotp($event.target.checked)" />
                <i></i>
                <span>{{ tx("登录时要求验证码", "Require a code at sign-in") }}</span>
              </label>
              <button type="button" @click="setupTotp">{{ tx("重新扫码绑定", "Scan again") }}</button>
            </template>
          </article>
          <article class="security-card">
            <header><h3>{{ tx("登录密码", "Password") }}</h3></header>
            <p>{{ tx("修改当前管理员的登录密码。", "Change the password for this admin account.") }}</p>
            <input v-model="ownPass.current_password" type="password" :placeholder="tx('当前密码', 'Current password')" />
            <input v-model="ownPass.new_password" type="password" :placeholder="tx('新密码至少 8 位', 'New password, at least 8 characters')" />
            <button class="primary" type="button" @click="changeOwnPassword">{{ tx("保存密码", "Save password") }}</button>
          </article>
          <article class="security-card">
            <header><h3>{{ tx("投稿积分", "Submission points") }}</h3></header>
            <p>{{ tx("前台用户每提交一个通过审核的链接，获得这么多积分。", "Members receive this many points for each accepted link.") }}</p>
            <input v-model.number="pointsPerLink" type="number" min="1" />
            <button class="primary" type="button" @click="savePointRule">{{ tx("保存积分规则", "Save point rule") }}</button>
          </article>
          <p v-if="error" class="security-error">{{ error === "invalid code" ? tx("验证码不正确，还没有绑定成功。", "That code is not valid, so nothing was changed.") : error }}</p>
        </div>

        <div v-else class="table-scroll">
          <table>
            <thead>
              <tr>
                <th><input type="checkbox" :checked="activeView.rows.length && activeView.rows.every((row) => picked.includes(row.id))" @change="togglePage(activeView.rows, $event.target.checked)" /></th>
                <template v-if="section === 'links'">
                  <th>{{ tx("名称", "Name") }}</th><th>{{ tx("地址", "URL") }}</th><th>{{ tx("来源", "Source") }}</th><th>{{ tx("收藏", "Saves") }}</th><th>{{ tx("推荐", "Picks") }}</th><th>{{ tx("点击", "Clicks") }}</th>
                </template>
                <template v-else-if="section === 'structure'">
                  <th>ID</th><th>slug</th><th>{{ tx("中文名", "Chinese") }}</th><th>{{ tx("英文名", "English") }}</th><th>{{ tx("类型", "Kind") }}</th><th>{{ tx("排序", "Sort") }}</th><th>{{ tx("显示", "Visible") }}</th><th>18+</th>
                </template>
                <template v-else-if="section === 'categories'">
                  <th>ID</th><th>{{ tx("栏目", "Tab") }}</th><th>slug</th><th>{{ tx("中文名", "Chinese") }}</th><th>{{ tx("英文名", "English") }}</th><th>{{ tx("排序", "Sort") }}</th><th>{{ tx("显示", "Visible") }}</th>
                </template>
                <template v-else-if="section === 'news'">
                  <th>{{ tx("分类", "Topic") }}</th><th>{{ tx("标题", "Title") }}</th><th>{{ tx("来源", "Source") }}</th>
                </template>
                <template v-else-if="section === 'pages'">
                  <th>key</th><th>{{ tx("标题", "Title") }}</th>
                </template>
                <template v-else-if="section === 'notes'">
                  <th>{{ tx("标题", "Title") }}</th><th>{{ tx("状态", "Status") }}</th>
                </template>
                <template v-else-if="section === 'ads'">
                  <th>{{ tx("位置", "Slot") }}</th><th>{{ tx("名称", "Name") }}</th>
                </template>
                <template v-else-if="section === 'crawl'">
                  <th>{{ tx("标题", "Title") }}</th><th>{{ tx("地址", "URL") }}</th>
                </template>
                <template v-else-if="section === 'users' && userKind === 'admin'">
                  <th>{{ tx("邮箱", "Email") }}</th><th>{{ tx("验证器", "Authenticator") }}</th><th>IP</th>
                </template>
                <template v-else-if="section === 'users'">
                  <th>{{ tx("邮箱", "Email") }}</th><th>{{ tx("昵称", "Name") }}</th><th>{{ tx("会员", "Plan") }}</th><th>{{ tx("等级", "Level") }}</th><th>{{ tx("代理", "Proxy") }}</th><th>IP</th><th>{{ tx("注册", "Joined") }}</th>
                </template>
                <template v-else-if="section === 'proxies' && proxyKind === 'sources'">
                  <th>{{ tx("开源列表", "Source list") }}</th>
                </template>
                <template v-else-if="section === 'proxies'">
                  <th>{{ tx("代理", "Proxy") }}</th><th>{{ tx("检测时间", "Checked") }}</th>
                </template>
                <template v-else-if="section === 'levels'">
                  <th>{{ tx("等级", "Level") }}</th><th>{{ tx("积分门槛", "Points") }}</th><th>{{ tx("每分钟次数", "Per minute") }}</th>
                </template>
                <template v-else-if="section === 'alerts'">
                  <th>{{ tx("邮箱", "Email") }}</th><th>IP</th><th>{{ tx("说明", "Detail") }}</th>
                </template>
                <th>{{ tx("操作", "Actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in activeView.rows" :key="row.id || row.url || row.level">
                <td><input type="checkbox" :checked="picked.includes(row.id)" @change="togglePick(row.id, $event.target.checked)" /></td>
                <template v-if="section === 'links'">
                  <td>{{ row.title_zh || row.title_en }}</td><td class="clip">{{ row.url }}</td><td>{{ sourceLabel(row.source) }}</td><td>{{ row.favorite_count }}</td><td>{{ row.recommend_count }}</td><td>{{ row.click_count }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('link', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="removeIds('/manage/links', [row.id])">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'structure'">
                  <td>{{ row.id }}</td><td>{{ row.slug }}</td><td>{{ row.title_zh }}</td><td>{{ row.title_en }}</td><td>{{ row.kind }}</td><td>{{ row.sort }}</td><td>{{ row.visible ? tx("是", "Yes") : tx("否", "No") }}</td><td>{{ row.adult ? tx("是", "Yes") : tx("否", "No") }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('tab', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="removeIds('/manage/tabs', [row.id])">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'categories'">
                  <td>{{ row.id }}</td><td>{{ row.tab_id }}</td><td>{{ row.slug }}</td><td>{{ row.title_zh }}</td><td>{{ row.title_en }}</td><td>{{ row.sort }}</td><td>{{ row.visible ? tx("是", "Yes") : tx("否", "No") }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('category', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="removeIds('/manage/categories', [row.id])">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'news'">
                  <td>{{ row.category }}</td><td>{{ row.title }}</td><td>{{ row.source }}</td>
                  <td class="row-actions"><button type="button" @click="dropNews(row.id)">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'pages'">
                  <td>{{ row.key }}</td><td>{{ row.title_zh || row.title_en }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('page', row)">{{ tx("编辑", "Edit") }}</button></td>
                </template>
                <template v-else-if="section === 'notes'">
                  <td>{{ row.title_zh || row.title_en }}</td><td>{{ row.enabled ? tx("显示", "On") : tx("隐藏", "Off") }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('note', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="dropNote(row.id)">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'ads'">
                  <td>{{ row.where }}</td><td>{{ row.title_zh || row.title_en }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('ad', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="removeAd(row.id)">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'crawl'">
                  <td>{{ row.title }}</td><td class="clip">{{ row.url }}</td>
                  <td class="row-actions"><button type="button" @click="approve(row.id)">{{ tx("收录", "Approve") }}</button></td>
                </template>
                <template v-else-if="section === 'users' && userKind === 'admin'">
                  <td>{{ row.email }}</td><td>{{ row.totp_enabled ? tx("已开启", "On") : tx("未开启", "Off") }}</td><td>{{ row.banned ? tx("已禁用", "Disabled") : row.last_ip }}</td>
                  <td class="row-actions">
                    <button type="button" @click="resetPassword(row)">{{ tx("重置密码", "Reset password") }}</button>
                    <button type="button" @click="resetTotp(row)">{{ tx("重置验证器", "Reset authenticator") }}</button>
                    <button type="button" @click="banUser(row)">{{ row.banned ? tx("解封", "Enable") : tx("禁用", "Disable") }}</button>
                  </td>
                </template>
                <template v-else-if="section === 'users'">
                  <td>{{ row.email }}</td>
                  <td>{{ row.display_name || "—" }}</td>
                  <td>{{ row.plan === "vip" ? "VIP" : tx("免费", "Free") }}</td>
                  <td>Lv.{{ row.level }} · {{ row.points }}</td>
                  <td>
                    <div class="proxy-edit">
                      <button type="button" :class="{ primary: row.proxy_unlimited }" @click="setProxy(row, { proxy_unlimited: !row.proxy_unlimited })">{{ row.proxy_unlimited ? tx("取消白名单", "Limited") : tx("设白名单", "Unlimited") }}</button>
                      <input v-model="row.proxy_limit" type="number" min="0" :placeholder="tx('次数', 'Limit')" />
                      <button type="button" @click="setProxy(row, { proxy_limit: row.proxy_limit === '' || row.proxy_limit == null ? null : Number(row.proxy_limit) })">{{ tx("保存", "Save") }}</button>
                    </div>
                  </td>
                  <td>{{ row.banned ? tx("已禁用", "Disabled") : (row.last_ip || "—") }}</td>
                  <td>{{ (row.created_at || "").slice(0, 10) }}</td>
                  <td class="row-actions">
                    <button type="button" @click="setPlan(row, row.plan === 'vip' ? 'free' : 'vip')">{{ row.plan === "vip" ? tx("改免费", "Make free") : tx("改 VIP", "Make VIP") }}</button>
                    <button type="button" @click="resetPassword(row)">{{ tx("重置密码", "Reset password") }}</button>
                    <button type="button" @click="banUser(row)">{{ row.banned ? tx("解封", "Enable") : tx("禁用", "Disable") }}</button>
                  </td>
                </template>
                <template v-else-if="section === 'proxies' && proxyKind === 'sources'">
                  <td class="clip">{{ row.url }}</td>
                  <td class="row-actions"><button type="button" @click="dropSource(row.url)">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'proxies'">
                  <td class="clip">{{ row.url }}</td><td>{{ row.checked_at }}</td>
                  <td class="row-actions"><button type="button" @click="dropProxy(row.url)">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'levels'">
                  <td>Lv.{{ row.level }}</td>
                  <td><input v-model.number="row.min_points" type="number" /></td>
                  <td><input v-model.number="row.proxy_per_minute" type="number" /></td>
                  <td class="row-actions"><button type="button" @click="saveLevel(row)">{{ tx("保存", "Save") }}</button></td>
                </template>
                <template v-else-if="section === 'alerts'">
                  <td>{{ row.email }}</td><td>{{ row.ip }}</td><td>{{ row.detail }}</td>
                  <td class="row-actions"><button v-if="!row.handled" type="button" @click="banAlert(row.id)">{{ tx("封禁", "Ban") }}</button><span v-else>{{ tx("已处理", "Done") }}</span></td>
                </template>
              </tr>
              <tr v-if="!activeView.rows.length"><td colspan="8">{{ tx("没有记录", "No rows") }}</td></tr>
            </tbody>
          </table>
        </div>
        <div v-if="section !== 'security'" class="console-pager">
          <span class="pager-total">{{ tx(`共 ${activeView.total} 条`, `${activeView.total} total`) }}</span>
          <button type="button" :disabled="activeView.current <= 1" @click="goPage(activeView.current - 1)">‹</button>
          <button type="button" class="is-current">{{ activeView.current }}</button>
          <button type="button" :disabled="activeView.current >= activeView.pages" @click="goPage(activeView.current + 1)">›</button>
          <select v-model.number="pageSize" @change="changePageSize">
            <option :value="10">{{ tx("10条/页", "10 / page") }}</option>
            <option :value="20">{{ tx("20条/页", "20 / page") }}</option>
            <option :value="50">{{ tx("50条/页", "50 / page") }}</option>
            <option :value="100">{{ tx("100条/页", "100 / page") }}</option>
          </select>
          <span>{{ tx("前往", "Go to") }}</span>
          <input v-model.number="jumpNo" type="number" min="1" :max="activeView.pages" @keyup.enter="goPage(jumpNo)" @change="goPage(jumpNo)" />
          <span>{{ tx("页", "") }}</span>
        </div>
      </section>

      <div v-if="editor" class="console-modal" @click.self="editor = null">
        <form class="form" @submit.prevent="saveEditor">
          <h3>{{ tx("编辑", "Edit") }}</h3>
          <template v-if="editor.kind === 'link'">
            <select v-model="editor.row.category_id"><option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.title_zh || cat.title_en }}</option></select>
            <input v-model="editor.row.title_zh" :placeholder="tx('中文名称', 'Chinese name')" />
            <input v-model="editor.row.title_en" :placeholder="tx('英文名称', 'English name')" />
            <input v-model="editor.row.url" placeholder="https://" required />
            <input v-model="editor.row.description_zh" :placeholder="tx('中文简介', 'Chinese description')" />
            <input v-model="editor.row.description_en" :placeholder="tx('英文简介', 'English description')" />
            <label><input type="checkbox" v-model="editor.row.is_free" /> {{ tx("免费", "Free") }}</label>
            <label><input type="checkbox" v-model="editor.row.is_hot" /> {{ tx("热门", "Hot") }}</label>
          </template>
          <template v-else-if="editor.kind === 'tab'">
            <input v-model="editor.row.slug" placeholder="slug" required />
            <input v-model="editor.row.title_zh" :placeholder="tx('中文名', 'Chinese name')" />
            <input v-model="editor.row.title_en" :placeholder="tx('英文名', 'English name')" />
            <select v-model="editor.row.kind">
              <option value="links">links</option>
              <option value="home">home</option>
            </select>
            <input v-model.number="editor.row.sort" type="number" :placeholder="tx('排序，数字越大越靠前', 'Sort, larger numbers come first')" />
            <label><input type="checkbox" v-model="editor.row.visible" /> {{ tx("显示", "Visible") }}</label>
            <label><input type="checkbox" v-model="editor.row.adult" /> 18+</label>
          </template>
          <template v-else-if="editor.kind === 'category'">
            <select v-model="editor.row.tab_id"><option v-for="tab in tabs" :key="tab.id" :value="tab.id">{{ tab.title_zh || tab.title_en }}</option></select>
            <input v-model="editor.row.slug" placeholder="slug" required />
            <input v-model="editor.row.title_zh" :placeholder="tx('中文名', 'Chinese name')" />
            <input v-model="editor.row.title_en" :placeholder="tx('英文名', 'English name')" />
            <input v-model.number="editor.row.sort" type="number" :placeholder="tx('排序，数字越大越靠前', 'Sort, larger numbers come first')" />
            <label><input type="checkbox" v-model="editor.row.visible" /> {{ tx("显示", "Visible") }}</label>
          </template>
          <template v-else-if="editor.kind === 'page'">
            <input v-model="editor.row.title_zh" />
            <input v-model="editor.row.title_en" />
            <textarea v-model="editor.row.body_zh" rows="4"></textarea>
            <textarea v-model="editor.row.body_en" rows="4"></textarea>
            <input v-model="editor.row.email" placeholder="Email" />
            <input v-model="editor.row.phone" placeholder="Phone" />
            <input v-model="editor.row.im" placeholder="Telegram" />
          </template>
          <template v-else-if="editor.kind === 'note'">
            <input v-model="editor.row.title_zh" :placeholder="tx('中文标题', 'Chinese title')" />
            <input v-model="editor.row.title_en" :placeholder="tx('英文标题', 'English title')" />
            <textarea v-model="editor.row.body_zh" rows="3"></textarea>
            <textarea v-model="editor.row.body_en" rows="3"></textarea>
            <label><input type="checkbox" v-model="editor.row.enabled" /> {{ tx("显示", "Visible") }}</label>
          </template>
          <template v-else-if="editor.kind === 'ad'">
            <select v-model="editor.row.slot">
              <optgroup v-for="group in slotGroups" :key="group.page" :label="group.page">
                <option v-for="item in group.items" :key="item.id" :value="item.id">{{ item.where }}</option>
              </optgroup>
            </select>
            <input v-model="editor.row.title_zh" :placeholder="tx('中文名称', 'Chinese name')" />
            <input v-model="editor.row.title_en" :placeholder="tx('英文名称', 'English name')" />
            <input v-model="editor.row.image_url" :placeholder="tx('图片地址', 'Image URL')" />
            <input v-model="editor.row.link_url" :placeholder="tx('跳转地址', 'Link')" />
          </template>
          <template v-else-if="editor.kind === 'crawl'">
            <input v-model="editor.row.url" placeholder="https://" required />
            <select v-model="editor.row.category_id"><option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.title_zh || cat.title_en }}</option></select>
          </template>
          <template v-else-if="editor.kind === 'admin'">
            <input v-model="editor.row.email" type="email" :placeholder="tx('邮箱', 'Email')" required />
            <input v-model="editor.row.password" type="password" :placeholder="tx('密码至少 8 位', 'Password, at least 8 characters')" required />
          </template>
          <template v-else-if="editor.kind === 'ban'">
            <input v-model="editor.row.ip" placeholder="IP" required />
          </template>
          <p v-if="error">{{ error }}</p>
          <div class="row-actions">
            <button class="primary" type="submit">{{ tx("保存", "Save") }}</button>
            <button type="button" @click="editor = null">{{ tx("取消", "Cancel") }}</button>
          </div>
        </form>
      </div>
    </div>
    </div>
  </div>
</template>
