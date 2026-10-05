<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import http from "../api";

const { t, locale } = useI18n();
const tabs = ref([]);
const tabId = ref(null);
const sections = ref([]);
const news = ref([]);
const notes = ref([]);
const growthRanks = ref([]);
const totalRanks = ref([]);
const bannerIndex = ref(0);
const dragX = ref(0);
const contact = ref(null);
const user = ref(null);
const period = ref("past_24_hours");
const ads = ref([]);
const query = ref("");
const siteQuery = ref("");
const siteHits = ref([]);
const siteWhere = ref("");
const engine = ref("baidu");
const engineGroups = [
  {
    zh: "网页",
    en: "Web",
    items: [
      { id: "baidu", zh: "百度", en: "Baidu" },
      { id: "google", zh: "Google", en: "Google" },
      { id: "bing", zh: "Bing", en: "Bing" },
      { id: "sogou", zh: "搜狗", en: "Sogou" },
      { id: "so360", zh: "360", en: "360" },
      { id: "shenma", zh: "神马", en: "Shenma" },
      { id: "yahoo", zh: "Yahoo", en: "Yahoo" },
      { id: "yandex", zh: "Yandex", en: "Yandex" },
      { id: "ecosia", zh: "Ecosia", en: "Ecosia" },
    ],
  },
  {
    zh: "聚合",
    en: "Meta",
    items: [
      { id: "duckduckgo", zh: "DuckDuckGo", en: "DuckDuckGo" },
      { id: "brave", zh: "Brave", en: "Brave" },
      { id: "startpage", zh: "Startpage", en: "Startpage" },
      { id: "qwant", zh: "Qwant", en: "Qwant" },
      { id: "miji", zh: "秘迹", en: "Miji" },
    ],
  },
  {
    zh: "空间",
    en: "Space",
    items: [
      { id: "weibo", zh: "微博", en: "Weibo" },
      { id: "xhs", zh: "小红书", en: "RED" },
      { id: "douyin", zh: "抖音", en: "Douyin" },
      { id: "bilibili", zh: "哔哩哔哩", en: "Bilibili" },
      { id: "zhihu", zh: "知乎", en: "Zhihu" },
      { id: "x", zh: "X", en: "X" },
    ],
  },
  {
    zh: "指纹",
    en: "Print",
    items: [
      { id: "browserscan", zh: "BrowserScan", en: "BrowserScan" },
      { id: "browserleaks", zh: "BrowserLeaks", en: "BrowserLeaks" },
      { id: "creepjs", zh: "CreepJS", en: "CreepJS" },
      { id: "amiunique", zh: "AmIUnique", en: "AmIUnique" },
    ],
  },
];
const hotWords = {
  zh: ["人工智能", "跨境电商", "ChatGPT", "GitHub", "Telegram", "短视频", "今日热点"],
  en: ["AI tools", "cross-border", "ChatGPT", "GitHub", "Telegram", "short video", "top news"],
};
const bannerAds = computed(() => ads.value.filter((item) => item.slot === "banner"));
const growthAds = computed(() => ads.value.filter((item) => item.slot === "github-growth"));
const totalAds = computed(() => ads.value.filter((item) => item.slot === "github-total"));
const footerAds = computed(() => ads.value.filter((item) => item.slot === "footer"));
const feedAds = computed(() => {
  const slug = currentTab.value?.slug;
  if (!slug) return [];
  return ads.value
    .filter((item) => item.slot.startsWith(`feed-${slug}-`))
    .sort((a, b) => a.slot.localeCompare(b.slot));
});

function feedAdAt(index) {
  if ((index + 1) % 2 !== 0) return null;
  return feedAds.value[(index + 1) / 2 - 1] || null;
}
const activeSection = ref(null);
const adultOk = ref(sessionStorage.getItem("adult-ok") === "1");

const currentTab = computed(() => tabs.value.find((item) => item.id === tabId.value));
const isHome = computed(() => !currentTab.value || currentTab.value.kind === "home");
const newsGroups = [
  { id: "society", zh: "社会新闻", en: "Society" },
  { id: "world", zh: "国际新闻", en: "World" },
  { id: "tech", zh: "科技数码", en: "Technology" },
  { id: "business", zh: "财经商业", en: "Business" },
  { id: "entertainment", zh: "娱乐八卦", en: "Entertainment" },
  { id: "film", zh: "影视音乐", en: "Film" },
  { id: "games", zh: "游戏电竞", en: "Games" },
  { id: "sports", zh: "体育赛事", en: "Sports" },
  { id: "auto", zh: "汽车出行", en: "Autos" },
  { id: "education", zh: "教育学习", en: "Education" },
  { id: "health", zh: "健康医疗", en: "Health" },
  { id: "travel", zh: "旅游出行", en: "Travel" },
  { id: "food", zh: "美食生活", en: "Food" },
  { id: "house", zh: "房产家居", en: "Housing" },
  { id: "fashion", zh: "时尚穿搭", en: "Fashion" },
  { id: "military", zh: "军事观察", en: "Military" },
  { id: "science", zh: "科学探索", en: "Science" },
  { id: "digital", zh: "数码硬件", en: "Gadgets" },
  { id: "ai-news", zh: "人工智能", en: "AI News" },
  { id: "jobs", zh: "职场求职", en: "Careers" },
  { id: "startup", zh: "创业投资", en: "Startups" },
  { id: "history", zh: "历史文化", en: "History" },
  { id: "parenting", zh: "亲子育儿", en: "Parenting" },
];
const groupedNews = computed(() =>
  newsGroups
    .map((group) => ({ ...group, items: news.value.filter((item) => (item.category || "tech") === group.id) }))
    .filter((group) => group.items.length)
);

async function loadTree() {
  const { data } = await http.get("/tree", { params: { locale: locale.value } });
  tabs.value = data;
  if (!data.find((item) => item.id === tabId.value)) {
    tabId.value = data.find((item) => item.kind === "home")?.id || data[0]?.id || null;
  }
}

async function loadBoard() {
  if (!currentTab.value || currentTab.value.kind === "home") {
    sections.value = [];
    return;
  }
  const { data } = await http.get("/board", { params: { tab_id: currentTab.value.id, locale: locale.value } });
  sections.value = data;
  activeSection.value = data[0]?.id || null;
}

function jumpTo(id) {
  activeSection.value = id;
  document.getElementById(`cat-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadRanks(next = period.value) {
  period.value = next;
  const [growth, total] = await Promise.all([
    http.get("/github", { params: { period: next } }),
    http.get("/github", { params: { period: "total" } }),
  ]);
  const byStars = (rows) => [...(Array.isArray(rows) ? rows : [])].sort(
    (a, b) => Number(String(b.stars).replace(/\D/g, "")) - Number(String(a.stars).replace(/\D/g, ""))
  );
  growthRanks.value = byStars(growth.data);
  totalRanks.value = byStars(total.data);
}

function moveBanner(step) {
  const count = bannerAds.value.length;
  if (!count) return;
  bannerIndex.value = (bannerIndex.value + step + count) % count;
}

function onBannerDown(event) {
  dragX.value = event.clientX;
}

function onBannerUp(event) {
  if (!dragX.value) return;
  const delta = event.clientX - dragX.value;
  dragX.value = 0;
  if (delta > 40) moveBanner(-1);
  else if (delta < -40) moveBanner(1);
}

function pickTab(id) {
  tabId.value = id;
}

function allowAdult() {
  adultOk.value = true;
  sessionStorage.setItem("adult-ok", "1");
}

async function logout() {
  await http.post("/auth/logout");
  user.value = null;
}

function setLocale(next) {
  locale.value = next;
  localStorage.setItem("locale", next);
}

const welcome = computed(() => {
  if (notes.value[0]) return `${notes.value[0].title} ${notes.value[0].body}`.trim();
  return locale.value === "zh" ? "欢迎来到 NEXA，工具、资讯和排行都在这里。" : "Welcome to NEXA — tools, news, and rankings.";
});

function siteIcon(url) {
  try {
    const host = new URL(url).hostname;
    return host ? `https://www.google.com/s2/favicons?domain=${host}&sz=64` : "";
  } catch {
    return "";
  }
}

function logoOf(link) {
  const url = String(link.url || "");
  const name = url.match(/t\.me\/([A-Za-z0-9_]{3,})/);
  if (name) return `https://t.me/i/userpic/320/${name[1]}.jpg`;
  const logo = link.logo_url || "";
  const placeholder = !logo || /empty\.png|google\.com\/s2\/favicons|opengraph|ogp|default_social/i.test(logo);
  return placeholder ? siteIcon(url) || "/favicon.svg" : logo;
}

function useFallback(event, link) {
  const img = event.target;
  const step = img.dataset.fallback || "0";
  const url = String(link.url || "");
  if (step === "0") {
    img.dataset.fallback = "1";
    img.src = url.includes("t.me/") ? "/tg.svg" : siteIcon(url) || "/favicon.svg";
    return;
  }
  if (step === "1" && !url.includes("t.me/")) {
    img.dataset.fallback = "2";
    img.src = "/favicon.svg";
  }
}

function searchWeb() {
  const text = query.value.trim();
  const direct = ["browserscan", "browserleaks", "creepjs", "amiunique"].includes(engine.value);
  if (!text && !direct) return;
  const encoded = encodeURIComponent(text);
  const urls = {
    baidu: `https://www.baidu.com/s?wd=${encoded}`,
    google: `https://www.google.com/search?q=${encoded}`,
    bing: `https://www.bing.com/search?q=${encoded}`,
    sogou: `https://www.sogou.com/web?query=${encoded}`,
    so360: `https://www.so.com/s?q=${encoded}`,
    shenma: `https://m.sm.cn/s?q=${encoded}`,
    yahoo: `https://search.yahoo.com/search?p=${encoded}`,
    yandex: `https://yandex.com/search/?text=${encoded}`,
    ecosia: `https://www.ecosia.org/search?q=${encoded}`,
    duckduckgo: `https://duckduckgo.com/?q=${encoded}`,
    brave: `https://search.brave.com/search?q=${encoded}`,
    startpage: `https://www.startpage.com/sp/search?query=${encoded}`,
    qwant: `https://www.qwant.com/?q=${encoded}`,
    miji: `https://mijisou.com/?q=${encoded}`,
    weibo: `https://s.weibo.com/weibo?q=${encoded}`,
    xhs: `https://www.xiaohongshu.com/search_result?keyword=${encoded}`,
    douyin: `https://www.douyin.com/search/${encoded}`,
    bilibili: `https://search.bilibili.com/all?keyword=${encoded}`,
    zhihu: `https://www.zhihu.com/search?type=content&q=${encoded}`,
    x: `https://x.com/search?q=${encoded}`,
    browserscan: "https://www.browserscan.net/zh",
    browserleaks: "https://browserleaks.com/",
    creepjs: "https://abrahamjuliot.github.io/creepjs/",
    amiunique: "https://amiunique.org/",
  };
  window.open(urls[engine.value] || urls.baidu, "_blank", "noopener");
}

let siteTimer = 0;
function onSiteInput(where) {
  siteWhere.value = where;
  clearTimeout(siteTimer);
  siteTimer = setTimeout(searchSite, 250);
}

async function searchSite() {
  const text = siteQuery.value.trim();
  if (!text) {
    siteHits.value = [];
    return;
  }
  const { data } = await http.get("/search", { params: { q: text, locale: locale.value } });
  siteHits.value = data;
}

function searchWord(word) {
  query.value = word;
  searchWeb();
}

watch(tabId, loadBoard);
watch(locale, async () => {
  const title = locale.value === "zh" ? "NEXA — 工具、资讯与排行" : "NEXA — AI tools, news, and rankings";
  const description = locale.value === "zh"
    ? "NEXA 是双语导航站，收录 AI 工具、跨境工具、资讯、Telegram 频道和 GitHub 排行。"
    : "NEXA is a bilingual directory of AI tools, cross-border tools, news, Telegram channels, and GitHub rankings.";
  document.title = title;
  document.documentElement.lang = locale.value === "zh" ? "zh-CN" : "en";
  document.querySelector('meta[name="description"]')?.setAttribute("content", description);
  document.querySelector('meta[property="og:title"]')?.setAttribute("content", title);
  document.querySelector('meta[property="og:description"]')?.setAttribute("content", description);
  await loadTree();
  await loadBoard();
});

onMounted(async () => {
  document.title = locale.value === "zh" ? "NEXA — 工具、资讯与排行" : "NEXA — AI tools, news, and rankings";
  const [tree, noteRes, newsRes, contactRes, me, adRes] = await Promise.allSettled([
    http.get("/tree", { params: { locale: locale.value } }),
    http.get("/announcements", { params: { locale: locale.value } }),
    http.get("/news"),
    http.get("/pages/contact", { params: { locale: locale.value } }),
    http.get("/auth/me"),
    http.get("/ads", { params: { locale: locale.value } }),
  ]);
  if (tree.status === "fulfilled") {
    tabs.value = tree.value.data;
    tabId.value = tabs.value.find((item) => item.kind === "home")?.id || tabs.value[0]?.id || null;
  }
  if (noteRes.status === "fulfilled") notes.value = noteRes.value.data;
  if (newsRes.status === "fulfilled") news.value = newsRes.value.data;
  if (contactRes.status === "fulfilled") contact.value = contactRes.value.data;
  if (me.status === "fulfilled") user.value = me.value.data;
  if (adRes.status === "fulfilled") ads.value = adRes.value.data;
  loadRanks("past_24_hours");
});

const bannerTimer = setInterval(() => moveBanner(1), 4000);
onUnmounted(() => clearInterval(bannerTimer));
</script>

<template>
  <div class="shell">
    <header class="top">
      <a class="brand" href="/"><img src="/logo.svg" alt="" />NEXA</a>
      <nav class="tabs">
        <button v-for="tab in tabs" :key="tab.id" :class="{ active: tab.id === tabId }" @click="pickTab(tab.id)">
          {{ tab.title }}
        </button>
      </nav>
      <div class="site-search">
        <input v-model="siteQuery" :placeholder="locale === 'zh' ? '站内搜索' : 'Search this site'" @input="onSiteInput('top')" @focus="onSiteInput('top')" />
        <div v-if="siteWhere === 'top' && siteQuery.trim() && siteHits.length" class="site-hits">
          <a v-for="hit in siteHits" :key="hit.id" :href="hit.url" target="_blank" rel="noreferrer">
            <strong>{{ hit.title }}</strong>
            <em>{{ hit.tab }} · {{ hit.category }}</em>
          </a>
        </div>
        <p v-else-if="siteWhere === 'top' && siteQuery.trim()" class="site-hits empty">{{ locale === "zh" ? "没有匹配的链接" : "No matching links" }}</p>
      </div>
      <div class="nav-links">
        <a href="/about">{{ t("about") }}</a>
        <a href="/contact">{{ t("contact") }}</a>
        <a v-if="user" href="/submit">{{ t("submit") }}</a>
        <button class="text-btn" @click="setLocale(locale === 'en' ? 'zh' : 'en')">{{ locale === "en" ? "中文" : "EN" }}</button>
        <a v-if="!user" href="/login">{{ t("login") }}</a>
        <button v-else class="text-btn" @click="logout">{{ t("logout") }}</button>
      </div>
    </header>
    <section class="mast">
      <a class="mast-brand" href="/">
        <span class="mast-name"><img class="mast-mark" src="/logo.svg" alt="" /><strong>NEXA</strong></span>
        <span>{{ welcome }}</span>
      </a>
      <div class="finder">
        <div class="engines">
          <div v-for="group in engineGroups" :key="group.en" class="engine-row">
            <span>{{ locale === "zh" ? group.zh : group.en }}</span>
            <button
              v-for="item in group.items"
              :key="item.id"
              type="button"
              :class="{ on: engine === item.id }"
              @click="engine = item.id"
            >{{ locale === "zh" ? item.zh : item.en }}</button>
          </div>
        </div>
        <form class="web-search" @submit.prevent="searchWeb">
          <input v-model="query" :placeholder="locale === 'zh' ? '搜索全网' : 'Search the web'" />
          <button type="submit">{{ locale === "zh" ? "搜索" : "Search" }}</button>
        </form>
        <div class="hot-words">
          <button v-for="word in hotWords[locale] || hotWords.en" :key="word" type="button" @click="searchWord(word)">{{ word }}</button>
        </div>
      </div>
      <aside v-if="bannerAds.length" class="mast-ads">
        <div class="carousel" @pointerdown="onBannerDown" @pointerup="onBannerUp">
          <a
            v-for="(ad, index) in bannerAds"
            :key="ad.id"
            class="slide"
            :class="{ on: index === bannerIndex }"
            :href="ad.link_url || undefined"
            target="_blank"
            rel="noopener"
          >
            <img v-if="ad.image_url" :src="ad.image_url" :alt="ad.title" />
            <span>{{ ad.title }}</span>
          </a>
          <div v-if="bannerAds.length > 1" class="dots">
            <button v-for="(ad, index) in bannerAds" :key="ad.id" type="button" :class="{ on: index === bannerIndex }" @click="bannerIndex = index"></button>
          </div>
        </div>
      </aside>
    </section>

    <div class="portal">
      <aside class="panel side-jump">
        <template v-if="isHome">
          <p class="side-label">{{ locale === "zh" ? "资讯" : "News" }}</p>
          <button v-for="group in groupedNews" :key="group.id" :class="{ on: activeSection === group.id }" @click="jumpTo(group.id)">
            <i></i>
            <span>{{ locale === "zh" ? group.zh : group.en }}</span>
            <em>{{ group.items.length }}</em>
          </button>
        </template>
        <template v-else>
          <p class="side-label">{{ currentTab?.title }}</p>
          <button v-for="section in sections" :key="section.id" :class="{ on: activeSection === section.id }" @click="jumpTo(section.id)">
            <i></i>
            <span>{{ section.title }}</span>
            <em>{{ section.links.length }}</em>
          </button>
        </template>
      </aside>

      <main class="panel feed">
        <template v-if="currentTab?.adult && !adultOk">
          <h2>{{ t("adultTitle") }}</h2>
          <p>{{ t("adultBody") }}</p>
          <button class="primary" @click="allowAdult">{{ t("enter") }}</button>
        </template>
        <template v-else-if="isHome">
          <template v-for="(group, index) in groupedNews" :key="group.id">
          <section :id="`cat-${group.id}`" class="group">
            <h2>{{ locale === "zh" ? group.zh : group.en }}</h2>
            <a class="story" v-for="item in group.items" :key="item.id" :href="item.url" target="_blank" rel="noreferrer">
              <h3>{{ item.title }}</h3>
              <p class="meta">{{ item.source }}<span v-if="item.published_at"> · {{ item.published_at.slice(0, 16).replace("T", " ") }}</span></p>
              <p v-if="item.summary">{{ item.summary.replace(/<[^>]+>/g, "").slice(0, 140) }}</p>
            </a>
          </section>
          <a v-if="feedAdAt(index)" class="feed-ad" :href="feedAdAt(index).link_url || undefined" target="_blank" rel="noopener">
            <img v-if="feedAdAt(index).image_url" :src="feedAdAt(index).image_url" :alt="feedAdAt(index).title" />
            <span>{{ feedAdAt(index).title }}</span>
          </a>
          </template>
          <p v-if="!groupedNews.length" class="meta">{{ locale === "zh" ? "还没有资讯" : "No stories yet" }}</p>
        </template>
        <template v-else>
          <template v-for="(section, index) in sections" :key="section.id">
          <section :id="`cat-${section.id}`" class="group">
            <h2>{{ section.title }}</h2>
            <div class="grid">
              <a class="card" v-for="link in section.links" :key="link.id" :href="link.url" target="_blank" rel="noreferrer">
                <img class="logo" :src="logoOf(link)" alt="" referrerpolicy="no-referrer" @error="useFallback($event, link)" />
                <div>
                  <h3>{{ link.title }}</h3>
                  <p>{{ link.description }}</p>
                </div>
              </a>
            </div>
          </section>
          <a v-if="feedAdAt(index)" class="feed-ad" :href="feedAdAt(index).link_url || undefined" target="_blank" rel="noopener">
            <img v-if="feedAdAt(index).image_url" :src="feedAdAt(index).image_url" :alt="feedAdAt(index).title" />
            <span>{{ feedAdAt(index).title }}</span>
          </a>
          </template>
        </template>
      </main>

      <aside class="panel rank-side">
        <section>
          <h2>GitHub · {{ locale === "zh" ? "增量" : "Growth" }}</h2>
          <div class="rank-switch">
            <button :class="{ on: period === 'past_24_hours' }" @click="loadRanks('past_24_hours')">24h</button>
            <button :class="{ on: period === 'past_week' }" @click="loadRanks('past_week')">{{ locale === "zh" ? "周" : "Week" }}</button>
            <button :class="{ on: period === 'past_month' }" @click="loadRanks('past_month')">{{ locale === "zh" ? "月" : "Month" }}</button>
          </div>
          <a class="rank" v-for="(repo, index) in growthRanks.slice(0, 10)" :key="repo.repo_name || index" :href="`https://github.com/${repo.repo_name}`" target="_blank">
            <b v-if="index > 2" class="medal">{{ index + 1 }}</b>
            <svg v-else class="medal-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 14.5 7 21l5-2.5L17 21l-1-6.5" :fill="['#e2b340','#b7c0ca','#c4845a'][index]" />
              <circle cx="12" cy="9" r="6.5" :fill="['#f0c84a','#d5dde6','#d39262'][index]" />
              <text x="12" y="11.6" text-anchor="middle" font-size="8" font-weight="700" fill="#3a3328">{{ index + 1 }}</text>
            </svg>
            <span>{{ repo.repo_name }}</span>
            <em>+{{ repo.stars }}</em>
          </a>
          <div v-if="growthAds.length" class="slot-ads">
            <a v-for="ad in growthAds" :key="ad.id" :href="ad.link_url || undefined" target="_blank" rel="noopener">
              <img v-if="ad.image_url" :src="ad.image_url" :alt="ad.title" />
              <span>{{ ad.title }}</span>
            </a>
          </div>
        </section>
        <section>
          <h2>GitHub · {{ locale === "zh" ? "总量" : "Total" }}</h2>
          <a class="rank" v-for="(repo, index) in totalRanks.slice(0, 10)" :key="'t-' + (repo.repo_name || index)" :href="`https://github.com/${repo.repo_name}`" target="_blank">
            <b v-if="index > 2" class="medal">{{ index + 1 }}</b>
            <svg v-else class="medal-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 14.5 7 21l5-2.5L17 21l-1-6.5" :fill="['#e2b340','#b7c0ca','#c4845a'][index]" />
              <circle cx="12" cy="9" r="6.5" :fill="['#f0c84a','#d5dde6','#d39262'][index]" />
              <text x="12" y="11.6" text-anchor="middle" font-size="8" font-weight="700" fill="#3a3328">{{ index + 1 }}</text>
            </svg>
            <span>{{ repo.repo_name }}</span>
            <em>{{ repo.stars }}</em>
          </a>
          <div v-if="totalAds.length" class="slot-ads">
            <a v-for="ad in totalAds" :key="ad.id" :href="ad.link_url || undefined" target="_blank" rel="noopener">
              <img v-if="ad.image_url" :src="ad.image_url" :alt="ad.title" />
              <span>{{ ad.title }}</span>
            </a>
          </div>
        </section>
      </aside>
    </div>

    <footer class="foot">
      <div class="foot-main">
        <div class="foot-brand">
          <a class="brand" href="/"><img src="/logo.svg" alt="" />NEXA</a>
          <div class="site-search foot-search">
            <input v-model="siteQuery" :placeholder="locale === 'zh' ? '站内搜索' : 'Search this site'" @input="onSiteInput('foot')" @focus="onSiteInput('foot')" />
            <div v-if="siteWhere === 'foot' && siteQuery.trim() && siteHits.length" class="site-hits up">
              <a v-for="hit in siteHits" :key="hit.id" :href="hit.url" target="_blank" rel="noreferrer">
                <strong>{{ hit.title }}</strong>
                <em>{{ hit.tab }} · {{ hit.category }}</em>
              </a>
            </div>
            <p v-else-if="siteWhere === 'foot' && siteQuery.trim()" class="site-hits up empty">{{ locale === "zh" ? "没有匹配的链接" : "No matching links" }}</p>
          </div>
        </div>
        <div class="foot-info">
          <p class="foot-links">
            <a href="/about">{{ t("about") }}</a>
            <a href="/contact">{{ t("contact") }}</a>
          </p>
          <p v-if="contact" class="foot-meta">
            <span v-if="contact.email">{{ contact.email }}</span>
            <span v-if="contact.phone">{{ contact.phone }}</span>
            <a v-if="contact.im" :href="contact.im.includes('t.me') ? contact.im : 'https://t.me/' + contact.im.replace(/^@/, '')" target="_blank" rel="noopener">Telegram {{ contact.im.replace(/^@/, '@') }}</a>
          </p>
        </div>
      </div>
      <a v-if="footerAds.length" class="foot-ad" :href="footerAds[0].link_url || undefined" target="_blank" rel="noopener">
        <img v-if="footerAds[0].image_url" :src="footerAds[0].image_url" :alt="footerAds[0].title" />
      </a>
    </footer>
  </div>
</template>
