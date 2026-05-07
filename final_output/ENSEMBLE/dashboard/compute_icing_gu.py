"""
구별 결빙 취약 도로 노드 비율 계산
- HTML에서 JISEOL(제설함), GU_GEO(구 경계) 추출
- osmnx로 서울 도로 네트워크 다운로드
- 각 노드가 제설함 100m/200m 버퍼 밖(=결빙 취약)인지 체크
- ICING_GU JS 상수 출력
"""

import re, json, sys
import osmnx as ox
import geopandas as gpd
import numpy as np
from scipy.spatial import KDTree
from shapely.geometry import shape

HTML_PATH = "1_Kim_climate_opt.html"

# ── 1. HTML에서 JISEOL, GU_GEO 추출 ─────────────────────────────────────────
print("HTML 데이터 추출 중...", flush=True)

with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
s = scripts[2]

# JISEOL
m = re.search(r"const JISEOL\s*=\s*(\[.*?\]);", s, re.DOTALL)
JISEOL = json.loads(m.group(1))
print(f"  JISEOL: {len(JISEOL)}개")

# GU_GEO
m = re.search(r"const GU_GEO\s*=\s*(\{.*?\});(?=\s*\nconst )", s, re.DOTALL)
GU_GEO = json.loads(m.group(1))
print(f"  GU_GEO features: {len(GU_GEO['features'])}개")

# GU_META (cd ↔ nm 매핑)
m = re.search(r"const GU_META\s*=\s*(\[.*?\]);", s, re.DOTALL)
GU_META = json.loads(m.group(1))
gu_cd_by_nm = {g["nm"]: g["cd"] for g in GU_META}
gu_nm_by_cd = {g["cd"]: g["nm"] for g in GU_META}
print(f"  GU_META: {len(GU_META)}개")

# ── 2. GU_GEO → GeoDataFrame (WGS84) ────────────────────────────────────────
gu_gdf = gpd.GeoDataFrame.from_features(GU_GEO["features"], crs="EPSG:4326")
gu_utm = gu_gdf.to_crs("EPSG:32652")   # UTM Zone 52N (한국)

# ── 3. osmnx 서울 도로 네트워크 다운로드 ─────────────────────────────────────
print("osmnx 서울 도로 네트워크 다운로드 중... (수 분 소요)", flush=True)
G = ox.graph_from_place("Seoul, South Korea", network_type="all")
nodes_gdf, _ = ox.graph_to_gdfs(G)
nodes_gdf = nodes_gdf.to_crs("EPSG:32652")
print(f"  도로 노드: {len(nodes_gdf)}개")

# ── 4. 구별 계산 ─────────────────────────────────────────────────────────────
print("구별 취약 비율 계산 중...", flush=True)

# JISEOL → numpy 배열 (UTM)
jiseol_gdf = gpd.GeoDataFrame(
    JISEOL,
    geometry=gpd.points_from_xy([j["lng"] for j in JISEOL], [j["lat"] for j in JISEOL]),
    crs="EPSG:4326"
).to_crs("EPSG:32652")

jiseol_xy = np.column_stack([jiseol_gdf.geometry.x, jiseol_gdf.geometry.y])
jiseol_gu = [j["gu"] for j in JISEOL]  # 구 이름

ICING_GU = {}

for _, gu_row in gu_utm.iterrows():
    cd   = gu_row["cd"]
    nm   = gu_row["nm"]
    geom = gu_row.geometry

    # 해당 구 노드
    gu_nodes = nodes_gdf[nodes_gdf.geometry.within(geom)]
    n_nodes = len(gu_nodes)
    if n_nodes == 0:
        ICING_GU[cd] = dict(nm=nm, vuln100=100.0, vuln200=100.0, nodes=0, jiseol=0)
        continue

    nodes_xy = np.column_stack([gu_nodes.geometry.x, gu_nodes.geometry.y])

    # 해당 구 JISEOL (gu 필드 기준 + bbox 여유)
    gu_jiseol_mask = [g == nm for g in jiseol_gu]
    gu_jiseol_xy   = jiseol_xy[gu_jiseol_mask]
    n_jiseol = len(gu_jiseol_xy)

    if n_jiseol == 0:
        ICING_GU[cd] = dict(nm=nm, vuln100=100.0, vuln200=100.0, nodes=n_nodes, jiseol=0)
        continue

    # KDTree로 최근접 제설함까지 거리
    tree = KDTree(gu_jiseol_xy)
    dists, _ = tree.query(nodes_xy, k=1)

    vuln100 = round(float(np.mean(dists > 100)) * 100, 1)
    vuln200 = round(float(np.mean(dists > 200)) * 100, 1)

    ICING_GU[cd] = dict(nm=nm, vuln100=vuln100, vuln200=vuln200, nodes=n_nodes, jiseol=n_jiseol)
    print(f"  {nm}: 취약100={vuln100}%, 취약200={vuln200}%, 노드={n_nodes}, 제설함={n_jiseol}", flush=True)

# ── 5. 출력 ───────────────────────────────────────────────────────────────────
print("\n=== ICING_GU JS 상수 ===")
lines = []
for cd, d in sorted(ICING_GU.items()):
    lines.append(
        f'  "{cd}": {{'
        f'nm:"{d["nm"]}", vuln100:{d["vuln100"]}, vuln200:{d["vuln200"]}, '
        f'nodes:{d["nodes"]}, jiseol:{d["jiseol"]}}}'
    )
js_const = "const ICING_GU = {\n" + ",\n".join(lines) + "\n};"
print(js_const)

# 파일로도 저장
with open("icing_gu_result.js", "w", encoding="utf-8") as f:
    f.write(js_const + "\n")
print("\n-> icing_gu_result.js 저장 완료")
