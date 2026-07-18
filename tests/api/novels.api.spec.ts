import { expect, test } from '@playwright/test';

import { loginAsAdmin } from './api-test-helpers';

test.describe('/api/novels CRUD', () => {
  test('creates, reads, updates, lists, and deletes a novel', async ({ request }) => {
    const token = await loginAsAdmin(request);
    const headers = {
      Authorization: `Bearer ${token}`,
    };

    const createdResponse = await request.post('/api/novels', {
      headers,
      data: {
        title: 'Playwright Novel',
        description: 'Novel created from API spec test',
        coverImageUrl: 'https://example.com/novel-cover.jpg',
        language: 'en',
        author: 'Playwright Author',
        tags: ['playwright', 'api'],
        notes: 'Created by Playwright API spec',
      },
    });
    expect(createdResponse.status()).toBe(201);
    const created = (await createdResponse.json()) as {
      id: string;
      title: string;
      description: string | null;
      coverImageUrl: string | null;
      language: string | null;
      author: string | null;
      tags: string[];
      notes: string | null;
      status: string;
      etag: string;
    };
    expect(created.id).toBeTruthy();
    expect(created.title).toBe('Playwright Novel');
    expect(created.description).toBe('Novel created from API spec test');
    expect(created.coverImageUrl).toBe('https://example.com/novel-cover.jpg');
    expect(created.language).toBe('en');
    expect(created.author).toBe('Playwright Author');
    expect(created.tags).toEqual(['playwright', 'api']);
    expect(created.notes).toBe('Created by Playwright API spec');
    expect(created.status).toBe('draft');
    expect(created.etag).toBeTruthy();

    const fetchedResponse = await request.get(`/api/novels/${created.id}`, {
      headers,
    });
    expect(fetchedResponse.status()).toBe(200);
    const fetched = (await fetchedResponse.json()) as {
      id: string;
      title: string;
      author: string | null;
      status: string;
      etag: string;
    };
    expect(fetched.id).toBe(created.id);
    expect(fetched.title).toBe('Playwright Novel');
    expect(fetched.author).toBe('Playwright Author');
    expect(fetched.status).toBe('draft');

    const updatedResponse = await request.patch(`/api/novels/${created.id}`, {
      headers,
      data: {
        title: 'Updated Playwright Novel',
        notes: 'Updated by Playwright API spec',
        status: 'active',
        etag: created.etag,
      },
    });
    expect(updatedResponse.status()).toBe(200);
    const updated = (await updatedResponse.json()) as {
      id: string;
      title: string;
      notes: string | null;
      status: string;
      etag: string;
    };
    expect(updated.id).toBe(created.id);
    expect(updated.title).toBe('Updated Playwright Novel');
    expect(updated.notes).toBe('Updated by Playwright API spec');
    expect(updated.status).toBe('active');
    expect(updated.etag).toBeTruthy();
    expect(updated.etag).not.toBe(created.etag);

    const listResponse = await request.get('/api/novels?limit=100', {
      headers,
    });
    expect(listResponse.status()).toBe(200);
    const list = (await listResponse.json()) as {
      items: Array<{
        id: string;
        title: string;
        author: string | null;
        status: string;
      }>;
      continuationToken: string | null;
    };
    const listedNovel = list.items.find((item) => item.id === created.id);
    expect(listedNovel).toBeTruthy();
    expect(listedNovel?.title).toBe('Updated Playwright Novel');
    expect(listedNovel?.author).toBe('Playwright Author');
    expect(listedNovel?.status).toBe('active');
    expect(list.continuationToken).toBeNull();

    const deletedResponse = await request.delete(`/api/novels/${created.id}`, {
      headers,
    });
    expect(deletedResponse.status()).toBe(204);

    const missingResponse = await request.get(`/api/novels/${created.id}`, {
      headers,
    });
    expect(missingResponse.status()).toBe(404);
  });
});
