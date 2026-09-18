# Create the Guten bootstrap infrastructure

This is the first billable infrastructure step. It creates the reviewed two Lightsail hosts (USD 36/month combined), an attached static IP and a private S3 backup bucket. Usage-based storage/requests/transfer and tax are additional. No database content, application containers, DNS changes, registry uploads or budget subscriptions are part of this stack.

The user reported USD 1.55 month-to-date and a USD 2.67 forecast for the existing account on September 18, 2026. The working full-month account baseline after adding the two hosts is therefore USD 38.67 before Guten backup/usage/tax and changes in existing resources. The first partial month is prorated. The user chose manual billing monitoring in Admin for now; automated budgets/alerts are deferred, and no hard spending cap is in place.

## Prepared files and access

The source-controlled generators are `scripts/prepare_infrastructure.py` and `scripts/prepare_infrastructure_launcher.py`. The prepared local launch file is:

```
/Users/samseatt/projects/guten/guten/.cloud-provision/launch-guten-bootstrap.sh
```

This file embeds the template and creation request, including only the **public** SSH key and permitted public source IPv4. The separate private key is `.cloud-provision/guten-cloud`, mode 0600 inside a mode-0700 ignored directory. Keep that private key on the Mac and back it up securely; never upload it to CloudShell, S3 or Git. The `.pub` file and generated template are also local/ignored. No existing SSH key/config was modified.

The generated template's SSH CIDR corresponds to the Mac's public IPv4 when prepared. If the ISP/VPN address changes, regenerate the template or deliberately update the `AdminIpv4Cidr` stack parameter. The initial policy permits SSH from that one IPv4 address; Lightsail's browser SSH source ranges are not opened. Verify actual IPv4/IPv6 firewall rules after creation before continuing host setup.

The local `guten-audit` profile remains read-only. Initial creation runs in your Admin browser's CloudShell session, so no Admin credentials are added to the Mac or given to the local deployment tooling. This replaces the need for a new local provisioning role for the one-time stack launch. A narrowly scoped deployment identity can be added later if useful.

## Launch in Chrome's Admin session

1. Select account `983732020946`, region **US East (N. Virginia) / us-east-1**.
2. Open **CloudShell** using the console terminal icon. Use its standard regional environment, not a new VPC environment.
3. Choose **Actions → Upload file → Browse**. In the Mac file picker, press **Command-Shift-G**, paste the full launch-file path above, select it and upload. Upload only the `.sh` file, not the directory or private key.
4. In CloudShell run:

   ```bash
   bash ~/launch-guten-bootstrap.sh
   ```

5. The script checks the account, existing stack/resource names and live bundle prices/specifications, then asks AWS to validate the template. It stops on failed checks. Only after those checks does it issue `create-stack` for `guten-bootstrap` in Virginia. It prints the StackId and returns while AWS creates resources.
6. Open CloudFormation in Virginia and check **guten-bootstrap → Events / Outputs**. `CREATE_COMPLETE` means AWS finished resource creation, not that SSH launch scripts or application readiness have been proven. The next step checks those separately. On failure, preserve the events/error text and inspect remaining resources rather than creating differently named duplicates.

CloudShell itself has no additional service charge; resources created through it are billed normally. Unlike console template upload, the script passes the template directly in the create request and does not upload an extra template object to S3.

## Exact stack contents

| Logical resource | AWS resource |
| --- | --- |
| ApplicationHost | `guten-app-01`, Ubuntu 24.04 LTS, `medium_3_0`, us-east-1a, public TCP 80/443 and restricted TCP 22 |
| DatabaseHost | `guten-db-01`, Ubuntu 24.04 LTS, `small_3_0`, us-east-1a, restricted TCP 22 only |
| ApplicationIp | `guten-app-ip`, attached to `guten-app-01` |
| BackupBucket | `guten-backups-983732020946-us-east-1`, Block Public Access, disabled ACLs, SSE-S3 encryption, versioning |
| BackupBucketPolicy | Deny non-TLS S3 access |

There are five CloudFormation resources, including the bucket policy. The bucket/policy are created before either billable host, so a bucket-name/permission failure does not first start the hosts. Existing unrelated resource names are never adopted. Wrong account is refused by the launcher; the template also conditions all resources on the agreed account/region. A regional Lightsail default SSH key may be used by AWS in addition to the dedicated public key installed by launch scripts; it is not a new paid service.

The only lifecycle cleanup enabled is aborting incomplete multipart uploads after seven days. Completed archives, media and noncurrent versions are not expired by this template. Configure/test their retention when backup upload is in place. No snapshots, extra disks, RDS, load balancers, CDN, NAT gateway, KMS key or paid monitoring subscription is created.

The launch script only installs the dedicated SSH public key and writes a host-role/status marker. Docker, private host firewall rules, TLS keys, PostgreSQL and the applications are subsequent steps. PostgreSQL is not exposed publicly or started by this template.

## Deletion and replacement protections

Stack termination protection is enabled. The stack policy blocks updates that delete/replace the database host or backup bucket. These are operational safeguards, not spending caps.

The database host and backup bucket use `RetainExceptOnCreate`: newly created resources are eligible for cleanup if the initial creation rolls back, while a later deliberate stack deletion retains established data-bearing resources. Application host/static IP are not retained on stack deletion. **Deleting the stack is not a complete billing shutdown**: retained database hosts/storage can continue billing. Before decommissioning, verify off-host recovery copies, explicitly inventory retained resources, and deliberately remove only resources that are no longer needed. Do not disable protection/delete a working stack to solve a transient deployment issue.

## Validation and follow-up

Six local tests passed, covering fixed resource inventory/bundles, private bucket settings, port restrictions, public-key validation, launch-shell syntax, and refusal of wrong accounts, duplicates, permission errors and changed prices. The launcher tests use a fake AWS CLI and create no cloud resources. AWS `cfn-lint` also passed against the generated template. After refreshing and verifying the audit login, AWS denied `cloudformation:ValidateTemplate` because GutenAudit lacks that permission. The Admin launch script performs AWS validation before creation; no audit-role permission expansion is required. Local validation is not a guarantee of live account quotas/provider behavior.

After creation: refresh `guten-audit` using `aws login --profile guten-audit --remote`; verify the stack outputs, instance specs, actual firewall rules, bucket policy/encryption/versioning and IP attachment; verify SSH host keys and launch completion; then install/configure Docker and private database networking. The read-only agent session must remain GutenAudit even while Chrome is signed in as Admin.

Sources:
- [Lightsail CloudFormation instance](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lightsail-instance.html)
- [CloudFormation deletion policies](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html)
- [CloudShell file upload](https://docs.aws.amazon.com/cloudshell/latest/userguide/getting-started.html)
- [CloudShell pricing](https://aws.amazon.com/cloudshell/pricing/)

## Initial live verification — September 18, 2026

Stack `guten-bootstrap/49a97500-b3b9-11f1-9176-120c6f6718cf` reached CREATE_COMPLETE with termination protection enabled. Live inventory confirms Ubuntu 24.04, us-east-1a, the 4 GB/80 GB app host and 2 GB/60 GB database host. `guten-app-ip` is attached to the app host. Application private IP: `172.26.5.8`; database private IP: `172.26.4.118`.

Actual firewall rules were verified through `GetInstances`: application TCP 80/443 public, TCP 22 restricted to the prepared /32; database only TCP 22 restricted to the same /32. No IPv6 public-port CIDRs are present. The bucket exists as a stack output, but independent encryption/versioning/policy inspection was denied by the audit role and remains pending.

Both SSH connections reached the hosts but rejected the dedicated bootstrap key. The stack's public-key parameter matches the local public key and the API confirms username `ubuntu` and regional `LightsailDefaultKeyPair`. Startup logs must be inspected using the existing regional default key before diagnosing or modifying the launch script. No recreation is planned. First-seen SSH host keys were pinned in ignored `.cloud-provision/known_hosts`; they have not been independently compared against console-provided fingerprints. No Docker installation, database import or application launch has occurred.


### SSH bootstrap repair

The regional default key successfully accessed both hosts. Their cloud-init logs showed `set: Illegal option -o pipefail`: Lightsail prepended an `sh` wrapper, so the embedded Bash shebang did not select Bash. The generated launch commands now use POSIX `sh` and `set -eu`.

The corrected commands were applied through `sudo sh` on both existing hosts, preserving the default authorized key. Fresh SSH connections using the dedicated Guten key then succeeded, and the application/database role markers were verified. No instances were recreated. Cloud-init's original error remains historical evidence; the repair did not rerun all cloud-init modules or erase its status. The already-created CloudFormation template still contains the original launch commands; the source fix applies to future generated templates, not a stack update or host replacement.

Seven local infrastructure tests pass, including executing the launch commands under an `sh` wrapper twice, checking key preservation, deduplication, permissions and role markers. Ownership operations alone are substituted in the unprivileged local test; the real commands succeeded on both hosts. Both hosts report x86_64 and ample free disk space. Docker, database restoration and application deployment remain pending.

The downloaded default private key was secured with mode 0600 and copied into ignored `.cloud-provision/`. Its Downloads copy also has mode 0600. Neither private key belongs in Git or a deployment archive.
