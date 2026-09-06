from pathlib import Path

from app.services.clip_page import KIND_LISTING, KIND_NOISE, KIND_VACANCY, extract_html, judge_page, page_shape
from app.services.clipper import extract_html as clipper_extract


FIXTURES = Path(__file__).parent / "fixtures"

LAMODA_HTML = """
<html><head>
<title>Frontend разработчик — вакансии в Lamoda — Москва.</title>
<meta property="og:title" content="Frontend разработчик — вакансии в Lamoda — Москва.">
</head><body>
<main>
<h1 class="VacancyHeader_vacancyHeader__title__A1Rby">Frontend разработчик</h1>
<div class="chips"><span class="chips__name">г. Москва</span></div>
<section class="VacancyDescription_vacancyDescription___gN2V">
<p><strong>Наш стек: </strong>Vue, Golang</p>
<h3>Чем Вам предстоит заниматься:</h3>
<ul><li>Разрабатывать и поддерживать UI-решения</li><li>Участвовать в проработке технических задач</li></ul>
<p>Ещё абзац про продукт и команду разработки интерфейсов в ритейле.</p>
</section>
<button>Откликнуться</button>
<form><label>Фамилия</label><input></form>
</main>
</body></html>
"""

GENERIC_HTML = """
<html><head><title>Senior Python Engineer | ACME</title>
<meta property="og:site_name" content="ACME">
</head><body>
<h1>Senior Python Engineer</h1>
<p>г. Берлин · гибрид · от 4000 €</p>
<h2>Обязанности</h2>
<ul><li>Писать сервисы на FastAPI и следить за нагрузкой продакшена.</li></ul>
<h2>Требования</h2>
<ul><li>Python, PostgreSQL, опыт от 4 лет.</li></ul>
<button>Откликнуться</button>
</body></html>
"""

NEWS_HTML = """
<html><head><title>Курс доллара вырос на три процента</title></head>
<body><h1>Курс доллара вырос</h1><p>Банк России не стал менять ставку.</p></body></html>
"""

LISTING_HTML = """
<html><head><title>Вакансии компании ACME</title></head>
<body>
<h1>Вакансии</h1>
<a href="/jobs/1">Go</a><a href="/jobs/2">Java</a><a href="/vacancies/3">QA</a>
<a href="/job/4">PM</a><a href="/careers/5">HR</a><a href="/vacancies/6">ML</a>
<a href="/jobs/7">iOS</a><a href="/job/8">Android</a>
</body></html>
"""


def test_extract_html_lamoda_uses_h1_company_and_body() -> None:
    out = clipper_extract(
        LAMODA_HTML, page_url="https://job.lamoda.ru/vacancies/moskva/frontend-vue-developer--1946"
    )
    assert out["title"] == "Frontend разработчик"
    assert out["company"] == "Lamoda"
    assert out["location"] == "Москва"
    assert "Vue" in out["description"]
    assert "UI-решения" in out["description"]
    assert "Фамилия" not in out["description"]
    assert "Vue" in out["skills"]


def test_extract_html_still_prefers_jsonld_jobposting() -> None:
    html = """
    <html><head>
      <title>Noise — вакансии в ACME — Москва.</title>
      <script type="application/ld+json">
      {"@type":"JobPosting","title":"Go backend","hiringOrganization":{"name":"ACME"},
       "description":"<p>Пишем сервисы на Go.</p>"}
      </script>
    </head><body><h1>Go backend</h1></body></html>
    """
    out = extract_html(html)
    assert out["title"] == "Go backend"
    assert out["company"] == "ACME"
    assert "сервисы" in out["description"]


def test_generic_ats_page_without_vendor_classes() -> None:
    out = extract_html(GENERIC_HTML, page_url="https://jobs.acme.test/openings/python-senior")
    assert out["title"] == "Senior Python Engineer"
    assert out["company"] == "ACME"
    assert out["grade"] == "senior"
    assert out["work_format"] == "гибрид"
    assert "FastAPI" in out["description"]
    judged = judge_page(
        url="https://jobs.acme.test/openings/python-senior",
        html=GENERIC_HTML,
        extracted=out,
    )
    assert judged.kind == KIND_VACANCY
    assert judged.allow


def test_jsonld_fixture_is_vacancy() -> None:
    html = (FIXTURES / "avito_detail.html").read_text()
    judged = judge_page(url="https://career.avito.com/vacancies/android/123", html=html)
    assert judged.kind == KIND_VACANCY
    out = extract_html(html)
    assert out["title"] == "Тимлид Android разработки"
    assert out["company"] == "Авито"


def test_news_and_wikipedia_are_noise() -> None:
    news = judge_page(url="https://lenta.ru/news/dollar", html=NEWS_HTML)
    assert news.kind == KIND_NOISE
    assert not news.allow
    wiki = judge_page(
        url="https://en.wikipedia.org/wiki/Software_engineer",
        html="<html><h1>Software engineer</h1><p>An engineer who writes software.</p></html>",
    )
    assert wiki.kind == KIND_NOISE


def test_catalog_is_listing() -> None:
    judged = judge_page(url="https://jobs.acme.test/vacancies", html=LISTING_HTML)
    assert judged.kind == KIND_LISTING
    assert "каталог" in judged.message


def test_hh_salary_article_is_not_a_vacancy() -> None:
    html = (FIXTURES / "hh_profession_python.html").read_text()
    judged = judge_page(url="https://career.hh.ru/profession/50", html=html)
    assert judged.kind != KIND_VACANCY


def test_page_shape_detail_vs_listing() -> None:
    assert page_shape("https://job.lamoda.ru/vacancies/moskva/frontend-vue-developer--1946") == "detail"
    assert page_shape("https://job.lamoda.ru/vacancies") == "listing"
    assert page_shape("https://hh.ru/vacancy/123456") == "detail"
    assert page_shape("https://hh.ru/vacancies/developer") == "listing"


def test_detect_hh_apply_form_url() -> None:
    from app.services.clipper import detect_source

    assert detect_source("https://hh.ru/vacancy/123456") == ("hh", "123456")
    assert detect_source("https://hh.ru/applicant/vacancy_response?vacancyId=123456") == ("hh", "123456")
    assert detect_source("https://magadan.hh.ru/applicant/vacancy_response?vacancyId=99") == ("hh", "99")
