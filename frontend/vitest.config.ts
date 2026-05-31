import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Unit/integration tests for the SPA. Uses jsdom so hooks that touch
// window/localStorage/fetch run without a browser.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
