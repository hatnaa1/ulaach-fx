from __future__ import annotations

import datetime
import html
import os
from decimal import Decimal
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from platform_routes import (
    _aqi_badge,
    _ww_text,
    extract_visitor_info,
    fetch_weather_hub_data,
    render_portal_page,
    render_tool_page,
    render_weather_page,
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://fx_reader:fx_read_only_2026_u@wx-postgres:5432/fx",
)
WEATHER_DATABASE_URL = os.environ.get(
    "WEATHER_DATABASE_URL",
    DATABASE_URL.rsplit("/", 1)[0] + "/weather",
)

UB_TZ = datetime.timezone(datetime.timedelta(hours=8))

# Монголбанкны 38 валютын албан дараалал ба 5 хэлний нэршил (MN, EN, CN, JP, KR)
CURRENCY_ORDER: list[str] = [
    "USD", "EUR", "JPY", "CHF", "SEK", "GBP", "BGN", "HUF", "EGP", "INR",
    "HKD", "RUB", "KZT", "CNY", "KRW", "KPW", "CAD", "AUD", "CZK", "TWD",
    "THB", "IDR", "MYR", "SGD", "AED", "KWD", "NZD", "DKK", "PLN", "UAH",
    "NOK", "NPR", "ZAR", "TRY", "VND", "XAU", "XAG", "SDR",
]

CURRENCY_I18N: dict[str, dict[str, str]] = {
    "USD": {"MN": "АНУ-ын доллар", "EN": "US Dollar", "CN": "美元", "JP": "米ドル", "KR": "미국 달러"},
    "EUR": {"MN": "Евро", "EN": "Euro", "CN": "欧元", "JP": "ユーロ", "KR": "유로"},
    "JPY": {"MN": "Японы иен", "EN": "Japanese Yen", "CN": "日元", "JP": "日本円", "KR": "일본 엔"},
    "CHF": {"MN": "Швейцарийн франк", "EN": "Swiss Franc", "CN": "瑞士法郎", "JP": "スイスフラン", "KR": "스위스 프랑"},
    "SEK": {"MN": "Шведийн крон", "EN": "Swedish Krona", "CN": "瑞典克朗", "JP": "スウェーデンクローナ", "KR": "스웨덴 크로나"},
    "GBP": {"MN": "Английн фунт", "EN": "British Pound", "CN": "英镑", "JP": "英ポンド", "KR": "영국 파운드"},
    "BGN": {"MN": "Болгарын лев", "EN": "Bulgarian Lev", "CN": "保加利亚列弗", "JP": "ブルガリアレフ", "KR": "불가리아 레프"},
    "HUF": {"MN": "Унгарын форинт", "EN": "Hungarian Forint", "CN": "匈牙利福林", "JP": "ハンガリーフォリント", "KR": "헝га리 포린트"},
    "EGP": {"MN": "Египетийн фунт", "EN": "Egyptian Pound", "CN": "埃及镑", "JP": "エジプトポンド", "KR": "이집트 파운드"},
    "INR": {"MN": "Энэтхэгийн рупи", "EN": "Indian Rupee", "CN": "印度卢比", "JP": "インドルピー", "KR": "인도 루피"},
    "HKD": {"MN": "Хонконгийн доллар", "EN": "Hong Kong Dollar", "CN": "港元", "JP": "香港ドル", "KR": "홍콩 달러"},
    "RUB": {"MN": "ОХУ-ын рубль", "EN": "Russian Ruble", "CN": "俄罗斯卢布", "JP": "ロシアルーブル", "KR": "러시아 루블"},
    "KZT": {"MN": "Казахстаны тэнгэ", "EN": "Kazakhstani Tenge", "CN": "哈萨克斯坦坚戈", "JP": "カザフスタンテンゲ", "KR": "카자흐스탄 텡게"},
    "CNY": {"MN": "БНХАУ-ын юань", "EN": "Chinese Yuan", "CN": "人民币", "JP": "中国人民元", "KR": "중국 위안"},
    "KRW": {"MN": "БНСУ-ын вон", "EN": "South Korean Won", "CN": "韩元", "JP": "韓国ウォン", "KR": "대한민국 원"},
    "KPW": {"MN": "БНАСАУ-ын вон", "EN": "North Korean Won", "CN": "朝鲜圆", "JP": "北朝鮮ウォン", "KR": "북한 원"},
    "CAD": {"MN": "Канадын доллар", "EN": "Canadian Dollar", "CN": "加元", "JP": "カナダドル", "KR": "캐나다 달러"},
    "AUD": {"MN": "Австралийн доллар", "EN": "Australian Dollar", "CN": "澳元", "JP": "豪ドル", "KR": "호주 달러"},
    "CZK": {"MN": "Чехийн крон", "EN": "Czech Koruna", "CN": "捷克克朗", "JP": "チェココルナ", "KR": "체코 코루나"},
    "TWD": {"MN": "Тайванийн доллар", "EN": "Taiwan Dollar", "CN": "新台币", "JP": "台湾ドル", "KR": "대만 달러"},
    "THB": {"MN": "Тайландын бат", "EN": "Thai Baht", "CN": "泰铢", "JP": "タイバーツ", "KR": "태국 바트"},
    "IDR": {"MN": "Индонезийн рупи", "EN": "Indonesian Rupiah", "CN": "印尼盾", "JP": "インドネシアルピア", "KR": "인도네시아 루피아"},
    "MYR": {"MN": "Малайзын ринггит", "EN": "Malaysian Ringgit", "CN": "马来西亚林吉特", "JP": "マレーシアリンギット", "KR": "말레이시아 링깃"},
    "SGD": {"MN": "Сингапурын доллар", "EN": "Singapore Dollar", "CN": "新加坡元", "JP": "シンガポールドル", "KR": "싱가포르 달러"},
    "AED": {"MN": "АНЭУ-ын дирхам", "EN": "UAE Dirham", "CN": "阿联酋迪拉姆", "JP": "UAEディルハム", "KR": "아랍에미리트 디르함"},
    "KWD": {"MN": "Кувейтийн динар", "EN": "Kuwaiti Dinar", "CN": "科威特第纳尔", "JP": "クウェートディナール", "KR": "쿠웨이트 디나르"},
    "NZD": {"MN": "Шинэ Зеландын доллар", "EN": "New Zealand Dollar", "CN": "新西兰元", "JP": "NZドル", "KR": "뉴질랜드 달러"},
    "DKK": {"MN": "Данийн крон", "EN": "Danish Krone", "CN": "丹麦克朗", "JP": "デンマーククローネ", "KR": "덴마크 크로네"},
    "PLN": {"MN": "Польшийн злот", "EN": "Polish Zloty", "CN": "波兰兹罗提", "JP": "ポーランドズウォティ", "KR": "폴란드 즐로티"},
    "UAH": {"MN": "Украины гривн", "EN": "Ukrainian Hryvnia", "CN": "乌克兰格里夫纳", "JP": "ウクライナフリヴニャ", "KR": "우크라이나 그리브나"},
    "NOK": {"MN": "Норвегийн крон", "EN": "Norwegian Krone", "CN": "挪威克朗", "JP": "ノルウェークローネ", "KR": "노르웨이 크로네"},
    "NPR": {"MN": "Непалын рупи", "EN": "Nepalese Rupee", "CN": "尼泊尔卢比", "JP": "ネパールルピー", "KR": "네팔 루피"},
    "ZAR": {"MN": "Өмнөд Африкийн ранд", "EN": "South African Rand", "CN": "南非兰特", "JP": "南アフリカランド", "KR": "남아공 랜드"},
    "TRY": {"MN": "Туркийн лира", "EN": "Turkish Lira", "CN": "土耳其里拉", "JP": "トルコリラ", "KR": "튀르키예 리라"},
    "VND": {"MN": "Вьетнамын донг", "EN": "Vietnamese Dong", "CN": "越南盾", "JP": "ベトナムドン", "KR": "베트남 동"},
    "XAU": {"MN": "Алт /унцаар/", "EN": "Gold (troy oz)", "CN": "黄金 (盎司)", "JP": "金 (トロイオンス)", "KR": "금 (트로이온스)"},
    "XAG": {"MN": "Мөнгө /унцаар/", "EN": "Silver (troy oz)", "CN": "白银 (盎司)", "JP": "銀 (トロイオンス)", "KR": "은 (트로이온스)"},
    "SDR": {"MN": "Зээлжих тусгай эрх", "EN": "Special Drawing Rights", "CN": "特别提款权", "JP": "特別引出権 (SDR)", "KR": "특별인출권 (SDR)"},
}

WIDGET_I18N: dict[str, dict[str, str]] = {
    "MN": {
        "title": "Валютын ханш",
        "col_cur": "Валют",
        "col_rate": "Албан ханш",
        "conv_title": "Ханш хөрвүүлэгч",
        "mnt_label": "MNT ₮",
        "source_label": "Эх сурвалж:",
        "source_name": "Монголбанк",
    },
    "EN": {
        "title": "Exchange Rates",
        "col_cur": "Currency",
        "col_rate": "Official Rate",
        "conv_title": "Converter",
        "mnt_label": "MNT ₮",
        "source_label": "Source:",
        "source_name": "Bank of Mongolia",
    },
    "CN": {
        "title": "官方汇率",
        "col_cur": "货币",
        "col_rate": "官方汇率 (₮)",
        "conv_title": "汇率换算",
        "mnt_label": "图格里克 ₮",
        "source_label": "数据来源:",
        "source_name": "蒙古银行",
    },
    "JP": {
        "title": "為替レート",
        "col_cur": "通貨",
        "col_rate": "公定レート (₮)",
        "conv_title": "通貨換算",
        "mnt_label": "トゥグルグ ₮",
        "source_label": "出典:",
        "source_name": "モンゴル銀行",
    },
    "KR": {
        "title": "공식 환율",
        "col_cur": "통화",
        "col_rate": "기준 환율 (₮)",
        "conv_title": "환율 계산기",
        "mnt_label": "투그릭 ₮",
        "source_label": "출처:",
        "source_name": "몽골은행",
    },
}

CURRENCY_NAMES: dict[str, str] = {k: v["MN"] for k, v in CURRENCY_I18N.items()}
CURRENCY_RANK: dict[str, int] = {code: idx for idx, code in enumerate(CURRENCY_ORDER)}

BANK_NAMES_MN: dict[str, str] = {
    "Khaan": "Хаан банк",
    "Golomt": "Голомт банк",
    "TDB": "Худалдаа хөгжлийн банк",
}

app = FastAPI(
    title="Ulaach FX — Монголбанк ба Арилжааны банкны ханшийн сервис",
    version="1.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)

os.makedirs("/app/static/img", exist_ok=True)
app.mount("/img", StaticFiles(directory="/app/static/img"), name="img")

_pool: asyncpg.Pool | None = None
_wx_pool: asyncpg.Pool | None = None


@app.on_event("startup")
async def _startup() -> None:
    global _pool, _wx_pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=8, command_timeout=10)
    _wx_pool = await asyncpg.create_pool(WEATHER_DATABASE_URL, min_size=1, max_size=6, command_timeout=10)


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _pool, _wx_pool
    if _pool is not None:
        await _pool.close()
        _pool = None
    if _wx_pool is not None:
        await _wx_pool.close()
        _wx_pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=8, command_timeout=10)
    return _pool


async def get_wx_pool() -> asyncpg.Pool:
    global _wx_pool
    if _wx_pool is None:
        _wx_pool = await asyncpg.create_pool(WEATHER_DATABASE_URL, min_size=1, max_size=6, command_timeout=10)
    return _wx_pool


def _fmt_rate(val: Decimal | float | None) -> str:
    if val is None:
        return "0.00"
    d = Decimal(str(val))
    return f"{d:,.2f}"


def _to_float(val: Decimal | float | None) -> float | None:
    if val is None:
        return None
    return round(float(val), 4)


def _fmt_ub_dt(dt: datetime.datetime | None) -> str:
    if dt is None:
        return datetime.datetime.now(UB_TZ).strftime("%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(UB_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _parse_currencies(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = [p.strip().upper() for p in raw.replace(",", "|").split("|")]
    return [p for p in parts if p]


def _norm_lang(raw: str | None) -> str:
    if not raw:
        return "MN"
    s = raw.strip().upper()
    alias = {"KO": "KR", "JA": "JP", "ZH": "CN", "MNG": "MN", "ENG": "EN"}
    s = alias.get(s, s)
    return s if s in WIDGET_I18N else "MN"


def _cur_name(code: str, lang: str = "MN") -> str:
    meta = CURRENCY_I18N.get(code)
    if not meta:
        return code
    return meta.get(lang) or meta["MN"]


def _parse_date_param(raw: str | None) -> datetime.date | None:
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Огнооны формат буруу байна: {s} (YYYY-MM-DD байх ёстой)")


async def _fetch_mnb_for_date(target_date: datetime.date | None, lang: str = "MN") -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if target_date is None:
            row = await conn.fetchrow("SELECT MAX(rate_date) AS max_date FROM mnb_rates")
            eff_date = row["max_date"] if row and row["max_date"] else datetime.date.today()
        else:
            row = await conn.fetchrow(
                "SELECT MAX(rate_date) AS max_date FROM mnb_rates WHERE rate_date <= $1",
                target_date,
            )
            eff_date = row["max_date"]
            if eff_date is None:
                row_min = await conn.fetchrow("SELECT MIN(rate_date) AS min_date FROM mnb_rates")
                eff_date = row_min["min_date"] if row_min and row_min["min_date"] else target_date

        rows = await conn.fetch(
            "SELECT code, rate, rate_date, fetched_at FROM mnb_rates WHERE rate_date = $1",
            eff_date,
        )

    items: list[dict[str, Any]] = []
    for r in rows:
        code = str(r["code"]).strip().upper()
        rate_dec = Decimal(str(r["rate"])) if r["rate"] is not None else Decimal("0")
        items.append(
            {
                "code": code,
                "last_date": _fmt_ub_dt(r["fetched_at"]),
                "name": _cur_name(code, lang),
                "rate": _fmt_rate(rate_dec),
                "rate_date": r["rate_date"].isoformat(),
                "rate_float": round(float(rate_dec), 4),
            }
        )
    items.sort(key=lambda x: CURRENCY_RANK.get(x["code"], 999))
    return items


@app.get("/health")
async def health() -> dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        mnb_row = await conn.fetchrow(
            "SELECT MIN(rate_date) AS min_d, MAX(rate_date) AS max_d, COUNT(*) AS cnt FROM mnb_rates"
        )
        bank_row = await conn.fetchrow(
            "SELECT MIN(rate_hour) AS min_h, MAX(rate_hour) AS max_h, COUNT(*) AS cnt FROM bank_rates"
        )
    return {
        "status": "ok",
        "mnb_rates": {
            "min_date": mnb_row["min_d"].isoformat() if mnb_row["min_d"] else None,
            "max_date": mnb_row["max_d"].isoformat() if mnb_row["max_d"] else None,
            "total_rows": mnb_row["cnt"],
        },
        "bank_rates": {
            "min_hour": _fmt_ub_dt(bank_row["min_h"]) if bank_row["min_h"] else None,
            "max_hour": _fmt_ub_dt(bank_row["max_h"]) if bank_row["max_h"] else None,
            "total_rows": bank_row["cnt"],
        },
    }


@app.get("/xansh.json")
@app.get("/api/v1/mnb")
async def xansh_json(
    currency: str | None = Query(None, description="Валютын кодууд: USD|EUR|CNY"),
    date: str | None = Query(None, description="Түүхэн огноо: YYYY-MM-DD"),
    rate_date: str | None = Query(None, description="Түүхэн огноо: YYYY-MM-DD (alias)"),
    lang: str | None = Query("MN", description="Хэл: MN | EN | CN | JP | KR"),
    myorder: str | None = Query(None, description="1 бол currency параметрийн дарааллаар эрэмбэлнэ"),
) -> JSONResponse:
    d = _parse_date_param(date or rate_date)
    lg = _norm_lang(lang)
    items = await _fetch_mnb_for_date(d, lang=lg)
    codes = _parse_currencies(currency)
    if codes:
        by_code = {item["code"]: item for item in items}
        if myorder:
            items = [by_code[c] for c in codes if c in by_code]
        else:
            code_set = set(codes)
            items = [item for item in items if item["code"] in code_set]
    return JSONResponse(content=items)


@app.get("/history.json")
@app.get("/api/v1/mnb/history")
async def mnb_history(
    currency: str = Query("USD", description="Валютын код: USD эсвэл USD|EUR|CNY"),
    start_date: str | None = Query(None, description="Эхлэх огноо: YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Дуусах огноо: YYYY-MM-DD"),
    days: int = Query(30, ge=1, le=366, description="Сүүлийн хэдэн хоног"),
    lang: str | None = Query("MN", description="Хэл: MN | EN | CN | JP | KR"),
) -> JSONResponse:
    codes = _parse_currencies(currency) or ["USD"]
    s_date = _parse_date_param(start_date)
    e_date = _parse_date_param(end_date)
    lg = _norm_lang(lang)

    pool = await get_pool()
    async with pool.acquire() as conn:
        if e_date is None:
            row = await conn.fetchrow("SELECT MAX(rate_date) AS max_d FROM mnb_rates")
            e_date = row["max_d"] or datetime.date.today()
        if s_date is None:
            s_date = e_date - datetime.timedelta(days=days)

        rows = await conn.fetch(
            """
            SELECT rate_date, code, rate, fetched_at
            FROM mnb_rates
            WHERE code = ANY($1::text[])
              AND rate_date BETWEEN $2 AND $3
            ORDER BY rate_date ASC, code ASC
            """,
            codes,
            s_date,
            e_date,
        )

    out = [
        {
            "code": r["code"],
            "name": _cur_name(r["code"], lg),
            "rate_date": r["rate_date"].isoformat(),
            "rate": _fmt_rate(r["rate"]),
            "rate_float": _to_float(r["rate"]),
            "last_date": _fmt_ub_dt(r["fetched_at"]),
        }
        for r in rows
    ]
    return JSONResponse(content=out)


@app.get("/banks.json")
@app.get("/api/v1/banks")
async def banks_json(
    bank: str | None = Query(None, description="Банк: Khaan|Golomt|TDB"),
    currency: str | None = Query(None, description="Валют: USD|EUR|CNY"),
    date: str | None = Query(None, description="Огноо: YYYY-MM-DD"),
    lang: str | None = Query("MN", description="Хэл: MN | EN | CN | JP | KR"),
) -> JSONResponse:
    codes = _parse_currencies(currency)
    banks = [b.strip() for b in bank.replace(",", "|").split("|") if b.strip()] if bank else []
    target_date = _parse_date_param(date)
    lg = _norm_lang(lang)

    pool = await get_pool()
    async with pool.acquire() as conn:
        if target_date is None:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (bank, code)
                    bank, code, rate_hour, name,
                    mongol_bank, non_cash_buy, non_cash_sell, cash_buy, cash_sell, fetched_at
                FROM bank_rates
                WHERE code <> ''
                ORDER BY bank, code, rate_hour DESC
                """
            )
        else:
            end_ts = datetime.datetime.combine(
                target_date, datetime.time(23, 59, 59), tzinfo=UB_TZ
            )
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (bank, code)
                    bank, code, rate_hour, name,
                    mongol_bank, non_cash_buy, non_cash_sell, cash_buy, cash_sell, fetched_at
                FROM bank_rates
                WHERE code <> ''
                  AND rate_hour <= $1
                ORDER BY bank, code, rate_hour DESC
                """,
                end_ts,
            )

    bank_set = {b.lower() for b in banks}
    code_set = set(codes)

    out: list[dict[str, Any]] = []
    for r in rows:
        b_name = str(r["bank"]).strip()
        c_code = str(r["code"]).strip().upper()
        if bank_set and b_name.lower() not in bank_set:
            continue
        if code_set and c_code not in code_set:
            continue
        out.append(
            {
                "bank": b_name,
                "bank_name_mn": BANK_NAMES_MN.get(b_name, b_name),
                "code": c_code,
                "name": _cur_name(c_code, lg) if c_code in CURRENCY_I18N else (r["name"] or c_code),
                "name_raw": r["name"],
                "rate_hour": _fmt_ub_dt(r["rate_hour"]),
                "rate_hour_utc": r["rate_hour"].isoformat() if r["rate_hour"] else None,
                "mongol_bank": _to_float(r["mongol_bank"]),
                "non_cash_buy": _to_float(r["non_cash_buy"]),
                "non_cash_sell": _to_float(r["non_cash_sell"]),
                "cash_buy": _to_float(r["cash_buy"]),
                "cash_sell": _to_float(r["cash_sell"]),
                "last_date": _fmt_ub_dt(r["fetched_at"]),
            }
        )

    out.sort(key=lambda x: (x["bank"], CURRENCY_RANK.get(x["code"], 999), x["code"]))
    return JSONResponse(content=out)


@app.get("/xansh.html", response_class=HTMLResponse)
async def xansh_html(
    currency: str | None = Query(None),
    date: str | None = Query(None),
    lang: str | None = Query("MN", description="Хэл: MN | EN | CN | JP | KR"),
    theme: str | None = Query("dark", description="Загвар: dark | light"),
    currency_title: str | None = Query(None),
    currency_rate_title: str | None = Query(None),
    source: str | None = Query(None),
    conv_tool: str | None = Query(None),
    myorder: str | None = Query(None),
) -> HTMLResponse:
    d = _parse_date_param(date)
    lg = _norm_lang(lang)
    i18n = WIDGET_I18N[lg]
    is_light = (theme or "").strip().lower() == "light"

    items = await _fetch_mnb_for_date(d, lang=lg)
    codes = _parse_currencies(currency)
    if codes:
        by_code = {item["code"]: item for item in items}
        if myorder:
            items = [by_code[c] for c in codes if c in by_code]
        else:
            code_set = set(codes)
            items = [item for item in items if item["code"] in code_set]

    eff_date = items[0]["rate_date"] if items else datetime.date.today().isoformat()
    col_cur = currency_title or i18n["col_cur"]
    col_rate = currency_rate_title or i18n["col_rate"]
    src_label = source or i18n["source_label"]

    rows_html = []
    options_html = []
    for item in items:
        c = html.escape(item["code"])
        name = html.escape(item["name"])
        r_str = html.escape(item["rate"])
        r_float = item["rate_float"]
        rows_html.append(
            f'      <tr>\n'
            f'        <td><div class="cur-cell"><span class="badge">{c}</span><span class="cur-name">{name}</span></div></td>\n'
            f'        <td class="rate-cell">{r_str} ₮</td>\n'
            f'      </tr>'
        )
        options_html.append(f'            <option value="{r_float}">{c}</option>')

    conv_block = ""
    if conv_tool:
        conv_block = f"""
    <div class="conv-box">
      <div class="conv-title">{html.escape(i18n["conv_title"])}</div>
      <div class="conv-row">
        <select id="rate" class="conv-select">
{chr(10).join(options_html)}
        </select>
        <input type="text" id="currency" class="conv-input" value="1" inputmode="decimal" />
      </div>
      <div class="conv-row" style="margin-top:6px;">
        <span class="conv-tag">{html.escape(i18n["mnt_label"])}</span>
        <input type="text" id="mnt" class="conv-input" placeholder="0.00" inputmode="decimal" />
      </div>
    </div>
    <script>
      (function() {{
        var mnt = document.getElementById('mnt');
        var cur = document.getElementById('currency');
        var sel = document.getElementById('rate');
        if (!mnt || !cur || !sel) return;
        function fmt(n) {{
          return n.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
        }}
        function clean(s) {{
          return parseFloat(String(s).replace(/,/g, ''));
        }}
        function fromCur() {{
          var r = parseFloat(sel.value);
          var v = clean(cur.value);
          mnt.value = (!isNaN(r) && !isNaN(v)) ? fmt(v * r) : '';
        }}
        function fromMnt() {{
          var r = parseFloat(sel.value);
          var v = clean(mnt.value);
          cur.value = (!isNaN(r) && !isNaN(v) && r > 0) ? (v / r).toFixed(2) : '';
        }}
        cur.addEventListener('input', fromCur);
        mnt.addEventListener('input', fromMnt);
        sel.addEventListener('change', fromCur);
        fromCur();
      }})();
    </script>"""

    theme_vars = (
        """
      --bg: #ffffff;
      --panel: #f8fafc;
      --ink: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --brand: #059669;
      --brand-soft: #ecfdf5;
      --brand-border: #a7f3d0;
        """
        if is_light
        else """
      --bg: #0b111e;
      --panel: #111a2e;
      --ink: #f1f5f9;
      --muted: #94a3b8;
      --border: #1e293b;
      --brand: #10b981;
      --brand-soft: rgba(16, 185, 129, 0.14);
      --brand-border: rgba(16, 185, 129, 0.32);
        """
    )

    page = f"""<!DOCTYPE html>
<html lang="{lg.lower()}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(i18n["title"])}</title>
  <style>
    :root {{{theme_vars}}}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans", sans-serif;
      font-size: 12px;
      background: var(--bg);
      color: var(--ink);
      -webkit-font-smoothing: antialiased;
    }}
    .widget {{
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--bg);
      overflow: hidden;
    }}
    .w-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 11px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
    }}
    .w-title {{
      font-weight: 700;
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--brand);
    }}
    .w-date {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 10.5px;
      color: var(--muted);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th {{
      text-align: left;
      padding: 6px 10px;
      font-size: 10.5px;
      color: var(--muted);
      font-weight: 600;
      border-bottom: 1px solid var(--border);
    }}
    th.right {{ text-align: right; }}
    td {{
      padding: 6px 10px;
      border-bottom: 1px solid var(--border);
    }}
    tbody tr:last-child td {{
      border-bottom: none;
    }}
    .cur-cell {{
      display: flex;
      align-items: center;
      gap: 7px;
      min-width: 0;
    }}
    .badge {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-weight: 700;
      font-size: 10.5px;
      padding: 1px 5px;
      border-radius: 4px;
      background: var(--brand-soft);
      border: 1px solid var(--brand-border);
      color: var(--brand);
      flex-shrink: 0;
    }}
    .cur-name {{
      color: var(--muted);
      font-size: 11px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .rate-cell {{
      text-align: right;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-weight: 600;
      font-size: 12px;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }}
    .conv-box {{
      padding: 8px 10px;
      background: var(--panel);
      border-top: 1px solid var(--border);
    }}
    .conv-title {{
      font-size: 10.5px;
      font-weight: 600;
      color: var(--muted);
      margin-bottom: 5px;
    }}
    .conv-row {{
      display: grid;
      grid-template-columns: 74px 1fr;
      gap: 6px;
      align-items: center;
    }}
    .conv-select, .conv-input {{
      width: 100%;
      height: 26px;
      background: var(--bg);
      color: var(--ink);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 0 7px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 11.5px;
      outline: none;
    }}
    .conv-input {{ text-align: right; }}
    .conv-select:focus, .conv-input:focus {{
      border-color: var(--brand);
    }}
    .conv-tag {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 10.5px;
      font-weight: 600;
      color: var(--muted);
      padding-left: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .w-foot {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 10px;
      border-top: 1px solid var(--border);
      font-size: 10.5px;
      color: var(--muted);
    }}
    .w-foot a {{
      color: var(--brand);
      text-decoration: none;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="widget">
    <div class="w-head">
      <span class="w-title"><span class="dot"></span>{html.escape(i18n["title"])}</span>
      <span class="w-date">{html.escape(eff_date)}</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>{html.escape(col_cur)}</th>
          <th class="right">{html.escape(col_rate)}</th>
        </tr>
      </thead>
      <tbody>
{chr(10).join(rows_html)}
      </tbody>
    </table>{conv_block}
    <div class="w-foot">
      <span>{html.escape(src_label)}</span>
      <a href="https://www.mongolbank.mn/mn/currency-rates" target="_blank" rel="noopener">{html.escape(i18n["source_name"])}</a>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=page)


@app.get("/ip", response_class=PlainTextResponse)
async def get_ip_plain(request: Request) -> PlainTextResponse:
    info = extract_visitor_info(request)
    return PlainTextResponse(content=info["ip"] + "\n")


@app.get("/json")
async def get_ip_json(request: Request) -> JSONResponse:
    return JSONResponse(content=extract_visitor_info(request))


@app.get("/headers")
async def get_request_headers(request: Request) -> JSONResponse:
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("cookie", "authorization")
    }
    return JSONResponse(content={"ip": extract_visitor_info(request)["ip"], "headers": headers})


@app.get("/weather.json")
@app.get("/api/v1/weather")
async def get_weather_json(
    aimag: str | None = Query(None, description="Аймгийн нэрээр шүүх (ж.нь: Нийслэл, Дархан-Уул, Өмнөговь)"),
    sid: int | None = Query(None, description="Станцын дугаараар шүүх (ж.нь: 292 = Улаанбаатар)"),
    all_stations: bool = Query(False, description="True бол бүх 321 станцыг буцаана; False бол 28 гол станцыг буцаана"),
) -> JSONResponse:
    wx_pool = await get_wx_pool()
    where_clauses = []
    params: list[Any] = []
    if sid is not None:
        params.append(sid)
        where_clauses.append(f"s.sid = ${len(params)}")
    elif aimag:
        params.append(f"%{aimag.strip()}%")
        where_clauses.append(f"s.aimag_name ILIKE ${len(params)}")
    elif not all_stations:
        where_clauses.append("s.sta_28 <> 0")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    async with wx_pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                s.sid,
                s.aimag_name,
                s.sum_name,
                s.sta_name,
                s.lat,
                s.lon,
                s.elev,
                s.sta_28,
                o.obs_time AT TIME ZONE 'Asia/Ulaanbaatar' AS obs_time_ub,
                o.temp,
                o.temp_min,
                o.temp_max,
                o.humidity,
                o.wind_speed,
                o.wind_dir,
                o.pressure_slp,
                o.precip,
                o.ww,
                o.cloud_nh
            FROM wx.stations s
            LEFT JOIN LATERAL (
                SELECT *
                FROM wx.obs_data d
                WHERE d.sid = s.sid
                ORDER BY d.obs_time DESC
                LIMIT 1
            ) o ON true
            {where_sql}
            ORDER BY CASE WHEN s.sta_28 = 0 THEN 999 ELSE s.sta_28 END ASC, s.sid ASC
            """,
            *params,
        )

    out = []
    for r in rows:
        out.append(
            {
                "sid": r["sid"],
                "aimag": r["aimag_name"],
                "sum": r["sum_name"],
                "station": r["sta_name"],
                "lat": r["lat"],
                "lon": r["lon"],
                "elev_m": r["elev"],
                "obs_time": r["obs_time_ub"].strftime("%Y-%m-%d %H:%M:%S") if r["obs_time_ub"] else None,
                "temp_c": round(float(r["temp"]), 1) if r["temp"] is not None else None,
                "temp_min_c": round(float(r["temp_min"]), 1) if r["temp_min"] is not None else None,
                "temp_max_c": round(float(r["temp_max"]), 1) if r["temp_max"] is not None else None,
                "humidity_pct": r["humidity"],
                "wind_ms": round(float(r["wind_speed"]), 1) if r["wind_speed"] is not None else None,
                "wind_dir_deg": r["wind_dir"],
                "pressure_hpa": round(float(r["pressure_slp"]), 1) if r["pressure_slp"] is not None else None,
                "precip_mm": round(float(r["precip"]), 2) if r["precip"] is not None else None,
                "condition": _ww_text(r["ww"], r["cloud_nh"]),
            }
        )
    return JSONResponse(content=out)


@app.get("/aqi.json")
@app.get("/api/v1/aqi")
async def get_aqi_json() -> JSONResponse:
    wx_pool = await get_wx_pool()
    async with wx_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (sid)
                sid, sname, lat, lon, aqi,
                pm25_value, pm10_value, no2_value, so2_value, co_value, o3_value,
                obs_time AT TIME ZONE 'Asia/Ulaanbaatar' AS obs_time_ub
            FROM wx.aqi_data
            WHERE obs_time > NOW() - INTERVAL '48 hours'
            ORDER BY sid, obs_time DESC
            """
        )
    out = []
    for r in rows:
        status_label, _ = _aqi_badge(r["aqi"])
        out.append(
            {
                "sid": r["sid"],
                "station": r["sname"],
                "lat": r["lat"],
                "lon": r["lon"],
                "aqi": r["aqi"],
                "status": status_label,
                "pm25": round(float(r["pm25_value"]), 2) if r["pm25_value"] is not None else None,
                "pm10": round(float(r["pm10_value"]), 2) if r["pm10_value"] is not None else None,
                "no2": round(float(r["no2_value"]), 2) if r["no2_value"] is not None else None,
                "so2": round(float(r["so2_value"]), 2) if r["so2_value"] is not None else None,
                "co": round(float(r["co_value"]), 2) if r["co_value"] is not None else None,
                "o3": round(float(r["o3_value"]), 2) if r["o3_value"] is not None else None,
                "obs_time": r["obs_time_ub"].strftime("%Y-%m-%d %H:%M:%S") if r["obs_time_ub"] else None,
            }
        )
    out.sort(key=lambda x: (x["aqi"] is None, -(x["aqi"] or 0)))
    return JSONResponse(content=out)


@app.get("/forecast.json")
@app.get("/api/v1/forecast")
async def get_forecast_json(
    sid: int = Query(292, description="Станцын дугаар (292 = Улаанбаатар)"),
) -> JSONResponse:
    wx_pool = await get_wx_pool()
    async with wx_pool.acquire() as conn:
        fore_3h = await conn.fetch(
            """
            SELECT DISTINCT ON (f_time)
                f_time AT TIME ZONE 'Asia/Ulaanbaatar' AS f_time_ub,
                pre_code, temp, temp_feels, precip_mm, precip_prob, wind
            FROM wx.fore_3hours
            WHERE sid = $1 AND f_time >= NOW() - INTERVAL '3 hours'
            ORDER BY f_time ASC, issued_at DESC
            LIMIT 16
            """,
            sid,
        )
        fore_day = await conn.fetch(
            """
            SELECT DISTINCT ON (fore_date)
                fore_date, ww_code, precip_prob, temp_day, temp_day_feels, wind_day
            FROM wx.fore_day
            WHERE sid = $1 AND fore_date >= CURRENT_DATE - INTERVAL '1 day'
            ORDER BY fore_date ASC, issued_at DESC
            LIMIT 7
            """,
            sid,
        )
    return JSONResponse(
        content={
            "sid": sid,
            "hourly_3h": [
                {
                    "time": r["f_time_ub"].strftime("%Y-%m-%d %H:%M:%S") if r["f_time_ub"] else None,
                    "temp_c": round(float(r["temp"]), 1) if r["temp"] is not None else None,
                    "feels_c": round(float(r["temp_feels"]), 1) if r["temp_feels"] is not None else None,
                    "wind_ms": round(float(r["wind"]), 1) if r["wind"] is not None else None,
                    "precip_prob_pct": r["precip_prob"],
                    "condition": _ww_text(r["pre_code"]),
                }
                for r in fore_3h
            ],
            "daily": [
                {
                    "date": r["fore_date"].isoformat(),
                    "temp_day_c": round(float(r["temp_day"]), 1) if r["temp_day"] is not None else None,
                    "feels_c": round(float(r["temp_day_feels"]), 1) if r["temp_day_feels"] is not None else None,
                    "wind_ms": round(float(r["wind_day"]), 1) if r["wind_day"] is not None else None,
                    "precip_prob_pct": r["precip_prob"],
                    "condition": _ww_text(r["ww_code"]),
                }
                for r in fore_day
            ],
        }
    )


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request, site: str | None = Query(None)) -> HTMLResponse:
    host_raw = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "ulaach.cc").split(":")[0].lower()
    target = (site or "").strip().lower()
    if not target:
        if host_raw.startswith("weather."):
            target = "weather"
        elif host_raw.startswith("tool.") or host_raw.startswith("ip."):
            target = "tool"
        elif host_raw.startswith("fx.") or host_raw.startswith("xansh."):
            target = "fx"
        else:
            target = "portal"

    if target == "tool":
        return render_tool_page(request)
    if target == "weather":
        wx_pool = await get_wx_pool()
        return await render_weather_page(wx_pool)
    if target == "portal":
        fx_pool = await get_pool()
        wx_pool = await get_wx_pool()
        return await render_portal_page(request, fx_pool, wx_pool)

    mnb_items = await _fetch_mnb_for_date(None, lang="MN")
    pool = await get_pool()
    async with pool.acquire() as conn:
        bank_rows = await conn.fetch(
            """
            SELECT DISTINCT ON (bank, code)
                bank, code, rate_hour, mongol_bank, non_cash_buy, non_cash_sell, cash_buy, cash_sell
            FROM bank_rates
            WHERE code IN ('USD', 'EUR', 'CNY', 'RUB', 'JPY', 'KRW', 'GBP')
            ORDER BY bank, code, rate_hour DESC
            """
        )

    latest_date = mnb_items[0]["rate_date"] if mnb_items else datetime.date.today().isoformat()
    latest_fetched = mnb_items[0]["last_date"] if mnb_items else ""

    major_codes = ["USD", "EUR", "CNY", "RUB", "JPY", "KRW", "GBP"]
    bank_map: dict[tuple[str, str], Any] = {}
    latest_bank_hour = ""
    for r in bank_rows:
        bank_map[(r["bank"], r["code"])] = r
        if not latest_bank_hour and r["rate_hour"]:
            latest_bank_hour = _fmt_ub_dt(r["rate_hour"])

    mnb_by_code = {x["code"]: x for x in mnb_items}

    bank_table_rows = []
    for code in major_codes:
        mnb_val = mnb_by_code.get(code, {}).get("rate", "—")
        c_name = CURRENCY_NAMES.get(code, code)

        def _cell(b: str) -> str:
            row = bank_map.get((b, code))
            if not row:
                return '<td class="muted center">—</td><td class="muted center">—</td>'
            nc_b = _fmt_rate(row["non_cash_buy"]) if row["non_cash_buy"] else "—"
            nc_s = _fmt_rate(row["non_cash_sell"]) if row["non_cash_sell"] else "—"
            return f'<td class="num buy">{nc_b}</td><td class="num sell">{nc_s}</td>'

        bank_table_rows.append(
            f"<tr>"
            f"<td><span class='code-badge'>{code}</span> <span class='cur-name'>{html.escape(c_name)}</span></td>"
            f"<td class='num strong mnb-col'>{mnb_val}</td>"
            f"{_cell('Khaan')}"
            f"{_cell('Golomt')}"
            f"{_cell('TDB')}"
            f"</tr>"
        )

    all_mnb_rows = []
    for item in mnb_items:
        all_mnb_rows.append(
            f"<tr>"
            f"<td><span class='code-badge'>{html.escape(item['code'])}</span></td>"
            f"<td>{html.escape(item['name'])}</td>"
            f"<td class='num strong'>{html.escape(item['rate'])} ₮</td>"
            f"<td class='mono muted'>{html.escape(item['rate_date'])}</td>"
            f"<td class='mono muted'>{html.escape(item['last_date'])}</td>"
            f"</tr>"
        )

    host = request.headers.get("host", "ulaach.cc")
    proto = request.headers.get("x-forwarded-proto", "https")
    base_url = f"{proto}://{host}"

    html_doc = f"""<!DOCTYPE html>
<html lang="mn">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ulaach.cc // Валютын ханшийн Developer API</title>
  <style>
    :root {{
      --bg: #090d16;
      --bg-grid: rgba(148, 163, 184, 0.04);
      --panel: #0f1624;
      --panel-alt: #131c2e;
      --code-bg: #060911;
      --ink: #e2e8f0;
      --ink-bright: #f8fafc;
      --muted: #8b9bb4;
      --border: #1e293b;
      --border-strong: #334155;
      --brand: #10b981;
      --brand-soft: rgba(16, 185, 129, 0.12);
      --brand-border: rgba(16, 185, 129, 0.32);
      --accent: #38bdf8;
      --accent-soft: rgba(56, 189, 248, 0.12);
      --buy: #34d399;
      --sell: #fbbf24;
      --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --sans: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      background-color: var(--bg);
      background-image:
        linear-gradient(to right, var(--bg-grid) 1px, transparent 1px),
        linear-gradient(to bottom, var(--bg-grid) 1px, transparent 1px);
      background-size: 28px 28px;
      color: var(--ink);
      line-height: 1.55;
      font-size: 14px;
      -webkit-font-smoothing: antialiased;
    }}
    .topbar {{
      border-bottom: 1px solid var(--border);
      background: rgba(9, 13, 22, 0.85);
      backdrop-filter: blur(8px);
      position: sticky;
      top: 0;
      z-index: 20;
    }}
    .topbar-inner {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .brand-bar {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-family: var(--mono);
      font-size: 13px;
      font-weight: 600;
      color: var(--ink-bright);
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--brand);
      box-shadow: 0 0 10px var(--brand);
      display: inline-block;
    }}
    .nav-links {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .nav-btn {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--ink);
      text-decoration: none;
      padding: 5px 11px;
      border-radius: 6px;
      border: 1px solid var(--border);
      background: var(--panel);
      transition: border-color 0.15s, color 0.15s;
    }}
    .nav-btn:hover {{
      border-color: var(--brand);
      color: var(--brand);
    }}
    .nav-btn.primary {{
      background: var(--brand-soft);
      border-color: var(--brand-border);
      color: var(--brand);
    }}
    .container {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 24px 72px;
    }}
    .hero {{
      margin-bottom: 24px;
      padding: 22px 24px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: linear-gradient(180deg, rgba(19, 28, 46, 0.75) 0%, rgba(15, 22, 36, 0.95) 100%);
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
    }}
    h1 {{
      margin: 0 0 8px 0;
      font-size: 22px;
      font-weight: 700;
      color: var(--ink-bright);
      letter-spacing: -0.02em;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 13.5px;
      max-width: 720px;
    }}
    .meta-strip {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      font-family: var(--mono);
      font-size: 11.5px;
    }}
    .meta-tag {{
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 5px 10px;
      color: var(--muted);
    }}
    .meta-tag strong {{
      color: var(--ink-bright);
      font-weight: 600;
    }}
    .section-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 22px 24px;
      margin-bottom: 20px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      padding-bottom: 14px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }}
    .section-title {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--ink-bright);
    }}
    .step-badge {{
      font-family: var(--mono);
      font-size: 11.5px;
      font-weight: 700;
      color: var(--brand);
      background: var(--brand-soft);
      border: 1px solid var(--brand-border);
      padding: 2px 8px;
      border-radius: 5px;
    }}
    .section-note {{
      font-family: var(--mono);
      font-size: 11.5px;
      color: var(--muted);
    }}
    .endpoint-list {{
      display: grid;
      gap: 10px;
      margin-bottom: 18px;
    }}
    .ep {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      flex-wrap: wrap;
      padding: 10px 14px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--code-bg);
      transition: border-color 0.15s;
    }}
    .ep:hover {{
      border-color: var(--border-strong);
    }}
    .ep-left {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      min-width: 0;
    }}
    .ep-method {{
      font-family: var(--mono);
      font-weight: 700;
      font-size: 11px;
      color: var(--brand);
      background: var(--brand-soft);
      border: 1px solid var(--brand-border);
      padding: 2px 8px;
      border-radius: 4px;
      letter-spacing: 0.04em;
    }}
    .ep-url {{
      font-family: var(--mono);
      font-size: 13px;
      font-weight: 600;
      color: var(--accent);
      text-decoration: none;
      word-break: break-all;
    }}
    .ep-url:hover {{
      text-decoration: underline;
    }}
    .ep-desc {{
      font-size: 12.5px;
      color: var(--muted);
    }}
    .code-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }}
    @media (max-width: 860px) {{
      .code-grid {{ grid-template-columns: 1fr; }}
    }}
    .code-box {{
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--code-bg);
      overflow: hidden;
    }}
    .code-bar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
      padding: 7px 12px;
      background: var(--panel-alt);
      border-bottom: 1px solid var(--border);
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
    }}
    .copy-btn {{
      font-family: var(--mono);
      font-size: 11px;
      color: var(--ink);
      background: transparent;
      border: 1px solid var(--border-strong);
      border-radius: 4px;
      padding: 3px 9px;
      cursor: pointer;
    }}
    .copy-btn:hover {{
      border-color: var(--brand);
      color: var(--brand);
    }}
    .lang-tabs {{
      display: flex;
      gap: 4px;
      align-items: center;
    }}
    .lang-btn {{
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 600;
      color: var(--muted);
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 3px 8px;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .lang-btn:hover {{
      color: var(--ink-bright);
      border-color: var(--border-strong);
    }}
    .lang-btn.active {{
      color: var(--brand);
      background: var(--brand-soft);
      border-color: var(--brand-border);
    }}
    pre {{
      margin: 0;
      padding: 13px 15px;
      overflow-x: auto;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.55;
      color: var(--ink);
    }}
    code {{
      font-family: var(--mono);
      font-size: 12px;
      background: var(--code-bg);
      border: 1px solid var(--border);
      padding: 1px 6px;
      border-radius: 4px;
      color: var(--accent);
    }}
    pre code {{
      background: transparent;
      border: none;
      padding: 0;
      color: inherit;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 9px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }}
    th {{
      background: var(--panel-alt);
      font-weight: 600;
      color: var(--muted);
      font-size: 11.5px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    tbody tr:hover {{
      background: rgba(255, 255, 255, 0.02);
    }}
    .num {{
      text-align: right;
      font-family: var(--mono);
      font-variant-numeric: tabular-nums;
    }}
    .mono {{
      font-family: var(--mono);
      font-size: 12px;
    }}
    .strong {{ font-weight: 600; color: var(--ink-bright); }}
    .mnb-col {{ color: var(--accent); }}
    .buy {{ color: var(--buy); }}
    .sell {{ color: var(--sell); }}
    .muted {{ color: var(--muted); }}
    .center {{ text-align: center; }}
    .code-badge {{
      display: inline-block;
      min-width: 44px;
      text-align: center;
      font-family: var(--mono);
      font-weight: 700;
      font-size: 11.5px;
      padding: 2px 7px;
      border-radius: 4px;
      background: var(--brand-soft);
      border: 1px solid var(--brand-border);
      color: var(--brand);
      margin-right: 6px;
    }}
    .widget-row {{
      display: grid;
      grid-template-columns: 1fr 270px;
      gap: 18px;
      align-items: start;
      margin-top: 16px;
    }}
    @media (max-width: 820px) {{
      .widget-row {{ grid-template-columns: 1fr; }}
    }}
    .iframe-wrap {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .scroll-table {{
      max-height: 440px;
      overflow-y: auto;
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    .scroll-table thead th {{
      position: sticky;
      top: 0;
      z-index: 2;
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <a class="brand-bar" href="https://ulaach.cc" style="text-decoration:none;">
        <span class="status-dot"></span>
        <span>fx.ulaach.cc // FX-API v1.2</span>
      </a>
      <div class="nav-links">
        <a class="nav-btn" href="https://ulaach.cc">← Portal (ulaach.cc)</a>
        <a class="nav-btn" href="#sec-1">01. Endpoints</a>
        <a class="nav-btn" href="#sec-2">02. Params &amp; Widget</a>
        <a class="nav-btn" href="#sec-3">03. Bank Rates</a>
        <a class="nav-btn" href="#sec-4">04. MNB 38 Currencies</a>
        <a class="nav-btn" href="https://weather.ulaach.cc">weather.ulaach.cc</a>
        <a class="nav-btn" href="https://tool.ulaach.cc">tool.ulaach.cc</a>
        <a class="nav-btn primary" href="/api/docs" target="_blank">OpenAPI →</a>
      </div>
    </div>
  </div>

  <div class="container">
    <div class="hero">
      <div>
        <h1>Монголбанк ба Арилжааны банкны ханшийн Developer API</h1>
        <p class="subtitle">Монголбанкны 38 валютын өдөр тутмын албан ханш, түүхэн огнооны лавлагаа (<code>?date=YYYY-MM-DD</code>), арилжааны банкуудын цаг тутмын ханш болон олон хэлний (<code>MN</code>, <code>EN</code>, <code>CN</code>, <code>JP</code>, <code>KR</code>) бэлэн веб виджет.</p>
      </div>
      <div class="meta-strip">
        <span class="meta-tag">MNB_DATE: <strong>{html.escape(latest_date)}</strong> (38 валют)</span>
        <span class="meta-tag">BANKS_SYNC: <strong>{html.escape(latest_bank_hour)}</strong></span>
        <span class="meta-tag">LANG: <strong>MN / EN / CN / JP / KR</strong></span>
      </div>
    </div>

    <!-- 01. Шууд дуудах JSON Endpoint-ууд -->
    <section id="sec-1" class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">01</span> Шууд дуудах JSON Endpoint-ууд</h2>
        <span class="section-note">Content-Type: application/json; charset=utf-8</span>
      </div>

      <div class="endpoint-list">
        <div class="ep">
          <div class="ep-left">
            <span class="ep-method">GET</span>
            <a class="ep-url" href="/xansh.json?currency=USD|EUR|CNY|RUB|JPY|KRW&lang=MN" target="_blank">/xansh.json?currency=USD|EUR|CNY|RUB|JPY|KRW&amp;lang=MN</a>
          </div>
          <span class="ep-desc">Монголбанкны өнөөдрийн албан ханш (38 валют, 5 хэлний сонголттой)</span>
        </div>

        <div class="ep">
          <div class="ep-left">
            <span class="ep-method">GET</span>
            <a class="ep-url" href="/xansh.json?date={html.escape(latest_date)}&currency=USD|EUR|CNY" target="_blank">/xansh.json?date={html.escape(latest_date)}&amp;currency=USD|EUR|CNY</a>
          </div>
          <span class="ep-desc">Тухайн огнооны Монголбанкны түүхэн албан ханш (амралтын өдөр бол өмнөх ажлын өдрийн ханш)</span>
        </div>

        <div class="ep">
          <div class="ep-left">
            <span class="ep-method">GET</span>
            <a class="ep-url" href="/banks.json?bank=Khaan|Golomt|TDB&currency=USD|EUR|CNY" target="_blank">/banks.json?bank=Khaan|Golomt|TDB&amp;currency=USD|EUR|CNY</a>
          </div>
          <span class="ep-desc">Арилжааны банкуудын бэлэн / бэлэн бус ханш (<code>?date=YYYY-MM-DD</code> түүхэн огноо дэмжинэ)</span>
        </div>

        <div class="ep">
          <div class="ep-left">
            <span class="ep-method">GET</span>
            <a class="ep-url" href="/history.json?currency=USD&days=30" target="_blank">/history.json?currency=USD&amp;days=30</a>
          </div>
          <span class="ep-desc">Валютын сүүлийн N хоногийн (эсвэл <code>start_date</code>..<code>end_date</code>) түүхэн цуваа</span>
        </div>
      </div>

      <div class="code-grid">
        <div class="code-box">
          <div class="code-bar">
            <span>JavaScript / Fetch &amp; cURL</span>
            <button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('code-req').innerText)">Copy</button>
          </div>
          <pre id="code-req"><code>// JavaScript (Fetch)
const res = await fetch("{base_url}/xansh.json?currency=USD|EUR&amp;date={html.escape(latest_date)}&amp;lang=MN");
const rates = await res.json();

# cURL
curl -s "{base_url}/xansh.json?currency=USD|EUR&amp;date={html.escape(latest_date)}&amp;lang=EN"</code></pre>
        </div>

        <div class="code-box">
          <div class="code-bar">
            <span>200 OK — JSON Response</span>
          </div>
          <pre><code>[
  {{
    "code": "USD",
    "last_date": "{html.escape(latest_fetched)}",
    "name": "АНУ-ын доллар",
    "rate": "{html.escape(mnb_by_code.get('USD', {}).get('rate', '3,597.30'))}",
    "rate_date": "{html.escape(latest_date)}",
    "rate_float": {mnb_by_code.get('USD', {}).get('rate_float', 3597.3)}
  }}
]</code></pre>
        </div>
      </div>
    </section>

    <!-- 02. GET Параметрүүд ба Олон хэлний IFrame Виджет -->
    <section id="sec-2" class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">02</span> GET Параметрүүд ба Олон хэлний IFrame Виджет</h2>
        <span class="section-note">Supported Languages: MN, EN, CN, JP, KR</span>
      </div>

      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th style="width:150px;">Параметр</th>
              <th style="width:200px;">Жишээ утга</th>
              <th>Тайлбар</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>currency</code></td>
              <td class="mono muted">USD|EUR|CNY|RUB</td>
              <td>Валютын 3 үсэгтэй кодуудыг <code>|</code> эсвэл <code>,</code> тэмдгээр тусгаарлан шүүж авна</td>
            </tr>
            <tr>
              <td><code>lang</code></td>
              <td class="mono muted">MN | EN | CN | JP | KR</td>
              <td>Валютын нэр болон виджетийн хэлийг сонгоно (Монгол, Англи, Хятад, Япон, Солонгос)</td>
            </tr>
            <tr>
              <td><code>date</code></td>
              <td class="mono muted">{html.escape(latest_date)}</td>
              <td>Түүхэн огноо (<code>YYYY-MM-DD</code>). <code>/xansh.json</code>, <code>/banks.json</code>, <code>/xansh.html</code> бүгд дэмжинэ</td>
            </tr>
            <tr>
              <td><code>theme</code></td>
              <td class="mono muted">dark | light</td>
              <td>Зөвхөн <code>/xansh.html</code> виджет дээр: Бараан (<code>dark</code>) эсвэл Цайвар (<code>light</code>) загвар</td>
            </tr>
            <tr>
              <td><code>conv_tool</code></td>
              <td class="mono muted">1</td>
              <td>Зөвхөн <code>/xansh.html</code> виджет дээр: Валют ↔ Төгрөг шууд хөрвүүлэгч гаргана</td>
            </tr>
            <tr>
              <td><code>bank</code></td>
              <td class="mono muted">Khaan|Golomt|TDB</td>
              <td>Зөвхөн <code>/banks.json</code> дээр: Арилжааны банкны нэрээр шүүх</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="widget-row">
        <div class="code-box">
          <div class="code-bar">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <span>HTML Embed (IFrame Widget)</span>
              <div class="lang-tabs" id="lang-tabs">
                <button type="button" class="lang-btn active" data-lang="MN">MN</button>
                <button type="button" class="lang-btn" data-lang="EN">EN</button>
                <button type="button" class="lang-btn" data-lang="CN">CN</button>
                <button type="button" class="lang-btn" data-lang="JP">JP</button>
                <button type="button" class="lang-btn" data-lang="KR">KR</button>
              </div>
              <div class="lang-tabs" id="theme-tabs">
                <button type="button" class="lang-btn active" data-theme="dark">Dark</button>
                <button type="button" class="lang-btn" data-theme="light">Light</button>
              </div>
            </div>
            <button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('code-iframe').innerText)">Copy</button>
          </div>
          <pre id="code-iframe"><code>&lt;iframe
  style="width:270px;height:360px;border:none;overflow:hidden;border-radius:10px;"
  src="{base_url}/xansh.html?currency=USD|EUR|CNY|JPY|KRW|RUB&amp;lang=MN&amp;theme=dark&amp;conv_tool=1"&gt;
&lt;/iframe&gt;</code></pre>
        </div>
        <div class="iframe-wrap">
          <iframe id="widget-preview-frame" style="width:270px;height:360px;border:none;overflow:hidden;border-radius:10px;display:block;" src="/xansh.html?currency=USD|EUR|CNY|JPY|KRW|RUB&lang=MN&theme=dark&conv_tool=1"></iframe>
        </div>
      </div>
    </section>

    <!-- 03. Арилжааны банкуудын бэлэн бус ханшийн харьцуулалт -->
    <section id="sec-3" class="section-card">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">03</span> Арилжааны банкуудын бэлэн бус ханшийн харьцуулалт</h2>
        <span class="section-note">Шинэчлэгдсэн: {html.escape(latest_bank_hour)} (GET /banks.json)</span>
      </div>

      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th rowspan="2">Валют</th>
              <th rowspan="2" class="num">Монголбанк</th>
              <th colspan="2" class="center">Хаан банк (Бэлэн бус)</th>
              <th colspan="2" class="center">Голомт банк (Бэлэн бус)</th>
              <th colspan="2" class="center">ХХБ (Бэлэн бус)</th>
            </tr>
            <tr>
              <th class="num">Авах</th><th class="num">Зарах</th>
              <th class="num">Авах</th><th class="num">Зарах</th>
              <th class="num">Авах</th><th class="num">Зарах</th>
            </tr>
          </thead>
          <tbody>
            {''.join(bank_table_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <!-- 04. Монголбанкны албан ханшийн жагсаалт (Бүх 38 валют) -->
    <section id="sec-4" class="section-card" style="margin-bottom:0;">
      <div class="section-head">
        <h2 class="section-title"><span class="step-badge">04</span> Монголбанкны албан ханшийн жагсаалт (Бүх 38 валют)</h2>
        <span class="section-note">Ханшийн огноо: {html.escape(latest_date)} (GET /xansh.json)</span>
      </div>

      <div class="scroll-table">
        <table>
          <thead>
            <tr>
              <th style="width:90px;">Код</th>
              <th>Валютын нэр</th>
              <th class="num">Албан ханш</th>
              <th style="width:140px;">Ханшийн огноо</th>
              <th style="width:170px;">Татсан цаг</th>
            </tr>
          </thead>
          <tbody>
            {''.join(all_mnb_rows)}
          </tbody>
        </table>
      </div>
    </section>
  </div>

  <script>
    (function() {{
      var curLang = 'MN';
      var curTheme = 'dark';
      var baseUrl = {repr(base_url)};
      var frame = document.getElementById('widget-preview-frame');
      var codeEl = document.getElementById('code-iframe');

      function updateWidget() {{
        var rel = '/xansh.html?currency=USD|EUR|CNY|JPY|KRW|RUB&lang=' + curLang + '&theme=' + curTheme + '&conv_tool=1';
        frame.src = rel;
        codeEl.textContent = [
          '<iframe',
          '  style="width:270px;height:360px;border:none;overflow:hidden;border-radius:10px;"',
          '  src="' + baseUrl + rel + '">',
          '</iframe>'
        ].join(String.fromCharCode(10));
      }}

      document.querySelectorAll('#lang-tabs .lang-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
          document.querySelectorAll('#lang-tabs .lang-btn').forEach(function(b) {{ b.classList.remove('active'); }});
          btn.classList.add('active');
          curLang = btn.getAttribute('data-lang');
          updateWidget();
        }});
      }});

      document.querySelectorAll('#theme-tabs .lang-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
          document.querySelectorAll('#theme-tabs .lang-btn').forEach(function(b) {{ b.classList.remove('active'); }});
          btn.classList.add('active');
          curTheme = btn.getAttribute('data-theme');
          updateWidget();
        }});
      }});
    }})();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_doc)
