# Store presentation correction

Version 2026.11.21.4 changes the product display name to Showmetech Photo Sync after the Store review found third-party product naming and screenshot representation issues. The compact header reads Photo Sync. This remains the same product and publisher.

Package identity, executable names, tray GUID, startup registration identity, per-user state directory, OAuth client and upload receipts remain unchanged. These are compatibility identifiers, not branding. No user data is bundled.

Replace Store screenshots with actual first-run widget and appearance captures from an isolated state with no account, personal media or filesystem paths. Capture each supported listing language. Do not submit screenshots of other products or imply Google endorsement.

Validation and submission are separate from Microsoft certification. Approval and public availability require destination readback.

Bruno requested the final Store name SMT Google Photos Uploader on November 21, 2026. Use that exact display name in every listing. Keep the independent-publisher disclaimer and genuine app screenshots. Name availability does not guarantee certification.

The release workflow pins Microsoft Store CLI v0.4.4 and uses its --inputDirectory option with a directory containing only the validated msixupload; --inputFile is not supported by that release.

CLI v0.4.4 selects the MSIX publisher from the positional package-file extension. Pass the msixupload file as the positional argument; inputDirectory only controls which artifacts are uploaded. Verified against Microsoft/MSStore.CLI/ProjectConfigurators/MSIXProjectPublisher.cs at tag v0.4.4.
