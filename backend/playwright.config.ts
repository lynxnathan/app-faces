import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "*.spec.ts",
  workers: 1,
  fullyParallel: false,
  reporter: "list",
  use: {
    locale: "en-US",
    baseURL: "http://127.0.0.1:8791",
    browserName: "firefox",
    viewport: { width: 1440, height: 1000 },
    trace: "off",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run build && node e2e/server.mjs",
    url: "http://127.0.0.1:8791/health",
    reuseExistingServer: false,
  },
  outputDir: "test-results",
});
