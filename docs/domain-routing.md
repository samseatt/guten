# Public domains and Portal entry points

## Recommended production addresses

| Address | Application and behavior |
| --- | --- |
| `https://neubank.org/` | Published `neubank` site, served by Guten Sites |
| `https://guten.ink/` | Published `guten` site, including its public introduction to Guten |
| `https://portal.guten.ink/` | Guten Portal home, behind GitHub authentication |
| `https://portal.guten.ink/dashboard` | Site Management Dashboard, behind the same authentication |

A subdomain needs a DNS record and certificate, not another purchased domain or another application server. Nginx on the application Lightsail instance can route by hostname; an AWS load balancer is not required for this initial deployment. Path routing such as `guten.ink/portal` is possible, but would require a consistent Portal base path, including its assets and API routes. The dedicated subdomain keeps those concerns simpler. Optionally redirect `guten.ink/portal` to `portal.guten.ink/` later.

## Root pages implemented now

Portal's `/` is a small workspace home with a Site Management Dashboard link. The navigation brand returns here. Add other working publication tools here as they are built; no placeholder menus are needed. Docker gateway authentication protects this home, the dashboard, all editing pages and editorial APIs, using host-only secure cookies for the Portal host.

Sites' bare `/` is a neutral Guten Sites page directing visitors to their publication address. It does not list hosted sites or assume the `guten` publication exists in every database. Local path-based access (`/<site>/<section>/<page>`) is retained. Local native ports remain 3000/3001; Docker rehearsal ports remain 13000/13001. These are HTTP development addresses, not HTTPS endpoints yet.

## Domain mapping and deployment

Use an explicit verified hostname-to-site mapping, not a hostname split or arbitrary Host header interpreted as a site name. Known public domain roots should serve their mapped site's existing landing selection, and section/page links should remain on that domain without adding the internal site slug. This requires more than rewriting `/`: renderer links, redirects, canonical addresses, and published API requests need consistent site/domain context. The public `sites.url` metadata alone must not authorize a hostname mapping.

The production proxy should reject unrecognized hostnames/direct-IP requests with 404 and expose only HTTPS/HTTP redirect ports. Application ports stay private. Thus the neutral bare-root page remains useful locally without becoming a public directory on AWS. `portal.guten.ink` explicitly routes to Portal; its public sibling `guten.ink` routes to Sites. Restrict public-domain APIs to published reads, and scope them to the mapped site. Preserve shared assets and Next.js resources without treating them as content slugs.

Explicit domain routing and the Caddy gateway are implemented; see [HTTPS gateway configuration and tests](https-gateway.md). DNS changes and public certificate issuance remain deployment work. See [implemented Portal authentication](authentication.md).

References: [Nginx hostname and path routing](https://nginx.org/en/docs/http/request_processing.html), [AWS ALB host/path conditions](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/rule-condition-types.html).
