import { expect, test } from '@playwright/test';

import { loginAsAdmin } from './api-test-helpers';

test.describe('/api/translations CRUD', () => {
  test('creates duplicate translations and persists AI configuration', async ({ request }) => {
    const token = await loginAsAdmin(request);
    const headers = { Authorization: `Bearer ${token}` };

    const novelResponse = await request.post('/api/novels', {
      headers,
      data: {
        title: 'Translation API Novel',
        language: 'zh',
      },
    });
    expect(novelResponse.status()).toBe(201);
    const novel = (await novelResponse.json()) as { id: string };
    const requestBody = {
      name: 'Vietnamese translation',
      novelId: novel.id,
      targetLanguage: 'vi',
    };

    const createdResponse = await request.post('/api/translations', {
      headers,
      data: requestBody,
    });
    const duplicateResponse = await request.post('/api/translations', {
      headers,
      data: requestBody,
    });
    expect(createdResponse.status()).toBe(201);
    expect(duplicateResponse.status()).toBe(201);
    const created = (await createdResponse.json()) as {
      id: string;
      etag: string;
      novel: { title: string };
      configuration: null;
    };
    const duplicate = (await duplicateResponse.json()) as { id: string };
    expect(duplicate.id).not.toBe(created.id);
    expect(created.novel.title).toBe('Translation API Novel');
    expect(created.configuration).toBeNull();

    const configuration = {
      providerId: 'openai',
      modelId: 'gpt-5-mini',
      globalPrompt: 'Translate the chapter faithfully.',
    };
    const updatedResponse = await request.put(`/api/translations/${created.id}`, {
      headers,
      data: {
        name: 'English translation',
        novelId: novel.id,
        targetLanguage: 'en',
        configuration,
        etag: created.etag,
      },
    });
    expect(updatedResponse.status()).toBe(200);
    const updated = (await updatedResponse.json()) as {
      name: string;
      targetLanguage: string;
      status: string;
      configuration: typeof configuration;
    };
    expect(updated.name).toBe('English translation');
    expect(updated.targetLanguage).toBe('en');
    expect(updated.status).toBe('ready');
    expect(updated.configuration).toEqual(configuration);

    const fetchedResponse = await request.get(`/api/translations/${created.id}`, {
      headers,
    });
    expect(fetchedResponse.status()).toBe(200);
    expect((await fetchedResponse.json()).configuration).toEqual(configuration);

    const listedResponse = await request.get('/api/translations', { headers });
    expect(listedResponse.status()).toBe(200);
    const listed = (await listedResponse.json()) as {
      items: Array<{ id: string; configuration: typeof configuration | null }>;
    };
    expect(listed.items.find((item) => item.id === created.id)?.configuration).toEqual(
      configuration,
    );

    expect(
      (await request.delete(`/api/translations/${created.id}`, { headers })).status(),
    ).toBe(204);
    expect(
      (await request.delete(`/api/translations/${duplicate.id}`, { headers })).status(),
    ).toBe(204);
    expect((await request.delete(`/api/novels/${novel.id}`, { headers })).status()).toBe(204);
  });
});
