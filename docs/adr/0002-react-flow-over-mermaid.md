# 0002. Use React Flow + ELK instead of Mermaid for the map

- **Status:** Accepted
- **Date:** 2026-11-07

## Context

Every competitor renders static Mermaid. Our core interactions, which are the request tracer, blast radius, layer filters, collapsing groups and an evidence panel per node and edge, need per-element state, events and incremental highlighting. Graphs can reach hundreds of nodes.

## Decision

Render the map with React Flow using custom node components, and lay it out with elkjs (`layered`, orthogonal routing) in a Web Worker. Mermaid stays available as an **export** format (v1.5).

## Consequences

- Full control over interaction, styling ([DESIGN.md](../../DESIGN.md)) and animation (anime.js for traces).
- Clear differentiation from competitors in the first 10 seconds of a demo.
- **Cost:** we own the layout quality; ELK tuning takes time. Large graphs need virtualisation and collapsed groups by default.
- Bundle size is larger than a Mermaid render; the map route is code-split.

## Alternatives considered

- **Mermaid:** no element-level interactivity, poor layout control for large graphs, and identical to competitors.
- **Cytoscape.js:** strong graph algorithms, but canvas rendering makes rich HTML nodes and accessible focus states harder.
- **D3 force layout:** non-deterministic positions, which hurts permalinks and diffing.
