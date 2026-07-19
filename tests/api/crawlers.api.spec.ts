import { expect, test } from '@playwright/test';

import { loginAsAdmin } from './api-test-helpers';

test.describe('/api/crawlers', () => {
  test('lists supported crawler sources', async ({ request }) => {
    const response = await request.get('/api/crawlers');

    expect(response.status()).toBe(200);
    expect(await response.json()).toEqual({
      items: [
        {
          id: 'novel543',
          name: 'Novel543',
          hosts: ['www.novel543.com'],
          metadataSupported: true,
        },
      ],
    });
  });

  test('requires authentication before fetching metadata', async ({ request }) => {
    const response = await request.get(
      '/api/crawlers/novel543/metadata?url=https://www.novel543.com/0603625457/dir',
    );

    expect(response.status()).toBe(401);
  });

  test('returns 404 for an unknown crawler id', async ({ request }) => {
    const token = await loginAsAdmin(request);

    const response = await request.get(
      '/api/crawlers/unknown/metadata?url=https://www.novel543.com/0603625457/dir',
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    expect(response.status()).toBe(404);
    expect(await response.json()).toEqual({
      detail: 'Crawler not found',
    });
  });

  test('validates Novel543 source URLs before fetching metadata', async ({ request }) => {
    const token = await loginAsAdmin(request);

    const response = await request.get(
      '/api/crawlers/novel543/metadata?url=https://example.com/0603625457/dir',
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    expect(response.status()).toBe(422);
    expect(await response.json()).toEqual({
      detail: 'Novel543 URLs must use an allowed host',
    });
  });

  test('requires authentication before fetching chapter content', async ({ request }) => {
    const response = await request.get(
      '/api/crawlers/novel543/chapter?url=https://www.novel543.com/0603625457/8096_1.html',
    );

    expect(response.status()).toBe(401);
  });

  test('returns 404 for an unknown crawler id before fetching chapter content', async ({
    request,
  }) => {
    const token = await loginAsAdmin(request);

    const response = await request.get(
      '/api/crawlers/unknown/chapter?url=https://www.novel543.com/0603625457/8096_1.html',
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    expect(response.status()).toBe(404);
    expect(await response.json()).toEqual({
      detail: 'Crawler not found',
    });
  });

  test('validates Novel543 chapter URLs before fetching chapter content', async ({ request }) => {
    const token = await loginAsAdmin(request);

    const response = await request.get(
      '/api/crawlers/novel543/chapter?url=https://example.com/0603625457/8096_1.html',
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    expect(response.status()).toBe(422);
    expect(await response.json()).toEqual({
      detail: 'Novel543 URLs must use an allowed host',
    });
  });
});
