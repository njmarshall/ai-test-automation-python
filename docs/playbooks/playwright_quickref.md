# Playwright Quick Reference

> Fast-recall cheatsheet for Senior SDET / Automation Architects  
> Framework: `@playwright/test` · TypeScript · v1.40+

---

## Table of Contents
- [Setup & Config](#setup--config)
- [Core API](#core-api)
- [Locators](#locators)
- [Assertions](#assertions)
- [Waiting Strategies](#waiting-strategies)
- [Page Object Model](#page-object-model)
- [Custom Fixtures](#custom-fixtures)
- [Auth & storageState](#auth--storagestate)
- [API Testing](#api-testing)
- [Network Mocking](#network-mocking)
- [Advanced Patterns](#advanced-patterns)
- [Gotchas](#gotchas)

---

## Setup & Config

```bash
# New project
npm init playwright@latest

# Add to existing project
npm i -D @playwright/test
npx playwright install
```

### `playwright.config.ts` essentials

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,                          // per-test ms
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  fullyParallel: true,
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3000',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox',  use: { browserName: 'firefox'  } },
    { name: 'webkit',   use: { browserName: 'webkit'   } },
  ],
});
```

---

## Core API

```ts
// Navigation
await page.goto('/login');
await page.goto('https://example.com', { waitUntil: 'networkidle' });
await page.goBack();
await page.reload();

// Actions
await page.getByRole('button', { name: 'Submit' }).click();
await page.getByLabel('Email').fill('user@example.com');
await page.getByRole('combobox').selectOption('CA');
await page.getByLabel('Remember me').check();
await page.getByRole('menuitem', { name: 'Products' }).hover();
await page.locator('#source').dragTo(page.locator('#target'));
```

---

## Locators

Prefer semantic/a11y locators — resilient to DOM churn.

```ts
// Preferred
page.getByRole('button', { name: 'Submit' })
page.getByLabel('Email address')
page.getByPlaceholder('Search...')
page.getByText('Welcome back')
page.getByTestId('submit-btn')          // data-testid="submit-btn"

// CSS / XPath fallback
page.locator('css=.btn-primary')
page.locator('xpath=//button[@type="submit"]')

// Chaining (scope to parent)
page.getByRole('dialog').getByRole('button', { name: 'Confirm' })

// nth (avoid if possible)
page.getByRole('button', { name: 'Edit' }).nth(0)
```

---

## Assertions

All `expect()` calls auto-wait/retry up to the assertion timeout (default 5s).

```ts
import { expect } from '@playwright/test';

await expect(page).toHaveURL('/dashboard');
await expect(page).toHaveTitle(/Dashboard/);

const btn = page.getByRole('button', { name: 'Save' });
await expect(btn).toBeVisible();
await expect(btn).toBeEnabled();
await expect(btn).toBeDisabled();
await expect(btn).toHaveText('Save changes');
await expect(btn).toHaveAttribute('aria-label', 'Save');

// Negative assertion
await expect(page.getByText('Error')).not.toBeVisible();

// Soft assertion — doesn't stop test on failure
await expect.soft(page.getByText('Count')).toHaveText('42');
```

---

## Waiting Strategies

> ⚠️ Avoid `page.waitForTimeout()` — it's a flakiness trap.

```ts
// Auto-waiting (built in) — just use locator actions
await page.getByRole('button').click();           // waits for actionable

// Wait for element state
await page.getByText('Loading...').waitFor({ state: 'hidden' });
await page.locator('.toast').waitFor({ state: 'visible' });

// Wait for navigation after action
await Promise.all([
  page.waitForURL('**/dashboard'),
  page.getByRole('button', { name: 'Login' }).click(),
]);

// Wait for a specific API response
const [response] = await Promise.all([
  page.waitForResponse(r =>
    r.url().includes('/api/user') && r.status() === 200
  ),
  page.getByRole('button', { name: 'Load' }).click(),
]);
```

---

## Page Object Model

```ts
// pages/LoginPage.ts
import { Page, Locator } from '@playwright/test';

export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitBtn: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput    = page.getByLabel('Email');
    this.passwordInput = page.getByLabel('Password');
    this.submitBtn     = page.getByRole('button', { name: 'Log in' });
  }

  async goto() {
    await this.page.goto('/login');
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitBtn.click();
  }
}
```

---

## Custom Fixtures

```ts
// fixtures.ts
import { test as base } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';

type MyFixtures = {
  loginPage: LoginPage;
  authenticatedPage: void;
};

export const test = base.extend<MyFixtures>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
  authenticatedPage: async ({ page }, use) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(process.env.TEST_USER!);
    await page.getByLabel('Password').fill(process.env.TEST_PASS!);
    await page.getByRole('button', { name: 'Log in' }).click();
    await page.waitForURL('**/dashboard');
    await use();
  },
});

export { expect } from '@playwright/test';
```

---

## Auth & storageState

Log in once in global setup — all tests reuse cookies/localStorage. Massive speed gain on CI.

```ts
// global-setup.ts
import { chromium } from '@playwright/test';

async function globalSetup() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(process.env.BASE_URL + '/login');
  await page.getByLabel('Email').fill(process.env.TEST_USER!);
  await page.getByLabel('Password').fill(process.env.TEST_PASS!);
  await page.getByRole('button', { name: 'Log in' }).click();
  await page.waitForURL('**/dashboard');
  await page.context().storageState({ path: 'auth.json' });
  await browser.close();
}
export default globalSetup;
```

```ts
// playwright.config.ts additions
globalSetup: './global-setup.ts',
use: { storageState: 'auth.json' }
```

### Multi-role projects

```ts
projects: [
  { name: 'admin',  use: { storageState: 'auth/admin.json'  } },
  { name: 'editor', use: { storageState: 'auth/editor.json' } },
  { name: 'viewer', use: { storageState: 'auth/viewer.json' } },
],

// Skip a role in a specific test:
test.skip(({ project }) => project.name === 'viewer', 'viewer has no access');
```

---

## API Testing

```ts
import { test, expect } from '@playwright/test';

test('GET /api/patients returns 200', async ({ request }) => {
  const response = await request.get('/api/patients');
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body).toHaveProperty('data');
});

test('POST creates a resource', async ({ request }) => {
  const response = await request.post('/api/patients', {
    data: { name: 'Jane Doe', dob: '1990-01-15' },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(response.status()).toBe(201);
});
```

### Hybrid API + UI test

```ts
test('patient appears in UI after API create', async ({ page, request }) => {
  // Seed via API
  const { id } = await request.post('/api/patients', {
    data: { name: 'Test Patient' }
  }).then(r => r.json());

  // Assert in UI
  await page.goto('/patients');
  await expect(page.getByText('Test Patient')).toBeVisible();

  // Cleanup via API
  await request.delete(`/api/patients/${id}`);
});
```

---

## Network Mocking

```ts
// Mock a failed response
await page.route('**/api/patients', route =>
  route.fulfill({
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({ error: 'Internal Server Error' }),
  })
);

// Abort (simulate offline / block analytics)
await page.route('**/*.analytics.js', route => route.abort());

// Intercept + modify real response
await page.route('**/api/config', async route => {
  const response = await route.fetch();
  const json = await response.json();
  json.featureFlag = true;
  await route.fulfill({ response, json });
});

// Assert payload sent by UI
const [request] = await Promise.all([
  page.waitForRequest(r =>
    r.url().includes('/api/save') && r.method() === 'POST'
  ),
  page.getByRole('button', { name: 'Save' }).click(),
]);
const body = request.postDataJSON();
expect(body.name).toBe('Jane');
```

---

## Advanced Patterns

### Data-driven tests

```ts
const cases = [
  { user: 'admin@test.com',  pass: 'admin123',  expected: '/admin'     },
  { user: 'user@test.com',   pass: 'user123',   expected: '/dashboard' },
];

for (const { user, pass, expected } of cases) {
  test(`${user} lands on ${expected}`, async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(user);
    await page.getByLabel('Password').fill(pass);
    await page.getByRole('button', { name: 'Log in' }).click();
    await expect(page).toHaveURL(expected);
  });
}
```

### Visual regression

```ts
test('dashboard layout', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page).toHaveScreenshot('dashboard.png', {
    fullPage: true,
    threshold: 0.2,
  });
});
// Update baseline: npx playwright test --update-snapshots
```

### CI sharding

```bash
# Shard 1 of 4 on a CI runner:
npx playwright test --shard=1/4

# Merge reports from all shards:
npx playwright merge-reports --reporter html ./blob-reports
```

### iFrames

```ts
const iframe = page.frameLocator('#sandbox-iframe');
await iframe.getByRole('button', { name: 'Agree' }).click();
await expect(iframe.getByText('Accepted')).toBeVisible();
```

### File upload / download

```ts
// Upload
const fileChooserPromise = page.waitForEvent('filechooser');
await page.getByLabel('Upload file').click();
const fileChooser = await fileChooserPromise;
await fileChooser.setFiles('tests/fixtures/sample.pdf');

// Download
const downloadPromise = page.waitForEvent('download');
await page.getByRole('link', { name: 'Export CSV' }).click();
const download = await downloadPromise;
await download.saveAs('./reports/' + download.suggestedFilename());
```

### Mobile emulation

```ts
// playwright.config.ts
import { devices } from '@playwright/test';

projects: [
  { name: 'Mobile Chrome', use: { ...devices['Pixel 5']    } },
  { name: 'Mobile Safari', use: { ...devices['iPhone 12']  } },
],

// Per-test override:
test.use({ viewport: { width: 390, height: 844 } });
```

---

## Gotchas

### Strict mode — multiple matches

```ts
// Throws if 2+ buttons named 'Edit' exist
await page.getByRole('button', { name: 'Edit' }).click(); // ERROR

// Fix: scope to a parent
await page
  .getByRole('row', { name: 'Jane Doe' })
  .getByRole('button', { name: 'Edit' })
  .click();
```

### Never use hard waits

```ts
// WRONG
await page.waitForTimeout(3000);

// RIGHT — auto-waits internally
await page.getByRole('button', { name: 'Submit' }).click();

// RIGHT — explicit state when needed
await page.locator('.spinner').waitFor({ state: 'hidden' });
```

### Debugging

```bash
# Open Playwright Inspector
PWDEBUG=1 npx playwright test

# Generate test via click-recording
npx playwright codegen https://example.com

# Open trace viewer
npx playwright show-trace trace.zip
```

---

## Useful CLI Commands

| Command | Purpose |
|---|---|
| `npx playwright test` | Run all tests |
| `npx playwright test --headed` | Run with visible browser |
| `npx playwright test --grep @smoke` | Run tagged tests |
| `npx playwright test --project=chromium` | Single browser |
| `npx playwright test --debug` | Step-through debugger |
| `npx playwright test --ui` | Interactive UI mode |
| `npx playwright show-report` | Open HTML report |
| `npx playwright codegen <url>` | Record test via browser |
| `npx playwright test --update-snapshots` | Refresh visual baselines |

---

*Part of the [ai-test-automation-python](https://github.com/njmarshall/ai-test-automation-python) portfolio*
