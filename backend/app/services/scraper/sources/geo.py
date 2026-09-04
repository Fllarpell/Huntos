"""Shared Hunt cities. HH area ids are the canonical keys.

The same chips go to HH search, company boards, and GeekJob. Matching looks at
whatever the board put in ``location`` (VK town, YADRO cities, Megafon city,
T-Bank subtitle, Solar / Kaspersky / Avito geo) — not a T-Bank-only slug map.

Area ids: https://api.hh.ru/areas
T-Bank URL slugs: only cities that board itself uses in vacancy URLs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.scraper.sources.stack_lexicon import fold_text


@dataclass(frozen=True)
class City:
    hh_id: str
    label: str
    words: tuple[str, ...]
    tbank: str | None = None


# Москва / СПб / Россия first (default picker), then the rest A→Я.
CITIES: tuple[City, ...] = (
    City("1", "Москва", ("москв", "moscow", "msk"), "moscow"),
    City(
        "2",
        "Санкт-Петербург",
        (
            "санкт-петербург",
            "санкт петербург",
            "петербург",
            "питер",
            "saint petersburg",
            "st petersburg",
            "st. petersburg",
            "spb",
        ),
        "saint-petersburg",
    ),
    City("113", "Россия", ()),
    City("14", "Архангельск", ("архангельск", "arkhangelsk")),
    City("15", "Астрахань", ("астрахань", "астрахани", "astrakhan")),
    City("11", "Барнаул", ("барнаул", "barnaul")),
    City("17", "Белгород", ("белгород", "belgorod")),
    City("67", "Великий Новгород", ("великий новгород", "veliky novgorod")),
    City("22", "Владивосток", ("владивосток", "vladivostok")),
    City("23", "Владимир", ("владимир", "vladimir")),
    City("24", "Волгоград", ("волгоград", "volgograd")),
    City("26", "Воронеж", ("воронеж", "voronezh"), "voronezh"),
    City("3", "Екатеринбург", ("екатеринбург", "екб", "ekaterinburg", "yekaterinburg"), "ekaterinburg"),
    City("2088", "Зеленоград", ("зеленоград", "zelenograd")),
    City("96", "Ижевск", ("ижевск", "izhevsk")),
    City("2734", "Иннополис", ("иннополис", "innopolis"), "innopolis"),
    City("35", "Иркутск", ("иркутск", "irkutsk")),
    City("88", "Казань", ("казань", "казани", "казан", "kazan"), "kazan"),
    City("41", "Калининград", ("калининград", "kaliningrad")),
    City("43", "Калуга", ("калуга", "калуге", "калуги", "kaluga")),
    City("47", "Кемерово", ("кемерово", "kemerovo")),
    City("53", "Краснодар", ("краснодар", "krasnodar"), "krasnodar"),
    City("54", "Красноярск", ("красноярск", "krasnoyarsk")),
    City("56", "Курск", ("курск", "kursk")),
    City("58", "Липецк", ("липецк", "lipetsk")),
    City("1399", "Магнитогорск", ("магнитогорск", "magnitogorsk")),
    City("1002", "Минск", ("минск", "minsk")),
    City("64", "Мурманск", ("мурманск", "murmansk")),
    City("1641", "Набережные Челны", ("набережные челны", "челны", "naberezhnye chelny")),
    City(
        "66",
        "Нижний Новгород",
        ("нижний новгород", "нижнем новгород", "nizhny novgorod", "nizhniy novgorod"),
        "nizhny-novgorod",
    ),
    City("1240", "Новокузнецк", ("новокузнецк", "novokuznetsk")),
    City("4", "Новосибирск", ("новосибирск", "новосиб", "nsk", "novosibirsk"), "novosibirsk"),
    City("68", "Омск", ("омск", "omsk")),
    City("70", "Оренбург", ("оренбург", "orenburg")),
    City("71", "Пенза", ("пенза", "пензе", "пензы", "penza")),
    City("72", "Пермь", ("перм", "perm"), "perm"),
    City("76", "Ростов-на-Дону", ("ростов-на-дону", "ростов на дону", "rostov-on-don", "rostov"), "rostov-on-don"),
    City("77", "Рязань", ("рязань", "рязани", "ryazan")),
    City("78", "Самара", ("самара", "самаре", "самары", "samara"), "samara"),
    City("79", "Саратов", ("саратов", "saratov")),
    City("83", "Смоленск", ("смоленск", "smolensk")),
    City("237", "Сочи", ("сочи", "sochi")),
    City("1381", "Сургут", ("сургут", "surgut")),
    City("89", "Тверь", ("тверь", "твери", "tver")),
    City("90", "Томск", ("томск", "tomsk"), "tomsk"),
    City("92", "Тула", ("тула", "туле", "тулы", "tula")),
    City("95", "Тюмень", ("тюмень", "тюмени", "tyumen")),
    City("98", "Ульяновск", ("ульяновск", "ulyanovsk")),
    City("99", "Уфа", ("уфа", "уфе", "уфы", "ufa")),
    City("102", "Хабаровск", ("хабаровск", "khabarovsk")),
    City("107", "Чебоксары", ("чебоксары", "чебоксар", "cheboksary")),
    City("104", "Челябинск", ("челябинск", "chelyabinsk")),
    City("112", "Ярославль", ("ярославл", "yaroslavl")),
)

CITY_IDS: frozenset[str] = frozenset(city.hh_id for city in CITIES)
CITY_BY_ID: dict[str, City] = {city.hh_id: city for city in CITIES}
CITY_CHOICES: tuple[tuple[str, str], ...] = tuple((city.hh_id, city.label) for city in CITIES)

_BOUNDARY = re.compile(r"[a-zа-я0-9]", re.I)


def _contains_stem(haystack: str, needle: str) -> bool:
    folded = fold_text(needle)
    if not folded:
        return False
    if " " in folded or "-" in folded:
        return folded in haystack
    start = 0
    while True:
        at = haystack.find(folded, start)
        if at < 0:
            return False
        if at == 0 or not _BOUNDARY.match(haystack[at - 1]):
            return True
        start = at + 1


def location_hits_cities(location: str, city_ids: list[str] | tuple[str, ...]) -> bool:
    if not city_ids or "113" in city_ids:
        return True
    folded = fold_text(location)
    if not folded.strip():
        return True
    for city_id in city_ids:
        city = CITY_BY_ID.get(city_id)
        if city is None:
            continue
        if any(_contains_stem(folded, word) for word in city.words):
            return True
    return False


def tbank_city_slug(subtitle: object) -> str | None:
    folded = fold_text(str(subtitle or "").strip())
    if not folded:
        return None
    ranked: list[tuple[int, str, str]] = []
    for city in CITIES:
        if not city.tbank:
            continue
        for word in city.words:
            ranked.append((len(fold_text(word)), fold_text(word), city.tbank))
    ranked.sort(reverse=True)
    for _length, word, slug in ranked:
        if _contains_stem(folded, word):
            return slug
    return None
