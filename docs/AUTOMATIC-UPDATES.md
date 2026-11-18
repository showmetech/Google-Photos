# Automatic desktop updates

The independent desktop edition can register a per-user Windows task using
`scripts/release.ps1 -EnableAutomatic`. The task invokes the same release entry
point with `-Automatic -Install` at sign-in and every six hours. It uses an
independently installed PowerShell host; it does not require Codex, GitHub login,
stored credentials, administrator rights, or a change to script execution policy.
The machine must already permit local scripts in that host.

The updater accepts only a newer stable release from `showmetech/Google-Photos`,
bound to an exact commit, with the expected EXE installer and SHA256SUMS asset.
Before installation it requires a successful `release.yml` run for that commit
including `build`, `github-release`, and `microsoft-store`. A missing Store
submission or failed publication blocks installation. SHA-256 validates the
download against the manifest from that same trusted repository; it is not an
independent publisher signature.

Uploads defer the update. The updater rechecks immediately before requesting a
clean app exit, verifies a rollback copy, invokes the regular installer, audits
the installation, and checks the new service and tray. Failed updates retain
evidence and attempt rollback without interrupting an active upload. User state
stays outside Programs. Only unique updater-owned download directories are
deleted; rollback backups are retained.

Status is saved in the user's `GooglePhotosUploader/data/desktop-update-status.json`.
`publication_unavailable` means the stable distribution channel is not ready; it
must not be reported as a successful update or as proof that a version is current.
Network or publication failures remain visible as `blocked`. Only stable public
releases are installed; source commits and build artifacts alone are insufficient.

The Windows task is named `Google Photos Uploader - Updates`. It runs only in
the current user's interactive session with limited privileges and ignores
overlapping invocations. To pause independent updates, disable this specific
task in Task Scheduler. Do not disable Microsoft Store or Windows updates.

For a Store-installed edition the updater reports `store_managed` and does not
run the independent installer. Microsoft Store manages that edition's updates.
Installing the EXE or merely uploading a package to GitHub does not enroll an
installation in Store-managed updates. See Microsoft's documentation:
https://learn.microsoft.com/windows/msix/app-installer/app-installer-file-overview

Verification covers stable/version/origin/checksum/workflow guards and active
worker deferral with local fixtures. A first live automatic upgrade still needs
a newer published release with all publishing gates satisfied. Certification,
public availability, and local installation are separate states.

