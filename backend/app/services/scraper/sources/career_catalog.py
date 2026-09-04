"""Company career boards Hunt can fetch without a private ATS token."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CareerBoard:
    slug: str
    name: str
    listing_url: str
    kind: str
    origin: str
    hint: str = ""
    logo_url: str = ""


# Public IT-filtered listings. Ozon stays opt-in: anti-bot blocks fetch outside RU.
BOARDS: tuple[CareerBoard, ...] = (
    CareerBoard(
        slug="aviasales",
        name="Авиасейлс",
        listing_url="https://www.aviasales.ru/about/vacancies",
        kind="aviasales",
        origin="https://www.aviasales.ru",
        hint="вся доска — IT-компания",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=aviasales.ru",
    ),
    CareerBoard(
        slug="avito",
        name="Авито",
        listing_url="https://career.avito.com/vacancies/razrabotka/",
        kind="avito",
        origin="https://career.avito.com",
        hint="разработка, data, безопасность — не продажи",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=avito.ru",
    ),
    CareerBoard(
        slug="kaspersky",
        name="Лаборатория Касперского",
        listing_url="https://careers.kaspersky.ru/vacancies",
        kind="kaspersky",
        origin="https://careers.kaspersky.ru",
        hint="разработка, DevOps, ИБ — не финансы",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=kaspersky.ru",
    ),
    CareerBoard(
        slug="tbank",
        name="Т-Банк",
        listing_url="https://www.tbank.ru/career/vacancies/it/",
        kind="tbank",
        origin="https://www.tbank.ru",
        hint="IT-лента по всей России, не бэк-офис",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=tbank.ru",
    ),
    CareerBoard(
        slug="vk",
        name="VK",
        listing_url="https://team.vk.company/vacancy/",
        kind="vk",
        origin="https://team.vk.company",
        hint="IT-специальности, не вся HR-лента",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=vk.com",
    ),
    CareerBoard(
        slug="yandex",
        name="Яндекс",
        listing_url="https://yandex.ru/jobs/",
        kind="yandex",
        origin="https://yandex.ru",
        hint="IT-профессии Яндекса",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=yandex.ru",
    ),
    CareerBoard(
        slug="yadro",
        name="YADRO",
        listing_url="https://careers.yadro.com/vacancies?direction=14",
        kind="yadro",
        origin="https://careers.yadro.com",
        hint="IT и разработка продуктов, не производство",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=yadro.com",
    ),
    CareerBoard(
        slug="megafon",
        name="МегаФон",
        listing_url="https://job.megafon.ru/",
        kind="megafon",
        origin="https://job.megafon.ru",
        hint="Backend, DevOps, ИБ, данные — не розница",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=megafon.ru",
    ),
    CareerBoard(
        slug="solar",
        name="Солар",
        listing_url="https://team.rt-solar.ru/vacancies/",
        kind="solar",
        origin="https://team.rt-solar.ru",
        hint="ИБ-компания, вся доска",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=rt-solar.ru",
    ),
    CareerBoard(
        slug="selectel",
        name="Selectel",
        listing_url="https://selectel.ru/careers/all/",
        kind="selectel",
        origin="https://selectel.ru",
        hint="облако и инфраструктура, вся доска",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=selectel.ru",
    ),
    CareerBoard(
        slug="x5",
        name="X5 Tech",
        listing_url="https://x5.tech/vacancy",
        kind="x5",
        origin="https://x5.tech",
        hint="цифровые роли X5, не магазины",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=x5.tech",
    ),
    CareerBoard(
        slug="itone",
        name="IT_ONE",
        listing_url="https://www.it-one.ru/vacancies/",
        kind="itone",
        origin="https://www.it-one.ru",
        hint="аутстафф IT, JSON-лента",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=it-one.ru",
    ),
    CareerBoard(
        slug="cloudru",
        name="Cloud.ru",
        listing_url="https://cloud.ru/career/vacancies",
        kind="cloudru",
        origin="https://cloud.ru",
        hint="облако, открытая лента",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=cloud.ru",
    ),
    CareerBoard(
        slug="croc",
        name="КРОК",
        listing_url="https://careers.croc.ru/vacancies/",
        kind="croc",
        origin="https://careers.croc.ru",
        hint="IT-направления: инфраструктура, ИБ, приложения, аналитика",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=croc.ru",
    ),
    CareerBoard(
        slug="jet",
        name="Инфосистемы Джет",
        listing_url="https://jet.su/career/vacancies/",
        kind="jet",
        origin="https://jet.su",
        hint="системный интегратор, вся IT-лента",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=jet.su",
    ),
    CareerBoard(
        slug="mts",
        name="МТС",
        listing_url="https://job.mts.ru/s/vacancy",
        kind="mts",
        origin="https://job.mts.ru",
        hint="только «Работа в IT» и «Технический блок», не вся HR-лента",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=mts.ru",
    ),
    CareerBoard(
        slug="ibs",
        name="IBS",
        listing_url="https://ibs.ru/career/jobs/",
        kind="ibs",
        origin="https://ibs.ru",
        hint="разработка, тестирование, инженеры, архитектура, аналитика",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=ibs.ru",
    ),
    CareerBoard(
        slug="2gis",
        name="2ГИС",
        listing_url="https://job.2gis.ru/vacancies?direction=development",
        kind="2gis",
        origin="https://job.2gis.ru",
        hint="разработка, тестирование, DevOps, ИБ, аналитика, data — не продажи",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=2gis.ru",
    ),
    CareerBoard(
        slug="alfa",
        name="Альфа-Банк",
        listing_url="https://job.alfabank.ru/vacancies",
        kind="alfa",
        origin="https://job.alfabank.ru",
        hint="IT и Alfa Digital — разработка, QA, data, инфраструктура",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=alfabank.ru",
    ),
    CareerBoard(
        slug="kontur",
        name="Контур",
        listing_url="https://kontur.ru/career/vacancies",
        kind="kontur",
        origin="https://kontur.ru",
        hint="разработка, ML, data, QA — не маркетинг и продажи",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=kontur.ru",
    ),
    CareerBoard(
        slug="wb",
        name="Wildberries",
        listing_url="https://career.wb.ru/",
        kind="wb",
        origin="https://career.wb.ru",
        hint="WBTech: разработка, тестирование, data, DevOps, ИБ",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=wildberries.ru",
    ),
    CareerBoard(
        slug="ozon",
        name="Ozon Tech",
        listing_url="https://job.ozon.ru/",
        kind="ozon",
        origin="https://job.ozon.ru",
        hint="IT-вакансии Ozon — нужен доступ без anti-bot",
        logo_url="https://www.google.com/s2/favicons?sz=128&domain=ozon.ru",
    ),
)

_BY_SLUG = {board.slug: board for board in BOARDS}

VK_IT_SPECIALTIES = frozenset(
    {
        282,  # Backend
        287,  # Frontend
        286,  # Mobile
        284,  # QA
        278,  # DevOps
        283,  # Machine Learning
        359,  # Инженерия данных
        203,  # Архитекторы
        270,  # Информационная безопасность
        306,  # Системная аналитика
        305,  # Системное администрирование
        280,  # Сетевое администрирование
        268,  # BI аналитика
        269,  # Data-аналитика
        316,  # Бизнес-аналитика
        295,  # Продуктовая аналитика
        292,  # Управление IT продуктом
    }
)

# Titles above feed stack_lexicon matching for every board.
# Yandex profession slugs are only a fetch adapter (see career_filters.YANDEX_STACK_PROFESSIONS).

# IT professions from https://yandex.ru/jobs/api/professions/ — development,
# testing, security, analytics, design, product. No HR / cashiers / devices.
YANDEX_IT_PROFESSIONS = (
    "backend-developer",
    "frontend-developer",
    "full-stack-developer",
    "ml-developer",
    "ml-researcher",
    "mob-app-developer",
    "mob-app-developer-android",
    "mob-app-developer-ios",
    "database-developer",
    "data-engineer",
    "system-developer",
    "desktop-developer",
    "dev-ops",
    "tester-auto",
    "tester-manual",
    "test-developer",
    "sys-admin",
    "database-admin",
    "information-security",
    "analyst",
    "analyst-developer",
    "system-analyst",
    "designer-uxui",
    "product-manager",
    "solutions-architect",
)

AVITO_IT_SLUGS = frozenset(
    {
        "razrabotka",
        "data-science",
        "analitika-dannykh",
        "informatsionnaya-bezopasnost",
        "dizayn",
        "upravlenie-produktom",
        "ux-issledovaniya",
        "ux-redaktsiya",
    }
)

KASPERSKY_IT_CATEGORIES = frozenset(
    {
        32627,  # Информационная безопасность
        32630,  # Системное администрирование
        32632,  # Технический писатель
        32646,  # Разработка C
        32649,  # Разработка Other
        32650,  # Тестирование ручное
        679402,  # DevOps
    }
)

TBANK_IT_CATEGORIES = frozenset({"tcareer_it", "it"})

# YADRO direction «IT и разработка продуктов» from /api/vacancies.
YADRO_IT_DIRECTION = 14

# Megafon specialty ids that are software / infra / security / data, not retail.
MEGAFON_IT_SPECIALTIES = (
    22,  # Backend
    23,  # BigData
    24,  # DevOps/SRE
    27,  # Архитектура
    28,  # Информационная безопасность
    29,  # ИТ-инфраструктура
    30,  # Мобильная разработка
    31,  # Развитие и поддержка IT-решений
    33,  # Системный анализ
    34,  # Тестирование
    56,  # Развитие и поддержка бизнес-систем
)

# careers.croc.ru section ids — IT-related directions only.
CROC_IT_SECTIONS = frozenset(
    {
        8,  # Программная и вычислительная инфраструктура
        11,  # Кибербезопасность
        13,  # Бизнес-приложения
        14,  # Телекоммуникации
        15,  # Аналитика
        17,  # Сервис и техподдержка
        19,  # Управление проектами
    }
)

# job.mts.ru top-level category slugs on vacancy cards (API filters ignore these).
MTS_IT_CATEGORIES = frozenset({"работа-в-it", "технический-блок"})

# IBS direction filters — IT-related only.
IBS_IT_FILTERS = (
    "napravlenie-is-razrabotka",
    "napravlenie-is-testirovanie",
    "napravlenie-is-inzhenery",
    "napravlenie-is-arkhitektura",
    "napravlenie-is-analitika-i-konsalting",
)

# job.2gis.ru direction ids — IT-related only.
TGIS_IT_DIRECTIONS = (
    22,  # Разработка
    23,  # Тестирование
    27,  # Инфраструктура и администрирование
    28,  # Data Science/AI
    36,  # Информационная безопасность
    37,  # Аналитика
)

# career.rwb.ru direction ids — IT-related only.
WB_IT_DIRECTIONS = (
    2,  # Аналитика
    3,  # Разработка
    4,  # Тестирование
    5,  # Базы данных
    6,  # Инфраструктура
    7,  # Data science
    8,  # Информационная безопасность
    9,  # Управление продуктом
    11,  # Дизайн
    12,  # UX
)


def get_board(slug: str | None) -> CareerBoard | None:
    key = (slug or "").strip().lower()
    return _BY_SLUG.get(key)


def board_public(board: CareerBoard) -> dict:
    return {
        "slug": board.slug,
        "name": board.name,
        "listing_url": board.listing_url,
        "hint": board.hint,
        "logo_url": board.logo_url,
    }
