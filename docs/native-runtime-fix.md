# Native HEIF runtime correction

Version 2026.11.21.5 fixes the offline runtime assembly path used for the Store package. Copying only Python import directories omitted the top-level `_pillow_heif` extension and its native DLLs. Importing `pillow_heif` did not detect this because it defers the native import error until plugin registration.

The isolated-seed path now copies the files recorded by the exact pinned distributions, checks their RECORD hashes, and rejects files outside site-packages. It does not copy unrelated installed packages or user state. See the [installed-project specification](https://packaging.python.org/en/latest/specifications/recording-installed-packages/).

Runtime assembly and MSIX staging both exercise HEIF plugin registration and an in-memory encode/decode round trip. The integration regression verifies that the complete copied payload works, then removes the extension and requires the probe to fail. This covers the failure missed by the former import-only check. See [pillow-heif plugin registration](https://pillow-heif.readthedocs.io/en/stable/pillow-plugin.html).

Package identity, tray GUID, state location, Google authorization and receipts are unchanged. Builds and local tests do not prove Microsoft certification, public availability or physical ARM64 compatibility. Store-installed copies must update through Microsoft Store; never patch WindowsApps in place.
