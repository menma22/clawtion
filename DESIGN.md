---
name: clawtion Design System
description: Design tokens and visual identity for clawtion — AI knowledge base + note-taking desktop app
version: "1.0"

colors:
  accent: "#4f46e5"        # Indigo — sophisticated, calm
  accent-hover: "#4338ca"
  accent-subtle: "#eef2ff"
  accent-muted: "#e0e7ff"
  danger: "#ef4444"
  danger-hover: "#dc2626"
  danger-subtle: "#fef2f2"
  success: "#10b981"
  success-subtle: "#ecfdf5"
  warning: "#f59e0b"
  warning-subtle: "#fffbeb"

  surface:
    app: "#ffffff"         # Warm white
    sidebar: "#f7f6f4"    # Notion-style warm gray
    card: "#ffffff"
    input: "#f2f1ef"
    hover: "#f2f1ef"
    active: "#ebeae8"
    overlay: "rgba(0, 0, 0, 0.4)"

  border:
    default: "#e9e7e4"
    subtle: "#f2f1ef"
    focus: "#4f46e5"

  text:
    primary: "#1a1a1a"
    secondary: "#6b6b6b"
    tertiary: "#9e9e9e"
    inverse: "#ffffff"

  dark:
    surface:
      app: "#191919"
      sidebar: "#1e1e1e"
      card: "#252525"
      input: "#2a2a2a"
      hover: "#2a2a2a"
      active: "#333333"
    border:
      default: "#333333"
      subtle: "#2a2a2a"
    text:
      primary: "#e4e4e4"
      secondary: "#999999"
      tertiary: "#666666"

typography:
  display-lg:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "36px"
    fontWeight: 700
    lineHeight: 1.2
  display-md:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.2
  headline-lg:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.3
  headline-md:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.3
  headline-sm:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.4
  body-lg:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  body-md:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  label-md:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1.4
  label-sm:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
  caption:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.4
  mono-md:
    fontFamily: "JetBrains Mono, Fira Code, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
    fontFeature: "'calt' 1, 'liga' 1"
  mono-sm:
    fontFamily: "JetBrains Mono, Fira Code, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5

spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  3xl: "64px"

rounded:
  none: "0px"
  sm: "4px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  full: "9999px"

shadows:
  sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
  md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)"
  lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)"
  xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)"

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.text.inverse}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-primary-active:
    backgroundColor: "{colors.primary-active}"
  button-secondary:
    backgroundColor: "{colors.surface.input}"
    textColor: "{colors.text.primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "40px"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.text.inverse}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text.secondary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
  input:
    backgroundColor: "{colors.surface.input}"
    textColor: "{colors.text.primary}"
    borderColor: "{colors.border.default}"
    borderRadius: "{rounded.md}"
    padding: "8px 12px"
    height: "40px"
  card:
    backgroundColor: "{colors.surface.card}"
    borderColor: "{colors.border.default}"
    borderRadius: "{rounded.lg}"
    padding: "{spacing.lg}"
  sidebar:
    width: "260px"
    backgroundColor: "{colors.surface.sidebar}"
    borderColor: "{colors.border.default}"
  statusbar:
    height: "32px"
    backgroundColor: "{colors.surface.sidebar}"
---

# clawtion Design System

## Brand & Style

clawtion is a **professional developer tool** — precise, fast, trustworthy. Think VS Code meets Notion. The visual identity conveys technical competence without feeling cold. It is a desktop application used daily by engineers and knowledge workers, so it must be comfortable for long sessions.

**Brand personality:**
- **Precise** — Clean geometric shapes, monospaced code, sharp corners on interactive elements
- **Calm** — Low-contrast surfaces, generous whitespace, no aggressive colors in default state
- **Fast** — Animations are brief (150-250ms), never decorative. Motion serves function.
- **Trustworthy** — Semantic colors (green=success, red=danger) are used consistently. Nothing is ambiguous.

**Target audience:** Software engineers, researchers, technical writers. They spend 4-8 hours/day in this tool.

## Colors

The palette is anchored on **Blue-500 (`#3b82f6`)** as the primary action color — blue is universally associated with trust, technology, and links. Tailwind CSS color scale values are used as the base, giving access to the full 50-950 range.

### Semantic color assignments

| Token | Hex | Role |
|-------|-----|------|
| `primary` | `#3b82f6` | Primary buttons, links, focus rings, active states |
| `danger` | `#ef4444` | Delete actions, error toasts, destructive confirmations |
| `success` | `#22c55e` | Success toasts, completion states, healthy indicators |
| `warning` | `#f59e0b` | Warnings, pending states, "needs attention" badges |

### Surface hierarchy
- **app** (lightest) → main content background
- **sidebar** (slightly darker) → navigation rail, folder tree
- **card** (white in light, slate in dark) → elevated content containers
- **input** (contrasting fill) → form fields, search bars
- **overlay** → modal backdrops

### Dark mode
All surface colors invert: white background becomes `#0f172a` (Slate-900), sidebar becomes `#1e293b` (Slate-800). Text inverts from dark to light. Semantic colors maintain their hue but adjust saturation slightly for readability on dark backgrounds.

## Typography

### Font stack
- **Sans:** `Inter` → Primary UI font. Clean, modern, excellent readability at small sizes.
- **Mono:** `JetBrains Mono` → Code blocks, file paths, technical identifiers. Ligatures enabled.

### Scale and usage

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| `display-lg` | 36px / 700 | Page titles (rare) |
| `display-md` | 30px / 700 | Modal headings |
| `headline-lg` | 24px / 700 | Section headers |
| `headline-md` | 20px / 600 | Card titles |
| `headline-sm` | 18px / 600 | Subsection headers |
| `body-lg` | 16px / 400 | Primary reading text, editor content |
| `body-md` | 14px / 400 | Secondary text, table cells |
| `body-sm` | 13px / 400 | Metadata, timestamps |
| `label-md` | 14px / 500 | Button text, form labels |
| `label-sm` | 12px / 500 | Badge text, tab labels |
| `caption` | 11px / 400 | Helper text, version info |
| `mono-md` | 14px / 400 | Code blocks, inline code |
| `mono-sm` | 12px / 400 | Inline code in small contexts |

## Layout & Spacing

**Base grid:** 8px. All spacing values are multiples of 8.

| Token | Value | Usage |
|-------|-------|-------|
| `xs` | 4px | Icon-to-label gap, tight inline spacing |
| `sm` | 8px | Element gap within a group |
| `md` | 16px | Standard padding, card padding |
| `lg` | 24px | Section separation |
| `xl` | 32px | Page-level padding |
| `2xl` | 48px | Large section breaks |
| `3xl` | 64px | Hero-level spacing (rare) |

**Layout constants:**
- Sidebar width: `260px` (collapsible to `0px`)
- StatusBar height: `32px`
- Content max-width: none (fluid, the app is full-width by default)

## Elevation

Shadows are used sparingly. Only cards and modals cast shadows. The sidebar and main content area are at the same elevation (flat).

| Token | Value | Usage |
|-------|-------|-------|
| `sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle card lift |
| `md` | `0 4px 6px rgba(0,0,0,0.1)` | Hovered card |
| `lg` | `0 10px 15px rgba(0,0,0,0.1)` | Dropdown, popover |
| `xl` | `0 20px 25px rgba(0,0,0,0.1)` | Modal |

Z-index scale: Sidebar (10), Sticky headers (20), Dropdowns (30), Toast (40), Modal overlay (50).

## Shapes

| Token | Value | Usage |
|-------|-------|-------|
| `none` | 0px | Code blocks, tables |
| `sm` | 4px | Badges, inline code, small buttons |
| `md` | 8px | Buttons, inputs, cards |
| `lg` | 12px | Modals, large cards |
| `xl` | 16px | Hero containers |
| `full` | 9999px | Pills, avatars, toggle switches |

## Components

### Button
- **Primary:** Blue fill, white text, `rounded.md`, `h:40px`. States: default → hover (darker blue) → active (darkest) → disabled (50% opacity) → loading (spinner replaces text).
- **Secondary:** Slate-100 fill, Slate-900 text. Used for cancel, back, non-primary actions.
- **Danger:** Red fill, white text. Used only for destructive actions. Always paired with a confirmation modal.
- **Ghost:** Transparent fill, secondary text. Used for icon buttons, toolbar actions.
- **Sizes:** `sm` (32px), `md` (40px), `lg` (48px).

### Input
- Slate-100 fill, 1px Slate-200 border. Focus: border becomes `primary` blue, 3px blue ring.
- Error state: border becomes `danger` red, helper text in red below.
- With icon: 36px padding-left for the icon slot.

### Card
- White/slate-800 background, 1px border, `rounded.lg`, `p:24px`.
- Hover: translates `-2px` on Y, shadow increases to `md`.

### Modal
- Fixed overlay (50% black), centered white panel.
- Panel: `rounded.xl`, `p:32px`, min-width 400px, max-width 90vw.
- Enter animation: backdrop fades in, panel scales from 0.9 + fades in (200ms spring).

### Toast
- Fixed bottom-right, stacked with 8px gap.
- Each toast: 360px wide, `rounded.md`, `p:16px`, shadow `lg`.
- Types: success (green left border), error (red left border), warning (amber left border), info (blue left border).
- Auto-dismiss after 5s with progress bar. Swipe-to-dismiss.

### Sidebar
- Fixed left, 260px wide, full height minus StatusBar.
- Folder tree: recursive indentation (16px per level), chevron toggle.
- Nav items: 40px height, 8px horizontal padding, `rounded.md`. Active item has `primary-subtle` background.

### StatusBar
- Fixed bottom, full width, 32px height.
- Shows: indexing status (colored dot + label), vault path (truncated), version.
- Font: `caption` (11px), secondary text color.

## Do's and Don'ts

### DO
- Use semantic color tokens (`text-primary`, `surface-card`) — never hardcode hex values
- Use `cn()` (clsx + tailwind-merge) for all className composition
- Wrap interactive elements with Framer Motion `whileTap={{ scale: 0.97 }}`
- Show loading skeletons (not spinners) for initial data fetches
- Use `<AnimatePresence>` for all mount/unmount animations
- Keep animations under 250ms — they should feel instant
- Use `body-lg` (16px) as the default reading font size
- Test all components in both light and dark mode

### DON'T
- Use emoji as icons — use Lucide React icons
- Nest scrollable containers — only the main content area scrolls
- Use more than one primary button per screen
- Show raw error messages to users — wrap in user-friendly text
- Use `window.alert()` — use Toast notifications
- Animate layout properties (width, height) — use transform instead
- Block the UI during API calls — use optimistic updates where possible
