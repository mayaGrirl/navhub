<template>
  <router-view />
  <button class="to-top" type="button" aria-label="Back to top" @click="scrollTop">
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 14.5 12 8.5l6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>
</template>

<script setup>
function scrollTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}
</script>
