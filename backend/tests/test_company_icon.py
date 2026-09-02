from __future__ import annotations

from app.services.clipper import extract_html
from app.services.company_icon import logo_from_hiring_org, normalize_company_icon
from app.services.scraper.sources.hh import normalize_hh_job
from app.services.scraper.sources.hirehi import normalize_job


HIREHI_CREST = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCI"
    "gdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIj48ZyBpZD0iaGlyZWhpLWNvbXBhbnktcGxhY2Vob2xkZXIiPjxjaXJjbGUgY3g9Ij"
    "EyIiBjeT0iMTIiIHI9IjEyIiBmaWxsPSIjRTJFOEYwIi8+PC9nPjwvc3ZnPg=="
)


def test_drops_hirehi_letter_crest() -> None:
    assert normalize_company_icon(HIREHI_CREST) is None
    assert normalize_company_icon("data:image/svg+xml;utf8,<svg></svg>") is None


def test_keeps_real_http_logo() -> None:
    url = "https://hhcdn.ru/employer-logo/12345.png"
    assert normalize_company_icon(url) == url


def test_absolutizes_hirehi_upload() -> None:
    assert (
        normalize_company_icon("/static/uploads/Ozon_20250322230928.svg")
        == "https://hirehi.ru/static/uploads/Ozon_20250322230928.svg"
    )


def test_rejects_localhost_and_bare_host() -> None:
    assert normalize_company_icon("http://127.0.0.1/logo.png") is None
    assert normalize_company_icon("https://cdn.example.com/") is None


def test_hirehi_normalize_strips_placeholder() -> None:
    row = normalize_job({"id": 1, "title": "Dev", "company": "NDA", "company_icon": HIREHI_CREST, "category": "development"})
    assert row["company_icon"] is None


def test_hh_keeps_employer_logo_from_page() -> None:
    row = normalize_hh_job(
        {
            "id": "42",
            "title": "Backend",
            "company": "Ozon",
            "company_icon": "//hhcdn.ru/employer-logo/ozon.png",
            "url": "https://hh.ru/vacancy/42",
        }
    )
    assert row["company_icon"] == "https://hhcdn.ru/employer-logo/ozon.png"


def test_hh_without_logo_stays_empty() -> None:
    row = normalize_hh_job({"id": "1", "title": "Dev", "company": "Acme"})
    assert row["company_icon"] is None


def test_clipper_takes_org_logo_not_og_image() -> None:
    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.example.com/stock-office.jpg">
      <script type="application/ld+json">
      {"@type":"JobPosting","title":"Go","hiringOrganization":{
        "name":"ACME","logo":"https://cdn.example.com/acme-logo.png"
      },"image":"https://cdn.example.com/job-hero.jpg"}
      </script>
    </head></html>
    """
    extracted = extract_html(html, page_url="https://jobs.example.com/go")
    assert extracted["company_icon"] == "https://cdn.example.com/acme-logo.png"
    assert extracted["title"] == "Go"
    assert extracted["company"] == "ACME"


def test_clipper_ignores_jobposting_image() -> None:
    html = """
    <script type="application/ld+json">
    {"@type":"JobPosting","title":"Go","hiringOrganization":{"name":"ACME"},
     "image":"https://cdn.example.com/job-hero.jpg"}
    </script>
    """
    assert "company_icon" not in extract_html(html)


def test_clipper_ignores_page_without_org_logo() -> None:
    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.example.com/stock-office.jpg">
      <title>Careers</title>
    </head></html>
    """
    extracted = extract_html(html)
    assert "company_icon" not in extracted


def test_logo_from_image_object() -> None:
    org = {"name": "X", "logo": {"@type": "ImageObject", "url": "https://cdn.example.com/x.webp"}}
    assert logo_from_hiring_org(org) == "https://cdn.example.com/x.webp"


def test_contact_org_reuses_vacancy_logo_by_name() -> None:
    from app.services.contacts import _org_icon

    by_name = {"ozon": "https://hirehi.ru/static/uploads/Ozon.svg"}
    assert (
        _org_icon("Ozon", None, by_inn={}, by_name=by_name)
        == "https://hirehi.ru/static/uploads/Ozon.svg"
    )
    assert _org_icon("NDA", None, by_inn={}, by_name=by_name) is None
