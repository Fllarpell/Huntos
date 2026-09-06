from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import urlparse

from app.services.scraper.jsonld import extract_job_posting
from app.services.scraper.salary import parse_salary
from app.services.scraper.sources.hirehi import strip_html

KIND_VACANCY = "vacancy"
KIND_LISTING = "listing"
KIND_NOISE = "noise"

_JOBISH_PATH = frozenset(
    {
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
        "вакансии",
        "вакансия",
    }
)
_BOARD_HOST = re.compile(
    r"(?:^|\.)("
    r"hh\.ru|rabota\.by|hh\.kz|hh1\.az|hirehi\.ru|career\.habr\.com|getmatch\.ru|"
    r"geekjob\.ru|linkedin\.com|indeed\.com|glassdoor\.com"
    r")$",
    re.I,
)
_NOISE_HOST = re.compile(
    r"(?:^|\.)("
    r"wikipedia\.org|youtube\.com|youtu\.be|twitter\.com|x\.com|reddit\.com|"
    r"facebook\.com|instagram\.com|tiktok\.com|vk\.com|ok\.ru"
    r")$",
    re.I,
)
_BOARD_COMPANY = frozenset(
    {
        "headhunter",
        "hh.ru",
        "хабр",
        "хабр карьера",
        "habr",
        "habr career",
        "linkedin",
        "indeed",
        "getmatch",
        "geekjob",
        "hirehi",
        "glassdoor",
        "avito работа",
    }
)
_ROLE = re.compile(
    r"(разработ|developer|engineer|инженер|аналитик|analyst|дизайнер|designer|"
    r"менеджер|manager|qa\b|тестиров|devops|sre\b|product\b|data\b|ml\b|frontend|"
    r"backend|fullstack|android|ios\b|scientist|researcher|рекрутер|hr[ -]?[bm]|"
    r"архитектор|architect|руководитель|лид|lead\b|специалист)",
    re.I,
)
_JOB_WORD = re.compile(r"(ваканси|job posting|we're hiring|ищем|открытая позиция)", re.I)
_APPLY = re.compile(
    r"(откликнуться|откликн|отправить резюме|оставить отклик|apply now|apply for|"
    r"send resume|i['’]m interested|respond to vacancy)",
    re.I,
)
_SECTIONS = re.compile(
    r"(обязанност|требования|чем (вам )?предстоит|мы предлагаем|условия работы|"
    r"responsibilit|requirements|qualifications|what you.?ll do|about the role|"
    r"what we offer|you will)",
    re.I,
)
_GRADE = re.compile(
    r"\b(intern(?:ship)?|стаж[её]р|junior|джун(?:иор)?|middle|мидл|senior|сеньор|"
    r"lead|лид|head|principal)\b",
    re.I,
)
_GRADE_MAP = {
    "intern": "intern",
    "internship": "intern",
    "стажер": "intern",
    "стажёр": "intern",
    "junior": "junior",
    "джун": "junior",
    "джуниор": "junior",
    "middle": "middle",
    "мидл": "middle",
    "senior": "senior",
    "сеньор": "senior",
    "lead": "lead",
    "лид": "lead",
    "head": "head",
    "principal": "lead",
}
_TITLE_TAG = re.compile(r"<title[^>]*>([^<]+)", re.I)
_OG_TITLE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_OG_TITLE_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:title["\']',
    re.I,
)
_OG_SITE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:site_name["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
_MAIN = re.compile(r"<main\b[^>]*>(.*?)</main>", re.I | re.S)
_ITEMPROP_DESC = re.compile(
    r"<([a-z0-9]+)[^>]*itemprop=['\"]description['\"][^>]*>(.*?)</\1>",
    re.I | re.S,
)
_MICRO_JOB = re.compile(r"itemtype=['\"][^'\"]*JobPosting", re.I)
_JOB_HREF = re.compile(r"""href=["'][^"']*(?:vacanc|/jobs?/|/job/|career)[^"']*""", re.I)
_CITY_CHIP = re.compile(r"г\.\s*([А-ЯЁA-Z][\w.\-]+(?:[ -][А-ЯЁа-яёA-Za-z.\-]+)*)")
_STACK_LINE = re.compile(
    r"(?:наш\s+)?(?:стек|stack|технологи(?:и|ях)|tech(?:nology)? stack)\s*:\s*([^\n]+)",
    re.I,
)
_SAL_FROM = re.compile(r'"salaryFrom"\s*:\s*(\d+)')
_SAL_TO = re.compile(r'"salaryTo"\s*:\s*(\d+)')
_SALARY_LINE = re.compile(
    r"(?:зп|зарплат[аые]|оклад|salary|compensation)[^\n]{0,48}|"
    r"(?:от|до)\s+\d[\d\s\u00a0]{2,}\s*(?:[₽$€]|руб|тыс)|"
    r"\d[\d\s\u00a0]{2,}\s*[–-]\s*\d[\d\s\u00a0]{2,}\s*(?:[₽$€]|руб)",
    re.I,
)
_INN = re.compile(r"ИНН\s*[:№]?\s*(\d{10}|\d{12})")
_BOARD_TITLE = re.compile(
    r"^\s*(?P<title>.+?)\s+[—–-]\s+вакансии\s+в\s+(?P<company>.+?)(?:\s+[—–-]\s+(?P<city>.+?))?\s*\.?\s*$",
    re.I,
)
_HH_TITLE = re.compile(
    r"^\s*(?P<title>.+?)\s+вакансия(?:\s+компании)?\s+(?P<company>.+?)(?:[,\s]+(?P<city>[А-ЯЁ][\w.\-]+))?\s*$",
    re.I,
)
_PIPE_TITLE = re.compile(r"^\s*(?P<title>.{6,80}?)\s+[|·•]\s+(?P<company>.{2,60}?)\s*$")
_FORM_STOPS = (
    "Откликнуться",
    "Фамилия",
    "Прикрепить резюме",
    "Я даю согласие",
    "Политика конфиденциальности",
    "Apply for this job",
    "Submit application",
)
_DESC_CLASS = (
    "vacancyDescription",
    "vacancy-description",
    "vacancy__description",
    "vacancy_description",
    "job-description",
    "jobDescription",
    "job_description",
    "JobDescription",
    "vacancyBody",
    "vacancies-detail",
    "vacancy-section",
    "job-details",
    "job-posting",
    "jobPosting",
    "hh-vacancy",
)


@dataclass
class ClipJudgement:
    kind: str
    score: int
    reasons: list[str] = field(default_factory=list)
    message: str = ""

    @property
    def allow(self) -> bool:
        return self.kind == KIND_VACANCY


def _clean_text(raw: str | None) -> str:
    return unescape(re.sub(r"\s+", " ", strip_html(raw or ""))).strip()


def noisy_title(title: str) -> bool:
    text = (title or "").casefold()
    if "вакансии в" in text or "vacancies at" in text:
        return True
    return text.count("—") + text.count("–") >= 2


def page_shape(url: str | None) -> str:
    parsed = urlparse(url or "")
    path = (parsed.path or "/").rstrip("/") or "/"
    parts = [part for part in path.split("/") if part]
    idx = next((i for i, part in enumerate(parts) if part.lower() in _JOBISH_PATH), None)
    if idx is None:
        if re.search(r"vacanc|/jobs?/|/careers?/", path, re.I):
            return "unknown"
        return "other"
    rest = parts[idx + 1 :]
    if not rest:
        return "listing"
    if len(rest) == 1 and not re.search(r"\d{3,}|--|uuid", rest[0], re.I):
        return "listing"
    return "detail"


def _parse_named_title(title: str) -> dict[str, str]:
    text = (title or "").strip()
    if not text:
        return {}
    for pattern in (_BOARD_TITLE, _HH_TITLE, _PIPE_TITLE):
        match = pattern.match(text)
        if not match:
            continue
        role = (match.group("title") or "").strip()
        if not (_ROLE.search(role) or _JOB_WORD.search(text)):
            continue
        out: dict[str, str] = {"title": role[:512]}
        company = (match.groupdict().get("company") or "").strip(" .")
        if company and company.casefold() not in _BOARD_COMPANY:
            out["company"] = company[:255]
        city = (match.groupdict().get("city") or "").strip(" .")
        if city:
            out["location"] = city[:128]
        return out
    return {}


def _best_h1(html: str) -> str:
    found: list[tuple[int, str]] = []
    for match in _H1.finditer(html or ""):
        text = _clean_text(match.group(1))
        if not text or len(text) > 180:
            continue
        low = text.casefold()
        if low in {"вакансии", "карьера", "jobs", "careers", "меню", "поиск"}:
            continue
        score = 0
        if _ROLE.search(text):
            score += 4
        if _GRADE.search(text):
            score += 1
        if _JOB_WORD.search(text):
            score += 1
        if noisy_title(text):
            score -= 2
        found.append((score, text))
    if not found:
        return ""
    found.sort(key=lambda item: (item[0], -len(item[1])), reverse=True)
    return found[0][1]


def _inner_by_class(html: str, needle: str) -> str:
    start = re.search(
        rf"<([a-z0-9]+)[^>]*class=['\"][^'\"]*{re.escape(needle)}[^'\"]*['\"][^>]*>",
        html or "",
        re.I | re.S,
    )
    if not start:
        return ""
    tag = start.group(1)
    rest = (html or "")[start.end() :]
    close = re.search(rf"</{re.escape(tag)}\s*>", rest, re.I)
    return rest[: close.start()] if close else rest


def _cut_form(text: str) -> str:
    trimmed = text.strip()
    for stop in _FORM_STOPS:
        index = trimmed.find(stop)
        if index >= 80:
            return trimmed[:index].strip()
    return trimmed


def _description_from_html(html: str) -> str:
    blob = ""
    item = _ITEMPROP_DESC.search(html or "")
    if item:
        blob = item.group(2)
    if not blob:
        for needle in _DESC_CLASS:
            blob = _inner_by_class(html or "", needle)
            if blob:
                break
    if not blob:
        main = _MAIN.search(html or "")
        blob = main.group(1) if main else ""
    if not blob:
        after = re.search(r"</h1>(.*)", html or "", re.I | re.S)
        blob = after.group(1) if after else (html or "")
    blob = re.sub(r"<script\b[^>]*>.*?</script>", " ", blob, flags=re.I | re.S)
    blob = re.sub(r"<style\b[^>]*>.*?</style>", " ", blob, flags=re.I | re.S)
    return _cut_form(strip_html(blob))[:20000]


def _visible_text(html: str) -> str:
    blob = re.sub(r"<script\b[^>]*>.*?</script>", " ", html or "", flags=re.I | re.S)
    blob = re.sub(r"<style\b[^>]*>.*?</style>", " ", blob, flags=re.I | re.S)
    return strip_html(blob)[:24000]


def _map_grade(text: str) -> str:
    match = _GRADE.search(text or "")
    if not match:
        return ""
    key = match.group(1).casefold().replace("ё", "е")
    return _GRADE_MAP.get(key) or _GRADE_MAP.get(match.group(1).casefold()) or ""


def _fill_from_html(html: str, out: dict[str, str]) -> None:
    og = _OG_TITLE.search(html or "") or _OG_TITLE_REV.search(html or "")
    title_tag = _TITLE_TAG.search(html or "")
    page_title = _clean_text((og.group(1) if og else "") or (title_tag.group(1) if title_tag else ""))
    named = _parse_named_title(page_title)
    h1 = _best_h1(html or "")
    if h1 and (not out.get("title") or noisy_title(out["title"])):
        out["title"] = h1[:512]
    elif named.get("title") and (not out.get("title") or noisy_title(out["title"])):
        out["title"] = named["title"]
    elif page_title and not out.get("title"):
        out["title"] = page_title[:512]
    if named.get("company") and not out.get("company"):
        out["company"] = named["company"]
    site = _OG_SITE.search(html or "")
    site_name = _clean_text(site.group(1) if site else "")
    if site_name and not out.get("company") and site_name.casefold() not in _BOARD_COMPANY:
        if _ROLE.search(out.get("title") or "") or named:
            out["company"] = site_name[:255]
    if named.get("location") and not out.get("location"):
        out["location"] = named["location"]
    if not out.get("location"):
        chip = _CITY_CHIP.search(html or "")
        if chip:
            out["location"] = chip.group(1).strip()[:128]
    if not out.get("description"):
        desc = _description_from_html(html or "")
        if len(desc) >= 40:
            out["description"] = desc
    if not out.get("salary_raw"):
        lo, hi = _SAL_FROM.search(html or ""), _SAL_TO.search(html or "")
        if lo or hi:
            low = lo.group(1) if lo else ""
            high = hi.group(1) if hi else ""
            if low and high and low != high:
                out["salary_raw"] = f"от {low} до {high}"
            elif low:
                out["salary_raw"] = f"от {low}"
            elif high:
                out["salary_raw"] = f"до {high}"
        else:
            line = _SALARY_LINE.search(out.get("description") or "") or _SALARY_LINE.search(
                _visible_text(html or "")[:4000]
            )
            if line:
                raw = " ".join(line.group(0).split())
                if parse_salary(raw)[0] or parse_salary(raw)[1]:
                    out["salary_raw"] = raw[:128]
    if not out.get("skills"):
        stack = _STACK_LINE.search(out.get("description") or "") or _STACK_LINE.search(html or "")
        if stack:
            bits = [part.strip(" .;") for part in re.split(r"[,/]| и ", stack.group(1)) if part.strip(" .;")]
            if bits:
                out["skills"] = ", ".join(bits[:24])
    nearby = ""
    h1m = _H1.search(html or "")
    if h1m:
        nearby = strip_html((html or "")[max(0, h1m.start() - 400) : h1m.end() + 1800])
    blob = f"{out.get('description') or ''}\n{nearby}\n{out.get('title') or ''}"
    if not out.get("work_format"):
        if re.search(r"удал[её]нн|remote|telecommute", blob, re.I):
            out["work_format"] = "удалённо"
        elif re.search(r"гибрид|hybrid", blob, re.I):
            out["work_format"] = "гибрид"
        elif re.search(r"(?<![\w])офис(?![\wа-яё])", blob, re.I):
            out["work_format"] = "офис"
    if not out.get("grade"):
        grade = _map_grade(out.get("title") or "") or _map_grade(nearby) or _map_grade(blob[:800])
        if grade:
            out["grade"] = grade
    if not out.get("language") and re.search(r"английск|english\s*(b[12]|c[12]|fluent|required)", blob, re.I):
        out["language"] = "en"
    if not out.get("company_inn"):
        inn = _INN.search(html or "")
        if inn:
            out["company_inn"] = inn.group(1)


def extract_html(html: str, *, page_url: str | None = None) -> dict[str, str]:
    out = extract_job_posting(html, page_url=page_url)
    _fill_from_html(html or "", out)
    return out


def _host(url: str | None) -> str:
    return (urlparse(url or "").hostname or "").lower()


def judge_page(
    *,
    url: str | None,
    html: str | None,
    text: str | None = None,
    source: str | None = None,
    extracted: dict[str, str] | None = None,
) -> ClipJudgement:
    html = html or ""
    visible = (text or "").strip() or _visible_text(html)
    extracted = extracted or extract_html(html, page_url=url)
    schema = extract_job_posting(html, page_url=url)
    posting = bool(schema) or bool(_MICRO_JOB.search(html))
    shape = page_shape(url)
    host = _host(url)
    score = 0
    reasons: list[str] = []

    if schema:
        score += 80
        reasons.append("schema.org JobPosting")
    if _MICRO_JOB.search(html):
        score += 40
        reasons.append("microdata JobPosting")
    if source in {"hh", "hirehi", "habr", "getmatch", "geekjob", "career"}:
        score += 30
        reasons.append("известная доска")
    elif _BOARD_HOST.search(host):
        score += 20
        reasons.append("доска вакансий")
    if shape == "detail":
        score += 30
        reasons.append("url карточки")
    elif shape == "listing":
        score -= 20
        reasons.append("url каталога")
    if _APPLY.search(visible):
        score += 15
        reasons.append("кнопка отклика")
    if _SECTIONS.search(visible):
        score += 20
        reasons.append("блок обязанности/требования")
    if _ROLE.search(extracted.get("title") or "") or _ROLE.search(visible[:600]):
        score += 15
        reasons.append("должность")
    if extracted.get("salary_raw"):
        score += 10
        reasons.append("зарплата")
    if extracted.get("company") and extracted.get("description"):
        score += 10
        reasons.append("компания и описание")

    links = len(_JOB_HREF.findall(html))
    if links >= 8 and shape != "detail" and not posting:
        score -= 35
        reasons.append("много ссылок на вакансии")

    if _NOISE_HOST.search(host):
        score -= 70
        reasons.append("не карьерный сайт")
    if host.endswith("habr.com") and not host.startswith("career."):
        score -= 40
        reasons.append("статья Хабра, не вакансия")
    if host in {"yandex.ru", "www.yandex.ru", "google.com", "www.google.com"} and shape == "other":
        score -= 50
        reasons.append("поиск, не карточка")

    kind = KIND_NOISE
    if posting or (source in {"hh", "hirehi", "habr", "getmatch", "geekjob", "career"} and shape != "listing"):
        kind = KIND_VACANCY
    elif score >= 50:
        kind = KIND_VACANCY
    elif shape == "listing" and not posting:
        kind = KIND_LISTING
    elif links >= 8 and shape != "detail" and not posting:
        kind = KIND_LISTING
    elif score >= 30 and shape == "detail":
        kind = KIND_VACANCY

    if kind == KIND_VACANCY:
        message = "похоже на вакансию"
    elif kind == KIND_LISTING:
        message = "это каталог вакансий — открой одну карточку"
    else:
        message = "не похоже на вакансию (новость, статья или лента)"
    return ClipJudgement(kind=kind, score=max(0, min(100, score)), reasons=reasons, message=message)
