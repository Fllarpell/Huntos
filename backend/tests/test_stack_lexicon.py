from __future__ import annotations

from app.services.scraper.sources.stack_lexicon import (
    STACK_IDS,
    STACK_SPEC,
    build_stack_spec,
    parse_inbox_query,
    parse_query_stacks,
    stack_evidence_terms,
)


def test_stack_spec_uses_catalog_labels_and_generated_hyphens() -> None:
    spec = build_stack_spec()
    assert tuple(spec) == STACK_IDS

    ml_tokens, ml_phrases, _ml_soft = spec["ml"]
    assert {"ml", "ai", "nlp", "mlops", "llm"} <= ml_tokens
    joined = " ".join(ml_phrases)
    assert "машинное обучение" in joined
    assert "data scientist" in joined
    assert "дата-сайентист" in joined or "дата сайентист" in joined
    assert "ml-инженер" in ml_phrases
    assert "ml инженер" in ml_phrases
    assert "ml-тимлид" in ml_phrases
    assert "machine learning" in joined

    go_tokens, go_phrases, _go_soft = spec["go"]
    assert "go" in go_tokens and "golang" in go_tokens
    assert "go-разработчик" in go_phrases
    assert "go разработчик" in go_phrases

    backend_phrases = spec["backend"][1]
    assert "go-разработчик" in backend_phrases

    java_phrases = " ".join(spec["java"][1])
    assert "java" not in spec["java"][1]
    assert "javascript" not in java_phrases

    sec_tokens, sec_phrases, _sec_soft = spec["security"]
    assert {"soc", "siem", "appsec", "dfir", "forensic"} <= sec_tokens
    joined_sec = " ".join(sec_phrases)
    assert "информационная безопасность" in joined_sec


def test_stack_spec_phrase_budget_stays_small() -> None:
    """Regression: label×suffix explosion froze /api while computing salary corridor."""
    total = sum(len(phrases) for _tokens, phrases, _soft in STACK_SPEC.values())
    assert total < 12_000


def test_matching_stack_ids_is_fast_on_typical_titles() -> None:
    import time

    from app.services.scraper.sources.stack_lexicon import matching_stack_ids

    titles = [
        "Senior Python Developer / Backend",
        "ML-инженер (NLP)",
        "Go-разработчик в финтех",
        "Системный аналитик",
        "DevOps / SRE",
    ] * 40
    started = time.perf_counter()
    for title in titles:
        matching_stack_ids(title, ["Python", "FastAPI"], "Backend")
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0, elapsed


def test_stack_spec_cached_identity() -> None:
    assert STACK_SPEC is build_stack_spec()
    assert STACK_SPEC is build_stack_spec()


def test_parse_nlp_is_topic_not_ml_stack() -> None:
    stacks, leftover, topics = parse_inbox_query("nlp")
    assert stacks == []
    assert leftover == ""
    assert topics and any("nlp" in group for group in topics)

    stacks2, leftover2 = parse_query_stacks("nlp")
    assert stacks2 == []
    assert leftover2 == ""


def test_parse_ml_still_stack_chip() -> None:
    stacks, leftover, topics = parse_inbox_query("ml")
    assert stacks == ["ml"]
    assert leftover == ""
    assert topics == []


def test_parse_python_nlp_combines() -> None:
    stacks, leftover, topics = parse_inbox_query("python nlp")
    assert stacks == ["python"]
    assert leftover == ""
    assert topics and any("nlp" in group for group in topics)


def test_parse_go_alias() -> None:
    stacks, leftover, topics = parse_inbox_query("golang яндекс")
    assert stacks == ["go"]
    assert leftover == "яндекс"
    assert topics == []


def test_every_stack_has_evidence_lexicon() -> None:
    for stack_id in STACK_IDS:
        terms = stack_evidence_terms(stack_id)
        assert terms, stack_id
        assert any(len(term) >= 3 for term in terms), (stack_id, terms)


def test_parse_react_and_k8s_map_to_stacks() -> None:
    stacks, leftover, topics = parse_inbox_query("react kubernetes")
    assert stacks == ["frontend", "devops"]
    assert leftover == ""
    assert topics == []
