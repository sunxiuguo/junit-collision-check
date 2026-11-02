import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  workers: 2,
  retries: process.env.CASE === 'retry' ? 1 : 0,
  reporter: [['junit', {
    outputFile: process.env.REPORT,
    includeProjectInTestName: process.env.PREFIX === '1',
    includeRetries: true,
  }]],
  projects: [{ name: 'api-one' }, { name: 'api-two' }],
  use: { baseURL: process.env.SYNTHETIC_BASE_URL },
});
