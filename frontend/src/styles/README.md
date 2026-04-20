# Styles

Source of truth for tokens is `src/index.css`. Module-specific files under
`src/styles/` (chat, draw, settings, etc.) are imported at the top of
`index.css`.

## Design tokens

Always reference tokens; don't hardcode pixel values or hex colors.

### Color (shadcn-style HSL)
Use as `hsl(var(--foreground))`, `hsl(var(--primary) / 0.5)`, etc.

- `--background` / `--foreground` — page surface + ink
- `--primary` / `--primary-foreground` — CTA color
- `--secondary` / `--muted` / `--accent` — neutral surfaces
- `--destructive` — danger CTAs, delete
- `--border` / `--input` / `--ring` — UI chrome
- `--sidebar*` — dark sidebar palette

### Radius

- `--radius-sm`, `--radius-md` (default), `--radius-lg`, `--radius-xl`
- `--radius` is an alias for `--radius-md`

### Spacing — 4px base scale

- `--space-xs` 4px
- `--space-sm` 8px
- `--space-md` 12px
- `--space-lg` 16px
- `--space-xl` 24px
- `--space-2xl` 32px

### Z-index layers

Reuse these; do not invent new numbers.

- `--z-dropdown` 50
- `--z-overlay` 90 (sidebar backdrop, etc.)
- `--z-sidebar` 100
- `--z-sidebar-toggle` 110 (hamburger above sidebar)
- `--z-modal` 1000
- `--z-toast` 2000

### Breakpoints

Tokens exist for documentation; `@media` cannot read CSS variables.

- `--bp-sm` 480px — phone
- `--bp-md` 768px — tablet (current mobile cutoff)
- `--bp-lg` 1024px — small desktop

### Touch

- `--tap-size` 44px — minimum interactive target (iOS HIG)

## Naming — BEM-ish

- Root class: `.block`
- Nested element: `.block-element` (not `.block__element`)
- Modifier: `.block--modifier` (double-dash, e.g. `.btn--primary`)

Prefix component-local styles with the component name (`.chat-…`, `.draw-…`)
to avoid collisions. Global primitives use single-word names (`.btn`,
`.input`, `.modal`).

## Primitives (global)

Shared building blocks live in `index.css`:

- `.btn` / `--primary` / `--ghost` / `--danger` / `--icon` / `--pill` — see `components/Button.tsx`
- `.input` — bordered text input; `.select` — styled `<select>` with chevron
  - Both bump to 16px on mobile (`@media max-width: 768px`) to prevent iOS auto-zoom on focus
- `.panel-textarea` — transparent full-width textarea inside module panels (also 16px on mobile)
- `.overlay` / `.modal` / `.modal-actions` — see `components/Modal.tsx` (ESC + backdrop-click + body scroll lock)
  - Mobile: card becomes full-viewport (no radius/border)
- `.shell-root` / `.sidebar` / `.nav-item` / `.module-panel-*` — app chrome

Module-specific CSS files should only hold styles that are truly unique to
that module. When you find yourself copy-pasting button/input/modal styles,
promote them to a primitive instead.
