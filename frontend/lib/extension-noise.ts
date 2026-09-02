const ATTRS = ["bis_skin_checked", "bis_register"];

function blobOf(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (value instanceof Error) return `${value.message}\n${value.stack ?? ""}`;
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

export function isExtensionNoise(...parts: unknown[]): boolean {
  const text = parts.map(blobOf).join("\n");
  return (
    text.includes("chrome-extension://") ||
    text.includes("bis_skin") ||
    text.includes("M_ID") ||
    text.includes("hydrated but some attributes")
  );
}

function stripNode(node: Node) {
  if (!(node instanceof Element)) return;
  for (const attr of ATTRS) {
    if (node.hasAttribute(attr)) node.removeAttribute(attr);
  }
}

function stripTree(root: Node = document.documentElement) {
  if (!(root instanceof Element) && !(root instanceof Document)) return;
  stripNode(root);
  root.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(",")).forEach(stripNode);
}

function wrapConsole() {
  const orig = console.error;
  if ((orig as { __huntFiltered?: boolean }).__huntFiltered) return;
  const filtered = (...args: unknown[]) => {
    if (isExtensionNoise(...args)) return;
    orig.apply(console, args);
  };
  (filtered as { __huntFiltered?: boolean }).__huntFiltered = true;
  console.error = filtered as typeof console.error;
}

let installed = false;

/** Run before React hydrates. Extensions mutate HTML and throw into the Next overlay. */
export function installExtensionNoiseGuard() {
  if (typeof window === "undefined" || installed) return;
  installed = true;

  stripTree();
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === "attributes") stripNode(mutation.target);
      else mutation.addedNodes.forEach((node) => stripTree(node as ParentNode));
    }
  });
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ATTRS,
  });

  const swallow = (event: Event) => {
    const errorEvent = event as ErrorEvent & { reason?: unknown };
    if (
      isExtensionNoise(
        errorEvent.error,
        errorEvent.reason,
        errorEvent.message,
        errorEvent.filename,
      )
    ) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  };
  window.addEventListener("error", swallow, true);
  window.addEventListener("unhandledrejection", swallow, true);

  wrapConsole();
  queueMicrotask(wrapConsole);
  setTimeout(wrapConsole, 0);
  setTimeout(wrapConsole, 50);
}
