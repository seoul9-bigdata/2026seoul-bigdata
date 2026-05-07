<script>
	import { onMount, onDestroy } from 'svelte';
	import data from '$lib/data/transit.json';
	import 'leaflet/dist/leaflet.css';

	const D = data.DATA;
	const STATIONS = D.stations;
	const XFER = D.xfer_breakdown;
	const CHAIN = D.chain_breakdown;

	let { active = true } = $props();

	let mapEl = $state();
	let map;
	let L;
	let stationLayer;
	let Chart;
	let canvasMix = $state();
	let canvasGu = $state();
	let mixChart, guChart;

	// 색상: avg_xfer_sec 따라
	function colorForSec(sec) {
		if (sec == null) return '#cccccc';
		if (sec < 600) return '#3ecfa0';
		if (sec < 900) return '#5aadff';
		if (sec < 1200) return '#f5b740';
		return '#ff5f5f';
	}
	function radiusForRides(r) {
		if (!r) return 4;
		// 5..6831 → 4..12
		const v = Math.log10(Math.max(1, r));
		return Math.max(4, Math.min(12, 4 + v * 2.2));
	}

	// SGG 코드 → 자치구 이름 (서울 25개)
	const SGG_TO_NAME = {
		'11110': '종로구', '11140': '중구', '11170': '용산구', '11200': '성동구',
		'11215': '광진구', '11230': '동대문구', '11260': '중랑구', '11290': '성북구',
		'11305': '강북구', '11320': '도봉구', '11350': '노원구', '11380': '은평구',
		'11410': '서대문구', '11440': '마포구', '11470': '양천구', '11500': '강서구',
		'11530': '구로구', '11545': '금천구', '11560': '영등포구', '11590': '동작구',
		'11620': '관악구', '11650': '서초구', '11680': '강남구', '11710': '송파구',
		'11740': '강동구'
	};

	// TOP 환승시간 긴 정류장 (이용객 50 이상만)
	const topSlow = STATIONS
		.filter((s) => s.avg_xfer_sec && s.elder_rides >= 50)
		.sort((a, b) => b.avg_xfer_sec - a.avg_xfer_sec)
		.slice(0, 10);

	// TOP 이용객 많은 정류장
	const topBusy = [...STATIONS]
		.sort((a, b) => (b.elder_rides || 0) - (a.elder_rides || 0))
		.slice(0, 10);

	// 환승 종류 4분해 (전체 합산)
	const xferAgg = (() => {
		const agg = { BB: 0, BT: 0, TB: 0, TT: 0 };
		Object.values(XFER).forEach((row) => {
			Object.entries(row).forEach(([k, v]) => {
				if (agg[k] != null) agg[k] += v.pax || 0;
			});
		});
		return agg;
	})();

	// 자치구별 평균 환승시간
	const guAvg = (() => {
		const m = {};
		STATIONS.forEach((s) => {
			if (!s.sgg_cd || !s.avg_xfer_sec || !s.elder_rides || s.elder_rides < 30) return;
			const nm = SGG_TO_NAME[s.sgg_cd];
			if (!nm) return;
			(m[nm] = m[nm] || []).push(s.avg_xfer_sec);
		});
		return Object.entries(m)
			.map(([nm, arr]) => ({ nm, avg: arr.reduce((a, b) => a + b, 0) / arr.length }))
			.sort((a, b) => b.avg - a.avg);
	})();

	function popupHtml(s) {
		const xb = XFER[s.sttn_id];
		let xferDetail = '';
		if (xb) {
			const labels = { BB: '버스→버스', BT: '버스→지하철', TB: '지하철→버스', TT: '지하철→지하철' };
			xferDetail =
				'<div style="margin-top:6px"><b style="font-size:11px;color:#5f5e5a">환승 종류</b>';
			Object.entries(xb).forEach(([k, v]) => {
				xferDetail += `<div style="font-size:11px;color:#2c2c2a">· ${labels[k] || k}: ${v.pax}명 / 평균 ${Math.round(v.sec)}초</div>`;
			});
			xferDetail += '</div>';
		}
		const cb = CHAIN[s.sttn_id];
		let chainDetail = '';
		if (cb && cb.pairs && cb.pairs.length) {
			chainDetail = `<div style="margin-top:6px"><b style="font-size:11px;color:#5f5e5a">환승 chain (TOP)</b>`;
			cb.pairs.slice(0, 4).forEach((p) => {
				chainDetail += `<div style="font-size:10px;color:#2c2c2a">${p.from} → ${p.to} (${p.n})</div>`;
			});
			chainDetail += '</div>';
		}
		return `
			<div style="font-family:inherit;min-width:200px">
				<b style="font-size:13px">${s.sttn_nm}</b>
				<div style="font-size:11px;color:#888780;margin-top:2px">${s.kind === 'bus' ? '버스' : '지하철'}</div>
				<div style="font-size:11px;color:#2c2c2a;margin-top:5px">
					평균 환승시간 <b style="color:${colorForSec(s.avg_xfer_sec)}">${Math.round(s.avg_xfer_sec)}초</b><br>
					노인 이용객 <b>${(s.elder_rides || 0).toLocaleString()}</b>명
				</div>
				${xferDetail}${chainDetail}
			</div>`;
	}

	function buildLayer() {
		if (!L || !map) return;
		if (stationLayer) map.removeLayer(stationLayer);
		stationLayer = L.layerGroup();
		STATIONS.forEach((s) => {
			if (!s.lat || !s.lon) return;
			L.circleMarker([s.lat, s.lon], {
				radius: radiusForRides(s.elder_rides),
				fillColor: colorForSec(s.avg_xfer_sec),
				color: '#fff',
				weight: 0.8,
				fillOpacity: 0.82
			})
				.bindPopup(popupHtml(s))
				.addTo(stationLayer);
		});
		stationLayer.addTo(map);
	}

	function panToStn(s) {
		if (!map || !s.lat) return;
		map.setView([s.lat, s.lon], 14, { animate: true });
		// 마커 popup 띄우려면 새로 생성
		L.popup({ offset: [0, -6] }).setLatLng([s.lat, s.lon]).setContent(popupHtml(s)).openOn(map);
	}

	function setupMixChart() {
		if (!canvasMix || !Chart) return;
		const labels = ['버스→버스', '버스→지하철', '지하철→버스', '지하철→지하철'];
		const vals = [xferAgg.BB, xferAgg.BT, xferAgg.TB, xferAgg.TT];
		mixChart = new Chart(canvasMix, {
			type: 'bar',
			data: {
				labels,
				datasets: [
					{
						data: vals,
						backgroundColor: ['#5aadff', '#3ecfa0', '#f5b740', '#b48ef4'],
						borderRadius: 3,
						borderSkipped: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: {
					x: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#5f5e5a' } },
					y: {
						grid: { color: '#f1efe8' },
						ticks: {
							font: { size: 10 },
							color: '#888780',
							callback: (v) => v.toLocaleString()
						},
						title: { display: true, text: '환승 노인 (명)', font: { size: 10 }, color: '#888780' }
					}
				}
			}
		});
	}

	function setupGuChart() {
		if (!canvasGu || !Chart) return;
		const labels = guAvg.map((g) => g.nm);
		const vals = guAvg.map((g) => +g.avg.toFixed(1));
		const bgs = vals.map((v) => colorForSec(v) + 'cc');
		guChart = new Chart(canvasGu, {
			type: 'bar',
			data: { labels, datasets: [{ data: vals, backgroundColor: bgs, borderRadius: 2 }] },
			options: {
				indexAxis: 'y',
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: {
					x: {
						grid: { color: '#f1efe8' },
						ticks: { font: { size: 9 }, color: '#888780' },
						title: { display: true, text: '평균 환승시간 (초)', font: { size: 10 }, color: '#888780' }
					},
					y: { grid: { display: false }, ticks: { font: { size: 9 }, color: '#2c2c2a' } }
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
		buildLayer();

		const ChartMod = await import('chart.js/auto');
		Chart = ChartMod.default;
		setupMixChart();
		setupGuChart();
	});

	onDestroy(() => {
		map?.remove();
		mixChart?.destroy();
		guChart?.destroy();
	});

	$effect(() => {
		if (active && map) {
			setTimeout(() => map.invalidateSize(), 0);
		}
	});
</script>

<div class="r2">
	<div class="card">
		<div class="ct">서울시 정류장·역 환승 별자리 — 노인 환승시간 매핑</div>
		<div class="map-wrap">
			<div bind:this={mapEl} class="lmap"></div>
		</div>
		<div class="leg">
			<div class="li"><span class="dot" style:background="#3ecfa0"></span>&lt; 600초</div>
			<div class="li"><span class="dot" style:background="#5aadff"></span>600–900초</div>
			<div class="li"><span class="dot" style:background="#f5b740"></span>900–1200초</div>
			<div class="li"><span class="dot" style:background="#ff5f5f"></span>≥ 1200초 (취약)</div>
			<div class="li" style:color="#888780;margin-left:6px">크기 = 노인 이용객 수 (log scale)</div>
		</div>
		<div class="src">
			3,290개 정류장·역 픽셀 마커 — 클릭 시 환승 종류 (BB/BT/TB/TT) 분해와 환승 chain 표시
		</div>
	</div>

	<div class="side">
		<div class="card">
			<div class="ct">TOP 10 — 환승시간 긴 정류장 (취약)</div>
			<ul class="rank">
				{#each topSlow as s, i (s.sttn_id)}
					<li>
						<button type="button" class="rank-btn" onclick={() => panToStn(s)}>
							<span class="rk">{i + 1}</span>
							<span class="nm">{s.sttn_nm}</span>
							<span class="vr" style:color={colorForSec(s.avg_xfer_sec)}>
								{Math.round(s.avg_xfer_sec)}초
							</span>
						</button>
					</li>
				{/each}
			</ul>
		</div>
		<div class="card">
			<div class="ct">TOP 10 — 노인 이용객 많은 정류장</div>
			<ul class="rank">
				{#each topBusy as s, i (s.sttn_id)}
					<li>
						<button type="button" class="rank-btn" onclick={() => panToStn(s)}>
							<span class="rk">{i + 1}</span>
							<span class="nm">{s.sttn_nm}</span>
							<span class="vr" style:color="#185fa5">
								{(s.elder_rides || 0).toLocaleString()}
							</span>
						</button>
					</li>
				{/each}
			</ul>
		</div>
	</div>
</div>

<div class="r2b">
	<div class="card">
		<div class="ct">환승 종류 4분해 — 노인 환승 패턴 합산</div>
		<div class="chart-wrap"><canvas bind:this={canvasMix}></canvas></div>
		<div class="src">버스→버스 환승이 가장 큰 비중 — 지하철 환승은 절대 수에서 적지만 시간이 오래 걸림</div>
	</div>
	<div class="card">
		<div class="ct">자치구 평균 환승시간 — 정렬 (긴 순)</div>
		<div class="chart-wrap" style:height="380px"><canvas bind:this={canvasGu}></canvas></div>
	</div>
</div>

<style>
	.r2 {
		display: grid;
		grid-template-columns: 1.45fr 1fr;
		gap: 14px;
		margin-bottom: 14px;
	}
	.r2b {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 14px;
		margin-bottom: 14px;
	}
	.side {
		display: flex;
		flex-direction: column;
		gap: 14px;
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
	.map-wrap {
		position: relative;
		height: 520px;
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
		grid-template-columns: 22px 1fr auto;
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
		transition: background 0.14s;
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
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.vr {
		font-size: 12px;
		font-weight: 500;
	}
	.chart-wrap {
		position: relative;
		height: 240px;
		width: 100%;
	}
	@media (max-width: 900px) {
		.r2,
		.r2b {
			grid-template-columns: 1fr;
		}
	}
</style>
