import { randomUUID } from 'node:crypto';

import { expect, test } from '@playwright/test';

import { ADMIN_EMAIL, loginAsAdmin } from './api-test-helpers';

test.describe('/api/users CRUD', () => {
  test('creates, reads, updates, lists, and deletes a user', async ({ request }) => {
    const token = await loginAsAdmin(request);
    const headers = {
      Authorization: `Bearer ${token}`,
    };
    const uniqueEmail = `playwright-${randomUUID()}@example.com`;

    const createdResponse = await request.post('/api/users', {
      headers,
      data: {
        email: uniqueEmail,
        password: 'member-password',
        displayName: 'Playwright Member',
        role: 'member',
        status: 'active',
      },
    });
    expect(createdResponse.status()).toBe(201);
    const created = (await createdResponse.json()) as {
      id: string;
      email: string;
      displayName: string;
      role: string;
      status: string;
      etag: string;
    };
    expect(created.email).toBe(uniqueEmail);
    expect(created.displayName).toBe('Playwright Member');
    expect(created.role).toBe('member');
    expect(created.status).toBe('active');
    expect(created.id).toBeTruthy();
    expect(created.etag).toBeTruthy();

    const fetchedResponse = await request.get(`/api/users/${created.id}`, {
      headers,
    });
    expect(fetchedResponse.status()).toBe(200);
    const fetched = (await fetchedResponse.json()) as {
      id: string;
      email: string;
      displayName: string;
      status: string;
      etag: string;
    };
    expect(fetched.id).toBe(created.id);
    expect(fetched.email).toBe(uniqueEmail);
    expect(fetched.displayName).toBe('Playwright Member');
    expect(fetched.status).toBe('active');

    const updatedResponse = await request.patch(`/api/users/${created.id}`, {
      headers: {
        ...headers,
        'If-Match': created.etag,
      },
      data: {
        displayName: 'Updated Playwright Member',
        status: 'inactive',
      },
    });
    expect(updatedResponse.status()).toBe(200);
    const updated = (await updatedResponse.json()) as {
      id: string;
      email: string;
      displayName: string;
      status: string;
      etag: string;
    };
    expect(updated.id).toBe(created.id);
    expect(updated.displayName).toBe('Updated Playwright Member');
    expect(updated.status).toBe('inactive');
    expect(updated.etag).toBeTruthy();
    expect(updated.etag).not.toBe(created.etag);

    const listResponse = await request.get('/api/users?limit=100', {
      headers,
    });
    expect(listResponse.status()).toBe(200);
    const list = (await listResponse.json()) as {
      items: Array<{
        id: string;
        email: string;
        displayName: string | null;
        status: string;
      }>;
      continuationToken: string | null;
    };
    const listedUser = list.items.find((item) => item.id === created.id);
    expect(listedUser).toBeTruthy();
    expect(listedUser?.email).toBe(uniqueEmail);
    expect(listedUser?.displayName).toBe('Updated Playwright Member');
    expect(listedUser?.status).toBe('inactive');
    expect(list.items.some((item) => item.email === ADMIN_EMAIL)).toBeTruthy();
    expect(list.continuationToken).toBeNull();

    const deletedResponse = await request.delete(`/api/users/${created.id}`, {
      headers: {
        ...headers,
        'If-Match': updated.etag,
      },
    });
    expect(deletedResponse.status()).toBe(204);

    const missingResponse = await request.get(`/api/users/${created.id}`, {
      headers,
    });
    expect(missingResponse.status()).toBe(404);
  });
});
