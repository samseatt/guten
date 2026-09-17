import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base = process.env.GUTEN_PORTAL_URL;
if (base !== 'http://127.0.0.1:13011' || process.env.GUTEN_AUTH_TEST !== '1') throw new Error('Isolated auth test runner required');
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
const results = [];
try {
  const anonymous = await browser.newContext();
  for (const [method,path] of [['GET','/api/guten/sites'],['POST','/api/guten/sites'],['PUT','/api/guten/notes/1'],['DELETE','/api/guten/sites/test/publication'],['POST','/api/guten/publish/test']]) {
    const response = await anonymous.request.fetch(base+path,{method,headers:{'X-Forwarded-User':'samseatt','X-Auth-Request-User':'samseatt','Authorization':'Bearer made-up'}});
    assert.equal(response.status(),401,method+' '+path);
  }
  assert.ok([400,403,500].includes((await anonymous.request.get(base+'/oauth2/callback?code=invalid&state=forged')).status()));
  assert.equal((await anonymous.request.get(base+'/api/guten/sites')).status(),401);
  results.push('anonymous APIs, spoofed headers and forged callback denied');
  async function login(context,allowed) {
    const page=await context.newPage(); await page.goto(base+'/dashboard');
    await page.getByRole('button',{name:/GitHub/i}).click();
    const callback = page.waitForResponse(response => new URL(response.url()).pathname === '/oauth2/callback');
    await page.getByRole('link',{name:allowed?'Approve allowed test account':'Approve disallowed test account',exact:true}).click();
    return {page, callbackStatus:(await callback).status()};
  }
  const denied = await browser.newContext();
  const deniedLogin = await login(denied,false);
  assert.ok([403,500].includes(deniedLogin.callbackStatus));
  assert.equal((await denied.cookies()).some(c => c.name === '_guten_portal'),false);
  await expect.poll(async () => (await denied.request.get(base+'/api/guten/sites')).status()).toBe(401);
  results.push('non-allowlisted GitHub identity denied');
  const approved = await browser.newContext();
  const {page,callbackStatus} = await login(approved,true);
  assert.equal(callbackStatus,302);
  await expect(page.getByRole('heading',{name:'Guten Dashboard',exact:true})).toBeVisible();
  assert.equal((await approved.request.get(base+'/api/guten/sites')).status(),200);
  for (const origin of [undefined,'https://untrusted.example','null']) {
    const response=await approved.request.post(base+'/api/guten/sites',{headers:origin?{Origin:origin}:{},data:{name:'should_not_exist'}});
    assert.equal(response.status(),403,'CSRF origin '+origin);
  }
  const cookies=await approved.cookies();
  const session=cookies.find(c=>c.name==='_guten_portal');assert.ok(session);
  assert.equal(session.httpOnly,true);assert.equal(session.sameSite,'Lax');assert.equal(session.domain,'127.0.0.1');
  const tampered=await browser.newContext();await tampered.addCookies([{...session,value:session.value+'tampered'}]);
  assert.equal((await tampered.request.get(base+'/api/guten/sites')).status(),401);
  const expired=await browser.newContext();await expired.addCookies([{...session,expires:Math.floor(Date.now()/1000)-60}]);
  assert.equal((await expired.request.get(base+'/api/guten/sites')).status(),401);
  results.push('approved identity, HttpOnly/SameSite cookie, CSRF, expiration and tamper checks passed');
  await approved.storageState({path:process.env.GUTEN_AUTH_STATE});
  const logout = await browser.newContext({storageState:process.env.GUTEN_AUTH_STATE});
  const logoutPage=await logout.newPage();await logoutPage.goto(base+'/');
  await logoutPage.getByRole('link',{name:'Sign out',exact:true}).click();
  await expect.poll(async () => (await logout.request.get(base+'/api/guten/sites')).status()).toBe(401);
  results.push('logout removes session');
  fs.writeFileSync(process.env.GUTEN_AUTH_RESULTS,JSON.stringify({passed:true,checks:results},null,2));
} finally { await browser.close(); }
