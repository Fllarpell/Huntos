function hhVacancyUrl() {
  const href = location.href;
  const path = href.match(/\/vacancy\/(\d+)/i);
  if (path) return `https://hh.ru/vacancy/${path[1]}`;
  const query = href.match(/[?&]vacancyId=(\d+)/i);
  if (query) return `https://hh.ru/vacancy/${query[1]}`;
  return "";
}

function visible(el) {
  if (!el) return false;
  const box = el.getBoundingClientRect();
  return box.width > 40 && box.height > 24;
}

function findLetterField() {
  const sels = [
    'textarea[data-qa="vacancy-response-popup-form-letter-input"]',
    'textarea[data-qa*="letter-input"]',
    'textarea[data-qa*="letter"]',
    'textarea[name="letter"]',
    '[contenteditable="true"][data-qa*="letter"]',
  ];
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (visible(el)) return el;
  }
  const areas = [...document.querySelectorAll("textarea")].filter((node) => {
    const name = String(node.getAttribute("name") || "");
    return !/^task_/.test(name) && visible(node);
  });
  return areas[0] || null;
}

function openLetterBox() {
  const qa = document.querySelector('[data-qa*="letter-toggle"]');
  if (qa) {
    qa.click();
    return true;
  }
  const hints = ["написать сопроводительное", "добавить сопроводительное"];
  const nodes = [...document.querySelectorAll("button, a, label, span, [role='button']")];
  for (const node of nodes) {
    const text = (node.innerText || "").trim().toLowerCase();
    if (text.length > 80) continue;
    if (hints.some((hint) => text.includes(hint))) {
      node.click();
      return true;
    }
  }
  return false;
}

function setField(el, value) {
  if (!el) return false;
  if (el.isContentEditable) {
    el.focus();
    el.innerText = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  }
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, "value");
  if (desc && desc.set) desc.set.call(el, value);
  else el.value = value;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fillLetter(text) {
  if (!findLetterField()) openLetterBox();
  for (let i = 0; i < 8; i += 1) {
    const field = findLetterField();
    if (field && setField(field, text)) return true;
    await sleep(250);
  }
  return false;
}

function ensureButton() {
  if (!hhVacancyUrl()) {
    const old = document.getElementById("huntos-hh-letter");
    if (old) old.remove();
    return;
  }
  if (document.getElementById("huntos-hh-letter")) return;
  const btn = document.createElement("button");
  btn.id = "huntos-hh-letter";
  btn.type = "button";
  btn.textContent = "письмо HuntOS";
  Object.assign(btn.style, {
    position: "fixed",
    right: "16px",
    bottom: "16px",
    zIndex: "2147483646",
    border: "0",
    borderRadius: "10px",
    padding: "8px 12px",
    background: "#7dd3c7",
    color: "#090a0c",
    font: "600 13px/1.2 ui-sans-serif, system-ui, sans-serif",
    cursor: "pointer",
    boxShadow: "0 8px 24px rgba(0,0,0,.25)",
  });
  btn.addEventListener("click", () => void runLetter(btn));
  document.documentElement.appendChild(btn);
}

async function runLetter(btn) {
  const url = hhVacancyUrl() || location.href;
  btn.disabled = true;
  const prev = btn.textContent;
  btn.textContent = "пишу…";
  try {
    const html = document.documentElement ? document.documentElement.outerHTML.slice(0, 350000) : "";
    const row = await chrome.runtime.sendMessage({ type: "hh-letter", url, html });
    if (!row || !row.ok) {
      if (row && row.login) window.open(row.login, "_blank");
      throw new Error((row && row.error) || "не вышло");
    }
    const ok = await fillLetter(row.text);
    if (!ok) {
      await navigator.clipboard.writeText(row.text);
      btn.textContent = "скопировал";
      return;
    }
    btn.textContent = "в форме";
  } catch (err) {
    btn.textContent = err instanceof Error ? err.message : "ошибка";
  } finally {
    btn.disabled = false;
    window.setTimeout(() => {
      if (document.getElementById("huntos-hh-letter") === btn) btn.textContent = prev;
    }, 2400);
  }
}

ensureButton();
new MutationObserver(() => ensureButton()).observe(document.documentElement, {
  subtree: true,
  childList: true,
});
