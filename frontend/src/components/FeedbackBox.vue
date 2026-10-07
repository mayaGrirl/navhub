<script setup>
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import http from "../api";

const props = defineProps({ inline: Boolean, loggedIn: { type: Boolean, default: true } });
const { locale } = useI18n();
const zh = () => String(locale.value).startsWith("zh");
const open = ref(false);
const list = ref([]);
const current = ref(null);
const title = ref("");
const body = ref("");
const file = ref(null);
const preview = ref("");
const reply = ref("");
const notice = ref("");
const fileInput = ref(null);
const statusText = {
  pending: ["待处理", "Open"],
  working: ["处理中", "In progress"],
  done: ["已完成", "Done"],
  rejected: ["拒绝", "Rejected"],
  closed: ["关闭", "Closed"],
};

function openMine() {
  const next = "/submit?tab=feedback";
  if (!props.loggedIn) {
    window.location.href = `/login?next=${encodeURIComponent(next)}`;
    return;
  }
  window.location.href = next;
}
function goLogin() {
  const next = window.location.pathname + window.location.search;
  window.location.href = `/login?next=${encodeURIComponent(next)}`;
}
async function load() {
  if (!props.loggedIn) return;
  const { data } = await http.get("/feedback");
  list.value = Array.isArray(data) ? data : [];
}
async function show(id) {
  current.value = (await http.get(`/feedback/${id}`)).data;
  reply.value = "";
}
async function openBox() {
  if (!props.loggedIn) {
    goLogin();
    return;
  }
  open.value = true;
  notice.value = "";
  await load();
}
function pickFile(event) {
  const chosen = event.target.files?.[0] || null;
  file.value = chosen;
  preview.value = "";
  if (!chosen) return;
  if (!chosen.type.startsWith("image/") || chosen.size > 2 * 1024 * 1024) {
    file.value = null;
    event.target.value = "";
    notice.value = zh() ? "请选择 2MB 以内的图片" : "Use an image under 2MB";
    return;
  }
  preview.value = URL.createObjectURL(chosen);
}
function clearFile() {
  file.value = null;
  preview.value = "";
  if (fileInput.value) fileInput.value.value = "";
}
async function submit() {
  if (!props.loggedIn) {
    goLogin();
    return;
  }
  notice.value = "";
  const form = new FormData();
  form.append("title", title.value.trim());
  form.append("body", body.value.trim());
  if (file.value) form.append("file", file.value);
  try {
    current.value = (await http.post("/feedback", form)).data;
    title.value = "";
    body.value = "";
    clearFile();
    notice.value = zh() ? "已提交" : "Sent";
    await load();
    open.value = false;
  } catch (err) {
    if (err.response?.status === 401) {
      goLogin();
      return;
    }
    notice.value = err.response?.data?.detail || (zh() ? "提交失败" : "Could not send");
  }
}
async function sendReply() {
  if (!props.loggedIn || !current.value || !reply.value.trim()) return;
  current.value = (await http.post(`/feedback/${current.value.id}/reply`, { body: reply.value })).data;
  reply.value = "";
  await load();
}
function label(status) {
  const pair = statusText[status] || statusText.pending;
  return zh() ? pair[0] : pair[1];
}

onMounted(() => { if (props.inline && props.loggedIn) load(); });
</script>

<template>
  <button v-if="!inline" class="text-btn" type="button" @click="openBox">{{ zh() ? "网站反馈" : "Feedback" }}</button>
  <section v-if="inline" class="feedback-records">
    <header>
      <strong>{{ zh() ? "我的反馈" : "My feedback" }}</strong>
      <button class="primary" type="button" @click="openBox">{{ zh() ? "提交反馈" : "New feedback" }}</button>
    </header>
    <button v-for="row in list" :key="row.id" type="button" class="ticket-row" :class="{ on: current && current.id === row.id }" @click="show(row.id)">
      <span>
        <b>{{ row.title }}</b>
        <small>{{ zh() ? "提交" : "Sent" }} {{ (row.created_at || "").slice(0, 16).replace("T", " ") }} · {{ zh() ? "更新" : "Updated" }} {{ (row.updated_at || row.created_at || "").slice(0, 16).replace("T", " ") }}</small>
      </span>
      <em :class="row.status">{{ label(row.status) }}</em>
    </button>
    <p v-if="!list.length" class="meta">{{ zh() ? "还没有反馈" : "No tickets yet" }}</p>
    <article v-if="current" class="ticket-detail">
      <h3>{{ current.title }}</h3>
      <p>{{ current.body }}</p>
      <img v-if="current.image_url" :src="current.image_url" alt="" />
      <div v-for="note in current.notes" :key="note.id" class="ticket-note" :class="note.role">
        <b>{{ note.role === "admin" ? (zh() ? "管理员" : "Admin") : (zh() ? "我" : "Me") }}</b>
        <span>{{ (note.created_at || "").slice(0, 16).replace("T", " ") }}</span>
        <p>{{ note.body }}</p>
      </div>
      <textarea v-model="reply" rows="3" :placeholder="zh() ? '补充说明' : 'Add a reply'"></textarea>
      <button type="button" class="primary" @click="sendReply">{{ zh() ? "回复" : "Reply" }}</button>
    </article>
  </section>
  <Teleport to="body">
  <section v-if="open" class="feedback-panel pop" @click.self="open = false">
    <div class="feedback-card">
      <header>
        <strong>{{ zh() ? "网站反馈" : "Feedback" }}</strong>
        <button type="button" class="popup-x" :aria-label="zh() ? '关闭' : 'Close'" @click="open = false">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        </button>
      </header>
      <form class="feedback-form" @submit.prevent="submit">
        <label>{{ zh() ? "标题" : "Title" }}<input v-model="title" maxlength="160" :placeholder="zh() ? '用一句话说明问题' : 'One line about the issue'" required /></label>
        <label>{{ zh() ? "内容" : "Message" }}<textarea v-model="body" rows="5" :placeholder="zh() ? '发生了什么，希望怎么处理' : 'What happened, and what should change'" required></textarea></label>
        <div class="upload-tile" :class="{ filled: preview }">
          <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp" @change="pickFile" />
          <img v-if="preview" :src="preview" alt="" />
          <span v-else>{{ zh() ? "上传图片" : "Add an image" }}<small>{{ zh() ? "PNG、JPG、GIF、WEBP，不超过 2MB" : "PNG, JPG, GIF or WEBP, up to 2MB" }}</small></span>
          <button v-if="preview" type="button" @click.stop.prevent="clearFile">{{ zh() ? "移除" : "Remove" }}</button>
        </div>
        <button class="primary" type="submit">{{ zh() ? "提交反馈" : "Send feedback" }}</button>
        <button v-if="!inline" class="text-btn mine-link" type="button" @click="openMine">{{ zh() ? "查看我的反馈" : "View my feedback" }}</button>
        <p v-if="notice" class="feedback-notice">{{ notice }}</p>
      </form>
    </div>
  </section>
  </Teleport>
</template>
