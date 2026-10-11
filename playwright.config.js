// SentiCall v3 — Playwright End-to-End Test Configuration
const { defineConfig, devices } = require('@playwright/test');
const path = require('path');

const fakeAudioFile = path.resolve(__dirname, 'tests', 'test_scam_16k.wav');

module.exports = defineConfig({
  testDir: './tests',
  testMatch: /.*\.spec\.js/,
  timeout: 45000,
  expect: {
    timeout: 10000
  },
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
    permissions: ['microphone'],
    launchOptions: {
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        `--use-file-for-fake-audio-capture=${fakeAudioFile}`
      ]
    }
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    }
  ],
  webServer: {
    command: 'python run_server.py',
    url: 'http://127.0.0.1:8000/healthz',
    reuseExistingServer: false,
    timeout: 30000
  }
});
