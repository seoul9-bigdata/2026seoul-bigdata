<script>
	import { onMount, onDestroy } from 'svelte';
	import cwData from '$lib/data/transit_crosswalk.json';
	import 'leaflet/dist/leaflet.css';

	const ACC = cwData.ACC; // 노인 보행사고
	const CW = cwData.CW; // 횡단보도

	let { active = true } = $props();

	let mapEl = $state();
	let map;
	let L;
	let accLayer, cwLayer;
	let Chart;
	let canvasGu = $state();
	let guChart;

	let showAcc = $state(true);
	let showCw = $state(true);
	let selectedGu = $state('전체');

	const guList = (() => {
		const s = new Set();
		ACC.forEach((a) => a.gu && s.add(a.gu));
		CW.forEach((c) => c.gu && s.add(c.gu));
		return ['전체', ...[...s].sort((a, b) => a.localeCompare(b, 'ko'))];
	})();

	// 자치구별 집계 (사고수 + 신호없는 횡단보도수)
	const guStats = (() => {
		const m = {};
		ACC.forEach((a) => {
			if (!a.gu) return;
			(m[a.gu] = m[a.gu] || { gu: a.gu, accCnt: 0, cwCnt: 0 }).accCnt++;
		});
		CW.forEach((c) => {
			if (!c.gu) return;
			(m[c.gu] = m[c.gu] || { gu: c.gu, accCnt: 0, cwCnt: 0 }).cwCnt++;
		});
		return Object.values(m).sort((a, b) => b.accCnt - a.accCnt);
	})();

	function popupAcc(a) {
		return `
			<div style="font-family:inherit;min-width:180px">
				<b style="font-size:12px;color:#ff5f5f">🚨 노인 보행사고</b>
				<div style="font-size:11px;color:#888780;margin-top:2px">${a.gu}</div>
				<div style="font-size:11px;color:#2c2c2a;margin-top:5px">
					사고 유형 <b>${a.acdnt || '-'}</b><br>
					심각도 <b style="color:${a.grade === '사망사고' ? '#c0392b' : a.grade === '중상사고' ? '#d46800' : '#185fa5'}">${a.grade || '-'}</b><br>
					횡단보도 ${a.crosswalk ? '✅ 있음' : '❌ 없음'}
				</div>
			</div>`;
	}
	function popupCw(c) {
		return `
			<div style="font-family:inherit;min-width:180px">
				<b style="font-size:12px;color:#5aadff">🚦 횡단보도</b>
				<div style="font-size:11px;color:#888780;margin-top:2px">${c.gu}</div>
				<div style="font-size:11px;color:#2c2c2a;margin-top:5px">
					음향 신호 <b>${c['음향'] ? '있음' : '없음'}</b><br>
					고원식 <b>${c['고원식'] ? '있음' : '없음'}</b>
				</div>
			</div>`;
	}

	function buildLayers() {
		if (!L || !map) return;
		if (accLayer) map.removeLayer(accLayer);
		if (cwLayer) map.removeLayer(cwLayer);
		accLayer = L.layerGroup();
		cwLayer = L.layerGroup();

		const filterGu = (item) => selectedGu === '전체' || item.gu === selectedGu;

		ACC.filter(filterGu).forEach((a) => {
			if (!a.lat || !a.lon) return;
			L.circleMarker([a.lat, a.lon], {
				radius: a.grade === '사망사고' ? 5 : 3.5,
				fillColor: '#ff5f5f',
				color: '#fff',
				weight: 0.6,
				fillOpacity: 0.7
			})
				.bindPopup(popupAcc(a))
				.addTo(accLayer);
		});

		CW.filter(filterGu).forEach((c) => {
			if (!c.lat || !c.lon) return;
			L.circleMarker([c.lat, c.lon], {
				radius: 2.4,
				fillColor: '#5aadff',
				color: '#fff',
				weight: 0.3,
				fillOpacity: 0.55
			})
				.bindPopup(popupCw(c))
				.addTo(cwLayer);
		});

		if (showAcc) accLayer.addTo(map);
		if (showCw) cwLayer.addTo(map);
	}

	function tog(layer, on) {
		if (!map || !layer) return;
		if (on && !layer._map) layer.addTo(map);
		else if (!on && layer._map) map.removeLayer(layer);
	}

	function setupChart() {
		if (!canvasGu || !Chart) return;
		const top = guStats.slice(0, 25);
		guChart = new Chart(canvasGu, {
			type: 'bar',
			data: {
				labels: top.map((g) => g.gu),
				datasets: [
					{
						label: '노인 사고수',
						data: top.map((g) => g.accCnt),
						backgroundColor: '#ff5f5fcc',
						borderRadius: 2
					},
					{
						label: '횡단보도',
						data: top.map((g) => g.cwCnt),
						backgroundColor: '#5aadffaa',
						borderRadius: 2
					}
				]
			},
			options: {
				indexAxis: 'y',
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { position: 'bottom', labels: { font: { size: 10 }, boxWidth: 10 } }
				},
				scales: {
					x: {
						grid: { color: '#f1efe8' },
						ticks: { font: { size: 9 }, color: '#888780' }
					},
					y: {
						grid: { display: false },
						ticks: { font: { size: 9 }, color: '#2c2c2a' }
					}
				}
			}
		});
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

		const ChartMod = await import('chart.js/auto');
		Chart = ChartMod.default;
		setupChart();
	});

	onDestroy(() => {
		map?.remove();
		guChart?.destroy();
	});

	$effect(() => {
		if (active && map) setTimeout(() => map.invalidateSize(), 0);
	});

	$effect(() => {
		void selectedGu;
		if (map) buildLayers();
	});

	$effect(() => {
		tog(accLayer, showAcc);
		tog(cwLayer, showCw);
	});
</script>

<div class="r2">
	<div class="card">
		<div class="ct">횡단보도 안전 — 노인 보행사고 + 횡단보도</div>
		<div class="ctrl">
			<span class="lbl">자치구</span>
			<select bind:value={selectedGu}>
				{#each guList as g}<option value={g}>{g}</option>{/each}
			</select>
			<button type="button" class="chk-btn" class:on={showAcc} onclick={() => (showAcc = !showAcc)}>
				<span class="chk-dot" style:background="#ff5f5f"></span>노인 사고 ({ACC.length.toLocaleString()})
			</button>
			<button type="button" class="chk-btn" class:on={showCw} onclick={() => (showCw = !showCw)}>
				<span class="chk-dot" style:background="#5aadff"></span>횡단보도 ({CW.length.toLocaleString()})
			</button>
		</div>
		<div class="map-wrap">
			<div bind:this={mapEl} class="lmap"></div>
		</div>
		<div class="src">
			빨강 = 65세 이상 보행사고 · 파랑 = 횡단보도 — 사망사고는 큰 마커
		</div>
	</div>

	<div class="card side-card">
		<div class="ct">자치구별 — 노인 사고수 vs 횡단보도</div>
		<div class="chart-wrap"><canvas bind:this={canvasGu}></canvas></div>
		<div class="src" style:margin-top="6px">사고수 많은 순으로 25개 자치구 정렬</div>
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
		background: #fff;
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 16px 18px;
		min-width: 0;
		overflow: hidden;
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
		align-items: center;
	}
	.lbl {
		font-size: 11px;
		color: var(--color-text3);
	}
	select {
		font-family: inherit;
		font-size: 11px;
		padding: 4px 8px;
		border: 0.5px solid var(--color-text4);
		border-radius: 6px;
		background: #fff;
		color: var(--color-text);
		cursor: pointer;
		outline: none;
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
	.chart-wrap {
		position: relative;
		height: 600px;
		width: 100%;
	}
	.src {
		font-size: 11px;
		color: var(--color-text3);
		margin-top: 8px;
		line-height: 1.7;
	}
	@media (max-width: 900px) {
		.r2 {
			grid-template-columns: 1fr;
		}
	}
</style>
