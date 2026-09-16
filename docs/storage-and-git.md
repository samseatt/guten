# Storage and Git conventions

## What belongs where

| Material | Working location | Versioning / backup |
| --- | --- | --- |
| Source, migrations, schema definitions, scripts, configuration examples, docs | Git repositories | Local Git commits, then deliberate remote pushes |
| Live site content | guten_datalake | Timestamped full database archives; Git is not the content backup |
| Database dump archives | Ignored guten-datalake/db_dump or explicit ARCHIVE_ROOT | Copy complete archive directories to separate storage; verify SHA-256 checksums |
| Site images and uploaded media | Currently each frontend's ignored public/assets | Archive both trees with paths intact; future S3 object storage |
| Small application icons and design assets maintained with the code | Tracked public files / source | Git is appropriate |
| Credentials, local.mk, logs, dependencies, generated builds | Ignored local files | Recreate builds/dependencies; manage credentials separately |

An ignored folder may remain inside a repository. Moving it outside is optional, not required for Git hygiene. Ignore rules do not untrack already committed files, so check the index before committing. Do not blanket-ignore all SQL or all PNG files: schema/migration SQL and small application artwork may legitimately belong in Git. Use explicit staging instead of git add . for these multi-repository changes.

The coordination repository and four service repositories have independent histories; commit each affected repository separately. Either the developer or Codex can make local commits. Codex may make scoped local commits when requested; pushes, deployment, and sharing remain distinct actions. Git commits are not backups of ignored content.

## Practical backup routine

1. Run make backup before database migrations and after substantial content editing.
2. Copy the whole completed database archive, including SHA256SUMS, to the archive storage.
3. After adding/changing media, copy both guten-sites/public/assets and guten-portal/public/assets into the same dated archive, preserving relative paths. Stop media editing during the copy and verify source/archive hashes. Do not use a deletion-mirroring sync against historical backups.
4. Retain dated archives rather than overwriting the only good copy. Keep a further off-device/off-site copy where practical.
5. Rehearse database restoration periodically. Restore image trees alongside the repositories on a new machine. A fresh Git clone alone cannot recreate the current content sites.

The verified archive supplied on 2026-09-16 is located under /Volumes/macext/archive/guten_archive_2006-09-16. The directory really uses 2006 in its name; it was not renamed. This path is an archive location, not an application dependency.

## Image URLs: preserve the current contract

Keep serving local files from public/assets while native development continues. Do not remove or relocate them until a replacement serving path is working. Archive folder paths and local disk paths must never become browser URLs.

For the first AWS deployment, prefer the existing root-relative URL contract, for example /assets/example.png:

- Local: Next.js serves public/assets/example.png.
- AWS: CloudFront routes /assets/* to an S3 origin; the object key remains assets/example.png. Other routes go to the application origin.
- Keep the S3 bucket private and grant CloudFront origin access control access. Visitors can still view public site images through CloudFront.

This avoids embedding bucket names or environment variables into stored Markdown. The same relative URLs can work across environments and custom domains when their distributions implement the same route. This is a proposed deployment design, not implemented infrastructure.

If a dedicated media hostname later becomes preferable, introduce one media URL resolver with an environment-configured public base URL. Apply it to Markdown images as well as primary_image, logo, and favicon fields. An environment variable alone cannot rewrite stored Markdown. Do not save signed/expiring download URLs as permanent content references, and never expose AWS credentials through frontend configuration.

Preserve existing object paths during migration. Use a site namespace and unique/versioned filenames for new uploads (for example assets/sites/<site-id>/<unique-id>.png) to prevent collisions and avoid stale CDN content when images change. Audit current local, absolute, and external references before migration.

Enable S3 versioning for future media storage to retain earlier object versions; maintain a separate backup/retention policy rather than treating the serving bucket as the sole archive. No S3 upload or account change is part of this cleanup.

Primary AWS references:
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesCacheBehavior.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html
