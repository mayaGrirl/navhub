<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import http, { setGate } from "../api";

const router = useRouter();

const props = defineProps({ gate: String });
const ready = ref(false);
const missing = ref(false);
const section = ref("links");
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
  const [t, c, l, p, a, u, j, i, lv, al] = await Promise.all([
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
  ]);
  tabs.value = t.data;
  categories.value = c.data;
  links.value = l.data;
  pages.value = p.data;
  ads.value = a.data;
  users.value = u.data;
  jobs.value = j.data;
  items.value = i.data;
  levels.value = lv.data.levels || [];
  pointsPerLink.value = lv.data.points_per_link || 1;
  alerts.value = al.data;
  try {
    proxies.value = (await http.get("/manage/proxies")).data;
  } catch {
    proxies.value = { count: 0, sources: 0, items: [], note: "unavailable" };
  }
}

onMounted(async () => {
  setGate(props.gate);
  try {
    await http.get("/manage/ping");
    me.value = (await http.get("/auth/me")).data;
    ready.value = true;
    if (me.value.totp_enabled && me.value.totp_ok) await load();
  } catch (err) {
    if (err.response?.status === 404) {
      missing.value = true;
      router.replace("/");
    }
    else {
      needConsole.value = true;
      error.value = err.response?.data?.detail || "";
    }
  }
});

async function consoleLogin() {
  error.value = "";
  try {
    await http.post("/auth/console", { email: consoleEmail.value, password: consolePassword.value, totp: consoleCode.value });
    me.value = (await http.get("/auth/me")).data;
    ready.value = true;
    needConsole.value = false;
    if (me.value.totp_enabled && me.value.totp_ok) await load();
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}

async function setupTotp() {
  totp.value = (await http.post("/auth/totp/setup")).data;
}

async function confirmTotp() {
  await http.post("/auth/totp/confirm", { code: code.value });
  me.value = (await http.get("/auth/me")).data;
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
async function banAlert(id) {
  await http.post(`/manage/alerts/${id}/ban`);
  await load();
}
async function banUser(user) {
  await http.put(`/manage/users/${user.id}`, { banned: !user.banned });
  await load();
}
async function setPlan(user, plan) {
  await http.put(`/manage/users/${user.id}`, { plan, days: 30 });
  await load();
}
</script>

<template>
  <p v-if="missing" class="page">Not found.</p>
  <form v-else-if="needConsole" class="page form" @submit.prevent="consoleLogin">
    <h1>管理后台登录</h1>
    <input v-model="consoleEmail" type="email" placeholder="邮箱" required />
    <input v-model="consolePassword" type="password" placeholder="密码" required />
    <input v-model="consoleCode" placeholder="验证器验证码，未开启可留空" />
    <button class="primary" type="submit">登录后台</button>
    <p v-if="error === 'totp required'">这个账号已开启验证器，请填写验证码。</p>
    <p v-else-if="error === 'invalid credentials'">邮箱或密码不正确。</p>
    <p v-else-if="error">{{ error }}</p>
  </form>
  <div v-else-if="!ready" class="page">Checking the console address…</div>
  <div v-else class="admin">
    <h1>Console</h1>
    <div v-if="!me.totp_enabled || !me.totp_ok">
      <p>Set up an authenticator before editing the directory.</p>
      <button class="primary" @click="setupTotp">Generate key</button>
      <p v-if="totp">{{ totp.secret }}</p>
      <input v-model="code" placeholder="6-digit code" />
      <button class="primary" @click="confirmTotp">Confirm</button>
    </div>
    <template v-else>
      <div class="nav-links">
        <button class="text-btn" @click="section = 'alerts'">报警 {{ alerts.filter((item) => !item.handled).length }}</button>
        <button class="text-btn" @click="section = 'links'">Links</button>
        <button class="text-btn" @click="section = 'structure'">Tabs</button>
        <button class="text-btn" @click="section = 'pages'">Pages</button>
        <button class="text-btn" @click="section = 'ads'">Ads</button>
        <button class="text-btn" @click="section = 'crawl'">Crawl</button>
        <button class="text-btn" @click="section = 'users'">Users</button>
        <button class="text-btn" @click="section = 'proxies'">Proxies</button>
        <button class="text-btn" @click="section = 'levels'">Levels</button>
      </div>
      <form v-if="section === 'links'" class="form" @submit.prevent="saveLink">
        <select v-model="linkForm.category_id">
          <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.title_en }}</option>
        </select>
        <input v-model="linkForm.title_en" placeholder="English name" />
        <input v-model="linkForm.title_zh" placeholder="中文名称" />
        <input v-model="linkForm.url" placeholder="https://" required />
        <input v-model="linkForm.description_en" placeholder="English description" />
        <input v-model="linkForm.description_zh" placeholder="中文简介" />
        <label><input type="checkbox" v-model="linkForm.is_free" /> Free</label>
        <label><input type="checkbox" v-model="linkForm.is_hot" /> Hot</label>
        <button class="primary">Add link</button>
        <table>
          <tr v-for="link in links" :key="link.id">
            <td>{{ link.title_zh || link.title_en }}</td>
            <td>{{ sourceLabel(link.source) }}</td>
            <td>{{ link.status }}</td>
            <td>{{ link.review_note }}</td>
            <td><input v-model.number="link.favorite_count" type="number" min="0" /></td>
            <td><input v-model.number="link.recommend_count" type="number" min="0" /></td>
            <td><button type="button" @click="saveCounts(link)">保存次数</button></td>
          </tr>
        </table>
      </form>
      <form v-if="section === 'structure'" class="form" @submit.prevent="saveTab">
        <input v-model="tabForm.slug" placeholder="slug" required />
        <input v-model="tabForm.title_en" placeholder="English tab" />
        <input v-model="tabForm.title_zh" placeholder="中文分区" />
        <label><input type="checkbox" v-model="tabForm.adult" /> 18+</label>
        <button class="primary">Add tab</button>
        <input v-model="catForm.tab_id" placeholder="Tab id" />
        <input v-model="catForm.slug" placeholder="category slug" />
        <input v-model="catForm.title_en" placeholder="English category" />
        <input v-model="catForm.title_zh" placeholder="中文细分类" />
        <button class="primary" type="button" @click="saveCategory">Add category</button>
        <p v-for="tab in tabs" :key="tab.id">{{ tab.id }} {{ tab.title_en }} / {{ tab.title_zh }}</p>
      </form>
      <div v-if="section === 'pages'" class="form">
        <form v-for="page in pages" :key="page.id" @submit.prevent="savePage(page)">
          <h3>{{ page.key }}</h3>
          <input v-model="page.title_en" />
          <input v-model="page.title_zh" />
          <textarea v-model="page.body_en" rows="3"></textarea>
          <textarea v-model="page.body_zh" rows="3"></textarea>
          <input v-model="page.email" placeholder="Email" />
          <input v-model="page.phone" placeholder="Phone" />
          <input v-model="page.im" placeholder="Telegram，如 nexa 或 https://t.me/nexa" />
          <input v-model="page.address" placeholder="Address" />
          <button class="primary">Save</button>
        </form>
      </div>
      <form v-if="section === 'ads'" class="form" @submit.prevent="saveAd">
        <p>选位置后再添加。删掉后，前台那个位置马上不再显示。</p>
        <select v-model="adForm.slot">
          <optgroup v-for="group in slotGroups" :key="group.page" :label="group.page">
            <option v-for="item in group.items" :key="item.id" :value="item.id">{{ group.page }} · {{ item.where }}</option>
          </optgroup>
        </select>
        <input v-model="adForm.title_zh" placeholder="中文名称" />
        <input v-model="adForm.title_en" placeholder="English name" />
        <input v-model="adForm.image_url" placeholder="图片地址" />
        <input v-model="adForm.link_url" placeholder="跳转地址" />
        <button class="primary">Add ad</button>
        <table>
          <tr><th>显示位置</th><th>名称</th><th></th></tr>
          <tr v-for="ad in ads" :key="ad.id">
            <td>{{ slotWhere(ad.slot) }}</td>
            <td>{{ ad.title_zh || ad.title_en }}</td>
            <td><button type="button" @click="removeAd(ad.id)">删除</button></td>
          </tr>
        </table>
      </form>
      <form v-if="section === 'crawl'" class="form" @submit.prevent="fetchCrawl">
        <input v-model="crawlForm.url" placeholder="https://example.com" required />
        <input v-model="crawlForm.category_id" placeholder="Category id" required />
        <button class="primary">Fetch page</button>
        <table>
          <tr v-for="item in items" :key="item.id">
            <td>{{ item.title }}</td>
            <td>{{ item.url }}</td>
            <td><button type="button" @click="approve(item.id)">Approve</button></td>
          </tr>
        </table>
      </form>
      <div v-if="section === 'levels'" class="form">
        <p>0 到 10 级。积分达到该级门槛后自动升级，每分钟代理次数跟着当前等级走。站内已有的相同网址不加分。</p>
        <label>每个有效链接获得的积分</label>
        <input v-model.number="pointsPerLink" type="number" min="1" />
        <button type="button" @click="savePointRule">保存积分</button>
        <table>
          <tr v-for="row in levels" :key="row.level">
            <td>Lv.{{ row.level }}</td>
            <td><input v-model.number="row.min_points" type="number" /></td>
            <td><input v-model.number="row.proxy_per_minute" type="number" /></td>
            <td><button type="button" @click="saveLevel(row)">保存</button></td>
          </tr>
        </table>
      </div>
      <div v-if="section === 'proxies'" class="form">
        <p>可用代理 {{ proxies.count }} 条，来源 {{ proxies.sources }} 个。每 3 分钟检测，失效的会删掉。</p>
        <p v-if="proxies.note">{{ proxies.note }}</p>
        <h2>可用代理</h2>
        <table>
          <tr v-for="item in proxies.items" :key="item.url"><td>{{ item.url }}</td><td>{{ item.checked_at }}</td><td><button type="button" @click="dropProxy(item.url)">删除</button></td></tr>
        </table>
        <h2>来源</h2>
        <table>
          <tr v-for="item in proxies.source_items" :key="item.url"><td>{{ item.url }}</td><td><button type="button" @click="dropSource(item.url)">删除</button></td></tr>
        </table>
      </div>
      <div v-if="section === 'alerts'" class="form">
        <p v-if="!alerts.length">暂无报警</p>
        <p v-for="item in alerts" :key="item.id">
          {{ item.email }} · {{ item.ip }} · {{ item.detail }}
          <button v-if="!item.handled" type="button" @click="banAlert(item.id)">封禁账号和 IP</button>
          <span v-else>已处理</span>
        </p>
      </div>
      <table v-if="section === 'users'">
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.email }}</td>
          <td>{{ user.role }}</td>
          <td>{{ user.plan }}</td>
          <td>{{ user.banned ? "已封禁" : user.last_ip }}</td>
          <td>
            <button @click="setPlan(user, 'vip')">VIP 30d</button>
            <button @click="setPlan(user, 'free')">Free</button>
            <button @click="banUser(user)">{{ user.banned ? "解封" : "封禁" }}</button>
          </td>
        </tr>
      </table>
    </template>
  </div>
</template>
