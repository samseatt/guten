// Read-only public-site acceptance. Optional SSH preview transport leaves DNS untouched.
import {chromium, request, expect} from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const origin='https://guten.ink';
const preview=process.env.GUTEN_PREVIEW_BASE;
const output=process.env.GUTEN_PUBLIC_ARTIFACTS;
if (!output) throw Error('Set GUTEN_PUBLIC_ARTIFACTS to a new artifact directory');
fs.mkdirSync(output,{recursive:false});
const api=await request.newContext();
async function get(path,headers={}) {
  return api.get((preview||origin)+path,{headers:{...headers,...(preview?{Host:'guten.ink'}:{})}});
}
const landingResponse=await get('/api/guten/published/sites/guten/landing');
assert.equal(landingResponse.status(),200);
const landing=await landingResponse.json();
const path='/'+encodeURIComponent(landing.section_name)+'/'+encodeURIComponent(landing.page_name);
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||undefined});
const context=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
const checks=[];
try {
  if (preview) {
    await context.route(origin+'/**',async route=>{
      const url=new URL(route.request().url());
      const response=await route.fetch({url:preview+url.pathname+url.search,headers:{...route.request().headers(),host:'guten.ink'},maxRedirects:0});
      await route.fulfill({response});
    });
  }
  const page=await context.newPage();const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin+'/');
  await expect(page).toHaveURL(origin+path);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href',origin+path);
  await expect(page.locator('img').first()).toBeVisible();
  await expect.poll(()=>page.locator('img').evaluateAll(images=>images.every(image=>image.complete&&image.naturalWidth>0))).toBe(true);
  const images=await page.locator('img').count();
  checks.push('root resolves to published landing page with canonical URL and loaded images');
  await page.screenshot({path:output+'/landing.png',fullPage:true});
  const links=await page.locator('a[href^="/"]').evaluateAll(elements=>elements.map(a=>a.getAttribute('href')));
  const next=links.find(href=>href!==path && /^\/[^/]+\/[^/]+$/.test(href) && !href.startsWith('/api/'));
  assert.ok(next,'Expected another published page link');
  await page.locator(`a[href="${next}"]`).first().click();
  await expect(page).toHaveURL(origin+next);await page.reload();
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href',origin+next);
  checks.push('menu navigation and direct page reload');
  for(const endpoint of ['/api/guten/sites','/api/guten/published/sites/neubank/landing']) {
    assert.equal((await get(endpoint)).status(),404);
  }
  assert.equal((await get('/api/guten/published/sites/neubank/landing',{'X-Guten-Site':'neubank','X-Forwarded-Host':'neubank.org'})).status(),404);
  checks.push('editorial API, other publications and spoofed publication headers rejected');
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/results.json',JSON.stringify({origin,transport:preview?'loopback SSH preview':'public HTTPS',landing,images,checks},null,2)+'\n');
  console.log(JSON.stringify({landing,images,checks}));
} finally {await context.close();await browser.close();await api.dispose();}
