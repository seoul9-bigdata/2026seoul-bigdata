"""
G8 Phase 1: transit.json 의 각 항목에 `gu` (자치구명) 필드 추가

전략:
  1. climate.json 의 GU_GEO (FeatureCollection) 로 25개 자치구 polygon 구성
  2. stations / climate 는 sgg_cd (법정동 5자리 코드) 가 있으면 정적 매핑 우선 사용
  3. 그 외 또는 sgg_cd 가 null 이면 point-in-polygon (STRtree) fallback
  4. anchors 는 `gu` 가 이미 있으므로 손대지 않음
  5. od_stations 는 ride_gu / goff_gu 두 필드 추가
  6. xfer_breakdown / chain_breakdown 은 dict 이고 lat/lng 없어 건드리지 않음

저장: 원본과 동일한 minified (indent 없음, ensure_ascii=False)
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree


# ---- 경로 ------------------------------------------------------------------
ROOT = Path("/Users/saroro/GitHub/prototype-seoul/svelte_output")
DATA_DIR = ROOT / "src" / "lib" / "data"
CLIMATE_JSON = DATA_DIR / "climate.json"
TRANSIT_JSON = DATA_DIR / "transit.json"
TRANSIT_BAK = DATA_DIR / "transit.json.bak"


# ---- sgg_cd -> 자치구명 정적 매핑 (서울 25 자치구 법정동 코드) -----------------
SGG_CD_TO_GU: dict[str, str] = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}


def build_spatial_index(geojson: dict) -> tuple[STRtree, list[object], list[str]]:
    """GU_GEO FeatureCollection -> STRtree + polygons + names (인덱스로 정렬)."""
    polys: list[object] = []
    names: list[str] = []
    for feat in geojson["features"]:
        nm = feat["properties"].get("nm")
        if not nm:
            raise RuntimeError(f"feature properties missing 'nm': {feat['properties']}")
        polys.append(shape(feat["geometry"]))
        names.append(nm)
    tree = STRtree(polys)
    return tree, polys, names


def gu_from_point(lat, lon, tree: STRtree, polys: list[object], names: list[str]) -> str | None:
    """lat/lng -> 자치구명 (없으면 None). lat 이 None / NaN 이면 None."""
    if lat is None or lon is None:
        return None
    try:
        latf = float(lat)
        lonf = float(lon)
    except (TypeError, ValueError):
        return None
    if latf != latf or lonf != lonf:  # NaN check
        return None
    pt = Point(lonf, latf)  # GeoJSON 은 (lon, lat) 순서
    # STRtree.query 는 후보 인덱스 배열 반환 (shapely 2.x)
    candidates = tree.query(pt)
    for idx in candidates:
        if polys[idx].contains(pt) or polys[idx].intersects(pt):
            return names[int(idx)]
    return None


def gu_from_sgg_cd(sgg_cd) -> str | None:
    if sgg_cd is None:
        return None
    key = str(sgg_cd).strip()
    if not key:
        return None
    # 5자리 zero-pad (혹시 정수면)
    if key.isdigit() and len(key) < 5:
        key = key.zfill(5)
    return SGG_CD_TO_GU.get(key)


def process_stations(rows, tree, polys, names):
    """stations / climate 공통: sgg_cd 우선, fallback point-in-polygon. lat/lon."""
    stats = {"by_sgg": 0, "by_pip": 0, "missing": 0}
    misses: list[dict] = []
    counter: Counter = Counter()
    for r in rows:
        gu = gu_from_sgg_cd(r.get("sgg_cd"))
        if gu:
            stats["by_sgg"] += 1
        else:
            gu = gu_from_point(r.get("lat"), r.get("lon"), tree, polys, names)
            if gu:
                stats["by_pip"] += 1
            else:
                stats["missing"] += 1
                if len(misses) < 3:
                    misses.append({
                        "sgg_cd": r.get("sgg_cd"),
                        "lat": r.get("lat"),
                        "lon": r.get("lon"),
                        "name": r.get("sttn_nm") or r.get("name"),
                    })
        r["gu"] = gu
        if gu:
            counter[gu] += 1
    return stats, misses, counter


def process_latlng(rows, tree, polys, names, lat_key="lat", lon_key="lng", out_key="gu"):
    """heat / emergency: lat/lng 만 있음."""
    stats = {"by_pip": 0, "missing": 0}
    misses: list[dict] = []
    counter: Counter = Counter()
    for r in rows:
        gu = gu_from_point(r.get(lat_key), r.get(lon_key), tree, polys, names)
        if gu:
            stats["by_pip"] += 1
            counter[gu] += 1
        else:
            stats["missing"] += 1
            if len(misses) < 3:
                misses.append({
                    "lat": r.get(lat_key),
                    "lng": r.get(lon_key),
                    "name": r.get("name"),
                })
        r[out_key] = gu
    return stats, misses, counter


def process_od_stations(rows, tree, polys, names):
    """od_stations: ride_gu / goff_gu 두 필드."""
    stats = {"ride_ok": 0, "ride_miss": 0, "goff_ok": 0, "goff_miss": 0}
    misses: list[dict] = []
    counter_ride: Counter = Counter()
    counter_goff: Counter = Counter()
    for r in rows:
        ride_gu = gu_from_point(r.get("ride_lat"), r.get("ride_lon"), tree, polys, names)
        goff_gu = gu_from_point(r.get("goff_lat"), r.get("goff_lon"), tree, polys, names)
        r["ride_gu"] = ride_gu
        r["goff_gu"] = goff_gu
        if ride_gu:
            stats["ride_ok"] += 1
            counter_ride[ride_gu] += 1
        else:
            stats["ride_miss"] += 1
            if len(misses) < 3:
                misses.append({"side": "ride", "lat": r.get("ride_lat"), "lon": r.get("ride_lon"), "name": r.get("ride_nm")})
        if goff_gu:
            stats["goff_ok"] += 1
            counter_goff[goff_gu] += 1
        else:
            stats["goff_miss"] += 1
            if len(misses) < 3:
                misses.append({"side": "goff", "lat": r.get("goff_lat"), "lon": r.get("goff_lon"), "name": r.get("goff_nm")})
    return stats, misses, counter_ride, counter_goff


def top_bottom(counter: Counter, n=5) -> tuple[list, list]:
    items = counter.most_common()
    top = items[:n]
    bottom = items[-n:] if len(items) >= n else items
    return top, bottom


def main() -> int:
    print(f"[1/6] load climate GU_GEO: {CLIMATE_JSON}")
    with CLIMATE_JSON.open("r", encoding="utf-8") as f:
        climate = json.load(f)
    gu_geo = climate.get("GU_GEO")
    if not gu_geo:
        print("ERROR: GU_GEO not found in climate.json", file=sys.stderr)
        return 1
    feats = gu_geo.get("features", [])
    print(f"  features: {len(feats)}")

    # sgg_cd 매핑 검증 — 한두 개 sample 출력
    print(f"  sgg_cd mapping sample: 11620 -> {SGG_CD_TO_GU.get('11620')} (expect 관악구)")
    print(f"  sgg_cd mapping sample: 11680 -> {SGG_CD_TO_GU.get('11680')} (expect 강남구)")
    # GU_GEO 자치구명 일치 검증
    gu_geo_names = {feat["properties"]["nm"] for feat in feats}
    mapping_names = set(SGG_CD_TO_GU.values())
    if mapping_names != gu_geo_names:
        only_geo = gu_geo_names - mapping_names
        only_map = mapping_names - gu_geo_names
        print(f"  WARN gu set diff: only_geo={only_geo} only_map={only_map}")
    else:
        print(f"  gu name sets match (25/25)")

    print(f"[2/6] build spatial index (STRtree)")
    tree, polys, names = build_spatial_index(gu_geo)

    print(f"[3/6] load transit.json: {TRANSIT_JSON}")
    size_before = TRANSIT_JSON.stat().st_size
    with TRANSIT_JSON.open("r", encoding="utf-8") as f:
        transit = json.load(f)
    DATA = transit["DATA"]

    # 처리
    print(f"[4/6] process datasets")
    counters: dict[str, Counter] = {}
    report: dict[str, dict] = {}

    # stations (sgg_cd + lat/lon)
    s_stats, s_misses, s_counter = process_stations(DATA["stations"], tree, polys, names)
    total = len(DATA["stations"])
    matched = s_stats["by_sgg"] + s_stats["by_pip"]
    report["stations"] = {
        "total": total,
        "matched": matched,
        "missing": s_stats["missing"],
        "by_sgg": s_stats["by_sgg"],
        "by_pip": s_stats["by_pip"],
        "misses": s_misses,
    }
    counters["stations"] = s_counter

    # climate
    c_stats, c_misses, c_counter = process_stations(DATA["climate"], tree, polys, names)
    total = len(DATA["climate"])
    matched = c_stats["by_sgg"] + c_stats["by_pip"]
    report["climate"] = {
        "total": total,
        "matched": matched,
        "missing": c_stats["missing"],
        "by_sgg": c_stats["by_sgg"],
        "by_pip": c_stats["by_pip"],
        "misses": c_misses,
    }
    counters["climate"] = c_counter

    # heat (lat/lng)
    h_stats, h_misses, h_counter = process_latlng(DATA["heat"], tree, polys, names, "lat", "lng", "gu")
    report["heat"] = {
        "total": len(DATA["heat"]),
        "matched": h_stats["by_pip"],
        "missing": h_stats["missing"],
        "misses": h_misses,
    }
    counters["heat"] = h_counter

    # emergency (lat/lng)
    e_stats, e_misses, e_counter = process_latlng(DATA["emergency"], tree, polys, names, "lat", "lng", "gu")
    report["emergency"] = {
        "total": len(DATA["emergency"]),
        "matched": e_stats["by_pip"],
        "missing": e_stats["missing"],
        "misses": e_misses,
    }
    counters["emergency"] = e_counter

    # od_stations (ride/goff)
    od_stats, od_misses, od_ride_c, od_goff_c = process_od_stations(DATA["od_stations"], tree, polys, names)
    report["od_stations"] = {
        "total": len(DATA["od_stations"]),
        "ride_ok": od_stats["ride_ok"],
        "ride_miss": od_stats["ride_miss"],
        "goff_ok": od_stats["goff_ok"],
        "goff_miss": od_stats["goff_miss"],
        "misses": od_misses,
    }
    counters["od_stations:ride"] = od_ride_c
    counters["od_stations:goff"] = od_goff_c

    # anchors: gu 가 비어있는 케이스(86건)만 lat/lon 으로 fill — 기존 값 보존
    a_filled = 0
    a_kept = 0
    a_missing = 0
    a_counter: Counter = Counter()
    a_misses: list[dict] = []
    for r in DATA["anchors"]:
        cur_gu = r.get("gu")
        if isinstance(cur_gu, str) and cur_gu.strip():
            a_kept += 1
            a_counter[cur_gu] += 1
        else:
            gu = gu_from_point(r.get("lat"), r.get("lon"), tree, polys, names)
            if gu:
                r["gu"] = gu
                a_filled += 1
                a_counter[gu] += 1
            else:
                a_missing += 1
                if len(a_misses) < 3:
                    a_misses.append({"lat": r.get("lat"), "lon": r.get("lon"), "name": r.get("name")})
    report["anchors"] = {
        "total": len(DATA["anchors"]),
        "kept": a_kept,
        "filled": a_filled,
        "missing": a_missing,
        "misses": a_misses,
    }
    counters["anchors"] = a_counter
    print(f"  anchors: kept={a_kept} filled={a_filled} missing={a_missing} (total {len(DATA['anchors'])})")

    print(f"  xfer_breakdown: dict ({len(DATA['xfer_breakdown'])} keys) (untouched — no lat/lng)")
    print(f"  chain_breakdown: dict ({len(DATA['chain_breakdown'])} keys) (untouched — no lat/lng)")

    # 백업 + 저장
    print(f"[5/6] backup + write")
    if not TRANSIT_BAK.exists():
        shutil.copy2(TRANSIT_JSON, TRANSIT_BAK)
        print(f"  backup: {TRANSIT_BAK} (size {TRANSIT_BAK.stat().st_size})")
    else:
        print(f"  backup already exists at {TRANSIT_BAK} — not overwriting")

    # minified, ensure_ascii=False
    with TRANSIT_JSON.open("w", encoding="utf-8") as f:
        json.dump(transit, f, ensure_ascii=False, separators=(",", ":"))
    size_after = TRANSIT_JSON.stat().st_size
    print(f"  size_before={size_before} size_after={size_after} delta={size_after - size_before:+d}")

    # 보고
    print(f"[6/6] report")
    for ds, info in report.items():
        print(f"  --- {ds} ---")
        print(f"    total={info['total']}  matched={info.get('matched', '-')}  missing={info.get('missing', '-')}")
        if "by_sgg" in info:
            print(f"    by_sgg={info['by_sgg']} by_pip={info['by_pip']}")
        if "ride_ok" in info:
            print(f"    ride_ok={info['ride_ok']} ride_miss={info['ride_miss']} goff_ok={info['goff_ok']} goff_miss={info['goff_miss']}")
        if info.get("misses"):
            print(f"    miss samples:")
            for m in info["misses"]:
                print(f"      {m}")
    print()
    print("  자치구별 분포 (top 5 / bottom 5):")
    for ds, c in counters.items():
        if not c:
            continue
        top, bot = top_bottom(c)
        print(f"    [{ds}] total_gu={len(c)}")
        print(f"      top5    : {top}")
        print(f"      bottom5 : {bot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
