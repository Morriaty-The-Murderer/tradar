# Security Policy

## Reporting A Vulnerability

Please do not open a public issue for a sensitive vulnerability. If the GitHub repository has private vulnerability reporting enabled, use that channel. Otherwise, contact the maintainer privately.

## Data Sensitivity

Tradar reads local agent sessions, project documents, and git traces. Generated reports may include summaries or excerpts from private work.

Do not publish:

- raw agent sessions;
- generated run directories;
- local SQLite databases;
- `.env` files;
- unredacted reports;
- real machine-specific config files.

## Maintainer Checklist

Before publishing a release or accepting a PR, check for:

- credential-like strings;
- private local paths in examples;
- generated run artifacts;
- internal planning notes;
- stale references to old package names.
