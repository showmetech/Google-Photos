# Publishing contract

1. Change and test source in this repository. Update `release.json` and `PhotosNative/PhotosNative.csproj` together. Review generated assets, privacy and third-party notices. Commit only reviewed source.
2. Push `main` (or `scripts/release.ps1 -Publish` after GitHub CLI authentication). The hosted workflow builds and tests, creates GitHub release assets, then submits the version to Microsoft Store. Failures are visible in Actions; a blocked Store stage is not success.
3. To install the matching desktop installer, run `scripts/release.ps1 -Install`. It verifies remote commit, workflow completion and installer digest. For a Store-installed edition, let Microsoft Store perform updates.
4. A submission is not publication. Verify Partner Center certification and the public Store listing before reporting all distribution channels current. Microsoft controls review timing, so simultaneous public availability cannot be guaranteed.

## First Store submission

An active Partner Center developer account and a reserved application are required. Initial product creation, age ratings, product identity and the first listing/submission require Partner Center. Do not invent IDs or publish development identity packages.

Copy the exact package identity name, publisher distinguished name, publisher display name and product ID from the existing product into `store/identity.json` locally. This file is ignored. Set repository variable `MSSTORE_IDENTITY_JSON` to this identity JSON and `MSSTORE_PRODUCT_ID` to its product ID.

For authorized automated submissions, the publisher must associate an Entra application with the existing Partner Center account and grant the documented publishing role. Store `AZURE_AD_TENANT_ID`, `AZURE_AD_APPLICATION_CLIENT_ID`, `AZURE_AD_APPLICATION_SECRET`, and `SELLER_ID` as GitHub Actions secrets. Never put credentials in the source or the distributed app. Creating or broadening that access is a separate security-sensitive account action.

The MSIX version is `year.month.(day*100+revision).0`; revisions must be below 100. Example: desktop `2026.11.7.1` maps to Store `2026.11.701.0`. Every new version must increase monotonically. Store gives a signed MSIX after certification; a development MSIX and the independent unsigned EXE are not equivalent to a Store release.

## Google authorization release gate

The current app supports each user importing their own Google desktop OAuth client. A new user must configure folders and Google consent before uploading. It does not distribute the developer's credentials. An effortless public sign-in flow using an application-owned Google client requires Google Cloud consent-screen configuration, policy compliance and any required verification; that is not proven by a Windows build or Store certification.

## Coverage

Builds: x64 and ARM64 UI, self-contained .NET, x64 bundled Python/rclone on both. Test Windows 11 x64 and physical ARM64, fresh user, Unicode/long/UNC paths, missing/offline origins, OAuth cancel/revoke, shutdown/recovery, high contrast, text scaling and update preservation. Compile success cannot certify every computer.

## Official references

- https://learn.microsoft.com/windows/apps/publish/msstore-dev-cli/github-actions
- https://learn.microsoft.com/windows/msix/desktop/desktop-to-uwp-manual-conversion
- https://learn.microsoft.com/uwp/api/windows.applicationmodel.startuptask
- https://rclone.org/googlephotos/

## Current publishing access gate

The first hosted build passed, but GitHub rejected the release creation API with `403 Resource not accessible by integration`, although the job log listed `Contents: write`. No alternate token or identity was used. An administrator must reconcile that effective publishing permission. Set repository variable `RELEASE_PUBLISHING_ENABLED=true` only after that reconciliation and Store credentials/identity are ready. The publishing-prerequisites job prevents new publishing attempts and desktop installation while these requirements remain unresolved. Source publication and build artifacts remain separate from public Releases.
