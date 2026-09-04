from __future__ import annotations

from app.services.company_exclude import company_is_excluded, normalize_exclude_companies, vacancy_is_excluded


def test_normalize_dedupes_and_strips() -> None:
    assert normalize_exclude_companies([" Яндекс ", "яндекс", "vk", "x"]) == ["Яндекс", "vk"]


def test_exclude_yandex_aliases() -> None:
    names = ["яндекс"]
    assert company_is_excluded("Яндекс", names)
    assert company_is_excluded("Yandex", names)
    assert company_is_excluded("Yandex Go", names)
    assert company_is_excluded("Яндекс.Такси", names)
    assert company_is_excluded("YTsaurus", names)
    assert company_is_excluded("Плюс Фантех", names)
    assert not company_is_excluded("Купер", names)
    assert not company_is_excluded("NDA", names)
    assert not company_is_excluded("Маркет", names)


def test_exclude_yandex_career_teams() -> None:
    names = ["яндекс"]
    assert vacancy_is_excluded(
        names,
        company="Маркет",
        title="Backend",
        source="career",
        source_id="yandex:15322",
        source_url="https://yandex.ru/jobs/vacancies/backend-python-moscow",
        tags=["career", "yandex"],
    )
    assert vacancy_is_excluded(
        names,
        company="Алиса и Умные Устройства",
        title="Разработчик на Go в Яндекс Логистику",
        source="career",
        source_id="yandex:1",
    )
    assert vacancy_is_excluded(
        names,
        company="Автономный транспорт",
        source="career",
        source_id="yandex:99",
        company_icon="https://www.google.com/s2/favicons?sz=128&domain=yandex.ru",
    )
    assert not vacancy_is_excluded(names, company="Купер", title="ML", source="hh", source_id="123")


def test_exclude_other_career_boards() -> None:
    assert vacancy_is_excluded(
        ["т-банк"],
        company="Команда платежей",
        source="career",
        source_id="tbank:timlid/0a498705-0ee0-4bc7-97bf-05fbc5f35f64",
        source_url="https://www.tbank.ru/career/it/vacancy/moscow/x/0a498705-0ee0-4bc7-97bf-05fbc5f35f64/",
    )
    assert vacancy_is_excluded(["авито"], company="Техплатформа", source="career", source_id="avito:razrabotka/19100")
    assert vacancy_is_excluded(["vk"], company="VK", source="career", source_id="vk:45850")
    assert not vacancy_is_excluded(["vk"], company="Ozon", source="hh", source_id="1")


def test_exclude_vk_brand() -> None:
    assert company_is_excluded("ВКонтакте", ["vk"])
    assert company_is_excluded("VK", ["вк"])
    assert not company_is_excluded("Ozon", ["vk"])
    assert not company_is_excluded("ВкусВилл", ["vk"])
