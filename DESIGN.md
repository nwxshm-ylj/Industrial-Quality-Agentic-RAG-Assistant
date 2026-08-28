# Industrial Quality Console Design System

## Design intent

This interface is an industrial operations console, not a marketing website. It
must make system state, evidence, permissions, failures, and next actions easy to
scan during daily work. The visual language combines the information discipline
of enterprise design systems with the restrained interaction model of modern
developer tools.

## Principles

1. **Evidence before decoration**: retrieval sources, node progress, status, and
   metrics are more important than ornamental graphics.
2. **One primary accent**: teal identifies primary actions and active navigation.
   Semantic status colors are reserved for success, warning, danger, and info.
3. **High-contrast Chinese text**: body text must remain readable on every
   surface. Do not place muted text on a similarly colored background.
4. **Dense but breathable**: use a 4 px spacing grid, compact controls, and clear
   section boundaries without reducing body or table text below 13 px.
5. **Flat enterprise surfaces**: prefer borders and tonal backgrounds over large
   shadows, glass effects, gradients, or oversized rounded cards.
6. **Stable interaction contracts**: visual changes must not alter API payloads,
   streaming events, role permissions, or destructive-action confirmation.

## Foundations

### Color

- Canvas: `#f3f6f8`
- Base surface: `#ffffff`
- Subtle surface: `#f7f9fa`
- Strong surface: `#102a35`
- Primary text: `#172b3a`
- Secondary text: `#526674`
- Muted text: `#6f818d`
- Border: `#d7e0e5`
- Primary teal: `#0f766e`
- Primary hover: `#0d8a80`
- Success: `#198754`
- Warning: `#a86416`
- Danger: `#b64040`
- Info: `#356b8c`

Do not use semantic colors as decorative accents. On dark surfaces use
`#f4f8f9` for primary text and `#c2d0d6` for secondary text.

### Typography

- UI and Chinese copy: `Inter`, `Noto Sans SC`, `Microsoft YaHei`, system sans.
- Identifiers, request IDs, model names, and small labels: `IBM Plex Mono`,
  `SFMono-Regular`, `Consolas`, monospace.
- Body: 14 px minimum, 1.6 line height.
- Table: 13 px minimum.
- Small supporting text: 12 px minimum.
- Page title: 24 px desktop, 20 px mobile.

### Shape and depth

- Control radius: 4 px.
- Card/panel radius: 6 px.
- Large workspace radius: 8 px.
- Use `1px` borders for hierarchy.
- Shadows are limited to floating overlays and sticky navigation.

### Spacing

Use the 4 px scale: `4, 8, 12, 16, 20, 24, 32, 40`.

## Component rules

### Application shell

- Dark, stable left navigation; light sticky header; neutral content canvas.
- Selected navigation uses a teal left rail and tonal fill, not a gradient.
- Page title and context label remain visible at every desktop route.

### Cards and panels

- Default white surface, 1 px border, little or no shadow.
- Metric cards use a semantic top or left rule only when the metric has state.
- Avoid nested cards when a divider or grouped list is sufficient.

### Tables

- Header uses a subtle gray surface and medium-weight text.
- Rows use 13 px or larger text and a restrained hover background.
- Destructive actions require confirmation and remain visually distinct.

### Status

- Status always includes text; color alone is not sufficient.
- Ready/indexed/success: green.
- Degraded/pending/warning: amber.
- Failed/deleted/denied: red.
- Informational/processing: blue or teal.

### Chat and evidence

- The conversation remains the dominant column.
- Node progress and evidence are separate, scannable regions.
- Request ID, intent, latency, model usage, and degraded state are secondary
  operational details, never removed from the response presentation.
- Citations use a bordered evidence card with source identity and rank/score.

## Responsive behavior

- Below 1280 px, remove the optional session rail before reducing the evidence
  region.
- Below 920 px, stack conversation and evidence.
- Below 760 px, use a drawer for navigation and 16 px content padding.
- Tables may scroll horizontally; do not compress columns into unreadable text.

## Do

- Keep Chinese labels concise and unambiguous.
- Preserve keyboard focus indicators.
- Show loading, empty, degraded, denied, and error states explicitly.
- Verify admin, engineer, and viewer presentations independently.

## Do not

- Do not copy another company's logo, wording, or brand identity.
- Do not use `latest` visual trends at the expense of readability.
- Do not add neon glows, large gradients, glass cards, or decorative charts.
- Do not reduce text opacity until it becomes low contrast.
- Do not hide RBAC-protected controls with CSS alone; route and API guards remain
  authoritative.

