"""
의료 시설(병의원·약국) 좌표 데이터를 CSV에서 추출하여
svelte_output/src/lib/data/medical_facilities.json 으로 변환.

병의원: WGS84 (EPSG:4326) 직접 사용
약국: EPSG:5174 → WGS84 변환 (pyproj)
"""

import json
import math
import pandas as pd
from pathlib import Path
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_FILE = ROOT / "svelte_output" / "src" / "lib" / "data" / "medical_facilities.json"

HOSP_CSV = DATA_DIR / "서울시 병의원 위치 정보.csv"
PHARM_CSV = DATA_DIR / "서울시 약국 인허가 정보.csv"

HOSP_TYPES = {"의원", "병원", "보건소", "종합병원"}

# EPSG:5174 → WGS84
t5174 = Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)


def load_hospitals():
    df = pd.read_csv(HOSP_CSV, encoding="cp949")
    df = df[df["병원분류명"].isin(HOSP_TYPES)].copy()
    df = df.dropna(subset=["병원경도", "병원위도"])
    df["병원경도"] = pd.to_numeric(df["병원경도"], errors="coerce")
    df["병원위도"] = pd.to_numeric(df["병원위도"], errors="coerce")
    df = df.dropna(subset=["병원경도", "병원위도"])
    # 서울 영역 (WGS84 bbox)
    df = df[
        (df["병원경도"] >= 126.7) & (df["병원경도"] <= 127.2) &
        (df["병원위도"] >= 37.4) & (df["병원위도"] <= 37.7)
    ]
    result = []
    for _, r in df.iterrows():
        result.append({
            "lat": round(r["병원위도"], 6),
            "lng": round(r["병원경도"], 6),
            "name": str(r["기관명"]).strip(),
            "sub": str(r["병원분류명"]).strip(),
        })
    return result


def load_pharmacies():
    df = pd.read_csv(PHARM_CSV, encoding="cp949")
    df = df[
        (df["영업상태명"] == "영업/정상") &
        df["도로명주소"].str.startswith("서울", na=False)
    ].copy()
    df["px"] = pd.to_numeric(df["좌표정보(X)"].astype(str).str.strip(), errors="coerce")
    df["py"] = pd.to_numeric(df["좌표정보(Y)"].astype(str).str.strip(), errors="coerce")
    df = df.dropna(subset=["px", "py"])
    # EPSG:5174 → WGS84 (always_xy: X=경도방향, Y=위도방향)
    lngs, lats = t5174.transform(df["px"].values, df["py"].values)
    df["wgs_lat"] = lats
    df["wgs_lng"] = lngs
    # 서울 영역 필터
    df = df[
        (df["wgs_lng"] >= 126.7) & (df["wgs_lng"] <= 127.2) &
        (df["wgs_lat"] >= 37.4) & (df["wgs_lat"] <= 37.7)
    ]
    result = []
    for _, r in df.iterrows():
        if math.isfinite(r["wgs_lat"]) and math.isfinite(r["wgs_lng"]):
            result.append({
                "lat": round(r["wgs_lat"], 6),
                "lng": round(r["wgs_lng"], 6),
                "name": str(r["사업장명"]).strip(),
            })
    return result


def main():
    print("병의원 추출 중...")
    hosp = load_hospitals()
    print(f"  → {len(hosp)}개")

    print("약국 추출 중...")
    pharm = load_pharmacies()
    print(f"  → {len(pharm)}개")

    out = {"HOSP": hosp, "PHARM": pharm}
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = OUT_FILE.stat().st_size / 1024
    print(f"\n출력: {OUT_FILE}")
    print(f"파일 크기: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
