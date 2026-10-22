import { test, expect } from '@playwright/test';

if (!['retry', 'final-failure'].includes(process.env.CASE)) for (const key of ['book', 'map']) {
  test(`reads synthetic ${key}`, async ({ request }) => {
    const response = await request.get(`/catalog/${key}`);
    expect(response.status()).toBe(200);
    expect(await response.json()).toEqual({ id: key, synthetic: true });
  });
}

if (process.env.CASE === 'retry') test('synthetic transient response', async ({ request }, testInfo) => {
  const response = await request.get(`/transient?attempt=${testInfo.retry}`);
  expect(response.status()).toBe(200);
});

if (process.env.CASE === 'final-failure') test('synthetic final failure', async ({ request }) => {
  const response = await request.get('/always-fails');
  expect(response.status()).toBe(200);
});
