import { defineConfig, devices } from "@playwright/test";

const python = process.env.CONNECTHUB_PYTHON ?? (process.platform === "win32" ? '"..\\.venv\\Scripts\\python.exe"' : "python");
const postgresPath = process.platform === "win32"
  ? `C:\\Program Files\\PostgreSQL\\18\\bin;${process.env.PATH ?? ""}`
  : (process.env.PATH ?? "");

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  outputDir: "test-results",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    ...devices["Desktop Chrome"],
    channel: process.platform === "win32" ? "chrome" : undefined,
  },
  webServer: [
    {
      command: `${python} scripts/e2e_server.py`,
      cwd: "../backend",
      url: "http://127.0.0.1:18000/health/ready",
      timeout: 60_000,
      reuseExistingServer: false,
      env: { ...process.env, PSYCOPG_IMPL: "python", PATH: postgresPath },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174 --strictPort",
      url: "http://127.0.0.1:5174",
      timeout: 60_000,
      reuseExistingServer: false,
      env: { ...process.env, CONNECTHUB_BACKEND_TARGET: "http://127.0.0.1:18000" },
    },
  ],
});
