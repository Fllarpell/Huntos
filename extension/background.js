const DEFAULT_ORIGIN = "https://127.0.0.1:8443";

async function origin() {
  const stored = await chrome.storage.local.get("origin");
  return String(stored.origin || DEFAULT_ORIGIN).replace(/\/$/, "");
}

function errorText(payload, fallback) {
  if (payload && typeof payload === "object" && payload.detail) {
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

async function huntFetch(path, init) {
  const base = await origin();
  const cookie = await chrome.cookies.get({ url: base, name: "hunt_session" });
  if (!cookie?.value) {
    const err = new Error("зайди в HuntOS в этом Chrome");
    err.code = "auth";
    err.login = `${base}/login`;
    throw err;
  }
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Hunt-Session": cookie.value,
      ...(init && init.headers),
    },
  });
  let payload = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }
  if (res.status === 401) {
    const err = new Error("сессия истекла — зайди снова");
    err.code = "auth";
    err.login = `${base}/login`;
    throw err;
  }
  if (!res.ok) {
    throw new Error(errorText(payload, `ошибка ${res.status}`));
  }
  return payload;
}

async function hhLetter(url, html) {
  const base = await origin();
  const clip = await huntFetch("/api/vacancies/clip", {
    method: "POST",
    body: JSON.stringify({
      url,
      html: html || null,
      force: /vacancyId=|vacancy_response/i.test(url || ""),
    }),
  });
  const vacancy = clip && clip.vacancy;
  if (!vacancy || !vacancy.id) {
    throw new Error("карточка не создалась");
  }
  const letter = await huntFetch(`/api/vacancies/${vacancy.id}/hh-letter`, {
    method: "POST",
    body: JSON.stringify({ origin: base }),
  });
  return {
    text: (letter && letter.letter) || "",
    title: vacancy.title || "",
    profile: (letter && letter.profile_url) || "",
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.type !== "hh-letter") return undefined;
  hhLetter(msg.url || "", msg.html || "")
    .then((row) => sendResponse({ ok: true, ...row }))
    .catch((err) =>
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : "не вышло",
        login: err && err.login,
      }),
    );
  return true;
});
