from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.services.scraper.sources.career import CareerSource
from app.services.scraper.sources.career_filters import auto_name as career_auto_name
from app.services.scraper.sources.career_filters import listing_url_from_params as career_listing_url
from app.services.scraper.sources.career_filters import normalize_career_params
from app.services.scraper.sources.geekjob import GeekJobSource
from app.services.scraper.sources.geekjob_filters import auto_name as geekjob_auto_name
from app.services.scraper.sources.geekjob_filters import listing_url_from_params as geekjob_listing_url
from app.services.scraper.sources.geekjob_filters import normalize_geekjob_params
from app.services.scraper.sources.getmatch import GetMatchSource
from app.services.scraper.sources.getmatch_filters import auto_name as getmatch_auto_name
from app.services.scraper.sources.getmatch_filters import listing_url_from_params as getmatch_listing_url
from app.services.scraper.sources.getmatch_filters import normalize_getmatch_params
from app.services.scraper.sources.habr import HabrSource
from app.services.scraper.sources.habr_filters import auto_name as habr_auto_name
from app.services.scraper.sources.habr_filters import listing_url_from_params as habr_listing_url
from app.services.scraper.sources.habr_filters import normalize_habr_params
from app.services.scraper.sources.hh import HhSource
from app.services.scraper.sources.hh_filters import auto_name as hh_auto_name
from app.services.scraper.sources.hh_filters import listing_url_from_params as hh_listing_url
from app.services.scraper.sources.hh_filters import normalize_hh_params
from app.services.scraper.sources.hirehi import HireHiSource, listing_url_from_params as hirehi_listing_url
from app.services.scraper.sources.hirehi_filters import auto_name as hirehi_auto_name
from app.services.scraper.sources.hirehi_filters import normalize_hirehi_params


@dataclass(frozen=True)
class SourceSpec:
    id: str
    label: str
    adapter: type
    normalize_params: Callable[[dict | None], dict]
    auto_name: Callable[[dict], str]
    listing_url: Callable[[dict], str]
    default_interval_minutes: int = 60
    default_max_pages: int = 5
    page_limit: int = 20
    identity_drop: tuple[str, ...] = ()
    fetch_defaults: dict = field(default_factory=dict)


SPECS: dict[str, SourceSpec] = {
    "hirehi": SourceSpec(
        id="hirehi",
        label="HireHi",
        adapter=HireHiSource,
        normalize_params=normalize_hirehi_params,
        auto_name=hirehi_auto_name,
        listing_url=hirehi_listing_url,
        default_interval_minutes=60,
        default_max_pages=5,
        page_limit=20,
        identity_drop=("sort",),
        fetch_defaults={"sort": "date"},
    ),
    "hh": SourceSpec(
        id="hh",
        label="hh.ru",
        adapter=HhSource,
        normalize_params=normalize_hh_params,
        auto_name=hh_auto_name,
        listing_url=hh_listing_url,
        default_interval_minutes=180,
        default_max_pages=40,
        page_limit=50,
        identity_drop=("headed", "order_by"),
        fetch_defaults={"order_by": "publication_time"},
    ),
    "habr": SourceSpec(
        id="habr",
        label="Habr Career",
        adapter=HabrSource,
        normalize_params=normalize_habr_params,
        auto_name=habr_auto_name,
        listing_url=habr_listing_url,
        default_interval_minutes=60,
        default_max_pages=40,
        page_limit=25,
    ),
    "getmatch": SourceSpec(
        id="getmatch",
        label="GetMatch",
        adapter=GetMatchSource,
        normalize_params=normalize_getmatch_params,
        auto_name=getmatch_auto_name,
        listing_url=getmatch_listing_url,
        default_interval_minutes=180,
        default_max_pages=20,
        page_limit=20,
    ),
    "geekjob": SourceSpec(
        id="geekjob",
        label="GeekJob",
        adapter=GeekJobSource,
        normalize_params=normalize_geekjob_params,
        auto_name=geekjob_auto_name,
        listing_url=geekjob_listing_url,
        default_interval_minutes=60,
        default_max_pages=40,
        page_limit=50,
        identity_drop=("stack", "formats", "levels", "cities", "only_salary", "salary_from"),
    ),
    "career": SourceSpec(
        id="career",
        label="Компании",
        adapter=CareerSource,
        normalize_params=normalize_career_params,
        auto_name=career_auto_name,
        listing_url=career_listing_url,
        default_interval_minutes=60,
        default_max_pages=5,
        page_limit=20,
        identity_drop=("stack", "search", "levels", "formats", "cities", "only_salary", "salary_from"),
    ),
}

ADAPTERS: dict[str, type] = {spec.id: spec.adapter for spec in SPECS.values()}


def get_spec(source: str) -> SourceSpec | None:
    return SPECS.get(source)


def known_source(source: str) -> bool:
    return source in SPECS
