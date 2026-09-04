from __future__ import annotations

from app.services.scraper.sources.career_filters import career_job_matches, normalize_career_params, yandex_professions
from app.services.scraper.sources.geo import CITY_IDS, location_hits_cities, tbank_city_slug
from app.services.scraper.sources.hh_filters import AREAS, normalize_hh_params
from app.services.scraper.sources.geekjob_filters import normalize_geekjob_params


def test_shared_cities_cover_it_hubs_not_only_msk_spb() -> None:
    assert {"1", "2", "113", "3", "4", "88", "66", "53", "76", "2734", "90"} <= CITY_IDS
    ids = {row[0] for row in AREAS}
    assert ids == CITY_IDS
    assert ("88", "Казань") in AREAS


def test_location_hits_any_board_geo_string() -> None:
    assert location_hits_cities("Казань", ["88"])
    assert location_hits_cities("г. Нижний Новгород, гибрид", ["66"])
    assert location_hits_cities("Новосибирск", ["4"])
    assert location_hits_cities("Innopolis", ["2734"])
    assert not location_hits_cities("Москва", ["88"])
    assert not location_hits_cities("Томск", ["68"])
    assert location_hits_cities("Омск", ["68"])
    assert location_hits_cities("Россия, Москва, Санкт-Петербург", ["1"])
    assert not location_hits_cities("Россия, Москва, Санкт-Петербург", ["88"])


def test_tbank_slug_comes_from_shared_geo() -> None:
    assert tbank_city_slug("Казань") == "kazan"
    assert tbank_city_slug("г. Москва") == "moscow"
    assert tbank_city_slug("Санкт-Петербург") == "saint-petersburg"
    assert tbank_city_slug("Нижний Новгород") == "nizhny-novgorod"
    assert tbank_city_slug("Ростов-на-Дону") == "rostov-on-don"
    assert tbank_city_slug("Челябинск") is None


def test_career_city_filter_is_company_agnostic() -> None:
    kazan = {"title": "Go-разработчик", "location": "Казань"}
    moscow = {"title": "Go-разработчик", "location": "Москва"}
    nn = {"title": "AppSec инженер", "location": "Нижний Новгород"}
    assert career_job_matches(kazan, {"company": "yadro", "cities": ["88"]})
    assert career_job_matches(kazan, {"company": "megafon", "cities": ["88"]})
    assert career_job_matches(kazan, {"company": "vk", "cities": ["88"]})
    assert not career_job_matches(moscow, {"company": "solar", "cities": ["88"]})
    assert career_job_matches(nn, {"company": "yadro", "cities": ["66"]})
    assert normalize_career_params({"company": "vk", "cities": ["88", "nope"]})["cities"] == ["88"]
    assert normalize_geekjob_params({"cities": ["88", "4"]})["cities"] == ["4", "88"]
    assert normalize_hh_params({"area": ["88", "4"]})["area"] == ["88", "4"]


def test_titles_from_every_board_hit_shared_stack() -> None:
    def hit(title: str, stack: str, **extra: object) -> bool:
        return career_job_matches({"title": title, **extra}, {"company": "megafon", "stack": [stack]})

    assert hit("DFIR специалист/ SOC", "security")
    assert hit("AppSec инженер", "security")
    assert hit("Инженер SIEM", "security")
    assert hit("Инженер технического расследования (ИБ, forensic)", "security")
    assert hit("Архитектор LLM", "ml")
    assert hit("Архитектор LLM", "architect")
    assert hit("Scala-разработчик", "scala", skills=["Backend", "BigData"])
    assert hit("Scala-разработчик", "data", skills=["Backend", "BigData"])
    assert hit("Системный анализ", "sysanalyst")
    assert yandex_professions({"company": "yandex", "stack": ["python"]}) == ("backend-developer",)
    assert "information-security" in yandex_professions({"company": "yandex", "stack": ["security"]})
