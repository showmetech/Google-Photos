# Fluent 2 review — 27 November 2026

This review applies the public Fluent foundations and relevant component guidance to the existing WPF/.NET shell. It is not a claim that the app is a native WinUI implementation or that every platform-specific component in the Fluent website applies to WPF.

## Design decisions and coverage

| Area | Decision / implementation | Verification |
|---|---|---|
| Navigation | One persistent section selector replaces the section selector plus four nested tabs. Eight destinations expose all existing functionality directly. Icons supplement text, TextSearch and UIA names remain available. | Eight-page traversal; keyboard order; localized/RTL fixtures |
| Widget | Last confirmed photo remains primary. Preview height adapts to available height; queue and automatic action wrap rather than collide. First use opens settings through the primary action. | Native captures, existing empty/setup/queue tests |
| Settings | Selector remains outside the page scroller. Content scrolls only when it exceeds the viewport, preserving text size and reachability. | 320×520 and 360×600 DIP; text scale 100/150/200%; eight pages |
| Tall displays | Settings height is capped at 600 DIP while retaining the gap above the widget. Short displays retain the established overlay fallback. | Geometry tests; runtime placement |
| Buttons | Primary actions for save/connect use accent, secondary actions use neutral control surfaces. Labels can wrap. No decorative button effects. | Light/dark native controls and focus regression |
| Color | Foreground on accent uses linear-sRGB relative luminance and the better black/white contrast, replacing a rough weighted threshold. Existing Windows high-contrast colors remain respected. | 125 palette samples meet 4.5:1 |
| Motion | Section changes use a short 120ms opacity transition; no horizontal sliding or delayed interaction. Disabled with app/system motion or high contrast. Existing window reveal cancellation remains unchanged. | Navigation, close/reopen and reduced-motion paths |
| Menus/dialogs | Secondary options remain contextual; menus wrap labels within panel width. Details dialog is bounded by work area and restores invoking keyboard focus. | Source/build review; live modal coverage still partial |
| Feedback | Errors have an explicit details action. Saved folders receive feedback on the configuration surface. Completion receipts and accepted commands remain distinct. | Existing service receipts; UI source review |
| Privacy / lifecycle | No credentials, uploads, baseline migration, worker or startup behavior is changed by this UI revision. | Isolated fixture profile; backend regression CI |

## Official sources studied

Foundations: [principles](https://fluent2.microsoft.design/design-principles), [layout](https://fluent2.microsoft.design/layout), [color](https://fluent2.microsoft.design/color), [typography](https://fluent2.microsoft.design/typography), [iconography](https://fluent2.microsoft.design/iconography), [shapes](https://fluent2.microsoft.design/shapes), [material](https://fluent2.microsoft.design/material), [elevation](https://fluent2.microsoft.design/elevation), [motion](https://fluent2.microsoft.design/motion), [accessibility](https://fluent2.microsoft.design/accessibility), [content](https://fluent2.microsoft.design/content-design), [tokens](https://fluent2.microsoft.design/design-tokens), [Windows overview](https://fluent2.microsoft.design/components/windows).

Relevant component guidance: [button](https://fluent2.microsoft.design/components/web/react/core/button/usage/), [menu](https://fluent2.microsoft.design/components/web/react/core/menu/usage/), [dialog](https://fluent2.microsoft.design/components/web/react/core/dialog/usage/), [dropdown](https://fluent2.microsoft.design/components/web/react/core/dropdown/usage/), [progress](https://fluent2.microsoft.design/components/web/react/core/progressbar/usage/), [message bar](https://fluent2.microsoft.design/components/web/react/core/messagebar/usage/). Web guidance is used for interaction principles, not React code in WPF. [Windows adaptive guidance](https://learn.microsoft.com/windows/apps/design/layout/responsive-design) informs native sizing. Outlook/OneDrive examples in these official references inform task hierarchy and progress; no independent competitive benchmark or user study was performed.

Some guessed legacy component URLs returned 404; the public `/core/.../usage/` routes above were subsequently resolved. Employee-only resources were not accessed. Do not describe this review as certification of every page or resource of the living Fluent website.

## Limits of validation

Builds and `--verify` use isolated state. They do not establish real OAuth, uploads, Store startup, all hardware, or a screen-reader usability study. Manual UIA inspection confirmed the selector and labels; coordinate input was unavailable, one screenshot disagreed with the WPF render, and the later keyboard selection was interrupted by concurrent user input. Do not count those interrupted steps as passed. Production installation and Store certification remain separate release gates.

Future UI changes must revisit this matrix, document applicable Fluent guidance, add meaningful regressions, inspect captures, and record remaining gaps.
