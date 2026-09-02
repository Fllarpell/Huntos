"""App-level Prometheus series. HTTP RED lives on the instrumentator."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

scraper_runs_total = Counter(
    "wf_scraper_runs_total",
    "Scraper config executions",
    ["status"],
)
scraper_run_seconds = Histogram(
    "wf_scraper_run_seconds",
    "Scraper run wall time",
    buckets=(1, 5, 15, 30, 60, 120, 300),
)
telegram_parse_total = Counter(
    "wf_telegram_parse_total",
    "Telegram parse batches",
    ["status"],
)
vacancies_scored_total = Counter(
    "wf_vacancies_scored_total",
    "Vacancies leaving PENDING scoring",
)
scheduler_running = Gauge(
    "wf_scheduler_running",
    "1 when APScheduler is started in this process",
)
scheduler_jobs = Gauge(
    "wf_scheduler_jobs",
    "Scheduled job count in this process",
)

# Labelled counters are omitted from /metrics until the first .inc().
# Pre-create the statuses we emit so Grafana rate() is a zero line, not No data.
for _status in ("ok", "error", "unknown"):
    scraper_runs_total.labels(status=_status)
    telegram_parse_total.labels(status=_status)
