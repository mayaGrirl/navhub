<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import http from "../api";

const router = useRouter();
const ready = ref(false);

const tree = ref([]);
const categoryId = ref("");
const title = ref("");
const url = ref("");
const description = ref("");
const message = ref("");

onMounted(async () => {
  try {
    await http.get("/auth/me");
  } catch {
    router.replace("/login");
    return;
  }
  ready.value = true;
  const { data } = await http.get("/tree");
  tree.value = data.filter((tab) => tab.kind === "links");
  categoryId.value = tree.value[0]?.categories[0]?.id || "";
});

async function send() {
  message.value = "";
  try {
    const { data } = await http.post("/submissions", {
      category_id: categoryId.value,
      title,
      title_en: title.value,
      title_zh: title.value,
      url: url.value,
      description_en: description.value,
      description_zh: description.value,
    });
    message.value = `Submitted for review. ${data.used}/${data.limit} this month.`;
  } catch (err) {
    message.value = err.response?.data?.detail || "failed";
  }
}
</script>

<template>
  <form v-if="ready" class="page form" @submit.prevent="send">
    <p><a href="/">NEXA</a></p>
    <h1>Submit a link</h1>
    <select v-model="categoryId">
      <optgroup v-for="tab in tree" :key="tab.id" :label="tab.title">
        <option v-for="cat in tab.categories" :key="cat.id" :value="cat.id">{{ cat.title }}</option>
      </optgroup>
    </select>
    <input v-model="title" placeholder="Name" required />
    <input v-model="url" placeholder="https://" required />
    <textarea v-model="description" rows="4" placeholder="Short description"></textarea>
    <button class="primary" type="submit">Submit</button>
    <p>{{ message }}</p>
  </form>
</template>
