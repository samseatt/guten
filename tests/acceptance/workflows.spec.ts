import { test, expect, APIRequestContext } from '@playwright/test';
import { randomUUID } from 'node:crypto';

const api = process.env.GUTEN_API_URL!;
const sites = process.env.GUTEN_SITES_URL!;
let name: string;
async function call(request: APIRequestContext, method: string, path: string, data?: unknown) {
  const response = await request.fetch(api + path, { method, data });
  expect(response.ok(), `${method} ${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}
const scope = () => ({ site_name: name, section_name: 'first', page_name: 'one' });
const editor = () => `/sites/${name}/sections/first/pages/one`;

test.beforeEach(async ({ request }) => {
  name = 'browser_' + randomUUID().replaceAll('-', '');
  await call(request, 'POST', '/sites', { name, title: name, url: '', logo: '', favicon: '', color: '' });
  for (const section of ['first','second']) {
    await call(request, 'POST', '/sections', { site_name: name, name: section, title: section, label: section });
    for (const page of ['one','two']) {
      await call(request, 'POST', '/pages', { site_name: name, section_name: section, name: page, title: page, content: 'Original acceptance content' });
    }
  }
});
test.afterEach(async ({ request }) => {
  const status = await call(request, 'GET', `/sites/${name}/publication`);
  if (status.is_published) await call(request, 'DELETE', `/sites/${name}/publication`, { expected_fingerprint: status.published_fingerprint });
  await call(request, 'DELETE', `/sites/${name}`);
});

test('editorial CRUD, cancellation, failed saves and unsaved content preservation', async ({ page, request }) => {
  await page.goto(editor());
  const content = page.getByRole('textbox', { name: 'Content (Markdown)', exact: true });
  await expect(content).toHaveValue('Original acceptance content');
  await content.fill('Unsaved acceptance content');
  const notes = page.getByRole('region', { name: 'Notes', exact: true });
  const note = notes.getByRole('textbox', { name: 'Note (Markdown)' });
  await note.fill('   ');
  await notes.getByRole('button', { name: 'Add Note', exact: true }).click();
  await expect(notes.getByText('Note must not be empty.')).toBeVisible();
  await note.fill('First editorial note');
  await page.route('**/api/guten/notes', async route => {
    if (route.request().method() === 'POST') await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Acceptance simulated outage' }) });
    else await route.continue();
  });
  await notes.getByRole('button', { name: 'Add Note', exact: true }).click();
  await expect(notes.getByText('Acceptance simulated outage')).toBeVisible();
  await expect(note).toHaveValue('First editorial note');
  await page.unroute('**/api/guten/notes');
  await notes.getByRole('button', { name: 'Add Note', exact: true }).click();
  await expect(notes.getByText('Note added.')).toBeVisible();
  await expect(content).toHaveValue('Unsaved acceptance content');
  await notes.getByRole('button', { name: 'Edit note 1', exact: true }).click();
  await note.fill('Cancelled change');
  await notes.getByRole('button', { name: 'Cancel Note Edit' }).click();
  await expect(notes.getByText('First editorial note', { exact: true })).toBeVisible();
  await notes.getByRole('button', { name: 'Edit note 1', exact: true }).click();
  await note.fill('Updated editorial note');
  await notes.getByRole('button', { name: 'Update Note' }).click();
  await expect(notes.getByText('Note updated.')).toBeVisible();
  await note.fill('Unsubmitted next note');
  await page.getByRole('button', { name: 'Save Changes' }).click();
  await expect(page.getByText('Page saved.')).toBeVisible();
  await expect(note).toHaveValue('Unsubmitted next note');
  const refs = page.getByRole('region', { name: 'References', exact: true });
  await refs.getByRole('textbox', { name: 'Reference URL' }).fill('javascript:alert(1)');
  await refs.getByRole('button', { name: 'Add Reference' }).click();
  await expect(refs.getByText('Enter an HTTP or HTTPS URL of at most 255 characters.')).toBeVisible();
  await refs.getByRole('textbox', { name: 'Reference URL' }).fill('https://example.org/reference');
  await refs.getByRole('textbox', { name: 'Reference description (optional)', exact: true }).fill('Reference example');
  await refs.getByRole('button', { name: 'Add Reference' }).click();
  await expect(refs.getByText('Reference added.')).toBeVisible();
  await refs.getByRole('button', { name: 'Edit reference 1', exact: true }).click();
  await refs.getByRole('textbox', { name: 'Reference URL' }).fill('https://example.org/edited');
  await refs.getByRole('button', { name: 'Update Reference' }).click();
  await expect(refs.getByText('Reference updated.')).toBeVisible();
  await page.reload();
  await expect(content).toHaveValue('Unsaved acceptance content');
  await expect(refs.getByText('https://example.org/edited', { exact: true })).toBeVisible();
  await expect(notes.getByText('Updated editorial note', { exact: true })).toBeVisible();
  for (const [region, kind] of [[notes, 'Note'], [refs, 'Reference']] as const) {
    await region.getByRole('button', { name: `Delete ${kind.toLowerCase()} 1`, exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(region.getByRole('button', { name: `Edit ${kind.toLowerCase()} 1`, exact: true })).toBeVisible();
    await region.getByRole('button', { name: `Delete ${kind.toLowerCase()} 1`, exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: `Delete ${kind}`, exact: true }).click();
    await expect(region.getByText(`${kind} deleted.`)).toBeVisible();
  }
  expect(await call(request, 'GET', `/notes?site=${name}&section=first&page=one`)).toEqual([]);
  expect(await call(request, 'GET', `/refs?site=${name}&section=first&page=one`)).toEqual([]);
});

test('section and page ordering persists through reload, preview and publication', async ({ page, request }) => {
  await page.goto(`/sites/${name}/sections`);
  await page.getByRole('button', { name: 'Move second up', exact: true }).click();
  await expect(page.getByText('Section order saved.')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Move second up', exact: true })).toBeDisabled();
  await page.goto(`/sites/${name}/sections/first/pages`);
  await page.getByRole('button', { name: 'Move two up', exact: true }).click();
  await expect(page.getByText('Page order saved.')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Move two up', exact: true })).toBeDisabled();
  const sections = await call(request, 'GET', `/sections?site=${name}`);
  expect(sections.map((s: {name:string}) => s.name)).toEqual(['second', 'first']);
  const pages = await call(request, 'GET', `/pages?site=${name}&section=first`);
  expect(pages.map((p: {name:string}) => p.name)).toEqual(['two', 'one']);
  await page.goto(`/draft/${name}/first/one`);
  await expect(page.getByText('Original acceptance content', { exact: true })).toBeVisible();
  await expect(page.locator(`a[href^="/draft/${name}/first/"]`)).toHaveText(['two','one']);
  const status = await call(request, 'GET', `/sites/${name}/publication`);
  await call(request, 'POST', `/publish/${name}`, { expected_fingerprint: status.draft_fingerprint });
  await page.goto(`${sites}/${name}/first/one`);
  await expect(page.getByText('Original acceptance content', { exact: true })).toBeVisible();
  await expect(page.locator(`a[href^="/${name}/first/"]`)).toHaveText(['two','one']);
  await expect(page.getByRole('banner').getByRole('link')).toHaveText(['second','first']);
});

test('publish confirmation, draft isolation, stale review rejection and unpublish', async ({ page, request, context }) => {
  const publicPage = await context.newPage();
  await page.goto('/dashboard');
  const card = page.getByRole('region', { name, exact: true });
  await expect(card.getByText('Not published', { exact: true })).toBeVisible();
  await card.getByRole('button', { name: 'Publish', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
  expect((await call(request, 'GET', `/sites/${name}/publication`)).is_published).toBe(false);
  await card.getByRole('button', { name: 'Publish', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Publish Site', exact: true }).click();
  await expect(card.getByText('Site published.', { exact: true })).toBeVisible();
  await publicPage.goto(`${sites}/${name}/first/one`);
  await expect(publicPage.getByText('Original acceptance content', { exact: true })).toBeVisible();
  await page.goto(editor());
  await page.getByRole('textbox', { name: 'Content (Markdown)', exact: true }).fill('Revised acceptance content');
  await page.getByRole('button', { name: 'Save Changes' }).click();
  await expect(page.getByText('Page saved.')).toBeVisible();
  await page.goto(`/draft/${name}/first/one`);
  await expect(page.getByText('Revised acceptance content', { exact: true })).toBeVisible();
  await publicPage.reload();
  await expect(publicPage.getByText('Original acceptance content', { exact: true })).toBeVisible();
  await page.goto('/dashboard');
  await expect(card.getByText('Unpublished changes', { exact: true })).toBeVisible();
  await card.getByRole('button', { name: 'Publish', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await call(request, 'PUT', '/pages/one', { ...scope(), name: 'one', title: 'one', content: 'Concurrent acceptance content' });
  await page.getByRole('dialog').getByRole('button', { name: 'Publish Site', exact: true }).click();
  await expect(card.getByRole('alert')).toContainText(/changed/i);
  await publicPage.reload();
  await expect(publicPage.getByText('Original acceptance content', { exact: true })).toBeVisible();
  await card.getByRole('button', { name: 'Publish', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Publish Site', exact: true }).click();
  await expect(card.getByText('Site published.', { exact: true })).toBeVisible();
  await publicPage.reload();
  await expect(publicPage.getByText('Concurrent acceptance content', { exact: true })).toBeVisible();
  await card.getByRole('button', { name: 'Unpublish', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Unpublish Site', exact: true }).click();
  await expect(card.getByText('Site unpublished. Draft content is preserved.')).toBeVisible();
  await publicPage.reload();
  await expect(publicPage.getByText('No published page is available at this address.')).toBeVisible();
  await page.goto(`/draft/${name}/first/one`);
  await expect(page.getByText('Concurrent acceptance content', { exact: true })).toBeVisible();
});
