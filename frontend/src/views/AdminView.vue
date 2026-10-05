<script setup>
import { onMounted, ref } from "vue";
import http, { setGate } from "../api";

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
const items = ref([]);
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
  { page: "综合资讯内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-general-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "AI工具内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-ai-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "跨境电商内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-cross-border-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "午夜媒体内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-media-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "TG群内容区", items: [1, 2, 3, 4].map((n) => ({ id: `feed-telegram-${n}`, where: `第 ${n} 条，隔两个分类出现` })) },
  { page: "关于我们右侧", items: [1, 2, 3].map((n) => ({ id: `about-${n}`, where: `右侧第 ${n} 个` })) },
  { page: "联系方式右侧", items: [1, 2, 3].map((n) => ({ id: `contact-${n}`, where: `右侧第 ${n} 个` })) },
  { page: "登录 / 注册左侧", items: [1, 2, 3].map((n) => ({ id: `auth-${n}`, where: `左侧轮播第 ${n} 张` })) },
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

async function load() {
  const [t, c, l, p, a, u, j, i] = await Promise.all([
    http.get("/manage/tabs"),
    http.get("/manage/categories"),
    http.get("/manage/links"),
    http.get("/manage/pages"),
    http.get("/manage/ads"),
    http.get("/manage/users"),
    http.get("/manage/crawl/jobs"),
    http.get("/manage/crawl/items"),
  ]);
  tabs.value = t.data;
  categories.value = c.data;
  links.value = l.data;
  pages.value = p.data;
  ads.value = a.data;
  users.value = u.data;
  jobs.value = j.data;
  items.value = i.data;
}

onMounted(async () => {
  setGate(props.gate);
  try {
    await http.get("/manage/ping");
    me.value = (await http.get("/auth/me")).data;
    ready.value = true;
    if (me.value.totp_enabled && me.value.totp_ok) await load();
  } catch (err) {
    if (err.response?.status === 404) missing.value = true;
    else error.value = err.response?.data?.detail || "Sign in as an admin, then open this address again.";
  }
});

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
async function setPlan(user, plan) {
  await http.put(`/manage/users/${user.id}`, { plan, days: 30 });
  await load();
}
</script>

<template>
  <p v-if="missing" class="page">Not found.</p>
  <div v-else-if="!ready" class="page">
    <p>{{ error || "Checking the console address…" }}</p>
    <p><a href="/login">Log in</a> with the admin account first. Administrators must complete the authenticator step below.</p>
  </div>
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
        <button class="text-btn" @click="section = 'links'">Links</button>
        <button class="text-btn" @click="section = 'structure'">Tabs</button>
        <button class="text-btn" @click="section = 'pages'">Pages</button>
        <button class="text-btn" @click="section = 'ads'">Ads</button>
        <button class="text-btn" @click="section = 'crawl'">Crawl</button>
        <button class="text-btn" @click="section = 'users'">Users</button>
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
          <tr v-for="link in links" :key="link.id"><td>{{ link.title_en }}</td><td>{{ link.status }}</td><td>{{ link.url }}</td></tr>
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
      <table v-if="section === 'users'">
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.email }}</td>
          <td>{{ user.role }}</td>
          <td>{{ user.plan }}</td>
          <td>
            <button @click="setPlan(user, 'vip')">VIP 30d</button>
            <button @click="setPlan(user, 'free')">Free</button>
          </td>
        </tr>
      </table>
    </template>
  </div>
</template>
