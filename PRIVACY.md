# SMT Google Photos Uploader — Privacy policy

Effective date: November 21, 2026

SMT Google Photos Uploader is an independent Windows application published by Showmetech. It is not an official Google product.

## Data used by the application

The application reads the photo and video folders that you select. When you enable synchronization, it sends selected media, filenames, and album information directly to Google Photos using rclone and Google's services. Google processes that information under your Google account and Google's privacy policy: https://policies.google.com/privacy

Your folder choices, Google authorization, synchronization database, upload receipts, diagnostic logs, and cached preview are stored in your Windows user profile. They are not included in the public installer. The application does not upload this local state to a Showmetech server and does not include an application analytics or advertising service.

## Authorization and control

Each user configures their own folders and Google authorization. The current version requires a Google desktop OAuth client configured by the user. The publisher's personal Google account and authorization are not supplied with the app.

You can pause synchronization or change its folders in Settings. You can revoke Google access in your Google account's third-party connections settings. Pausing or uninstalling the app does not delete photos already uploaded to Google Photos.

The application keeps per-user state outside its installation directory to preserve settings and receipts during updates. Uninstallation may leave this state behind. After exiting the application, you can remove its GooglePhotosUploader directory in your Windows Local AppData folder if you want to erase the local settings, authorization, logs, database, and preview. Keep any receipts you need before doing so.

## Diagnostics and support

Diagnostic information can contain filenames, folder paths, timestamps, and error messages. Review and redact it before voluntarily sharing a report. Do not send passwords, authorization tokens, private photos, or OAuth secrets to support.

Microsoft Store, Windows, and Google may process their own account, download, diagnostic, or service data under their respective policies. Their processing is separate from this application.

## Contact

Questions about this application and this policy: contato@showmetech.com.br

Source and issues: https://github.com/showmetech/Google-Photos
