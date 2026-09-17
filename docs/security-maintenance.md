# Dependency security maintenance

The September 17, 2026 update keeps Next.js on its existing major: Next and eslint-config-next 15.5.25, React/React DOM 19.3.0. Crust retains Express 4 and receives compatible dependency fixes. Datalake advances FastAPI to 0.141.1 and Starlette to 1.6.0 with compatible audited dependencies. Python requirements remain locked; requirements.in records supported bounds and a Starlette security floor.

Both frontends override Next's bundled PostCSS to 8.5.28 and the old brace-expansion 1.x line to 1.1.21. Keep these targeted overrides until the parent packages incorporate fixed dependencies; remove them only after fresh installs, audits, builds and regression tests pass. Do not use npm audit fix --force as a routine upgrade command. The lockfiles, not an existing node_modules directory, must reproduce the fixes.

## Re-run audits

Use a separate tooling environment; no audit packages are added to application containers:

```bash
python3 -m venv .venv-security
.venv-security/bin/python -m pip install -r requirements-security.txt
make security-check SECURITY_PYTHON=.venv-security/bin/python
```

The command audits the coordination repository, all three Node applications and the locked Python application dependencies. It returns failure for reported advisories or audit-tool/network failures and retains JSON reports under ignored artifacts/security_*. It does not update dependencies. Audits are a point-in-time check of known package advisories; they do not certify application logic or operating-system image security. Container image/OS scans and PostgreSQL's major-version lifecycle must also be checked before cloud release.

After dependency edits, install from the lockfiles and run make check, make acceptance, make docker-build and make docker-test. Run make docker-test-lifecycle when packaging changes. The native acceptance suite uses a disposable database; Docker tests use only guten_compose_test_local. Existing img-element performance lint warnings are unrelated to dependency security and remain intentional pending the media delivery work.

Reference: [Next.js August 2026 security release](https://nextjs.org/blog/august-2026-security-release).

## Recorded verification — September 17, 2026

- Native acceptance: 17 Python configuration/integration tests and 3 browser workflows passed (`artifacts/20260917T110201_729d885e38`).
- All five application/tooling dependency audits passed with no known advisories (`artifacts/security_20260917T112130`).
- Final Docker images built successfully. Authentication checks, all 3 authenticated browser workflows, upstream replacement and page/API fail-closed checks passed (`artifacts/auth_20260917T113955_a070ca43`).
- Non-root isolation, shared read-only PNG delivery and persistence across application/database container replacement passed (`artifacts/compose_lifecycle_20260917T113705_997c0ba1`).

Paths are relative to the coordination repository; reports are intentionally ignored and can be archived separately. Tests use disposable/rehearsal databases and synthetic content. Real GitHub consent and the owner login are a separate manual verification step described in authentication.md.
