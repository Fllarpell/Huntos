"""Public internship and student-school programs in Russian IT.

Seeded from Postypashki tracker (https://old.postypashki.ru/стажировки-2/)
plus official career pages where Postypashki linked to YouTube/Telegram.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InternshipProgram:
    slug: str
    name: str
    company: str
    url: str
    kind: str  # internship | school
    catalog_status: str  # open | waiting | closed | monitor
    hint: str = ""


# catalog_status: open | waiting | closed | monitor
PROGRAMS: tuple[InternshipProgram, ...] = (
    # --- internships (Postypashki + extras) ---
    InternshipProgram(
        "yandex-intern",
        "Яндекс",
        "Яндекс",
        "https://yandex.ru/yaintern/",
        "internship",
        "open",
        "релокейт для иногородних",
    ),
    InternshipProgram(
        "tbank-intern",
        "Т-Банк",
        "Т-Банк",
        "https://www.tbank.ru/career/intern/",
        "internship",
        "waiting",
        "набор сезонный, следите за анонсами",
    ),
    InternshipProgram(
        "ozon-camp",
        "Ozon Camp",
        "Ozon",
        "https://camp.ozon.ru/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "ozon-route",
        "Ozon Route 256",
        "Ozon",
        "https://route256.ozon.ru/",
        "internship",
        "waiting",
        "школа + fast-track на стажировку",
    ),
    InternshipProgram(
        "sber-seasons",
        "SberSeasons",
        "Сбер",
        "https://sberseasons.ru/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "safeboard",
        "SafeBoard",
        "ИБ-компании",
        "https://safeboard.ru/",
        "internship",
        "open",
        "программа для студентов в информационной безопасности",
    ),
    InternshipProgram(
        "vk-intern",
        "VK",
        "VK",
        "https://intern.vk.company/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "kontur-intern",
        "Контур",
        "СКБ Контур",
        "https://kontur.ru/education/programs/intern",
        "internship",
        "open",
    ),
    InternshipProgram(
        "avito-start",
        "Авито Tech Start",
        "Авито",
        "https://start.avito.ru/tech",
        "internship",
        "closed",
        "набор закрыт — мониторьте следующий сезон",
    ),
    InternshipProgram(
        "raiffeisen-start",
        "Raiffeisen Start",
        "Райффайзенбанк",
        "https://career.raiffeisen.ru/start",
        "internship",
        "open",
    ),
    InternshipProgram(
        "alfa-students",
        "Я выбираю Альфа",
        "Альфа-Банк",
        "https://alfabank.ru/alfastudents/ichoosealfa/",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "aton-ittp",
        "АТОН ITTP",
        "АТОН",
        "https://career.aton.ru/start/ittp/",
        "internship",
        "closed",
    ),
    InternshipProgram(
        "lce-trainee",
        "Стажировки ЛЦЭ",
        "Лига цифровой экономики",
        "https://www.digitalleague.ru/traineeships/directions",
        "internship",
        "open",
    ),
    InternshipProgram(
        "gpb-levelup",
        "Level Up",
        "Газпромбанк",
        "https://gpb.fut.ru/levelup/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "aston-intern",
        "Aston",
        "Aston",
        "https://astondevs.ru/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "mts-intern",
        "МТС",
        "МТС",
        "https://job.mts.ru/s/internship",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "croc-intern",
        "КРОК",
        "КРОК",
        "https://internship.croc.ru/",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "aviasales-intern",
        "Aviasales",
        "Aviasales",
        "https://www.aviasales.ru/about/vacancies",
        "internship",
        "monitor",
        "стажировки рядом с вакансиями",
    ),
    InternshipProgram(
        "mars-intern",
        "Mars",
        "Mars",
        "https://mars-internship.vcv.jobs/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "vtb-intern",
        "ВТБ",
        "ВТБ",
        "https://vtbcareer.com/internship/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "samokat-intern",
        "Самокат Tech",
        "Самокат",
        "https://samokat.tech/internships",
        "internship",
        "open",
    ),
    InternshipProgram(
        "x5-techcrew",
        "X5 Tech Crew",
        "X5 Tech",
        "https://techcrew.start.x5.ru/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "t2-intern",
        "T2",
        "T2",
        "https://intern.t2.ru/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "beeline-beeginner",
        "beeginner",
        "билайн",
        "https://www.job-beeline.ru/beeginner",
        "internship",
        "open",
    ),
    InternshipProgram(
        "rostelecom-first",
        "First",
        "Ростелеком",
        "https://first.rt.ru/",
        "internship",
        "open",
    ),
    InternshipProgram(
        "megafon-intern",
        "МегаФон",
        "МегаФон",
        "https://job.megafon.ru/",
        "internship",
        "open",
        "фильтр «стажировка» на доске",
    ),
    InternshipProgram(
        "sovcom-trainee",
        "Совкомбанк",
        "Совкомбанк",
        "https://people.sovcombank.ru/students/traineeship",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "uralsib-students",
        "Уралсиб",
        "Уралсиб",
        "https://students.uralsib.ru/",
        "internship",
        "open",
    ),
    # --- extras beyond Postypashki ---
    InternshipProgram(
        "hh-internship",
        "HH Стажировки",
        "HeadHunter",
        "https://internship.hh.ru/",
        "internship",
        "open",
        "агрегатор программ по всей стране",
    ),
    InternshipProgram(
        "kaspersky-intern",
        "Лаборатория Касперского",
        "Kaspersky",
        "https://careers.kaspersky.ru/vacancies",
        "internship",
        "monitor",
        "ищите «стажёр» на карьерной доске",
    ),
    InternshipProgram(
        "yadro-intern",
        "YADRO",
        "YADRO",
        "https://careers.yadro.com/vacancies?direction=14",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "selectel-intern",
        "Selectel",
        "Selectel",
        "https://selectel.ru/careers/all/",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "wb-tech-intern",
        "WBTech",
        "Wildberries",
        "https://tech.wildberries.ru/",
        "internship",
        "monitor",
        "стажировки и Tech School",
    ),
    InternshipProgram(
        "positive-intern",
        "Positive Technologies",
        "Positive Technologies",
        "https://job.ptsecurity.com/",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "jet-intern",
        "Инфосистемы Джет",
        "Jet",
        "https://jet.su/career/vacancies/",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "2gis-intern",
        "2ГИС",
        "2ГИС",
        "https://job.2gis.ru/",
        "internship",
        "monitor",
    ),
    InternshipProgram(
        "t1-intern",
        "Т1 / Иннотех",
        "Т1",
        "https://career.t1.ru/",
        "internship",
        "monitor",
    ),
    # --- schools (Postypashki) ---
    InternshipProgram(
        "yandex-summer-schools",
        "Летние школы Яндекса",
        "Яндекс",
        "https://yandex.ru/yaintern/schools/summer",
        "school",
        "open",
        "льготы на отбор в стажировку",
    ),
    InternshipProgram(
        "tbank-academy",
        "Т-Банк Академия",
        "Т-Банк",
        "https://education.tbank.ru/academy/",
        "school",
        "open",
    ),
    InternshipProgram(
        "tbank-fintech",
        "Т-Банк Финтех",
        "Т-Банк",
        "https://education.tbank.ru/study/fintech/",
        "school",
        "open",
    ),
    InternshipProgram(
        "vk-education",
        "VK Education",
        "VK",
        "https://education.vk.company/students",
        "school",
        "open",
    ),
    InternshipProgram(
        "school21",
        "Школа 21",
        "Сбер",
        "https://21-school.ru/",
        "school",
        "open",
    ),
    InternshipProgram(
        "ozon-route-school",
        "Ozon Route 256 (курсы)",
        "Ozon",
        "https://route256.ozon.ru/",
        "school",
        "open",
    ),
    InternshipProgram(
        "wb-techschool",
        "Wildberries Tech School",
        "Wildberries",
        "https://tech.wildberries.ru/techschool",
        "school",
        "open",
    ),
    InternshipProgram(
        "alfa-campus",
        "Alfa Campus",
        "Альфа-Банк",
        "https://alfa-campus.ru/",
        "school",
        "open",
    ),
    InternshipProgram(
        "kontur-school",
        "СКБ Контур (образование)",
        "СКБ Контур",
        "https://kontur.ru/education/programs",
        "school",
        "open",
    ),
    InternshipProgram(
        "mts-fintech-academy",
        "МТС Финтех",
        "МТС",
        "https://rabota.mtsbank.ru/fintechacademy",
        "school",
        "open",
    ),
    InternshipProgram(
        "magnit-academy",
        "Академия Магнита",
        "Магнит",
        "https://magnit.academy/",
        "school",
        "open",
    ),
    InternshipProgram(
        "hh-school",
        "HH Школа",
        "HeadHunter",
        "https://school.hh.ru/",
        "school",
        "open",
    ),
)

_BY_SLUG = {row.slug: row for row in PROGRAMS}


def program_by_slug(slug: str) -> InternshipProgram | None:
    return _BY_SLUG.get(slug)


def programs(kind: str | None = None) -> list[InternshipProgram]:
    if kind is None:
        return list(PROGRAMS)
    return [row for row in PROGRAMS if row.kind == kind]
