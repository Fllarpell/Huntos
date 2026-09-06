#!/usr/bin/env python3
"""HuntOS — соло-бутстрап финмодель (0 инвесторов, 0 команды, старт с 0 юзеров).

Рост = набор регистраций (не % от пустой базы).
Личный runway отдельно от бизнес-EBITDA.
Хроника решений: finance/CHRONICLE.md
Run: backend/.venv/bin/python finance/build_model.py
"""

from __future__ import annotations

import math
from pathlib import Path

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

OUT = Path(__file__).resolve().parent / "HuntOS_финмодель.xlsx"

# ---------------------------------------------------------------------------
# СОЛО-БУТСТРАП (нет инвесторов, нет команды — только ты)
# ---------------------------------------------------------------------------
USD_RUB = 90.0
PAY_FEE = 0.03
TAX = 0.06

PRICE = {"free": 0.0, "lite": 490.0, "plus": 990.0, "pro": 1990.0}
# Lifetime «до оффера» — быстрый cash (CPO): один платёж вместо подписки на N мес
LT_PRICE = 2990.0
LT_MONTHS = 3
LT_SHARE_OF_NEW = 0.30  # доля новых платящих берёт Lifetime вместо месячной подписки

# Stock % платящих. Early = Plus-heavy (касса = 990, не 490 и не 1990).
# Бенчмарки freemium: B2C ~1–3%, типично 2–5%, great 6–8%.
MIX = {"free": 0.96, "lite": 0.008, "plus": 0.028, "pro": 0.004}  # ~4% paid, Plus focus
MIX_OPT = {"free": 0.93, "lite": 0.015, "plus": 0.045, "pro": 0.010}  # ~7%
MIX_PES = {"free": 0.98, "lite": 0.010, "plus": 0.008, "pro": 0.002}  # ~2%

# Воронка: CPO — 40% activation = розовые очки; B2C SaaS realistic ~15–20%
ACT_RATE = 0.15
WAS_OF_USERS = 0.25
# activated→paid ≈ paid_mix / ACT_RATE  (base: 0.04/0.15 ≈ 27% — жёстко, нужен онбординг)

# Старт с НУЛЯ. Цель CPO: ~100 signups / 30 дней (партизанский GTM), не 7–15.
USERS0 = 0
SIGNUPS_M1 = 100  # м.1: TG/LinkedIn/Habr/друзья — иначе нет статистики и A/B
SIGNUPS_GROWTH = 0.12
USER_CHURN = 0.06
SOFT_LAUNCH_MONTHS = 0  # тихий запуск 0.5× убивал набор → «долина смерти»
SOFT_LAUNCH_FACTOR = 1.0

PAY_CHURN = 0.25
PAY_CHURN_OPT = 0.18
PAY_CHURN_PES = 0.40
TARGET_USERS_100 = 100  # Time-to-100

LLM_IN, LLM_OUT, LLM_CACHE, CACHE_HIT = 0.15, 0.50, 0.03, 0.70
TOK = {"match": (450, 40), "letter": (1800, 280), "adapt": (2200, 500), "tg": (500, 60)}
LIMITS = {"lite": (10, 2, 0), "plus": (40, 20, 4), "pro": (80, 40, 10)}
# Free: «понюхать» модель, не жечь токены. Платящие окупают LLM с огромным запасом.
FREE_LIMITS = (3, 0, 0)  # мэтчи / письма / адаптации
FREE_UTIL = 0.25  # ещё реже выбирают лимит
UTIL = 0.35
TG_DAY, DAYS, TG_LLM_SHARE, LLM_PER_1K = 800, 30, 0.20, 40.0

# Инфра = серверы (VPS/DB). Домен — РАЗ В ГОД, не в месячной инфре.
INFRA_P1_USERS, INFRA_P1 = 500, 3800.0  # без «домена/12»
INFRA_P2_USERS, INFRA_P2 = 2000, 14800.0
INFRA_P3 = 34800.0
INFRA_ZERO = 2300.0  # минимальный VPS, пока пусто

DOMAIN_ANNUAL = 1000.0  # .ru/.com ≈ раз в год
CAPEX1 = 4000.0  # бутстрап без домена (домен отдельной строкой в м.1 и м.13)

FOUNDER_GATE, FOUNDER_SHARE = 50000.0, 0.50
# Пока выручки почти нет — ИП/банк/маркетинг минимальны
ADM_IP = 0.0  # включи ~4200 когда оформишь ИП
ADM_BANK = 500.0
ADM_MKT = 2000.0  # сам постишь; не агентство
CAC_Y1 = 400.0  # органика / guerrilla / referral
CAC_Y2 = 1800.0  # когда TG выгорит → Директ/VK (CPO: 1500–2500)
REF_CAC_CUT = 0.25  # referral loop с м.6 режет эффективный CAC
ADM_OTHER = 0.0

# B2B «спасательная шлюпка»: агрегаты рынка при WAS ≳500 (не персональный offer-radar)
B2B_PRICE = 25000.0
B2B_MIN_WAS = 500.0
B2B_MIN_MONTH = 6
B2B_CAP = 3
B2B_OPT_PRICE = 50000.0

# Личные деньги основателя (НЕ раунд)
PERSONAL_CASH0 = 300000.0  # твои накопления
PERSONAL_LIVING = 60000.0  # сколько нужно жить в месяц (эконом)
SIDE_INCOME = 40000.0  # фриланс/работа параллельно, пока продукт не кормит (0 = только накопления)
BUSINESS_CASH0 = 30000.0  # на старте в «бизнесе» (VPS)
# CAPEX1 / DOMAIN — выше в блоке инфра

TARGET_PAYING = 60  # метрика «модель ожила»

SC_OPT_ACQ = 2.0  # Habr/VC spike
SC_PES_ACQ = 0.12  # старый «тихий» набор ~12/мес = долина смерти


def cac_eff(month: int) -> float:
    base = CAC_Y1 if month <= 12 else CAC_Y2
    if month >= 6:
        return base * (1 - REF_CAC_CUT)
    return base


def call_cost(tin, tout):
    eff = (1 - CACHE_HIT) * LLM_IN + CACHE_HIT * LLM_CACHE
    return ((tin / 1e6) * eff + (tout / 1e6) * LLM_OUT) * USD_RUB


def tier_llm(m, l, a, cm, cl, ca, util=UTIL):
    return (m * cm + l * cl + a * ca) * util


def infra_for(n: float) -> float:
    if n <= 0:
        return INFRA_ZERO
    if n <= INFRA_P1_USERS:
        return INFRA_P1
    if n <= INFRA_P2_USERS:
        return INFRA_P2
    return INFRA_P3


def domain_in_month(m: int) -> float:
    """Домен раз в год: мес 1 и каждый 13, 25…"""
    return DOMAIN_ANNUAL if m == 1 or (m > 1 and (m - 1) % 12 == 0) else 0.0


def admin_for(rev: float) -> float:
    ip = 4200.0 if rev >= 10000 else ADM_IP
    return ip + ADM_BANK + ADM_MKT + ADM_OTHER


def mix_metrics(mix, llm_free, llm_lite, llm_plus, llm_pro):
    pm = mix["lite"] + mix["plus"] + mix["pro"]
    arpu = sum(mix[k] * PRICE[k] for k in PRICE)
    arpu_pay = (
        (mix["lite"] * PRICE["lite"] + mix["plus"] * PRICE["plus"] + mix["pro"] * PRICE["pro"]) / pm if pm else 0
    )
    llm_arpu = (
        mix["free"] * llm_free + mix["lite"] * llm_lite + mix["plus"] * llm_plus + mix["pro"] * llm_pro
    )
    # LLM только на платящего (для unit «окупает ли модель»)
    llm_on_pay = (
        (mix["lite"] * llm_lite + mix["plus"] * llm_plus + mix["pro"] * llm_pro) / pm if pm else 0
    )
    return pm, arpu, arpu_pay, llm_arpu, llm_on_pay


def signups(month: int, acq_mult: float = 1.0) -> float:
    raw = SIGNUPS_M1 * ((1 + SIGNUPS_GROWTH) ** (month - 1)) * acq_mult
    if month <= SOFT_LAUNCH_MONTHS:
        raw *= SOFT_LAUNCH_FACTOR
    return raw


def b2b_n(month: int, users: float, mode: str) -> int:
    if mode == "pes":
        return 0
    was = users * WAS_OF_USERS
    if month < B2B_MIN_MONTH or was < B2B_MIN_WAS:
        return 0
    if mode == "opt":
        t = min(1.0, (month - B2B_MIN_MONTH) / 9)
        return max(1, round(1 + t * 4))
    steps = 1 + (month - B2B_MIN_MONTH) // 3
    return min(B2B_CAP, steps)


def simulate(mix, pay_churn, acq_mult, b2b_mode, llm_free, llm_lite, llm_plus, llm_pro, llm_shared):
    pm, arpu, arpu_pay, llm_arpu, llm_on_pay = mix_metrics(mix, llm_free, llm_lite, llm_plus, llm_pro)
    users = float(USERS0)
    pay_prev = 0.0
    biz_cash = BUSINESS_CASH0
    personal = PERSONAL_CASH0
    rows = []
    first_pay_m = None
    hit_60_m = None
    hit_100_m = None
    # Lifetime cohorts: (expire_month, count) — не платят MRR, пока активны
    lt_cohorts: list[tuple[int, float]] = []

    for m in range(1, 25):
        su = signups(m, acq_mult)
        users = users * (1 - USER_CHURN) + su
        pay = users * pm
        new_pay = max(0.0, pay - pay_prev * (1 - pay_churn)) if m > 1 else pay
        cac_unit = cac_eff(m)
        cac = new_pay * cac_unit * (0.5 if m == 1 else 1.0)
        pay_prev = pay

        new_lt = new_pay * LT_SHARE_OF_NEW
        lt_cohorts.append((m + LT_MONTHS - 1, new_lt))
        lt_active = sum(c for exp, c in lt_cohorts if exp >= m)
        # подписочный MRR: платящие минус активный Lifetime; + cash Lifetime
        sub_pay = max(0.0, pay - lt_active)
        rev_sub = sub_pay * arpu_pay
        rev_lt = new_lt * LT_PRICE
        rev_b2c = rev_sub + rev_lt

        bn = b2b_n(m, users, b2b_mode)
        bp = B2B_OPT_PRICE if b2b_mode == "opt" else B2B_PRICE
        rev_b2b = bn * bp
        rev = rev_b2c + rev_b2b
        fee_tax = rev * (PAY_FEE + TAX)
        llm_users = users * llm_arpu
        llm = llm_users + llm_shared + users / 1000 * LLM_PER_1K
        infra = infra_for(users)
        adm = admin_for(rev)
        domain = domain_in_month(m)
        ebitda_pre = rev - fee_tax - llm - infra - adm - cac - domain
        founder_div = (
            max(0.0, FOUNDER_SHARE * (ebitda_pre - FOUNDER_GATE)) if ebitda_pre > FOUNDER_GATE else 0.0
        )
        ebitda = ebitda_pre - founder_div
        capex = CAPEX1 if m == 1 else 0.0

        gm_after_llm = rev - fee_tax - llm

        biz_start = biz_cash
        biz_cash = biz_start + ebitda - capex

        personal_start = personal
        personal = personal - PERSONAL_LIVING + SIDE_INCOME + founder_div
        biz_bailout = 0.0
        if biz_cash < 0:
            biz_bailout = -biz_cash
            personal -= biz_bailout
            biz_cash = 0.0

        if first_pay_m is None and pay >= 1:
            first_pay_m = m
        if hit_60_m is None and pay >= TARGET_PAYING:
            hit_60_m = m
        if hit_100_m is None and users >= TARGET_USERS_100:
            hit_100_m = m

        rows.append(
            {
                "m": m,
                "signups": su,
                "users": users,
                "was": users * WAS_OF_USERS,
                "pay": pay,
                "new_pay": new_pay,
                "new_lt": new_lt,
                "lt_active": lt_active,
                "sub_pay": sub_pay,
                "rev_sub": rev_sub,
                "rev_lt": rev_lt,
                "rev_b2c": rev_b2c,
                "rev_b2b": rev_b2b,
                "rev": rev,
                "fee_tax": fee_tax,
                "llm": llm,
                "llm_users": llm_users,
                "llm_shared": llm_shared + users / 1000 * LLM_PER_1K,
                "infra": infra,
                "domain": domain,
                "adm": adm,
                "cac": cac,
                "cac_unit": cac_unit,
                "gm_after_llm": gm_after_llm,
                "ebitda_pre": ebitda_pre,
                "founder": founder_div,
                "ebitda": ebitda,
                "capex": capex,
                "biz_start": biz_start,
                "biz_end": biz_cash,
                "personal_start": personal_start,
                "personal_end": personal,
                "living": PERSONAL_LIVING,
                "side": SIDE_INCOME,
                "bailout": biz_bailout,
                "b2b_n": bn,
                "margin": ebitda / rev if rev else 0,
            }
        )

    runway_end = next((r["m"] for r in rows if r["personal_end"] < 0), None)
    return {
        "rows": rows,
        "pm": pm,
        "arpu": arpu,
        "arpu_pay": arpu_pay,
        "llm_arpu": llm_arpu,
        "llm_on_pay": llm_on_pay,
        "llm_free": llm_free,
        "first_pay_m": first_pay_m,
        "hit_60_m": hit_60_m,
        "hit_100_m": hit_100_m,
        "runway_end": runway_end,
        "rev24": sum(r["rev"] for r in rows),
        "rev_lt24": sum(r["rev_lt"] for r in rows),
        "ebitda24": sum(r["ebitda"] for r in rows),
        "founder24": sum(r["founder"] for r in rows),
        "llm24": sum(r["llm"] for r in rows),
        "infra24": sum(r["infra"] for r in rows),
        "cac24": sum(r["cac"] for r in rows),
    }


def main() -> None:
    for mix in (MIX, MIX_OPT, MIX_PES):
        assert abs(sum(mix.values()) - 1) < 1e-9

    cm = call_cost(*TOK["match"])
    cl = call_cost(*TOK["letter"])
    ca = call_cost(*TOK["adapt"])
    ct = call_cost(*TOK["tg"])
    llm_free = tier_llm(*FREE_LIMITS, cm, cl, ca, util=FREE_UTIL)
    llm_lite = tier_llm(*LIMITS["lite"], cm, cl, ca)
    llm_plus = tier_llm(*LIMITS["plus"], cm, cl, ca)
    llm_pro = tier_llm(*LIMITS["pro"], cm, cl, ca)
    llm_shared = TG_DAY * DAYS * TG_LLM_SHARE * ct

    base = simulate(MIX, PAY_CHURN, 1.0, "base", llm_free, llm_lite, llm_plus, llm_pro, llm_shared)
    opt = simulate(MIX_OPT, PAY_CHURN_OPT, SC_OPT_ACQ, "opt", llm_free, llm_lite, llm_plus, llm_pro, llm_shared)
    pes = simulate(MIX_PES, PAY_CHURN_PES, SC_PES_ACQ, "pes", llm_free, llm_lite, llm_plus, llm_pro, llm_shared)
    series = base["rows"]

    wb = xlsxwriter.Workbook(str(OUT))
    fmt_title = wb.add_format({"bold": True, "font_size": 14, "font_color": "#1F4E79"})
    fmt_sec = wb.add_format({"bold": True, "font_size": 12, "font_color": "#2E75B6"})
    fmt_hdr = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E79", "align": "center", "border": 1})
    fmt_in = wb.add_format({"bg_color": "#FFF2CC", "border": 1, "num_format": "#,##0.00"})
    fmt_in_int = wb.add_format({"bg_color": "#FFF2CC", "border": 1, "num_format": "#,##0"})
    fmt_in_pct = wb.add_format({"bg_color": "#FFF2CC", "border": 1, "num_format": "0.00%"})
    fmt_calc = wb.add_format({"bg_color": "#E2EFDA", "border": 1, "num_format": "#,##0.00"})
    fmt_calc_int = wb.add_format({"bg_color": "#E2EFDA", "border": 1, "num_format": "#,##0"})
    fmt_calc_pct = wb.add_format({"bg_color": "#E2EFDA", "border": 1, "num_format": "0.00%"})
    fmt_note = wb.add_format({"font_color": "#666666", "italic": True})
    fmt_money = wb.add_format({"num_format": "#,##0.00"})
    fmt_warn = wb.add_format({"bg_color": "#FCE4D6", "border": 1})
    fmt_bad = wb.add_format({"bg_color": "#F8D7DA", "border": 1, "num_format": "#,##0.00"})

    def win(ws, r, c, v, kind="num"):
        f = {"num": fmt_in, "int": fmt_in_int, "pct": fmt_in_pct}[kind]
        ws.write(r, c, v, f)

    def wf(ws, r, c, formula, v, kind="num"):
        f = {"num": fmt_calc, "int": fmt_calc_int, "pct": fmt_calc_pct}[kind]
        if not str(formula).startswith("="):
            formula = "=" + formula
        ws.write_formula(r, c, formula, f, v)

    # ---- Readme ----
    readme = wb.add_worksheet("Readme")
    readme.set_column("A:A", 100)
    readme.write(0, 0, "HuntOS — СОЛО-БУТСТРАП (0 инвесторов, 0 команды, старт с 0 юзеров)", fmt_title)
    for i, t in enumerate(
        [
            "Две кассы + честный runway ~13м. Главный баг старой версии — СКОРОСТЬ набора (10/мес = смерть).",
            "Base: цель ~100 signups/мес1 (партизанский GTM). Pes = старый тихий набор (~12/мес).",
            "Plus 990 = касса; Lifetime 2990/3м = быстрый cash; Pro 1990 позже. Free AI-taste.",
            "Activation в модели 15% (не 40%). CAC Y1≈400 → Y2≈1800; referral −25% с м.6.",
            "B2B с WAS≳500 (агрегаты рынка). Offer-radar конкурентам — НЕ в модели (legal: спросить).",
            "Лист Plan = GTM + продукт (Career OS). Product / Bootstrap / Unit — цифры.",
        ]
    ):
        readme.write(2 + i, 0, t)

    # ---- Plan (CPO / board GTM + product) ----
    plan = wb.add_worksheet("Plan")
    plan.set_column("A:A", 28)
    plan.set_column("B:B", 88)
    plan.write(0, 0, "PLAN — выход из долины смерти (CPO/board 2026)", fmt_title)
    plan.write(1, 0, "Ввод аудита, не закон. Owner-канон: .cursor/rules/huntos-strategy.mdc", fmt_note)

    plan_blocks = [
        ("УГРОЗА", "Скорость: 7–15 signup/мес → нет A/B, нет статистики, runway сгорает на м.13–14."),
        ("ПРАВИЛО 1", f"Цель 30 дней: {SIGNUPS_M1} signups (TG/LinkedIn/Habr/друзья), не 15."),
        ("ПРАВИЛО 2", "Первые 3 мес продавать Plus 990 (+ Lifetime 2990). Не упираться в 1990."),
        ("ПРАВИЛО 3", f"B2B-шлюпка при WAS≳{B2B_MIN_WAS:.0f}: агрегаты рынка HR/изданиям — не персональный offer-radar."),
        ("GTM 1", "Консьерж-MVP: кнопка AI → TG; «скинь 990 на карту» до ЮKassa. Willingness-to-pay до биллинга."),
        ("GTM 2", "Habr/VC: жёсткая статья про боль HH/ATS → ссылка на CRM. 1 пост = потенциально 1–3k regs."),
        ("GTM 3", "Chrome clipper = бесплатный троян: инжест вакансий + база для SEO-агрегатора."),
        ("GTM 4", "Freemium trap: пуш на стадии «Отправлено» → follow-up AI (страх неопределённости)."),
        ("GTM 5", "Build-in-public TG-канал фаундера → CAC≈0 на первых сотнях."),
        ("PROD 1", "Zero-Data onboarding: PDF резюме → 3 карточки сразу (activation 15%→выше)."),
        ("PROD 2", "Продавать ATS-bypass / буллеты / keywords, не простыни cover letter."),
        ("PROD 3", "TG-бот MUST: ссылка→карточка + «завтра собес → шпаргалка»."),
        ("PROD 4", "Резюме-редактор ATS (JSON + react-pdf): PDF бесплатно, AI-адаптация = Plus. Career OS."),
        ("PROD 5", "Referral с дня 1 (друг +1м Plus / ты +лимиты) — защита от CAC Y2."),
        ("PROD 6", "MVP data: anti-ghosting плашка + AI negotiator на этапе Оффер. Leaderboard — вирал."),
        ("LEGAL", "Не делать: auto-apply, продажа intent/«перехват оффера» конкурентам — спросить владельца."),
        ("ФАЗА 0", "Лендинг/бот + консьерж 990 + пост в круге. Первые реальные деньги на карту."),
        ("ФАЗА 1", "Onboarding PDF + resume editor + clipper + TG-бот + пейволл-гейты."),
        ("ФАЗА 2", "Follow-up / negotiator / anti-ghosting. Публичный leaderboard."),
        ("ФАЗА 3", "B2B агрегаты (скорость найма). Shareable CV link для прогрева работодателей."),
    ]
    for i, (k, v) in enumerate(plan_blocks):
        plan.write(3 + i, 0, k)
        plan.write(3 + i, 1, v)

    # ---- Product: ICP + North Star + conversion ----
    prod = wb.add_worksheet("Product")
    prod.set_column("A:A", 36)
    prod.set_column("B:B", 78)
    prod.write(0, 0, "PRODUCT — кто юзер, полярная звезда, конверсия", fmt_title)

    prod.write(2, 0, "1. Кто такой юзер", fmt_sec)
    for i, (k, v) in enumerate(
        [
            ("User (счётчик базы)", "Любой зарегистрированный аккаунт (есть login)."),
            ("ICP (платящий)", "IT Middle/Senior или релокант; активный поиск; ЗП ≳150k; болит ATS/воронка."),
            ("Не ICP", "«Просто смотрю рынок», junior без бюджета, карьерный турист, HR/коуч."),
            ("Free-ценность", "CRM + клиппер + resume PDF + AI-taste (3 мэтча). Не жечь токены."),
            ("Paid-ценность", "Plus 990: ATS-bypass/адаптация/follow-up. Lifetime 2990/3м. Pro позже."),
            ("Почему минус", "EBITDA < 0 из‑за VPS/админ/CAC, не GLM. Домен 1×/год."),
            ("Позиционирование", "Career OS (резюме-якорь + воронка), не «ещё один канбан»."),
        ]
    ):
        prod.write(3 + i, 0, k)
        prod.write(3 + i, 1, v)

    prod.write(11, 0, "2. North Star", fmt_sec)
    for i, (k, v) in enumerate(
        [
            ("WAS", "Weekly Active Searchers = сдвиг ≥1 карточки вакансии за 7 дней."),
            ("Time-to-100", "Месяц, когда база ≥100 юзеров (нужна статистика, не 10 regs)."),
            ("Guardrail $", "Paying + MRR + Lifetime cash. WAS↑ без pay → слабый пейволл."),
            ("Цель", "60 платящих + Personal не в ноль до дивиденда с продукта."),
        ]
    ):
        prod.write(12 + i, 0, k)
        prod.write(12 + i, 1, v)

    prod.write(17, 0, "3. Воронка (жёсткие цифры)", fmt_sec)
    for c, h in enumerate(["Шаг", "Base", "Opt", "Pes"]):
        prod.write(18, c, h, fmt_hdr)
    funnel = [
        ("Signup → Activated (7д)", f"{ACT_RATE:.0%}", "25%", "10%"),
        ("Activated → Paid (≈ stock/act)", f"{(0.04/ACT_RATE):.0%}", f"{(0.07/0.25):.0%}", f"{(0.02/0.10):.0%}"),
        ("Stock платящих от базы", "4%", "7%", "2%"),
        ("Микс among paid (early)", "Lite20/Plus70/Pro10", "больше Plus", "больше Lite"),
        ("Lifetime share of new pay", f"{LT_SHARE_OF_NEW:.0%}", "40%", "15%"),
        ("Industry activation (справка)", "B2C часто 15–20%, не 40%", "", ""),
    ]
    for i, row in enumerate(funnel):
        for c, v in enumerate(row):
            prod.write(19 + i, c, v)

    prod.write(26, 0, "4. LLM vs серверы", fmt_sec)
    pm, arpu, arpu_pay, llm_arpu, llm_on_pay = mix_metrics(MIX, llm_free, llm_lite, llm_plus, llm_pro)
    ltv = arpu_pay / PAY_CHURN if PAY_CHURN else 0
    for i, (k, v, f) in enumerate(
        [
            ("LLM Free ₽/юзер/мес", llm_free, fmt_money),
            ("LLM на платящего", llm_on_pay, fmt_money),
            ("ARPU платящего (sub)", arpu_pay, fmt_money),
            ("Lifetime цена", LT_PRICE, fmt_money),
            ("Запас sub после LLM", arpu_pay - llm_on_pay, fmt_money),
        ]
    ):
        prod.write(27 + i, 0, k)
        prod.write(27 + i, 1, v, f)
    prod.write(32, 0, "Вывод")
    prod.write(32, 1, "Модель окупается. Угроза = медленный набор и Personal runway, не GLM.")

    prod.write(34, 0, "Срез base мес12")
    prod.write(34, 1, f"users={series[11]['users']:.0f} WAS≈{series[11]['was']:.0f} pay={series[11]['pay']:.0f} rev={series[11]['rev']:.0f}")
    prod.write(35, 0, "Time-to-100 / 60 pay / runway")
    prod.write(35, 1, f"{base['hit_100_m']} / {base['hit_60_m']} / {base['runway_end']}")
    # ---- Inputs ----
    ws = wb.add_worksheet("Inputs")
    ws.set_column("A:A", 48)
    ws.set_column("B:B", 14)
    ws.set_column("D:D", 56)
    ws.write(0, 0, "INPUTS — соло-бутстрап", fmt_title)
    R = {}
    r = 3

    def sec(t):
        nonlocal r
        ws.write(r, 0, t, fmt_sec)
        r += 1

    def put(name, val, kind, note, key):
        nonlocal r
        ws.write(r, 0, name)
        win(ws, r, 1, val, kind)
        if note:
            ws.write(r, 3, note, fmt_note)
        R[key] = r
        r += 1

    sec("A. Макро")
    put("Курс USD/RUB", USD_RUB, "num", "", "usd")
    put("Эквайринг", PAY_FEE, "pct", "", "fee")
    put("УСН", TAX, "pct", "", "tax")
    r += 1
    sec("B. Цены")
    put("Free", PRICE["free"], "num", "", "p0")
    put("Lite", PRICE["lite"], "num", "early — не касса", "p1")
    put("Plus", PRICE["plus"], "num", "касса первых месяцев", "p2")
    put("Pro", PRICE["pro"], "num", "после доверия / decoy", "p3")
    put("Lifetime «до оффера»", LT_PRICE, "num", f"покрывает ~{LT_MONTHS} мес", "plt")
    put("Доля новых pay → Lifetime", LT_SHARE_OF_NEW, "pct", "", "lt_share")
    r += 1
    sec("C. Микс BASE (~4% paid, Plus-heavy)")
    put("Free %", MIX["free"], "pct", "", "mf")
    put("Lite %", MIX["lite"], "pct", "~20% among paid", "ml")
    put("Plus %", MIX["plus"], "pct", "~70% among paid — касса", "mp")
    put("Pro %", MIX["pro"], "pct", "~10% among paid", "mr")
    r += 1
    sec("D. Набор с НУЛЯ (цель 100/мес1)")
    put("Юзеры на старте", USERS0, "int", "должно быть 0", "u0")
    put("Регистраций в мес 1", SIGNUPS_M1, "int", "CPO: иначе нет A/B", "su1")
    put("Рост набора MoM", SIGNUPS_GROWTH, "pct", "", "su_g")
    put("Churn базы", USER_CHURN, "pct", "", "u_ch")
    put("Месяцев soft-launch", SOFT_LAUNCH_MONTHS, "int", "0 = не душить старт", "soft_m")
    put("Коэф soft-launch", SOFT_LAUNCH_FACTOR, "num", "", "soft_f")
    put("Churn платящих", PAY_CHURN, "pct", "нашёл работу → отписка", "p_ch")
    put("Activation signup→act", ACT_RATE, "pct", "не 40% — розовые очки", "act")
    r += 1
    sec("E. LLM (min burn)")
    put("Input $/1M", LLM_IN, "num", "", "lin")
    put("Output $/1M", LLM_OUT, "num", "", "lout")
    put("Cache $/1M", LLM_CACHE, "num", "", "lcache")
    put("Cache hit", CACHE_HIT, "pct", "", "lhit")
    put("Util лимита (paid)", UTIL, "pct", "", "util")
    put("Токены мэтч in", TOK["match"][0], "int", "", "tm_in")
    put("Токены мэтч out", TOK["match"][1], "int", "", "tm_out")
    put("Токены письмо in", TOK["letter"][0], "int", "", "tl_in")
    put("Токены письмо out", TOK["letter"][1], "int", "", "tl_out")
    put("Токены адапт in", TOK["adapt"][0], "int", "", "ta_in")
    put("Токены адапт out", TOK["adapt"][1], "int", "", "ta_out")
    put("Токены TG in", TOK["tg"][0], "int", "", "tt_in")
    put("Токены TG out", TOK["tg"][1], "int", "", "tt_out")
    put("Lite мэтчи", LIMITS["lite"][0], "int", "", "lim_l_m")
    put("Lite письма", LIMITS["lite"][1], "int", "", "lim_l_l")
    put("Lite адаптации", LIMITS["lite"][2], "int", "", "lim_l_a")
    put("Plus мэтчи", LIMITS["plus"][0], "int", "", "lim_p_m")
    put("Plus письма", LIMITS["plus"][1], "int", "", "lim_p_l")
    put("Plus адаптации", LIMITS["plus"][2], "int", "", "lim_p_a")
    put("Pro мэтчи", LIMITS["pro"][0], "int", "", "lim_r_m")
    put("Pro письма", LIMITS["pro"][1], "int", "", "lim_r_l")
    put("Pro адаптации", LIMITS["pro"][2], "int", "", "lim_r_a")
    put("TG постов/день", TG_DAY, "int", "", "tg_d")
    put("Дней в месяце", DAYS, "int", "", "days")
    put("Доля TG в LLM", TG_LLM_SHARE, "pct", "", "tg_share")
    put("LLM ₽ на 1k юзеров сверх", LLM_PER_1K, "num", "", "llm_1k")
    put("WAS доля базы", WAS_OF_USERS, "pct", "", "was")
    put("Месяцев Lifetime", LT_MONTHS, "int", "", "lt_m")
    put("ИП ₽ если выручка ≥ порога", 4200.0, "num", "", "ip_on")
    put("Порог выручки для ИП", 10000.0, "num", "", "ip_gate")
    r += 1
    sec("F. Инфра ступени")
    put("Инфра при 0 юзерах", INFRA_ZERO, "num", "минимальный VPS пока пусто", "i0")
    put("Инфра фаза1", INFRA_P1, "num", f"1…{INFRA_P1_USERS}", "i1")
    put("Порог фазы1", INFRA_P1_USERS, "int", "", "i1u")
    put("Инфра фаза2", INFRA_P2, "num", "", "i2")
    put("Порог фазы2", INFRA_P2_USERS, "int", "", "i2u")
    put("Инфра фаза3", INFRA_P3, "num", "", "i3")
    r += 1
    sec("G. CAC (Y1 органика → Y2 платный)")
    put("Банк", ADM_BANK, "num", "", "bank")
    put("Маркетинг DIY", ADM_MKT, "num", "", "mkt")
    put("CAC год 1", CAC_Y1, "num", "guerrilla / referral", "cac1")
    put("CAC год 2", CAC_Y2, "num", "Директ/VK когда TG выгорит", "cac2")
    put("Referral cut CAC с м.6", REF_CAC_CUT, "pct", "", "ref")
    put("Порог дивиденда EBITDA", FOUNDER_GATE, "num", "", "fgate")
    put("Доля дивиденда", FOUNDER_SHARE, "pct", "", "fshare")
    r += 1
    sec("H. B2B (WAS-порог, агрегаты — не intent-radar)")
    put("B2B цена", B2B_PRICE, "num", "", "b2bp")
    put("B2B мин. месяц", B2B_MIN_MONTH, "int", "", "b2bm")
    put("B2B мин. WAS", B2B_MIN_WAS, "num", "не персональные сигналы", "b2bw")
    put("B2B кап (base)", B2B_CAP, "int", "", "b2bc")
    r += 1
    sec("I. Личный runway")
    put("Личные накопления", PERSONAL_CASH0, "num", "это ТВОИ деньги", "pc0")
    put("Жизнь ₽/мес", PERSONAL_LIVING, "num", "аренда/еда/всё", "plive")
    put("Подработка ₽/мес", SIDE_INCOME, "num", "0 = только накопления", "pside")
    put("Касса бизнеса старт", BUSINESS_CASH0, "num", "", "bc0")
    put("Домен ₽/год", DOMAIN_ANNUAL, "num", "мес 1 и 13", "domain")
    put("Capex мес1 (без домена)", CAPEX1, "num", "", "capex")
    put("Цель платящих", TARGET_PAYING, "int", "", "goal")
    r += 1
    sec("J. Free AI-taste")
    put("Free мэтчи / мес", FREE_LIMITS[0], "int", "письма/адаптация = 0", "f_match")
    put("Free util", FREE_UTIL, "pct", "", "f_util")

    def ib(key: str) -> str:
        return f"Inputs!$B${R[key] + 1}"

    def call_fx(tin_key: str, tout_key: str) -> str:
        return (
            f"(({ib(tin_key)}/1000000)*((1-{ib('lhit')})*{ib('lin')}+{ib('lhit')}*{ib('lcache')})"
            f"+({ib(tout_key)}/1000000)*{ib('lout')})*{ib('usd')}"
        )

    def tier_fx(m_key: str, l_key: str, a_key: str, util_ref: str) -> str:
        return f"({ib(m_key)}*{ib('cm')}+{ib(l_key)}*{ib('cl')}+{ib(a_key)}*{ib('ca')})*{util_ref}"

    r += 2
    ws.write(r, 0, "Считается с Inputs (зелёное) — крути жёлтое", fmt_sec)
    r += 1
    R["cm"] = r
    wf(ws, r, 1, call_fx("tm_in", "tm_out"), cm)
    ws.write(r, 0, "₽ за мэтч")
    r += 1
    R["cl"] = r
    wf(ws, r, 1, call_fx("tl_in", "tl_out"), cl)
    ws.write(r, 0, "₽ за письмо")
    r += 1
    R["ca"] = r
    wf(ws, r, 1, call_fx("ta_in", "ta_out"), ca)
    ws.write(r, 0, "₽ за адаптацию")
    r += 1
    R["ct"] = r
    wf(ws, r, 1, call_fx("tt_in", "tt_out"), ct)
    ws.write(r, 0, "₽ за TG-разбор")
    r += 1
    R["llm_free"] = r
    wf(
        ws,
        r,
        1,
        f"({ib('f_match')}*{ib('cm')}+0*{ib('cl')}+0*{ib('ca')})*{ib('f_util')}",
        llm_free,
    )
    ws.write(r, 0, "LLM Free ₽/юзер/мес")
    r += 1
    R["llm_lite"] = r
    wf(ws, r, 1, f"({ib('lim_l_m')}*{ib('cm')}+{ib('lim_l_l')}*{ib('cl')}+{ib('lim_l_a')}*{ib('ca')})*{ib('util')}", llm_lite)
    ws.write(r, 0, "LLM Lite ₽/мес")
    r += 1
    R["llm_plus"] = r
    wf(ws, r, 1, f"({ib('lim_p_m')}*{ib('cm')}+{ib('lim_p_l')}*{ib('cl')}+{ib('lim_p_a')}*{ib('ca')})*{ib('util')}", llm_plus)
    ws.write(r, 0, "LLM Plus ₽/мес")
    r += 1
    R["llm_pro"] = r
    wf(ws, r, 1, f"({ib('lim_r_m')}*{ib('cm')}+{ib('lim_r_l')}*{ib('cl')}+{ib('lim_r_a')}*{ib('ca')})*{ib('util')}", llm_pro)
    ws.write(r, 0, "LLM Pro ₽/мес")
    r += 1
    R["llm_shared"] = r
    wf(ws, r, 1, f"{ib('tg_d')}*{ib('days')}*{ib('tg_share')}*{ib('ct')}", llm_shared)
    ws.write(r, 0, "LLM shared TG ₽/мес")
    r += 1
    R["pm"] = r
    wf(ws, r, 1, f"{ib('ml')}+{ib('mp')}+{ib('mr')}", pm, "pct")
    ws.write(r, 0, "Доля платящих")
    r += 1
    R["arpu"] = r
    wf(ws, r, 1, f"{ib('mf')}*{ib('p0')}+{ib('ml')}*{ib('p1')}+{ib('mp')}*{ib('p2')}+{ib('mr')}*{ib('p3')}", arpu)
    ws.write(r, 0, "ARPU всех (sub-эквив)")
    r += 1
    R["arpu_pay"] = r
    wf(ws, r, 1, f"IF({ib('pm')}=0,0,({ib('ml')}*{ib('p1')}+{ib('mp')}*{ib('p2')}+{ib('mr')}*{ib('p3')})/{ib('pm')})", arpu_pay)
    ws.write(r, 0, "ARPU платящего")
    r += 1
    R["llm_arpu"] = r
    wf(
        ws,
        r,
        1,
        f"{ib('mf')}*{ib('llm_free')}+{ib('ml')}*{ib('llm_lite')}+{ib('mp')}*{ib('llm_plus')}+{ib('mr')}*{ib('llm_pro')}",
        llm_arpu,
    )
    ws.write(r, 0, "LLM ARPU всех")
    r += 1
    R["llm_on_pay"] = r
    wf(
        ws,
        r,
        1,
        f"IF({ib('pm')}=0,0,({ib('ml')}*{ib('llm_lite')}+{ib('mp')}*{ib('llm_plus')}+{ib('mr')}*{ib('llm_pro')})/{ib('pm')})",
        llm_on_pay,
    )
    ws.write(r, 0, "LLM на платящего")
    r += 1
    R["ltv"] = r
    wf(ws, r, 1, f"IF({ib('p_ch')}=0,0,{ib('arpu_pay')}/{ib('p_ch')})", ltv)
    ws.write(r, 0, "LTV (sub)")
    r += 1
    R["ltv_cac1"] = r
    wf(ws, r, 1, f"IF({ib('cac1')}=0,0,{ib('ltv')}/{ib('cac1')})", ltv / CAC_Y1)
    ws.write(r, 0, "LTV/CAC Y1")
    r += 1
    R["ltv_cac2"] = r
    wf(ws, r, 1, f"IF({ib('cac2')}=0,0,{ib('ltv')}/{ib('cac2')})", ltv / CAC_Y2)
    ws.write(r, 0, "LTV/CAC Y2")
    r += 1
    R["lt_cover"] = r
    wf(ws, r, 1, f"IF({ib('arpu_pay')}=0,0,{ib('plt')}/{ib('arpu_pay')})", LT_PRICE / arpu_pay if arpu_pay else 0)
    ws.write(r, 0, "Lifetime / ARPU_pay (мес)")

    # derived keys cm/cl live on Inputs — ib() works for them too

    # ---- Bootstrap (главный лист для соло) ----
    boot = wb.add_worksheet("Bootstrap")
    boot.set_column("A:A", 42)
    boot.set_column("B:D", 16)
    boot.write(0, 0, "BOOTSTRAP — путь с нуля без инвесторов", fmt_title)
    boot.write(1, 0, "Смотри сюда, если запускаешь один. PnL — детализация тех же цифр.", fmt_note)

    boot.write(3, 0, "Реальность старта", fmt_sec)
    facts = [
        ("Инвесторы", "нет"),
        ("Команда", "1 человек (ты)"),
        ("Юзеры день 0", 0),
        ("Личные накопления", PERSONAL_CASH0),
        ("Жизнь ₽/мес", PERSONAL_LIVING),
        ("Подработка ₽/мес", SIDE_INCOME),
        ("Чистый личный burn ₽/мес", PERSONAL_LIVING - SIDE_INCOME),
        ("Runway месяцев (грубо)", math.floor(PERSONAL_CASH0 / max(1, PERSONAL_LIVING - SIDE_INCOME))),
        ("Месяц первого платящего (base)", base["first_pay_m"] or "—"),
        ("Time-to-100 users (base)", base["hit_100_m"] or "—"),
        ("Месяц 60 платящих (base)", base["hit_60_m"] or "не за 24м"),
        ("Личные деньги кончаются (base)", base["runway_end"] or "хватает на 24м"),
        ("Месяц 60 платящих (opt)", opt["hit_60_m"] or "не за 24м"),
        ("Личные деньги кончаются (pes)", pes["runway_end"] or "хватает на 24м"),
        ("Pes = долина смерти (тихий набор)", f"acq×{SC_PES_ACQ}"),
    ]
    for i, (k, v) in enumerate(facts):
        boot.write(4 + i, 0, k)
        if k == "Личные накопления":
            wf(boot, 4 + i, 1, ib("pc0"), PERSONAL_CASH0)
        elif k == "Жизнь ₽/мес":
            wf(boot, 4 + i, 1, ib("plive"), PERSONAL_LIVING)
        elif k == "Подработка ₽/мес":
            wf(boot, 4 + i, 1, ib("pside"), SIDE_INCOME)
        elif k == "Чистый личный burn ₽/мес":
            wf(boot, 4 + i, 1, f"{ib('plive')}-{ib('pside')}", PERSONAL_LIVING - SIDE_INCOME)
        elif k == "Runway месяцев (грубо)":
            wf(
                boot,
                4 + i,
                1,
                f"IF(({ib('plive')}-{ib('pside')})<=0,99,INT({ib('pc0')}/MAX(1,{ib('plive')}-{ib('pside')})))",
                math.floor(PERSONAL_CASH0 / max(1, PERSONAL_LIVING - SIDE_INCOME)),
                "int",
            )
        else:
            boot.write(4 + i, 1, v, fmt_money if isinstance(v, float) else None)

    boot.write(20, 0, "Что делать руками первые 90 дней", fmt_sec)
    for i, t in enumerate(
        [
            "1. Консьерж: AI-кнопка → TG → 990 на карту. Не жди ЮKassa.",
            "2. Цель 100 regs/мес: TG-чаты + LinkedIn + Habr/VC + build-in-public.",
            "3. Clipper + TG-бот (ссылка→карточка). PDF onboarding → 3 карточки.",
            "4. Касса = Plus 990 + Lifetime 2990. Free = CRM+PDF+taste. Минус = VPS.",
            "5. B2B агрегаты после WAS≳500. Intent/offer-radar — НЕ без спроса владельцу.",
            "6. Personal burn = жизнь − подработка. Следи за м.13.",
        ]
    ):
        boot.write(21 + i, 0, t)

    # monthly bootstrap table
    boot.write(29, 0, "Помесячно BASE", fmt_sec)
    headers = ["Мес", "Signups", "Юзеры", "WAS", "Платящие", "Rev sub", "Rev LT", "Выручка", "EBITDA", "Personal"]
    for c, h in enumerate(headers):
        boot.write(30, c, h, fmt_hdr)
    for s in series:
        row = 30 + s["m"]
        m = s["m"]
        cname = xl_col_to_name(m)
        boot.write(row, 0, s["m"])
        wf(boot, row, 1, f"PnL!{cname}4", s["signups"])
        wf(boot, row, 2, f"PnL!{cname}5", s["users"], "int")
        wf(boot, row, 3, f"PnL!{cname}6", s["was"])
        wf(boot, row, 4, f"PnL!{cname}7", s["pay"])
        wf(boot, row, 5, f"PnL!{cname}8", s["rev_sub"])
        wf(boot, row, 6, f"PnL!{cname}9", s["rev_lt"])
        wf(boot, row, 7, f"PnL!{cname}12", s["rev"])
        wf(boot, row, 8, f"PnL!{cname}23", s["ebitda"])
        fpers = fmt_bad if s["personal_end"] < PERSONAL_LIVING * 3 else fmt_calc
        boot.write_formula(row, 9, f"=CashFlow!{cname}13", fpers, s["personal_end"])

    # ---- PnL ----
    p = wb.add_worksheet("PnL")
    p.set_column("A:A", 28)
    p.write(0, 0, "PnL 24м — Base соло", fmt_title)
    labs = [
        "Месяц",
        "Signups",
        "Юзеры",
        "WAS",
        "Платящие",
        "Выручка sub",
        "Выручка Lifetime",
        "Выручка B2C",
        "Выручка B2B",
        "Выручка всего",
        "Fee+tax",
        "LLM всего",
        "Инфра (серверы)",
        "Домен (год)",
        "Админ",
        "CAC",
        "CAC unit",
        "GM после LLM",
        "EBITDA pre-div",
        "Дивиденд тебе",
        "EBITDA",
        "Маржа",
    ]
    for i, lab in enumerate(labs):
        p.write(2 + i, 0, lab)
    p.write(35, 0, "new_pay (служебное)")
    p.write(36, 0, "new_lt (служебное)")
    p.write(37, 0, "lt_active (служебное)")
    p.write(38, 0, "sub_pay (служебное)")

    for s in series:
        m = s["m"]
        c = m
        col = xl_col_to_name(c)
        prev = xl_col_to_name(c - 1) if m > 1 else None
        p.write(2, c, s["m"], fmt_hdr)

        su_fx = (
            f"{ib('su1')}*(1+{ib('su_g')})^({col}3-1)"
            f"*IF({col}3<={ib('soft_m')},{ib('soft_f')},1)"
        )
        wf(p, 3, c, su_fx, s["signups"])

        if m == 1:
            users_fx = f"{ib('u0')}*(1-{ib('u_ch')})+{col}4"
        else:
            users_fx = f"{prev}5*(1-{ib('u_ch')})+{col}4"
        wf(p, 4, c, users_fx, s["users"], "int")
        wf(p, 5, c, f"{col}5*{ib('was')}", s["was"])
        wf(p, 6, c, f"{col}5*{ib('pm')}", s["pay"])

        if m == 1:
            new_pay_fx = f"{col}7"
        else:
            new_pay_fx = f"MAX(0,{col}7-{prev}7*(1-{ib('p_ch')}))"
        wf(p, 35, c, new_pay_fx, s["new_pay"])
        wf(p, 36, c, f"{col}36*{ib('lt_share')}", s["new_lt"])
        start_lt = max(1, m - LT_MONTHS + 1)
        lt_fx = (
            f"SUM(INDEX($B$37:$Y$37,1,MAX(1,{col}3-{ib('lt_m')}+1))"
            f":INDEX($B$37:$Y$37,1,{col}3))"
        )
        wf(p, 37, c, lt_fx, s["lt_active"])
        wf(p, 38, c, f"MAX(0,{col}7-{col}38)", s["sub_pay"])

        wf(p, 7, c, f"{col}39*{ib('arpu_pay')}", s["rev_sub"])
        wf(p, 8, c, f"{col}37*{ib('plt')}", s["rev_lt"])
        wf(p, 9, c, f"{col}8+{col}9", s["rev_b2c"])
        b2b_fx = (
            f"IF(OR({col}3<{ib('b2bm')},{col}6<{ib('b2bw')}),0,"
            f"MIN({ib('b2bc')},1+INT(({col}3-{ib('b2bm')})/3)))*{ib('b2bp')}"
        )
        wf(p, 10, c, b2b_fx, s["rev_b2b"])
        wf(p, 11, c, f"{col}10+{col}11", s["rev"])
        wf(p, 12, c, f"{col}12*({ib('fee')}+{ib('tax')})", s["fee_tax"])
        wf(
            p,
            13,
            c,
            f"{col}5*{ib('llm_arpu')}+{ib('llm_shared')}+{col}5/1000*{ib('llm_1k')}",
            s["llm"],
        )
        infra_fx = (
            f"IF({col}5<=0,{ib('i0')},IF({col}5<={ib('i1u')},{ib('i1')},"
            f"IF({col}5<={ib('i2u')},{ib('i2')},{ib('i3')})))"
        )
        wf(p, 14, c, infra_fx, s["infra"])
        wf(p, 15, c, f"IF(OR({col}3=1,AND({col}3>1,MOD({col}3-1,12)=0)),{ib('domain')},0)", s["domain"])
        wf(p, 16, c, f"IF({col}12>={ib('ip_gate')},{ib('ip_on')},0)+{ib('bank')}+{ib('mkt')}", s["adm"])
        cac_unit_fx = f"IF({col}3<=12,{ib('cac1')},{ib('cac2')})*IF({col}3>=6,1-{ib('ref')},1)"
        wf(p, 18, c, cac_unit_fx, s["cac_unit"])
        wf(p, 17, c, f"{col}36*{col}19*IF({col}3=1,0.5,1)", s["cac"])
        wf(p, 19, c, f"{col}12-{col}13-{col}14", s["gm_after_llm"])
        wf(p, 20, c, f"{col}12-{col}13-{col}14-{col}15-{col}17-{col}18-{col}16", s["ebitda_pre"])
        wf(
            p,
            21,
            c,
            f"IF({col}21>{ib('fgate')},MAX(0,{ib('fshare')}*({col}21-{ib('fgate')})),0)",
            s["founder"],
        )
        wf(p, 22, c, f"{col}21-{col}22", s["ebitda"])
        wf(p, 23, c, f"IF({col}12=0,0,{col}23/{col}12)", s["margin"], "pct")
        p.set_column(c, c, 11)

    p.write(25, 0, "Сумма выручки 24м")
    wf(p, 25, 1, "SUM(B12:Y12)", base["rev24"])
    p.write(26, 0, "Сумма Lifetime 24м")
    wf(p, 26, 1, "SUM(B9:Y9)", base["rev_lt24"])
    p.write(27, 0, "Сумма LLM 24м")
    wf(p, 27, 1, "SUM(B14:Y14)", base["llm24"])
    p.write(28, 0, "Сумма инфра 24м")
    wf(p, 28, 1, "SUM(B15:Y15)", base["infra24"])
    p.write(29, 0, "Сумма CAC 24м")
    wf(p, 29, 1, "SUM(B18:Y18)", base["cac24"])
    p.write(30, 0, "Сумма EBITDA 24м")
    wf(p, 30, 1, "SUM(B23:Y23)", base["ebitda24"])
    p.write(31, 0, "Дивиденд тебе 24м")
    wf(p, 31, 1, "SUM(B22:Y22)", base["founder24"])
    p.write(32, 0, "Угроза = Personal runway + медленный набор (см. Pes), не LLM", fmt_note)

    # ---- CashFlow (две кассы) ----
    cf = wb.add_worksheet("CashFlow")
    cf.set_column("A:A", 28)
    cf.write(0, 0, "Две кассы: Business + Personal", fmt_title)
    labs = ["Мес", "Biz начало", "EBITDA", "Capex", "Bailout из личного", "Biz конец", "Personal начало", "Жизнь", "Подработка", "Дивиденд", "Personal конец"]
    for i, lab in enumerate(labs):
        cf.write(2 + i, 0, lab)
    for s in series:
        m = s["m"]
        c = m
        col = xl_col_to_name(c)
        prev = xl_col_to_name(c - 1) if m > 1 else None
        cf.write(2, c, s["m"], fmt_hdr)
        if m == 1:
            biz_start_fx = ib("bc0")
            pers_start_fx = ib("pc0")
        else:
            biz_start_fx = f"{prev}8"
            pers_start_fx = f"{prev}13"
        wf(cf, 3, c, biz_start_fx, s["biz_start"])
        wf(cf, 4, c, f"PnL!{col}23", s["ebitda"])
        wf(cf, 5, c, f"IF({col}3=1,{ib('capex')},0)", s["capex"])
        wf(cf, 6, c, f"MAX(0,-({col}4+{col}5-{col}6))", s["bailout"])
        wf(cf, 7, c, f"MAX(0,{col}4+{col}5-{col}6)", s["biz_end"])
        wf(cf, 8, c, pers_start_fx, s["personal_start"])
        wf(cf, 9, c, ib("plive"), s["living"])
        wf(cf, 10, c, ib("pside"), s["side"])
        wf(cf, 11, c, f"PnL!{col}22", s["founder"])
        wf(cf, 12, c, f"{col}9-{col}10+{col}11+{col}12-{col}7", s["personal_end"])
        cf.set_column(c, c, 11)

    # ---- Scenarios ----
    sc = wb.add_worksheet("Scenarios")
    sc.set_column("A:A", 40)
    sc.set_column("B:D", 16)
    sc.write(0, 0, "Base / Optimistic / Pessimistic — соло", fmt_title)
    for i, h in enumerate(["", "Base", "Optimistic", "Pessimistic"]):
        if i:
            sc.write(2, i, h, fmt_hdr)
    scs = [base, opt, pes]
    rows = [
        ("ARPU sub-эквив", lambda s: s["arpu"]),
        ("Платящих %", lambda s: s["pm"]),
        ("Time-to-100 users", lambda s: s["hit_100_m"] or 0),
        ("Мес. первого платящего", lambda s: s["first_pay_m"] or 0),
        ("Мес. 60 платящих", lambda s: s["hit_60_m"] or 0),
        ("Личные ₽ кончаются в мес.", lambda s: s["runway_end"] or 0),
        ("Юзеры мес12", lambda s: s["rows"][11]["users"], "PnL!L5"),
        ("WAS мес12", lambda s: s["rows"][11]["was"], "PnL!L6"),
        ("Платящие мес12", lambda s: s["rows"][11]["pay"], "PnL!L7"),
        ("Выручка мес12", lambda s: s["rows"][11]["rev"], "PnL!L12"),
        ("Lifetime мес12", lambda s: s["rows"][11]["rev_lt"], "PnL!L9"),
        ("EBITDA мес12", lambda s: s["rows"][11]["ebitda"], "PnL!L23"),
        ("Personal конец мес12", lambda s: s["rows"][11]["personal_end"], "CashFlow!L13"),
        ("Юзеры мес24", lambda s: s["rows"][23]["users"], "PnL!Y5"),
        ("Платящие мес24", lambda s: s["rows"][23]["pay"], "PnL!Y7"),
        ("Выручка мес24", lambda s: s["rows"][23]["rev"], "PnL!Y12"),
        ("EBITDA мес24", lambda s: s["rows"][23]["ebitda"], "PnL!Y23"),
        ("Personal конец мес24", lambda s: s["rows"][23]["personal_end"], "CashFlow!Y13"),
        ("Выручка сумм 24м", lambda s: s["rev24"], "PnL!B26"),
        ("Lifetime сумм 24м", lambda s: s["rev_lt24"], "PnL!B27"),
        ("LLM сумм 24м", lambda s: s["llm24"], "PnL!B28"),
        ("Инфра сумм 24м", lambda s: s["infra24"], "PnL!B29"),
        ("EBITDA сумм 24м", lambda s: s["ebitda24"], "PnL!B31"),
    ]
    for i, row in enumerate(rows):
        lab, fn, *rest = row
        fx = rest[0] if rest else None
        sc.write(3 + i, 0, lab)
        for col, s in enumerate(scs, start=1):
            v = fn(s)
            if fx and col == 1:
                wf(sc, 3 + i, col, fx, v, "pct" if "Платящих %" in lab else "num")
            else:
                sc.write(3 + i, col, v, fmt_calc_pct if "Платящих %" in lab else fmt_calc)

    sc.write(27, 0, "Base=guerrilla 100/м1. Opt=Habr×2. Pes=тихий набор (долина смерти). Lifetime + CAC Y2 вшиты.", fmt_note)

    ch = wb.add_chart({"type": "column"})
    ch.add_series({"name": "Выручка м12", "categories": ["Scenarios", 2, 1, 2, 3], "values": ["Scenarios", 12, 1, 12, 3], "fill": {"color": "#0D7377"}})
    ch.add_series({"name": "EBITDA м12", "categories": ["Scenarios", 2, 1, 2, 3], "values": ["Scenarios", 14, 1, 14, 3], "fill": {"color": "#E85D04"}})
    ch.set_title({"name": "Мес 12"})
    ch.set_size({"width": 720, "height": 360})
    sc.insert_chart("A29", ch)

    # ---- Charts ----
    charts = wb.add_worksheet("Charts")
    charts.write(0, 0, "Графики соло-запуска", fmt_title)

    def line(name, sheet, row, color):
        c = wb.add_chart({"type": "line"})
        c.add_series(
            {
                "name": name,
                "categories": [sheet, 2, 1, 2, 24],
                "values": [sheet, row, 1, row, 24],
                "line": {"color": color, "width": 2.5},
                "marker": {"type": "circle", "size": 4},
            }
        )
        c.set_size({"width": 720, "height": 340})
        return c

    # PnL: 4 users, 6 pay, 11 rev, 13 llm, 14 infra, 19 gm, 22 ebitda
    c1 = wb.add_chart({"type": "line"})
    for name, row, colr in [("Юзеры", 4, "#1F4E79"), ("Платящие", 6, "#2A9D8F")]:
        c1.add_series({"name": name, "categories": ["PnL", 2, 1, 2, 24], "values": ["PnL", row, 1, row, 24], "line": {"color": colr, "width": 2.5}})
    c1.set_title({"name": "Набор с нуля"})
    c1.set_size({"width": 720, "height": 340})
    charts.insert_chart("A3", c1)

    c2 = wb.add_chart({"type": "line"})
    for name, row, colr in [("Выручка", 11, "#0D7377"), ("EBITDA", 22, "#E85D04")]:
        c2.add_series({"name": name, "categories": ["PnL", 2, 1, 2, 24], "values": ["PnL", row, 1, row, 24], "line": {"color": colr, "width": 2.5}})
    c2.set_title({"name": "Выручка и EBITDA"})
    c2.set_size({"width": 720, "height": 340})
    charts.insert_chart("M3", c2)

    c3 = wb.add_chart({"type": "area"})
    c3.add_series(
        {
            "name": "Personal cash",
            "categories": ["CashFlow", 2, 1, 2, 24],
            "values": ["CashFlow", 12, 1, 12, 24],
            "fill": {"color": "#6D597A", "transparency": 35},
            "line": {"color": "#6D597A"},
        }
    )
    c3.set_title({"name": "Личный runway (главный риск соло)"})
    c3.set_size({"width": 720, "height": 340})
    charts.insert_chart("A22", c3)

    c4 = wb.add_chart({"type": "line"})
    c4.add_series(
        {
            "name": "Biz cash",
            "categories": ["CashFlow", 2, 1, 2, 24],
            "values": ["CashFlow", 7, 1, 7, 24],
            "line": {"color": "#0D7377", "width": 2.5},
        }
    )
    c4.set_title({"name": "Касса бизнеса"})
    c4.set_size({"width": 720, "height": 340})
    charts.insert_chart("M22", c4)

    c_llm = wb.add_chart({"type": "line"})
    for name, row, colr in [("LLM", 13, "#9B5DE5"), ("Инфра (серверы)", 14, "#E85D04"), ("GM после LLM", 19, "#2A9D8F")]:
        c_llm.add_series({"name": name, "categories": ["PnL", 2, 1, 2, 24], "values": ["PnL", row, 1, row, 24], "line": {"color": colr, "width": 2.5}})
    c_llm.set_title({"name": "LLM vs серверы (минус = инфра)"})
    c_llm.set_size({"width": 720, "height": 340})
    charts.insert_chart("A40", c_llm)

    # ---- Unit ----
    u = wb.add_worksheet("Unit")
    u.set_column("A:A", 44)
    u.set_column("B:B", 14)
    u.write(0, 0, "Unit — LLM ок; угроза = набор + CAC Y2", fmt_title)
    u.write(2, 0, "ARPU платящего (sub)")
    wf(u, 2, 1, ib("arpu_pay"), arpu_pay)
    u.write(3, 0, "Lifetime")
    wf(u, 3, 1, ib("plt"), LT_PRICE)
    u.write(4, 0, "LLM на платящего ₽/мес")
    wf(u, 4, 1, ib("llm_on_pay"), llm_on_pay)
    u.write(5, 0, "Запас sub после LLM")
    wf(u, 5, 1, f"{ib('arpu_pay')}-{ib('llm_on_pay')}", arpu_pay - llm_on_pay)
    u.write(6, 0, "LLM Free (taste)")
    wf(u, 6, 1, ib("llm_free"), llm_free)
    u.write(8, 0, "LTV (sub)")
    wf(u, 8, 1, ib("ltv"), ltv)
    u.write(9, 0, "CAC Y1 / Y2")
    wf(u, 9, 1, ib("cac1"), CAC_Y1)
    wf(u, 9, 2, ib("cac2"), CAC_Y2)
    u.write(10, 0, "LTV/CAC Y1")
    wf(u, 10, 1, ib("ltv_cac1"), ltv / CAC_Y1)
    u.write(11, 0, "LTV/CAC Y2 (без referral)")
    wf(u, 11, 1, ib("ltv_cac2"), ltv / CAC_Y2)
    u.write(12, 0, "LTV/CAC Y2 с referral")
    wf(u, 12, 1, f"IF({ib('cac2')}*(1-{ib('ref')})=0,0,{ib('ltv')}/({ib('cac2')}*(1-{ib('ref')})))", ltv / (CAC_Y2 * (1 - REF_CAC_CUT)))
    u.write(14, 0, "Payback Y1 ≈ CAC / (ARPU×(1-fee-tax))")
    wf(u, 14, 1, f"{ib('cac1')}/({ib('arpu_pay')}*(1-{ib('fee')}-{ib('tax')}))", CAC_Y1 / (arpu_pay * (1 - PAY_FEE - TAX)))
    u.write(16, 0, "Сумма 24м: LLM / инфра / Lifetime")
    wf(u, 16, 1, "PnL!B28", base["llm24"])
    wf(u, 16, 2, "PnL!B29", base["infra24"])
    wf(u, 16, 3, "PnL!B27", base["rev_lt24"])
    u.write(18, 0, "Вывод: математика бьётся. Выживание = 100 regs/мес + Plus/LT + Personal.", fmt_note)

    # ---- Dashboard ----
    dash = wb.add_worksheet("Dashboard")
    dash.set_column("A:A", 44)
    dash.set_column("B:D", 16)
    dash.write(0, 0, "DASHBOARD — соло-бутстрап", fmt_title)
    dash.write(1, 0, "Нет инвесторов. Нет команды. Старт с 0. Открой Bootstrap для помесячки.", fmt_warn)

    snap = [
        ("Режим", "solo + guerrilla GTM"),
        ("Цены", "490 / 990(+LT 2990) / 1990"),
        ("Платящих (base)", f"{pm:.0%} Plus-heavy"),
        ("Activation model", f"{ACT_RATE:.0%}"),
        ("Signups мес1", SIGNUPS_M1),
        ("Time-to-100", base["hit_100_m"]),
        ("North Star", "WAS"),
        ("ARPU pay / LT", f"{arpu_pay:.0f} / {LT_PRICE:.0f}"),
        ("LLM Free / на pay", f"{llm_free:.2f} / {llm_on_pay:.2f}"),
        ("LTV/CAC Y1 / Y2", f"{ltv/CAC_Y1:.1f} / {ltv/CAC_Y2:.1f}"),
        ("Lifetime 24м", round(base["rev_lt24"], 0)),
        ("Личный burn", PERSONAL_LIVING - SIDE_INCOME),
        ("Runway мес (грубо)", math.floor(PERSONAL_CASH0 / max(1, PERSONAL_LIVING - SIDE_INCOME))),
        ("Мес → 60 pay", base["hit_60_m"] or "нет за 24м"),
        ("Personal dry", base["runway_end"] or "нет"),
        ("Выручка мес6", round(series[5]["rev"], 0)),
        ("EBITDA мес6", round(series[5]["ebitda"], 0)),
        ("Платящие мес6", round(series[5]["pay"], 1)),
        ("Выручка мес12", round(series[11]["rev"], 0)),
        ("EBITDA мес12", round(series[11]["ebitda"], 0)),
        ("WAS мес12", round(series[11]["was"], 0)),
        ("Personal мес12", round(series[11]["personal_end"], 0)),
        ("Выручка мес24", round(series[23]["rev"], 0)),
        ("EBITDA мес24", round(series[23]["ebitda"], 0)),
        ("Personal мес24", round(series[23]["personal_end"], 0)),
    ]
    for i, (k, v) in enumerate(snap):
        dash.write(3 + i, 0, k)
        dash.write(3 + i, 1, v, fmt_money if isinstance(v, float) else None)

    dash.write(3, 2, "Сценарий")
    dash.write(3, 3, "60 payers")
    dash.write(3, 4, "Personal dry")
    for i, (name, s) in enumerate([("Base", base), ("Opt", opt), ("Pes", pes)]):
        dash.write(4 + i, 2, name)
        dash.write(4 + i, 3, s["hit_60_m"] or "—")
        dash.write(4 + i, 4, s["runway_end"] or "ok")

    dash.write(32, 0, "Крути на Inputs: Signups мес1, жизнь ₽/мес, личные накопления — это твои реальные рычаги.", fmt_note)

    # ---- Infra note ----
    ir = wb.add_worksheet("InfraRoadmap")
    ir.set_column("A:A", 70)
    ir.write(0, 0, "Инфра соло", fmt_title)
    ir.write(2, 0, f"0 юзеров: {INFRA_ZERO:.0f} ₽ (минимальный VPS)")
    ir.write(3, 0, f"1–{INFRA_P1_USERS}: {INFRA_P1:.0f} ₽")
    ir.write(4, 0, f"{INFRA_P1_USERS}–{INFRA_P2_USERS}: {INFRA_P2:.0f} ₽")
    ir.write(5, 0, f">{INFRA_P2_USERS}: {INFRA_P3:.0f} ₽")
    ir.write(7, 0, f"Домен ≈ {DOMAIN_ANNUAL:.0f} ₽/год (мес 1 и 13 в PnL), не дроби на 12 в инфру.")
    ir.write(8, 0, "Clipper у юзеров = proxy 0. Один ты — не строй HighLoad заранее.", fmt_note)
    ir.write(9, 0, "Минус на старте ≈ эта таблица + CAC/админ. GLM при taste+paid — копейки.", fmt_note)

    wb.close()
    ascii_out = OUT.with_name("HuntOS_finmodel.xlsx")
    ascii_out.write_bytes(OUT.read_bytes())
    print("OK", OUT)
    print(
        f"hit100={base['hit_100_m']} first_pay={base['first_pay_m']} hit60={base['hit_60_m']} "
        f"runway_end={base['runway_end']} m1_su={series[0]['signups']:.0f} "
        f"m12_pay={series[11]['pay']:.1f} m12_rev={series[11]['rev']:.0f} "
        f"m12_lt={series[11]['rev_lt']:.0f} m12_pers={series[11]['personal_end']:.0f} "
        f"lt24={base['rev_lt24']:.0f}"
    )
    print(f"opt60={opt['hit_60_m']} pes60={pes['hit_60_m']} pes_dry={pes['runway_end']} pes_m1={pes['rows'][0]['signups']:.1f}")


if __name__ == "__main__":
    main()
