from __future__ import annotations

from app.services.scraper.sources.career_filters import auto_name as career_auto_name
from app.services.scraper.sources.career_filters import career_job_matches
from app.services.scraper.sources.geekjob_filters import auto_name as geekjob_auto_name
from app.services.scraper.sources.getmatch_filters import auto_name as getmatch_auto_name
from app.services.scraper.sources.habr_filters import auto_name as habr_auto_name
from app.services.scraper.sources.hirehi_filters import auto_name as hirehi_auto_name
from app.services.scraper.sources.stack_lexicon import STACK_IDS


ALL_STACK = list(STACK_IDS)


def test_wide_career_name_is_ves_it_not_first_two_chips() -> None:
    name = career_auto_name({"company": "yandex", "stack": ALL_STACK})
    assert "весь IT" in name
    assert "qa" not in name
    assert "devops" not in name


def test_wide_career_does_not_drop_jobs_without_stack_words() -> None:
    job = {"title": "Product Manager", "company": "Яндекс", "skills": []}
    assert career_job_matches(job, {"company": "yandex", "stack": ALL_STACK})
    assert not career_job_matches(job, {"company": "yandex", "stack": ["java"]})


def test_wide_aggregator_names() -> None:
    assert "весь IT" in geekjob_auto_name({"stack": ALL_STACK})
    assert "весь IT" in habr_auto_name({"s": ["10", "12", "22", "7", "2", "3", "4", "5", "44", "73", "76", "41", "43"]})
    assert "весь IT" in hirehi_auto_name({"subcategory": [], "format": ["удалённо", "офис", "гибрид"]})
    assert "все специальности" in getmatch_auto_name(
        {
            "specialties": [
                "python",
                "golang",
                "java_scala",
                "js_frontend",
                "js_backend",
                "fullstack",
                "qa_auto",
                "qa_manual",
                "dev_ops",
            ]
        }
    )


def test_wide_hh_name_is_not_no_experience_jargon() -> None:
    from app.services.scraper.sources.hh_filters import auto_name as hh_auto_name, listing_url_from_params, normalize_hh_params

    params = {
        "area": ["113"],
        "experience": ["noExperience", "between1And3", "between3And6", "moreThan6"],
        "schedule": ["flexible", "fullDay", "remote"],
    }
    name = hh_auto_name(params)
    assert name == "Россия · весь IT"
    assert "без опыта" not in name
    assert "гибкий" not in name
    data = normalize_hh_params(params)
    assert data["experience"] == []
    assert data["schedule"] == []
    assert "professional_role=96" in listing_url_from_params(params)
    assert "professional_role=121" not in listing_url_from_params(params)
    assert "professional_role=34" not in listing_url_from_params(params)


def test_wide_career_rejects_sales_support_and_minecraft() -> None:
    params = {"company": "yandex", "stack": ALL_STACK}
    assert not career_job_matches({"title": "Менеджер по продажам", "skills": []}, params)
    assert not career_job_matches({"title": "Специалист технической поддержки", "skills": []}, params)
    assert not career_job_matches(
        {"title": "Minecraft-аниматор / In-game Animator (Blockbuster / BBS)", "skills": []},
        params,
    )
    assert not career_job_matches({"title": "Графический дизайнер", "skills": []}, params)
    assert not career_job_matches({"title": "Оператор торговой сети", "skills": []}, params)
    assert not career_job_matches({"title": "Специалист по подбору персонала", "skills": []}, params)
    assert career_job_matches({"title": "Python-разработчик", "skills": ["Python"]}, params)
    assert career_job_matches({"title": "DevOps / SRE", "skills": []}, params)
    assert career_job_matches({"title": "UX/UI дизайнер", "skills": ["Figma"]}, params)

