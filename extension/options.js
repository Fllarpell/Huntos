const DEFAULT_ORIGIN = "https://127.0.0.1:8443";

async function load() {
  const stored = await chrome.storage.local.get("origin");
  document.getElementById("origin").value = stored.origin || DEFAULT_ORIGIN;
}

document.getElementById("save").addEventListener("click", async () => {
  const raw = document.getElementById("origin").value.trim().replace(/\/$/, "") || DEFAULT_ORIGIN;
  let url;
  try {
    url = new URL(raw);
  } catch {
    document.getElementById("ok").textContent = "нужен https://…";
    return;
  }
  const origin = url.origin;
  await chrome.storage.local.set({ origin });
  try {
    await chrome.permissions.request({ origins: [`${origin}/*`] });
  } catch {
    /* optional */
  }
  document.getElementById("ok").textContent = "сохранено";
});

void load();
