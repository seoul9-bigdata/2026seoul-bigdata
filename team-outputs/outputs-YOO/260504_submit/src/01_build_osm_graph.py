"""
01_build_osm_graph.py — 서울 보행 OSM 그래프 다운로드

KIM(`outputs-KIM/260418_submit/src/00_build_graph.py`) 차용.
출력: cache/seoul_walk.graphml (200~400MB, 10~20분)

이미 cache에 파일 있으면 즉시 로드.
"""
import time
import logging
from pathlib import Path

import osmnx as ox

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
CACHE.mkdir(exist_ok=True)
GRAPHML = CACHE / "seoul_walk.graphml"


def build():
    if GRAPHML.exists():
        log.info("기존 graphml 로드: %s", GRAPHML)
        G = ox.load_graphml(str(GRAPHML))
        log.info("로드 완료 — 노드 %d / 엣지 %d",
                 G.number_of_nodes(), G.number_of_edges())
        return G

    log.info("서울 보행 네트워크 다운로드 시작 (osmnx)…")
    log.info("예상 10~20분")
    t0 = time.time()
    G = ox.graph_from_place(
        "Seoul, South Korea",
        network_type="walk",
        simplify=True,
        retain_all=False,
    )
    log.info("다운로드 완료 (%.1fs) — 노드 %d / 엣지 %d",
             time.time() - t0, G.number_of_nodes(), G.number_of_edges())

    log.info("저장: %s", GRAPHML)
    ox.save_graphml(G, str(GRAPHML))
    log.info("저장 완료")
    return G


if __name__ == "__main__":
    G = build()
    # 커버리지 검증
    import pyproj  # noqa
    checkpoints = [
        ("강동구 길동사거리", 127.1435, 37.5415),
        ("노원구 상계역",     127.0655, 37.6561),
        ("서울시청",         126.9779, 37.5665),
        ("관악구 신림역",    126.9228, 37.4845),
        ("강서구 화곡역",    126.8551, 37.5493),
    ]
    log.info("\n=== 커버리지 ===")
    for name, lon, lat in checkpoints:
        node = ox.distance.nearest_nodes(G, lon, lat)
        nx_, ny_ = G.nodes[node]["x"], G.nodes[node]["y"]
        d = ((nx_ - lon) ** 2 + (ny_ - lat) ** 2) ** 0.5 * 111000
        flag = "OK" if d < 500 else "WARN"
        log.info("  %s %s — 최근접 %.0fm", flag, name, d)
    print(f"\nDONE: {GRAPHML}")
