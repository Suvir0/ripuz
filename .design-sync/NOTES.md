# Ripuz Design System — sync notes

## Config decisions

- `provider: DsThemeWrap` — `@storybook/addon-themes` `withThemeByDataAttribute` fails at runtime when bundled outside Storybook (TypeError: not a function). Light theme is the CSS default via `:root` selectors, so a passthrough wrapper (`_ds_wrap.tsx`) is sufficient. Dark theme uses `[data-theme="dark"]` override.
- `titleMap: {"Primitives/Icons": null, "Screens/FullApp": null}` — `Icons` story shows TYPE_ICONS constants (not a component). `FullApp` is a multi-screen composite story with no matching export.
- `Modal: cardMode: "single"` — Modal uses React portals for backdrop; `position:fixed` children escape grid cells in product card view. Single-story card mode applied.

## Known render characteristics

- Background color differs between storybook (beige canvas from storybook layout) and preview (white). [GENERAL] — judge component, not canvas.
- Modal backdrop (gray overlay) is not captured in previews — it renders via React portal to document.body, outside the capture frame. Both Modal stories graded `close`; content is identical.
- ThemeToggle: `[RENDER_THIN]` — light/dark variants look identical in preview (toggle button, no visible state change without user interaction). Non-blocking.
- Font: Space Grotesk and JetBrains Mono load from remote CDN (`[FONT_REMOTE]`). Both appear in previews and storybook — CDN is reachable. Non-blocking.

## Screen viewport

Screen components (AddScreen, JobsScreen, LibraryScreen, SettingsScreen) use `cfg.overrides.<Name>.viewport: "1280x1024"` — the default 720px height clipped the bottom of full-page UIs. Set to 1024px to show full content including action buttons at bottom of page.

## Re-sync risks

- `_ds_wrap.tsx` (DsThemeWrap): extra entry used as provider wrapper. If the design system adds a real ThemeProvider export in a future version, `cfg.provider` can reference it directly and `extraEntries`/`_ds_wrap.tsx` can be removed.
- Icons/FullApp stories excluded from sync. If either gains a real component export, update titleMap.
- Modal `close` grade: backdrop not captured. If Modal gains a non-portal backdrop option, this could be upgraded to `match`.
- Space Grotesk / JetBrains Mono are CDN-hosted — if CDN is unavailable at sync time, fonts fall back to system fonts. Both sides fall back identically, so grade won't catch it. Verify fonts visually if running sync in a network-isolated environment.
