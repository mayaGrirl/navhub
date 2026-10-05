<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import http from "../api";

const props = defineProps({ mode: String });
const router = useRouter();
const email = ref("");
const password = ref("");
const totp = ref("");
const error = ref("");

async function send() {
  error.value = "";
  try {
    const path = props.mode === "register" ? "/auth/register" : "/auth/login";
    await http.post(path, { email: email.value, password: password.value, totp: totp.value });
    router.push("/");
  } catch (err) {
    error.value = err.response?.data?.detail || "failed";
  }
}
</script>

<template>
  <form class="page form" @submit.prevent="send">
    <p><a href="/">Nav</a></p>
    <h1>{{ mode === "register" ? "Register" : "Log in" }}</h1>
    <input v-model="email" type="email" placeholder="Email" required />
    <input v-model="password" type="password" placeholder="Password" required />
    <input v-if="mode === 'login'" v-model="totp" placeholder="Authenticator code, if enabled" />
    <button class="primary" type="submit">{{ mode === "register" ? "Create account" : "Log in" }}</button>
    <p v-if="error">{{ error }}</p>
  </form>
</template>
