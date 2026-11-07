# Google Photos Uploader

Windows 11 desktop photo/video upload manager: a compact tray widget, settings panel, local receipts, one background worker and app-owned UI recovery. Independent project; not an official Google product.

## Installation and setup

Use the installer from Releases, or the Microsoft Store once a certified listing is available. Windows 11 x64 is supported; the ARM64 UI is compiled natively and currently uses an x64 Python/rclone backend through Windows 11 emulation. ARM64 hardware validation is still pending.

The runtime is bundled: users do not need Python or .NET installed. In Settings, review detected Windows Pictures/Videos folders, choose any non-overlapping folders, import your own desktop OAuth client and authorize your Google account. A new installation starts with automatic uploading disabled until configuration is explicitly saved. No developer account, photos or authorization token is included.

Google Photos restricts API access to content created through the authorized application. The app cannot reconcile arbitrary old albums online or guarantee uploads to albums created by another application. It records confirmed per-file results and blocks invalid/empty local originals. Existing-library declarations require explicit confirmation.

UI translations: Portuguese, English and Spanish; other languages use English fallback, with locale-aware formatting and right-to-left layout where applicable. No claim is made that every hardware/language combination has been certified.

## One release for desktop, GitHub and Microsoft Store

`release.json` is the version source. Every change to `main` triggers `.github/workflows/release.yml`: validate backend, build x64/ARM64, assemble a clean bundled runtime, create installer and MSIX, publish a GitHub release, then submit the same version to Microsoft Store. Increment the version for each release; an existing version cannot silently move to another commit.

The publishing-prerequisites job deliberately fails with precise missing requirements until GitHub Releases permission and Partner Center are configured. It never submits the development identity. A successful submission still requires Microsoft's certification before becoming live. See [publishing instructions](docs/PUBLISHING.md), [privacy](PRIVACY.md), and [third-party notices](THIRD_PARTY.md).

Local app updates must use `scripts/release.ps1`. Direct binary copying bypasses the release process and must not be described as a synchronized release. The local command checks the remote commit and CI state before installing a GitHub release asset. Microsoft Store editions receive their updates from Microsoft Store; do not replace files inside WindowsApps.

## Build

Use .NET 10 SDK, Windows SDK MakeAppx, Python 3.13.15 with Tcl/Tk, and Inno Setup 6. `python scripts/build_runtime.py --seed <clean-python-installation>` downloads the pinned official rclone distribution and checks its SHA-256. Run `dotnet publish PhotosNative/PhotosNative.csproj -c Release -r win-x64 --self-contained true -o artifacts/native-x64` (and win-arm64), then package using `scripts/package_msix.py`. Production MSIX requires the exact Partner Center identity; `--development` creates validation-only packages, unsuitable for Store submission.

## Privacy and release boundaries

Never commit `config.json`, `rclone.conf`, tokens, client secrets, databases, user audits, photos, logs, build output or runtime binaries. Runtime state belongs to the Windows user's application data, not the installation directory. Updates preserve that state. GitHub source publication does not authorize distributing anyone's Google credentials.
