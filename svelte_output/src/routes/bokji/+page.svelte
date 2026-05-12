<script>
	import { onMount, onDestroy, untrack } from 'svelte';
	import { loadGraph, computeIsochrone } from '$lib/util/isochrone.js';
	import { applySort, compareBy } from '$lib/util/sortable.js';
	import bokji from '$lib/data/bokji.json';
	import Card from '$lib/components/Card.svelte';
	import ChartCard from '$lib/components/ChartCard.svelte';
	import MapShell from '$lib/components/MapShell.svelte';
	import Note from '$lib/components/Note.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import CountUp from '$lib/components/CountUp.svelte';

	const meta = {
		title: '복지·녹지 인프라',
		kicker: 'YANG · 노인복지관·경로당·공원',
		accent: 'var(--color-purple)'
	};

	const { DONG, WELFARE, PARK, GU_CENTER, SPEEDS, TC } = bokji;

	// ── 상태 (Svelte 5 runes) ──────────────────────────────────────
	let cW = $state(0);              // 보행자 인덱스
	let cFilter = $state('both');    // 시설 유형 + 지도 레이어 통합: both / welfare / park
	let cG = $state('종로구');        // 자치구
	let cSlope = $state(false);
	let sortKey = $state('combined');
	let sortDir = $state(/** @type {'asc' | 'desc'} */ ('desc'));
	function setSort(/** @type {string} */ k) {
		({ sortKey, sortDir } = applySort(k, sortKey, sortDir, ['gu']));
	}

	const gus = [...new Set(DONG.map((d) => d.gu))].sort();

	// ── 헬퍼 (도달 수 계산) ─────────────────────────────────────────
	function getW(d) {
		return (cSlope ? d.wc : d.w)[cW];
	}
	function getP(d) {
		return (cSlope ? d.pc : d.p)[cW];
	}
	function wScore(d) {
		const base = d.w[0];
		if (base === 0) return null;
		return parseFloat(((getW(d) / base) * 100).toFixed(1));
	}
	function pScore(d) {
		const base = d.p[0];
		if (base === 0) return null;
		return parseFloat(((getP(d) / base) * 100).toFixed(1));
	}
	function combinedScore(d) {
		const ws = wScore(d),
			ps = pScore(d);
		if (ws === null && ps === null) return null;
		if (ws === null) return ps;
		if (ps === null) return ws;
		return parseFloat(((ws + ps) / 2).toFixed(1));
	}
	function curScore(d) {
		if (cFilter === 'welfare') return wScore(d);
		if (cFilter === 'park') return pScore(d);
		return combinedScore(d);
	}
	function scoreColor(s) {
		if (s === null) return '#9E9E9E';
		if (s >= 80) return '#2E7D32';
		if (s >= 50) return '#F57F17';
		return '#C62828';
	}
	function hav(lat1, lng1, lat2, lng2) {
		const R = 6371000, toR = Math.PI / 180;
		const dlat = (lat2 - lat1) * toR, dlng = (lng2 - lng1) * toR;
		const a = Math.sin(dlat/2)**2 + Math.cos(lat1*toR)*Math.cos(lat2*toR)*Math.sin(dlng/2)**2;
		return R * 2 * Math.asin(Math.sqrt(Math.min(a, 1)));
	}

	// ── 통계 카드 ──────────────────────────────────────────────────
	const stats = $derived.by(() => {
		const gd = DONG.filter((d) => d.gu === cG);
		const n = gd.length || 1;
		const avgW = (gd.reduce((s, d) => s + getW(d), 0) / n).toFixed(1);
		const avgP = (gd.reduce((s, d) => s + getP(d), 0) / n).toFixed(1);
		const validW = gd.filter((d) => d.w[0] > 0);
		const validP = gd.filter((d) => d.p[0] > 0);
		const avgWS = validW.length
			? parseFloat((validW.reduce((s, d) => s + wScore(d), 0) / validW.length).toFixed(1))
			: null;
		const avgPS = validP.length
			? parseFloat((validP.reduce((s, d) => s + pScore(d), 0) / validP.length).toFixed(1))
			: null;
		return { gd, avgW, avgP, avgWS, avgPS };
	});

	// ── 자치구별 테이블 집계 ──────────────────────────────────────
	const guTableRows = $derived.by(() => {
		const guMap = {};
		DONG.forEach((d) => {
			if (!guMap[d.gu]) guMap[d.gu] = [];
			guMap[d.gu].push(d);
		});
		return Object.entries(guMap)
			.map(([gu, dongs]) => {
				const wCnt = WELFARE.filter((w) => w.gu === gu).length;
				const pCnt = PARK.filter((p) => p.gu === gu).length;
				const pop65Dongs = dongs.filter((d) => d.pop65 > 0);
				const validW = pop65Dongs.filter((d) => wScore(d) !== null);
				const validP = pop65Dongs.filter((d) => pScore(d) !== null);
				const ws = validW.length
					? parseFloat((validW.reduce((s, d) => s + wScore(d), 0) / validW.length).toFixed(1))
					: null;
				const ps = validP.length
					? parseFloat((validP.reduce((s, d) => s + pScore(d), 0) / validP.length).toFixed(1))
					: null;
				const combined =
					ws !== null && ps !== null ? parseFloat(((ws + ps) / 2).toFixed(1)) : ws ?? ps;
				return { gu, wCnt, pCnt, ws, ps, combined };
			})
			.sort(compareBy(sortKey, sortDir));
	});

	// ── Leaflet ────────────────────────────────────────────────────
	let mapEl = $state();
	let mapReady = $state(false);
	let map;
	let L;
	let welfareGroup;
	let parkGroup;
	let radiusCircle = null;
	let clickMark = null;
	/** @type {{lat:number,lng:number}|null} */
	let clickPoint = $state(null);
	let isoLayer = null;
	let graph = null;
	let graphLoading = $state(false);
	let graphError = $state('');
	let isoMeta = $state(/** @type {{count:number,ms:number}|null} */ (null));

	onMount(async () => {
		await import('leaflet/dist/leaflet.css');
		L = (await import('leaflet')).default;
		map = L.map(mapEl, { zoomControl: true }).setView([37.5665, 126.978], 11);
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			subdomains: 'abcd',
			maxZoom: 19,
			attribution: '&copy; OSM &copy; CARTO'
		}).addTo(map);

		welfareGroup = L.layerGroup().addTo(map);
		parkGroup = L.layerGroup().addTo(map);

		WELFARE.forEach((w) => {
			L.circleMarker([w.lat, w.lng], {
				radius: 5,
				color: TC[w.type] || '#185FA5',
				weight: 1,
				fillColor: TC[w.type] || '#185FA5',
				fillOpacity: 0.85
			})
				.bindTooltip(`<b>${w.name}</b><br><i style="color:#888">${w.type}</i>`)
				.addTo(welfareGroup);
		});

		PARK.forEach((p) => {
			const r = Math.max(3, Math.min(11, (p.area || 0) / 30000));
			L.circleMarker([p.lat, p.lng], {
				radius: r,
				color: '#2E7D32',
				weight: 1,
				fillColor: '#4CAF50',
				fillOpacity: 0.55
			})
				.bindTooltip(`<b>${p.name}</b><br>${p.area > 0 ? (p.area / 10000).toFixed(1) + 'ha' : ''}`)
				.addTo(parkGroup);
		});

		map.on('click', (e) => {
			const { lat, lng } = e.latlng;
			clickPoint = { lat, lng };
			map.setView([lat, lng], map.getZoom(), { animate: true, duration: 0.3 });
			if (clickMark) { map.removeLayer(clickMark); clickMark = null; }
			clickMark = L.circleMarker([lat, lng], {
				radius: 9, fillColor: '#ff3b30', color: '#fff',
				weight: 2.5, fillOpacity: 1, pane: 'markerPane'
			})
				.bindTooltip(`클릭 지점<br>${lat.toFixed(5)}, ${lng.toFixed(5)}`)
				.addTo(map);
			// 가장 가까운 자치구로 cG 갱신 → 차트 자동 연동
			let minDist = Infinity, nearestGu = null;
			for (const [gu, center] of Object.entries(GU_CENTER)) {
				const d = hav(lat, lng, center[0], center[1]);
				if (d < minDist) { minDist = d; nearestGu = gu; }
			}
			if (nearestGu) cG = nearestGu;
			// isochrone은 radiusCircle $effect가 clickPoint + cG 변경에 반응해 자동 계산
		});

		mapReady = true;
	});

	// 레이어 토글 (cFilter)
	$effect(() => {
		if (!mapReady) return;
		if (cFilter === 'welfare') {
			map.addLayer(welfareGroup);
			map.removeLayer(parkGroup);
		} else if (cFilter === 'park') {
			map.removeLayer(welfareGroup);
			map.addLayer(parkGroup);
		} else {
			map.addLayer(welfareGroup);
			map.addLayer(parkGroup);
		}
	});

	// 자치구 중심(또는 클릭 지점) 반경원 + 뷰 이동
	$effect(() => {
		if (!mapReady) return;
		// react to cG, cW, cSlope, clickPoint
		const cp = clickPoint;
		const origin = cp ? [cp.lat, cp.lng] : GU_CENTER[cG];
		if (radiusCircle) {
			map.removeLayer(radiusCircle);
			radiusCircle = null;
		}
		if (!origin) return;
		let radiusM = Math.round(SPEEDS[cW].mps * 30 * 60);
		let tooltipExtra = '';
		if (cSlope && cW > 0) {
			const gd = DONG.filter((d) => d.gu === cG);
			const avgTobler = gd.length ? gd.reduce((s, d) => s + d.tobler, 0) / gd.length : 1.0;
			radiusM = Math.round(SPEEDS[cW].mps * avgTobler * 30 * 60);
			tooltipExtra = ` (경사보정 · 구평균 tobler ${avgTobler.toFixed(3)})`;
		}
		radiusCircle = L.circle(origin, {
			radius: radiusM,
			color: '#b48ef4',
			weight: 2,
			dashArray: '8,5',
			fill: false
		})
			.bindTooltip(
				cp
					? `클릭 지점 · ${SPEEDS[cW].key} 30분 반경 ~${(radiusM / 1000).toFixed(2)} km${tooltipExtra}`
					: `${cG} 중심 · ${SPEEDS[cW].key} 30분 반경 ~${(radiusM / 1000).toFixed(2)} km${tooltipExtra}`
			)
			.addTo(map);
		// 클릭 지점은 setView 안 함 (사용자가 보고 있는 위치 보존), 자치구 중심일 때만 자동 이동
		if (!cp) map.setView(origin, 12, { animate: true, duration: 0.4 });
		// isochrone 폴리곤도 같이 갱신
		untrack(() => drawIsochrone(origin[0] ?? origin.lat, origin[1] ?? origin.lng, radiusM));
	});

	onDestroy(() => { isoLayer = null; map?.remove(); });

	const PURPLE = '#b48ef4';
	async function drawIsochrone(lat, lng, maxDistM) {
		if (!map || !L) return;
		if (isoLayer) { map.removeLayer(isoLayer); isoLayer = null; }
		isoMeta = null;
		try {
			if (!graph) {
				graphLoading = true;
				graphError = '';
				graph = await loadGraph();
				graphLoading = false;
			}
			const { ring, count, ms } = computeIsochrone(graph, lat, lng, maxDistM);
			if (!ring) { graphError = '도달 노드 부족 — 다른 지점 선택'; return; }
			isoLayer = L.polygon(ring, {
				color: PURPLE, weight: 2.5, opacity: 0.9,
				fillColor: PURPLE, fillOpacity: 0.18, smoothFactor: 1.2
			})
				.bindTooltip(`OSM 보행망 ${count.toLocaleString()} 노드 도달 · ${ms}ms`)
				.addTo(map);
			isoMeta = { count, ms };
			graphError = '';
		} catch (e) {
			console.error('[bokji] isochrone failed', e);
			graphError = '그래프 로드 실패 — 직선 반경만 표시';
			graphLoading = false;
		}
	}

	function resetToCenter() {
		if (clickMark && map) { map.removeLayer(clickMark); clickMark = null; }
		if (isoLayer && map) { map.removeLayer(isoLayer); isoLayer = null; }
		clickPoint = null;
		isoMeta = null;
	}

	// 보행자·경사 변경 시 기존 클릭 지점 이소크론 재계산
	$effect(() => {
		void cW; void cSlope;
		if (!untrack(() => mapReady)) return;
		const cp = untrack(() => clickPoint);
		if (!cp) return;
		const gd = DONG.filter((d) => d.gu === untrack(() => cG));
		const tobler = cSlope && cW > 0 ? gd.reduce((s, d) => s + d.tobler, 0) / Math.max(1, gd.length) : 1.0;
		const maxDistM = Math.round(SPEEDS[cW].mps * tobler * 30 * 60);
		drawIsochrone(cp.lat, cp.lng, maxDistM);
	});

	// ── Chart.js ──────────────────────────────────────────────────
	let Chart;
	let guChart;
	let dropoffChart;
	let scatterChart;
	let radarChart;
	let dongChart;

	async function ensureChart() {
		if (!Chart) Chart = (await import('chart.js/auto')).default;
		return Chart;
	}

	async function setupGuChart(canvas) {
		const C = await ensureChart();
		guChart = new C(canvas, {
			type: 'bar',
			data: { labels: [], datasets: [] },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 200 },
				indexAxis: 'y',
				layout: { padding: { top: 2, bottom: 2, right: 10 } },
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: { label: (c) => ` ${parseFloat(c.raw).toFixed(1)}개 (평균)` }
					}
				},
				scales: {
					x: {
						grid: { color: '#f1efe8' },
						title: { display: true, text: '평균 도달 가능 시설 수', font: { size: 10 } }
					},
					y: { ticks: { font: { size: 9 } } }
				}
			}
		});
		updateGuChart();
	}

	// 속도 si에서 dongs 그룹의 평균 도달가능점수 (type='w'|'p')
	function avgScoreAtSpeed(dongs, type, si) {
		const arr =
			type === 'w'
				? dongs
						.filter((d) => d.w[0] > 0)
						.map((d) => ((cSlope && si > 0 ? d.wc[si] : d.w[si]) / d.w[0]) * 100)
				: dongs
						.filter((d) => d.p[0] > 0)
						.map((d) => ((cSlope && si > 0 ? d.pc[si] : d.p[si]) / d.p[0]) * 100);
		return arr.length ? parseFloat((arr.reduce((s, v) => s + v, 0) / arr.length).toFixed(1)) : null;
	}

	// ── Chart A: 속도별 도달가능점수 드롭오프 라인차트 ──────────────
	async function setupDropoffChart(canvas) {
		const C = await ensureChart();
		dropoffChart = new C(canvas, {
			type: 'line',
			data: { labels: SPEEDS.map((s) => s.key), datasets: [] },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 180 },
				plugins: {
					legend: { position: 'top', labels: { font: { size: 10 }, boxWidth: 12, padding: 8 } },
					tooltip: { callbacks: { label: (c) => ` ${parseFloat(c.raw).toFixed(1)}점` } }
				},
				scales: {
					x: { grid: { display: false }, ticks: { font: { size: 10 } } },
					y: {
						min: 0,
						max: 100,
						grid: { color: '#f1efe8' },
						title: { display: true, text: '도달가능점수 (%)', font: { size: 10 } },
						ticks: { font: { size: 10 }, callback: (v) => v + '점' }
					}
				}
			}
		});
		updateDropoffChart();
	}

	function updateDropoffChart() {
		if (!dropoffChart) return;
		const gd = DONG.filter((d) => d.gu === cG);
		const all = DONG;
		const slopeSuffix = cSlope ? ' (경사보정)' : '';
		dropoffChart.data.datasets = [
			{
				label: `${cG} 복지${slopeSuffix}`,
				data: SPEEDS.map((_, i) => avgScoreAtSpeed(gd, 'w', i)),
				borderColor: '#185FA5',
				backgroundColor: '#185FA515',
				tension: 0.3,
				pointRadius: 4,
				fill: true
			},
			{
				label: `${cG} 공원${slopeSuffix}`,
				data: SPEEDS.map((_, i) => avgScoreAtSpeed(gd, 'p', i)),
				borderColor: '#2E7D32',
				backgroundColor: '#2E7D3215',
				tension: 0.3,
				pointRadius: 4,
				fill: true
			},
			{
				label: '서울 전체 복지',
				data: SPEEDS.map((_, i) => avgScoreAtSpeed(all, 'w', i)),
				borderColor: '#185FA5',
				borderDash: [4, 3],
				backgroundColor: 'transparent',
				tension: 0.3,
				pointRadius: 2,
				borderWidth: 1.2
			},
			{
				label: '서울 전체 공원',
				data: SPEEDS.map((_, i) => avgScoreAtSpeed(all, 'p', i)),
				borderColor: '#2E7D32',
				borderDash: [4, 3],
				backgroundColor: 'transparent',
				tension: 0.3,
				pointRadius: 2,
				borderWidth: 1.2
			}
		];
		dropoffChart.update('none');
	}

	// ── Chart B: 복지·공원 도달 버블 산점도 ──────────────────────────
	async function setupScatterChart(canvas) {
		const C = await ensureChart();
		scatterChart = new C(canvas, {
			type: 'bubble',
			data: { datasets: [] },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 180 },
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label: (c) => {
								const d = c.raw._dong;
								if (!d) return '';
								return [`${d.dong}`, `복지:${c.raw.x}개 공원:${c.raw.y}개`, `노인인구:${d.pop65}명`];
							}
						}
					}
				},
				scales: {
					x: {
						grid: { color: '#f1efe8' },
						title: { display: true, text: '복지시설 도달 수', font: { size: 10 } },
						ticks: { font: { size: 10 } }
					},
					y: {
						grid: { color: '#f1efe8' },
						title: { display: true, text: '공원 도달 수', font: { size: 10 } },
						ticks: { font: { size: 10 } }
					}
				}
			}
		});
		updateScatterChart();
	}

	function updateScatterChart() {
		if (!scatterChart) return;
		const gd = DONG.filter((d) => d.gu === cG && d.pop65 > 0);
		const maxPop = Math.max(...gd.map((d) => d.pop65), 1);
		const points = gd.map((d) => {
			const col =
				cW === 0
					? d.vuln >= 0.7
						? 'rgba(198,40,40,0.75)'
						: d.vuln >= 0.4
							? 'rgba(245,127,23,0.75)'
							: 'rgba(46,125,50,0.75)'
					: scoreColor(combinedScore(d)) + 'bb';
			return { x: getW(d), y: getP(d), r: Math.max(4, Math.round((d.pop65 / maxPop) * 16)), _dong: d };
		});
		scatterChart.data.datasets = [
			{
				data: points,
				backgroundColor: points.map((_, i) => {
					const d = gd[i];
					return cW === 0
						? d.vuln >= 0.7
							? 'rgba(198,40,40,0.75)'
							: d.vuln >= 0.4
								? 'rgba(245,127,23,0.75)'
								: 'rgba(46,125,50,0.75)'
						: scoreColor(combinedScore(d)) + 'bb';
				})
			}
		];
		scatterChart.update('none');
	}

	// ── Chart C: 보행 접근성 프로필 레이더차트 ───────────────────────
	async function setupRadarChart(canvas) {
		const C = await ensureChart();
		radarChart = new C(canvas, {
			type: 'radar',
			data: {
				labels: SPEEDS.slice(1)
					.map((s) => `복지(${s.key})`)
					.concat(SPEEDS.slice(1).map((s) => `공원(${s.key})`)),
				datasets: []
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 180 },
				plugins: {
					legend: { position: 'top', labels: { font: { size: 10 }, boxWidth: 12 } },
					tooltip: { callbacks: { label: (c) => ` ${parseFloat(c.raw).toFixed(1)}점` } }
				},
				scales: {
					r: {
						min: 0,
						max: 100,
						ticks: { font: { size: 9 }, stepSize: 20, callback: (v) => v + '점' },
						pointLabels: { font: { size: 9 } },
						grid: { color: '#e8e4db' },
						angleLines: { color: '#d3d1c7' }
					}
				}
			}
		});
		updateRadarChart();
	}

	function updateRadarChart() {
		if (!radarChart) return;
		const gd = DONG.filter((d) => d.gu === cG);
		const all = DONG;
		const guVals = [1, 2, 3]
			.map((i) => avgScoreAtSpeed(gd, 'w', i) ?? 0)
			.concat([1, 2, 3].map((i) => avgScoreAtSpeed(gd, 'p', i) ?? 0));
		const allVals = [1, 2, 3]
			.map((i) => avgScoreAtSpeed(all, 'w', i) ?? 0)
			.concat([1, 2, 3].map((i) => avgScoreAtSpeed(all, 'p', i) ?? 0));
		const slopeSuffix = cSlope ? ' (경사보정)' : '';
		radarChart.data.datasets = [
			{
				label: `${cG}${slopeSuffix}`,
				data: guVals,
				borderColor: '#8b5cf6',
				backgroundColor: '#8b5cf620',
				pointBackgroundColor: '#8b5cf6',
				borderWidth: 2
			},
			{
				label: '서울 전체',
				data: allVals,
				borderColor: '#9E9E9E',
				backgroundColor: 'transparent',
				borderDash: [4, 3],
				pointBackgroundColor: '#9E9E9E',
				borderWidth: 1.5
			}
		];
		radarChart.update('none');
	}

	async function setupDongChart(canvas) {
		const C = await ensureChart();
		dongChart = new C(canvas, {
			type: 'bar',
			data: { labels: [], datasets: [] },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 200 },
				indexAxis: 'y',
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label: (c) => ` 도달가능점수: ${parseFloat(c.raw).toFixed(1)}점`
						}
					}
				},
				scales: {
					x: {
						grid: { color: '#f1efe8' },
						title: { display: true, text: '', font: { size: 10 } }
					},
					y: { ticks: { font: { size: 9 } } }
				}
			}
		});
		updateDongChart();
	}

	function updateGuChart() {
		if (!guChart) return;
		const guMap = {};
		DONG.forEach((d) => {
			if (!guMap[d.gu]) guMap[d.gu] = [];
			guMap[d.gu].push(d);
		});
		let vals = Object.entries(guMap).map(([g, dongs]) => {
			let v;
			if (cFilter === 'welfare') v = dongs.reduce((s, d) => s + getW(d), 0) / dongs.length;
			else if (cFilter === 'park') v = dongs.reduce((s, d) => s + getP(d), 0) / dongs.length;
			else v = dongs.reduce((s, d) => s + getW(d) + getP(d), 0) / dongs.length;
			return { gu: g, val: v };
		});
		vals.sort((a, b) => b.val - a.val);
		guChart.data.labels = vals.map((v) => v.gu);
		guChart.data.datasets = [
			{
				data: vals.map((v) => +v.val.toFixed(2)),
				backgroundColor: vals.map((v) => (v.gu === cG ? '#D85A30' : SPEEDS[cW].color + 'aa')),
				borderRadius: 3,
				minBarLength: 4,
				barPercentage: 0.9,
				categoryPercentage: 0.92
			}
		];
		guChart.update('none');
	}

	function updateDongChart() {
		if (!dongChart) return;
		const gd = DONG.filter((d) => d.gu === cG && d.pop65 > 0);
		dongChart.options.scales.x.max = 100;
		dongChart.options.scales.x.min = 0;
		dongChart.options.scales.x.title.text = '도달가능점수 (점)';
		const withScores = gd
			.map((d) => ({ d, s: curScore(d) }))
			.filter(({ s }) => s !== null)
			.sort((a, b) => (a.s ?? 0) - (b.s ?? 0));
		const colors = withScores.map(({ s }) => {
			if (s >= 80) return 'rgba(15,110,86,0.8)';
			if (s >= 50) return 'rgba(133,79,11,0.8)';
			return 'rgba(163,45,45,0.85)';
		});
		dongChart.data.labels = withScores.map(({ d }) => d.dong);
		dongChart.data.datasets = [
			{ data: withScores.map(({ s }) => parseFloat((s ?? 0).toFixed(1))), backgroundColor: colors, borderRadius: 3, minBarLength: 4 }
		];
		dongChart.update('none');
	}

	// 컨트롤 변경 시 차트 재그리기
	$effect(() => {
		void cW;
		void cFilter;
		void cG;
		void cSlope;
		updateGuChart();
		updateDropoffChart();
		updateScatterChart();
		updateRadarChart();
		updateDongChart();
	});

	// ── 테이블 헬퍼 ────────────────────────────────────────────────
	function gradePillClass(sc) {
		return sc == null ? 'pna' : sc >= 80 ? 'phi' : sc >= 50 ? 'pmd' : 'plo';
	}
	function gradeText(sc) {
		return sc == null ? '-' : sc >= 80 ? '양호' : sc >= 50 ? '보통' : '미흡';
	}
	function scoreBarStyle(sc) {
		if (sc == null) return 'display:none';
		const col = scoreColor(sc);
		const w = Math.round((sc * 40) / 100);
		return `background:${col};width:${w}px`;
	}
	const dongChartTitle = $derived(
		`${cG} 행정동별 도달가능점수${cSlope ? ' (경사보정)' : ''}`
	);
	const dongChartHeight = $derived(
		Math.max(280, DONG.filter((d) => d.gu === cG && d.pop65 > 0).length * 26 + 50) + 'px'
	);
</script>

<svelte:head>
	<title>④ 복지/녹지 — 노인 복지·녹지 접근성 분석</title>
</svelte:head>

<section class="bokji-hero">
	<div class="hero-glow"></div>
	<div class="bokji-hero-inner">
		<div class="hero-text">
			<p class="hero-kicker">④ 복지/녹지 · 양석준</p>
			<h1 class="hero-title">
				노인 <em>복지·녹지</em> 접근성
			</h1>
			<div class="hero-chips">
				<span class="chip purple">🏛 복지시설 {WELFARE.length}개소</span>
				<span class="chip purple">🌳 공원 {PARK.length}개소</span>
				<span class="chip-sep">·</span>
				<span class="chip muted">428개 행정동 · OSM 보행 네트워크 · Tobler 경사보정 · 서울시 2025</span>
			</div>
		</div>
	</div>
</section>

<section class="wrap mx-auto px-[18px] pt-[18px] pb-[52px]" style:max-width="1320px">
	<!-- ── 컨트롤 패널 ── -->
	<div class="ctrl">
		<div class="crow">
			<span class="lbl">보행자 유형</span>
			{#each SPEEDS as s, i}
				<button type="button" class="btn bw" class:on={cW === i} onclick={() => (cW = i)}>
					{['🚶', '🧓', '🦽', '♿'][i]} {s.key} &nbsp;{s.mps} m/s
				</button>
			{/each}
		</div>
		<div class="crow">
			<span class="lbl">레이어</span>
			<button
				type="button"
				class="chk-btn slope"
				class:on={cSlope}
				onclick={() => (cSlope = !cSlope)}
			>
				<span class="chk-dot" style="background:#8B5CF6"></span>경사로 보정
			</button>
			<span class="ml-1 text-[11px]" style:color="var(--color-text3)">
				· Tobler 보행속도 모델 · OSM 기반 동별 경사도 반영 · 일반인 속도 제외
			</span>
		</div>
		<div class="crow">
			<span class="lbl">기준 자치구</span>
			<select bind:value={cG}>
				{#each gus as g}
					<option value={g}>{g}</option>
				{/each}
			</select>
			<span class="ml-1.5 text-[11px]" style:color="var(--color-text3)"
				>자치구 중심점 기준 · 점선 원은 30분 내 도달 가능 범위</span
			>
		</div>

		<!-- ── 통계 4열 ── -->
		<div class="mt-3">
			{#key cG + '|' + cW + '|' + cSlope}
			<StatGrid cols={4}>
				<StatCard
					label="평균 도달 복지시설 수"
					sub={`${cG} · ${SPEEDS[cW].key} · 30분${cSlope && cW > 0 ? ' · 경사보정' : ''}`}
				>
					{#snippet children()}
						<CountUp value={+stats.avgW} decimals={1} suffix="개소" />
					{/snippet}
				</StatCard>
				<StatCard
					label="평균 도달 공원 수"
					sub={`${cG} · ${SPEEDS[cW].key} · 30분${cSlope && cW > 0 ? ' · 경사보정' : ''}`}
				>
					{#snippet children()}
						<CountUp value={+stats.avgP} decimals={1} suffix="개소" />
					{/snippet}
				</StatCard>
				<StatCard
					label={`복지 도달가능점수${cSlope && cW > 0 ? ' (경사보정)' : ''}`}
					sub={cW === 0 ? '노인 보행자 선택 시 표시' : `${cG} · ${SPEEDS[cW].key} · 일반인 대비`}
					tone="blue"
				>
					{#snippet children()}
						{#if cW === 0 || stats.avgWS === null}—{:else}
							<CountUp value={stats.avgWS} decimals={1} suffix="점" />
						{/if}
					{/snippet}
				</StatCard>
				<StatCard
					label={`공원 도달가능점수${cSlope && cW > 0 ? ' (경사보정)' : ''}`}
					sub={cW === 0 ? '노인 보행자 선택 시 표시' : `${cG} · ${SPEEDS[cW].key} · 일반인 대비`}
					tone="green"
				>
					{#snippet children()}
						{#if cW === 0 || stats.avgPS === null}—{:else}
							<CountUp value={stats.avgPS} decimals={1} suffix="점" />
						{/if}
					{/snippet}
				</StatCard>
			</StatGrid>
			{/key}
		</div>
	</div>

	<!-- ── 지도 (단독 full-width) ── -->
	<div class="mt-3.5">
		<Card title="서울시 복지·녹지 시설 분포 지도">
			<div class="map-top-row mb-2.5">
				<div class="map-tabs">
					<button
						type="button"
						class="btn"
						class:on={cFilter === 'both'}
						onclick={() => (cFilter = 'both')}>복지시설 + 공원</button
					>
					<button
						type="button"
						class="btn"
						class:on={cFilter === 'welfare'}
						onclick={() => (cFilter = 'welfare')}>복지시설만</button
					>
					<button
						type="button"
						class="btn"
						class:on={cFilter === 'park'}
						onclick={() => (cFilter = 'park')}>공원만</button
					>
				</div>
				<div class="iso-meta">
					{#if graphLoading}
						<span class="iso-loading">⚙ OSM 보행망 로드 중…</span>
					{:else if graphError}
						<span class="iso-err">⚠ {graphError}</span>
					{:else if isoMeta}
						<span class="iso-ok">OSM 보행망 <b>{isoMeta.count.toLocaleString()}</b> 노드 도달 · {isoMeta.ms}ms</span>
					{/if}
				</div>
			</div>
			<MapShell
				height="420px"
				legend={[
					{ color: '#185FA5', label: '노인복지관', shape: 'circle' },
					{ color: '#E8A838', label: '노인교실', shape: 'circle' },
					{ color: '#8AAFD4', label: '소규모복지관', shape: 'circle' },
					{ color: '#4CAF50', label: '공원', shape: 'circle' },
					{ color: '#b48ef4', label: '30분 보행반경 (점선)' },
					{ color: '#b48ef4', label: 'OSM 보행망 도달범위 (클릭)' }
				]}
				source="출처: 서울시 사회복지시설(노인여가복지시설) 목록 · 서울시 주요 공원현황(2026 상반기) · 반경 = 자치구 중심점 기준 직선거리 · 채워진 폴리곤 = OSM 보행망 Dijkstra+Convex Hull (지도 클릭 시 계산)"
			>
				<div bind:this={mapEl} class="absolute inset-0 h-full w-full"></div>
				{#if clickPoint}
					<button type="button" class="map-reset-btn" onclick={resetToCenter}>중심점</button>
				{/if}
			</MapShell>
		</Card>
	</div>

	<!-- ── 3개 시각화 차트 ── -->
	<div class="r3 mt-3.5">
		<ChartCard
			title={`${cG} 속도별 도달가능점수 드롭오프`}
			height="260px"
			onmount={setupDropoffChart}
		/>
		<ChartCard
			title={`${cG} 행정동 복지·공원 도달 분포`}
			height="260px"
			onmount={setupScatterChart}
		/>
		<ChartCard
			title={`${cG} 보행 접근성 프로필 (vs 서울 전체)`}
			height="260px"
			onmount={setupRadarChart}
		/>
	</div>

	<!-- ── 자치구별 차트 + TOP10 ── -->
	<div class="r2b mt-3.5">
		<ChartCard
			title="자치구별 평균 도달 시설 수 (현재 보행자·시설 기준)"
			height="300px"
			onmount={setupGuChart}
		/>
		<div style="position:relative">
			<ChartCard title={dongChartTitle} height={dongChartHeight} onmount={setupDongChart} />
			{#if cW === 0}
				<div class="tbl-overlay">
					<div style="font-size:28px">📊</div>
					<div style="font-size:13px;font-weight:500;color:#5f5e5a">노인 보행자를 선택하세요</div>
					<div class="tbl-overlay-sub">일반인은 비교 기준값(분모)이므로<br />모든 동이 <b>100점</b> — 비교 의미 없음</div>
				</div>
			{/if}
		</div>
	</div>

	<!-- ── 자치구별 집계 테이블 ── -->
	<div class="card-shell mt-3.5">
		<div class="ct-label mb-2">자치구별 복지·녹지 접근성 상세표</div>
		<p class="mb-1.5 text-[11px]" style:color="var(--color-text3)">
			열 헤더 클릭으로 정렬 · {SPEEDS[cW].key} 기준 · 일반인 도달 수 = 0 시 N/A{cSlope ? ' · 경사로 보정 적용' : ''}
		</p>
		<div style="position:relative">
			<div class="tbl-wrap">
				<table class="ktbl">
					<thead>
						<tr>
							<th class="th-sort" class:active={sortKey==='gu'} onclick={() => setSort('gu')}>
								자치구{#if sortKey==='gu'}<span class="sort-arr">{sortDir==='desc'?'▼':'▲'}</span>{/if}
							</th>
							<th class="th-sort" class:active={sortKey==='wCnt'} onclick={() => setSort('wCnt')}>
								복지시설 수{#if sortKey==='wCnt'}<span class="sort-arr">{sortDir==='desc'?'▼':'▲'}</span>{/if}
							</th>
							<th class="th-sort" class:active={sortKey==='pCnt'} onclick={() => setSort('pCnt')}>
								공원시설 수{#if sortKey==='pCnt'}<span class="sort-arr">{sortDir==='desc'?'▼':'▲'}</span>{/if}
							</th>
							<th class="th-sort" class:active={sortKey==='ws'} onclick={() => setSort('ws')}>
								복지 점수{cSlope ? ' (경사)' : ''}{#if sortKey==='ws'}<span class="sort-arr">{sortDir==='desc'?'▼':'▲'}</span>{/if}
							</th>
							<th class="th-sort" class:active={sortKey==='ps'} onclick={() => setSort('ps')}>
								녹지 점수{cSlope ? ' (경사)' : ''}{#if sortKey==='ps'}<span class="sort-arr">{sortDir==='desc'?'▼':'▲'}</span>{/if}
							</th>
							<th class="th-sort" class:active={sortKey==='combined'} onclick={() => setSort('combined')}>
								합산 점수{#if sortKey==='combined'}<span class="sort-arr">{sortDir==='desc'?'▼':'▲'}</span>{/if}
							</th>
							<th>접근성</th>
						</tr>
					</thead>
					<tbody>
						{#each guTableRows as r (r.gu)}
							<tr>
								<td style="text-align:left">{r.gu}</td>
								<td>{r.wCnt}</td>
								<td>{r.pCnt}</td>
								<td>
									<b style="color:{scoreColor(r.ws)}">{r.ws !== null ? r.ws.toFixed(1) + '점' : 'N/A'}</b>
									<span class="score-bar" style={scoreBarStyle(r.ws)}></span>
								</td>
								<td>
									<b style="color:{scoreColor(r.ps)}">{r.ps !== null ? r.ps.toFixed(1) + '점' : 'N/A'}</b>
									<span class="score-bar" style={scoreBarStyle(r.ps)}></span>
								</td>
								<td>
									<b style="color:{scoreColor(r.combined)}">{r.combined !== null ? r.combined.toFixed(1) + '점' : 'N/A'}</b>
									<span class="score-bar" style={scoreBarStyle(r.combined)}></span>
								</td>
								<td><span class="pill {gradePillClass(r.combined)}">{gradeText(r.combined)}</span></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if cW === 0}
				<div class="tbl-overlay">
					<div style="font-size:28px">📋</div>
					<div style="font-size:13px;font-weight:500;color:#5f5e5a">노인 보행자를 선택하세요</div>
					<div class="tbl-overlay-sub">일반인은 비교 기준값(분모)이므로<br />모든 구가 <b>100점</b> — 비교 의미 없음</div>
				</div>
			{/if}
		</div>
	</div>

	<Note tone="warm" class="mt-3">
		※ 도달가능점수 = (선택 속도 도달 시설 수 / 일반인 속도 도달 시설 수) × 100 · 분모(일반인 도달 수) = 0이면 N/A<br />
		※ 경사로 보정: Tobler 보행속도 모델 적용 · 동별 OSM 경사도 기반 · 일반인 속도는 보정 대상 제외<br />
		※ 분석 기준: OSM 보행 네트워크 · 30분 보행 · 행정동 중심점 출발 · 서울시 2026
	</Note>
</section>

<style>
	.ctrl {
		background: var(--color-card);
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 16px 20px;
		margin-bottom: 14px;
	}
	.crow {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
		margin-bottom: 10px;
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
		margin-right: 2px;
	}
	select {
		font-size: 12px;
		padding: 5px 10px;
		border-radius: 8px;
		border: 0.5px solid var(--color-text4);
		background: #fff;
		color: var(--color-text);
		font-family: inherit;
		cursor: pointer;
		outline: none;
	}
	select:focus {
		border-color: var(--color-text2);
	}
	/* ── 버튼 (ShelterTab 통일) ── */
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
	.chk-btn {
		font-size: 12px;
		padding: 5px 13px;
		border-radius: 20px;
		border: 0.5px solid var(--color-text4);
		background: transparent;
		color: var(--color-text2);
		cursor: pointer;
		transition: all 0.14s;
		font-family: inherit;
		white-space: nowrap;
		display: flex;
		align-items: center;
		gap: 5px;
	}
	.chk-btn:hover {
		border-color: var(--color-text2);
		color: var(--color-text);
	}
	.chk-btn.slope.on {
		background: #f0eafd;
		border-color: #8b5cf6;
		color: #5b21b6;
	}
	.chk-btn.dong.on {
		background: #fff4e5;
		border-color: #ff6f00;
		color: #c05000;
	}
	.chk-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	/* ── 오버레이 (일반인 잠금) ── */
	.tbl-overlay {
		position: absolute;
		inset: 0;
		border-radius: 8px;
		background: rgba(245,244,240,0.92);
		backdrop-filter: blur(3px);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 10px;
		padding: 20px;
	}
	.tbl-overlay-sub {
		font-size: 11px;
		color: #aaa9a5;
		text-align: center;
		line-height: 1.7;
		background: #fff;
		border-radius: 8px;
		padding: 8px 14px;
	}
	/* ── 그리드 ── */
	.r2 {
		display: grid;
		grid-template-columns: 1.45fr 1fr;
		gap: 14px;
	}
	.r2b {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 14px;
	}
	/* ── 3열 차트 그리드 ── */
	.r3 {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 14px;
	}
	.map-top-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		flex-wrap: wrap;
	}
	.map-tabs {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}
	.iso-meta {
		font-family: var(--font-mono);
		font-size: 10.5px;
		color: var(--color-text3);
		letter-spacing: 0.04em;
		min-height: 16px;
	}
	.iso-loading { color: var(--color-text3); opacity: 0.85; }
	.iso-err { color: #c0392b; }
	.iso-ok b { color: var(--color-text); font-weight: 600; }
	.map-reset-btn {
		position: absolute;
		top: 10px;
		right: 10px;
		z-index: 1000;
		padding: 5px 12px;
		border-radius: 6px;
		border: 0.5px solid var(--color-border);
		background: rgba(255,255,255,0.92);
		backdrop-filter: blur(4px);
		font-size: 12px;
		font-family: inherit;
		color: var(--color-text);
		cursor: pointer;
		box-shadow: 0 1px 4px rgba(0,0,0,0.12);
		transition: background 0.14s;
	}
	.map-reset-btn:hover { background: #fff; }
	/* ── 테이블 (ShelterTab ktbl 통일) ── */
	.tbl-wrap {
		overflow-x: auto;
	}
	.ktbl {
		width: 100%;
		border-collapse: collapse;
		font-size: 12px;
		table-layout: fixed;
	}
	.ktbl th {
		background: var(--color-card-soft);
		padding: 8px 10px;
		text-align: right;
		font-weight: 500;
		color: var(--color-text2);
		border-bottom: 1px solid var(--color-border);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	/* 정렬 화살표 공간 확보 — 글자와 겹치지 않도록 */
	.ktbl th.th-sort {
		padding-right: 24px;
		position: relative;
		overflow: visible;
	}
	.ktbl th:first-child {
		text-align: left;
		width: 88px;
	}
	.ktbl th:last-child {
		text-align: center;
	}
	.ktbl td {
		padding: 7px 10px;
		border-bottom: 0.5px solid var(--color-border-soft);
		color: var(--color-text);
		text-align: right;
		white-space: nowrap;
		overflow: hidden;
	}
	.ktbl td:first-child {
		text-align: left;
	}
	.ktbl td:last-child {
		text-align: center;
	}
	.ktbl tr:hover td {
		background: #fafaf8;
	}
	.score-bar {
		display: inline-block;
		height: 8px;
		border-radius: 3px;
		vertical-align: middle;
		margin-left: 4px;
	}
	.pill {
		display: inline-block;
		padding: 2px 8px;
		border-radius: 10px;
		font-size: 11px;
		font-weight: 500;
	}
	.phi {
		background: #2e7d3218;
		color: #2e7d32;
	}
	.pmd {
		background: #f57f1718;
		color: #e65100;
	}
	.plo {
		background: #c6282818;
		color: #c62828;
	}
	.pna {
		background: #9e9e9e14;
		color: #666;
	}
	/* .th-sort / .sort-arr 는 layout.css 글로벌 정의 사용 — 페이지 로컬 override 제거.
	   글로벌이 활성 시에도 헤더 글자색 그대로 두고, 화살표만 도메인 액센트 (var(--pill-accent)) 로 표시. */
	.bokji-hero {
		position: relative;
		background: var(--color-dark);
		color: var(--color-dark-text);
		padding: 22px 28px;
		overflow: hidden;
	}
	.hero-glow {
		pointer-events: none;
		position: absolute;
		top: -60px;
		right: -80px;
		width: 340px;
		height: 340px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(180,142,244,0.18), transparent 65%);
	}
	.bokji-hero-inner {
		position: relative;
		max-width: 1320px;
		margin: 0 auto;
	}
	.hero-kicker {
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-purple);
		opacity: 0.85;
		margin-bottom: 8px;
	}
	.hero-title {
		font-family: var(--font-display);
		font-size: 26px;
		line-height: 1.2;
		margin-bottom: 12px;
		color: var(--color-dark-text);
	}
	.hero-title em {
		font-style: normal;
		color: var(--color-purple);
	}
	.hero-chips {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}
	.chip {
		font-size: 11px;
		padding: 3px 9px;
		border-radius: 12px;
		background: rgba(255,255,255,0.07);
		color: rgba(241,239,232,0.65);
		white-space: nowrap;
	}
	.chip.purple {
		background: rgba(180,142,244,0.15);
		color: #b48ef4;
		border: 0.5px solid rgba(180,142,244,0.3);
	}
	.chip.muted {
		background: transparent;
		color: rgba(241,239,232,0.35);
	}
	.chip-sep {
		color: rgba(241,239,232,0.25);
		font-size: 11px;
	}
	@media (max-width: 900px) {
		.r2,
		.r2b,
		.r3 {
			grid-template-columns: 1fr;
		}
	}
	/* Leaflet 컨테이너 */
	:global(.leaflet-container) {
		font-family: inherit;
		background: #e8e4db;
	}
</style>
