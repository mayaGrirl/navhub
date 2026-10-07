<script setup>
import { onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import http from "../api";

const props = defineProps({ pageKey: String });
const { locale } = useI18n();
const page = ref(null);
const ads = ref([]);
const slots = {
  about: ["about-1", "about-2", "about-3"],
  contact: ["contact-1", "contact-2", "contact-3"],
};

async function load() {
  const [{ data }, adRes] = await Promise.all([
    http.get(`/pages/${props.pageKey}`, { params: { locale: locale.value } }),
    http.get("/ads", { params: { locale: locale.value } }),
  ]);
  page.value = data;
  const wanted = slots[props.pageKey] || [];
  ads.value = adRes.data.filter((item) => wanted.includes(item.slot));
}

watch(locale, load);
onMounted(load);
</script>

<template>
  <div class="doc" v-if="page">
    <article class="page">
      <a class="brand" href="/"><img src="/logo.svg" alt="" />NEXA</a>
      <h1>{{ page.title }}</h1>
      <p class="prose">{{ page.body }}</p>
      <ul class="contacts" v-if="page.email || page.phone || page.im || page.address">
        <li v-if="page.email">{{ page.email }}</li>
        <li v-if="page.phone">{{ page.phone }}</li>
        <li v-if="page.im">{{ page.im }}</li>
        <li v-if="page.address">{{ page.address }}</li>
      </ul>
    </article>
    <aside v-if="ads.length" class="doc-ads">
      <a v-for="ad in ads" :key="ad.id" :href="ad.link_url || undefined" target="_blank" rel="noopener">
        <img v-if="ad.image_url" :src="ad.image_url" :alt="ad.title" loading="lazy" decoding="async" />
        <b v-if="!ad.image_url || ad.image_url.endsWith('ad-placeholder.svg')" class="ad-no">{{ ad.no }}</b>
        <span>{{ ad.title }}</span>
      </a>
    </aside>
  </div>
</template>
