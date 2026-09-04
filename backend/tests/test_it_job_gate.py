from __future__ import annotations

from app.services.scraper.sources.it_job_gate import is_non_it_title, listing_is_it_job, looks_like_it_job


def test_rejects_sales_support_hr_and_game_art() -> None:
    junk = [
        "Менеджер по продажам",
        "Специалист технической поддержки",
        "Специалист поддержки клиентов (УДАЛЁННО)",
        "Специалист по подбору персонала",
        "Minecraft-аниматор / In-game Animator (Blockbuster / BBS)",
        "Графический дизайнер",
        "Оператор торговой сети",
    ]
    for title in junk:
        assert is_non_it_title(title), title
        assert not listing_is_it_job({"title": title})
        assert not looks_like_it_job({"title": title})


def test_keeps_engineering_and_product() -> None:
    keep = [
        "Python-разработчик",
        "DevOps / SRE",
        "Системный аналитик",
        "Product Manager",
        "UX/UI дизайнер",
        "ML-инженер",
        "QA Automation",
    ]
    for title in keep:
        assert listing_is_it_job({"title": title}), title
        assert looks_like_it_job({"title": title}), title
