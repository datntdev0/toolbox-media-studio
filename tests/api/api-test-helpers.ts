import { expect, type APIRequestContext } from '@playwright/test';

export const API_BASE_URL = process.env.API_BASE_URL ?? 'http://127.0.0.1:8000';
export const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? 'admin@example.com';
export const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? 'SecurePassword123!';

export async function loginAsAdmin(request: APIRequestContext): Promise<string> {
  const response = await request.post('/auth/login', {
    data: {
      email: ADMIN_EMAIL,
      password: ADMIN_PASSWORD,
    },
  });

  await expect(response, 'admin login should succeed').toBeOK();
  const body = (await response.json()) as { access_token: string };
  expect(body.access_token).toBeTruthy();
  return body.access_token;
}
