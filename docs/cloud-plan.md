# Initial cloud deployment decision

Agreed September 17, 2026: two Linux Lightsail instances in us-east-1, with Caddy handling public HTTPS. No cloud resources have been provisioned by this plan.

| Host | Workload | Initial bundle | Monthly base cost (USD) |
| --- | --- | --- | --- |
| Applications | Sites, Portal, Crust, Datalake, OAuth2 Proxy, Nginx and Caddy | 4 GB RAM / 80 GB disk, public IPv4 | $24 |
| Database | PostgreSQL; separate databases and roles for each project | 2 GB RAM / 60 GB disk, public IPv4 | $12 |

These are initial estimates, not measured capacity guarantees. Backups, excess transfer, domain/DNS charges and taxes are additional. Check bundle availability/prices before creation. Both hosts are single points of failure: this launch prioritizes cost and recoverability rather than high availability. Lightsail bills stopped instances; a months-long pause requires a verified backup/snapshot and deliberate deletion/recreation to stop instance charges. Existing EC2 experiments are unrelated and remain untouched.

## HTTPS, names and network boundaries

One attached static IPv4 address on the application host serves all 34 publication domains plus portal.guten.ink, using an explicit hostname allowlist. Retain DNS with existing providers; Lightsail's included DNS zone limit is separate from the number of sites we can serve. No Lightsail load balancer is planned.

Caddy obtains and renews public ACME certificates, with persistent certificate/account storage separate from application releases. Add each publication's chosen apex/www names and redirect aliases to its canonical address. Validate with ACME staging before production issuance. Reject unknown hostnames. Retain the tested Nginx/OAuth access controls behind Caddy. Forwarded HTTPS/host headers must be trusted only from that internal proxy path; verify secure cookies, callback redirects, CSRF checks and published-only APIs end to end.

Only HTTP-to-HTTPS and HTTPS are public application entry points; restrict administrative SSH. No public PostgreSQL port. Database traffic uses private addresses and explicit PostgreSQL/host firewall restrictions, because Lightsail's public firewall does not filter private traffic. Docker-published ports must be covered by the actual container forwarding rules, not merely an assumed host firewall policy. Use authenticated encrypted DB connections and a least-privilege Guten application role. Do not expose Crust, Datalake or raw frontend ports.

Hostname-to-site context, domain-relative links, canonical URLs and the Caddy gateway are implemented and locally tested; see [HTTPS gateway](https-gateway.md). The production GitHub OAuth App, real DNS/certificates and cross-host DB connection remain deployment work. Preserve local path-based development. Domain registration/DNS ownership will be checked before cutover.

## Database readiness and recovery

PostgreSQL 14 support ends November 12, 2026. Target PostgreSQL 17 after isolated restore and acceptance verification. Never start a new PostgreSQL major against an existing major's data volume. The Mac's master Guten database and all VitalEdge databases remain unchanged.

Run the archived-content comparison and synthetic API/browser tests using the existing Datalake Python environment:

```bash
/path/to/datalake/python -B scripts/rehearse_postgres.py --archive /absolute/path/to/completed/guten/archive
```

The script verifies full.dump against its recorded checksum, creates fresh PostgreSQL 14 and 17 containers on random loopback ports, restores the same archive into both, and compares all user-table row hashes/counts, sequence state and constraints. It then runs the existing acceptance suite in a separate synthetic database on PostgreSQL 17. It removes only its newly created containers and anonymous volumes, retaining reports under ignored artifacts/postgres17_*; the acceptance harness also retains its normal report directory.

This verifies portable restores with ownership/grants omitted. Production grants, extensions, collation choices and performance need separate validation. The Mac archive uses en_CA.UTF-8; these Linux image defaults are not proof of identical locale-dependent behavior. Choose and document the production locale explicitly before provisioning. Browser tests exercise synthetic content; archived-row comparison checks the historical content without editing it.

Before cutover: take a fresh master archive, verify its checksum and restore into the new deployment database, validate counts/content and app-role permissions, and rehearse recovery. Schedule encrypted off-host dumps and media backups with retention and failure reporting; snapshots supplement logical dumps. Resolve narrowly scoped backup-upload credentials explicitly; do not copy Admin or GutenAudit sessions onto servers. Human-readable site exports are useful supplementary archives, not a replacement for database backups.

## Release path

Build/test versioned container images in GitHub Actions, pin deployed image digests and record a release manifest spanning the four repositories. Deploy an explicitly approved release with Docker Compose and health checks; retain the previous release for rollback. Database migrations and restore are explicit operations, never incidental app startup. Host secret files and writable data stay outside images and Git.

Start with a manually invoked deployment script, then automate its invocation after the first proven cloud release. Image registry access, SSH trust and any AWS deployment role must be narrowly scoped. The existing GutenAudit role is for inventory, not provisioning. CI should build images off the small production hosts.

Implementation sequence: PostgreSQL 17 rehearsal; production hostname/HTTPS and auth tests; database-host packaging and backup/restore; release build/deploy scripts; review exact resources/cost and provision; validate on test domains before moving public DNS. Media may initially use the existing shared read-only directory with off-host backups; S3 delivery can follow independently.

Sources checked September 17, 2026:
- https://aws.amazon.com/lightsail/pricing/
- https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html
- https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html
- https://caddyserver.com/docs/automatic-https
- https://www.postgresql.org/support/versioning/

## Rehearsal evidence — September 17, 2026

First run passed: 19 restored tables / 920 rows, 17 sequences and 56 constraints matched between fresh PostgreSQL 14 and 17 clusters. The archive contained 34 sites, 87 sections and 298 pages in each of draft/published. All 17 API/configuration tests and all 3 browser workflows passed on PostgreSQL 17. Both temporary containers/volumes and the synthetic acceptance database were removed successfully.

Local retained evidence: `artifacts/postgres17_20260917T173346_d059baa36943/` (restore comparison) and `artifacts/20260917T173411_89b8138cab/` (API/browser reports). Input was the completed archive `guten_datalake_20260917T035834Z_VrgBVL`, SHA-256 `e275522ef249bc2ac820851fd0b10e4c4285083d5c5fa883952558c8f67bd5ea`. No master database or existing service was upgraded. Production locale/grants and a fresh cutover backup remain required.

## Database host package

Private TLS PostgreSQL 17 packaging, dedicated app/backup roles, age-encrypted archives and a guarded restore workflow are now implemented; see [database operations](cloud-database.md). Local integration tests precede provisioning. Cross-host firewall enforcement, actual S3 credentials/upload, retention, external alerts and Linux timer validation remain deployment acceptance work.

## Release tooling

Committed-source image building, digest-pinned app-host bundles, read-only schema compatibility checks and explicit deployment/rollback tooling are implemented; see [releases](releases.md). Registry publication and a real two-host deployment/rollback rehearsal remain pending.
