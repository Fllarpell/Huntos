export const FEEDBACK_PAGES = [
  { href: "/", label: "Inbox" },
  { href: "/pipeline", label: "Воронка" },
  { href: "/time", label: "Время" },
  { href: "/contacts", label: "Контакты" },
  { href: "/internships", label: "Стажировки" },
  { href: "/hackathons", label: "Хакатоны" },
  { href: "/thesis", label: "Тезис" },
  { href: "/settings", label: "Настройки" },
] as const;

const BY_HREF = new Map<string, string>(FEEDBACK_PAGES.map((item) => [item.href, item.label]));

let settingsTab: string | null = null;

export function setFeedbackSettingsTab(label: string | null) {
  settingsTab = label;
}

export function pageLabel(page: string | null | undefined): string | null {
  const raw = (page || "").trim();
  if (!raw) return null;
  if (BY_HREF.has(raw)) return BY_HREF.get(raw) || raw;
  const path = raw.split("?")[0];
  if (path !== raw && BY_HREF.has(path)) {
    const base = BY_HREF.get(path) || path;
    const rest = raw.slice(path.length).replace(/^[?&#]/, "");
    return rest ? `${base} · ${rest}` : base;
  }
  return raw;
}

export function currentFeedbackPage(): string {
  if (typeof window === "undefined") return "Inbox";
  const path = window.location.pathname || "/";
  const base = BY_HREF.get(path) || path;
  if (path === "/settings" && settingsTab) return `${base} · ${settingsTab}`;
  return base;
}
