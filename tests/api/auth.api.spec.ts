import { expect, test } from '@playwright/test';

import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAsAdmin } from './api-test-helpers';

test.describe('auth/login', () => {
  test('returns a bearer token for the seeded admin user', async ({ request }) => {
    const response = await request.post('/auth/login', {
      data: {
        email: ADMIN_EMAIL,
        password: ADMIN_PASSWORD,
      },
    });

    expect(response.status()).toBe(200);
    const body = (await response.json()) as {
      access_token: string;
      token_type: string;
    };
    expect(body.token_type).toBe('bearer');
    expect(body.access_token).toBeTruthy();
  });
});

test.describe('auth/me', () => {
  test('returns the current admin profile for a valid bearer token', async ({ request }) => {
    const token = await loginAsAdmin(request);

    const response = await request.get('/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    expect(response.status()).toBe(200);
    const body = (await response.json()) as {
      email: string;
      displayName: string;
      role: string;
      status: string;
    };
    expect(body.email).toBe(ADMIN_EMAIL);
    expect(body.displayName).toBe('Admin');
    expect(body.role).toBe('admin');
    expect(body.status).toBe('active');
  });
});
