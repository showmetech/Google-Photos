# Fluent 2 — Windows / WPF

This app keeps its existing WPF implementation and built-in PresentationFramework.Fluent theme.
It does not claim to use WinUI 3 or every Fluent 2 component.

The shared button resource uses semantic fill, hover, pressed, disabled and text tokens;
4 DIP control corners, 1 DIP outlines, 32 DIP minimum height, balanced padding and a
visible 2 DIP keyboard focus outline. The primary sync action retains the user's
Windows accent. Icons and typography remain Segoe Fluent Icons and Segoe UI Variable.
Dark/light resources update with appearance changes. High contrast uses system brushes.
Button states change immediately; existing app window animations and their preference
remain unchanged. User opacity, pin, placement and all sync behavior are preserved.

Settings selection uses native text content and semantic foreground, avoiding stale
VisualBrush copies of UIElement labels when switching themes.

Verification: build, isolated `--verify --verify-fluent`, thirteen checks for control
corners/states in both themes and the keyboard focus style; widget/settings renders.
No actual media or account is needed. High contrast was reviewed in code but was not
enabled globally on the user's computer. NuGet vulnerability retrieval may warn NU1900
when network is unavailable; this is not a clean vulnerability audit.

References:
- https://fluent2.microsoft.design/components/windows
- https://fluent2.microsoft.design/design-tokens
- https://fluent2.microsoft.design/typography
- https://fluent2.microsoft.design/motion
