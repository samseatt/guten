# Add a website to Guten: an editor and operator cookbook

Verified against the deployed application on September 19, 2026. Start here when adding a publication; older vision documents describe features that are not necessarily implemented.

This guide follows a fictional publication, **Field Notes**, with internal name `fieldnotes` and public address `example.com`. `example.com` is an illustrative domain: substitute a domain you control. You can prepare content before choosing one.

A launch has three parts: create and publish the content in Portal, point the domain to Guten with DNS, and have the Guten operator activate that domain in the server configuration. None of those steps automatically performs the other two.

## Who does what?

| Person | Responsibility |
| --- | --- |
| Content editor | Create the site, add sections/pages, supply image files, review drafts, publish and verify content. |
| Domain owner | Access the DNS account, record previous settings and change the website records when the operator is ready. |
| Guten operator | Grant Portal access, install images, prepare and deploy the domain mapping, verify DNS/HTTPS and retain recovery records. |

One person may fill all three roles. Editors do not need AWS credentials or terminal commands for normal content work. New domains and image files currently require operator assistance; those tasks are not yet self-service in Portal.

## 1. Get access and choose the site's identity

Open [Guten Portal](https://portal.guten.ink/dashboard) and sign in with GitHub. Ask the operator to allow your GitHub account first. The current installation initially allows only `samseatt`; creating a GitHub account alone does not grant access. Treat Portal access as trusted editorial access across the installation, not a separate permission boundary for one site.

Use this production Portal for real content. The Mac's localhost services and rehearsal database are separate development copies and do not synchronize their edits to AWS. See [the content-master policy](content-master.md).

Choose a short, stable **Site Name**, such as `fieldnotes`. This is an internal routing identifier, not the domain and not the display title. Prefer lowercase letters and digits; avoid spaces and punctuation. It must be unique across Guten. Decide it before creating the site; the normal Edit Site screen does not rename it. Section/page names also become address components, so choose them with lasting links in mind.

## 2. Create the site and its first content

On the dashboard, choose **Create a New Site**. These are the current form fields:

| Field | Example and purpose |
| --- | --- |
| Site Name | `fieldnotes` — the stable internal identifier. |
| Site Title | `Field Notes` — the reader-facing name. |
| Site URL | `https://example.com` — the intended public address. Use the root address without a page path. This metadata does **not** register a domain, change DNS or activate hosting. |
| Logo Location | `/assets/fieldnotes/logo-v1.png` — a file path agreed with the operator. Entering it does not upload a logo. |
| Favicon URL | `/assets/fieldnotes/favicon-v1.ico` — the small browser-tab icon, again requiring an installed file. |
| Color | `#245c45` — an example hexadecimal theme color. Display depends on the current renderer. |

Site Name and Site Title are marked required at creation. Prepare real image paths and a color if possible: the later Edit Site form also marks the URL, logo, favicon and color fields required. Do not invent a path and assume an image will be generated. If these assets are not ready, ask the operator for suitable installed placeholders.

Create the site, then follow **Manage Sections** to add sections and pages. At least one readable page is needed for a useful launch. Add titles, Markdown content and images, and use the ordering controls to arrange sections and pages. You do not need to assign numeric database IDs yourself.

After creating pages, use **Edit Site → Landing Page** to choose the page readers should see first. An explicit selection makes the intended home page clear. The alternative, **None (Auto-routed)**, leaves the choice to Guten's fallback routing.

Refs and Notes can be managed in Portal but are not currently rendered on the public site or draft pages. Theme/template assignments beyond the supported baseline are not part of this cookbook.

## 3. Supply images and arrange their installation

Portal currently stores image **references**, not uploaded files. A path such as `/assets/fieldnotes/welcome-v1.png` means “load this file from this website's assets directory.” It works on both the public site and authenticated draft preview when the shared file is installed.

Give the operator the files and their intended paths. Prefer a site-specific folder, lowercase filenames without spaces, and new filenames for revised artwork. For example:

| Use | Value to enter |
| --- | --- |
| Page's Image URL / Primary Image URL field | `/assets/fieldnotes/welcome-v1.png` |
| Image embedded in Markdown | `![A woodland path](/assets/fieldnotes/woodland-v1.png)` |

Do not enter a Mac path such as `/Users/...`, a `file://` address, or `localhost`. Readers cannot access your computer. Use a leading `/assets/` for shared Guten files. The operator must confirm that the exact filename, capitalization and extension exist.

**Images are shared between draft and published rendering.** Replacing an existing file can change the live site's appearance without pressing Publish. Use `welcome-v2.png` for a revision, point the draft to it, review it, then publish. Keep the old file while any draft or published page still references it.

For the operator: production files currently live under `/srv/guten/assets` on the app host, shared read-only by both frontends. They are outside container images and Git. The S3 bucket currently holds database backups, not site images. Follow [media packaging](media-packaging.md) and [host media installation](cloud-app-bootstrap.md#media-installation), with these production qualifications:

- Inventory **current AWS draft and published references**, not the old native Mac database. `package_media.py` uses PostgreSQL client connection settings and defaults to a local connection unless configured otherwise. Verify the connection target before running it; do not copy passwords into commands or documentation.
- A replacement media version must preserve files needed by existing sites, including published content no longer referenced by a newer draft. An inventory of only the new site's files is not a replacement for the whole shared directory.
- The current installer is a **first-install** tool: it refuses an existing active path. Subsequent media staging, verified version switching and frontend container recreation require an operator-planned update. There is not yet a one-command ongoing media-update workflow. Do not rerun the bootstrap example expecting it to overwrite live assets.
- Archive the source files and verified bundle separately. Database backups store references, not the image bytes. Keep the prior media version for recovery.

An editor's handoff can be as simple as: “Please install these three Field Notes files at these `/assets/fieldnotes/...` paths and confirm when they are available in View Draft.”

## 4. Review the draft and publish deliberately

Choose **View Draft** from the dashboard. Check the home page, text, menu order, page links and images. A draft preview requires Portal login; it is not an anonymous review link.

When the saved content is ready, choose **Publish** and review the confirmation. This makes the site's current draft the published version, including ordering changes and deletions. It affects that site, not every site in Guten. If someone changes the draft during confirmation, refresh the publication status and review again.

For a first launch, coordinate this with the operator **before public activation**. Publishing prepares the content but does not make an unconfigured domain reachable. **View Published** can appear after publication yet return “No public domain configured for this site” until the operator deploys the mapping. Once the domain is live, later ordinary text changes need only Save → View Draft → Publish; no DNS change or container rebuild is needed.

**Unpublish** removes the published content while preserving the draft. It does not remove DNS records, deactivate the configured hostname or delete image files.

## 5. Understand the two DNS records

The **registrar** is where the domain is registered and renewed. The **DNS provider** runs the nameservers that answer where it points. They may be different companies: a domain registered at Namecheap can use Cloudflare DNS. Edit records at the active DNS provider, not necessarily the registrar.

For the existing Guten deployment, the operator-confirmed app-host IPv4 address is **52.54.75.169** as of September 19, 2026. Confirm it before a future launch. Do not use the database host's address or create a new server for each domain.

| Record type | Host / Name | Value / Target | TTL |
| --- | --- | --- | --- |
| A | `@` | `52.54.75.169` | Automatic / Auto |
| CNAME | `www` | `example.com` | Automatic / Auto |

`@` means the bare domain (`example.com`). An **A record** gives its server's IPv4 address. A **CNAME** makes `www.example.com` an alias of the root domain for DNS lookup. Neither value should contain `https://`, a port or a page path. Some consoles display a final dot (`example.com.`); that is normal.

The CNAME itself does not redirect the browser's address bar. Guten's web gateway performs the redirect from `www` to the preferred root address, preserving the page path. It also redirects HTTP to HTTPS. **TTL** is how long DNS answers may be cached; Auto is suitable here. Old answers can remain until their earlier cache lifetime expires.

### Namecheap example

1. Open **Domain List → Manage** for your domain. Check **Nameservers**. If it already uses **Namecheap BasicDNS**, leave that setting alone.
2. Open **Advanced DNS → Host Records**. Save the previous records (including values, TTLs and redirect settings) for rollback.
3. When the operator says the release is ready, replace the parking/forwarding records for `@` and `www` with the two rows above. A stock setup often has `www` pointing to `parkingpage.namecheap.com` and an unmasked URL Redirect for `@`; remove/replace those conflicting website entries.
4. Save both records. Check for an old **AAAA** record on the same names: it directs IPv6 visitors elsewhere. Have the operator resolve any conflict; this setup does not call for adding an IPv6 record.

Do not change nameservers merely to enter an IP address. If the domain still uses another provider's nameservers, either edit there or arrange a deliberate DNS-provider move first. Switching to BasicDNS may leave an empty zone; it does not automatically copy records. A registrar transfer can also preserve the old nameservers. Review existing mail/verification records and DNSSEC with the operator before a provider switch. For a new person's domain, do not assume the obsolete-email exception from the original Guten rollout applies.

Namecheap's [record-type guide](https://www.namecheap.com/support/knowledgebase/article.aspx/579/2237/which-record-type-option-should-i-choose-for-the-information-im-about-to-enter/) explains these fields; use the Guten values above rather than a hosting provider's sample IP.

### Cloudflare example

Keep the existing Cloudflare nameservers. Under the domain's **DNS → Records**, use the same root A and www CNAME records, with **DNS only** (gray cloud) and Auto TTL for both. This is the tested Guten configuration: DNS sends visitors directly to the AWS host, where Caddy handles HTTPS. Cloudflare's [proxy-status explanation](https://developers.cloudflare.com/dns/proxy-status/) describes the distinction.

If the old website uses Cloudflare Pages, record its CNAME targets before replacing them. Keep the Pages project available for rollback. A Pages-managed record may require handling through its custom-domain settings; ask the operator rather than deleting the project. Preserve unrelated records.

## 6. Operator handoff: activate the hostname and HTTPS

Send the operator the internal site name, preferred domain, requested `www` alias, DNS provider, old record snapshot and confirmation that content/images are ready.

The operator must:

1. Add a mapping to a **new cumulative domain manifest**, preserving all existing publications and Portal. The live baseline at this writing is `deploy/domains.batch9.json`; verify the latest successful release before copying it. The new entry for this example is:

   ```json
   { "host": "example.com", "site": "fieldnotes", "aliases": ["www.example.com"] }
   ```

2. Check that the mapping matches the actual site name and published content. Prepare and privately test an immutable release using [the release runbook](releases.md). Domain-only changes can reuse compatible pinned application images; they do not require new per-site containers, a new database or a new Lightsail instance.
3. Coordinate the DNS change, verify the authoritative records and public resolver answers, then deploy the prepared release. Caddy obtains and renews HTTPS certificates for the configured names. DNS alone does not create a certificate, and this setup does not require buying a separate certificate or adding Certbot.
4. Verify trusted HTTPS, root/www and HTTP redirects, landing page, images, navigation, direct-page reload and existing-site/Portal regression. Retain deployment evidence and the previous release. Record the new live manifest in the README.

Do not edit an already packaged release in place or restore a database dump to activate a domain. A first-time launch can have a short interval between DNS reaching AWS and HTTPS activation; coordinate the work instead of assuming an instant switch.

## 7. Accept the launch and keep it maintainable

Open the root address and its `www` form on a phone and a computer. Confirm they end at the intended HTTPS site, then follow page links and check images. Verify **View Published** in Portal as well. Report any failure to the operator with the exact URL and error.

If one device still sees the old site, it may be cached DNS. If all devices fail, the operator should check delegation, records, certificates and routing; waiting alone does not fix a missing server mapping. Do not repeatedly change correct records while caches settle.

Keep domain renewal/payment details current. Store the launch mapping and procedures in Git; store credentials, database archives and original images separately. Confirm scheduled database backups and monitoring remain healthy, and retain media backups too. Adding this site does not itself require new AWS infrastructure, but content growth still consumes shared disk and traffic capacity.

For future edits: use production Portal, save, preview and publish. For new files: arrange the media update first. For a domain change or retiring a site: coordinate DNS and the deployed mapping with the operator; changing Site URL or pressing Unpublish is not a complete infrastructure change.

## If you do not have a domain yet

You can create content and use authenticated **View Draft** in Portal. There is currently no anonymous public directory, IP-based preview, or public `guten.ink/fieldnotes` fallback for arbitrary sites. Local development URLs are not shareable production hosting.

An operator could assign a subdomain of an owned domain, such as `fieldnotes.guten.ink`, with owner approval, DNS and an explicit deployed mapping. That avoids purchasing a separate domain, but it is not automatic or currently allocated by Portal.
