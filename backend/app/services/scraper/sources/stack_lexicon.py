"""IT stack labels from public catalogs, plus generated title variants.

Seeds are copied from filter UIs / role dictionaries (not invented synonym lists).
Runtime matching does not crawl; CI stays offline.

Catalogs:
- HH professional_roles, category 11 «Информационные технологии»
  https://api.hh.ru/professional_roles
- Habr Career specializations / divisions
  https://career.habr.com/vacancies
  https://career.habr.com/info/divisions
- HireHi subcategories (``hirehi_filters.SUBCATEGORIES``)
- GetMatch specialties (``getmatch_filters.SPECIALTIES``)
- Yandex Jobs professions https://yandex.ru/jobs/api/professions/
- T-Bank IT profession chips https://www.tbank.ru/career/vacancies/it/
- Avito career directories https://career.avito.com/vacancies/
- VK team IT specialties (``career_catalog.VK_IT_SPECIALTIES``)
- Megafon job specialties https://job.megafon.ru/
- YADRO specializations / titles https://careers.yadro.com/api/vacancies
- Kaspersky vacancy categories https://careers.kaspersky.ru/vacancies
- Solar (РТК) vacancy titles https://team.rt-solar.ru/vacancies/

Combinations (hyphen / space / slash × role suffix from those same catalogs)
are generated in code so «ML-тимлид» and «ML инженер» both hit.
"""

from __future__ import annotations

import re
from functools import cache

# Role words glued onto a skill chip in HH / T-Bank / Yandex / Avito titles:
# «DevOps-инженер», «ML-инженер», «ML-тимлид», «Go-разработчик», «DevOps инженер».
_ROLE_SUFFIXES = (
    "инженер",
    "разработчик",
    "developer",
    "engineer",
    "тимлид",
    "техлид",
    "лид",
    "lead",
    "менеджер",
    "manager",
    "аналитик",
    "analyst",
    "специалист",
    "администратор",
    "архитектор",
    "architect",
    "тестировщик",
    "tester",
    "исследователь",
    "researcher",
    "ops",
)

_SEPARATORS = ("-", " ", "/", " - ", " — ", " – ")

# Distinctive chips / keys from the catalogs. Short latin stems stay tokens only
# so «java» does not substring-match «javascript».
_TOKENS: dict[str, tuple[str, ...]] = {
    "python": ("python", "django", "fastapi", "flask", "pytest"),
    "go": ("go", "golang"),
    "java": ("java", "spring"),
    "csharp": ("c#", "с#", "csharp", "dotnet", "asp.net", ".net"),
    "cpp": ("c++", "с++", "cpp"),
    "php": ("php", "laravel", "symfony"),
    "rust": ("rust",),
    "kotlin": ("kotlin",),
    "scala": ("scala",),
    "ruby": ("ruby", "rails"),
    "nodejs": ("node", "nodejs", "node.js", "express", "nestjs"),
    "onec": ("1c", "1с", "onec", "erp"),
    "backend": ("backend", "бэкенд", "бекенд", "back-end"),
    "frontend": (
        "frontend",
        "фронтенд",
        "фронт",
        "front-end",
        "react",
        "vue",
        "angular",
        "javascript",
        "typescript",
        "next.js",
        "nextjs",
    ),
    "fullstack": ("fullstack", "фулстек", "фуллстек", "full-stack"),
    "mobile": ("mobile", "flutter", "react-native"),
    "android": ("android",),
    "ios": ("ios", "swift", "swiftui"),
    "qa": ("qa", "autotest", "selenium", "cypress"),
    "devops": (
        "devops",
        "dev-ops",
        "kubernetes",
        "k8s",
        "terraform",
        "ansible",
        "cicd",
        "helm",
        "prometheus",
    ),
    "sre": ("sre",),
    "admin": ("sysadmin",),
    "security": ("security", "infosec", "soc", "siem", "appsec", "dfir", "forensic"),
    "embedded": ("embedded", "firmware", "rtos"),
    "ml": ("ml", "ai", "nlp", "mlops", "llm", "pytorch", "tensorflow"),
    "data": ("bigdata", "dwh", "etl", "spark", "airflow"),
    "analytics": ("аналитик", "analyst", "bi"),
    "sysanalyst": ("system-analyst",),
    "architect": ("архитектор", "architect"),
    "product": ("продакт", "product-manager", "product-owner"),
    "design": ("дизайнер", "designer", "figma"),
}

# Human labels as shown on the sites.
_LABELS: dict[str, tuple[str, ...]] = {
    "python": ("Python",),
    "go": ("Go", "Golang"),
    "java": ("Java", "Java / Scala"),
    "csharp": (".NET/C#", "C#", ".NET", "ASP.NET"),
    "cpp": ("C++", "Разработка C"),
    "php": ("PHP",),
    "rust": ("Rust",),
    "kotlin": ("Kotlin",),
    "scala": ("Scala",),
    "ruby": ("Ruby on Rails",),
    "nodejs": ("Node.js", "NodeJS"),
    "onec": ("1C", "1С", "1С-аналитика", "ERP / CRM", "ERP", "CRM"),
    "backend": (
        "Backend",
        "Back-end",
        "Разработчик бэкенда",
        "backend-developer",
    ),
    "frontend": (
        "Frontend",
        "Front-end",
        "JS / TS",
        "Разработчик интерфейсов",
        "Верстка",
        "frontend-developer",
    ),
    "fullstack": (
        "Fullstack",
        "Full-Stack",
        "Full stack",
        "Разработчик фулстек",
        "QA Fullstack",
        "full-stack-developer",
    ),
    "mobile": (
        "Mobile",
        "Мобильная разработка",
        "Разработчик мобильных приложений",
        "mob-app-developer",
    ),
    "android": ("Android",),
    "ios": ("iOS",),
    "qa": (
        "QA Auto",
        "QA Manual",
        "QA Automation",
        "QA Fullstack",
        "Тестировщик",
        "Тестирование",
        "Тестирование ручное",
        "Инженер по автоматизации тестирования",
        "Инженер по ручному тестированию",
        "quality assurance",
        "tester-auto",
        "tester-manual",
        "test-developer",
    ),
    "devops": (
        "DevOps",
        "DevOps-инженер",
        "DevOps инженер",
        "DevOps/SRE",
        "Инфраструктура/Администрирование",
        "ИТ-инфраструктура",
        "dev-ops",
    ),
    "sre": ("SRE", "site reliability", "DevOps/SRE"),
    "admin": (
        "Системный администратор",
        "Системное администрирование",
        "Системный инженер",
        "Сетевой инженер",
        "Сетевое администрирование",
        "Администрирование",
        "sys-admin",
        "database-admin",
    ),
    "security": (
        "Специалист по информационной безопасности",
        "Информационная безопасность",
        "Инженер по информационной безопасности",
        "Application security",
        "AppSec",
        "AppSec инженер",
        "SOC",
        "DFIR",
        "DFIR специалист/ SOC",
        "SIEM",
        "Инженер SIEM",
        "forensic",
        "Инженер технического расследования (ИБ, forensic)",
        "information-security",
    ),
    "embedded": ("Embedded", "system-developer", "desktop-developer"),
    "ml": (
        "ML/AI",
        "ML / DS",
        "Дата-сайентист",
        "Data Scientist",
        "Разработчик Machine Learning",
        "Исследователь Machine Learning",
        "Машинное обучение",
        "ML Ops",
        "ML-инженер",
        "ML-тимлид",
        "AI",
        "LLM",
        "Архитектор LLM",
        "Risk Data Science",
        "machine learning",
        "deep learning",
        "data science",
        "computer vision",
        "ml-developer",
        "ml-researcher",
    ),
    "data": (
        "Data Engineer",
        "Инженер данных",
        "Инженерия данных",
        "Разработчик баз данных",
        "Администратор баз данных",
        "Работа с данными",
        "BigData",
        "Аналитика данных",
        "data-engineer",
        "database-developer",
        "database-admin",
    ),
    "analytics": (
        "Аналитик",
        "BI-аналитик, аналитик данных",
        "Продуктовый аналитик",
        "Бизнес-аналитик",
        "Data Analyst",
        "BI-аналитика",
        "Продуктовая аналитика",
        "Аналитика",
        "Аналитика данных",
        "Data-аналитика",
        "analyst-developer",
    ),
    "sysanalyst": (
        "Системный аналитик",
        "Системная аналитика",
        "Системный анализ",
        "system analyst",
        "systems analyst",
        "system-analyst",
    ),
    "architect": (
        "Архитектор",
        "Архитектура",
        "Архитекторы",
        "Архитектор решений",
        "solution architect",
        "software architect",
        "solutions-architect",
    ),
    "product": (
        "Менеджер продукта",
        "Управление продуктом",
        "Product",
        "Product Manager",
        "Technical Product Manager",
        "Управление IT продуктом",
        "product owner",
        "product-manager",
    ),
    "design": (
        "Дизайнер, художник",
        "Дизайн",
        "Дизайнер UX/UI",
        "Продуктовый дизайн",
        "UX‑редактура",
        "UX-исследования",
        "UX-редактура",
        "product designer",
        "Гейм-дизайнер",
        "Технический писатель",
        "designer-uxui",
    ),
}

# Stems that company boards glue to role suffixes («Go-разработчик», «ML-тимлид»).
# Backend also generates «{язык}-разработчик» from T-Bank / HireHi language chips
# because those boards often omit the word Backend (Avito «Go-разработчик»).
_STEMS: dict[str, tuple[str, ...]] = {
    "python": ("python",),
    "go": ("go", "golang"),
    "java": ("java",),
    "csharp": ("c#", "с#", ".net", "dotnet", "csharp"),
    "cpp": ("c++", "с++", "cpp"),
    "php": ("php",),
    "rust": ("rust",),
    "kotlin": ("kotlin",),
    "scala": ("scala",),
    "ruby": ("ruby",),
    "nodejs": ("node", "node.js", "nodejs"),
    "onec": ("1c", "1с", "erp", "crm"),
    "backend": ("backend", "back-end", "бэкенд", "python", "go", "golang", "java", "php", "rust", "ruby", "scala", "c#", ".net"),
    "frontend": ("frontend", "front-end", "фронтенд", "фронт", "react", "angular"),
    "fullstack": ("fullstack", "full-stack", "фулстек"),
    "mobile": ("mobile", "ios", "android"),
    "android": ("android",),
    "ios": ("ios", "swift"),
    "qa": ("qa",),
    "devops": ("devops", "dev-ops"),
    "sre": ("sre",),
    "admin": ("sysadmin",),
    "security": ("security", "infosec", "иб", "soc", "siem", "appsec", "dfir"),
    "embedded": ("embedded",),
    "ml": ("ml", "ai", "nlp", "mlops", "llm"),
    "data": ("data", "dwh", "bigdata"),
    "analytics": ("bi",),
    "sysanalyst": (),
    "architect": ("architect",),
    "product": ("product", "продакт"),
    "design": ("ux", "ui", "ux/ui"),
}

STACK_IDS: tuple[str, ...] = (
    "python",
    "go",
    "java",
    "csharp",
    "cpp",
    "php",
    "rust",
    "kotlin",
    "scala",
    "ruby",
    "nodejs",
    "onec",
    "backend",
    "frontend",
    "fullstack",
    "mobile",
    "android",
    "ios",
    "qa",
    "devops",
    "sre",
    "admin",
    "security",
    "embedded",
    "ml",
    "data",
    "analytics",
    "sysanalyst",
    "architect",
    "product",
    "design",
)

_RU_END = re.compile(
    r"(иями|ами|ями|ностью|ности|ность|ного|ному|ого|ему|ой|ей|ии|ия|ие|ая|ый|ий|ое|ые|ов|ам|ах|ую|юю|ья|ью|ом|ем)$",
    re.I,
)


def fold_text(text: str) -> str:
    return (text or "").lower().replace("ё", "е")


def soften_ru(text: str) -> str:
    parts: list[str] = []
    for word in re.split(r"[\s/_—–-]+", fold_text(text)):
        if not word:
            continue
        if re.search(r"[а-я]", word) and len(word) >= 6:
            parts.append(_RU_END.sub("", word) or word)
        else:
            parts.append(word)
    return " ".join(parts)


def _separator_variants(text: str) -> set[str]:
    folded = fold_text(text)
    parts = [part for part in re.split(r"[\s/_—–-]+", folded) if part]
    out = {folded, " ".join(parts)}
    if len(parts) >= 2:
        for sep in (" ", "-", "/", ""):
            out.add(sep.join(parts))
    return {item.strip() for item in out if item.strip()}


def _usable_phrase(text: str) -> bool:
    phrase = fold_text(text)
    if len(phrase) < 4:
        return False
    if re.search(r"[а-я]|[-/_.#+ ]", phrase):
        return True
    return len(phrase) >= 8


# Suffix glue is only for short stems («ml», «go»). Applying it to full catalog
# labels (e.g. «машинное обучение») exploded to ~50k phrases and froze the API
# event loop when inbox/thesis ran matching_stack_ids over a few hundred cards.
_SUFFIX_SEPARATORS = ("-", " ", "/")


def _with_suffixes(stem: str) -> set[str]:
    out: set[str] = set()
    stem_f = fold_text(stem)
    if not stem_f or " " in stem_f or len(stem_f) > 16:
        return out
    for suffix in _ROLE_SUFFIXES:
        for sep in _SUFFIX_SEPARATORS:
            out.add(f"{stem_f}{sep}{suffix}")
            out.add(f"{suffix}{sep}{stem_f}")
    return out


@cache
def build_stack_spec() -> dict[str, tuple[frozenset[str], tuple[str, ...], tuple[str, ...]]]:
    spec: dict[str, tuple[frozenset[str], tuple[str, ...], tuple[str, ...]]] = {}
    for stack_id in STACK_IDS:
        tokens = {fold_text(item) for item in _TOKENS.get(stack_id, ()) if item}
        phrases: set[str] = set()
        for label in _LABELS.get(stack_id, ()):
            for variant in _separator_variants(label):
                if _usable_phrase(variant):
                    phrases.add(variant)
        for stem in _STEMS.get(stack_id, ()):
            for variant in _separator_variants(stem):
                if _usable_phrase(variant):
                    phrases.add(variant)
            for variant in _with_suffixes(stem):
                if _usable_phrase(variant):
                    phrases.add(variant)
        ordered = tuple(sorted(phrases, key=lambda item: (len(item), item)))
        soft: list[str] = []
        seen_soft: set[str] = set()
        for phrase in ordered:
            softened = soften_ru(phrase)
            if len(softened) >= 4 and softened not in seen_soft:
                seen_soft.add(softened)
                soft.append(softened)
        spec[stack_id] = (frozenset(tokens), ordered, tuple(soft))
    return spec


STACK_SPEC = build_stack_spec()

_TOKEN = re.compile(r"[cс]\+\+|c#|с#|[a-zа-я0-9]+(?:[+#.][a-zа-я0-9]+)*", re.I)

_QUERY_ALIASES: dict[str, str] = {
    "golang": "go",
    "фронт": "frontend",
    "фронтенд": "frontend",
    "бэк": "backend",
    "бэкенд": "backend",
    "бекенд": "backend",
    "фулстек": "fullstack",
    "фуллстек": "fullstack",
    "typescript": "frontend",
    "javascript": "frontend",
    "react": "frontend",
    "vue": "frontend",
    "angular": "frontend",
    "nextjs": "frontend",
    "next.js": "frontend",
    "django": "python",
    "fastapi": "python",
    "flask": "python",
    "spring": "java",
    "dotnet": "csharp",
    ".net": "csharp",
    "c#": "csharp",
    "с#": "csharp",
    "c++": "cpp",
    "с++": "cpp",
    "node": "nodejs",
    "nodejs": "nodejs",
    "node.js": "nodejs",
    "nestjs": "nodejs",
    "laravel": "php",
    "symfony": "php",
    "rails": "ruby",
    "k8s": "devops",
    "kubernetes": "devops",
    "terraform": "devops",
    "ansible": "devops",
    "pytorch": "ml",
    "tensorflow": "ml",
    "spark": "data",
    "airflow": "data",
    "etl": "data",
    "dwh": "data",
    "figma": "design",
    "ux": "design",
    "ui": "design",
    "swift": "ios",
    "flutter": "mobile",
    "selenium": "qa",
    "cypress": "qa",
}


def _blob_tokens(blob: str) -> set[str]:
    found: set[str] = set()
    for match in _TOKEN.finditer(fold_text(blob)):
        token = match.group(0).strip(".")
        if token:
            found.add(token)
    return found


def _stack_hits_cached(
    stack_id: str,
    *,
    folded: str,
    found: set[str],
    softened: str,
) -> bool:
    spec = STACK_SPEC.get(stack_id)
    if spec is None:
        return stack_id in folded
    tokens, phrases, soft_phrases = spec
    if tokens & found:
        return True
    if any(phrase in folded for phrase in phrases):
        return True
    if softened == folded or not soft_phrases:
        return False
    return any(phrase in softened for phrase in soft_phrases)


def stack_hits(stack_id: str, blob: str) -> bool:
    folded = fold_text(blob)
    return _stack_hits_cached(
        stack_id,
        folded=folded,
        found=_blob_tokens(blob),
        softened=soften_ru(folded),
    )


def matching_stack_ids(*parts: object) -> list[str]:
    blob = " ".join(str(part) for part in parts if part)
    if not blob.strip():
        return []
    folded = fold_text(blob)
    found = _blob_tokens(blob)
    softened = soften_ru(folded)
    return [
        item
        for item in STACK_IDS
        if _stack_hits_cached(item, folded=folded, found=found, softened=softened)
    ]


def stack_from_query_params(params: dict | None) -> list[str]:
    data = dict(params or {})
    raw: list[str] = []
    for key in ("stack", "subcategory"):
        value = data.get(key)
        if isinstance(value, list):
            raw.extend(str(item) for item in value if item)
        elif isinstance(value, str) and value.strip():
            raw.append(value.strip())
    specialty = str(data.get("specialty") or "").strip()
    if specialty:
        raw.append(_QUERY_ALIASES.get(fold_text(specialty), specialty))
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        key = _QUERY_ALIASES.get(fold_text(item), fold_text(item))
        if key in STACK_IDS and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def union_stack(*groups: list[str] | tuple[str, ...] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group or []:
            key = str(item).strip()
            if key in STACK_IDS and key not in seen:
                seen.add(key)
                out.append(key)
    return out


def parse_query_stacks(q: str) -> tuple[list[str], str]:
    """Split a user query into stack chips and leftover text.

    ``go`` / ``frontend`` / ``golang`` become stack filters. ``яндекс go`` keeps
    «яндекс» as text and Go as stack.

    Narrow topic terms (``nlp``, ``llm``, …) stay as synonym groups — they do
    *not* promote the parent ``ml`` chip alone.
    """
    stacks, leftover, _topics = parse_inbox_query(q)
    return stacks, leftover


# Terms narrower than a whole stack chip — must hit vacancy text.
# Every language/specialty still goes through STACK_IDS + _TOKENS/_LABELS;
# these only cover subdomains that would otherwise collapse into a parent chip.
_TOPIC_SYNONYMS: dict[str, tuple[str, ...]] = {
    "nlp": (
        "nlp",
        "natural language",
        "language processing",
        "language model",
        "large language",
        "llm",
        "vlm",
        "transformer",
        "bert",
        "gpt",
        "чат-бот",
        "чатбот",
        "nlp-инженер",
        "nlp инженер",
        "speech recognition",
        "asr",
    ),
    "llm": (
        "llm",
        "large language",
        "language model",
        "gpt",
        "nlp",
        "rag",
        "prompt",
        "agentic",
        "llm-агент",
        "ai-агент",
    ),
    "vlm": (
        "vlm",
        "vision language",
        "vision-language",
        "multimodal",
        "мультимодаль",
    ),
    "mlops": (
        "mlops",
        "ml ops",
        "ml-ops",
        "feature store",
        "model registry",
        "model serving",
    ),
    "rag": (
        "rag",
        "retrieval augmented",
        "retrieval-augmented",
        "vector store",
        "embeddings",
        "pgvector",
    ),
    "cv": (
        "computer vision",
        "компьютерного зрения",
        "компьютерное зрение",
        "opencv",
        "object detection",
        "image segmentation",
        "vision language",
    ),
    "asr": (
        "asr",
        "speech recognition",
        "speech-to-text",
        "speech to text",
        "распознаван",
        "голосовой ассистент",
    ),
    "appsec": ("appsec", "application security", "sast", "dast", "secure code"),
    "soc": ("soc", "security operations", "siem", "cyber defense"),
    "dfir": ("dfir", "forensic", "incident response", "threat hunting"),
}
_TOPIC_KEYS = frozenset(_TOPIC_SYNONYMS)

# Tokens too ambiguous for bare substring LIKE (go→google, java→javascript, ai→said).
_AMBIGUOUS_EVIDENCE = frozenset(
    {
        "go",
        "ai",
        "ml",
        "bi",
        "qa",
        "net",
        "php",
        "ios",
        "ui",
        "ux",
        "c",
        "r",
        "js",
        "ts",
        "иб",
        "java",  # bare LIKE hits javascript
        "node",  # nodejs / node
        "rust",
    }
)


@cache
def stack_evidence_terms(stack_id: str) -> tuple[str, ...]:
    """Search lexicon for one stack: tokens + distinctive labels/phrases.

    Used so inbox filters trust vacancy text, not polluted ``stack_ids`` JSON.
    """
    if stack_id not in STACK_IDS:
        return ()
    terms: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        syn = fold_text(raw).strip()
        if len(syn) < 2 or syn in seen or syn in _TOPIC_KEYS:
            return
        if syn in _AMBIGUOUS_EVIDENCE:
            return
        seen.add(syn)
        terms.append(syn)

    add(stack_id)
    for item in _TOKENS.get(stack_id, ()):
        add(item)
    for item in _LABELS.get(stack_id, ()):
        add(item)
    for item in _STEMS.get(stack_id, ()):
        add(item)
    spec = STACK_SPEC.get(stack_id)
    if spec is not None:
        _tokens, phrases, _soft = spec
        for phrase in phrases:
            # Prefer role phrases («go-разработчик») over bare ambiguous stems.
            if len(fold_text(phrase)) >= 4:
                add(phrase)
            if len(terms) >= 64:
                break
    # Always keep language/specialty self-id even if marked ambiguous via longer forms.
    if stack_id == "go":
        for item in ("golang", "go-разработчик", "go разработчик", "go-developer", "go developer"):
            add(item)
    elif stack_id == "java":
        for item in ("java-разработчик", "java разработчик", "java developer", "spring"):
            add(item)
    elif stack_id == "ml":
        for item in ("machine learning", "deep learning", "data scientist", "дата-сайентист", "ml-инженер", "ml инженер"):
            add(item)
    elif stack_id == "qa":
        for item in ("qa engineer", "qa-инженер", "тестировщик", "тестирование", "autotest"):
            add(item)
    elif stack_id == "ios":
        for item in ("swift", "swiftui", "ios-разработчик", "ios разработчик"):
            add(item)
    return tuple(terms)


def content_matches_stack(stack_id: str, *parts: object) -> bool:
    """True when vacancy text supports this stack (same engine as matching_stack_ids)."""
    return stack_id in matching_stack_ids(*parts)


def parse_inbox_query(q: str) -> tuple[list[str], str, list[tuple[str, ...]]]:
    """Return (stack_ids, leftover_text, topic_synonym_groups)."""
    tokens = [part for part in fold_text(q).replace(",", " ").split() if part]
    stacks: list[str] = []
    rest: list[str] = []
    topics: list[tuple[str, ...]] = []
    seen_stack: set[str] = set()
    seen_topic: set[str] = set()
    for token in tokens:
        if token in _TOPIC_SYNONYMS and token not in seen_topic:
            seen_topic.add(token)
            topics.append(_TOPIC_SYNONYMS[token])
            continue
        mapped = _QUERY_ALIASES.get(token, token)
        hit: str | None = mapped if mapped in STACK_IDS else None
        if hit is None:
            for stack_id in STACK_IDS:
                names = {fold_text(stack_id)}
                primary = {
                    fold_text(item)
                    for item in _TOKENS.get(stack_id, ())
                    if len(fold_text(item)) >= 2 and fold_text(item) not in _TOPIC_KEYS
                }
                for label in _LABELS.get(stack_id, ()):
                    folded_label = fold_text(label)
                    if " " not in folded_label and folded_label not in _TOPIC_KEYS:
                        names.add(folded_label)
                if token in names or token in primary:
                    hit = stack_id
                    break
        if hit and hit not in seen_stack:
            seen_stack.add(hit)
            stacks.append(hit)
        elif not hit:
            rest.append(token)
    return stacks, " ".join(rest), topics

