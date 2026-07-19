import { expect, test } from '@playwright/test';

test.describe('/health', () => {
  test('returns Azure dependency health statuses', async ({ request }) => {
    const response = await request.get('/health');

    expect(response.status()).toBe(200);
    const body = (await response.json()) as {
      azCosmosDb: string;
      azStorageBlob: string;
      azStorageQueue: string;
    };

    expect(['ok', 'error']).toContain(body.azCosmosDb);
    expect(['ok', 'error']).toContain(body.azStorageBlob);
    expect(['ok', 'error']).toContain(body.azStorageQueue);
  });
});
