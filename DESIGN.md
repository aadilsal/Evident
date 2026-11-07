---
version: alpha
name: Evident
description: Evidence-backed architecture maps. A transit diagram of your codebase, with an exhibit tag on every line.
colors:
  primary: "#F2D544"
  on-primary: "#14161A"
  primary-hover: "#FFE36A"
  surface: "#0F1115"
  surface-raised: "#171A20"
  surface-sunken: "#0A0C0F"
  on-surface: "#E8E6E1"
  on-surface-muted: "#9BA1AB"
  outline: "#2A2F38"
  outline-strong: "#3B4250"
  highlight: "#3A3418"
  paper: "#F6F4EE"
  ink: "#16181C"
  layer-route: "#4C8DFF"
  layer-handler: "#A4ACB8"
  layer-middleware: "#F08A3C"
  layer-model: "#34C084"
  layer-service: "#E0559A"
  layer-env: "#2BB8C8"
  error: "#F26464"
  warning: "#F5A524"
typography:
  display:
    fontFamily: IBM Plex Sans
    fontSize: 56px
    fontWeight: "600"
    lineHeight: 1.05
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: IBM Plex Sans
    fontSize: 36px
    fontWeight: "600"
    lineHeight: 1.15
    letterSpacing: -0.01em
  headline-md:
    fontFamily: IBM Plex Sans
    fontSize: 22px
    fontWeight: "600"
    lineHeight: 1.3
  body-lg:
    fontFamily: IBM Plex Sans
    fontSize: 18px
    fontWeight: "400"
    lineHeight: 1.6
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 15px
    fontWeight: "400"
    lineHeight: 1.55
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 13px
    fontWeight: "400"
    lineHeight: 1.5
  label-lg:
    fontFamily: IBM Plex Sans
    fontSize: 14px
    fontWeight: "600"
    lineHeight: 1.2
  label-md:
    fontFamily: IBM Plex Sans Condensed
    fontSize: 13px
    fontWeight: "500"
    lineHeight: 1.2
    letterSpacing: 0.01em
  label-sm:
    fontFamily: IBM Plex Sans Condensed
    fontSize: 11px
    fontWeight: "600"
    lineHeight: 1.2
    letterSpacing: 0.06em
  code-md:
    fontFamily: IBM Plex Mono
    fontSize: 13px
    fontWeight: "400"
    lineHeight: 1.6
  code-sm:
    fontFamily: IBM Plex Mono
    fontSize: 12px
    fontWeight: "400"
    lineHeight: 1.5
rounded:
  none: 0px
  sm: 3px
  md: 6px
  lg: 10px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 40px
  3xl: 64px
  canvas-grid: 24px
  panel-width: 440px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 0 16px
    height: 40px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.md}"
    padding: 0 16px
    height: 40px
  input-repo-url:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.on-surface}"
    typography: "{typography.code-md}"
    rounded: "{rounded.md}"
    padding: 0 16px
    height: 48px
  graph-node:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: 8px 12px
  layer-stripe-route:
    backgroundColor: "{colors.layer-route}"
    width: 3px
  layer-stripe-handler:
    backgroundColor: "{colors.layer-handler}"
    width: 3px
  layer-stripe-middleware:
    backgroundColor: "{colors.layer-middleware}"
    width: 3px
  layer-stripe-model:
    backgroundColor: "{colors.layer-model}"
    width: 3px
  layer-stripe-service:
    backgroundColor: "{colors.layer-service}"
    width: 3px
  layer-stripe-env:
    backgroundColor: "{colors.layer-env}"
    width: 3px
  layer-tag:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: 2px 6px
  badge-extracted:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 2px 8px
  badge-inferred:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
    padding: 2px 8px
  evidence-panel:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-sm}"
    width: "{spacing.panel-width}"
    padding: "{spacing.lg}"
  exhibit-tag:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.on-surface-muted}"
    typography: "{typography.code-sm}"
    rounded: "{rounded.sm}"
    padding: 4px 8px
  code-snippet:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.on-surface}"
    typography: "{typography.code-md}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  code-line-evidence:
    backgroundColor: "{colors.highlight}"
    textColor: "{colors.on-surface}"
  finding-error:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.error}"
    typography: "{typography.label-lg}"
  finding-warning:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.warning}"
    typography: "{typography.label-lg}"
  page-light:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
motion:
  feedback: 120ms
  panel: 200ms
  trace-hop: 160ms
  trace-stagger: 90ms
  count-up: 600ms
  ease-standard: cubic-bezier(0.2, 0, 0, 1)
  ease-draw: cubic-bezier(0.4, 0, 0.2, 1)
---

## Overview

Evident looks like **a 1970s transit diagram pinned inside a court exhibit binder.**

The map is drawn in the tradition of Massimo Vignelli's 1972 New York subway diagram. Each architectural layer is a coloured line, nodes are stations, edges run straight or turn at clean angles, and geography gives way to clarity. Everything around the map comes from the evidence binder. File paths are set in monospace like an exhibit sticker (`EXHIBIT · app/api/invoices/route.ts · L8–24`). Code snippets sit on a darker sheet, and the proving lines are marked with a strip of highlighter yellow, as if someone ran a marker over a printout.

The audience is a developer who has just landed in an unfamiliar codebase and wants to know *what talks to what*, then wants proof. The interface is a working tool, not a pitch deck. It is calm, dense and exact, and it never decorates. Its confidence comes from showing the receipt, not from glow.

Dark is the default because the map is a lightbox: coloured lines on a graphite field. Light mode is the binder page (`{colors.paper}` and `{colors.ink}`) for people who read on paper-white.

## Colors

The system is a graphite field with transit-line colours and exactly one accent.

- **Graphite** `{colors.surface}` is the canvas: never pure black, so line colours keep their saturation. `{colors.surface-raised}` holds nodes and panels. `{colors.surface-sunken}` holds code, inputs and exhibit tags, which are always recessed and never raised.
- **Bone** `{colors.on-surface}` carries all text. `{colors.on-surface-muted}` is for metadata such as line numbers, counts and secondary labels.
- **Hairlines** `{colors.outline}` divide; `{colors.outline-strong}` marks focus-adjacent borders and the dashed outline of inferred elements.
- **Highlighter** `{colors.primary}` is the single accent. It means *this is the proof, or this is what you're following*. It appears in exactly three places: the primary call to action ("Map this repo"), the active request-trace path, and evidence lines, shown as a dim strip in `{colors.highlight}`. Nothing else is yellow, so when it appears the eye goes straight to it.
- **Transit lines**, one per layer, are used for node accent stripes, edge strokes and layer tags:
  - Routes `{colors.layer-route}`: signal blue
  - Handlers and functions `{colors.layer-handler}`: steel grey, because they are the connective track, not a destination
  - Middleware `{colors.layer-middleware}`: guard orange
  - Prisma models and tables `{colors.layer-model}`: ledger green
  - External services `{colors.layer-service}`: magenta
  - Env vars `{colors.layer-env}`: teal
- **Findings** use `{colors.error}` for security-relevant findings (unguarded write, unvalidated body) and `{colors.warning}` for hygiene (unused model, undocumented env var, circular import).

Colour is never the only signal. Layers also carry a `layer-tag` label and an icon, `inferred` is drawn dashed, and findings carry a severity word.

In light mode, `{colors.paper}` replaces the surfaces and `{colors.ink}` replaces the text. Layer colours darken about 15% lightness to hold 3:1 against paper, and the highlighter becomes an 18%-opacity strip under ink text.

## Typography

There is one family, IBM Plex, in three cuts, because it was drawn for engineering documentation and reads like a spec sheet, not a startup.

- **Plex Sans** for UI and prose. `{typography.display}` appears only once, in the landing-page headline. Inside the app, nothing is larger than `{typography.headline-md}`.
- **Plex Sans Condensed** for anything on the map: node labels in `{typography.label-md}` and uppercase layer tags in `{typography.label-sm}`. Condensed is transit signage: it fits `POST /api/organizations/[id]/members` on a node without truncation.
- **Plex Mono** for paths, code, line ranges, SHAs and counts. If a value came from the repo, it is set in mono. That's how a user tells *fact* from *interface* at a glance.

Use figures in mono for anything counted (`38 routes · 12 models`). Use sentence case everywhere except layer tags.

## Layout

- The app is three panes. The left rail (240px) holds views, layer filters and findings. The canvas fills the middle. The evidence panel (`{spacing.panel-width}`) slides in from the right. The canvas is never covered by a modal; dialogs exist only for share and export.
- The canvas shows a faint drafting grid at `{spacing.canvas-grid}` in `{colors.outline}` at 40% opacity. Nodes snap to it, and ELK layout output is rounded to it.
- The spacing scale is `{spacing.xs}` to `{spacing.3xl}` on a 4px base. Inside panels, the default gap is `{spacing.md}` and the gap between sections is `{spacing.xl}`.
- The landing page uses a 1120px max width with a 12-column grid. The hero puts the URL input above the fold, with a live, pre-analysed map underneath rather than a screenshot.

## Elevation & Depth

The world is flat, like a printed diagram. Depth comes from surface steps (sunken, surface, raised), not shadows.

- Nodes and the rail have no shadow, only a 1px `{colors.outline}` border.
- Only floating layers get a shadow, `0 8px 24px rgba(0,0,0,0.45)`: the evidence panel, the command palette (⌘K), tooltips and the share dialog.
- No glass, no backdrop blur, no glow. The active trace is shown by a thicker stroke (2px → 3px) in `{colors.primary}`, with non-trace nodes dimmed to 35% opacity, never by a bloom.

## Shapes

- Nodes use `{rounded.md}`, with a 3px left stripe in their layer colour (the transit line running into the station).
- Exhibit tags and layer tags use `{rounded.sm}`: rectangular, like a printed label.
- Pills (`{rounded.full}`) are only for the `extracted` / `inferred` badges.
- Edges are orthogonal with 6px corner radii (ELK orthogonal routing). There are no bezier spaghetti curves.
- `extracted` elements have a solid 1px border; `inferred` elements have a dashed 1px border in `{colors.outline-strong}`. The badge repeats it in words.

## Components

- **Repo URL input** (`input-repo-url`) is the hero of the landing page and the top bar of the app. It uses mono text, a placeholder of `github.com/owner/repo`, and an inline `button-primary` reading "Map this repo". Validation is inline, in plain words, and sits under the field.
- **Graph node** (`graph-node`) has a layer stripe, a condensed label, and a right-aligned mono count (e.g. `3 writes`). Hover raises the border to `{colors.outline-strong}`; selected uses a 2px `{colors.on-surface}` border. Collapsed groups show a stacked edge (two offset borders) and a member count.
- **Evidence panel** (`evidence-panel`) runs top to bottom: the node title with a badge (`badge-extracted` / `badge-inferred`) and a confidence value in mono, then one `exhibit-tag` per evidence item, then a `code-snippet` with Shiki highlighting, where the proving lines use `code-line-evidence`, the highlighter strip. Every exhibit tag links to the exact GitHub permalink at that SHA.
- **Request tracer** uses the same panel as a numbered hop list (1 Route → 2 Middleware → 3 Handler → …), with each hop's snippet collapsible.
- **Finding row** (`finding-error` / `finding-warning`) shows a severity word, a one-sentence message in body text, and the nodes it touches as clickable layer tags. Clicking one frames those nodes on the canvas.
- **Pipeline progress** is a horizontal six-stop transit line (Fetch · Parse · Extract · Link · Analyse · Group). Stops fill as stages complete, and live counts tick beside them in mono (`412 files`, `38 routes`).
- **Benchmarks page** uses tables first and charts second. Precision and recall per category go in a plain table; the history chart is one line per category in layer colours, with the target drawn as a dashed rule.

## Motion

Motion explains causality. It never decorates. When something moves, it is showing you *where a request goes* or *what just finished*.

- **anime.js** owns choreography. The request trace draws hop by hop: each edge animates `strokeDashoffset` over `{motion.trace-hop}` with `{motion.ease-draw}`, staggered by `{motion.trace-stagger}`, and the next node lights only when its incoming edge arrives. Pipeline stops fill the same way. Counts in the progress line count up over `{motion.count-up}`.
- **CSS transitions** own UI feedback. Hover and press take `{motion.feedback}`; panel slide-in takes `{motion.panel}`; both use `{motion.ease-standard}`.
- The camera (React Flow `fitView` / `setCenter`) eases over 300ms when framing a selection. It never auto-pans while the user is dragging.
- There's no bounce, spring overshoot, parallax or idle animation on the canvas. A still map is correct.
- Under `prefers-reduced-motion`, traces appear instantly, counts jump to their final value, and camera moves cut.

## Implementation stack

| Concern | Library | Rule |
| --- | --- | --- |
| Tokens → CSS | Tailwind CSS v4 | Generated from this file: `designmd export --format css-tailwind DESIGN.md`. No hard-coded hex in components. |
| App primitives | shadcn/ui on Radix | Dialog, Tabs, Tooltip, DropdownMenu, ScrollArea, plus a ⌘K palette via `cmdk`. Restyle to these tokens; never ship shadcn's default zinc look. |
| Graph | React Flow + elkjs | Custom node components only. Orthogonal edge routing. |
| Choreography | anime.js v4 | Trace drawing, pipeline progress, count-ups. The only animation library inside the app. |
| Landing-page effects | Aceternity UI (copy-paste, curated) | Allowed: **Tracing Beam** (the How-it-works scroll is literally a trace), **Grid / Dot background** (it's the drafting grid), **Code block**. These pull in `motion` as a dependency, which is acceptable on marketing routes only. |
| Code snippets | Shiki | A custom theme built from these tokens; evidence lines via line decorations. |
| Icons | Lucide | 16px in the UI, 1.5px stroke, `{colors.on-surface-muted}` unless they denote a layer. |
| Charts | Recharts or visx | Layer colours, no gradients, target line dashed. |

**Banned Aceternity components:** Aurora Background, Spotlight, Lamp, Meteors, Sparkles, Background Beams, Glowing Stars, 3D Card, Wavy Background and gradient/animated text. They belong to the "AI startup" register this product exists to argue against.

## Do's and Don'ts

- **Do** put a real, pre-analysed map on the landing page (cal.com or similar) that visitors can click. The product is the hero image.
- **Do** set every value that came from the repo (paths, routes, line numbers, SHAs, counts) in Plex Mono. Interface chrome is never mono.
- **Do** keep yellow scarce. If you're about to use `{colors.primary}` for anything other than the CTA, the trace or evidence, don't.
- **Do** pair every colour signal with a word or line style (badge text, dashed border, severity label).
- **Don't** use gradients, glassmorphism, glows, aurora or mesh backgrounds, or purple-to-blue anything.
- **Don't** use emoji as icons in the product UI, or a bento grid of feature cards with icons in circles.
- **Don't** write "AI-powered", "magic" or "✨" in UI copy. Say what it found: "38 routes, 12 models, 4 findings."
- **Don't** round anything beyond `{rounded.lg}` except badges, and don't use soft 16–24px "friendly" card radii.
- **Don't** animate the canvas when nothing has happened. No floating nodes, no pulsing dots, no breathing gradients.
- **Don't** let the LLM's voice into the interface. Group summaries are labelled `inferred` and set in body text; they are never headlines.
