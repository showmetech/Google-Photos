# Release requirements

This repository is the distribution source for Google Photos Uploader. Preserve existing user media, account client, databases and receipts. Never commit or package user data, Google authorization or local configuration.

Every desktop release must also update reviewed source on GitHub and run `.github/workflows/release.yml`. Use `scripts/release.ps1`; do not silently copy developer binaries into production. Preserve the distinction between GitHub publication, Store submission, certification, public Store availability and local installation. If Store access or certification is blocked, report that exact state rather than claiming all channels are synchronized.

Do not restore historical local source over this repository. Reconcile subsequent changes here first. Do not create a recurring Codex inspection; background health and uploads are owned by the application.

After every installer or explicitly authorized desktop hotfix, run scripts/audit-installation.ps1 and verify runtime health before declaring completion. Keep all user state and rollback backups in the per-user GooglePhotosUploader directory, never in Programs. Archive verified legacy items reversibly with a receipt; never delete unknown files, media, credentials, source checkouts or user backups as generic cleanup.

## Interface changes

For UI changes, consult the applicable Fluent 2 foundations and component guidance recorded in docs/FLUENT2-REVIEW-2026-11.md. Update that coverage matrix with the implementation, tests and explicit gaps. Preserve keyboard focus, Windows text scaling, high contrast, reduced motion and responsive reachability; do not claim a WPF theme is a WinUI migration or that isolated checks prove live account/Store behavior.
