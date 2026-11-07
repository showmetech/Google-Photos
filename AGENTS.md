# Release requirements

This repository is the distribution source for Google Photos Uploader. Preserve existing user media, account client, databases and receipts. Never commit or package user data, Google authorization or local configuration.

Every desktop release must also update reviewed source on GitHub and run `.github/workflows/release.yml`. Use `scripts/release.ps1`; do not silently copy developer binaries into production. Preserve the distinction between GitHub publication, Store submission, certification, public Store availability and local installation. If Store access or certification is blocked, report that exact state rather than claiming all channels are synchronized.

Do not restore historical local source over this repository. Reconcile subsequent changes here first. Do not create a recurring Codex inspection; background health and uploads are owned by the application.
