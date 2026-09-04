from __future__ import annotations

import json
from pathlib import Path

from app.services.getmatch_salaries import parse_getmatch_salaries
from app.services.habr_salaries import parse_habr_salaries_html, parse_habr_salary_rows
from app.services.hh_salaries import parse_hh_profession_html
from app.services.salary_aggregators import filter_aggregators
from app.services.salary_stats import corridor_from_vacancies
from app.services.scraper.jsonld import extract_job_posting
from app.services.scraper.salary import parse_salary
from types import SimpleNamespace

FIXTURES = Path(__file__).parent / "fixtures"


def test_habr_salaries_html_grades() -> None:
    html = (FIXTURES / "habr_salaries.html").read_text(encoding="utf-8")
    rows = parse_habr_salaries_html(html)
    assert [row["grade"] for row in rows] == [None, "intern", "junior", "middle", "senior", "lead"]
    overall = rows[0]
    assert overall["median"] == 190833
    assert overall["p25"] == 108333
    assert overall["p75"] == 305833
    assert overall["n"] == 40943
    assert overall["source"] == "habr_career"
    junior = next(row for row in rows if row["grade"] == "junior")
    assert junior["median"] == 93333


def test_habr_salaries_nuxt_pointers() -> None:
    payload = [
        None,
        {
            "name": 2,
            "min": 3,
            "p25": 4,
            "median": 5,
            "p75": 6,
            "max": 7,
            "total": 8,
            "title": 9,
        },
        "Intern",
        30833,
        47666,
        68666,
        97000,
        143333,
        1772,
        "По Intern IT-специалистам",
    ]
    rows = parse_habr_salary_rows(payload)
    assert len(rows) == 1
    assert rows[0]["grade"] == "intern"
    assert rows[0]["p25"] == 47666
    assert rows[0]["median"] == 68666
    assert rows[0]["n"] == 1772


def test_getmatch_salaries_thousands() -> None:
    payload = json.loads((FIXTURES / "getmatch_salaries.json").read_text(encoding="utf-8"))
    row = parse_getmatch_salaries(payload)
    assert row is not None
    assert row["p25"] == 160_000
    assert row["median"] == 230_000
    assert row["p90"] == 400_000
    assert row["p75"] is None
    assert row["n"] == 68299
    assert row["source"] == "getmatch_salaries"


def test_jsonld_uses_currency_not_unit_text() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "JobPosting",
      "title": "Backend",
      "baseSalary": {
        "@type": "MonetaryAmount",
        "currency": "USD",
        "value": {"@type": "QuantitativeValue", "minValue": 4000, "maxValue": 4500, "unitText": "MONTH"}
      }
    }
    </script>
    """
    posted = extract_job_posting(html)
    assert posted["salary_raw"] == "от 4000 до 4500 USD"
    assert "MONTH" not in posted["salary_raw"]
    lo, hi, currency = parse_salary(posted["salary_raw"])
    assert (lo, hi, currency) == (4000, 4500, "USD")


def test_hh_profession_median() -> None:
    html = (FIXTURES / "hh_profession_python.html").read_text(encoding="utf-8")
    row = parse_hh_profession_html(html, meta={"id": 50, "specialty": "python", "label": "Python"})
    assert row is not None
    assert row["median"] == 102955
    assert row["specialty"] == "python"
    assert row["source"] == "hh_career"
    assert "102" != str(row["median"])  # vacancy count heading ignored


def test_aggregators_enter_corridor_mix() -> None:
    vacancies = [
        SimpleNamespace(
            salary_min=250_000,
            salary_currency="RUB",
            source="hh",
            grade="middle",
            title="Python",
            skills=["python"],
            category="development",
        )
        for _ in range(3)
    ]
    aggregators = [
        {
            "key": "habr_all",
            "grade": None,
            "specialty": None,
            "p25": 100_000,
            "median": 190_000,
            "p75": 300_000,
            "source": "habr_career",
            "mix": True,
        },
        {
            "key": "hh_python",
            "grade": None,
            "specialty": "python",
            "p25": None,
            "median": 100_000,
            "p75": None,
            "source": "hh_career",
            "mix": True,
        },
    ]
    mixed = corridor_from_vacancies(vacancies, aggregators=aggregators)
    vacancy_only = corridor_from_vacancies(vacancies)
    assert mixed["n_vacancies"] == 3
    assert mixed["n_aggregators"] == 2
    assert mixed["median"] != vacancy_only["median"]
    assert mixed["by_source"]["habr_career"] == 1
    assert mixed["by_source"]["hh_career"] == 1
    python = {item["key"]: item for item in mixed["by_specialty"]}["python"]
    assert python["n"] > 3

    junior_only = filter_aggregators(aggregators, grade="junior")
    assert junior_only == []


def test_hh_overall_is_range_not_python() -> None:
    from app.services.hh_salaries import hh_overall_from_rows
    from app.services.salary_fallback import bundled_aggregators

    rows = bundled_aggregators()
    python = next(row for row in rows if row.get("key") == "hh_career_50")
    overall = hh_overall_from_rows(rows)
    assert overall is not None
    assert overall["key"] == "hh_career_all"
    assert overall["specialty"] is None
    assert overall["p25"] and overall["median"] and overall["p75"]
    assert overall["p25"] < overall["median"] < overall["p75"]
    assert overall["median"] != python["median"]
    assert any(row.get("key") == "hh_career_all" for row in rows)


def test_empty_vacancies_still_get_aggregator_corridor() -> None:
    from app.services.salary_fallback import bundled_aggregators

    empty = corridor_from_vacancies([], aggregators=bundled_aggregators())
    assert empty["n_vacancies"] == 0
    assert empty["n_aggregators"] > 0
    assert empty["p25"] and empty["median"] and empty["p75"]
    assert empty["p25"] <= empty["median"] <= empty["p75"]
    grades = {item["key"] for item in empty["by_grade"]}
    assert {"junior", "middle", "senior"} <= grades
    specs = {item["key"] for item in empty["by_specialty"]}
    assert "python" in specs

