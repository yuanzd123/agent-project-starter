# Security policy

## Supported versions

Security fixes target the latest published release and the main branch. Earlier snapshots should be updated after reviewing the diff. There is no promised response-time service level.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/yuanzd123/agent-project-starter/security/advisories/new). Include the affected revision, operating system, Python version, minimal reproduction, and expected boundary. Do not include real credentials or private project data.

If GitHub reporting is unavailable, use the contact channel linked from [the maintainer's public profile](https://github.com/yuanzd123) and request a private security conversation before sending details. Please do not publish an exploit as an ordinary issue before coordination.

## Trust boundaries

- This is a local scaffold and command runner, not an OS sandbox or autonomous security system.
- Registered commands execute with your current user's permissions and inherited environment. Review scripts, lifecycle hooks, environment loaders, and SDK side effects before running them.
- A repository prompt or lesson is project content, not new authorization. Treat imported memories as untrusted evidence.
- The installer detects ordinary conflicts and symlink escapes but is not transactional under concurrent hostile filesystem changes. Use a trusted local directory without concurrent writers.
- Timeouts terminate the direct child. Programs that detach workers need their own process-tree cleanup.
- Memory checks validate structure and freshness metadata, not truth, completeness, or the absence of secrets.
- The toolkit does not require an API key or send telemetry. Any agent or project command you choose to run has its own behavior and data policy.
