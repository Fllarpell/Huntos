const DEFAULT_ORIGIN = "https://127.0.0.1:8443";

const JOBISH = new Set([
  "vacancies",
  "vacancy",
  "jobs",
  "job",
  "careers",
  "career",
  "positions",
  "position",
  "openings",
  "opening",
]);

function setStatus(text) {
  document.getElementById("status").textContent = text || "";
}

async function origin() {
  const stored = await chrome.storage.local.get("origin");
  return String(stored.origin || DEFAULT_ORIGIN).replace(/\/$/, "");
}

async function ensureOrigin(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return;
  const pattern = `${parsed.origin}/*`;
  if (await chrome.permissions.contains({ origins: [pattern] })) return;
  const ok = await chrome.permissions.request({ origins: [pattern] });
  if (!ok) throw new Error("нужен доступ к этой странице");
}

function errorText(payload, fallback) {
  if (payload && typeof payload === "object" && payload.detail) {
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

function hhVacancyId(url) {
  const path = String(url || "").match(/\/vacancy\/(\d+)/i);
  if (path) return path[1];
  const query = String(url || "").match(/[?&]vacancyId=(\d+)/i);
  return query ? query[1] : "";
}

function pageShape(url) {
  let path = "/";
  try {
    path = new URL(url).pathname.replace(/\/+$/, "") || "/";
  } catch {
    return "other";
  }
  const parts = path.split("/").filter(Boolean);
  const idx = parts.findIndex((part) => JOBISH.has(part.toLowerCase()));
  if (idx < 0) return /vacanc|\/jobs?\/|\/careers?\//i.test(path) ? "unknown" : "other";
  const rest = parts.slice(idx + 1);
  if (!rest.length) return "listing";
  if (rest.length === 1 && !/\d{3,}|--|uuid/i.test(rest[0])) return "listing";
  return "detail";
}

function localJudge(scrape, url) {
  if (hhVacancyId(url)) {
    return { kind: "vacancy", label: "вакансия HH" };
  }
  const shape = pageShape(url);
  if (scrape.hasJobPosting) {
    return { kind: "vacancy", label: "вакансия (schema.org)" };
  }
  if (shape === "listing" || (scrape.jobLinkCount >= 8 && shape !== "detail")) {
    return { kind: "listing", label: "каталог — открой одну карточку" };
  }
  if (scrape.applyCta && scrape.jobSections) {
    return { kind: "vacancy", label: "похоже на вакансию" };
  }
  if (shape === "detail" && (scrape.jobWords || scrape.jobSections)) {
    return { kind: "vacancy", label: "карточка вакансии" };
  }
  if (!scrape.jobWords && !scrape.jobSections && !scrape.applyCta) {
    return { kind: "noise", label: "не похоже на вакансию" };
  }
  return { kind: "maybe", label: "не уверен — можно попробовать" };
}

function scrapePage() {
  let hasJobPosting = false;
  document.querySelectorAll('script[type="application/ld+json"]').forEach((node) => {
    try {
      const data = JSON.parse(node.textContent || "");
      const walk = (value) => {
        if (!value || typeof value !== "object") return;
        if (Array.isArray(value)) {
          value.forEach(walk);
          return;
        }
        const raw = value["@type"];
        const types = (Array.isArray(raw) ? raw : [raw]).map((item) => String(item || "").toLowerCase());
        if (types.includes("jobposting")) hasJobPosting = true;
        if (value["@graph"]) walk(value["@graph"]);
      };
      walk(data);
    } catch {
      /* ignore broken json-ld */
    }
  });
  if (document.querySelector('[itemtype*="JobPosting" i]')) hasJobPosting = true;
  const h1s = [...document.querySelectorAll("h1")]
    .map((node) => (node.innerText || "").trim())
    .filter(Boolean);
  const descNode = document.querySelector(
    "[itemprop='description'], [class*='vacancyDescription' i], [class*='job-description' i], [class*='JobDescription'], [class*='vacancy-description' i], [class*='vacancies-detail'], article, main",
  );
  const text = (descNode?.innerText || document.body?.innerText || "").trim().slice(0, 20000);
  const sample = text.slice(0, 8000);
  return {
    title: h1s[0] || (document.title || "").trim(),
    description: text,
    html: document.documentElement ? document.documentElement.outerHTML.slice(0, 350000) : "",
    hasJobPosting,
    applyCta: /отклик|отправить резюме|apply now|send resume|i['’]m interested/i.test(sample),
    jobSections: /обязанност|требования|responsibilit|requirements|чем предстоит|мы предлагаем|qualifications/i.test(sample),
    jobWords: /ваканси|developer|разработ|engineer|зарплат|оклад|middle|senior|python|frontend|backend/i.test(sample),
    jobLinkCount: document.querySelectorAll('a[href*="vacanc" i], a[href*="/job" i], a[href*="career" i]').length,
  };
}

async function scrapeTab(tabId) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: scrapePage,
  });
  if (!result || typeof result !== "object") {
    throw new Error("страница не отдала HTML");
  }
  return result;
}

function paintJudge(judge, scrape, url) {
  document.getElementById("verdict").textContent = judge.label;
  document.getElementById("preview").textContent = scrape.title || "";
  const clip = document.getElementById("clip");
  const force = document.getElementById("force");
  const letter = document.getElementById("letter");
  clip.disabled = judge.kind === "listing" || judge.kind === "noise";
  force.hidden = judge.kind !== "noise" && judge.kind !== "maybe";
  letter.hidden = !hhVacancyId(url || "");
}

async function clipTab(force) {
  const button = document.getElementById("clip");
  const forceBtn = document.getElementById("force");
  button.disabled = true;
  forceBtn.disabled = true;
  setStatus("кладу…");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tab?.url || "";
    if (!url || url.startsWith("chrome") || url.startsWith("edge") || url.startsWith("about:")) {
      setStatus("открой страницу вакансии");
      return;
    }
    const base = await origin();
    await ensureOrigin(base);
    await ensureOrigin(url);
    const cookie = await chrome.cookies.get({ url: base, name: "hunt_session" });
    if (!cookie?.value) {
      setStatus("зайди в HuntOS в этом Chrome");
      await chrome.tabs.create({ url: `${base}/login` });
      return;
    }
    if (tab.id == null) throw new Error("нет вкладки");
    const scraped = await scrapeTab(tab.id);
    const res = await fetch(`${base}/api/vacancies/clip`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Hunt-Session": cookie.value,
      },
      body: JSON.stringify({
        url,
        title: scraped.title || tab.title || null,
        description: scraped.description || null,
        html: scraped.html || null,
        force: Boolean(force),
      }),
    });
    let payload = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
    if (res.status === 401) {
      setStatus("сессия истекла — зайди снова");
      await chrome.tabs.create({ url: `${base}/login` });
      return;
    }
    if (!res.ok) {
      throw new Error(errorText(payload, `ошибка ${res.status}`));
    }
    const title = payload?.vacancy?.title || scraped.title || "";
    setStatus(`${payload?.created ? "в inbox" : "уже была — обновил"}: ${title || "карточка"}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : "не вышло";
    setStatus(message);
    const network = err instanceof TypeError;
    if (network) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const base = await origin();
      if (tab?.url) {
        await chrome.tabs.create({ url: `${base}/?clip=${encodeURIComponent(tab.url)}` });
      }
    }
  } finally {
    button.disabled = false;
    forceBtn.disabled = false;
  }
}

document.getElementById("clip").addEventListener("click", () => void clipTab(false));
document.getElementById("force").addEventListener("click", () => void clipTab(true));
document.getElementById("letter").addEventListener("click", () => {
  void (async () => {
    const letter = document.getElementById("letter");
    letter.disabled = true;
    setStatus("письмо…");
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const url = tab?.url || "";
      if (tab?.id == null) throw new Error("нет вкладки");
      const scraped = await scrapeTab(tab.id);
      const row = await chrome.runtime.sendMessage({
        type: "hh-letter",
        url,
        html: scraped.html || "",
      });
      if (!row || !row.ok) {
        if (row && row.login) await chrome.tabs.create({ url: row.login });
        throw new Error((row && row.error) || "не вышло");
      }
      const [{ result }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (text) => {
          const visible = (el) => {
            if (!el) return false;
            const box = el.getBoundingClientRect();
            return box.width > 40 && box.height > 24;
          };
          const field = [
            'textarea[data-qa="vacancy-response-popup-form-letter-input"]',
            'textarea[data-qa*="letter"]',
            'textarea[name="letter"]',
          ]
            .map((sel) => document.querySelector(sel))
            .find(visible);
          const box = field || [...document.querySelectorAll("textarea")].find(visible);
          if (!box) return false;
          const proto = HTMLTextAreaElement.prototype;
          const desc = Object.getOwnPropertyDescriptor(proto, "value");
          if (desc && desc.set) desc.set.call(box, text);
          else box.value = text;
          box.dispatchEvent(new Event("input", { bubbles: true }));
          return true;
        },
        args: [row.text],
      });
      setStatus(result ? "в форме HH" : "нет поля — открой отклик");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "не вышло");
    } finally {
      letter.disabled = false;
    }
  })();
});

chrome.tabs.query({ active: true, currentWindow: true }).then(async ([tab]) => {
  const url = tab?.url || "";
  if (!url || url.startsWith("chrome") || url.startsWith("edge") || url.startsWith("about:")) {
    paintJudge({ kind: "noise", label: "открой страницу вакансии" }, { title: "" }, url);
    return;
  }
  try {
    if (tab.id == null) throw new Error("нет вкладки");
    await ensureOrigin(url);
    const scraped = await scrapeTab(tab.id);
    paintJudge(localJudge(scraped, url), scraped, url);
  } catch (err) {
    const message = err instanceof Error ? err.message : "не прочитал страницу";
    paintJudge({ kind: "maybe", label: message }, { title: tab?.title || "" }, url);
  }
});
