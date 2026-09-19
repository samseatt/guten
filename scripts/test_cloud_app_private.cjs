// Run inside the app Docker network. Read-only probes; no real login or content edits.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const http = require('node:http');
const host = process.argv[2] || 'portal.guten.ink';
const expectedImageHash = process.argv[3];
assert.match(host, /^[a-z0-9.-]+$/);
assert.match(expectedImageHash, /^[0-9a-f]{64}$/);
const checks = [];
function request(port, path, extra = {}) {
  // Node's fetch may override Host; these probes must exercise production routing.
  return new Promise((resolve, reject) => {
    const request = http.get({hostname: 'web', port, path, headers: {Host: host, ...extra}}, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => resolve({
        status: response.statusCode,
        headers: {
          get: name => response.headers[name.toLowerCase()],
          getSetCookie: () => response.headers['set-cookie'] || []
        },
        json: async () => JSON.parse(Buffer.concat(chunks).toString())
      }));
      response.on('error', reject);
    });
    request.setTimeout(15000, () => request.destroy(new Error('Private HTTP probe timed out')));
    request.on('error', reject);
  });
}

(async () => {
  let response = await request(8081, '/dashboard');
  assert.equal(response.status, 403, 'dashboard must require login');
  checks.push('dashboard requires login');
  for (const headers of [{}, {'X-Forwarded-User': 'samseatt', 'X-Forwarded-Email': 'fake@example.com', Authorization: 'Bearer fake'}]) {
    response = await request(8081, '/api/guten/sites', headers);
    assert.equal(response.status, 401, 'editorial API must reject unauthenticated/spoofed requests');
  }
  checks.push('editorial API rejects anonymous and spoofed identities');
  response = await request(8081, '/oauth2/sign_in');
  assert.equal(response.status, 200);
  response = await request(8081, '/oauth2/start?rd=%2Fdashboard');
  assert.equal(response.status, 302);
  const location = new URL(response.headers.get('location'));
  assert.equal(location.origin, 'https://github.com');
  assert.equal(location.searchParams.get('redirect_uri'), `https://${host}/oauth2/callback`);
  assert.ok(location.searchParams.get('client_id'));
  const cookies = response.headers.getSetCookie();
  assert.ok(cookies.length);
  for (const cookie of cookies) {
    assert.ok(/; Secure(?:;|$)/i.test(cookie), 'CSRF cookie requires Secure');
    assert.ok(/; HttpOnly(?:;|$)/i.test(cookie), 'CSRF cookie requires HttpOnly');
    assert.ok(/; SameSite=Lax(?:;|$)/i.test(cookie), 'CSRF cookie requires SameSite=Lax');
    assert.ok(!/; Domain=/i.test(cookie), 'CSRF cookie must remain host-only');
  }
  checks.push('GitHub redirect and Secure/HttpOnly/host-only CSRF cookies');
  response = await request(8080, '/');
  assert.equal(response.status, 404);
  checks.push('publications unavailable in Portal-only mode');
  response = await request(8082, '/api/guten/sites');
  assert.equal(response.status, 200);
  const sites = await response.json();
  assert.ok(Array.isArray(sites) && sites.length > 0);
  checks.push(`internal read-only content path returns ${sites.length} sites`);
  for (const service of ['portal']) {
    response = await fetch(`http://${service}:3000/assets/default.png`, {signal: AbortSignal.timeout(15000)});
    assert.equal(response.status, 200);
    const bytes = Buffer.from(await response.arrayBuffer());
    assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), expectedImageHash);
  }
  checks.push('Portal serves the verified shared draft-preview image');
  response = await fetch('http://sites:3000/assets/default.png');
  assert.equal(response.status, 404, 'Sites must reject unconfigured hosts even for assets');
  checks.push('Sites refuses unconfigured publication hosts');
  console.log(JSON.stringify({passed: checks}, null, 2));
})().catch(error => { console.error(JSON.stringify({failed:error.message,passed:checks})); process.exitCode = 1; });
