import { expect, test } from '@playwright/test';

import { loginAsAdmin } from './api-test-helpers';

test.describe('/api/workspaces CRUD', () => {
  test('creates and updates an audio workspace with an original language', async ({ request }) => {
    const token = await loginAsAdmin(request);
    const headers = { Authorization: `Bearer ${token}` };
    const novelResponse = await request.post('/api/novels', {
      headers,
      data: {
        title: 'Audio workspace API novel',
        language: 'en',
      },
    });
    expect(novelResponse.status()).toBe(201);
    const novel = (await novelResponse.json()) as { id: string };

    const languagesResponse = await request.get(`/api/novels/${novel.id}/languages`, {
      headers,
    });
    expect(languagesResponse.status()).toBe(200);
    expect(await languagesResponse.json()).toEqual({
      items: [{ code: 'en', sourceType: 'original' }],
    });

    const missingChapterResponse = await request.get(
      `/api/novels/${novel.id}/chapters/missing?language=en`,
      { headers },
    );
    expect(missingChapterResponse.status()).toBe(404);

    const createdResponse = await request.post('/api/workspaces', {
      headers,
      data: {
        title: 'English audio',
        type: 'audio',
        novelId: novel.id,
        language: 'en',
      },
    });
    expect(createdResponse.status()).toBe(201);
    const workspace = (await createdResponse.json()) as {
      id: string;
      title: string;
      sourceType: string;
    };
    expect(workspace.sourceType).toBe('original');

    const listedResponse = await request.get('/api/workspaces?type=audio', { headers });
    expect(listedResponse.status()).toBe(200);
    expect(
      ((await listedResponse.json()) as { items: Array<{ id: string }> }).items
        .some((item) => item.id === workspace.id),
    ).toBe(true);

    const updatedResponse = await request.put(`/api/workspaces/${workspace.id}`, {
      headers,
      data: { title: 'Updated English audio' },
    });
    expect(updatedResponse.status()).toBe(200);
    expect(((await updatedResponse.json()) as { title: string }).title)
      .toBe('Updated English audio');

    expect(
      (await request.delete(`/api/workspaces/${workspace.id}`, { headers })).status(),
    ).toBe(204);
    expect((await request.delete(`/api/novels/${novel.id}`, { headers })).status()).toBe(204);
  });
});
