<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import http, { setGate, track } from "../api";

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
const listTab = ref("");
const listCat = ref("");
const listSource = ref("");
const listStatus = ref("");
const filterCats = computed(() => categories.value.filter((cat) => !listTab.value || cat.tab_id === Number(listTab.value)));
const pageNo = ref(1);
const pageSize = ref(10);
const jumpNo = ref(1);
const picked = ref([]);
const editor = ref(null);
const editorTitle = computed(() => {
  const names = {
    link: ["编辑链接", "Edit link"],
    tab: ["编辑栏目", "Edit tab"],
    category: ["编辑分类", "Edit category"],
    page: ["编辑页面", "Edit page"],
    note: ["编辑公告", "Edit notice"],
    ad: ["编辑广告", "Edit ad"],
    crawl: ["编辑采集", "Edit crawl"],
    admin: ["新增管理员", "Add admin"],
    ban: ["禁用 IP", "Block IP"],
    password: ["重置密码", "Reset password"],
  };
  const pair = names[editor.value?.kind] || ["编辑", "Edit"];
  return tx(pair[0], pair[1]);
});
const notice = ref("");
const ask = ref(null);
function confirmDelete(text, run) {
  ask.value = { text, run };
}
async function acceptAsk() {
  const job = ask.value;
  ask.value = null;
  notice.value = tx("正在删除…", "Deleting…");
  try {
    await job.run();
    notice.value = tx("已删除", "Deleted");
  } catch (err) {
    notice.value = err.response?.data?.detail || tx("删除失败", "Delete failed");
  }
}
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
  mail: tx("邮件", "Mail"),
  feedback: tx("反馈", "Feedback"),
  actions: tx("日志", "Logs"),
}[section.value] || ""));
watch(section, () => {
  query.value = "";
  listTab.value = "";
  listCat.value = "";
  listSource.value = "";
  listStatus.value = "";
  pageNo.value = 1;
  jumpNo.value = 1;
  picked.value = [];
  editor.value = null;
  notice.value = "";
  load();
  if (ready.value) track("view", `admin:${section.value}`);
});
watch([query, listTab, listCat, listSource, listStatus], () => { pageNo.value = 1; jumpNo.value = 1; picked.value = []; });
function hitText(row, keys) {
  const text = query.value.trim().toLowerCase();
  if (!text) return true;
  return keys.some((key) => String(row[key] ?? "").toLowerCase().includes(text));
}
function inTab(categoryId) {
  const tabId = Number(listTab.value) || 0;
  const catId = Number(listCat.value) || 0;
  if (!tabId && !catId) return true;
  if (catId && categoryId !== catId) return false;
  if (!tabId) return true;
  const cat = categories.value.find((item) => item.id === categoryId);
  return cat?.tab_id === tabId;
}
function pageOf(rows, keys) {
  const filtered = rows.filter((row) => hitText(row, keys));
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
const linkView = computed(() => pageOf(links.value.filter((row) => inTab(row.category_id) && (!listSource.value || row.source === listSource.value)).map((row) => ({ ...row, name: row.title_zh || row.title_en })), ["name", "url"]));
const tabView = computed(() => pageOf(tabs.value.filter((row) => !listStatus.value || row.kind === listStatus.value), ["title_zh", "title_en", "slug"]));
const catView = computed(() => pageOf(categories.value.filter((row) => !listTab.value || row.tab_id === Number(listTab.value)), ["title_zh", "title_en", "slug"]));
const newsView = computed(() => pageOf(news.value.filter((row) => !listStatus.value || row.category === listStatus.value), ["title", "source"]));
const pageView = computed(() => pageOf(pages.value, ["key", "title_zh", "title_en"]));
const noteKind = ref("ticker");
const noteView = computed(() => pageOf(announcements.value.filter((row) => (noteKind.value === "popup" ? row.popup : !row.popup) && (listStatus.value === "" || String(row.enabled) === listStatus.value)), ["title_zh", "title_en"]));
const adView = computed(() => {
  const order = slotGroups.flatMap((group) => group.items.map((item) => ({ ...item, page: group.page })));
  const rows = [];
  order.forEach((item, index) => {
    const matched = ads.value
      .filter((ad) => ad.slot === item.id)
      .sort((a, b) => (a.sort - b.sort) || (a.id - b.id));
    const group = matched.length ? matched : [{ slot: item.id, title_zh: "", enabled: false, image_url: "", show_placeholder: true }];
    group.forEach((row, slide) => {
      const where = `${item.page} · ${item.where}`;
      rows.push({
        ...row,
        where,
        page: item.page,
        no: index + 1,
        carousel: !!item.carousel,
        slideCount: group.length,
      });
    });
  });
  const picked = rows.filter((row) => (!listStatus.value || String(!!row.enabled) === listStatus.value) && (!listTab.value || row.page === listTab.value));
  return pageOf(picked, ["where", "title_zh", "title_en"]);
});
const crawlKind = ref("jobs");
const crawlLogs = ref([]);
const logJob = ref(0);
const jobView = computed(() => pageOf(jobs.value.filter((row) => inTab(row.category_id) && (!listStatus.value || row.status === listStatus.value)).map((row) => ({ ...row, category: categories.value.find((cat) => cat.id === row.category_id)?.title_zh || "" })), ["name", "list_url"]));
const crawlView = computed(() => pageOf(items.value.filter((row) => inTab(row.category_id)), ["title", "url"]));
const userKind = ref("member");
const memberView = computed(() => pageOf(users.value.filter((row) => row.role !== "admin" && (!listStatus.value || row.plan === listStatus.value)), ["email", "last_ip"]));
const adminUserView = computed(() => pageOf(users.value.filter((row) => row.role === "admin"), ["email", "role", "last_ip"]));
const proxyView = computed(() => pageOf(proxies.value.items || [], ["url"]));
const sourceView = computed(() => pageOf(proxies.value.source_items || [], ["url"]));
const levelView = computed(() => pageOf(levels.value, ["level"]));
const alertView = computed(() => pageOf(alerts.value, ["email", "ip", "detail"]));
const banView = computed(() => pageOf(ipBans.value, ["ip"]));
const logKind = ref("user");
const logAccount = ref("");
const logFrom = ref("");
const logTo = ref("");
const logAction = ref("");
const logResult = ref("");
const logIp = ref("");
function isAdminLog(row) {
  return row.role === "admin";
}
const logActions = computed(() => {
  const pool = actions.value.filter((row) => (logKind.value === "admin" ? isAdminLog(row) : !isAdminLog(row)));
  return [...new Set(pool.map((row) => row.action).filter(Boolean))];
});
const actionView = computed(() => pageOf(actions.value.filter((row) => {
  if (logKind.value === "admin" ? !isAdminLog(row) : isAdminLog(row)) return false;
  const account = logAccount.value.trim().toLowerCase();
  const who = `${row.email || ""} ${row.display_name || ""}`.toLowerCase();
  if (account && !who.includes(account)) return false;
  const ip = logIp.value.trim().toLowerCase();
  if (ip && !String(row.ip || "").toLowerCase().includes(ip)) return false;
  if (logAction.value && row.action !== logAction.value) return false;
  if (logResult.value === "ok" && !row.ok) return false;
  if (logResult.value === "fail" && row.ok) return false;
  const stamp = String(row.created_at || "").slice(0, 10);
  if (logFrom.value && stamp < logFrom.value) return false;
  if (logTo.value && stamp > logTo.value) return false;
  return true;
}), ["email", "display_name", "detail"]));
const views = { links: linkView, structure: tabView, categories: catView, news: newsView, pages: pageView, notes: noteView, ads: adView, crawl: crawlView, proxies: proxyView, sources: sourceView, levels: levelView, alerts: alertView, bans: banView, actions: actionView };
const actionNames = {
  register: ["注册", "Register"],
  login: ["登录", "Login"],
  admin_login: ["管理员登录", "Admin login"],
  logout: ["退出", "Log out"],
  admin_logout: ["管理员退出", "Admin log out"],
  profile: ["修改资料", "Profile"],
  password: ["修改密码", "Password"],
  admin_password: ["管理员改密", "Admin password"],
  totp_setup: ["验证器设置", "Authenticator setup"],
  totp_confirm: ["验证器确认", "Authenticator confirm"],
  totp_switch: ["验证器开关", "Authenticator switch"],
  plan: ["开通会员", "Plan"],
  submit: ["提交链接", "Submit link"],
  feedback: ["提交反馈", "Feedback"],
  feedback_reply: ["回复反馈", "Feedback reply"],
  upload: ["上传图片", "Upload"],
  proxy_token: ["代理令牌", "Proxy token"],
  video: ["视频播放", "Video"],
  mark: ["收藏或推荐", "Save or pick"],
  tab: ["栏目", "Tab"],
  category: ["分类", "Category"],
  link: ["链接", "Link"],
  page: ["单页", "Page"],
  ad: ["广告", "Ad"],
  news: ["资讯", "News"],
  notice: ["公告", "Notice"],
  user: ["用户", "User"],
  admin_create: ["新增管理员", "Add admin"],
  admin_upload: ["后台上传", "Admin upload"],
  ip_ban: ["禁用 IP", "Block IP"],
  ip_unban: ["解除 IP", "Unblock IP"],
  alert: ["处理报警", "Alert"],
  crawl: ["采集任务", "Crawl job"],
  crawl_item: ["采集条目", "Crawl item"],
  crawl_fetch: ["手动采集", "Manual crawl"],
  level: ["等级", "Level"],
  point_rule: ["积分规则", "Point rule"],
  mail_settings: ["邮件设置", "Mail settings"],
  mail_test: ["测试邮件", "Test mail"],
  mail_send: ["发送邮件", "Send mail"],
  mail_task: ["邮件任务", "Mail task"],
  feedback_admin: ["处理反馈", "Feedback admin"],
  proxy_clear: ["清空代理", "Clear proxies"],
  proxy_source_clear: ["清空代理源", "Clear proxy sources"],
  admin: ["后台操作", "Admin action"],
  account: ["账号页", "Account page"],
  click: ["点击链接", "Link click"],
  search: ["站内搜索", "Site search"],
  view: ["浏览页面", "Page view"],
  locale: ["切换语言", "Language"],
  tab: ["切换栏目", "Tab"],
  notice: ["打开公告", "Notice"],
  search_web: ["外部搜索", "Web search"],
  adult: ["成人栏目", "Adult tab"],
};
function actorText(row) {
  const email = String(row.email || "").trim();
  const name = String(row.display_name || "").trim();
  if (!email && !name) return tx("未登录", "Signed out");
  if (email && name) return `${email}（${name}）`;
  return email || name;
}
function actionLabel(code) {
  const pair = actionNames[code];
  return pair ? tx(pair[0], pair[1]) : code;
}
const pageNames = {
  "/": ["首页", "Home"],
  "/about": ["关于", "About"],
  "/contact": ["联系", "Contact"],
  "/advertise": ["广告合作", "Advertise"],
  "/login": ["登录", "Log in"],
  "/register": ["注册", "Register"],
  "/submit": ["个人中心", "Account"],
  profile: ["个人资料", "Profile"],
  levels: ["等级规则", "Levels"],
  marks: ["收藏推荐", "Saved"],
  submit: ["提交链接", "Submit a link"],
  proxy: ["免费代理", "Proxies"],
  video: ["视频播放", "Video"],
  feedback: ["网站反馈", "Feedback"],
  "admin:overview": ["概览", "Overview"],
  "admin:alerts": ["报警", "Alerts"],
  "admin:links": ["链接", "Links"],
  "admin:structure": ["栏目", "Tabs"],
  "admin:categories": ["分类", "Categories"],
  "admin:news": ["资讯", "News"],
  "admin:pages": ["单页", "Pages"],
  "admin:notes": ["公告", "Notices"],
  "admin:ads": ["广告", "Ads"],
  "admin:crawl": ["采集", "Crawl"],
  "admin:users": ["用户", "Users"],
  "admin:proxies": ["代理", "Proxies"],
  "admin:levels": ["等级", "Levels"],
  "admin:security": ["账号安全", "Security"],
  "admin:mail": ["邮件", "Mail"],
  "admin:feedback": ["反馈", "Feedback"],
  "admin:actions": ["日志", "Logs"],
};
function placeName(raw) {
  const key = String(raw || "").trim();
  if (key.startsWith("/:")) return `${tx("首页", "Home")} · ${key.slice(2)}`;
  if (key.startsWith("submit:")) return `${tx("个人中心", "Account")} · ${placeName(key.slice(7))}`;
  const pair = pageNames[key];
  return pair ? tx(pair[0], pair[1]) : key;
}
function actionText(row) {
  const base = actionLabel(row.action);
  const detail = String(row.detail || "").trim();
  if (row.action === "view" || row.action === "account" || row.action === "tab" || row.action === "notice") {
    const where = placeName(detail);
    return where ? `${base} · ${where}` : base;
  }
  const hit = detail.match(/^(GET|POST|PUT|PATCH|DELETE)\s+(\S+)(?:\s+([\s\S]+))?$/);
  if (!hit) return detail && detail !== row.action ? `${base} · ${detail}` : base;
  const verb = { POST: tx("新增", "Create"), PUT: tx("修改", "Update"), PATCH: tx("修改", "Update"), DELETE: tx("删除", "Delete"), GET: tx("查看", "Open") }[hit[1]] || hit[1];
  const path = hit[2].replace(/\?.*$/, "");
  const parts = path.replace(/^\/api\//, "").split("/").filter(Boolean);
  const tail = parts[parts.length - 1] || "";
  const id = /^\d+$/.test(tail) ? ` #${tail}` : "";
  const extra = [hit[3], hit[2].includes("?") ? hit[2].split("?")[1] : ""].filter(Boolean).join(" ");
  return extra ? `${verb}${base}${id} · ${extra}` : `${verb}${base}${id}`;
}
const proxyKind = ref("alive");
const activeView = computed(() => {
  if (section.value === "proxies" && proxyKind.value === "sources") return sourceView.value;
  if (section.value === "crawl") return crawlKind.value === "jobs" ? jobView.value : crawlView.value;
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
  { name: tx("资讯", "News"), n: linkStats.value.news || 0, color: "#36cfc9" },
  { name: tx("用户", "Users"), n: linkStats.value.users || 0, color: "#b7c3d0" },
  { name: tx("广告", "Ads"), n: linkStats.value.ads || 0, color: "#8aa4d6" },
  { name: tx("栏目", "Tabs"), n: linkStats.value.tabs || 0, color: "#d0d5dd" },
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
const actions = ref([]);
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
const mailState = ref({ settings: {}, tasks: [], logs: [] });
const mailForm = ref({ subject: "", body: "", audience: "all", email: "", run_at: "", interval_minutes: 0 });
const mailTest = ref("");
const mailHint = ref("");
const mailTab = ref("channels");
const feedbackRows = ref([]);
const feedbackCurrent = ref(null);
const feedbackNote = ref("");
const feedbackStatus = ref("pending");
const me = ref(null);
const userOpen = ref(false);
const totp = ref(null);
const code = ref("");
const linkForm = ref({ category_id: "", title_en: "", title_zh: "", url: "", description_en: "", description_zh: "", is_free: false, is_hot: false });
const tabForm = ref({ slug: "", title_en: "", title_zh: "", kind: "links", adult: false });
const catForm = ref({ tab_id: "", slug: "", title_en: "", title_zh: "" });
const crawlForm = ref({ url: "", category_id: "" });
const adForm = ref({ slot: "banner", title_zh: "广告位", title_en: "Ad slot", image_url: "/ad-placeholder.svg", link_url: "/contact", enabled: true, sort: 0 });
const slotGroups = [
  { page: "首页顶部右侧", items: [{ id: "banner", where: "搜索框右边轮播", carousel: true }] },
  { page: "首页栏目上方", items: [{ id: "strip", where: "通栏横图" }] },
  { page: "首页右侧", items: [
    { id: "github-growth", where: "增量榜下面" },
    { id: "github-total", where: "总量榜下面" },
    { id: "rail", where: "竖图广告" },
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

const listLoading = ref(true);
const refreshing = ref(false);
async function refreshSection() {
  if (refreshing.value) return;
  refreshing.value = true;
  try {
    await load(true);
    if (section.value === "crawl") await loadLogs();
  } finally {
    refreshing.value = false;
  }
}
let loadSeq = 0;
async function load(quiet = false) {
  const seq = ++loadSeq;
  const name = section.value;
  if (!quiet) listLoading.value = true;
  const tasks = [];
  const apply = [];
  const take = (url, fn) => tasks.push(http.get(url).then((res) => apply.push(() => fn(res.data))));
  if (name === "overview") {
    take("/manage/link-stats", (data) => { linkStats.value = data; });
    tasks.push(loadTrend());
  } else if (name === "links") {
    take("/manage/links", (data) => { links.value = data; });
    take("/manage/tabs", (data) => { tabs.value = data; });
    take("/manage/categories", (data) => { categories.value = data; });
  } else if (name === "structure" || name === "categories") {
    take("/manage/tabs", (data) => { tabs.value = data; });
    take("/manage/categories", (data) => { categories.value = data; });
  } else if (name === "news") {
    take("/manage/news", (data) => { news.value = data; });
  } else if (name === "pages") {
    take("/manage/pages", (data) => { pages.value = data; });
  } else if (name === "notes") {
    take("/manage/announcements", (data) => { announcements.value = data; });
  } else if (name === "ads") {
    take("/manage/ads", (data) => { ads.value = data; });
  } else if (name === "crawl") {
    take("/manage/crawl/jobs", (data) => { jobs.value = data; });
    take("/manage/crawl/items", (data) => { items.value = data; });
    take("/manage/tabs", (data) => { tabs.value = data; });
    take("/manage/categories", (data) => { categories.value = data; });
  } else if (name === "users") {
    take("/manage/users", (data) => { users.value = data; });
    take("/manage/levels", (data) => { levels.value = data.levels || []; pointsPerLink.value = data.points_per_link || 1; });
  } else if (name === "levels" || name === "security") {
    take("/manage/levels", (data) => { levels.value = data.levels || []; pointsPerLink.value = data.points_per_link || 1; });
  } else if (name === "alerts") {
    take("/manage/alerts", (data) => { alerts.value = data; });
    take("/manage/ip-bans", (data) => { ipBans.value = data; });
  } else if (name === "proxies") {
    tasks.push(http.get("/manage/proxies").then((res) => apply.push(() => { proxies.value = res.data; })).catch(() => apply.push(() => { proxies.value = { count: 0, sources: 0, items: [], note: "unavailable" }; })));
  } else if (name === "mail") {
    take("/manage/mail", (data) => { mailState.value = data; });
  } else if (name === "feedback") {
    take("/manage/feedback", (data) => { feedbackRows.value = data; if (feedbackCurrent.value) feedbackCurrent.value = data.find((row) => row.id === feedbackCurrent.value.id) || feedbackCurrent.value; });
  } else if (name === "actions") {
    take("/manage/actions", (data) => { actions.value = data; });
  }
  if (name !== "alerts") take("/manage/alerts", (data) => { alerts.value = data; });
  try {
    await Promise.all(tasks);
    if (seq !== loadSeq) return;
    apply.forEach((fn) => fn());
    if (!linkForm.value.category_id && categories.value[0]) linkForm.value.category_id = categories.value[0].id;
    if (!catForm.value.tab_id && tabs.value[0]) catForm.value.tab_id = tabs.value[0].id;
  } catch (err) {
    if (seq === loadSeq) notice.value = err.response?.data?.detail || tx("加载失败", "Load failed");
  } finally {
    if (seq === loadSeq) listLoading.value = false;
  }
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

watch(section, (value) => {
  if (value === "crawl") loadLogs();
  if (value !== "crawl") return;
  if (window.__crawlPoll) clearInterval(window.__crawlPoll);
  window.__crawlPoll = setInterval(() => {
    if (section.value === "crawl" && jobs.value.some((row) => row.status === "running")) {
      load(true);
      loadLogs();
    }
  }, 3000);
});

function closeUserMenu() {
  userOpen.value = false;
}

onMounted(async () => {
  window.addEventListener("click", closeUserMenu);
  setGate(props.gate);
  try {
    await http.get("/manage/ping", { timeout: 8000 });
    me.value = (await http.get("/auth/console/me", { timeout: 8000 })).data;
    ready.value = true;
    await load();
  } catch (err) {
    const status = err.response?.status;
    if (status === 404) {
      missing.value = true;
      router.replace("/");
    } else if (status === 401 || status === 403 || !err.response) {
      needConsole.value = true;
      error.value = err.response ? "" : tx("后台暂时没有响应，可以稍后再登录。", "The console did not respond. Try signing in again.");
      loadMatch();
    } else {
      ready.value = true;
      error.value = err.response?.data?.detail || "load failed";
    }
  }
});

onBeforeUnmount(() => window.removeEventListener("click", closeUserMenu));

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
  confirmDelete(tx("删除这条资讯？", "Delete this news item?"), async () => {
    await http.delete(`/manage/news/${id}`);
    await load();
  });
}
async function saveNote() {
  await http.post("/manage/announcements", noteForm.value);
  noteForm.value = { title_en: "", title_zh: "", body_en: "", body_zh: "", enabled: true };
  await load();
}
async function dropNote(id) {
  confirmDelete(tx("删除这条公告？", "Delete this notice?"), async () => {
    await http.delete(`/manage/announcements/${id}`);
    await load();
  });
}
async function toggleCrawl(row) {
  const previous = row.auto_crawl;
  row.auto_crawl = !row.auto_crawl;
  try {
    await http.put(`/manage/tabs/${row.id}`, { auto_crawl: row.auto_crawl });
  } catch (err) {
    row.auto_crawl = previous;
    notice.value = err.response?.data?.detail || "save failed";
  }
}
async function toggleNote(row) {
  const source = announcements.value.find((item) => item.id === row.id);
  if (!source) return;
  const previous = !!source.enabled;
  source.enabled = !previous;
  try {
    await http.put(`/manage/announcements/${source.id}`, { enabled: source.enabled });
  } catch (err) {
    source.enabled = previous;
    notice.value = err.response?.data?.detail || "save failed";
  }
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
async function loadLogs() {
  const { data } = await http.get("/manage/crawl/logs", { params: { job_id: logJob.value || 0 } });
  crawlLogs.value = data;
}
async function stopJob(row) {
  notice.value = tx("正在停止…", "Stopping…");
  await http.post(`/manage/crawl/jobs/${row.id}/stop`);
  notice.value = tx("已停止", "Stopped");
  await load();
}
async function runJob(row) {
  notice.value = tx("正在开始采集…", "Starting…");
  await http.post(`/manage/crawl/jobs/${row.id}/run`);
  notice.value = tx("已开始采集", "Started");
  await load();
}
async function dropJob(id) {
  confirmDelete(tx("删除这个采集任务？未收录的结果会一起删掉。", "Delete this crawl job and its pending items?"), async () => {
    await http.delete(`/manage/crawl/jobs/${id}`);
    await load();
  });
}
function crawlStatus(row) {
  const map = { running: ["采集中", "Running"], stopped: ["已停止", "Stopped"], done: ["完成", "Done"], error: ["失败", "Failed"], idle: ["等待", "Waiting"] };
  const pair = map[row.status] || map.idle;
  return tx(pair[0], pair[1]);
}
async function approve(id) {
  notice.value = tx("正在收录…", "Approving…");
  await http.post(`/manage/crawl/items/${id}/approve`);
  notice.value = tx("已收录", "Approved");
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
  confirmDelete(tx("删除这个代理？", "Delete this proxy?"), async () => {
    await http.delete("/manage/proxies", { params: { url } });
    await load();
  });
}
async function dropSource(url) {
  confirmDelete(tx("删除这个代理源？", "Delete this source?"), async () => {
    await http.delete("/manage/proxy-sources", { params: { url } });
    await load();
  });
}
function sourceLabel(source) {
  if (source === "user") return "用户提交";
  return "系统";
}
function openNew(kind) {
  const blank = {
    link: { ...linkForm.value, id: null },
    tab: { slug: "", title_en: "", title_zh: "", kind: "links", sort: 0, visible: true, adult: false, auto_crawl: false },
    category: { tab_id: tabs.value[0]?.id || "", slug: "", title_en: "", title_zh: "", sort: 0, visible: true },
    note: { title_en: "", title_zh: "", body_en: "", body_zh: "", image_url: "", popup: noteKind.value === "popup", enabled: true },
    ad: { ...adForm.value, id: null },
    crawl: { id: null, name: "", keyword: "", list_url: "", category_id: categories.value[0]?.id || "", interval_minutes: 1440 },
    admin: { email: "", password: "" },
    ban: { ip: "" },
  };
  editor.value = { kind, row: blank[kind] };
  fillPick(blank[kind]);
}
function openEdit(kind, row) {
  editor.value = { kind, row: { ...row } };
  fillPick(row);
}
const pickOpen = ref("");
const tabQuery = ref("");
const catQuery = ref("");
function tabName(id) {
  const tab = tabs.value.find((item) => item.id === id);
  return tab ? (tab.title_zh || tab.title_en) : "";
}
function fillPick(row) {
  const cat = categories.value.find((item) => item.id === row?.category_id);
  const tabId = cat?.tab_id || row?.tab_id || "";
  if (row) row._tab_id = tabId;
  tabQuery.value = tabName(tabId);
  catQuery.value = cat ? (cat.title_zh || cat.title_en) : "";
  pickOpen.value = "";
}
const tabHits = computed(() => {
  const q = tabQuery.value.trim().toLowerCase();
  return tabs.value.filter((tab) => !q || `${tab.title_zh} ${tab.title_en}`.toLowerCase().includes(q)).slice(0, 12);
});
const catHits = computed(() => {
  const tabId = editor.value?.row?._tab_id;
  const q = catQuery.value.trim().toLowerCase();
  return categories.value.filter((cat) => (!tabId || cat.tab_id === tabId) && (!q || `${cat.title_zh} ${cat.title_en}`.toLowerCase().includes(q))).slice(0, 12);
});
function chooseTab(tab) {
  editor.value.row._tab_id = tab.id;
  editor.value.row.tab_id = tab.id;
  tabQuery.value = tab.title_zh || tab.title_en;
  const still = categories.value.find((cat) => cat.id === editor.value.row.category_id && cat.tab_id === tab.id);
  if (!still && editor.value.kind !== "category") {
    editor.value.row.category_id = "";
    catQuery.value = "";
  }
  pickOpen.value = "";
}
function chooseCat(cat) {
  editor.value.row.category_id = cat.id;
  editor.value.row._tab_id = cat.tab_id;
  catQuery.value = cat.title_zh || cat.title_en;
  tabQuery.value = tabName(cat.tab_id);
  pickOpen.value = "";
}
async function bump(field) {
  if (!picked.value.length) return;
  await http.post("/manage/links/bump", { ids: picked.value, field });
  picked.value = [];
  notice.value = tx("已按随机数累加", "Counts increased");
  await load();
}
async function removeIds(path, ids) {
  const list = [...ids];
  confirmDelete(tx(`删除选中的 ${list.length} 条？`, `Delete ${list.length} selected?`), async () => {
    for (const id of list) await http.delete(`${path}/${id}`);
    picked.value = [];
    await load();
  });
}
const dropOver = ref(false);
async function uploadImageFile(file) {
  if (!file || !file.type.startsWith("image/")) return;
  const body = new FormData();
  body.append("file", file);
  const res = await http.post("/manage/uploads", body);
  editor.value.row.image_url = res.data.url;
  dropOver.value = false;
}
function onImagePick(event) {
  uploadImageFile(event.target.files?.[0]);
}
async function addSlide(row) {
  await http.post("/manage/ads", {
    slot: row.slot,
    title_zh: "广告位",
    title_en: "Ad slot",
    image_url: "",
    link_url: "",
    enabled: true,
    show_placeholder: true,
    sort: (row.sort || 0) + 1,
  });
  await load();
}
async function removeSlide(row) {
  confirmDelete(tx("删除这一张轮播图？", "Delete this slide?"), async () => {
    await http.delete(`/manage/ads/${row.id}`);
    await load();
  });
}
async function toggleAd(row, key) {
  const source = ads.value.find((ad) => ad.id === row.id);
  if (!source) return;
  const previous = !!source[key];
  source[key] = !previous;
  try {
    await http.put(`/manage/ads/${source.id}`, { [key]: source[key] });
    source.updated_at = new Date().toISOString();
  } catch (err) {
    source[key] = previous;
    notice.value = err.response?.data?.detail || "save failed";
  }
}
function onImageDrop(event) {
  dropOver.value = false;
  uploadImageFile(event.dataTransfer?.files?.[0]);
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
      if (!(row.keyword || "").trim() && !(row.list_url || "").trim() && !(row.name || "").trim()) {
        error.value = tx("填写关键词或网址", "Enter a keyword or a URL");
        return;
      }
      if (!row.category_id) {
        error.value = tx("请选择分类", "Choose a category");
        return;
      }
      if (row.id) await http.put(`/manage/crawl/jobs/${row.id}`, row);
      else await http.post("/manage/crawl/jobs", row);
    } else if (kind === "admin") {
      await http.post("/manage/admins", row);
    } else if (kind === "ban") {
      await http.post("/manage/ip-bans", { ip: row.ip });
    } else if (kind === "password") {
      if ((row.password || "").length < 8) throw Object.assign(new Error("short"), { response: { data: { detail: "password too short" } } });
      await http.put(`/manage/users/${row.id}/password`, { password: row.password });
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
function resetPassword(user) {
  error.value = "";
  editor.value = { kind: "password", row: { id: user.id, email: user.email, password: "" } };
}
async function saveProxyLimit(row) {
  const raw = String(row.proxy_limit ?? "").trim();
  const value = raw === "" ? null : Math.max(0, Math.trunc(Number(raw)));
  if (raw !== "" && Number.isNaN(Number(raw))) return;
  row.proxy_limit = value;
  await http.put(`/manage/users/${row.id}`, { proxy_limit: value });
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
  confirmDelete(tx("解除这个 IP 的禁用？", "Remove this IP ban?"), async () => {
    await http.delete("/manage/ip-bans", { params: { ip } });
    await load();
  });
}
async function setPlan(user, plan) {
  await http.put(`/manage/users/${user.id}`, { plan, days: 30 });
  await load();
}
function totpText(row) {
  if (!row.totp_confirmed) return tx("未绑定", "Not bound");
  return row.totp_enabled ? tx("绑定已开启", "Bound, on") : tx("绑定未开启", "Bound, off");
}
async function saveMail() {
  const s = mailState.value.settings;
  const missing = s.gmail_enabled && (!s.gmail_user || !s.gmail_pass) ? tx("开启 Gmail 需要填写账号和密码", "Gmail needs an account and password")
    : s.netease_enabled && (!s.netease_user || !s.netease_pass) ? tx("开启 163 需要填写账号和密码", "163 needs an account and password")
    : s.sendgrid_enabled && !s.sendgrid_key ? tx("开启 SendGrid 需要填写 API Key", "SendGrid needs an API key")
    : s.mailgun_enabled && (!s.mailgun_key || !s.mailgun_domain) ? tx("开启 Mailgun 需要填写 API Key 和域名", "Mailgun needs an API key and domain")
    : "";
  if (missing) {
    mailHint.value = missing;
    return;
  }
  try {
    const { data } = await http.put("/manage/mail", s);
    mailState.value.settings = data;
    notice.value = tx("已保存", "Saved");
    mailHint.value = "";
  } catch (err) {
    mailHint.value = err.response?.data?.detail || tx("保存失败", "Save failed");
  }
}
async function sendTest() {
  mailHint.value = tx("正在发送测试邮件…", "Sending the test…");
  try {
    const { data } = await http.post("/manage/mail/test", { email: mailTest.value });
    mailHint.value = data.ok ? tx(`已通过 ${data.channel} 发出，请到邮箱查看。`, `Sent through ${data.channel}. Check the inbox.`) : (data.message || tx("没有发出去", "Not sent"));
    await load();
  } catch (err) {
    mailHint.value = err.response?.data?.detail || tx("发送失败", "Send failed");
  }
}
async function sendMail() {
  notice.value = tx("正在发送…", "Sending…");
  const { data } = await http.post("/manage/mail/send", mailForm.value);
  notice.value = tx(`已处理 ${data.sent || 0} 封`, `Handled ${data.sent || 0}`);
  await load();
}
async function addMailTask() {
  await http.post("/manage/mail/tasks", mailForm.value);
  notice.value = tx("已加入定时", "Scheduled");
  await load();
}
async function dropMailTask(id) {
  confirmDelete(tx("删除这个定时邮件？", "Delete this scheduled mail?"), async () => {
    await http.delete(`/manage/mail/tasks/${id}`);
    await load();
  });
}
async function setProxy(user, payload) {
  await http.put(`/manage/users/${user.id}`, payload);
  await load();
}
function toggleFeedback(row) {
  if (feedbackCurrent.value?.id === row.id) {
    feedbackCurrent.value = null;
    feedbackNote.value = "";
    return;
  }
  feedbackCurrent.value = row;
  feedbackStatus.value = row.status || "pending";
  feedbackNote.value = "";
}
async function saveFeedback() {
  if (!feedbackCurrent.value) return;
  const { data } = await http.put(`/manage/feedback/${feedbackCurrent.value.id}`, { status: feedbackStatus.value, note: feedbackNote.value });
  feedbackNote.value = "";
  feedbackStatus.value = data.status || "pending";
  feedbackCurrent.value = data;
  notice.value = tx("已保存", "Saved");
  await load();
}
async function consoleLogout() {
  userOpen.value = false;
  await http.post("/auth/console/logout");
  me.value = null;
  needConsole.value = true;
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
  <div v-else-if="!ready" class="boot">
    <div class="boot-card">
      <img src="/logo.svg" alt="" />
      <strong>NEXA</strong>
      <i></i>
      <span>{{ tx("正在进入后台", "Opening the console") }}</span>
    </div>
  </div>
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
        <button class="text-btn" :class="{ on: section === 'mail' }" @click="section = 'mail'">{{ tx("邮件", "Mail") }}</button>
        <button class="text-btn" :class="{ on: section === 'feedback' }" @click="section = 'feedback'">{{ tx("反馈", "Feedback") }}</button>
        <button class="text-btn" :class="{ on: section === 'actions' }" @click="section = 'actions'">{{ tx("日志", "Logs") }}</button>
      </nav>
    </aside>
    <div class="console-main">
    <header class="console-top">
      <div class="console-title">
        <strong>{{ sectionTitle }}</strong>
        <button type="button" class="refresh-btn" :disabled="refreshing" @click="refreshSection">{{ refreshing ? tx("刷新中", "Refreshing") : tx("刷新", "Refresh") }}</button>
      </div>
      <div class="console-user" @click.stop>
        <button type="button" class="user-mail" @click="userOpen = !userOpen">{{ me.email }}</button>
        <div v-if="userOpen" class="user-menu">
          <button type="button" @click="section = 'security'; userOpen = false">{{ tx("账号安全", "Security") }}</button>
          <button type="button" @click="consoleLogout">{{ tx("登出", "Log out") }}</button>
        </div>
      </div>
    </header>
    <div class="admin">
      <section v-if="section === 'overview'" class="form overview">
        <div class="list-tools"><button type="button" class="refresh-btn" :disabled="refreshing" @click="refreshSection">{{ refreshing ? tx("刷新中", "Refreshing") : tx("刷新", "Refresh") }}</button></div>
        <div v-if="listLoading" class="list-mask"><i></i><span>{{ tx("正在加载", "Loading") }}</span></div>
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
        <div v-if="listLoading" class="list-mask"><i></i><span>{{ tx("正在加载", "Loading") }}</span></div>
        <div v-if="section !== 'security' && section !== 'mail' && section !== 'feedback'" class="list-bar">
          <div class="filters">
          <template v-if="section === 'links' || section === 'categories' || section === 'crawl'">
            <select v-model="listTab" @change="listCat = ''">
              <option value="">{{ tx("全部栏目", "All tabs") }}</option>
              <option v-for="tab in tabs" :key="tab.id" :value="tab.id">{{ tab.title_zh || tab.title_en }}</option>
            </select>
            <select v-if="section !== 'categories'" v-model="listCat">
              <option value="">{{ tx("全部分类", "All categories") }}</option>
              <option v-for="cat in filterCats" :key="cat.id" :value="cat.id">{{ cat.title_zh || cat.title_en }}</option>
            </select>
          </template>
          <select v-if="section === 'links'" v-model="listSource">
            <option value="">{{ tx("全部来源", "All sources") }}</option>
            <option value="user">{{ tx("用户提交", "Submitted") }}</option>
            <option value="admin">{{ tx("系统", "System") }}</option>
          </select>
          <select v-if="section === 'structure'" v-model="listStatus">
            <option value="">{{ tx("全部类型", "All kinds") }}</option>
            <option value="links">links</option>
            <option value="home">home</option>
          </select>
          <select v-if="section === 'news'" v-model="listStatus">
            <option value="">{{ tx("全部分类", "All topics") }}</option>
            <option v-for="name in [...new Set(news.map((row) => row.category).filter(Boolean))]" :key="name" :value="name">{{ name }}</option>
          </select>
          <select v-if="section === 'notes' || section === 'ads'" v-model="listStatus">
            <option value="">{{ tx("全部状态", "All statuses") }}</option>
            <option value="true">{{ tx("显示", "Shown") }}</option>
            <option value="false">{{ tx("隐藏", "Hidden") }}</option>
          </select>
          <select v-if="section === 'ads'" v-model="listTab">
            <option value="">{{ tx("全部位置", "All places") }}</option>
            <option v-for="group in slotGroups" :key="group.page" :value="group.page">{{ group.page }}</option>
          </select>
          <select v-if="section === 'crawl' && crawlKind === 'jobs'" v-model="listStatus">
            <option value="">{{ tx("全部状态", "All statuses") }}</option>
            <option value="running">{{ tx("采集中", "Running") }}</option>
            <option value="done">{{ tx("完成", "Done") }}</option>
            <option value="error">{{ tx("失败", "Failed") }}</option>
            <option value="stopped">{{ tx("已停止", "Stopped") }}</option>
          </select>
          <select v-if="section === 'users' && userKind === 'member'" v-model="listStatus">
            <option value="">{{ tx("全部套餐", "All plans") }}</option>
            <option value="free">{{ tx("免费", "Free") }}</option>
            <option value="vip">VIP</option>
          </select>
          <input v-if="section !== 'categories' && section !== 'levels' && section !== 'ads' && section !== 'actions'" v-model="query" :placeholder="section === 'users' ? tx('搜索邮箱或 IP', 'Search email or IP') : section === 'proxies' ? tx('搜索代理地址', 'Search proxy') : tx('搜索名称或地址', 'Search name or URL')" />
          </div>
          <div class="actions">
          <button type="button" class="refresh-btn" :disabled="refreshing" @click="refreshSection">{{ refreshing ? tx("刷新中", "Refreshing") : tx("刷新", "Refresh") }}</button>
          <button v-if="section === 'links'" class="primary" type="button" @click="openNew('link')">{{ tx("新增", "Add") }}</button>
          <button v-if="section === 'structure'" class="primary" type="button" @click="openNew('tab')">{{ tx("新增栏目", "Add tab") }}</button>
          <button v-if="section === 'structure'" type="button" @click="section = 'categories'">{{ tx("分类列表", "Categories") }}</button>
          <button v-if="section === 'categories'" class="primary" type="button" @click="openNew('category')">{{ tx("新增分类", "Add category") }}</button>
          <button v-if="section === 'categories'" type="button" @click="section = 'structure'">{{ tx("返回栏目", "Back to tabs") }}</button>
          <template v-if="section === 'notes'">
            <button type="button" :class="{ primary: noteKind === 'ticker' }" @click="noteKind = 'ticker'; pageNo = 1">{{ tx("跑马灯", "Ticker") }}</button>
            <button type="button" :class="{ primary: noteKind === 'popup' }" @click="noteKind = 'popup'; pageNo = 1">{{ tx("弹框", "Popup") }}</button>
            <button class="primary" type="button" @click="openNew('note')">{{ tx("新增", "Add") }}</button>
          </template>
          <template v-if="section === 'crawl'">
            <button type="button" :class="{ primary: crawlKind === 'jobs' }" @click="crawlKind = 'jobs'; pageNo = 1">{{ tx("采集任务", "Jobs") }}</button>
            <button type="button" :class="{ primary: crawlKind === 'items' }" @click="crawlKind = 'items'; pageNo = 1">{{ tx("待收录", "Pending") }}</button>
            <button v-if="crawlKind === 'jobs'" class="primary" type="button" @click="openNew('crawl')">{{ tx("新建任务", "New job") }}</button>
          </template>
          <template v-if="section === 'proxies'">
            <button type="button" :class="{ primary: proxyKind === 'alive' }" @click="proxyKind = 'alive'; pageNo = 1">{{ tx("有效代理", "Working") }} {{ proxies.count || 0 }}</button>
            <button type="button" :class="{ primary: proxyKind === 'sources' }" @click="proxyKind = 'sources'; pageNo = 1">{{ tx("开源代理池", "Source lists") }} {{ proxies.sources || 0 }}</button>
          </template>
          <template v-if="section === 'users'">
            <button type="button" :class="{ primary: userKind === 'member' }" @click="userKind = 'member'; pageNo = 1">{{ tx("前台会员", "Members") }}</button>
            <button type="button" :class="{ primary: userKind === 'admin' }" @click="userKind = 'admin'; pageNo = 1">{{ tx("管理员", "Admins") }}</button>
            <button v-if="userKind === 'admin'" class="primary" type="button" @click="openNew('admin')">{{ tx("新增管理员", "Add admin") }}</button>
          </template>
          <template v-if="section === 'actions'">
            <button type="button" :class="{ primary: logKind === 'user' }" @click="logKind = 'user'; pageNo = 1">{{ tx("用户", "Users") }}</button>
            <button type="button" :class="{ primary: logKind === 'admin' }" @click="logKind = 'admin'; pageNo = 1">{{ tx("管理员", "Admins") }}</button>
          </template>
          <button v-if="section === 'alerts'" class="primary" type="button" @click="openNew('ban')">{{ tx("禁用 IP", "Block IP") }}</button>
          <template v-if="section === 'links'">
            <button type="button" :disabled="!picked.length" @click="bump('favorite_count')">{{ tx("收藏累加", "Add saves") }}</button>
            <button type="button" :disabled="!picked.length" @click="bump('recommend_count')">{{ tx("推荐累加", "Add picks") }}</button>
            <button type="button" :disabled="!picked.length" @click="bump('click_count')">{{ tx("点击累加", "Add clicks") }}</button>
            <button type="button" :disabled="!picked.length" @click="removeIds('/manage/links', picked)">{{ tx("批量删除", "Delete selected") }}</button>
          </template>
          <button v-if="section === 'news'" type="button" :disabled="!picked.length" @click="removeIds('/manage/news', picked)">{{ tx("批量删除", "Delete selected") }}</button>
          <button v-if="section === 'notes'" type="button" :disabled="!picked.length" @click="removeIds('/manage/announcements', picked)">{{ tx("批量删除", "Delete selected") }}</button>
          <span v-if="notice">{{ notice }}</span>
          </div>
        </div>
        <p v-if="section === 'levels'">{{ tx("积分门槛和每分钟代理次数可以改。等级本身固定为 0 到 10。", "Point thresholds and proxy limits can be edited. Levels stay 0 to 10.") }}</p>
        <p v-if="section === 'proxies'">{{ proxies.note || tx("每 3 分钟检测一次，打不开的代理会删掉。", "Checked every 3 minutes. Unusable proxies are removed.") }}</p>
        <div v-if="section === 'security'" class="security-page">
          <div class="list-tools"><button type="button" class="refresh-btn" :disabled="refreshing" @click="refreshSection">{{ refreshing ? tx("刷新中", "Refreshing") : tx("刷新", "Refresh") }}</button></div>
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

        <div v-else-if="section === 'mail'" class="mail-page">
          <div class="list-tools"><button type="button" class="refresh-btn" :disabled="refreshing" @click="refreshSection">{{ refreshing ? tx("刷新中", "Refreshing") : tx("刷新", "Refresh") }}</button></div>
          <nav class="mail-tabs">
            <button type="button" :class="{ on: mailTab === 'channels' }" @click="mailTab = 'channels'">{{ tx("通道", "Channels") }}</button>
            <button type="button" :class="{ on: mailTab === 'send' }" @click="mailTab = 'send'">{{ tx("发信", "Send") }}</button>
            <button type="button" :class="{ on: mailTab === 'schedule' }" @click="mailTab = 'schedule'">{{ tx("定时", "Schedule") }}</button>
          </nav>
          <div v-if="mailTab === 'channels'" class="mail-board">
          <article class="security-card mail-config">
            <header><h3>{{ tx("发信通道", "Channels") }}</h3><button class="primary" type="button" @click="saveMail">{{ tx("保存", "Save") }}</button></header>
            <p>{{ tx("打开开关后填写账号。留空的项会用服务器 .env 里已有的值。", "Turn a channel on to fill its account. A blank field keeps the value already in the server .env.") }}</p>
            <section class="channel">
              <header><strong>Gmail</strong><label class="switch"><input type="checkbox" v-model="mailState.settings.gmail_enabled" /><i></i></label></header>
              <div v-if="mailState.settings.gmail_enabled" class="channel-fields">
                <label class="field"><span>SMTP</span><input v-model="mailState.settings.gmail_host" placeholder="smtp.gmail.com" /></label>
                <label class="field"><span>{{ tx("端口", "Port") }}</span><input v-model.number="mailState.settings.gmail_port" type="number" /></label>
                <label class="field"><span>{{ tx("账号", "Account") }}</span><input v-model="mailState.settings.gmail_user" type="email" /></label>
                <label class="field"><span>{{ tx("密码", "Password") }}</span><input v-model="mailState.settings.gmail_pass" /></label>
                <label class="field"><span>{{ tx("发件邮箱", "From") }}</span><input v-model="mailState.settings.gmail_from" type="email" /></label>
                <label class="field"><span>{{ tx("发件名称", "From name") }}</span><input v-model="mailState.settings.gmail_from_name" /></label>
              </div>
            </section>
            <section class="channel">
              <header><strong>163</strong><label class="switch"><input type="checkbox" v-model="mailState.settings.netease_enabled" /><i></i></label></header>
              <div v-if="mailState.settings.netease_enabled" class="channel-fields">
                <label class="field"><span>SMTP</span><input v-model="mailState.settings.netease_host" placeholder="smtp.163.com" /></label>
                <label class="field"><span>{{ tx("端口", "Port") }}</span><input v-model.number="mailState.settings.netease_port" type="number" /></label>
                <label class="field"><span>{{ tx("账号", "Account") }}</span><input v-model="mailState.settings.netease_user" type="email" /></label>
                <label class="field"><span>{{ tx("密码", "Password") }}</span><input v-model="mailState.settings.netease_pass" /></label>
                <label class="field"><span>{{ tx("发件邮箱", "From") }}</span><input v-model="mailState.settings.netease_from" type="email" /></label>
                <label class="field"><span>{{ tx("发件名称", "From name") }}</span><input v-model="mailState.settings.netease_from_name" /></label>
              </div>
            </section>
            <section class="channel">
              <header><strong>SendGrid</strong><label class="switch"><input type="checkbox" v-model="mailState.settings.sendgrid_enabled" /><i></i></label></header>
              <div v-if="mailState.settings.sendgrid_enabled" class="channel-fields">
                <label class="field"><span>API Key</span><input v-model="mailState.settings.sendgrid_key" /></label>
                <label class="field"><span>{{ tx("发件邮箱", "From") }}</span><input v-model="mailState.settings.sendgrid_from" type="email" /></label>
                <label class="field"><span>{{ tx("发件名称", "From name") }}</span><input v-model="mailState.settings.sendgrid_from_name" /></label>
              </div>
            </section>
            <section class="channel">
              <header><strong>Mailgun</strong><label class="switch"><input type="checkbox" v-model="mailState.settings.mailgun_enabled" /><i></i></label></header>
              <div v-if="mailState.settings.mailgun_enabled" class="channel-fields">
                <label class="field"><span>API Key</span><input v-model="mailState.settings.mailgun_key" /></label>
                <label class="field"><span>{{ tx("域名", "Domain") }}</span><input v-model="mailState.settings.mailgun_domain" placeholder="mg.example.com" /></label>
                <label class="field"><span>{{ tx("区域", "Region") }}</span><select v-model="mailState.settings.mailgun_region"><option value="us">US</option><option value="eu">EU</option></select></label>
                <label class="field"><span>{{ tx("发件邮箱", "From") }}</span><input v-model="mailState.settings.mailgun_from" type="email" /></label>
                <label class="field"><span>{{ tx("发件名称", "From name") }}</span><input v-model="mailState.settings.mailgun_from_name" /></label>
              </div>
            </section>
            <label class="switch"><input type="checkbox" v-model="mailState.settings.notify_default" /><i></i><span>{{ tx("默认通知邮件", "Default notices") }}</span></label>
            <p v-if="mailHint">{{ mailHint }}</p>
          </article>
          <article class="security-card">
            <header><h3>{{ tx("测试配置", "Test") }}</h3></header>
            <p>{{ tx("填一个收件邮箱，发送一封固定的测试信。成功说明当前打开的通道可用。", "Send one fixed test message. A success means the open channel works.") }}</p>
            <div class="bind-row">
              <input v-model="mailTest" type="email" :placeholder="tx('测试收件邮箱', 'Test inbox')" />
              <button class="primary" type="button" @click="sendTest">{{ tx("发送测试邮件", "Send test") }}</button>
            </div>
            <p v-if="mailHint">{{ mailHint }}</p>
          </article>
          <article class="security-card wide">
            <header><h3>{{ tx("最近记录", "Recent") }}</h3></header>
            <p v-for="line in mailState.logs" :key="line.id">{{ (line.created_at || "").slice(0, 16).replace("T", " ") }} {{ line.recipient }} · {{ line.channel }} · {{ line.status }} {{ line.message }}</p>
            <p v-if="!mailState.logs.length">{{ tx("还没有发送记录", "No messages yet") }}</p>
          </article>
          </div>
          <article v-else-if="mailTab === 'send'" class="security-card">
            <header><h3>{{ tx("给用户发信", "Send") }}</h3></header>
            <input v-model="mailForm.subject" :placeholder="tx('标题', 'Subject')" />
            <textarea v-model="mailForm.body" rows="6" :placeholder="tx('正文', 'Message')"></textarea>
            <input v-model="mailForm.email" type="email" :placeholder="tx('单个邮箱，留空则群发', 'One address, or leave empty for the group')" />
            <select v-model="mailForm.audience">
              <option value="all">{{ tx("全部会员", "All members") }}</option>
              <option value="vip">VIP</option>
              <option value="free">{{ tx("免费会员", "Free members") }}</option>
            </select>
            <button class="primary" type="button" @click="sendMail">{{ tx("立即发送", "Send now") }}</button>
          </article>
          <article v-else-if="mailTab === 'schedule'" class="security-card">
            <header><h3>{{ tx("定时发送", "Schedule") }}</h3></header>
            <input v-model="mailForm.subject" :placeholder="tx('标题', 'Subject')" />
            <textarea v-model="mailForm.body" rows="4" :placeholder="tx('正文', 'Message')"></textarea>
            <input v-model="mailForm.email" type="email" :placeholder="tx('单个邮箱，留空则群发', 'One address, or leave empty for the group')" />
            <select v-model="mailForm.audience">
              <option value="all">{{ tx("全部会员", "All members") }}</option>
              <option value="vip">VIP</option>
              <option value="free">{{ tx("免费会员", "Free members") }}</option>
            </select>
            <input v-model="mailForm.run_at" type="datetime-local" />
            <input v-model.number="mailForm.interval_minutes" type="number" min="0" :placeholder="tx('重复间隔（分钟），0 为只发一次', 'Repeat minutes, 0 sends once')" />
            <button class="primary" type="button" @click="addMailTask">{{ tx("加入定时", "Schedule") }}</button>
            <p v-for="task in mailState.tasks" :key="task.id">{{ task.subject }} · {{ (task.run_at || "").replace("T", " ").slice(0, 16) }} <button type="button" @click="dropMailTask(task.id)">{{ tx("删除", "Delete") }}</button></p>
            <p v-if="!mailState.tasks.length">{{ tx("还没有定时任务", "No schedule yet") }}</p>
          </article>
        </div>

        <div v-else-if="section === 'feedback'" class="feedback-admin">
          <div class="list-tools"><button type="button" class="refresh-btn" :disabled="refreshing" @click="refreshSection">{{ refreshing ? tx("刷新中", "Refreshing") : tx("刷新", "Refresh") }}</button></div>
          <article class="security-card">
            <header><h3>{{ tx("反馈工单", "Tickets") }}</h3></header>
            <p v-if="!feedbackRows.length">{{ tx("还没有反馈", "No tickets yet") }}</p>
            <div v-for="row in feedbackRows" :key="row.id" class="ticket-fold">
              <button type="button" class="ticket-row" :class="{ on: feedbackCurrent && feedbackCurrent.id === row.id }" @click="toggleFeedback(row)">
                <span>
                  <b>{{ row.title }}</b>
                  <small>{{ tx("提交", "Sent") }} {{ (row.created_at || "").slice(0, 16).replace("T", " ") }} · {{ tx("更新", "Updated") }} {{ (row.updated_at || row.created_at || "").slice(0, 16).replace("T", " ") }}</small>
                </span>
                <em :class="row.status">{{ row.email }} · {{ ({ pending: tx('待处理', 'Open'), working: tx('处理中', 'In progress'), done: tx('已完成', 'Done'), rejected: tx('拒绝', 'Rejected'), closed: tx('关闭', 'Closed') })[row.status] || row.status }}</em>
              </button>
              <div v-if="feedbackCurrent && feedbackCurrent.id === row.id" class="ticket-detail">
                <p>{{ feedbackCurrent.email }}</p>
                <p>{{ feedbackCurrent.body }}</p>
                <img v-if="feedbackCurrent.image_url" :src="feedbackCurrent.image_url" alt="" class="ticket-shot" />
                <div v-for="note in feedbackCurrent.notes" :key="note.id" class="ticket-note" :class="note.role">
                  <b>{{ note.role === 'admin' ? tx('管理员', 'Admin') : tx('用户', 'User') }}</b>
                  <span>{{ (note.created_at || '').slice(0, 16).replace('T', ' ') }}</span>
                  <p>{{ note.body }}</p>
                </div>
                <select v-model="feedbackStatus">
                  <option value="pending">{{ tx("待处理", "Open") }}</option>
                  <option value="working">{{ tx("处理中", "In progress") }}</option>
                  <option value="done">{{ tx("已完成", "Done") }}</option>
                  <option value="rejected">{{ tx("拒绝", "Rejected") }}</option>
                  <option value="closed">{{ tx("关闭", "Closed") }}</option>
                </select>
                <textarea v-model="feedbackNote" rows="3" :placeholder="tx('备注，用户能看到', 'Note the user will see')"></textarea>
                <button class="primary" type="button" @click="saveFeedback">{{ tx("保存状态和备注", "Save status and note") }}</button>
              </div>
            </div>
          </article>
        </div>

        <div v-else-if="section === 'actions'" class="table-scroll">
          <div class="log-filters">
            <input v-model="logAccount" :placeholder="tx('账号：邮箱或用户名', 'Account: email or name')" @input="pageNo = 1" />
            <input v-model="logFrom" type="date" :title="tx('开始日期', 'From')" @change="pageNo = 1" />
            <input v-model="logTo" type="date" :title="tx('结束日期', 'To')" @change="pageNo = 1" />
            <select v-model="logAction" @change="pageNo = 1">
              <option value="">{{ tx("全部操作", "All actions") }}</option>
              <option v-for="code in logActions" :key="code" :value="code">{{ actionLabel(code) }}</option>
            </select>
            <select v-model="logResult" @change="pageNo = 1">
              <option value="">{{ tx("全部结果", "All results") }}</option>
              <option value="ok">{{ tx("成功", "OK") }}</option>
              <option value="fail">{{ tx("失败", "Failed") }}</option>
            </select>
            <input v-model="logIp" placeholder="IP" @input="pageNo = 1" />
          </div>
          <table>
            <thead>
              <tr>
                <th>{{ tx("时间", "Time") }}</th>
                <th>{{ tx("账号", "Account") }}</th>
                <th>{{ tx("身份", "Role") }}</th>
                <th>{{ tx("操作", "Action") }}</th>
                <th>{{ tx("结果", "Result") }}</th>
                <th>IP</th>
                <th>{{ tx("说明", "Detail") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in activeView.rows" :key="row.id">
                <td>{{ (row.created_at || "").replace("T", " ") }}</td>
                <td>{{ actorText(row) }}</td>
                <td>{{ row.role === "admin" ? tx("管理员", "Admin") : row.role === "user" ? tx("用户", "User") : "—" }}</td>
                <td>{{ actionText(row) }}</td>
                <td><span class="tag" :class="{ on: row.ok, warn: !row.ok }">{{ row.ok ? tx("成功", "OK") : tx("失败", "Failed") }}</span></td>
                <td>{{ row.ip }}</td>
                <td class="clip">{{ row.detail }}</td>
              </tr>
              <tr v-if="!activeView.rows.length"><td colspan="7">{{ tx("没有记录", "No rows") }}</td></tr>
            </tbody>
          </table>
          <div class="console-pager">
            <span class="pager-total">{{ tx(`共 ${activeView.total} 条`, `${activeView.total} total`) }}</span>
            <button type="button" :disabled="activeView.current <= 1" @click="goPage(activeView.current - 1)">‹</button>
            <button type="button" class="is-current">{{ activeView.current }}</button>
            <button type="button" :disabled="activeView.current >= activeView.pages" @click="goPage(activeView.current + 1)">›</button>
          </div>
        </div>

        <div v-else :class="{ 'crawl-split': section === 'crawl' }">
        <div class="crawl-main">
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th v-if="section !== 'ads'" class="check"><input type="checkbox" :checked="activeView.rows.length && activeView.rows.every((row) => picked.includes(row.id))" @change="togglePage(activeView.rows, $event.target.checked)" /></th>
                <template v-if="section === 'links'">
                  <th>{{ tx("名称", "Name") }}</th><th>{{ tx("地址", "URL") }}</th><th>{{ tx("来源", "Source") }}</th><th class="num">{{ tx("展示收藏", "Shown saves") }}</th><th class="num">{{ tx("展示推荐", "Shown picks") }}</th><th class="num">{{ tx("展示点击", "Shown clicks") }}</th><th class="num">{{ tx("真实收藏", "Real saves") }}</th><th class="num">{{ tx("真实推荐", "Real picks") }}</th><th class="num">{{ tx("真实点击", "Real clicks") }}</th>
                </template>
                <template v-else-if="section === 'structure'">
                  <th>ID</th><th>slug</th><th>{{ tx("中文名", "Chinese") }}</th><th>{{ tx("英文名", "English") }}</th><th>{{ tx("类型", "Kind") }}</th><th>{{ tx("排序", "Sort") }}</th><th>{{ tx("显示", "Visible") }}</th><th>18+</th><th>{{ tx("全网采集", "Web crawl") }}</th>
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
                  <th>{{ tx("图片", "Image") }}</th><th>{{ tx("标题", "Title") }}</th><th>{{ tx("状态", "Status") }}</th><th>{{ tx("时间", "Time") }}</th>
                </template>
                <template v-else-if="section === 'ads'">
                  <th>{{ tx("图片", "Image") }}</th><th>{{ tx("位置", "Slot") }}</th><th>{{ tx("名称", "Name") }}</th><th>{{ tx("展示", "Shown") }}</th><th>{{ tx("占位图", "Placeholder") }}</th><th>{{ tx("更新时间", "Updated") }}</th>
                </template>
                <template v-else-if="section === 'crawl' && crawlKind === 'jobs'">
                  <th>{{ tx("名称", "Name") }}</th><th>{{ tx("地址", "URL") }}</th><th>{{ tx("分类", "Category") }}</th><th>{{ tx("状态", "Status") }}</th><th>{{ tx("上次运行", "Last run") }}</th><th>{{ tx("条数", "Found") }}</th>
                </template>
                <template v-else-if="section === 'crawl'">
                  <th>{{ tx("标题", "Title") }}</th><th>{{ tx("地址", "URL") }}</th>
                </template>
                <template v-else-if="section === 'users' && userKind === 'admin'">
                  <th>{{ tx("邮箱", "Email") }}</th><th>{{ tx("昵称", "Name") }}</th><th>{{ tx("验证器", "Authenticator") }}</th><th>IP</th><th>{{ tx("注册", "Joined") }}</th>
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
                <td v-if="section !== 'ads'" class="check"><input type="checkbox" :checked="picked.includes(row.id)" @change="togglePick(row.id, $event.target.checked)" /></td>
                <template v-if="section === 'links'">
                  <td>{{ row.title_zh || row.title_en }}</td><td class="clip">{{ row.url }}</td><td><span class="tag">{{ sourceLabel(row.source) }}</span></td><td class="num">{{ row.favorite_count }}</td><td class="num">{{ row.recommend_count }}</td><td class="num">{{ row.click_count }}</td><td class="num">{{ row.real_favorite_count || 0 }}</td><td class="num">{{ row.real_recommend_count || 0 }}</td><td class="num">{{ row.real_click_count || 0 }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('link', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="removeIds('/manage/links', [row.id])">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'structure'">
                  <td>{{ row.id }}</td><td>{{ row.slug }}</td><td>{{ row.title_zh }}</td><td>{{ row.title_en }}</td><td>{{ row.kind }}</td><td class="num">{{ row.sort }}</td><td><span class="tag" :class="{ on: row.visible }">{{ row.visible ? tx("显示", "On") : tx("隐藏", "Off") }}</span></td><td><span class="tag" :class="{ warn: row.adult }">{{ row.adult ? tx("是", "Yes") : tx("否", "No") }}</span></td>
                  <td><button v-if="row.kind === 'links'" type="button" :class="{ primary: row.auto_crawl }" @click="toggleCrawl(row)">{{ row.auto_crawl ? tx("采集中", "On") : tx("已关闭", "Off") }}</button></td>
                  <td class="row-actions"><button type="button" @click="openEdit('tab', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="removeIds('/manage/tabs', [row.id])">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'categories'">
                  <td>{{ row.id }}</td><td>{{ row.tab_id }}</td><td>{{ row.slug }}</td><td>{{ row.title_zh }}</td><td>{{ row.title_en }}</td><td class="num">{{ row.sort }}</td><td><span class="tag" :class="{ on: row.visible }">{{ row.visible ? tx("显示", "On") : tx("隐藏", "Off") }}</span></td>
                  <td class="row-actions"><button type="button" @click="openEdit('category', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="removeIds('/manage/categories', [row.id])">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'news'">
                  <td><span class="tag">{{ row.category }}</span></td><td class="clip">{{ row.title }}</td><td>{{ row.source }}</td>
                  <td class="row-actions"><button type="button" @click="dropNews(row.id)">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'pages'">
                  <td>{{ row.key }}</td><td>{{ row.title_zh || row.title_en }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('page', row)">{{ tx("编辑", "Edit") }}</button></td>
                </template>
                <template v-else-if="section === 'notes'">
                  <td><img v-if="row.image_url" class="ad-thumb" :src="row.image_url" alt="" /><span v-else class="ad-thumb empty"></span></td>
                  <td class="clip">{{ row.title_zh || row.title_en }}</td>
                  <td><button type="button" :class="{ primary: row.enabled }" @click="toggleNote(row)">{{ row.enabled ? tx("显示", "On") : tx("隐藏", "Off") }}</button></td>
                  <td class="time">{{ (row.created_at || "").slice(0, 16).replace("T", " ") }}</td>
                  <td class="row-actions"><button type="button" @click="openEdit('note', row)">{{ tx("编辑", "Edit") }}</button><button type="button" @click="dropNote(row.id)">{{ tx("删除", "Delete") }}</button></td>
                </template>
                <template v-else-if="section === 'ads'">
                  <td><span class="ad-thumb-wrap"><img class="ad-thumb" :src="row.image_url && row.image_url !== '/ad-placeholder.svg' ? row.image_url : '/ad-placeholder.svg'" alt="" /><b>{{ row.no }}</b></span></td>
                  <td>{{ row.where }}</td>
                  <td>{{ row.title_zh || row.title_en }}</td>
                  <td><button type="button" :class="{ primary: row.enabled }" @click="toggleAd(row, 'enabled')">{{ row.enabled ? tx("展示", "Shown") : tx("不展示", "Hidden") }}</button></td>
                  <td><button type="button" :class="{ primary: row.show_placeholder }" @click="toggleAd(row, 'show_placeholder')">{{ row.show_placeholder ? tx("开启", "On") : tx("关闭", "Off") }}</button></td>
                  <td class="time">{{ (row.updated_at || "").slice(0, 16).replace("T", " ") }}</td>
                  <td class="row-actions">
                    <button v-if="row.carousel" type="button" @click="addSlide(row)">{{ tx("添加一组", "Add slide") }}</button>
                    <button type="button" @click="openEdit('ad', row)">{{ tx("编辑", "Edit") }}</button>
                    <button v-if="row.carousel && row.slideCount > 1" type="button" @click="removeSlide(row)">{{ tx("删除", "Delete") }}</button>
                  </td>
                </template>
                <template v-else-if="section === 'crawl' && crawlKind === 'jobs'">
                  <td>{{ row.name }}</td>
                  <td class="clip">{{ row.list_url || row.keyword || tx("全网", "Web") }}</td>
                  <td>{{ row.category }}</td>
                  <td><span class="tag" :class="{ on: row.status === 'running' || row.status === 'done', warn: row.status === 'error' }" :title="row.message || ''">{{ crawlStatus(row) }}</span></td>
                  <td class="time">{{ (row.last_run_at || "").slice(0, 16).replace("T", " ") }}</td>
                  <td class="num">{{ row.found_count || 0 }}</td>
                  <td class="row-actions">
                    <button type="button" @click="openEdit('crawl', row)">{{ tx("编辑", "Edit") }}</button>
                    <button v-if="row.status === 'running'" type="button" @click="stopJob(row)">{{ tx("停止", "Stop") }}</button>
                    <button v-else type="button" @click="runJob(row)">{{ tx("开始", "Run") }}</button>
                    <button type="button" @click="logJob = row.id; loadLogs(); notice = tx('已打开这条任务的记录', 'Showing this job')">{{ tx("记录", "Log") }}</button>
                    <button type="button" @click="dropJob(row.id)">{{ tx("删除", "Delete") }}</button>
                  </td>
                </template>
                <template v-else-if="section === 'crawl'">
                  <td>{{ row.title }}</td><td class="clip">{{ row.url }}</td>
                  <td class="row-actions"><button type="button" @click="approve(row.id)">{{ tx("收录", "Approve") }}</button></td>
                </template>
                <template v-else-if="section === 'users' && userKind === 'admin'">
                  <td>{{ row.email }}</td><td>{{ row.display_name || "—" }}</td><td><span class="tag" :class="{ on: row.totp_confirmed && row.totp_enabled, warn: row.totp_confirmed && !row.totp_enabled }">{{ totpText(row) }}</span></td><td>{{ row.last_ip || "—" }}</td><td class="time">{{ (row.created_at || "").slice(0, 10) }}</td>
                  <td class="row-actions">
                    <button type="button" @click="resetPassword(row)">{{ tx("重置密码", "Reset password") }}</button>
                    <button type="button" @click="resetTotp(row)">{{ tx("重置验证器", "Reset authenticator") }}</button>
                    <button type="button" @click="banUser(row)">{{ row.banned ? tx("解封", "Enable") : tx("禁用", "Disable") }}</button>
                  </td>
                </template>
                <template v-else-if="section === 'users'">
                  <td>{{ row.email }}</td>
                  <td>{{ row.display_name || "—" }}</td>
                  <td><span class="tag" :class="{ on: row.plan === 'vip' }">{{ row.plan === "vip" ? "VIP" : tx("免费", "Free") }}</span></td>
                  <td>Lv.{{ row.level }} · {{ row.points }}</td>
                  <td>
                    <div class="proxy-edit">
                      <button type="button" :class="{ primary: row.proxy_unlimited }" @click="setProxy(row, { proxy_unlimited: !row.proxy_unlimited })">{{ row.proxy_unlimited ? tx("取消白名单", "Limited") : tx("设白名单", "Unlimited") }}</button>
                      <input class="limit-box" v-model="row.proxy_limit" type="number" min="0" step="1" inputmode="numeric" :placeholder="tx('次数', 'Limit')" @blur="saveProxyLimit(row)" @keyup.enter="$event.target.blur()" />
                    </div>
                  </td>
                  <td>{{ row.banned ? tx("已禁用", "Disabled") : (row.last_ip || "—") }}</td>
                  <td class="time">{{ (row.created_at || "").slice(0, 10) }}</td>
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
        </div>
        <div v-if="section === 'crawl'" class="crawl-console">
          <header>
            <strong>{{ tx("执行记录", "Run log") }}</strong>
            <select v-model.number="logJob" @change="loadLogs">
              <option :value="0">{{ tx("全部任务", "All jobs") }}</option>
              <option v-for="row in jobs" :key="row.id" :value="row.id">{{ row.name }}</option>
            </select>
          </header>
          <pre v-if="crawlLogs.length"><span v-for="line in crawlLogs" :key="line.id">{{ (line.created_at || "").slice(11, 19) }}  {{ line.job }}  {{ line.message }}
</span></pre>
          <p v-else>{{ tx("还没有执行记录", "No log yet") }}</p>
        </div>
        </div>
      </section>

      <div v-if="ask" class="console-modal">
        <form class="dialog ask" @submit.prevent="acceptAsk">
          <header><h3>{{ tx("确认删除", "Confirm delete") }}</h3><button class="dialog-x" type="button" @click="ask = null">×</button></header>
          <div class="dialog-body"><p>{{ ask.text }}</p></div>
          <footer>
            <button type="button" @click="ask = null">{{ tx("取消", "Cancel") }}</button>
            <button class="primary" type="submit">{{ tx("确认删除", "Delete") }}</button>
          </footer>
        </form>
      </div>
      <div v-if="editor" class="console-modal">
        <form class="dialog" @submit.prevent="saveEditor">
          <header>
            <h3>{{ editorTitle }}</h3>
            <button class="dialog-x" type="button" @click="editor = null" aria-label="close">×</button>
          </header>
          <div class="dialog-body">
            <template v-if="editor.kind === 'link'">
              <div class="field pick">
                <span>{{ tx("栏目", "Tab") }}</span>
                <input v-model="tabQuery" :placeholder="tx('输入栏目名称', 'Type a tab')" @focus="pickOpen = 'tab'" @input="pickOpen = 'tab'" />
                <ul v-if="pickOpen === 'tab'">
                  <li v-for="tab in tabHits" :key="tab.id" @mousedown.prevent="chooseTab(tab)">{{ tab.title_zh || tab.title_en }}</li>
                  <li v-if="!tabHits.length" class="empty">{{ tx("没有匹配的栏目", "No matching tab") }}</li>
                </ul>
              </div>
              <div class="field pick">
                <span>{{ tx("分类", "Category") }}</span>
                <input v-model="catQuery" :placeholder="tx('输入分类名称', 'Type a category')" @focus="pickOpen = 'cat'" @input="pickOpen = 'cat'" />
                <ul v-if="pickOpen === 'cat'">
                  <li v-for="cat in catHits" :key="cat.id" @mousedown.prevent="chooseCat(cat)">{{ cat.title_zh || cat.title_en }}</li>
                  <li v-if="!catHits.length" class="empty">{{ tx("没有匹配的分类", "No matching category") }}</li>
                </ul>
              </div>
              <label class="field"><span>{{ tx("地址", "URL") }}</span><input v-model="editor.row.url" placeholder="https://" required /></label>
              <label class="field"><span>{{ tx("中文名称", "Chinese name") }}</span><input v-model="editor.row.title_zh" /></label>
              <label class="field"><span>{{ tx("英文名称", "English name") }}</span><input v-model="editor.row.title_en" /></label>
              <label class="field wide"><span>{{ tx("中文简介", "Chinese description") }}</span><input v-model="editor.row.description_zh" /></label>
              <label class="field wide"><span>{{ tx("英文简介", "English description") }}</span><input v-model="editor.row.description_en" /></label>
              <label class="field choice"><span>{{ tx("免费", "Free") }}</span><input type="checkbox" v-model="editor.row.is_free" /></label>
              <label class="field choice"><span>{{ tx("热门", "Hot") }}</span><input type="checkbox" v-model="editor.row.is_hot" /></label>
            </template>
            <template v-else-if="editor.kind === 'tab'">
              <label class="field"><span>slug</span><input v-model="editor.row.slug" required /></label>
              <label class="field"><span>{{ tx("类型", "Kind") }}</span><select v-model="editor.row.kind"><option value="links">links</option><option value="home">home</option></select></label>
              <label class="field"><span>{{ tx("中文名", "Chinese name") }}</span><input v-model="editor.row.title_zh" /></label>
              <label class="field"><span>{{ tx("英文名", "English name") }}</span><input v-model="editor.row.title_en" /></label>
              <label class="field"><span>{{ tx("排序", "Sort") }}</span><input v-model.number="editor.row.sort" type="number" /></label>
              <label class="field choice"><span>{{ tx("显示", "Visible") }}</span><input type="checkbox" v-model="editor.row.visible" /></label>
              <label class="field choice"><span>18+</span><input type="checkbox" v-model="editor.row.adult" /></label>
              <label v-if="editor.row.kind === 'links'" class="field choice"><span>{{ tx("全网采集", "Web crawl") }}</span><input type="checkbox" v-model="editor.row.auto_crawl" /></label>
            </template>
            <template v-else-if="editor.kind === 'category'">
              <div class="field pick">
                <span>{{ tx("栏目", "Tab") }}</span>
                <input v-model="tabQuery" :placeholder="tx('输入栏目名称', 'Type a tab')" @focus="pickOpen = 'tab'" @input="pickOpen = 'tab'" />
                <ul v-if="pickOpen === 'tab'">
                  <li v-for="tab in tabHits" :key="tab.id" @mousedown.prevent="chooseTab(tab)">{{ tab.title_zh || tab.title_en }}</li>
                  <li v-if="!tabHits.length" class="empty">{{ tx("没有匹配的栏目", "No matching tab") }}</li>
                </ul>
              </div>
              <label class="field"><span>slug</span><input v-model="editor.row.slug" required /></label>
              <label class="field"><span>{{ tx("中文名", "Chinese name") }}</span><input v-model="editor.row.title_zh" /></label>
              <label class="field"><span>{{ tx("英文名", "English name") }}</span><input v-model="editor.row.title_en" /></label>
              <label class="field"><span>{{ tx("排序", "Sort") }}</span><input v-model.number="editor.row.sort" type="number" /></label>
              <label class="field choice"><span>{{ tx("显示", "Visible") }}</span><input type="checkbox" v-model="editor.row.visible" /></label>
            </template>
            <template v-else-if="editor.kind === 'page'">
              <label class="field"><span>{{ tx("中文标题", "Chinese title") }}</span><input v-model="editor.row.title_zh" /></label>
              <label class="field"><span>{{ tx("英文标题", "English title") }}</span><input v-model="editor.row.title_en" /></label>
              <label class="field wide"><span>{{ tx("中文正文", "Chinese body") }}</span><textarea v-model="editor.row.body_zh" rows="5"></textarea></label>
              <label class="field wide"><span>{{ tx("英文正文", "English body") }}</span><textarea v-model="editor.row.body_en" rows="5"></textarea></label>
              <label class="field"><span>Email</span><input v-model="editor.row.email" /></label>
              <label class="field"><span>{{ tx("电话", "Phone") }}</span><input v-model="editor.row.phone" /></label>
              <label class="field"><span>Telegram</span><input v-model="editor.row.im" /></label>
            </template>
            <template v-else-if="editor.kind === 'note'">
              <label class="field"><span>{{ tx("中文标题", "Chinese title") }}</span><input v-model="editor.row.title_zh" /></label>
              <label class="field"><span>{{ tx("英文标题", "English title") }}</span><input v-model="editor.row.title_en" /></label>
              <label class="field wide"><span>{{ tx("中文正文", "Chinese body") }}</span><textarea v-model="editor.row.body_zh" rows="4"></textarea></label>
              <label class="field wide"><span>{{ tx("英文正文", "English body") }}</span><textarea v-model="editor.row.body_en" rows="4"></textarea></label>
              <div class="field wide">
                <span>{{ tx("图片", "Image") }}</span>
                <label class="dropzone" :class="{ over: dropOver }" @dragover.prevent="dropOver = true" @dragleave.prevent="dropOver = false" @drop.prevent="onImageDrop">
                  <img v-if="editor.row.image_url" :src="editor.row.image_url" alt="" />
                  <em>{{ tx("拖到这里，或点击选择图片", "Drop an image here, or click to choose") }}</em>
                  <input type="file" accept="image/*" @change="onImagePick" />
                </label>
              </div>
              <label class="field choice"><span>{{ tx("显示", "Visible") }}</span><input type="checkbox" v-model="editor.row.enabled" /></label>
            </template>
            <template v-else-if="editor.kind === 'ad'">
              <div class="field wide">
                <span>{{ tx("位置", "Slot") }}</span>
                <p class="slot-lock">{{ slotWhere(editor.row.slot) }}</p>
              </div>
              <label class="field"><span>{{ tx("中文名称", "Chinese name") }}</span><input v-model="editor.row.title_zh" /></label>
              <label class="field"><span>{{ tx("英文名称", "English name") }}</span><input v-model="editor.row.title_en" /></label>
              <div class="field wide">
                <span>{{ tx("图片", "Image") }}</span>
                <label class="dropzone" :class="{ over: dropOver }" @dragover.prevent="dropOver = true" @dragleave.prevent="dropOver = false" @drop.prevent="onImageDrop">
                  <img v-if="editor.row.image_url" :src="editor.row.image_url" alt="" />
                  <em>{{ tx("拖到这里，或点击选择图片", "Drop an image here, or click to choose") }}</em>
                  <input type="file" accept="image/*" @change="onImagePick" />
                </label>
              </div>
              <label class="field"><span>{{ tx("跳转地址", "Link") }}</span><input v-model="editor.row.link_url" /></label>
              <label class="field choice"><span>{{ tx("展示", "Shown") }}</span><input type="checkbox" v-model="editor.row.enabled" /></label>
              <label class="field choice"><span>{{ tx("占位图", "Placeholder") }}</span><input type="checkbox" v-model="editor.row.show_placeholder" /></label>
            </template>
            <template v-else-if="editor.kind === 'crawl'">
              <label class="field"><span>{{ tx("名称", "Name") }}</span><input v-model="editor.row.name" :placeholder="tx('任务名称', 'Job name')" /></label>
              <label class="field"><span>{{ tx("关键词", "Keyword") }}</span><input v-model="editor.row.keyword" :placeholder="tx('例如 美女', 'For example, design tools')" /></label>
              <label class="field wide"><span>{{ tx("指定网址", "Specific URL") }}</span><input v-model="editor.row.list_url" placeholder="https://" /></label>
              <p class="field wide slot-lock">{{ tx("填写网址就只采这个页面。留空则按关键词从全网搜索站点入库。", "A URL crawls that page only. Leave it empty to search the web for the keyword.") }}</p>
              <div class="field pick">
                <span>{{ tx("栏目", "Tab") }}</span>
                <input v-model="tabQuery" :placeholder="tx('输入栏目名称', 'Type a tab')" @focus="pickOpen = 'tab'" @input="pickOpen = 'tab'" />
                <ul v-if="pickOpen === 'tab'">
                  <li v-for="tab in tabHits" :key="tab.id" @mousedown.prevent="chooseTab(tab)">{{ tab.title_zh || tab.title_en }}</li>
                  <li v-if="!tabHits.length" class="empty">{{ tx("没有匹配的栏目", "No matching tab") }}</li>
                </ul>
              </div>
              <div class="field pick">
                <span>{{ tx("分类", "Category") }}</span>
                <input v-model="catQuery" :placeholder="tx('输入分类名称', 'Type a category')" @focus="pickOpen = 'cat'" @input="pickOpen = 'cat'" />
                <ul v-if="pickOpen === 'cat'">
                  <li v-for="cat in catHits" :key="cat.id" @mousedown.prevent="chooseCat(cat)">{{ cat.title_zh || cat.title_en }}</li>
                  <li v-if="!catHits.length" class="empty">{{ tx("没有匹配的分类", "No matching category") }}</li>
                </ul>
              </div>
              <label class="field"><span>{{ tx("间隔（分钟）", "Interval (minutes)") }}</span><input v-model.number="editor.row.interval_minutes" type="number" min="1" /></label>
            </template>
            <template v-else-if="editor.kind === 'admin'">
              <label class="field"><span>{{ tx("邮箱", "Email") }}</span><input v-model="editor.row.email" type="email" required /></label>
              <label class="field"><span>{{ tx("密码", "Password") }}</span><input v-model="editor.row.password" type="password" minlength="8" required /></label>
            </template>
            <template v-else-if="editor.kind === 'ban'">
              <label class="field"><span>IP</span><input v-model="editor.row.ip" required /></label>
            </template>
            <template v-else-if="editor.kind === 'password'">
              <label class="field wide"><span>{{ editor.row.email }}</span><input v-model="editor.row.password" type="password" minlength="8" :placeholder="tx('新密码至少 8 位', 'New password, at least 8 characters')" required /></label>
            </template>
          </div>
          <footer>
            <p v-if="error">{{ error === "password too short" ? tx("新密码至少 8 位", "New password, at least 8 characters") : error }}</p>
            <button type="button" @click="editor = null">{{ tx("取消", "Cancel") }}</button>
            <button class="primary" type="submit">{{ tx("确定", "OK") }}</button>
          </footer>
        </form>
      </div>
    </div>
    </div>
  </div>
</template>
