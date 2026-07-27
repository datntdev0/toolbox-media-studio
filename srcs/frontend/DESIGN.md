---
version: alpha
name: Novel Media Studio
description: A calm, operational dashboard for turning web novels into managed media projects.
colors:
  primary: "#10B981"
  primary-hover: "#059669"
  primary-subtle: "#D1FAE5"
  on-primary: "#052E16"
  ink: "#111827"
  text: "#374151"
  muted: "#6B7280"
  dimmed: "#9CA3AF"
  default: "#FFFFFF"
  elevated: "#F9FAFB"
  border: "#E5E7EB"
  success: "#166534"
  warning: "#92400E"
  error: "#991B1B"
typography:
  display:
    fontFamily: Public Sans, sans-serif
    fontSize: 1.875rem
    fontWeight: 600
    lineHeight: 2.25rem
    letterSpacing: -0.025em
  heading:
    fontFamily: Public Sans, sans-serif
    fontSize: 1.125rem
    fontWeight: 600
    lineHeight: 1.75rem
  body-md:
    fontFamily: Public Sans, sans-serif
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.5rem
  body-sm:
    fontFamily: Public Sans, sans-serif
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.25rem
  label:
    fontFamily: Public Sans, sans-serif
    fontSize: 0.75rem
    fontWeight: 500
    lineHeight: 1rem
rounded:
  sm: 0.375rem
  md: 0.5rem
  lg: 0.75rem
  full: 9999px
spacing:
  xs: 0.25rem
  sm: 0.5rem
  md: 1rem
  lg: 1.5rem
  xl: 2rem
  2xl: 3rem
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 0.5rem
    height: 2rem
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 0.5rem
    height: 2rem
  card:
    backgroundColor: "{colors.default}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: 1rem
  input:
    backgroundColor: "{colors.default}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 0.5rem
    height: 2rem
  selected-row:
    backgroundColor: "{colors.primary-subtle}"
    textColor: "{colors.ink}"
  metadata:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
  empty-state-icon:
    textColor: "{colors.dimmed}"
  divider:
    backgroundColor: "{colors.border}"
  status-success:
    backgroundColor: "{colors.primary-subtle}"
    textColor: "{colors.success}"
    rounded: "{rounded.full}"
  status-warning:
    backgroundColor: "#FEF3C7"
    textColor: "{colors.warning}"
    rounded: "{rounded.full}"
  status-error:
    backgroundColor: "#FEE2E2"
    textColor: "{colors.error}"
    rounded: "{rounded.full}"
---

## Overview

Novel Media Studio is a focused, editorial-operational workspace. It should feel like a quiet reading room joined to a reliable production console: generous whitespace, clear hierarchy, understated surfaces, and a single green action color. The product handles long-running, sometimes imperfect workflows, so the visual language should make state, progress, and recovery obvious without becoming alarmist.

Use Nuxt UI components and its semantic Tailwind tokens as the implementation layer. The tokens above are the normative design intent; use semantic classes such as `bg-default`, `bg-elevated`, `text-highlighted`, `text-muted`, `border-default`, and `text-primary` so Nuxt UI’s light/dark modes remain coherent.

## Colors

Emerald is the sole affirmative and interactive accent. It identifies primary actions, selected work, progress, active navigation, and success—not decoration. Reserve the soft emerald surface for selected rows and restrained positive context.

Ink and gray provide the information hierarchy: `ink` for titles and active reading content, `text` for ordinary controls, `muted` for supporting metadata, and `dimmed` only for low-priority or empty-state decoration. Use white/default surfaces for active content and the elevated neutral for secondary panels, toolbars, skeleton surroundings, and subtle button fills.

Use status colors semantically and sparingly: green for completed/success, amber for source changes or unavailable-but-recoverable work, and red for failures or irreversible deletion. Never encode status by color alone: pair it with a label and, when helpful, a familiar icon.

## Typography

Public Sans is the UI voice throughout. It is practical and highly legible for metadata-heavy dashboards while remaining comfortable for the novel reader.

Use `display` only for prominent page or reader titles. Use `heading` for card, panel, and section titles. Keep ordinary controls and lists at `body-sm`; use `label` for compact metadata, counts, progress labels, and uppercase reader chapter eyebrows. The reader may step up to a relaxed 1rem–1.125rem body size with a generous line height, but it should remain plain sans-serif text rather than imitate a decorative book layout.

Prefer sentence case. Keep titles concise, wrap them naturally, and truncate only dense list metadata. Use tabular numerals for counters, chapter positions, and progress values where alignment matters.

## Layout

The default layout is an application shell: a collapsible, resizable left navigation rail and one or more dashboard panels. Page headers use a dashboard navbar; contextual tabs and filters appear in a toolbar directly below it. Keep a consistent page rhythm of 16–24 px within panels, with 24–48 px between major sections.

Scraping and novel detail are master-detail workspaces. On desktop, retain the split view: a constrained, resizable navigation/outline panel on the left and a flexible detail or reader panel on the right. On screens below `lg`, preserve the list as the primary view and show the selected detail in a full-width slideover. Persist selections in the URL so deep links and browser navigation work.

Use responsive single-column grids by default; expand library cards to two columns only when enough width exists. Avoid dense multi-column forms. Align destructive and secondary actions near the content they affect; keep the primary creation/action control in the header’s right region.

## Elevation & Depth

The interface is intentionally low-elevation. Separate regions primarily through neutral background changes, borders, spacing, and panel structure rather than strong shadows. Cards, inputs, and list containers use a thin `border` and rounded corners. Use a subtle shadow only when a floating overlay needs clear separation: modal, slideover, dropdown, or a compact action cluster over a card image.

Do not stack cards inside cards without a clear hierarchy. A selected row is identified by the primary-subtle fill and primary border treatment, not by elevation. Keep sticky reader actions on the default background with a top border so their purpose remains clear while scrolling.

## Shapes

Use the radius scale consistently: `sm` for compact internal elements, `md` for inputs and buttons, and `lg` for cards, empty states, and media containers. Use fully rounded shapes only for status badges, avatars, and tiny count indicators—not general containers.

Cover art is intentionally rectangular with a modest radius. Use `object-cover` and provide a primary-subtle book icon fallback when an image is missing or fails. Avoid oversized rounded “pill” cards and excessive glass effects; this is a calm utility interface, not a marketing surface.

## Components

### Navigation and panels

Use `UDashboardGroup`, `UDashboardSidebar`, `UDashboardPanel`, `UDashboardNavbar`, and `UDashboardToolbar` for product screens. Navigation items need an Iconify icon and concise label. The current route should be visually primary; nested settings/admin destinations should remain discoverable but quieter. Keep feedback/help links and template-only destinations visually separate from core workflow navigation.

### Buttons and actions

Use the primary button for the page’s main forward action: create a scraping, create a novel, bind a source, or save a chapter. Use neutral soft/outline/ghost variants for navigation, filtering, editing, and optional actions. Destructive actions must use the error color, an explicit label or accessible name, and a confirmation dialog when irreversible.

Icon-only actions require an accessible label and tooltip. Disable or show loading state while a mutation is in flight; do not permit parallel destructive operations on the same collection.

### Lists, tables, and selection

List rows should be immediately scannable: cover/fallback icon, title, source or secondary metadata, current status, and progress. The entire main row is a keyboard-focusable selection target; local edit/delete actions must not accidentally select it. Restore focus to the originating row after a detail closes.

Use tables only for genuinely tabular administration data. Keep column controls, filters, pagination, and bulk operations in the table’s header/footer, and show how many rows are selected.

### Progress, status, and feedback

Show durable job progress as `completed / total`, a labeled badge, and a slim progress bar for queued/running work. Use a spinning icon only while actively running. Long-running work should keep the screen useful, refresh after its realtime invalidation event, and display a retry action when a fetch fails.

Use skeletons with the approximate final shape while loading. Use `UEmpty` for a genuine no-content condition and `UAlert` for recoverable load/mutation errors. Use toasts for concise mutation confirmation; do not rely on a toast as the only evidence that persisted state changed.

### Forms and overlays

Use Nuxt UI form fields with visible labels, validation messages, and Zod schemas where validation is client-side. Modal forms focus on one task and must retain form state until explicitly cancelled or completed. On mobile, use a slideover for a selected detail/reader rather than compressing a complex split pane.

### Novel reader

Make reading content the visual focus: centered, comfortably narrow column, chapter eyebrow, clear chapter title, relaxed paragraph spacing, and no competing decorative elements. Editing switches to a plain monospaced textarea and a sticky save/cancel bar. Before changing chapter, closing the reader, or leaving the route, ask before discarding a dirty draft. Show source-update, manual-edit, removed-source, and unavailable-content states explicitly in the outline.

## Do's and Don'ts

**Do** use a restrained emerald accent, semantic UI tokens, readable whitespace, explicit loading/empty/error states, URL-backed selection, and labeled accessible controls.

**Do** preserve the desktop master-detail workflow and replace it with a focused slideover on mobile.

**Do** make asynchronous progress and conflict states understandable in the interface, including ETag save conflicts and unavailable bound sources.

**Don't** introduce a second accent palette, gradients, heavy shadows, decorative glass surfaces, or marketing-style hero treatments into product pages.

**Don't** use red for ordinary actions or green as a general decorative color. Do not hide a failure behind a silent refresh or use color without text/icon support.

**Don't** hand-build primitives that Nuxt UI already provides, or hard-code light-mode colors where semantic Nuxt UI tokens preserve dark-mode support.
