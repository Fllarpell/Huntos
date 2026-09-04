from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.clipper import detect_source
from app.services.scraper.query_key import make_query_key
from app.services.scraper.sources.career import (
    normalize_career_job,
    parse_aviasales_detail,
    parse_aviasales_listing,
    parse_avito_detail,
    parse_avito_listing,
    parse_cloudru_detail,
    parse_cloudru_listing,
    parse_croc_detail,
    parse_croc_listing,
    parse_dgis_detail,
    parse_dgis_listing,
    parse_alfa_detail,
    parse_alfa_listing,
    parse_kontur_detail,
    parse_kontur_listing,
    parse_wb_detail,
    parse_wb_listing,
    parse_itone_detail,
    parse_itone_listing,
    parse_jet_detail,
    parse_jet_listing,
    parse_mts_detail,
    parse_mts_listing,
    parse_ibs_detail,
    parse_ibs_listing,
    parse_kaspersky_detail,
    parse_kaspersky_listing,
    parse_megafon_detail,
    parse_megafon_listing,
    parse_solar_detail,
    parse_solar_listing,
    parse_selectel_detail,
    parse_selectel_listing,
    parse_tbank_api_payload,
    parse_tbank_detail,
    parse_tbank_listing,
    parse_vk_detail_html,
    parse_vk_listing,
    parse_x5_detail,
    parse_x5_listing,
    parse_yadro_detail,
    parse_yadro_listing,
    parse_yandex_detail,
    parse_yandex_listing,
    tbank_next_offset,
)
from app.services.scraper.sources.career_catalog import BOARDS
from app.services.scraper.sources.career_filters import normalize_career_params

FIXTURES = Path(__file__).parent / "fixtures"


def test_query_key_career_is_company() -> None:
    a = make_query_key("career", {"company": "Aviasales"})
    b = make_query_key("career", {"company": "aviasales"})
    assert a == b
    vk = make_query_key("career", {"company": "vk"})
    assert a != vk
    hire = make_query_key("hirehi", {"search": "python"})
    assert a != hire
    go = make_query_key("career", {"company": "vk", "stack": ["go"]})
    py = make_query_key("career", {"company": "vk", "stack": ["python"]})
    assert go == py


def test_aviasales_listing_and_detail_normalize() -> None:
    jobs = parse_aviasales_listing((FIXTURES / "aviasales_listing.html").read_text())
    assert [item["id"] for item in jobs] == ["aviasales:4307347", "aviasales:1"]
    assert jobs[0]["title"] == ".net Developer"
    assert jobs[0]["company"] == "Авиасейлс"

    detail = parse_aviasales_detail((FIXTURES / "aviasales_detail.html").read_text(), "aviasales:4307347")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["source"] == "career"
    assert payload["source_id"] == "aviasales:4307347"
    assert payload["title"] == ".net Developer"
    assert payload["company"] == "Авиасейлс"
    assert payload["work_format"] == "удалённо"
    assert "C#" in payload["skills"]
    assert "PostgreSQL" in (payload["description"] or "") or "C#" in (payload["requirements"] or "")


def test_vk_listing_keeps_it_only_and_html_detail() -> None:
    data = json.loads((FIXTURES / "vk_listing.json").read_text())
    jobs = parse_vk_listing(data)
    assert len(jobs) == 1
    assert jobs[0]["id"] == "vk:45850"
    assert jobs[0]["title"] == "Go-разработчик"

    detail = parse_vk_detail_html((FIXTURES / "vk_vacancy.html").read_text(), "vk:45850")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["source"] == "career"
    assert payload["source_id"] == "vk:45850"
    assert payload["company"] == "VK"
    assert payload["work_format"] == "удалённо"
    blob = payload["description"] or ""
    assert "PostgreSQL" in blob
    assert "Задачи" in blob
    assert "- Разработка инфраструктуры" in blob
    assert "ДМС" in blob
    assert blob.count("ДМС") == 1
    assert "Формат работы:" in blob
    assert "senior" in blob.lower()
    assert "Похожие" not in blob
    assert "платёжных" not in blob
    assert "Откликнуться" not in blob
    assert "© 2026" not in blob


def test_vk_detail_without_article_keeps_fields() -> None:
    html = """
    <h1>Python-разработчик, Москва</h1>
    <h4 class="vacancy-title">Формат работы</h4>
    <div class="vacancy-tag">Дистанционный</div>
    <div class="features-item-text">ДМС</div>
    <h2>Похожие вакансии</h2>
    <h3>Go-разработчик в команду разработки платёжных решений</h3>
    """
    detail = parse_vk_detail_html(html, "vk:1")
    blob = detail["description"] or ""
    assert "Дистанционный" in blob
    assert "ДМС" in blob
    assert "платёжных" not in blob


def test_yandex_listing_and_detail_normalize() -> None:
    listing = json.loads((FIXTURES / "yandex_listing.json").read_text())
    jobs = parse_yandex_listing(listing)
    assert jobs[0]["id"] == "yandex:15322"
    assert jobs[0]["source_url"] == "https://yandex.ru/jobs/vacancies/backend-python-moscow"

    detail = parse_yandex_detail(json.loads((FIXTURES / "yandex_detail.json").read_text()), "yandex:15322")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["source"] == "career"
    assert payload["title"] == "Backend-разработчик"
    assert payload["company"] == "Яндекс"
    assert payload["work_format"] in {"удалённо", "гибрид"}
    assert "Python" in payload["skills"]
    blob = payload["description"] or ""
    assert "сервис" in blob.lower() or "Python" in blob


def test_clipper_detects_career_urls() -> None:
    assert detect_source("https://www.aviasales.ru/about/vacancies/4307347") == ("career", "aviasales:4307347")
    assert detect_source("https://team.vk.company/vacancy/45850/") == ("career", "vk:45850")
    assert detect_source("https://yandex.ru/jobs/api/publications/15322/") == ("career", "yandex:15322")
    assert detect_source("https://yandex.ru/jobs/vacancies/backend-python-moscow") == (
        "career",
        "yandex:backend-python-moscow",
    )
    assert detect_source("https://career.avito.com/vacancies/razrabotka/19100/") == (
        "career",
        "avito:razrabotka/19100",
    )
    assert detect_source("https://careers.kaspersky.ru/vacancy/25341") == ("career", "kaspersky:25341")
    assert detect_source("https://careers.yadro.com/vacancy/2499") == ("career", "yadro:2499")
    assert detect_source("https://job.megafon.ru/vacancy/arhitektor-llm-4748") == (
        "career",
        "megafon:1/arhitektor-llm-4748",
    )
    assert detect_source("https://team.rt-solar.ru/vacancies/862/") == ("career", "solar:862")
    assert detect_source("https://selectel.ru/careers/all/vacancy/1572/") == ("career", "selectel:1572")
    assert detect_source("https://x5.tech/vacancy/76dc9436-816f-4583-98a3-c04ac13b32e7") == (
        "career",
        "x5:76dc9436-816f-4583-98a3-c04ac13b32e7",
    )
    assert detect_source("https://www.it-one.ru/vacancies/40b2f0c964fdeeedb63cdfae64470738/") == (
        "career",
        "itone:40b2f0c964fdeeedb63cdfae64470738",
    )
    assert detect_source("https://cloud.ru/career/vacancies/2829875") == ("career", "cloudru:2829875")
    assert detect_source("https://careers.croc.ru/vacancies/inzhener-po-informatsionnoy-bezopasnosti/") == (
        "career",
        "croc:inzhener-po-informatsionnoy-bezopasnosti",
    )
    assert detect_source("https://jet.su/career/vacancies/inzhener-proektirovshchik-po-monitoringu/") == (
        "career",
        "jet:inzhener-proektirovshchik-po-monitoringu",
    )
    assert detect_source("https://job.mts.ru/vacancy/699529378433859649") == ("career", "mts:699529378433859649")
    assert detect_source("https://ibs.ru/career/jobs/inzhener-avtomatizirovannogo-testirovaniya-backend-tyumen/") == (
        "career",
        "ibs:inzhener-avtomatizirovannogo-testirovaniya-backend-tyumen",
    )
    assert detect_source("https://job.2gis.ru/vacancies/development/461") == ("career", "2gis:461")
    assert detect_source("https://job.alfabank.ru/vacancies/moskva/remote-job/vedushchii-razrabotchik-c_-_-_net_38244") == (
        "career",
        "alfa:38244",
    )
    assert detect_source("https://kontur.ru/career/vacancies/5478") == ("career", "kontur:5478")
    assert detect_source("https://career.wb.ru/vacancy/31543") == ("career", "wb:31543")
    assert detect_source(
        "https://www.tbank.ru/career/it/vacancy/moscow/timlid-produktovoj-analitiki/0a498705-0ee0-4bc7-97bf-05fbc5f35f64/"
    ) == ("career", "tbank:timlid-produktovoj-analitiki/0a498705-0ee0-4bc7-97bf-05fbc5f35f64")


def test_avito_listing_keeps_it_only() -> None:
    jobs = parse_avito_listing((FIXTURES / "avito_listing.html").read_text())
    assert [item["id"] for item in jobs] == ["avito:razrabotka/19100"]
    assert jobs[0]["title"] == "Тимлид Android разработки"
    assert jobs[0]["remote"] is True
    detail = parse_avito_detail((FIXTURES / "avito_detail.html").read_text(), "avito:razrabotka/19100")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["source"] == "career"
    assert payload["company"] == "Авито"
    assert payload["work_format"] in {"удалённо", "гибрид"}
    blob = payload["description"] or ""
    assert "О команде" in blob
    assert "- быстро и стабильно собирать" in blob
    assert "time to market;развивать" not in blob
    assert "Похожие" not in blob


def test_kaspersky_listing_drops_finance() -> None:
    jobs = parse_kaspersky_listing((FIXTURES / "kaspersky_listing.html").read_text())
    assert [item["id"] for item in jobs] == ["kaspersky:25341", "kaspersky:25668"]
    detail = parse_kaspersky_detail((FIXTURES / "kaspersky_detail.html").read_text(), "kaspersky:25341")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "Лаборатория Касперского"
    assert "SOC" in (payload["description"] or "") or "SOC" in " ".join(payload["skills"])


def test_tbank_listing_keeps_it_only() -> None:
    jobs = parse_tbank_listing((FIXTURES / "tbank_listing.html").read_text())
    assert len(jobs) == 1
    assert jobs[0]["id"].startswith("tbank:")
    assert "0a498705-0ee0-4bc7-97bf-05fbc5f35f64" in jobs[0]["id"]
    assert jobs[0]["title"] == "Тимлид продуктовой аналитики"
    detail = parse_tbank_detail((FIXTURES / "tbank_detail.html").read_text(), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "Т-Банк"
    assert "Python" in (payload["description"] or "") or "аналитик" in (payload["title"] or "").lower()


def test_tbank_api_keeps_it_all_cities() -> None:
    jobs = parse_tbank_api_payload(json.loads((FIXTURES / "tbank_api.json").read_text()))
    assert [item["title"] for item in jobs] == [
        "ML-тимлид в AI-центр — Кредитные продукты",
        "ML-инженер (NLP, Авто.ру)",
    ]
    assert jobs[0]["location"] == "Казань"
    assert "/kazan/" in jobs[0]["source_url"]
    assert jobs[1]["location"] == "Москва"
    assert "/moscow/" in jobs[1]["source_url"]
    payload = json.loads((FIXTURES / "tbank_api.json").read_text())
    assert tbank_next_offset(payload, 0) == 50
    payload["payload"]["nextPagination"]["it"]["isFinished"] = True
    assert tbank_next_offset(payload, 0) is None


def test_stack_tokens_cover_hyphen_titles() -> None:
    from app.services.scraper.sources.career_filters import STACK_IDS, career_job_matches, normalize_career_params

    assert "csharp" in STACK_IDS and "security" in STACK_IDS and "sysanalyst" in STACK_IDS
    assert normalize_career_params({"company": "tbank", "stack": ["csharp", "nope"]})["stack"] == ["csharp"]

    def hit(title: str, stack: str, **extra: str) -> bool:
        return career_job_matches({"title": title, **extra}, {"company": "tbank", "stack": [stack]})

    assert hit("ML-тимлид в AI-центр — Кредитные продукты", "ml")
    assert hit("Стажер ML-инженер", "ml", short_summary="Обучайте искусственный интеллект")
    assert hit("ML инженер (NLP)", "ml")
    assert hit("Дата-сайентист", "ml")
    assert hit("Senior AI / ML Engineer", "ml")
    assert hit("Go-разработчик", "go")
    assert hit("Go-разработчик", "backend")
    assert hit("Backend-разработчик — Node.js", "backend")
    assert hit("Backend-разработчик — Node.js", "nodejs")
    assert hit("QA-инженер — автоматизация (Авто.ру)", "qa")
    assert hit("DevOps-инженер", "devops")
    assert hit(".NET Developer", "csharp")
    assert hit("C#-разработчик", "csharp")
    assert hit("1С-разработчик", "onec")
    assert hit("Инженер информационной безопасности", "security")
    assert hit("Системный аналитик", "sysanalyst")
    assert hit("Системный аналитик", "analytics")
    assert hit("SRE / Platform Engineer", "sre")
    assert hit("ML-продакт-менеджер (VoiceKit)", "ml")
    assert hit("ML-продакт-менеджер (VoiceKit)", "product")
    assert hit("Product Manager", "product")
    assert hit("Data Engineer", "data")
    assert hit("Инженер данных", "data")
    assert not hit("HTML-верстальщик", "ml")
    assert not hit("Бизнес-аналитик", "ml")
    assert not hit("JavaScript-разработчик", "java")
    assert not hit("Go-разработчик", "python")


def test_career_boards_and_company_required(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    client.post("/api/auth/register", json={"email": f"career-{suffix}@hunt.test", "password": "password1"})
    cookies = {"hunt_session": client.cookies["hunt_session"]}
    boards = client.get("/api/scraper/boards", cookies=cookies)
    assert boards.status_code == 200
    slugs = {item["slug"] for item in boards.json()}
    assert slugs == {board.slug for board in BOARDS}

    missing = client.post(
        "/api/scraper-configs",
        json={"name": "x", "source": "career", "enabled": True, "query_params": {}},
        cookies=cookies,
    )
    assert missing.status_code == 400

    unknown = client.post(
        "/api/scraper-configs",
        json={"name": "x", "source": "career", "enabled": True, "query_params": {"company": "gazprom"}},
        cookies=cookies,
    )
    assert unknown.status_code == 400

    ok = client.post(
        "/api/scraper-configs",
        json={"name": "", "source": "career", "enabled": True, "query_params": {"company": "aviasales"}},
        cookies=cookies,
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["source"] == "career"
    assert body["query_params"]["company"] == "aviasales"
    assert body["name"] == "Авиасейлс"
    assert "aviasales.ru" in (body["listing_url"] or "")


def test_normalize_career_params_drops_unknown() -> None:
    assert normalize_career_params({"company": "VK"}) == {"company": "vk"}
    assert normalize_career_params({"company": "gazprom"}) == {"company": ""}
    assert normalize_career_params(
        {"company": "aviasales", "search": " python ", "stack": ["python"], "formats": ["remote"]}
    ) == {
        "company": "aviasales",
        "search": "python",
        "stack": ["python"],
        "formats": ["remote"],
    }


def test_career_listing_filters_by_common_search() -> None:
    from app.services.scraper.sources.career_filters import career_job_matches

    data = json.loads((FIXTURES / "vk_listing.json").read_text())
    jobs = parse_vk_listing(data)
    go = jobs[0]
    assert career_job_matches(go, {"company": "vk", "search": "go"})
    assert career_job_matches(go, {"company": "vk", "stack": ["go", "backend"]})
    assert not career_job_matches(go, {"company": "vk", "search": "python"})
    assert not career_job_matches(go, {"company": "vk", "stack": ["python"]})


def test_career_targets_live_match_boards() -> None:
    from app.services.scraper.sources.career_targets import TARGETS

    live = {item.slug for item in TARGETS if item.channel == "live"}
    boards = {board.slug for board in BOARDS}
    assert live == boards
    slugs = [item.slug for item in TARGETS]
    assert len(slugs) == len(set(slugs))


def test_career_normalize_uses_board_logo() -> None:
    jobs = parse_aviasales_listing((FIXTURES / "aviasales_listing.html").read_text())
    detail = parse_aviasales_detail((FIXTURES / "aviasales_detail.html").read_text(), "aviasales:4307347")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company_icon"]
    assert "aviasales.ru" in payload["company_icon"]

    vk = json.loads((FIXTURES / "vk_listing.json").read_text())
    vk_jobs = parse_vk_listing(vk)
    vk_detail = parse_vk_detail_html((FIXTURES / "vk_vacancy.html").read_text(), "vk:45850")
    vk_payload = normalize_career_job(vk_detail, vk_jobs[0])
    assert vk_payload["company_icon"]
    assert "vk.com" in vk_payload["company_icon"]


def test_yadro_listing_keeps_it_drops_factory() -> None:
    payload = json.loads((FIXTURES / "yadro_listing.json").read_text())
    jobs = parse_yadro_listing(payload)
    assert [item["title"] for item in jobs] == ["DFIR специалист/ SOC", "AppSec инженер", "Инженер SIEM"]
    assert jobs[0]["id"] == "yadro:2499"
    detail = parse_yadro_detail(payload, "yadro:2499")
    out = normalize_career_job(detail, jobs[0])
    assert out["company"] == "YADRO"
    assert "SIEM" in (out["description"] or "") or "DFIR" in (out["title"] or "")
    assert out["work_format"] in {"удалённо", "гибрид", "Гибридный", "офис"}


def test_megafon_listing_and_detail_normalize() -> None:
    listing = json.loads((FIXTURES / "megafon_listing.json").read_text())
    jobs = parse_megafon_listing(listing)
    assert jobs[0]["id"] == "megafon:1/arhitektor-llm-4748"
    assert jobs[0]["title"] == "Архитектор LLM"
    detail = parse_megafon_detail(json.loads((FIXTURES / "megafon_detail.json").read_text()), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "МегаФон"
    assert "LLM" in (payload["description"] or "") or "LLM" in " ".join(payload["skills"])
    assert payload["work_format"] == "удалённо" or "удал" in (jobs[0].get("work_format") or "").lower()


def test_solar_listing_and_detail() -> None:
    jobs = parse_solar_listing((FIXTURES / "solar_listing.html").read_text())
    assert jobs[0]["id"] == "solar:862"
    assert "forensic" in jobs[0]["title"].lower()
    detail = parse_solar_detail((FIXTURES / "solar_detail.html").read_text(), "solar:862")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "Солар"
    assert "Volatility" in (payload["description"] or "") or "ИБ" in (payload["description"] or "")


def test_selectel_listing_and_detail() -> None:
    jobs = parse_selectel_listing((FIXTURES / "selectel_listing.html").read_text())
    assert [item["id"] for item in jobs] == ["selectel:1887", "selectel:1572"]
    assert jobs[0]["title"].startswith("Backend")
    assert jobs[0]["remote"] is True
    detail = parse_selectel_detail((FIXTURES / "selectel_detail.html").read_text(), "selectel:1572")
    payload = normalize_career_job(detail, jobs[1])
    assert payload["company"] == "Selectel"
    assert "S3" in (payload["description"] or "") or "хранилищ" in (payload["description"] or "")
    assert "Похожие" not in (payload["description"] or "")


def test_x5_listing_and_detail() -> None:
    jobs = parse_x5_listing((FIXTURES / "x5_listing.html").read_text())
    assert jobs[0]["id"] == "x5:76dc9436-816f-4583-98a3-c04ac13b32e7"
    assert "Go" in jobs[0]["title"]
    detail = parse_x5_detail((FIXTURES / "x5_detail.html").read_text(), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "X5 Tech"
    assert "Go" in (payload["description"] or "") or "Go" in payload["title"]


def test_itone_listing_and_detail() -> None:
    jobs = parse_itone_listing(json.loads((FIXTURES / "itone_listing.json").read_text()))
    assert jobs[0]["id"] == "itone:40b2f0c964fdeeedb63cdfae64470738"
    assert jobs[0]["title"] == "Старший Java разработчик"
    assert jobs[0]["remote"] is True
    detail = parse_itone_detail((FIXTURES / "itone_detail.html").read_text(), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "IT_ONE"
    assert "Spring" in (payload["description"] or "")
    assert "кредитного инспектора" in (payload["description"] or "")


def test_cloudru_listing_and_detail() -> None:
    jobs = parse_cloudru_listing((FIXTURES / "cloudru_listing.html").read_text())
    assert jobs[0]["id"] == "cloudru:2829875"
    assert "Frontend" in jobs[0]["title"]
    detail = parse_cloudru_detail((FIXTURES / "cloudru_detail.html").read_text(), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "Cloud.ru"
    assert "React" in (payload["description"] or "") or "Frontend" in payload["title"]


def test_croc_listing_and_detail() -> None:
    jobs = parse_croc_listing((FIXTURES / "croc_listing.html").read_text())
    assert jobs[0]["id"] == "croc:stazher-tekhnicheskoy-podderzhki-kiberbezopasnosti"
    assert "кибербезопас" in jobs[0]["title"].lower()
    detail = parse_croc_detail((FIXTURES / "croc_detail.html").read_text(), "croc:inzhener-po-informatsionnoy-bezopasnosti")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "КРОК"
    assert "безопас" in (payload["title"] or "").lower() or "безопас" in (payload["description"] or "").lower()


def test_jet_listing_and_detail() -> None:
    jobs = parse_jet_listing((FIXTURES / "jet_listing.html").read_text())
    assert jobs[0]["id"] == "jet:inzhener-proektirovshchik-po-monitoringu"
    assert "мониторинг" in jobs[0]["title"].lower()
    detail = parse_jet_detail((FIXTURES / "jet_detail.html").read_text(), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "Инфосистемы Джет"
    assert "мониторинг" in (payload["title"] or "").lower() or "мониторинг" in (payload["description"] or "").lower()


def test_mts_listing_and_detail() -> None:
    jobs = parse_mts_listing(json.loads((FIXTURES / "mts_listing.json").read_text()))
    assert jobs[0]["id"] == "mts:699529378433859649"
    assert jobs[0]["company"] == "МТС"
    detail = parse_mts_detail(json.loads((FIXTURES / "mts_detail.json").read_text()), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "МТС"
    assert "сопровожд" in (payload["title"] or "").lower()
    assert "Jira" in (payload["description"] or "") or "поддерж" in (payload["description"] or "").lower()


def test_ibs_listing_and_detail() -> None:
    jobs = parse_ibs_listing((FIXTURES / "ibs_listing.html").read_text())
    assert jobs[0]["id"].startswith("ibs:")
    detail = parse_ibs_detail((FIXTURES / "ibs_detail.html").read_text(), "ibs:inzhener-avtomatizirovannogo-testirovaniya-backend-tyumen")
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "IBS"
    assert "тестирован" in (payload["title"] or "").lower()


def test_dgis_listing_and_detail() -> None:
    jobs = parse_dgis_listing(json.loads((FIXTURES / "2gis_listing.json").read_text()))
    assert jobs[0]["id"] == "2gis:478"
    assert jobs[0]["company"] == "2ГИС"
    detail = parse_dgis_detail(json.loads((FIXTURES / "2gis_detail.json").read_text()), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "2ГИС"
    assert "безопас" in (payload["title"] or "").lower() or "безопас" in (payload["description"] or "").lower()


def test_alfa_listing_and_detail() -> None:
    jobs = parse_alfa_listing(json.loads((FIXTURES / "alfa_listing.json").read_text()))
    assert any(job["id"] == "alfa:38244" for job in jobs)
    dev = next(job for job in jobs if job["id"] == "alfa:38244")
    detail = parse_alfa_detail(json.loads((FIXTURES / "alfa_detail.json").read_text()), dev["id"])
    payload = normalize_career_job(detail, dev)
    assert payload["company"] == "Альфа-Банк"
    assert "C#" in (payload["description"] or "") or "C#" in payload["skills"]
    assert payload["work_format"] == "удалённо"


def test_kontur_listing_and_detail() -> None:
    jobs = parse_kontur_listing((FIXTURES / "kontur_listing.html").read_text())
    assert any(job["id"] == "kontur:3728" for job in jobs)
    dev = next(job for job in jobs if job["id"] == "kontur:3728")
    assert "разработ" in dev["title"].lower()
    detail = parse_kontur_detail((FIXTURES / "kontur_detail.html").read_text(), "kontur:5478")
    payload = normalize_career_job(detail, {"id": "kontur:5478", "company": "Контур"})
    assert payload["company"] == "Контур"
    assert "маркетолог" in (payload["title"] or "").lower() or "Диадок" in (payload["title"] or "")


def test_wb_listing_and_detail() -> None:
    jobs = parse_wb_listing(json.loads((FIXTURES / "wb_listing.json").read_text()))
    assert jobs[0]["id"].startswith("wb:")
    assert jobs[0]["company"] == "Wildberries"
    detail = parse_wb_detail(json.loads((FIXTURES / "wb_detail.json").read_text()), jobs[0]["id"])
    payload = normalize_career_job(detail, jobs[0])
    assert payload["company"] == "Wildberries"
    assert "SOC" in (payload["title"] or "") or "SOC" in (payload["description"] or "")
