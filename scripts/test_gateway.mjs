import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
if(process.env.GUTEN_GATEWAY_TEST!=='1')throw Error('Use isolated gateway runner');
const [alpha,beta]=JSON.parse(process.env.GUTEN_TEST_SITES);
const portal='https://portal.guten.test:14443';
const publicURL='https://alpha.guten.test:14443';
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL||undefined,args:['--host-resolver-rules=MAP *.guten.test 127.0.0.1','--no-proxy-server']});
const checks=[];
const context=await browser.newContext({ignoreHTTPSErrors:true});
try {
  await context.tracing.start({screenshots:true,snapshots:true});
  const page=await context.newPage();
  if(process.env.GUTEN_TEST_AUTH_OUTAGE==='1'){
    for(const path of ['/dashboard','/api/guten/sites'])assert.ok([502,503,504].includes((await page.goto(portal+path)).status()));
    assert.equal((await page.goto(publicURL+'/')).status(),200);
    fs.writeFileSync(process.env.GUTEN_GATEWAY_ARTIFACTS+'/outage.json',JSON.stringify({passed:true}));
  } else {
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(publicURL+'/');
    await expect(page).toHaveURL(publicURL+'/first/one');
    await expect(page.getByText('Content for '+alpha,{exact:true})).toBeVisible();
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href',publicURL+'/first/one');
    await expect(page.locator('a[href="/first/two"]')).toHaveText('two');
    await page.locator('a[href="/first/two"]').click();
    await expect(page).toHaveURL(publicURL+'/first/two');
    await page.reload();await expect(page.getByText('Content for '+alpha,{exact:true})).toBeVisible();
    console.log('Gateway checks completed:', checks.length + 1);
    checks.push('domain root, landing redirect, menu navigation, hard reload and canonical URL');
    const fetchStatus=(path,options={})=>page.evaluate(async({path,options})=>(await fetch(path,options)).status,{path,options});
    assert.equal(await fetchStatus(`/api/guten/published/sites/${alpha}/page?section=first&page=one`),200);
    assert.equal(await fetchStatus(`/api/guten/published/sites/${beta}/page?section=first&page=one`),404);
    assert.equal(await fetchStatus(`/api/guten/published/sites/${alpha}/page?section=first&page=one`,{method:'POST'}),403);
    assert.equal(await fetchStatus('/api/guten/sites'),404);
    assert.equal(await fetchStatus('/api/guten/published/sites/'+encodeURIComponent(beta)+'/landing',{headers:{'X-Forwarded-Host':'beta.guten.test','X-Guten-Site':beta}}),404);
    await page.goto(publicURL+'/'+beta+'/first/one');
    assert.equal((await page.locator('body').innerText()).includes('Content for '+beta),false);
    await page.goto('https://beta.guten.test:14443/first/one');await expect(page.getByText('Content for '+beta,{exact:true})).toBeVisible();
    await page.goto('https://www.alpha.guten.test:14443/first/two');await expect(page).toHaveURL(publicURL+'/first/two');
    await page.goto('http://alpha.guten.test:18080/first/one');await expect(page).toHaveURL(publicURL+'/first/one');
    assert.equal((await page.goto('http://unknown.guten.test:18080/')).status(),404);
    console.log('Gateway checks completed:', checks.length + 1);
    checks.push('publication isolation, public write rejection, spoofed headers, aliases and HTTPS redirect');
    const denied=await browser.newContext({ignoreHTTPSErrors:true});
    const deniedPage=await denied.newPage();
    await deniedPage.goto(portal+'/dashboard');
    await deniedPage.getByRole('button',{name:/GitHub/i}).click();
    const deniedCallback=deniedPage.waitForResponse(r=>new URL(r.url()).pathname==='/oauth2/callback');
    await deniedPage.getByRole('link',{name:'Approve disallowed test account',exact:true}).click();
    assert.ok([403,500].includes((await deniedCallback).status()));
    assert.equal(await deniedPage.evaluate(async()=>(await fetch('/api/guten/sites')).status),401);
    await denied.close();
    await page.goto(portal+'/dashboard');await expect(page.getByRole('button',{name:/GitHub/i})).toBeVisible();
    assert.equal(await fetchStatus('/api/guten/sites',{headers:{'X-Forwarded-User':'samseatt','Authorization':'Bearer forged','X-Forwarded-Proto':'http'}}),401);
    await page.getByRole('button',{name:/GitHub/i}).click();
    await page.getByRole('link',{name:'Approve allowed test account',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Guten Dashboard',exact:true})).toBeVisible();
    const session=(await context.cookies()).find(c=>c.name==='_guten_portal');
    assert.ok(session);assert.equal(session.secure,true);assert.equal(session.httpOnly,true);assert.equal(session.sameSite,'Lax');assert.equal(session.domain,'portal.guten.test');
    assert.equal(await fetchStatus('/api/guten/sites'),200);
    assert.equal(await fetchStatus('/api/guten/pages/one',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({site_name:alpha,section_name:'first',name:'one',title:'one',content:'Content for '+alpha})}),200);
    // GET cannot spoof authentication; unsafe requests without Origin are checked via curl below.
    await page.goto(portal+'/published/'+alpha);await expect(page).toHaveURL(publicURL+'/first/one');
    assert.equal((await context.cookies(publicURL)).some(c=>c.name==='_guten_portal'),false);
    assert.deepEqual(errors,[]);
    console.log('Gateway checks completed:', checks.length + 1);
    checks.push('HTTPS OAuth callback, secure host-only cookie, authenticated APIs and Portal published link');
    // Server-side requests allow testing missing/foreign Origin without browser rewriting it.
    const {execFileSync}=await import('node:child_process');
    for(const origin of ['', 'https://attacker.test','null']){
      const args=['-sk','--resolve','portal.guten.test:14443:127.0.0.1','-o','/dev/null','-w','%{http_code}','-X','POST','-H','Cookie: '+session.name+'='+session.value];
      if(origin)args.push('-H','Origin: '+origin);
      args.push(portal+'/api/guten/sites');assert.equal(execFileSync('curl',args,{encoding:'utf8'}),'403');
    }
    console.log('Gateway checks completed:', checks.length + 1);
    checks.push('authenticated requests with missing/foreign Origin blocked');
    await page.goto(portal+'/');await page.getByRole('link',{name:'Sign out',exact:true}).click();
    assert.equal(await fetchStatus('/api/guten/sites'),401);
    console.log('Gateway checks completed:', checks.length + 1);
    checks.push('logout');
    fs.writeFileSync(process.env.GUTEN_GATEWAY_ARTIFACTS+'/gateway.json',JSON.stringify({passed:true,checks},null,2));
  }
} finally {
  await context.tracing.stop({path:process.env.GUTEN_GATEWAY_ARTIFACTS+(process.env.GUTEN_TEST_AUTH_OUTAGE?'/outage-trace.zip':'/trace.zip')}).catch(()=>{});
  await browser.close();
}
