<script setup>
import { onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import http from "../api";

const props = defineProps({ pageKey: String });
const { locale } = useI18n();
const page = ref(null);

async function load() {
  const { data } = await http.get(`/pages/${props.pageKey}`, { params: { locale: locale.value } });
  page.value = data;
}

watch(locale, load);
onMounted(load);
</script>

<template>
  <article class="page" v-if="page">
    <p><a href="/">Nav</a></p>
    <h1>{{ page.title }}</h1>
    <p>{{ page.body }}</p>
    <p v-if="page.email">{{ page.email }}</p>
    <p v-if="page.phone">{{ page.phone }}</p>
    <p v-if="page.im">{{ page.im }}</p>
    <p v-if="page.address">{{ page.address }}</p>
  </article>
</template>
