"""Last-known public IT salary snapshots. Used when an account has no vacancy forks yet."""

from __future__ import annotations

from app.services.getmatch_salaries import GETMATCH_SALARIES_URL
from app.services.habr_salaries import HABR_SALARIES_URL
from app.services.hh_salaries import HH_CAREER_ORIGIN, hh_overall_from_rows
from app.services.levels_fyi import LEVELS_ORIGIN

# Habr Career /salaries overall IT by grade (monthly RUB, survey).
_HABR = (
    ("all", None, "All", 108_333, 190_833, 305_833, 40_943),
    ("intern", "intern", "Intern", 47_666, 68_666, 97_000, 1_772),
    ("junior", "junior", "Junior", 63_659, 93_333, 136_666, 5_812),
    ("middle", "middle", "Middle", 108_333, 166_666, 242_133, 18_433),
    ("senior", "senior", "Senior", 206_666, 293_333, 388_333, 9_559),
    ("lead", "lead", "Lead", 248_333, 377_500, 503_333, 5_367),
)

# career.hh.ru profession medians (vacancy-posted, monthly RUB).
_HH = (
    (50, "python", "Python-разработчик", 102_955),
    (38, "java", "Java-разработчик", 112_782),
    (46, "go", "Golang-разработчик", 154_443),
    (45, "csharp", "C#/.NET-разработчик", 123_842),
    (41, "ruby", "Ruby-разработчик", 184_000),
    (49, "php", "PHP-разработчик", 97_212),
    (40, "frontend", "Frontend-разработчик", 86_566),
    (43, "backend", "Backend-разработчик", 88_438),
    (44, "fullstack", "Fullstack-разработчик", 136_697),
    (42, "android", "Android-разработчик", 115_021),
    (47, "ios", "iOS-разработчик", 97_435),
    (52, "mobile", "Flutter-разработчик", 119_950),
    (53, "devops", "DevOps-инженер", 111_226),
    (1, "ml_ai", "Data Scientist", 128_788),
    (7, "data_engineer", "Data Engineer", 115_329),
    (5, "analytics", "BI-аналитик", 64_684),
    (57, "backend", "Инженер-программист", 121_628),
    (96, "backend", "Архитектор ПО", 75_233),
    (95, "qa", "Нагрузочное тестирование", 56_243),
)


def bundled_aggregators() -> list[dict]:
    """Always-on priors so a fresh account still sees a market corridor."""
    rows: list[dict] = []
    for key, grade, name, p25, median, p75, n in _HABR:
        rows.append(
            {
                "key": f"habr_{key}",
                "grade": grade,
                "specialty": None,
                "label": "IT · все грейды" if grade is None else f"IT · {name}",
                "n": n,
                "p25": p25,
                "median": median,
                "p75": p75,
                "currency": "RUB",
                "period": "month",
                "source": "habr_career",
                "url": HABR_SALARIES_URL,
                "attribution": "Хабр Карьера · зарплаты (анкеты специалистов)",
                "mix": True,
            }
        )
    rows.append(
        {
            "key": "getmatch_all",
            "grade": None,
            "specialty": None,
            "label": "IT · все грейды",
            "n": 68_299,
            "p25": 160_000,
            "median": 230_000,
            "p75": None,
            "p90": 400_000,
            "currency": "RUB",
            "period": "month",
            "source": "getmatch_salaries",
            "url": GETMATCH_SALARIES_URL,
            "attribution": "GetMatch · зарплаты (анонимный срез, p25 / медиана / p90)",
            "mix": True,
        }
    )
    for pid, specialty, label, median in _HH:
        rows.append(
            {
                "key": f"hh_career_{pid}",
                "grade": None,
                "specialty": specialty,
                "label": label,
                "n": None,
                "p25": None,
                "median": median,
                "p75": None,
                "currency": "RUB",
                "period": "month",
                "source": "hh_career",
                "url": f"{HH_CAREER_ORIGIN}/profession/{pid}",
                "attribution": "hh.ru · медианы зарплат в вакансиях (career.hh.ru)",
                "mix": True,
            }
        )
    overall = hh_overall_from_rows(rows)
    if overall:
        rows.append(overall)
    # Levels.fyi Russia SWE, annual TC from the public .md, shown monthly.
    annual = (2_762_962, 3_877_113, 5_086_353)
    monthly = tuple(int(round(v / 12)) for v in annual)
    rows.append(
        {
            "key": "swe_russia",
            "grade": None,
            "specialty": None,
            "label": "Software Engineer · Russia",
            "n": None,
            "p25": monthly[0],
            "median": monthly[1],
            "p75": monthly[2],
            "currency": "RUB",
            "period": "month",
            "source": "levels.fyi",
            "url": f"{LEVELS_ORIGIN}/t/software-engineer/locations/russia",
            "attribution": "Data source: Levels.fyi (https://www.levels.fyi)",
            "mix": True,
        }
    )
    return rows
