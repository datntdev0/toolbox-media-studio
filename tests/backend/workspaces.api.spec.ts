import { expect, test } from '@playwright/test';

import { loginAsAdmin } from './api-test-helpers';

test.describe('/api/workspaces CRUD', () => {
  test('creates duplicate workspaces and updates their values', async ({ request }) => {
    const token = await loginAsAdmin(request);
    const headers = { Authorization: `Bearer ${token}` };

    const novelResponse = await request.post('/api/novels', {
      headers,
      data: {
        title: 'Workspace API Novel',
        language: 'zh',
      },
    });
    expect(novelResponse.status()).toBe(201);
    const novel = (await novelResponse.json()) as { id: string };
    const requestBody = {
      name: 'Vietnamese workspace',
      kind: 'translation',
      novelId: novel.id,
      targetLanguage: 'vi',
    };

    const createdResponse = await request.post('/api/workspaces', {
      headers,
      data: requestBody,
    });
    const duplicateResponse = await request.post('/api/workspaces', {
      headers,
      data: requestBody,
    });
    expect(createdResponse.status()).toBe(201);
    expect(duplicateResponse.status()).toBe(201);
    const created = (await createdResponse.json()) as {
      id: string;
      etag: string;
      novel: { title: string };
    };
    const duplicate = (await duplicateResponse.json()) as { id: string };
    expect(duplicate.id).not.toBe(created.id);
    expect(created.novel.title).toBe('Workspace API Novel');

    const updatedResponse = await request.put(`/api/workspaces/${created.id}`, {
      headers,
      data: {
        name: 'English workspace',
        novelId: novel.id,
        targetLanguage: 'en',
        etag: created.etag,
      },
    });
    expect(updatedResponse.status()).toBe(200);
    const updated = (await updatedResponse.json()) as {
      name: string;
      targetLanguage: string;
    };
    expect(updated.name).toBe('English workspace');
    expect(updated.targetLanguage).toBe('en');

    const listedResponse = await request.get('/api/workspaces?kind=translation', {
      headers,
    });
    expect(listedResponse.status()).toBe(200);
    const listed = (await listedResponse.json()) as {
      items: Array<{ id: string }>;
    };
    expect(listed.items.some((item) => item.id === created.id)).toBeTruthy();

    expect(
      (await request.delete(`/api/workspaces/${created.id}`, { headers })).status(),
    ).toBe(204);
    expect(
      (await request.delete(`/api/workspaces/${duplicate.id}`, { headers })).status(),
    ).toBe(204);
    expect((await request.delete(`/api/novels/${novel.id}`, { headers })).status()).toBe(204);
  });
});
