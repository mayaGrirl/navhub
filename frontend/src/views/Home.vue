<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import http from "../api";

const { t, locale } = useI18n();
const tabs = ref([]);
const tabId = ref(null);
const sections = ref([]);
const news = ref([]);
const notes = ref([]);
const ranks = ref([]);
const contact = ref(null);
const user = ref(null);
const period = ref("past_24_hours");
const activeSection = ref(null);
const adultOk = ref(sessionStorage.getItem("adult-ok") === "1");

const currentTab = computed(() => tabs.value.find((item) => item.id === tabId.value));
const isHome = computed(() => !currentTab.value || currentTab.value.kind === "home");

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
  const { data } = await http.get("/github", { params: { period: next } });
  ranks.value = Array.isArray(data) ? data : [];
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

watch(tabId, loadBoard);
watch(locale, async () => {
  await loadTree();
  await loadBoard();
});

onMounted(async () => {
  const [tree, noteRes, newsRes, contactRes, me] = await Promise.allSettled([
    http.get("/tree", { params: { locale: locale.value } }),
    http.get("/announcements", { params: { locale: locale.value } }),
    http.get("/news"),
    http.get("/pages/contact", { params: { locale: locale.value } }),
    http.get("/auth/me"),
  ]);
  if (tree.status === "fulfilled") {
    tabs.value = tree.value.data;
    tabId.value = tabs.value.find((item) => item.kind === "home")?.id || tabs.value[0]?.id || null;
  }
  if (noteRes.status === "fulfilled") notes.value = noteRes.value.data;
  if (newsRes.status === "fulfilled") news.value = newsRes.value.data;
  if (contactRes.status === "fulfilled") contact.value = contactRes.value.data;
  if (me.status === "fulfilled") user.value = me.value.data;
  loadRanks("past_24_hours");
});
</script>

<template>
  <div class="shell">
    <header class="top">
      <a class="brand" href="/"><i>N</i>Nav</a>
      <nav class="tabs">
        <button v-for="tab in tabs" :key="tab.id" :class="{ active: tab.id === tabId }" @click="pickTab(tab.id)">
          {{ tab.title }}
        </button>
      </nav>
      <div class="nav-links">
        <a href="/about">{{ t("about") }}</a>
        <a href="/advertise">{{ t("ads") }}</a>
        <a href="/contact">{{ t("contact") }}</a>
        <a href="/submit">{{ t("submit") }}</a>
        <button class="text-btn" @click="setLocale(locale === 'en' ? 'zh' : 'en')">{{ locale === "en" ? "中文" : "EN" }}</button>
        <a v-if="!user" href="/login">{{ t("login") }}</a>
        <button v-else class="text-btn" @click="logout">{{ t("logout") }}</button>
      </div>
    </header>

    <div class="portal">
      <aside class="panel side-jump">
        <template v-if="isHome">
          <h2>{{ locale === "zh" ? "系统消息" : "Notices" }}</h2>
          <article v-for="note in notes" :key="note.id" class="note">
            <strong>{{ note.title }}</strong>
            <p>{{ note.body }}</p>
          </article>
          <p v-if="!notes.length" class="meta">{{ locale === "zh" ? "暂无消息" : "No notices" }}</p>
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
          <h2>{{ locale === "zh" ? "资讯" : "News" }}</h2>
          <a class="story" v-for="item in news" :key="item.id" :href="item.url" target="_blank" rel="noreferrer">
            <h3>{{ item.title }}</h3>
            <p class="meta">{{ item.source }}<span v-if="item.published_at"> · {{ item.published_at.slice(0, 16).replace("T", " ") }}</span></p>
            <p v-if="item.summary">{{ item.summary.replace(/<[^>]+>/g, "").slice(0, 140) }}</p>
          </a>
          <p v-if="!news.length" class="meta">{{ locale === "zh" ? "还没有资讯" : "No stories yet" }}</p>
        </template>
        <template v-else>
          <section v-for="section in sections" :key="section.id" :id="`cat-${section.id}`" class="group">
            <h2>{{ section.title }}</h2>
            <div class="grid">
              <a class="card" v-for="link in section.links" :key="link.id" :href="link.url" target="_blank" rel="noreferrer">
                <img v-if="link.logo_url" class="logo" :src="link.logo_url" alt="" />
                <div v-else class="fallback">{{ link.title.slice(0, 1) }}</div>
                <div>
                  <h3>{{ link.title }}</h3>
                  <p>{{ link.description }}</p>
                </div>
              </a>
            </div>
          </section>
        </template>
      </main>

      <aside class="panel">
        <h2>GitHub</h2>
        <div class="rank-switch">
          <button :class="{ on: period === 'past_24_hours' }" @click="loadRanks('past_24_hours')">24h</button>
          <button :class="{ on: period === 'past_week' }" @click="loadRanks('past_week')">{{ locale === "zh" ? "周" : "Week" }}</button>
          <button :class="{ on: period === 'past_month' }" @click="loadRanks('past_month')">{{ locale === "zh" ? "月" : "Month" }}</button>
        </div>
        <a class="rank" v-for="(repo, index) in ranks.slice(0, 12)" :key="repo.repo_name || index" :href="`https://github.com/${repo.repo_name}`" target="_blank">
          <b>{{ index + 1 }}</b>
          <span>{{ repo.repo_name }}</span>
          <em>+{{ repo.stars }}</em>
        </a>
      </aside>
    </div>

    <footer class="foot" v-if="contact">
      <span v-if="contact.email">{{ contact.email }}</span>
      <span v-if="contact.phone"> · {{ contact.phone }}</span>
      <span v-if="contact.im"> · {{ contact.im }}</span>
    </footer>
  </div>
</template>
