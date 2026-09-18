# Guten bootstrap provisioning and cost review

Prepared September 18, 2026. Status: planning only; no resources, budgets, subscriptions, DNS records or access policies have been created. The `guten-audit` CLI session was refreshed and verified as account `983732020946`, assumed role `GutenAudit`, in `us-east-1`. Resource inventory is recorded below. Budget and quota visibility require a separate Admin console check; unavailable data must not be treated as zero costs or unused quota.

## Planned resource allowlist

| Resource | Proposed name / configuration | Recurring basis |
| --- | --- | --- |
| Application Lightsail instance | `guten-app-01`, `medium_3_0`, Linux x86, 4 GB RAM / 80 GB disk, public IPv4 | USD 24/month maximum bundle price |
| Database Lightsail instance | `guten-db-01`, `small_3_0`, Linux x86, 2 GB RAM / 60 GB disk, public IPv4; PostgreSQL only on private interface | USD 12/month maximum bundle price |
| Lightsail static IPv4 | `guten-app-ip`, attached immediately to application instance | No extra charge while attached |
| S3 backup bucket | Suggested `guten-backups-983732020946-us-east-1`; availability/ownership to verify | Storage, requests and applicable transfer; usage based |
| Budget notifications | Proposed USD 50/month Guten planning threshold | Monitoring/notifications free; no paid reports/actions planned |

The live API confirms both bundle IDs and prices. Use the available `ubuntu_24_04` OS-only blueprint (Ubuntu 24.04 LTS) and proposed zone `us-east-1a` for both hosts. All six Virginia Lightsail zones currently report available; recheck at creation time. No commitments, reserved capacity or reliance on introductory free trials. The USD 36/month sum is only the two new instances, not the account's total bill. Stopped Lightsail instances continue to incur charges. Unattached static IPs have an hourly charge after the documented grace period.

No RDS, Lightsail managed database, load balancer, NAT gateway, Kubernetes, CloudFront distribution, additional block disks, managed secrets service, customer-managed KMS key, paid observability subscription or additional AWS staging host is in this bootstrap plan. Caddy serves the publication domains and Portal on the application host. The database host's included public IPv4 is not an authorization to expose PostgreSQL publicly. Existing EC2/S3 resources remain untouched.

## Storage and media

Create a private backup bucket separate from existing projects, with Block Public Access, SSE-S3 encryption, versioning, HTTPS-only access and narrowly scoped upload/recovery permissions. Store encrypted database archives and dated media backups under distinct prefixes. Keep the age recovery key off the servers and outside this bucket.

The current unfiltered local Sites assets tree contains 2,946 files totaling 4,269,382,717 bytes (about 4.27 decimal GB). This is a sizing upper bound, not the deployment manifest: it includes unused files. All currently retained local database dump-directory files together total about 12 MB; this is not a measured future daily growth rate. Inventory referenced draft/published/Markdown/media files before copying. Avoid blindly making a new complete unchanged media copy every day.

Use S3 Standard initially to keep retrieval straightforward. Estimate retained bytes, object operations and recovery downloads before setting lifecycle rules; include noncurrent versions and incomplete multipart uploads. Proposed starting retention is 30 daily DB archives plus a separately retained monthly archive for six months, subject to implementing and rehearsing that retention workflow. Media retention should preserve independent recovery copies without repeatedly duplicating an unchanged tree. These rules are not enabled yet; never age out the only verified recovery copy.

For now, serve images from `/srv/guten/assets`, mounted read-only as each frontend's `public/assets`. S3 is off-host backup, not an image-serving dependency. A separate private media bucket plus an appropriate delivery layer can be introduced later. No CDN or image delivery resources are provisioned at this stage.

## Cost controls and current user preference

User decision, September 18: existing account spending is USD 1.55 month-to-date with USD 2.67 forecast. Proceed using manual Admin billing monitoring; automated budgets/alerts below are deferred proposals, not a prerequisite or configured protection. Full-month working subtotal with the two hosts is USD 38.67 before new backup/usage/tax and changes in existing resources.

1. Inspect current resources and existing budgets. Establish the pre-Guten billing baseline separately; stopped EC2 disks/snapshots and existing buckets can still contribute costs. A Virginia inventory is not proof that other regions are empty.
2. Configure a proposed USD 50 monthly Guten alert budget with actual-spend notifications at USD 25, 40 and 50 and a forecast alert at USD 50 when available. Agree the recipient and verify delivery. Activate/validate cost allocation tags before relying on a Guten-only filter; use an account-wide budget adjusted for the existing baseline as a backstop. Existing S3 charges must not be confused with new Guten charges.
3. Use fixed resource counts/names and reviewed bundle IDs in provisioning. Refuse duplicate creation, unexpected accounts/regions or larger bundles. Treat this as a script safeguard, not a universal AWS spending ceiling.
4. Restrict the provisioning role to the needed resources/services and region. `GutenAudit` stays read-only. Do not install administrator credentials on the servers or deploy agents with authority to purchase arbitrary services.
5. Keep container logs rotated locally; do not enable unbounded centralized log ingestion. Keep the single static IP attached. Add no snapshots, monitoring subscriptions or retention expansion without including their costs in the plan.
6. Verify S3 uploads and restore, then enable bounded retention and backup failure/disk-space reporting. Review billing after first provisioning and again after several days of usage; record any difference from the plan.

AWS Budgets notifications can lag billing data and do not impose a hard cap. Forecasts may be unavailable without enough history. AWS documents a newer project spend-limit experience with limited availability; eligibility and coverage for this existing account/Lightsail plan are not established, so we must not count on it. No automatic project termination or data-deleting budget action is proposed.

The practical protection is a small fixed architecture, explicit resource creation, limited permissions, retention, usage alerts and follow-up billing review. The USD 50 threshold is a warning level, not a guaranteed maximum. Taxes, currency conversion, excess transfer and existing resources are outside the USD 36 instance subtotal. S3's usage-based component needs a retained-data estimate and monitoring; we have not represented it as a fixed price.

## Read-only inventory command

```bash
aws login --profile guten-audit --remote
python3 scripts/audit_aws.py
```

The script checks account `983732020946` and assumed role `GutenAudit` before inventory. It reads Virginia Lightsail instances/bundles/OS blueprints/static IPs/snapshots, EC2 instances/EBS/addresses, global S3 bucket names and available budget summaries. Reports are private, ignored files under `artifacts/`. No object contents are downloaded, no Cost Explorer queries are made, and no resources are modified. Permission failures are recorded as unavailable, not as zero resources or zero spending. CLI login is interactive; credentials/tokens stay out of chat and Git.

After inventory: resolve the exact OS/bundle IDs and current quotas, prepare narrow provisioning permissions and repeatable host/firewall setup, finalize budget recipient/filters and the concrete creation commands, then proceed through the reviewed resource plan. Host provisioning, real S3 upload, backup notifications, retention and public-domain release testing remain subsequent steps.

## Sources checked September 18, 2026

- [Lightsail current bundle pricing](https://aws.amazon.com/lightsail/pricing/)
- [Lightsail billing and static IP charges](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html)
- [S3 usage pricing](https://aws.amazon.com/s3/pricing/)
- [AWS Budgets monitoring pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/)
- [Budget alert delays](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [Budget update frequency and forecast history](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html)
- [Limited-release project spend limits](https://docs.aws.amazon.com/accounts/latest/reference/create-spend-limit.html)

## Verified inventory — September 18, 2026, 19:06 UTC

Private report: `artifacts/aws_audit_20260918T190648Z.json`.

- Identity: `arn:aws:sts::983732020946:assumed-role/GutenAudit/Admin`. The final `Admin` is the role session name; the active permissions are GutenAudit.
- Virginia Lightsail: zero instances, static IPs and instance snapshots.
- Selected bundle prices: `medium_3_0` USD 24/month; `small_3_0` USD 12/month. OS-only `ubuntu_24_04` is available.
- Virginia EC2: three stopped t2.micro instances, three attached gp2 volumes totaling 26 GB, no Elastic IP allocations returned. This is existing infrastructure, not new Guten cost.
- Five existing S3 buckets returned by the global list; no dedicated Guten bucket exists in this account inventory. This does not establish global availability of the proposed bucket name.
- `budgets:ViewBudget` was denied; existing budgets, subscribers, current spending and forecast remain unknown.
- `servicequotas:ListServiceQuotas` was denied; no assumption about the account's actual Lightsail quota was made.
- Follow-up Lightsail region query confirmed `us-east-1a` through `us-east-1f` available. This does not reserve capacity.

Admin in a separate Chrome browser can be used for billing review and later deliberate provisioning, while Safari/CLI retain the audit role. The CLI profile must not be overwritten with Admin. Console sign-in may need an IAM billing-access prerequisite; if the Admin billing page is denied, inspect that prerequisite rather than switching the agent's profile to root.

Step-one billing input received: USD 1.55 month-to-date and USD 2.67 forecast. User will monitor Admin billing manually for now and defer new automated budgets/alerts. No budget or hard cost cap was enabled. Initial infrastructure creation is prepared as a reviewed CloudFormation stack launched in Admin CloudShell; see [creation procedure](create-infrastructure.md). The local CLI retains the read-only audit identity.
