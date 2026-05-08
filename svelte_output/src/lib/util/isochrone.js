/**
 * OSM 보행 그래프 기반 이소크론(도달가능 폴리곤) 계산 — 원본 SHIM v6 동등.
 *
 * 그래프 데이터는 `static/infra_graph.json.gz` 에서 fetch.
 *  - n: 노드 수 (~266,780)
 *  - lat_base, lng_base: 좌표 base
 *  - lats/lngs: Uint16Array (base + i × 1e-5)
 *  - row, col: CSR 희소 인접행렬 (Uint32Array)
 *  - dist: Edge weight (Uint16Array, m 단위)
 *
 * 사용:
 *   import { loadGraph, computeIsochrone } from '$lib/util/isochrone.js';
 *   const G = await loadGraph();              // 1회만 (~3 MB fetch)
 *   const ring = computeIsochrone(G, lat, lng, maxDistM);  // [lat,lng][]
 *   L.polygon(ring, { ... }).addTo(map);
 */

/** @typedef {{ n: number, latBase: number, lngBase: number, lats: Float32Array, lngs: Float32Array, row: Uint32Array, col: Uint32Array, dist: Uint16Array }} Graph */

import { inflate } from 'pako';

/** @type {Graph | null} */
let _cached = null;
/** @type {Promise<Graph> | null} */
let _inflight = null;

function b64ToBytes(s) {
	const bin = atob(s);
	const out = new Uint8Array(bin.length);
	for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
	return out;
}

/**
 * 그래프 한 번만 로드 (모듈 캐시). 두 번째 호출부터 즉시 반환.
 * @returns {Promise<Graph>}
 */
export async function loadGraph() {
	if (_cached) return _cached;
	if (_inflight) return _inflight;

	_inflight = (async () => {
		const res = await fetch('/infra_graph.json.gz');
		if (!res.ok) throw new Error('infra_graph.json.gz fetch 실패: ' + res.status);
		const buf = new Uint8Array(await res.arrayBuffer());
		// gz 자동 감지 — 헤더 0x1f 0x8b 면 압축, 아니면 raw json
		const text =
			buf[0] === 0x1f && buf[1] === 0x8b
				? new TextDecoder().decode(inflate(buf))
				: new TextDecoder().decode(buf);
		const j = JSON.parse(text);

		const n = j.n;
		const lat16 = new Uint16Array(inflate(b64ToBytes(j.lats)).buffer);
		const lng16 = new Uint16Array(inflate(b64ToBytes(j.lngs)).buffer);
		const row = new Uint32Array(inflate(b64ToBytes(j.row)).buffer);
		const col = new Uint32Array(inflate(b64ToBytes(j.col)).buffer);
		const dist = new Uint16Array(inflate(b64ToBytes(j.dist)).buffer);

		const lats = new Float32Array(n);
		const lngs = new Float32Array(n);
		for (let i = 0; i < n; i++) {
			lats[i] = j.lat_base + lat16[i] * 1e-5;
			lngs[i] = j.lng_base + lng16[i] * 1e-5;
		}

		_cached = { n, latBase: j.lat_base, lngBase: j.lng_base, lats, lngs, row, col, dist };
		return _cached;
	})();

	return _inflight;
}

/** 최근접 그래프 노드 (유클리드 근사) */
export function nearestNode(G, lat, lng) {
	let best = 0,
		bestD = Infinity;
	const dLat = 111320;
	const dLng = 111320 * Math.cos((lat * Math.PI) / 180);
	const { lats, lngs, n } = G;
	for (let i = 0; i < n; i++) {
		const dy = (lats[i] - lat) * dLat;
		const dx = (lngs[i] - lng) * dLng;
		const d = dy * dy + dx * dx;
		if (d < bestD) {
			bestD = d;
			best = i;
		}
	}
	return best;
}

/** Min-Heap (이진 힙, [dist, node] 페어 저장) */
class MinHeap {
	constructor() {
		/** @type {[number, number][]} */
		this.h = [];
	}
	push(dist, node) {
		this.h.push([dist, node]);
		this._up(this.h.length - 1);
	}
	pop() {
		const top = this.h[0];
		const last = this.h.pop();
		if (this.h.length && last) {
			this.h[0] = last;
			this._down(0);
		}
		return top;
	}
	get size() {
		return this.h.length;
	}
	_up(i) {
		const h = this.h;
		while (i > 0) {
			const p = (i - 1) >> 1;
			if (h[p][0] <= h[i][0]) break;
			[h[p], h[i]] = [h[i], h[p]];
			i = p;
		}
	}
	_down(i) {
		const h = this.h;
		const n = h.length;
		while (true) {
			let s = i,
				l = 2 * i + 1,
				r = 2 * i + 2;
			if (l < n && h[l][0] < h[s][0]) s = l;
			if (r < n && h[r][0] < h[s][0]) s = r;
			if (s === i) break;
			[h[s], h[i]] = [h[i], h[s]];
			i = s;
		}
	}
}

/** Dijkstra → maxDistM 이내 도달 가능한 노드 인덱스 배열 */
export function dijkstra(G, srcNode, maxDistM) {
	const { n, row, col, dist } = G;
	const out = new Float32Array(n).fill(Infinity);
	out[srcNode] = 0;
	const pq = new MinHeap();
	pq.push(0, srcNode);
	const reachable = [];
	while (pq.size > 0) {
		const top = pq.pop();
		if (!top) break;
		const [d, u] = top;
		if (d > out[u]) continue;
		if (d > maxDistM) break;
		reachable.push(u);
		const start = row[u],
			end = row[u + 1];
		for (let e = start; e < end; e++) {
			const v = col[e];
			const nd = d + dist[e];
			if (nd < out[v]) {
				out[v] = nd;
				if (nd <= maxDistM) pq.push(nd, v);
			}
		}
	}
	return reachable;
}

/**
 * Convex Hull (Graham scan) — 도달 가능 노드 → 폴리곤 ring [lat,lng]
 * @returns {[number, number][] | null}
 */
export function reachableToPolygon(G, reachable) {
	if (reachable.length < 4) return null;
	const { lats, lngs } = G;
	/** @type {[number, number][]} [lng, lat] */
	const pts = reachable.map((i) => [lngs[i], lats[i]]);
	pts.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
	const cross = (O, A, B) => (A[0] - O[0]) * (B[1] - O[1]) - (A[1] - O[1]) * (B[0] - O[0]);
	const n = pts.length;
	const hull = [];
	for (let i = 0; i < n; i++) {
		while (
			hull.length >= 2 &&
			cross(hull[hull.length - 2], hull[hull.length - 1], pts[i]) <= 0
		)
			hull.pop();
		hull.push(pts[i]);
	}
	const lower = hull.length;
	for (let i = n - 2; i >= 0; i--) {
		while (
			hull.length > lower &&
			cross(hull[hull.length - 2], hull[hull.length - 1], pts[i]) <= 0
		)
			hull.pop();
		hull.push(pts[i]);
	}
	hull.pop();
	if (hull.length < 3) return null;
	const ring = hull.map((p) => /** @type {[number,number]} */ ([p[1], p[0]]));
	ring.push(ring[0]);
	return ring;
}

/**
 * 한 번에 도달 폴리곤 계산 (lat/lng → polygon ring).
 * @param {Graph} G
 * @param {number} lat
 * @param {number} lng
 * @param {number} maxDistM
 * @returns {{ ring: [number,number][] | null, count: number, ms: number }}
 */
export function computeIsochrone(G, lat, lng, maxDistM) {
	const t0 = performance.now();
	const src = nearestNode(G, lat, lng);
	const reachable = dijkstra(G, src, maxDistM);
	const ring = reachableToPolygon(G, reachable);
	return { ring, count: reachable.length, ms: Math.round(performance.now() - t0) };
}
