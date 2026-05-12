<script>
	import { onMount, onDestroy } from 'svelte';
	import data from '$lib/data/transit.json';
	import 'leaflet/dist/leaflet.css';

	const D = data.DATA;
	const OD = D.od_stations;

	let { active = true, cG = '전체' } = $props();

	let mapEl = $state();
	let map;
	let L;
	let odLayer;

	// cG 필터링 제거: 40건 전체 항상 표시, cG 와 관련된 OD 만 시각적 강조
	function isRelated(o) {
		return cG !== '전체' && (o.ride_gu === cG || o.goff_gu === cG);
	}
	const hasFilter = $derived(cG !== '전체');

	function colorN(n) {
		if (n >= 20) return '#ff5f5f';
		if (n >= 13) return '#f5b740';
		if (n >= 8) return '#5aadff';
		return '#b48ef4';
	}
	function widthN(n) {
		return Math.sqrt(n) * 1.4;
	}

	function bezier(lat1, lon1, lat2, lon2, n = 24, curv = 0.18) {
		const mx = (lon1 + lon2) / 2;
		const my = (lat1 + lat2) / 2;
		const dx = lon2 - lon1;
		const dy = lat2 - lat1;
		const len = Math.hypot(dx, dy) || 1;
		const offX = (-dy / len) * curv * len;
		const offY = (dx / len) * curv * len;
		const cx = mx + offX;
		const cy = my + offY;
		const pts = [];
		for (let i = 0; i <= n; i++) {
			const t = i / n;
			const x = (1 - t) ** 2 * lon1 + 2 * (1 - t) * t * cx + t ** 2 * lon2;
			const y = (1 - t) ** 2 * lat1 + 2 * (1 - t) * t * cy + t ** 2 * lat2;
			pts.push([y, x]);
		}
		return pts;
	}

	const sortedOD = $derived([...OD].sort((a, b) => b.n - a.n));

	function popupHtml(o) {
		return `
			<div style="font-family:inherit;min-width:200px">
				<b style="font-size:12px;color:#888780">환승 OD pair</b>
				<div style="font-size:13px;color:#2c2c2a;margin-top:4px">
					🟢 ${o.ride_nm}<br>
					⬇<br>
					🔴 ${o.goff_nm}
				</div>
				<div style="font-size:11px;color:#185fa5;margin-top:6px">
					환승 노인 <b>${o.n}</b>회
				</div>
				<div style="font-size:10px;color:#888780;margin-top:2px">
					${o.ride_kind === 'bus' ? '버스' : '지하철'} → ${o.goff_kind === 'bus' ? '버스' : '지하철'}
				</div>
			</div>`;
	}

	function buildLayer() {
		if (!L || !map) return;
		if (odLayer) map.removeLayer(odLayer);
		odLayer = L.layerGroup();

		// 베지어 곡선 — 비관련 먼저, 관련은 마지막에 그려 위에 올림
		const dimOD = sortedOD.filter((o) => !isRelated(o));
		const hotOD = sortedOD.filter((o) => isRelated(o));
		const drawOrder = hasFilter ? [...dimOD, ...hotOD] : sortedOD;

		drawOrder.forEach((o) => {
			if (!o.ride_lat || !o.goff_lat) return;
			const pts = bezier(o.ride_lat, o.ride_lon, o.goff_lat, o.goff_lon);
			const col = colorN(o.n);
			const w = widthN(o.n);
			const related = isRelated(o);
			const style = hasFilter
				? related
					? { color: col, weight: w + 1.5, opacity: 1.0 }
					: { color: col, weight: Math.max(1.2, w * 0.7), opacity: 0.22 }
				: { color: col, weight: w, opacity: 0.7 };
			L.polyline(pts, style)
				.bindPopup(popupHtml(o))
				.addTo(odLayer);
		});

		// 출발 점 (초록): 정류장 단위 집계 + 해당 정류장이 cG 관련 OD 에 포함되는지 표시
		const rideMap = new Map();
		sortedOD.forEach((o) => {
			const k = `${o.ride_lat},${o.ride_lon}`;
			if (!rideMap.has(k))
				rideMap.set(k, { ...o, sumN: 0, count: 0, related: false });
			const r = rideMap.get(k);
			r.sumN += o.n;
			r.count++;
			if (isRelated(o)) r.related = true;
		});
		const rideArr = [...rideMap.values()];
		const rideOrder = hasFilter
			? [...rideArr.filter((r) => !r.related), ...rideArr.filter((r) => r.related)]
			: rideArr;
		rideOrder.forEach((r) => {
			const dim = hasFilter && !r.related;
			L.circleMarker([r.ride_lat, r.ride_lon], {
				radius: Math.max(7, Math.min(15, 7 + r.sumN / 8)),
				fillColor: '#3ecfa0',
				color: '#fff',
				weight: dim ? 1 : 1.5,
				fillOpacity: dim ? 0.3 : 0.9,
				opacity: dim ? 0.4 : 1
			})
				.bindPopup(
					`<div style="font-family:inherit"><b>🟢 ${r.ride_nm}</b><br><span style="font-size:11px;color:#888780">출발 ${r.count}건 · 합계 ${r.sumN}회</span></div>`
				)
				.addTo(odLayer);
		});

		// 도착 점 (분홍)
		const goffMap = new Map();
		sortedOD.forEach((o) => {
			const k = `${o.goff_lat},${o.goff_lon}`;
			if (!goffMap.has(k))
				goffMap.set(k, { ...o, sumN: 0, count: 0, related: false });
			const g = goffMap.get(k);
			g.sumN += o.n;
			g.count++;
			if (isRelated(o)) g.related = true;
		});
		const goffArr = [...goffMap.values()];
		const goffOrder = hasFilter
			? [...goffArr.filter((g) => !g.related), ...goffArr.filter((g) => g.related)]
			: goffArr;
		goffOrder.forEach((g) => {
			const dim = hasFilter && !g.related;
			L.circleMarker([g.goff_lat, g.goff_lon], {
				radius: Math.max(6, Math.min(12, 6 + g.sumN / 9)),
				fillColor: '#f472b6',
				color: '#fff',
				weight: dim ? 0.8 : 1.2,
				fillOpacity: dim ? 0.28 : 0.85,
				opacity: dim ? 0.4 : 1
			})
				.bindPopup(
					`<div style="font-family:inherit"><b>🔴 ${g.goff_nm}</b><br><span style="font-size:11px;color:#888780">도착 ${g.count}건 · 합계 ${g.sumN}회</span></div>`
				)
				.addTo(odLayer);
		});

		odLayer.addTo(map);
	}

	function panToOD(o) {
		if (!map) return;
		const midLat = (o.ride_lat + o.goff_lat) / 2;
		const midLon = (o.ride_lon + o.goff_lon) / 2;
		map.setView([midLat, midLon], 13, { animate: true });
		L.popup({ offset: [0, -6] }).setLatLng([midLat, midLon]).setContent(popupHtml(o)).openOn(map);
	}

	function zoomToFiltered() {
		if (!L || !map) return;
		if (cG === '전체') {
			map.setView([37.5665, 126.978], 11, { animate: true });
			return;
		}
		const pts = [];
		sortedOD.forEach((o) => {
			if (!isRelated(o)) return;
			if (o.ride_lat && o.ride_lon) pts.push([o.ride_lat, o.ride_lon]);
			if (o.goff_lat && o.goff_lon) pts.push([o.goff_lat, o.goff_lon]);
		});
		if (pts.length === 0) return;
		const lats = pts.map((p) => p[0]);
		const lons = pts.map((p) => p[1]);
		const bounds = L.latLngBounds([
			[Math.min(...lats), Math.min(...lons)],
			[Math.max(...lats), Math.max(...lons)]
		]);
		map.fitBounds(bounds.pad(0.15));
	}

	onMount(async () => {
		if (typeof window === 'undefined') return;
		L = (await import('leaflet')).default;
		map = L.map(mapEl, { zoomControl: true }).setView([37.5665, 126.978], 11);
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			attribution: '© CARTO',
			subdomains: 'abcd',
			maxZoom: 19
		}).addTo(map);
		buildLayer();
	});

	onDestroy(() => map?.remove());

	$effect(() => {
		if (active && map) setTimeout(() => map.invalidateSize(), 0);
	});

	// cG 변경 시: 베지어 곡선 재구성 + 지도 줌
	$effect(() => {
		void cG;
		void sortedOD;
		if (!map) return;
		buildLayer();
		zoomToFiltered();
	});
</script>

<div class="r2">
	<div class="card">
		<div class="ct">노인 환승 OD — 베지어 곡선 (출발 → 도착 정류장 흐름)</div>
		<div class="map-wrap">
			<div bind:this={mapEl} class="lmap"></div>
		</div>
		<div class="leg">
			<div class="li"><span class="dot" style:background="#3ecfa0"></span>🟢 출발 정류장</div>
			<div class="li"><span class="dot" style:background="#f472b6"></span>🔴 도착 정류장</div>
			<div class="li"><span class="bar" style:background="#ff5f5f"></span>≥20회</div>
			<div class="li"><span class="bar" style:background="#f5b740"></span>13–19</div>
			<div class="li"><span class="bar" style:background="#5aadff"></span>8–12</div>
			<div class="li"><span class="bar" style:background="#b48ef4"></span>&lt;8</div>
		</div>
		<div class="src">
			TOP 40 노인 환승 OD pair — 곡선 두께 = √(환승수) × 1.4 · 곡률 0.18
		</div>
	</div>

	<div class="card side-card">
		<div class="ct">TOP OD pair — 환승 노인수 정렬</div>
		<ul class="rank">
			{#each sortedOD as o, i}
				<li class:related={isRelated(o)} class:dim={hasFilter && !isRelated(o)}>
					<button type="button" class="rank-btn" onclick={() => panToOD(o)}>
						<span class="rk">{i + 1}</span>
						<span class="nm">
							<span class="nm-from">🟢 {o.ride_nm}</span>
							<span class="nm-to">🔴 {o.goff_nm}</span>
						</span>
						<span class="vr" style:color={colorN(o.n)}>{o.n}회</span>
					</button>
				</li>
			{/each}
		</ul>
	</div>
</div>

<style>
	.r2 {
		display: grid;
		grid-template-columns: 1.45fr 1fr;
		gap: 14px;
		margin-bottom: 14px;
	}
	.card {
		background: var(--color-card);
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 16px 18px;
		min-width: 0;
		overflow: hidden;
	}
	.side-card {
		max-height: 720px;
		overflow-y: auto;
	}
	.ct {
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.06em;
		color: var(--color-text3);
		text-transform: uppercase;
		margin-bottom: 10px;
	}
	.map-wrap {
		position: relative;
		height: 540px;
		border-radius: 8px;
		overflow: hidden;
		background: #e8e4db;
	}
	.lmap {
		position: absolute;
		inset: 0;
		height: 100% !important;
	}
	.leg {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
		margin-top: 9px;
		font-size: 11px;
		color: var(--color-text2);
	}
	.li {
		display: flex;
		align-items: center;
		gap: 5px;
	}
	.dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		display: inline-block;
	}
	.bar {
		width: 16px;
		height: 3px;
		border-radius: 2px;
		display: inline-block;
	}
	.src {
		font-size: 11px;
		color: var(--color-text3);
		margin-top: 8px;
		line-height: 1.7;
	}
	.rank {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.rank li {
		border-bottom: 0.5px solid var(--color-border-soft);
		transition: opacity 0.2s ease, background 0.2s ease;
	}
	.rank li:last-child {
		border-bottom: none;
	}
	.rank li.related {
		background: color-mix(in srgb, var(--pill-accent, #5aadff) 10%, transparent);
	}
	.rank li.related .rank-btn {
		font-weight: 600;
	}
	.rank li.dim {
		opacity: 0.4;
	}
	.rank li.dim .rank-btn:hover {
		opacity: 1;
	}
	.rank-btn {
		display: grid;
		grid-template-columns: 24px 1fr auto;
		gap: 8px;
		align-items: center;
		width: 100%;
		text-align: left;
		padding: 7px 4px;
		background: transparent;
		border: none;
		cursor: pointer;
		font-family: inherit;
		font-size: 12px;
		color: var(--color-text);
	}
	.rank-btn:hover {
		background: var(--color-bg2);
	}
	.rk {
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--color-text3);
		text-align: center;
	}
	.nm {
		display: flex;
		flex-direction: column;
		min-width: 0;
		gap: 1px;
	}
	.nm-from,
	.nm-to {
		font-size: 11px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--color-text);
	}
	.nm-to {
		color: var(--color-text2);
	}
	.vr {
		font-size: 13px;
		font-weight: 500;
	}
	@media (max-width: 900px) {
		.r2 {
			grid-template-columns: 1fr;
		}
	}
</style>
