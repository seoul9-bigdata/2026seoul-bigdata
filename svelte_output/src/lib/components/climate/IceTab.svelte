<script>
	import { onMount, onDestroy } from 'svelte';
	import data from '$lib/data/climate.json';
	import CountUp from '$lib/components/CountUp.svelte';
	import { applySort, compareBy } from '$lib/util/sortable.js';
	import 'leaflet/dist/leaflet.css';

	const { ICING_GU, ICING_S, JISEOL, GU_GEO, SEOUL_OUTLINE } = data;

	let { active = false } = $props();

	let curBuf = $state(200);
	let iceOn = $state({ icing: true, cov: true, boxes: true });

	let mapEl = $state();
	let canvasRank = $state();
	let map;
	let L;
	let Chart;
	let icingLayer = null;
	let covLayer = null;
	let boxesLayer = null;
	let icingChoroLayer = null;
	let rankChart = null;

	function vulnColor(pct) {
		if (pct == null) return '#cccccc';
		if (pct >= 70) return '#C62828';
		if (pct >= 50) return '#EF6C00';
		if (pct >= 30) return '#F9A825';
		return '#2E7D32';
	}

	// 헤더 클릭 정렬 — 디폴트: 취약 비율 내림차순
	let sortKey = $state('pct');
	let sortDir = $state(/** @type {'asc' | 'desc'} */ ('desc'));
	function setSort(/** @type {string} */ k) {
		({ sortKey, sortDir } = applySort(k, sortKey, sortDir, ['nm']));
	}

	const rankRows = $derived.by(() => {
		const rows = Object.entries(ICING_GU).map(([cd, d]) => ({
			cd,
			nm: d.nm,
			pct: curBuf === 100 ? d.vuln100 : d.vuln200,
			nodes: d.nodes,
			jiseol: d.jiseol
		}));
		rows.sort(compareBy(sortKey, sortDir));
		return rows;
	});

	const cards = $derived.by(() => {
		const km2 = curBuf === 100 ? ICING_S.icing_100_km2 : ICING_S.icing_200_km2;
		const pct = +(km2 / ICING_S.base_km2 * 100).toFixed(1);
		const cov = +(ICING_S.base_km2 - km2).toFixed(1);
		const cpct = (100 - pct).toFixed(1);
		return { km2, pct, cov, cpct };
	});

	// ── Canvas 레이어 클래스 빌더 (L 로딩 후 호출) ──
	// Leaflet zoom anim 동기화: leaflet-zoom-animated 클래스 + _animateZoom 사용
	function makeCovCanvasLayer(LL) {
		return LL.Layer.extend({
			initialize: function (buf) {
				this._buf = buf;
			},
			onAdd: function (m) {
				this._map = m;
				const cv = (this._cv = document.createElement('canvas'));
				cv.className = 'leaflet-zoom-animated';
				cv.style.cssText = 'position:absolute;pointer-events:none;z-index:350';
				m.getPanes().overlayPane.appendChild(cv);
				m.on('moveend viewreset zoomend', this._reset, this);
				m.on('zoomanim', this._animateZoom, this);
				this._reset();
			},
			onRemove: function (m) {
				this._cv.remove();
				m.off('moveend viewreset zoomend', this._reset, this);
				m.off('zoomanim', this._animateZoom, this);
			},
			setBuf: function (buf) {
				this._buf = buf;
				if (this._map) this._reset();
			},
			_animateZoom: function 이미 (e) {
				const m = this._map;
				const scale = m.getZoomScale(e.zoom);
				const offset = m._latLngBoundsToNewLayerBounds(m.getBounds(), e.zoom, e.center).min;
				LL.DomUtil.setTransform(this._cv, offset, scale);
			},
			_reset: function () {
				const m = this._map;
				const tl = m.containerPointToLayerPoint([0, 0]);
				const sz = m.getSize();
				const cv = this._cv;
				LL.DomUtil.setTransform(cv, tl, 1);
				cv.width = sz.x;
				cv.height = sz.y;
				this._draw();
			},
			_draw: function () {
				const m = this._map,
					buf = this._buf;
				const cv = this._cv,
					sz = m.getSize();
				const tl = m.containerPointToLayerPoint([0, 0]);
				const ctx = cv.getContext('2d');
				ctx.clearRect(0, 0, sz.x, sz.y);
				const proj = (lat, lng) => {
					const lp = m.latLngToLayerPoint([lat, lng]);
					return [lp.x - tl.x, lp.y - tl.y];
				};
				const mPerPx = m.distance(
					m.containerPointToLatLng([sz.x / 2, sz.y / 2]),
					m.containerPointToLatLng([sz.x / 2 + 1, sz.y / 2])
				);
				const rPx = buf / mPerPx;
				ctx.beginPath();
				for (const b of JISEOL) {
					const [x, y] = proj(b.lat, b.lng);
					ctx.moveTo(x + rPx, y);
					ctx.arc(x, y, rPx, 0, Math.PI * 2);
				}
				ctx.fillStyle = 'rgba(21,101,192,0.13)';
				ctx.fill();
				ctx.strokeStyle = 'rgba(30,136,229,0.25)';
				ctx.lineWidth = 0.4;
				ctx.stroke();
			}
		});
	}

	function makeIcingCanvasLayer(LL) {
		return LL.Layer.extend({
			initialize: function (buf) {
				this._buf = buf;
			},
			onAdd: function (m) {
				this._map = m;
				const cv = (this._cv = document.createElement('canvas'));
				cv.className = 'leaflet-zoom-animated';
				cv.style.cssText = 'position:absolute;pointer-events:none;z-index:400';
				m.getPanes().overlayPane.appendChild(cv);
				m.on('moveend viewreset zoomend', this._reset, this);
				m.on('zoomanim', this._animateZoom, this);
				this._reset();
			},
			onRemove: function (m) {
				this._cv.remove();
				m.off('moveend viewreset zoomend', this._reset, this);
				m.off('zoomanim', this._animateZoom, this);
			},
			setBuf: function (buf) {
				this._buf = buf;
				if (this._map) this._reset();
			},
			_animateZoom: function (e) {
				const m = this._map;
				const scale = m.getZoomScale(e.zoom);
				const offset = m._latLngBoundsToNewLayerBounds(m.getBounds(), e.zoom, e.center).min;
				LL.DomUtil.setTransform(this._cv, offset, scale);
			},
			_reset: function () {
				const m = this._map;
				const tl = m.containerPointToLayerPoint([0, 0]);
				const sz = m.getSize();
				const cv = this._cv;
				LL.DomUtil.setTransform(cv, tl, 1);
				cv.width = sz.x;
				cv.height = sz.y;
				this._draw();
			},
			_draw: function () {
				const m = this._map,
					buf = this._buf;
				const cv = this._cv;
				const sz = m.getSize();
				const tl = m.containerPointToLayerPoint([0, 0]);
				const ctx = cv.getContext('2d');
				ctx.clearRect(0, 0, sz.x, sz.y);
				const proj = (lat, lng) => {
					const lp = m.latLngToLayerPoint([lat, lng]);
					return [lp.x - tl.x, lp.y - tl.y];
				};
				ctx.fillStyle = 'rgba(198,40,40,0.55)';
				ctx.beginPath();
				SEOUL_OUTLINE.forEach(([lng, lat], i) => {
					const [x, y] = proj(lat, lng);
					i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
				});
				ctx.closePath();
				ctx.fill();
				ctx.globalCompositeOperation = 'destination-out';
				const mPerPx = m.distance(
					m.containerPointToLatLng([sz.x / 2, sz.y / 2]),
					m.containerPointToLatLng([sz.x / 2 + 1, sz.y / 2])
				);
				const rPx = buf / mPerPx;
				ctx.fillStyle = 'rgba(0,0,0,1)';
				ctx.beginPath();
				for (const b of JISEOL) {
					const [x, y] = proj(b.lat, b.lng);
					ctx.moveTo(x + rPx, y);
					ctx.arc(x, y, rPx, 0, Math.PI * 2);
				}
				ctx.fill();
				ctx.globalCompositeOperation = 'source-over';
			}
		});
	}

	let CovCanvasLayer, IcingCanvasLayer;

	function buildLayers(buf) {
		if (icingLayer) {
			icingLayer.remove();
			icingLayer = null;
		}
		icingLayer = new IcingCanvasLayer(buf);
		if (iceOn.icing) icingLayer.addTo(map);

		if (covLayer) {
			covLayer.remove();
			covLayer = null;
		}
		covLayer = new CovCanvasLayer(buf);
		if (iceOn.cov) covLayer.addTo(map);
		if (iceOn.boxes && boxesLayer) boxesLayer.addTo(map);
	}

	function setupRankChart() {
		if (!canvasRank || !Chart) return;
		const labels = rankRows.map((r) => r.nm);
		const dataArr = rankRows.map((r) => r.pct);
		const bgs = rankRows.map((r) => vulnColor(r.pct) + 'cc');
		rankChart = new Chart(canvasRank, {
			type: 'bar',
			data: { labels, datasets: [{ data: dataArr, backgroundColor: bgs, borderRadius: 3, borderSkipped: false }] },
			options: {
				indexAxis: 'y',
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: {
					x: {
						min: 0,
						max: 100,
						grid: { color: '#f1efe8' },
						ticks: { font: { size: 9 }, color: '#888780' },
						title: { display: true, text: '취약 도로 노드 비율 (%)', font: { size: 9 }, color: '#888780' }
					},
					y: { grid: { display: false }, ticks: { font: { size: 9 }, color: '#2c2c2a' } }
				}
			}
		});
	}

	function updateRankChart() {
		if (!rankChart) {
			setupRankChart();
			return;
		}
		const labels = rankRows.map((r) => r.nm);
		const dataArr = rankRows.map((r) => r.pct);
		const bgs = rankRows.map((r) => vulnColor(r.pct) + 'cc');
		rankChart.data.labels = labels;
		rankChart.data.datasets[0].data = dataArr;
		rankChart.data.datasets[0].backgroundColor = bgs;
		rankChart.update('none');
	}

	function updateChoro() {
		if (!icingChoroLayer) return;
		icingChoroLayer.setStyle((f) => {
			const d = ICING_GU[f.properties.cd];
			const pct = d ? (curBuf === 100 ? d.vuln100 : d.vuln200) : null;
			return {
				fillColor: vulnColor(pct),
				fillOpacity: 0.38,
				color: '#fff',
				weight: 0.8,
				opacity: 0.7
			};
		});
	}

	onMount(async () => {
		if (typeof window === 'undefined') return;
		const leaflet = await import('leaflet');
		L = leaflet.default;
		CovCanvasLayer = makeCovCanvasLayer(L);
		IcingCanvasLayer = makeIcingCanvasLayer(L);

		map = L.map(mapEl, { center: [37.55, 126.978], zoom: 11 });
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			attribution: '© OSM · © CartoDB',
			maxZoom: 19,
			subdomains: 'abcd'
		}).addTo(map);

		boxesLayer = L.layerGroup();
		JISEOL.forEach((b) => {
			L.circleMarker([b.lat, b.lng], {
				radius: 2,
				fillColor: '#00E5FF',
				color: 'transparent',
				fillOpacity: 0.75
			})
				.bindTooltip(`<b>${b.nm}</b><br>${b.addr}<br><span style="color:#888780">${b.gu}</span>`, {
					direction: 'top'
				})
				.addTo(boxesLayer);
		});

		buildLayers(200);

		icingChoroLayer = L.geoJSON(GU_GEO, {
			style: (f) => {
				const d = ICING_GU[f.properties.cd];
				const pct = d ? d.vuln200 : null;
				return {
					fillColor: vulnColor(pct),
					fillOpacity: 0.38,
					color: '#fff',
					weight: 0.8,
					opacity: 0.7
				};
			},
			onEachFeature: (f, layer) => {
				const d = ICING_GU[f.properties.cd];
				if (!d) return;
				const pct = curBuf === 100 ? d.vuln100 : d.vuln200;
				layer.bindTooltip(
					`<b>${f.properties.nm}</b><br>결빙 취약 ${pct.toFixed(1)}% · 제설함 ${d.jiseol}개`,
					{ direction: 'top' }
				);
			}
		}).addTo(map);

		const ChartMod = await import('chart.js/auto');
		Chart = ChartMod.default;
		setupRankChart();
	});

	onDestroy(() => {
		if (map) {
			map.remove();
			map = null;
		}
		if (rankChart) rankChart.destroy();
	});

	$effect(() => {
		if (active && map) setTimeout(() => map.invalidateSize(), 0);
	});

	$effect(() => {
		void curBuf;
		if (map && IcingCanvasLayer) {
			buildLayers(curBuf);
			updateChoro();
		}
		if (Chart) updateRankChart();
	});

	$effect(() => {
		// 명시적 destructure 로 의존성 추적 보장
		const { icing, cov, boxes } = iceOn;
		if (!map) return;
		// layer 별 독립 처리 + hasLayer 멱등성 체크 — 한 layer 가 null 이어도 다른 toggle 차단 안 함
		const setLayer = (/** @type {any} */ layer, /** @type {boolean} */ on) => {
			if (!layer) return;
			if (on) {
				if (!map.hasLayer(layer)) layer.addTo(map);
			} else {
				if (map.hasLayer(layer)) map.removeLayer(layer);
			}
		};
		setLayer(icingLayer, icing);
		setLayer(covLayer, cov);
		setLayer(boxesLayer, boxes);
	});

	function togIce(key) {
		iceOn = { ...iceOn, [key]: !iceOn[key] };
	}

	function vulnPillClass(pct) {
		if (pct == null || pct < 30) return 'phi';
		if (pct < 50) return 'pmd';
		return 'plo';
	}
	function vulnPillText(pct) {
		if (pct == null || pct < 30) return '양호';
		if (pct < 50) return '보통';
		return '취약';
	}
	function vulnBarStyle(pct) {
		if (pct == null) return 'display:none';
		return `background:${vulnColor(pct)};width:${Math.round((pct * 40) / 100)}px`;
	}
</script>

<div class="ctrl">
	<div class="crow">
		<span class="lbl">제설함 반경</span>
		<button class="btn bw" class:on={curBuf === 100} onclick={() => (curBuf = 100)}>100m</button>
		<button class="btn bw" class:on={curBuf === 200} onclick={() => (curBuf = 200)}>200m</button>
		<span style="margin-left:14px;color:#888780">|</span>
		<button class="btn bw" class:on={iceOn.icing} onclick={() => togIce('icing')}>
			결빙취약 {iceOn.icing ? 'ON' : 'OFF'}
		</button>
		<button class="btn bw" class:on={iceOn.cov} onclick={() => togIce('cov')}>
			커버원 {iceOn.cov ? 'ON' : 'OFF'}
		</button>
		<button class="btn bw" class:on={iceOn.boxes} onclick={() => togIce('boxes')}>
			제설함 {iceOn.boxes ? 'ON' : 'OFF'}
		</button>
	</div>
	<div class="sgrid">
		{#key curBuf}
		<div class="sc">
			<div class="sl">서울 행정동 면적</div>
			<div class="sv"><CountUp value={+ICING_S.base_km2} decimals={1} /><span class="sv-unit"> km²</span></div>
			<div class="ss">서울시 행정동 전체</div>
		</div>
		<div class="sc">
			<div class="sl">제설함 커버 구역</div>
			<div class="sv green"><CountUp value={+cards.cov} decimals={1} /><span class="sv-unit"> km²</span></div>
			<div class="ss">{cards.cpct}% · {curBuf}m 반경</div>
		</div>
		<div class="sc">
			<div class="sl">결빙 취약 구역</div>
			<div class="sv red"><CountUp value={+cards.km2} decimals={1} /><span class="sv-unit"> km²</span></div>
			<div class="ss">{cards.pct}% · {curBuf}m 반경</div>
		</div>
		<div class="sc">
			<div class="sl">제설함 수</div>
			<div class="sv"><CountUp value={JISEOL.length} /></div>
			<div class="ss">서울시 등록 개소</div>
		</div>
		{/key}
	</div>
</div>

<div class="r2">
	<div class="card">
		<div class="ct">겨울 결빙 취약 구역 지도</div>
		<div class="map-wrap"><div bind:this={mapEl} class="lmap"></div></div>
		<div class="leg">
			<div class="li"><div class="ld" style="background:#C62828;opacity:.7"></div>결빙 취약 구역 (한강·산지 제외)</div>
			<div class="li"><div class="ld" style="background:#1565C0;opacity:.13;border:1px solid rgba(30,136,229,.5)"></div>제설함 커버리지 원</div>
			<div class="li"><div class="ld" style="background:#00E5FF;border-radius:50%"></div>제설함 위치</div>
		</div>
		<div class="src">제설함 10,437개 · 100m/200m 버퍼 합집합 · 서울 행정동 − OSM 자연지물</div>
	</div>
	<div class="ice-side">
		<div class="card">
			<div class="ct">구별 결빙 취약 도로 비율</div>
			<div style="font-size:10px;color:#888780;margin-bottom:6px">
				OSM 도로 노드 기준 · 제설함 버퍼 밖 노드 비율 (취약 높을수록 위험)
			</div>
			<div class="chart-wrap-tall"><canvas bind:this={canvasRank}></canvas></div>
		</div>
	</div>
</div>

<div class="card" style="margin-top:14px">
	<div class="ct">자치구별 결빙 취약 상세표</div>
	<div style="font-size:10px;color:#888780;margin-bottom:8px">
		OSM 도로 노드 기준 · 100m/200m 버퍼 토글에 연동
	</div>
	<div class="tbl-wrap">
		<table class="ktbl">
			<thead>
				<tr>
					<th class="th-sort left" class:active={sortKey === 'nm'} onclick={() => setSort('nm')}>
						자치구
						{#if sortKey === 'nm'}<span class="sort-arr">{sortDir === 'desc' ? '▼' : '▲'}</span>{/if}
					</th>
					<th class="th-sort" class:active={sortKey === 'jiseol'} onclick={() => setSort('jiseol')}>
						제설함
						{#if sortKey === 'jiseol'}<span class="sort-arr">{sortDir === 'desc' ? '▼' : '▲'}</span>{/if}
					</th>
					<th class="th-sort" class:active={sortKey === 'nodes'} onclick={() => setSort('nodes')}>
						도로 노드
						{#if sortKey === 'nodes'}<span class="sort-arr">{sortDir === 'desc' ? '▼' : '▲'}</span>{/if}
					</th>
					<th class="th-sort" class:active={sortKey === 'pct'} onclick={() => setSort('pct')}>
						취약 비율
						{#if sortKey === 'pct'}<span class="sort-arr">{sortDir === 'desc' ? '▼' : '▲'}</span>{/if}
					</th>
					<th class="center">취약도</th>
				</tr>
			</thead>
			<tbody>
				{#each rankRows as r (r.cd)}
					<tr>
						<td class="left">{r.nm}</td>
						<td>{r.jiseol}</td>
						<td>{r.nodes.toLocaleString()}</td>
						<td>
							<b style:color={vulnColor(r.pct)}>{r.pct.toFixed(1)}%</b>
							<span class="score-bar" style={vulnBarStyle(r.pct)}></span>
						</td>
						<td class="center">
							<span class="pill {vulnPillClass(r.pct)}">{vulnPillText(r.pct)}</span>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.ctrl {
		background: var(--color-card);
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 14px 20px;
		margin-bottom: 14px;
	}
	.crow {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
		margin-bottom: 9px;
	}
	.crow:last-child {
		margin-bottom: 0;
	}
	.lbl {
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.06em;
		color: var(--color-text3);
		white-space: nowrap;
	}
	.btn {
		font-size: 12px;
		padding: 5px 14px;
		border-radius: 20px;
		border: 0.5px solid var(--color-text4);
		background: transparent;
		color: var(--color-text2);
		cursor: pointer;
		transition: all 0.14s;
		font-family: inherit;
		white-space: nowrap;
	}
	.btn:hover {
		border-color: var(--color-text2);
		color: var(--color-text);
	}
	.btn.on {
		background: var(--pill-accent, var(--color-dark));
		color: var(--pill-on-text, var(--color-dark-text));
		border-color: var(--pill-accent, var(--color-dark));
	}
	.btn.on:hover {
		filter: brightness(1.08);
	}
	.btn.bw {
		border-radius: 8px;
	}
	.sgrid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 10px;
		margin-top: 10px;
	}
	.sc {
		background: var(--color-card-soft);
		border-radius: 8px;
		padding: 12px 14px;
	}
	.sl {
		font-size: 11px;
		color: var(--color-text3);
		margin-bottom: 3px;
	}
	.sv {
		font-size: 22px;
		font-weight: 500;
	}
	.sv.red {
		color: #c0392b;
	}
	.sv.green {
		color: #0f6e56;
	}
	.sv-unit {
		font-size: 13px;
		color: var(--color-text3);
	}
	.ss {
		font-size: 11px;
		color: var(--color-text3);
		margin-top: 2px;
	}
	.r2 {
		display: grid;
		grid-template-columns: 1fr 320px;
		gap: 14px;
		align-items: start;
	}
	.ice-side {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}
	.card {
		background: var(--color-card);
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
		height: 420px;
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
		gap: 14px;
		flex-wrap: wrap;
		margin-top: 9px;
	}
	.li {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 11px;
		color: var(--color-text2);
	}
	.ld {
		width: 12px;
		height: 12px;
		border-radius: 2px;
		flex-shrink: 0;
	}
	.src {
		font-size: 11px;
		color: var(--color-text3);
		margin-top: 8px;
		line-height: 1.7;
	}
	.chart-wrap-tall {
		position: relative;
		height: 380px;
		width: 100%;
	}
	.tbl-wrap {
		overflow-x: auto;
		border: 0.5px solid var(--color-border);
		border-radius: 8px;
		background: var(--color-card);
	}
	.ktbl {
		width: 100%;
		border-collapse: collapse;
		font-size: 12px;
	}
	.ktbl th {
		background: var(--color-card-soft);
		padding: 9px 14px;
		text-align: right;
		font-weight: 500;
		color: var(--color-text2);
		border-bottom: 1px solid var(--color-border);
		border-right: 0.5px solid var(--color-border-soft);
		white-space: nowrap;
	}
	.ktbl th:last-child { border-right: none; }
	.ktbl th.left { text-align: left; }
	.ktbl th.center { text-align: center; }
	.ktbl th:first-child { border-top-left-radius: 7.5px; }
	.ktbl th:last-child { border-top-right-radius: 7.5px; }
	/* 정렬 화살표 공간 확보 */
	.ktbl th.th-sort { padding-right: 24px; position: relative; }
	.ktbl td {
		padding: 7px 14px;
		border-bottom: 0.5px solid var(--color-border-soft);
		border-right: 0.5px solid var(--color-border-soft);
		color: var(--color-text);
		text-align: right;
		white-space: nowrap;
	}
	.ktbl td:last-child { border-right: none; }
	.ktbl td.left { text-align: left; }
	.ktbl td.center { text-align: center; }
	.ktbl tr:last-child td {
		border-bottom: none;
	}
	.ktbl tr:hover td {
		background: #fafaf8;
	}
	.pill {
		display: inline-block;
		padding: 2px 8px;
		border-radius: 10px;
		font-size: 11px;
		font-weight: 500;
		margin-left: 4px;
	}
	.phi { background: #d4edda; color: #155724; }
	.pmd { background: #fff3cd; color: #856404; }
	.plo { background: #f8d7da; color: #721c24; }
	.score-bar {
		display: inline-block;
		height: 5px;
		border-radius: 3px;
		vertical-align: middle;
		margin-left: 4px;
	}
	@media (max-width: 900px) {
		.r2,
		.sgrid {
			grid-template-columns: 1fr;
		}
	}
</style>
