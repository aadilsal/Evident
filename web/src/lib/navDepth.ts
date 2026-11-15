// How many in-site pages are behind this one, stored on each history entry (survives reloads).
// Next's router only ever calls pushState/replaceState, so wrapping them is enough.

const KEY = "evDepth";
const EVENT = "evident:navigate";
let installed = false;

function depthOf(state: unknown): number {
  const d = (state as Record<string, unknown> | null)?.[KEY];
  return typeof d === "number" ? d : 0;
}

function install(): void {
  if (installed || typeof window === "undefined") return;
  installed = true;
  const { pushState, replaceState } = window.history;
  window.history.pushState = function (data: unknown, unused: string, url?: string | URL | null) {
    const next = { ...(data as object), [KEY]: depthOf(window.history.state) + 1 };
    pushState.call(this, next, unused, url);
    queueMicrotask(() => window.dispatchEvent(new Event(EVENT)));
  };
  window.history.replaceState = function (
    data: unknown,
    unused: string,
    url?: string | URL | null,
  ) {
    const next = { ...(data as object), [KEY]: depthOf(window.history.state) };
    replaceState.call(this, next, unused, url);
    queueMicrotask(() => window.dispatchEvent(new Event(EVENT)));
  };
}

export function subscribeNav(onChange: () => void): () => void {
  install();
  window.addEventListener("popstate", onChange);
  window.addEventListener(EVENT, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(EVENT, onChange);
  };
}

/** 0 on the page the visitor landed on; n after n in-site navigations. */
export function navDepth(): number {
  return depthOf(window.history.state);
}

export function currentPath(): string {
  return window.location.pathname;
}
