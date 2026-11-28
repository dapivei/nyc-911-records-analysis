import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

// The slides use the project's own figures in outputs/figures/ (no copies):
// write them as src="@figures/network/fig6_monthly_relay.png".
const figures = fileURLToPath(new URL('./outputs/figures', import.meta.url))

export default defineConfig({
  resolve: { alias: { '@figures': figures } },
  server: { fs: { allow: ['..'] } },      // let the dev server read the repo root
})
