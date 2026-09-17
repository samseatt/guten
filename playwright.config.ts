import { defineConfig } from '@playwright/test';
import path from 'node:path';

if (process.env.GUTEN_ACCEPTANCE_RUN !== '1' || !/^guten_acceptance_test_[a-f0-9]+$/.test(process.env.TEST_DATABASE || '')) {
  throw new Error('Run make acceptance: browser tests must use its disposable database and servers.');
}
for (const key of ['GUTEN_PORTAL_URL', 'GUTEN_SITES_URL', 'GUTEN_API_URL']) {
  const url = new URL(process.env[key] || '');
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || ['3000','3001','8000','8005'].includes(url.port)) {
    throw new Error('Browser tests require isolated loopback ports.');
  }
}
const artifacts = process.env.GUTEN_ACCEPTANCE_ARTIFACTS_DIR!;
export default defineConfig({
  testDir: './tests/acceptance', workers: 1, retries: 0, timeout: 120000,
  expect: { timeout: 20000 },
  outputDir: path.join(artifacts, 'browser-results'),
  reporter: [['list'], ['html', { outputFolder: path.join(artifacts, 'browser-report'), open: 'never' }],
             ['junit', { outputFile: path.join(artifacts, 'browser-results.xml') }]],
  use: { browserName: 'chromium', channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
         baseURL: process.env.GUTEN_PORTAL_URL, headless: true, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
});
