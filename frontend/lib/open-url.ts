export function openExternalUrl(url: string) {
  const href = /^https?:\/\//i.test(url.trim()) ? url.trim() : `https://${url.trim()}`;
  const win = window.open(href, "_blank", "noopener,noreferrer");
  if (win) {
    try {
      win.opener = null;
    } catch {
      /* ignore */
    }
    return;
  }
  window.location.assign(href);
}

export function onExternalClick(url: string, event: { button?: number; metaKey?: boolean; ctrlKey?: boolean; shiftKey?: boolean; altKey?: boolean; preventDefault: () => void; stopPropagation: () => void }) {
  event.stopPropagation();
  if ((event.button ?? 0) !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  openExternalUrl(url);
}
