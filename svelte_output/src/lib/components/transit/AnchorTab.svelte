<script>
	import { onMount, onDestroy } from 'svelte';
	import data from '$lib/data/transit.json';
	import 'leaflet/dist/leaflet.css';

	const D = data.DATA;
	const ANCHORS = D.anchors;

	let { active = true, cG = '전체' } = $props();

	let mapEl = $state();
	let map;
	let L;
	let layerByType = {};

	const TYPE_META = {
		'거점 시장': { color: '#7cd982', emoji: '🛒', short: '시장' },
		'거점 공원': { color: '#3ecfa0', emoji: '🌳', short: '공원' },
		'응급·상급병원': { color: '#f472b6', emoji: '🏥', short: '병원' },
		'노인복지관': { color: '#b48ef4', emoji: '🏛', short: '복지관' },
		'환승 거점역': { color: '#ff5f5f', emoji: '🚇', short: '환승' },
		'장거리 터미널·역': { color: '#5aadff', emoji: '🚌', short: '터미널' },
		'노인 명소': { color: '#f5b740', emoji: '⭐', short: '명소' }
	};

	let toggles = $state(
		Object.fromEntries(Object.keys(TYPE_META).map((k) => [k, true]))
	);

	// cG 필터링
	const anchorsF = $derived(
		cG === '전체' ? ANCHORS : ANCHORS.filter((a) => a.gu === cG)
	);

	// TOP 10 by elder_alights_300m — 필터된 데이터 기준 (전체 list/순위 통일)
	const top10 = $derived(
		[...anchorsF]
			.filter((a) => a.elder_alights_300m != null)
			.sort((a, b) => (b.elder_alights_300m || 0) - (a.elder_alights_300m || 0))
			.slice(0, 10)
	);

	function makeIcon(meta) {
		return L.divIcon({
			html: `<div style="width:24px;height:24px;border-radius:50%;background:${meta.color};border:2px solid #fff;box-shadow:0 0 0 1px ${meta.color}55;display:flex;align-items:center;justify-content:center;font-size:13px">${meta.emoji}</div>`,
			className: '',
			iconSize: [24, 24],
			iconAnchor: [12, 12]
		});
	}

	function popupHtml(a) {
		const meta = TYPE_META[a.anchor_type] || { color: '#888', emoji: '•', short: '?' };
		return `
			<div style="font-family:inherit;min-width:200px">
				<b style="font-size:13px">${meta.emoji} ${a.name}</b>
				<div style="font-size:11px;color:#888780;margin-top:2px">${a.anchor_type} · ${a.gu}</div>
				<div style="font-size:11px;color:#2c2c2a;margin-top:5px">
					최근접역 <b>${a.nearest_stn || '-'}</b><br>
					거리 <b>${a.nearest_stn_dist_m ?? '-'}m</b><br>
					300m 내 정류장 <b>${a.nearby_stations_300m ?? 0}</b>개<br>
					300m 내 노인 하차 <b style="color:#185fa5">${(a.elder_alights_300m || 0).toLocaleString()}</b>회
				</div>
			</div>`;
	}

	function buildLayers() {
		if (!L || !map) return;
		Object.values(layerByType).forEach((lyr) => map.removeLayer(lyr));
		layerByType = {};

		Object.keys(TYPE_META).forEach((t) => {
			const meta = TYPE_META[t];
			const icon = makeIcon(meta);
			const lyr = L.layerGroup();
			anchorsF.filter((a) => a.anchor_type === t && a.lat).forEach((a) => {
				L.marker([a.lat, a.lon], { icon }).bindPopup(popupHtml(a)).addTo(lyr);
			});
			layerByType[t] = lyr;
			if (toggles[t]) lyr.addTo(map);
		});
	}

	function zoomToFiltered() {
		if (!L || !map) return;
		if (cG === '전체') {
			map.setView([37.5665, 126.978], 11, { animate: true });
			return;
		}
		const pts = anchorsF.filter((a) => a.lat && a.lon).map((a) => [a.lat, a.lon]);
		if (pts.length === 0) return;
		const lats = pts.map((p) => p[0]);
		const lons = pts.map((p) => p[1]);
		const bounds = L.latLngBounds([
			[Math.min(...lats), Math.min(...lons)],
			[Math.max(...lats), Math.max(...lons)]
		]);
		map.fitBounds(bounds.pad(0.1));
	}

	function panTo(a) {
		if (!map) return;
		map.setView([a.lat, a.lon], 15, { animate: true });
		L.popup({ offset: [0, -10] }).setLatLng([a.lat, a.lon]).setContent(popupHtml(a)).openOn(map);
	}

	function tog(t) {
		toggles = { ...toggles, [t]: !toggles[t] };
		const lyr = layerByType[t];
		if (!lyr || !map) return;
		if (toggles[t]) lyr.addTo(map);
		else map.removeLayer(lyr);
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

	// cG 변경 시: 마커 재구성 + 지도 줌
	$effect(() => {
		void cG;
		void anchorsF;
		if (!map) return;
		buildLayers();
		zoomToFiltered();
	});
</script>

<div class="r2">
	<div class="card">
		<div class="ct">노인 거점 시설 — 시장·공원·병원·복지관·환승·터미널·명소</div>
		<div class="ctrl">
			{#each Object.entries(TYPE_META) as [t, meta]}
				<button type="button" class="chk-btn" class:on={toggles[t]} onclick={() => tog(t)}>
					<span class="chk-dot" style:background={meta.color}></span>{meta.emoji} {meta.short}
				</button>
			{/each}
		</div>
		<div class="map-wrap">
			<div bind:this={mapEl} class="lmap"></div>
		</div>
		<div class="src">
			347개 거점 시설 — 클릭 시 최근접역, 거리, 300m 내 노인 하차수 표시
		</div>
	</div>

	<div class="card side-card">
		<div class="ct">TOP 10 — 300m 노인 하차 많은 거점 (수요 거점)</div>
		<ul class="rank">
			{#each top10 as a, i}
				{@const meta = TYPE_META[a.anchor_type] || { color: '#888', emoji: '•' }}
				<li>
					<button type="button" class="rank-btn" onclick={() => panTo(a)}>
						<span class="rk">{i + 1}</span>
						<span class="ic" style:background={meta.color}>{meta.emoji}</span>
						<span class="nm">
							<span class="nm-main">{a.name}</span>
							<span class="nm-sub">{a.gu}</span>
						</span>
						<span class="vr">{(a.elder_alights_300m || 0).toLocaleString()}</span>
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
		background: rgba(90, 173, 255, 0.18);
		border-color: var(--color-blue);
		color: var(--color-blue);
		font-weight: 500;
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
		grid-template-columns: 22px 22px 1fr auto;
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
	.ic {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 11px;
		color: #fff;
	}
	.nm {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.nm-main {
		font-size: 12px;
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.nm-sub {
		font-size: 10px;
		color: var(--color-text3);
	}
	.vr {
		font-size: 12px;
		font-weight: 500;
		color: #185fa5;
	}
	@media (max-width: 900px) {
		.r2 {
			grid-template-columns: 1fr;
		}
	}
</style>
