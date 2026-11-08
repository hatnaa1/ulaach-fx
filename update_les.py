#!/usr/bin/env python3
"""
ULAACH.CC — Legal Entities Open Data (les.ulaach.cc) Updater / Importer
=======================================================================
Usage:
  1. Auto-fetch latest dataview from opendata.gov.mn (org 5296722):
     python3 update_les.py

  2. Fetch a specific opendata.gov.mn dataview ID (e.g. 8438 or 8535):
     python3 update_les.py 8438
     python3 update_les.py https://opendata.gov.mn/dataview/8438

  3. Import from a already-downloaded local JSON file:
     python3 update_les.py /path/to/LesOutputJson.json
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

OPENDATA_DETAIL_API = "https://opendata.gov.mn/api/v1/front/detail/view"
OPENDATA_SEARCH_API = "https://opendata.gov.mn/api/v1/front/search"
OPENDATA_MEDIA_BASE = "https://opendata.gov.mn/api/v1/media"
LES_DATA_UUID = "5dc482b0-5909-4340-af58-46dd5fff33ec"
LES_ORG_REG = "5296722"


def fetch_json_post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ulaach-les-importer/1.0 (+https://les.ulaach.cc)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_dataview(target: str | None) -> dict:
    dataview_id: int | None = None
    if target:
        m = re.search(r"(\d+)$", target.strip())
        if m:
            dataview_id = int(m.group(1))
    if dataview_id is None:
        print("[1/4] Looking up latest Legal Entities dataset on opendata.gov.mn...")
        res = fetch_json_post(
            OPENDATA_SEARCH_API,
            {
                "page": {"page": 1, "page_size": 5, "sort": "created_at DESC"},
                "org_reg_num": LES_ORG_REG,
                "data_uuid": LES_DATA_UUID,
                "frequency_uuid": "",
                "start_term": "",
                "end_term": "",
                "query": "",
            },
        )
        items = ((res.get("result") or {}).get("details") or {}).get("items") or []
        if not items:
            raise RuntimeError("No items returned from opendata.gov.mn search API")
        dataview_id = int(items[0]["id"])
        print(f"      Found latest dataview ID: {dataview_id} ({items[0].get('term')})")

    print(f"[1/4] Fetching metadata for dataview/{dataview_id}...")
    detail_res = fetch_json_post(OPENDATA_DETAIL_API, {"id": dataview_id})
    result = detail_res.get("result") or {}
    files = result.get("files") or []
    if not files:
        raise RuntimeError(f"No files found in dataview/{dataview_id}")
    f0 = files[0]
    return {
        "dataview_id": dataview_id,
        "file_id": f0.get("id"),
        "file_path": f0.get("path"),
        "file_size": f0.get("size"),
        "source_updated_at": f0.get("updated_at") or result.get("updated_at") or result.get("term"),
        "download_url": f"{OPENDATA_MEDIA_BASE}/{f0['path']}",
    }


def pg_escape_copy(val: str) -> str:
    return (
        val.replace("\\", "\\\\")
        .replace("\t", " ")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def format_person_Shareholder(row: list) -> dict:
    # ["Иргэн", "Монгол Улс", "цэдэнбалжир", "идэрбүргэд", "Эр", "2021.03.05"]
    return {
        "kind": (row[0] or "").strip() if len(row) > 0 else "",
        "country": (row[1] or "").strip() if len(row) > 1 else "",
        "last_name": (row[2] or "").strip() if len(row) > 2 else "",
        "first_name": (row[3] or "").strip() if len(row) > 3 else "",
        "gender": (row[4] or "").strip() if len(row) > 4 else "",
        "registered_at": (row[5] or "").strip() if len(row) > 5 else "",
    }


def format_person_executive(row: list) -> dict:
    # ["Гүйцэтгэх захирал", "Монгол Улс", "Цэдэнбалжир", "Идэрбүргэд", "Эр", "2021.03.05"]
    return {
        "title": (row[0] or "").strip() if len(row) > 0 else "",
        "country": (row[1] or "").strip() if len(row) > 1 else "",
        "last_name": (row[2] or "").strip() if len(row) > 2 else "",
        "first_name": (row[3] or "").strip() if len(row) > 3 else "",
        "gender": (row[4] or "").strip() if len(row) > 4 else "",
        "registered_at": (row[5] or "").strip() if len(row) > 5 else "",
    }


def format_person_ubo(row: list) -> dict:
    # ["Иргэн", "Идэрбүргэд", "Цэдэнбалжир", "Монгол Улс", "Эр"]
    return {
        "kind": (row[0] or "").strip() if len(row) > 0 else "",
        "first_name": (row[1] or "").strip() if len(row) > 1 else "",
        "last_name": (row[2] or "").strip() if len(row) > 2 else "",
        "country": (row[3] or "").strip() if len(row) > 3 else "",
        "gender": (row[4] or "").strip() if len(row) > 4 else "",
    }


def format_activity(row: list) -> dict:
    # ["Тийм", "2021.03.05", "Төмөр хашаа, хайс, хаалт хийх"]
    return {
        "active": (row[0] or "").strip() if len(row) > 0 else "",
        "registered_at": (row[1] or "").strip() if len(row) > 1 else "",
        "description": (row[2] or "").strip() if len(row) > 2 else "",
    }


def format_reorg(row: list) -> dict:
    # ["Нэгтгэх", "11-APR-16", "САТАС корпораци", "5384621 тоот ..."]
    return {
        "mode": (row[0] or "").strip() if len(row) > 0 else "",
        "registered_at": (row[1] or "").strip() if len(row) > 1 else "",
        "prev_name": (row[2] or "").strip() if len(row) > 2 else "",
        "note": (row[3] or "").strip() if len(row) > 3 else "",
    }


def main() -> None:
    t0 = time.time()
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    work_dir = Path("/tmp/les_import")
    work_dir.mkdir(parents=True, exist_ok=True)
    json_path = work_dir / "LesOutputJson.json"

    meta = {
        "dataview_id": 8438,
        "file_id": 23953,
        "file_path": "local",
        "file_size": 0,
        "source_updated_at": "",
    }

    if arg and Path(arg).is_file():
        json_path = Path(arg)
        meta["file_size"] = json_path.stat().st_size
        meta["source_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(json_path.stat().st_mtime))
        print(f"[1/4] Using local JSON file: {json_path} ({meta['file_size'] / (1024*1024):.2f} MB)")
    else:
        meta = resolve_dataview(arg)
        print(f"[2/4] Downloading {meta['download_url']} ({meta['file_size'] / (1024*1024):.2f} MB)...")
        subprocess.run(
            ["curl", "-L", "--fail", "--progress-bar", "-o", str(json_path), meta["download_url"]],
            check=True,
        )

    print("[3/4] Parsing JSON & loading into wx-postgres (les.entities)...")
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    rows = payload.get("Data") or []
    total_raw = len(rows)
    print(f"      Loaded {total_raw:,} raw records in {time.time() - t0:.1f}s. Preparing COPY stream...")

    # Start psql COPY into staging table
    init_sql = """
    DROP TABLE IF EXISTS les.entities_staging;
    CREATE UNLOGGED TABLE les.entities_staging (LIKE les.entities);
    """
    subprocess.run(
        ["docker", "exec", "-i", "wx-postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "weather", "-c", init_sql],
        check=True,
    )

    copy_cmd = [
        "docker", "exec", "-i", "wx-postgres",
        "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "weather",
        "-c", "COPY les.entities_staging (regno, name, registered_at, reg_year, legal_form, entity_type, shareholders, executives, beneficial_owners, activities, reorganizations, people_text, activities_text) FROM STDIN",
    ]
    proc = subprocess.Popen(copy_cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    seen_regnos: set[str] = set()
    imported_count = 0

    for item in rows:
        if not isinstance(item, list) or len(item) < 5:
            continue
        regno = str(item[0] or "").strip()
        if not regno or regno in seen_regnos:
            continue
        seen_regnos.add(regno)

        name = str(item[1] or "").strip()
        reg_date = str(item[2] or "").strip()
        reg_year_str = "\\N"
        if len(reg_date) >= 4 and reg_date[:4].isdigit():
            yr = int(reg_date[:4])
            if 1900 <= yr <= 2100:
                reg_year_str = str(yr)

        legal_form = str(item[3] or "").strip()
        entity_type = str(item[4] or "").strip()

        raw_sh = item[5] if len(item) > 5 and isinstance(item[5], list) else []
        raw_ex = item[6] if len(item) > 6 and isinstance(item[6], list) else []
        raw_ub = item[7] if len(item) > 7 and isinstance(item[7], list) else []
        raw_ac = item[8] if len(item) > 8 and isinstance(item[8], list) else []
        raw_re = item[9] if len(item) > 9 and isinstance(item[9], list) else []

        sh_list = [format_person_Shareholder(r) for r in raw_sh if isinstance(r, list)]
        ex_list = [format_person_executive(r) for r in raw_ex if isinstance(r, list)]
        ub_list = [format_person_ubo(r) for r in raw_ub if isinstance(r, list)]
        ac_list = [format_activity(r) for r in raw_ac if isinstance(r, list)]
        re_list = [format_reorg(r) for r in raw_re if isinstance(r, list)]

        people_tokens: list[str] = []
        for p in sh_list:
            ln, fn = p["last_name"], p["first_name"]
            if ln or fn:
                people_tokens.append(f"{ln} {fn}".strip())
        for p in ex_list:
            ln, fn = p["last_name"], p["first_name"]
            if ln or fn:
                people_tokens.append(f"{ln} {fn}".strip())
        for p in ub_list:
            ln, fn = p["last_name"], p["first_name"]
            if ln or fn:
                people_tokens.append(f"{ln} {fn}".strip())
        for r_item in re_list:
            if r_item["prev_name"]:
                people_tokens.append(r_item["prev_name"])
            if r_item["note"]:
                people_tokens.append(r_item["note"])

        act_tokens = [a["description"] for a in ac_list if a["description"]]

        people_txt = " | ".join(dict.fromkeys(people_tokens))
        act_txt = " | ".join(dict.fromkeys(act_tokens))

        line = (
            f"{pg_escape_copy(regno)}\t"
            f"{pg_escape_copy(name)}\t"
            f"{pg_escape_copy(reg_date)}\t"
            f"{reg_year_str}\t"
            f"{pg_escape_copy(legal_form)}\t"
            f"{pg_escape_copy(entity_type)}\t"
            f"{pg_escape_copy(json.dumps(sh_list, ensure_ascii=False))}\t"
            f"{pg_escape_copy(json.dumps(ex_list, ensure_ascii=False))}\t"
            f"{pg_escape_copy(json.dumps(ub_list, ensure_ascii=False))}\t"
            f"{pg_escape_copy(json.dumps(ac_list, ensure_ascii=False))}\t"
            f"{pg_escape_copy(json.dumps(re_list, ensure_ascii=False))}\t"
            f"{pg_escape_copy(people_txt)}\t"
            f"{pg_escape_copy(act_txt)}\n"
        )
        proc.stdin.write(line.encode("utf-8"))
        imported_count += 1

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"psql COPY failed with exit code {rc}")

    del payload
    del rows

    print(f"[4/4] Building trigram/B-tree indexes and swapping tables ({imported_count:,} unique entities)...")
    swap_sql = f"""
    CREATE INDEX idx_les_stg_name_trgm ON les.entities_staging USING gin (name public.gin_trgm_ops);
    CREATE INDEX idx_les_stg_people_trgm ON les.entities_staging USING gin (people_text public.gin_trgm_ops);
    CREATE INDEX idx_les_stg_act_trgm ON les.entities_staging USING gin (activities_text public.gin_trgm_ops);
    CREATE INDEX idx_les_stg_form ON les.entities_staging (legal_form);
    CREATE INDEX idx_les_stg_type ON les.entities_staging (entity_type);
    CREATE INDEX idx_les_stg_year ON les.entities_staging (reg_year DESC NULLS LAST, registered_at DESC);

    ALTER TABLE les.entities_staging SET LOGGED;

    BEGIN;
    DROP TABLE IF EXISTS les.entities;
    ALTER TABLE les.entities_staging RENAME TO entities;
    ALTER TABLE les.entities ADD PRIMARY KEY (regno);
    ALTER INDEX les.idx_les_stg_name_trgm RENAME TO idx_les_name_trgm;
    ALTER INDEX les.idx_les_stg_people_trgm RENAME TO idx_les_people_trgm;
    ALTER INDEX les.idx_les_stg_act_trgm RENAME TO idx_les_act_trgm;
    ALTER INDEX les.idx_les_stg_form RENAME TO idx_les_form;
    ALTER INDEX les.idx_les_stg_type RENAME TO idx_les_type;
    ALTER INDEX les.idx_les_stg_year RENAME TO idx_les_year;
    GRANT SELECT ON les.entities TO fx_reader;
    COMMIT;

    ANALYZE les.entities;
    """
    subprocess.run(
        ["docker", "exec", "-i", "wx-postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "weather", "-c", swap_sql],
        check=True,
    )

    stats_sql = """
    WITH form_counts AS (
      SELECT COALESCE(NULLIF(legal_form, ''), 'Тодорхойгүй') AS label, COUNT(*)::int AS count
      FROM les.entities
      GROUP BY 1
      ORDER BY count DESC
      LIMIT 12
    ),
    type_counts AS (
      SELECT COALESCE(NULLIF(entity_type, ''), 'Тодорхойгүй') AS label, COUNT(*)::int AS count
      FROM les.entities
      GROUP BY 1
      ORDER BY count DESC
    ),
    year_counts AS (
      SELECT reg_year AS year, COUNT(*)::int AS count
      FROM les.entities
      WHERE reg_year IS NOT NULL AND reg_year BETWEEN 1990 AND 2026
      GROUP BY 1
      ORDER BY 1 ASC
    ),
    totals AS (
      SELECT
        COUNT(*)::int AS total_entities,
        COUNT(*) FILTER (WHERE jsonb_array_length(shareholders) > 0)::int AS with_shareholders,
        COUNT(*) FILTER (WHERE jsonb_array_length(executives) > 0)::int AS with_executives,
        COUNT(*) FILTER (WHERE jsonb_array_length(beneficial_owners) > 0)::int AS with_ubo,
        COUNT(*) FILTER (WHERE jsonb_array_length(activities) > 0)::int AS with_activities,
        COUNT(*) FILTER (WHERE jsonb_array_length(reorganizations) > 0)::int AS with_reorg
      FROM les.entities
    )
    SELECT json_build_object(
      'totals', (SELECT row_to_json(totals) FROM totals),
      'by_legal_form', COALESCE((SELECT json_agg(row_to_json(form_counts)) FROM form_counts), '[]'::json),
      'by_entity_type', COALESCE((SELECT json_agg(row_to_json(type_counts)) FROM type_counts), '[]'::json),
      'by_year', COALESCE((SELECT json_agg(row_to_json(year_counts)) FROM year_counts), '[]'::json)
    )::text;
    """
    stats_out = subprocess.check_output(
        ["docker", "exec", "-i", "wx-postgres", "psql", "-t", "-A", "-U", "postgres", "-d", "weather", "-c", stats_sql],
        text=True,
    ).strip()

    meta_sql = f"""
    INSERT INTO les.metadata (id, dataview_id, file_id, file_path, file_size_bytes, source_updated_at, imported_at, total_entities, summary_stats)
    VALUES (
      1,
      {int(meta['dataview_id'] or 0)},
      {int(meta['file_id'] or 0)},
      '{pg_escape_copy(str(meta['file_path']))}',
      {int(meta['file_size'] or 0)},
      '{pg_escape_copy(str(meta['source_updated_at']))}',
      NOW(),
      {imported_count},
      $json${stats_out}$json$::jsonb
    )
    ON CONFLICT (id) DO UPDATE SET
      dataview_id = EXCLUDED.dataview_id,
      file_id = EXCLUDED.file_id,
      file_path = EXCLUDED.file_path,
      file_size_bytes = EXCLUDED.file_size_bytes,
      source_updated_at = EXCLUDED.source_updated_at,
      imported_at = NOW(),
      total_entities = EXCLUDED.total_entities,
      summary_stats = EXCLUDED.summary_stats;
    """
    subprocess.run(
        ["docker", "exec", "-i", "wx-postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "weather", "-c", meta_sql],
        check=True,
    )

    # Remove temporary 440MB file if downloaded to /tmp
    if json_path.parent == Path("/tmp/les_import") and json_path.exists():
        json_path.unlink()

    print(f"DONE! Imported {imported_count:,} legal entities in {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
