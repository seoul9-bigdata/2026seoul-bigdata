<script>
	import { onMount, onDestroy } from 'svelte';
	import data from '$lib/data/transit.json';
	import 'leaflet/dist/leaflet.css';

	const D = data.DATA;
	const HEAT = D.heat;
	const CLIMATE = D.climate;

	let { active = true, cG = '전체' } = $props();

	let mapEl = $state();
	let map;
	let L;
	let heatLayer, deadLayer, okLayer;

	let showHeat = $state(true);
	let showDead = $state(true);
	let showOk = $state(true);

	// cG 필터링
	const heatF = $derived(cG === '전체' ? HEAT : HEAT.filter((h) => h.gu === cG));
	const climateF = $derived(cG === '전체' ? CLIMATE : CLIMATE.filter((c) => c.gu === cG));

	// 사각지대 (heat_within_100m === 0)
	const deadStations = $derived(climateF.filter((c) => c.heat_within_100m === 0));
	const okStations = $derived(climateF.filter((c) => c.heat_within_100m > 0));

	// TOP10 사각지대 (heat_nearest_m 큰 순) — 전체 list/순위 통일
	const top10Dead = $derived(
		[...deadStations]
			.sort((a, b) => (b.heat_nearest_m || 0) - (a.heat_nearest_m || 0))
			.slice(0, 10)
	);

	function buildLayers() {
		if (!L || !map) return;
		if (heatLayer) map.removeLayer(heatLayer);
		if (deadLayer) map.removeLayer(deadLayer);
		if (okLayer) map.removeLayer(okLayer);

		heatLayer = L.layerGroup();
		heatF.forEach((h) => {
			if (!h.lat || !h.lng) return;
			L.circleMarker([h.lat, h.lng], {
				radius: 3,
				fillColor: '#ff8c00',
				color: '#fff',
				weight: 0.4,
				fillOpacity: 0.55
			})
				.bindPopup(
					`<b>${h.name}</b><br><span style="font-size:11px;color:#888780">더위쉼터 · ${h.type}</span>`
				)
				.addTo(heatLayer);
		});

		okLayer = L.layerGroup();
		okStations.forEach((c) => {
			if (!c.lat || !c.lon) return;
			L.circleMarker([c.lat, c.lon], {
				radius: 4,
				fillColor: '#3ecfa0',
				color: '#fff',
				weight: 0.8,
				fillOpacity: 0.85
			})
				.bindPopup(popupHtml(c))
				.addTo(okLayer);
		});

		deadLayer = L.layerGroup();
		deadStations.forEach((c) => {
			if (!c.lat || !c.lon) return;
			L.circleMarker([c.lat, c.lon], {
				radius: 7,
				fillColor: '#ff5f5f',
				color: '#fff',
				weight: 1.4,
				fillOpacity: 0.9
			})
				.bindPopup(popupHtml(c))
				.addTo(deadLayer);
		});

		if (showHeat) heatLayer.addTo(map);
		if (showOk) okLayer.addTo(map);
		if (showDead) deadLayer.addTo(map);
	}

	function popupHtml(c) {
		const dead = c.heat_within_100m === 0;
		return `
			<div style="font-family:inherit;min-width:200px">
				<b style="font-size:13px">${c.sttn_nm}</b>
				<div style="font-size:11px;color:#888780;margin-top:2px">${c.kind === 'bus' ? '버스' : '지하철'} · ${dead ? '🔥 폭염 사각지대' : '인접 더위쉼터 있음'}</div>
				<div style="font-size:11px;color:#2c2c2a;margin-top:5px">
					최근접 더위쉼터까지 <b style="color:${dead ? '#ff5f5f' : '#3ecfa0'}">${c.heat_nearest_m ?? '-'}m</b><br>
					100m 내 쉼터 <b>${c.heat_within_100m ?? 0}</b>개<br>
					노인 정오 이용객 <b>${(c.elder_rides_noon || 0).toLocaleString()}</b>명
				</div>
			</div>`;
	}

	function panTo(c) {
		if (!map) return;
		map.setView([c.lat, c.lon], 15, { animate: true });
		L.popup({ offset: [0, -6] }).setLatLng([c.lat, c.lon]).setContent(popupHtml(c)).openOn(map);
	}

	function tog(layer, on) {
		if (!map || !layer) return;
		if (on && !layer._map) layer.addTo(map);
		else if (!on && layer._map) map.removeLayer(layer);
	}

	function zoomToFiltered() {
		if (!L || !map) return;
		if (cG === '전체') {
			map.setView([37.5665, 126.978], 11, { animate: true });
			return;
		}
		const pts = [
			...climateF.filter((c) => c.lat && c.lon).map((c) => [c.lat, c.lon]),
			...heatF.filter((h) => h.lat && h.lng).map((h) => [h.lat, h.lng])
		];
		if (pts.length === 0) return;
		const lats = pts.map((p) => p[0]);
		const lons = pts.map((p) => p[1]);
		const bounds = L.latLngBounds([
			[Math.min(...lats), Math.min(...lons)],
			[Math.max(...lats), Math.max(...lons)]
		]);
		map.fitBounds(bounds.pad(0.1));
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
		buildLayers();
	});

	onDestroy(() => map?.remove());

	$effect(() => {
		if (active && map) setTimeout(() => map.invalidateSize(), 0);
	});

	$effect(() => {
		tog(heatLayer, showHeat);
		tog(okLayer, showOk);
		tog(deadLayer, showDead);
	});

	// cG 변경 시: 마커 재구성 + 지도 줌
	$effect(() => {
		void cG;
		void heatF;
		void climateF;
		if (!map) return;
		buildLayers();
		zoomToFiltered();
	});
</script>

<div class="r2">
	<div class="card">
		<div class="ct">폭염 정류장 — 100m 내 더위쉼터 사각지대 분포</div>
		<div class="ctrl">
			<button type="button" class="chk-btn" class:on={showHeat} onclick={() => (showHeat = !showHeat)}>
				<span class="chk-dot" style:background="#ff8c00"></span>더위쉼터 ({heatF.length})
			</button>
			<button type="button" class="chk-btn" class:on={showOk} onclick={() => (showOk = !showOk)}>
				<span class="chk-dot" style:background="#3ecfa0"></span>인접 정류장 ({okStations.length})
			</button>
			<button type="button" class="chk-btn" class:on={showDead} onclick={() => (showDead = !showDead)}>
				<span class="chk-dot" style:background="#ff5f5f"></span>사각지대 ({deadStations.length})
			</button>
		</div>
		<div class="map-wrap">
			<div bind:this={mapEl} class="lmap"></div>
		</div>
		<div class="src">
			주황 = 더위쉼터 4,107개 · 빨강 = 100m 내 쉼터 0개 정류장 (폭염 사각지대) · 초록 = 인접 정류장
		</div>
	</div>

	<div class="card side-card">
		<div class="ct">TOP 10 — 폭염 사각지대 (최근접 더위쉼터 거리 큰 순)</div>
		<ul class="rank">
			{#each top10Dead as c, i}
				<li>
					<button type="button" class="rank-btn" onclick={() => panTo(c)}>
						<span class="rk">{i + 1}</span>
						<span class="nm">{c.sttn_nm}</span>
						<span class="vr">{c.heat_nearest_m ?? '-'}m</span>
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
	.ctrl {
		display: flex;
		gap: 6px;
		margin-bottom: 9px;
		flex-wrap: wrap;
	}
	.chk-btn {
		font-size: 11px;
		padding: 4px 11px;
		border-radius: 16px;
		border: 0.5px solid var(--color-text4);
		background: transparent;
		color: var(--color-text2);
		cursor: pointer;
		font-family: inherit;
		display: flex;
		align-items: center;
		gap: 5px;
	}
	.chk-btn.on {
		background: var(--color-bg2);
		border-color: var(--color-text2);
		color: var(--color-text);
	}
	.chk-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
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
	}
	.rank li:last-child {
		border-bottom: none;
	}
	.rank-btn {
		display: grid;
		grid-template-columns: 26px 1fr auto;
		gap: 8px;
		align-items: center;
		width: 100%;
		text-align: left;
		padding: 6px 4px;
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
		font-size: 12px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.vr {
		font-size: 12px;
		font-weight: 500;
		color: #c0392b;
	}
	@media (max-width: 900px) {
		.r2 {
			grid-template-columns: 1fr;
		}
	}
</style>
