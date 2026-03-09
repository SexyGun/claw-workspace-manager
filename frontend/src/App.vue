<template>
  <n-config-provider :theme="theme">
    <n-message-provider>
      <router-view />
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { darkTheme, NConfigProvider, NMessageProvider } from 'naive-ui'

const theme = darkTheme
</script>

<style>
:root {
  color-scheme: dark;
  font-family: "IBM Plex Sans", "Source Sans 3", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(235, 104, 65, 0.32), transparent 30%),
    radial-gradient(circle at bottom right, rgba(40, 94, 164, 0.28), transparent 35%),
    #0f1726;
  color: #eef2ff;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background: transparent;
}

a {
  color: inherit;
  text-decoration: none;
}
</style>
