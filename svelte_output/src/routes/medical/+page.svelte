<script>
	import { onMount, onDestroy } from 'svelte';
	import medical from '$lib/data/medical.json';
	import facilities from '$lib/data/medical_facilities.json';
	import Card from '$lib/components/Card.svelte';
	import MapShell from '$lib/components/MapShell.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import Note from '$lib/components/Note.svelte';
	import KickerLabel from '$lib/components/KickerLabel.svelte';

	const meta = { title: '의료', kicker: 'LEE · 병의원·접근성', accent: 'var(--color-pink)' };

	/** @type {{ COUNTS: Record<string, Record<string, number>>, DONG_META: Record<string, {fn:string,gu:string,el:number}>, GEOJSON: any, SPEEDS: {id:string,label:string,speed:number,color:string}[] }} */
	const { COUNTS, DONG_META, GEOJSON, SPEEDS } = medical;

	const AVG_TOBLER = 0.8006;

	// ─── 상태 (Svelte 5 runes) ───
	let cB = $state(2); // 비교 속도 인덱스 (1/2/3)
	let cT = $state(15); // 시간(분) 15/30/45
	let cF = $state('all'); // 시설 유형 all/hosp/pharm
	let cSlope = $state(false);
	let cTop = $state('impact'); // impact | score

	// ─── POI 지도 토글 상태 ───
	let showHosp = $state(true);
	let showPharm = $state(true);

	// ─── 헬퍼 ───
	/**
	 * @param {string} speedId
	 * @param {number} time
	 * @param {string} ftype
	 * @param {string} dc
	 * @param {boolean} isSlope
	 */
	function getN(speedId, time, ftype, dc, isSlope) {
		const s = isSlope ? 'slope' : 'flat';
		if (ftype === 'all') {
			return (
				(COUNTS[`${speedId}_${time}_hosp_${s}`]?.[dc] || 0) +
				(COUNTS[`${speedId}_${time}_pharm_${s}`]?.[dc] || 0)
			);
		}
		return COUNTS[`${speedId}_${time}_${ftype}_${s}`]?.[dc] || 0;
	}

	/** @param {string} dc */
	function dongScore(dc) {
		const nYoung = getN('young', cT, cF, dc, cSlope);
		const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
		return nYoung > 0 ? (nB / nYoung) * 100 : 100;
	}

	/** @param {number} v */
	function scoreColor(v) {
		if (v >= 90) return '#1a9850';
		if (v >= 80) return '#91cf60';
		if (v >= 70) return '#d9ef8b';
		if (v >= 60) return '#fee08b';
		if (v >= 50) return '#fdae61';
		if (v >= 40) return '#d73027';
		return '#a50026';
	}
	/** @param {number} v */
	function ptScoreColor(v) {
		if (v >= 90) return 'rgba(26,152,80,.8)';
		if (v >= 80) return 'rgba(145,207,96,.8)';
		if (v >= 70) return 'rgba(217,239,139,.9)';
		if (v >= 60) return 'rgba(254,224,139,.9)';
		if (v >= 50) return 'rgba(253,174,97,.8)';
		if (v >= 40) return 'rgba(215,48,39,.8)';
		return 'rgba(165,0,38,.8)';
	}

	// ─── 통계 계산 (반응형 derived) ───
	const allDongStats = $derived.by(() => {
		// cB / cT / cF / cSlope 변경 시 재계산
		void cB;
		void cT;
		void cF;
		void cSlope;
		return Object.keys(DONG_META).map((dc) => {
			const nYoung = getN('young', cT, cF, dc, cSlope);
			const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
			const score = nYoung > 0 ? (nB / nYoung) * 100 : 100;
			const m = DONG_META[dc];
			const impact = Math.round((Math.max(0, 100 - score) / 100) * m.el);
			return { dc, fn: m.fn, gu: m.gu, el: m.el, nYoung, nB, score, impact };
		});
	});

	const guStats = $derived.by(() => {
		/** @type {Record<string,{sum:number,cnt:number,impact:number}>} */
		const byGu = {};
		allDongStats
			.filter((r) => r.nYoung > 0)
			.forEach((r) => {
				if (!byGu[r.gu]) byGu[r.gu] = { sum: 0, cnt: 0, impact: 0 };
				byGu[r.gu].sum += r.score;
				byGu[r.gu].cnt += 1;
				byGu[r.gu].impact += r.impact;
			});
		return Object.entries(byGu)
			.map(([gu, v]) => ({ gu, sc: v.sum / v.cnt, im: v.impact }))
			.sort((a, b) => a.sc - b.sc);
	});

	const statSummary = $derived.by(() => {
		const valid = allDongStats.filter((r) => r.nYoung > 0);
		const meanScore = valid.length ? valid.reduce((s, r) => s + r.score, 0) / valid.length : 0;
		const totalImpact = allDongStats.reduce((s, r) => s + r.impact, 0);
		const tr = cSlope ? AVG_TOBLER : 1.0;
		const rYoung = Math.round(1.28 * cT * 60 * tr);
		const rB = Math.round(SPEEDS[cB].speed * cT * 60 * tr);
		const theory = (SPEEDS[cB].speed / 1.28) ** 2 * 100;
		return { meanScore, totalImpact, rYoung, rB, theory };
	});

	const distBars = $derived.by(() => {
		const tr = cSlope ? AVG_TOBLER : 1.0;
		return SPEEDS.map((s, i) => {
			const dist = Math.round(s.speed * cT * 60 * tr);
			const pct = (dist / (1.28 * cT * 60)) * 100;
			const isB = i === cB;
			const isYoung = i === 0;
			return { ...s, dist, pct, isB, isYoung, opacity: isYoung || isB ? 1 : 0.35 };
		});
	});

	const tableRows = $derived(
		allDongStats
			.filter((r) => r.nYoung > 0)
			.sort((a, b) => a.score - b.score)
			.slice(0, 100)
	);

	const topRows = $derived.by(() => {
		const isImpact = cTop === 'impact';
		return isImpact
			? allDongStats
					.filter((r) => r.impact > 0)
					.sort((a, b) => b.impact - a.impact)
					.slice(0, 10)
			: allDongStats
					.filter((r) => r.nYoung > 0)
					.sort((a, b) => a.score - b.score)
					.slice(0, 10);
	});

	const mapTitle = $derived.by(() => {
		const b = SPEEDS[cB];
		const slopeNote = cSlope ? ' · 경사 보정 적용' : ' · 평지 기준';
		return `행정동별 의료 도달가능점수 — ${b.label} (${b.speed} m/s)${slopeNote}`;
	});

	const scTitle = $derived(`일반인 vs ${SPEEDS[cB].label} 접근 가능 시설 수`);

	// ─── Leaflet (POI 시설 지도) ───
	/** @type {HTMLDivElement | undefined} */
	let mapEl2 = $state();
	/** @type {any} */
	let facilityMap = null;
	/** @type {any} */
	let hospGroup = null;
	/** @type {any} */
	let pharmGroup = null;

	/** @type {Record<string, string>} 병의원 분류별 색상 */
	const HOSP_COLOR = {
		'의원': '#f472b6',
		'병원': '#e11d48',
		'보건소': '#7c3aed',
		'종합병원': '#1d4ed8'
	};

	onMount(async () => {
		// POI 지도 초기화
		if (mapEl2) {
			const L = (await import('leaflet')).default;
			await import('leaflet/dist/leaflet.css');

			facilityMap = L.map(mapEl2, { zoomControl: true, attributionControl: false }).setView(
				[37.5665, 126.978],
				11
			);
			L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
				subdomains: 'abcd',
				maxZoom: 18
			}).addTo(facilityMap);

			hospGroup = L.layerGroup();
			pharmGroup = L.layerGroup();

			facilities.HOSP.forEach((h) => {
				const col = HOSP_COLOR[h.sub] || '#f472b6';
				L.circleMarker([h.lat, h.lng], {
					radius: 4,
					fillColor: col,
					color: '#fff',
					weight: 0.8,
					fillOpacity: 0.85
				})
					.bindTooltip(`<b>${h.name}</b><br><span style="color:#888780">${h.sub}</span>`, {
						direction: 'top',
						offset: [0, -4]
					})
					.addTo(hospGroup);
			});

			facilities.PHARM.forEach((p) => {
				L.circleMarker([p.lat, p.lng], {
					radius: 3.5,
					fillColor: '#10b981',
					color: '#fff',
					weight: 0.8,
					fillOpacity: 0.85
				})
					.bindTooltip(`<b>${p.name}</b><br><span style="color:#888780">약국</span>`, {
						direction: 'top',
						offset: [0, -4]
					})
					.addTo(pharmGroup);
			});

			hospGroup.addTo(facilityMap);
			pharmGroup.addTo(facilityMap);
		}

		// 차트 초기화
		await initCharts();
	});

	onDestroy(() => {
		if (facilityMap) {
			try { facilityMap.remove(); } catch (e) {}
		}
		[scChart, gcChart, icChart].forEach((c) => c?.destroy?.());
	});

	// 시설 레이어 토글
	$effect(() => {
		if (!hospGroup || !pharmGroup || !facilityMap) return;
		showHosp ? hospGroup.addTo(facilityMap) : hospGroup.remove();
		showPharm ? pharmGroup.addTo(facilityMap) : pharmGroup.remove();
	});

	/*
	 * ── CHOROPLETH_MAP_ARCHIVED ──────────────────────────────────────
	 * 행정동 도달가능점수 choropleth 지도. 나중에 재활용 가능.
	 *
	 * let mapEl = $state();
	 * let leafletMap = null;
	 * let geoLayer = null;
	 *
	 * function styleFeature(feat) {
	 *   return {
	 *     fillColor: scoreColor(dongScore(feat.properties.dc)),
	 *     color: 'rgba(80,80,80,0.25)', weight: 0.5, fillOpacity: 0.82
	 *   };
	 * }
	 * function tooltipContent(feat) {
	 *   const dc = feat.properties.dc;
	 *   const m = DONG_META[dc];
	 *   if (!m) return '';
	 *   const nYoung = getN('young', cT, cF, dc, cSlope);
	 *   const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
	 *   const score = nYoung > 0 ? (nB / nYoung) * 100 : 100;
	 *   const impact = Math.round((Math.max(0, 100 - score) / 100) * m.el);
	 *   return `<b>${m.fn}</b><br>도달가능점수: <b>${score.toFixed(1)}점</b><br>`
	 *        + `일반인 ${nYoung}개 → ${SPEEDS[cB].label} ${nB}개<br>`
	 *        + `영향 노인 수: 약 ${impact.toLocaleString()}명`;
	 * }
	 * // onMount: leafletMap 초기화 + L.geoJSON(GEOJSON, {...}).addTo(leafletMap)
	 * // $effect: geoLayer.setStyle(styleFeature) + tooltipContent 업데이트
	 * ────────────────────────────────────────────────────────────────
	 */

	// ─── Chart.js ───
	/** @type {HTMLCanvasElement | undefined} */
	let scCanvas = $state();
	/** @type {HTMLCanvasElement | undefined} */
	let gcCanvas = $state();
	/** @type {HTMLCanvasElement | undefined} */
	let icCanvas = $state();

	/** @type {any} */
	let scChart = null;
	/** @type {any} */
	let gcChart = null;
	/** @type {any} */
	let icChart = null;
	/** @type {any} */
	let ChartLib = null;

	async function initCharts() {
		if (!scCanvas || !gcCanvas || !icCanvas) return;
		const mod = await import('chart.js/auto');
		ChartLib = mod.default;

		const sData = allDongStats.filter((r) => r.nYoung > 0);
		const ratio = SPEEDS[cB].speed / 1.28;
		const maxV = Math.max(...sData.map((r) => r.nYoung), 1) + 5;

		scChart = new ChartLib(scCanvas, {
			type: 'scatter',
			data: {
				datasets: [
					{
						label: '행정동',
						data: sData.map((r) => ({ x: r.nYoung, y: r.nB, sc: r.score, fn: r.fn })),
						backgroundColor: sData.map((r) => ptScoreColor(r.score)),
						pointRadius: 4,
						pointHoverRadius: 6
					},
					{
						label: '100점 (y=x)',
						data: [
							{ x: 0, y: 0 },
							{ x: maxV, y: maxV }
						],
						type: 'line',
						borderColor: '#aaa',
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						fill: false
					},
					{
						label: `이론선 (${(ratio * ratio * 100).toFixed(0)}점)`,
						data: [
							{ x: 0, y: 0 },
							{ x: maxV, y: maxV * ratio * ratio }
						],
						type: 'line',
						borderColor: '#ff8c00',
						borderWidth: 1.5,
						borderDash: [6, 3],
						pointRadius: 0,
						fill: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label: (ctx) => {
								const p = /** @type {any} */ (ctx.raw);
								if (p?.fn)
									return [
										p.fn,
										`일반인 ${p.x}개 → 비교 ${p.y}개`,
										`점수: ${p.sc.toFixed(1)}점`
									];
								return ctx.dataset.label || '';
							}
						}
					}
				},
				scales: {
					x: {
						title: { display: true, text: '일반인 도달 시설 수', font: { size: 11 } },
						grid: { color: '#f0f0ee' }
					},
					y: {
						title: { display: true, text: `${SPEEDS[cB].label} 도달 시설 수`, font: { size: 11 } },
						grid: { color: '#f0f0ee' }
					}
				}
			}
		});

		gcChart = new ChartLib(gcCanvas, {
			type: 'bar',
			data: {
				labels: guStats.map((r) => r.gu),
				datasets: [
					{
						data: guStats.map((r) => r.sc),
						backgroundColor: guStats.map((r) => scoreColor(r.sc)),
						borderWidth: 0
					}
				]
			},
			options: {
				indexAxis: 'y',
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: { label: (ctx) => `도달가능점수: ${Number(ctx.raw).toFixed(1)}점` }
					}
				},
				scales: {
					x: {
						min: 0,
						max: 100,
						grid: { color: '#f0f0ee' },
						ticks: { callback: (v) => v + '점' },
						title: { display: true, text: '평균 도달가능점수(점)', font: { size: 11 } }
					},
					y: { ticks: { font: { size: 11 } } }
				}
			}
		});

		buildTopChart();
	}

	function buildTopChart() {
		if (!ChartLib || !icCanvas) return;
		const isImpact = cTop === 'impact';
		const sorted = topRows;
		const labels = sorted.map((r) => r.fn);
		const vals = isImpact ? sorted.map((r) => r.impact) : sorted.map((r) => r.score);
		const colors = isImpact
			? sorted.map((_, i) => `hsl(${10 + i * 4},68%,${42 + i * 3}%)`)
			: sorted.map((r) => scoreColor(r.score));

		if (icChart) icChart.destroy();
		icChart = new ChartLib(icCanvas, {
			type: 'bar',
			data: {
				labels,
				datasets: [{ data: vals, backgroundColor: colors, borderWidth: 0 }]
			},
			options: {
				indexAxis: 'y',
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label: (ctx) =>
								isImpact
									? `약 ${Number(ctx.raw).toLocaleString()}명`
									: `${Number(ctx.raw).toFixed(1)}점`
						}
					}
				},
				scales: {
					x: {
						grid: { color: '#f0f0ee' },
						min: 0,
						max: isImpact ? undefined : 100,
						title: {
							display: true,
							text: isImpact ? '영향 노인 수(명)' : '도달가능점수(점)',
							font: { size: 11 }
						}
					},
					y: { ticks: { font: { size: 11 } } }
				}
			}
		});
	}

	// 컨트롤 변경 시 차트 갱신
	$effect(() => {
		void cB;
		void cT;
		void cF;
		void cSlope;
		if (!scChart || !gcChart) return;
		const sData = allDongStats.filter((r) => r.nYoung > 0);
		const ratio = SPEEDS[cB].speed / 1.28;
		const maxV = Math.max(...sData.map((r) => r.nYoung), 1) + 5;

		scChart.data.datasets[0].data = sData.map((r) => ({
			x: r.nYoung,
			y: r.nB,
			sc: r.score,
			fn: r.fn
		}));
		scChart.data.datasets[0].backgroundColor = sData.map((r) => ptScoreColor(r.score));
		scChart.data.datasets[1].data = [
			{ x: 0, y: 0 },
			{ x: maxV, y: maxV }
		];
		scChart.data.datasets[2].data = [
			{ x: 0, y: 0 },
			{ x: maxV, y: maxV * ratio * ratio }
		];
		scChart.data.datasets[2].label = `이론선 (${(ratio * ratio * 100).toFixed(0)}점)`;
		scChart.options.scales.y.title.text = `${SPEEDS[cB].label} 도달 시설 수`;
		scChart.update('none');

		gcChart.data.labels = guStats.map((r) => r.gu);
		gcChart.data.datasets[0].data = guStats.map((r) => r.sc);
		gcChart.data.datasets[0].backgroundColor = guStats.map((r) => scoreColor(r.sc));
		gcChart.update('none');
	});

	// cTop 변경 시 top 차트 재구축
	$effect(() => {
		void cTop;
		void cB;
		void cT;
		void cF;
		void cSlope;
		if (ChartLib) buildTopChart();
	});

	// ─── 버튼 라벨/상태 ───
	const compareLabels = [
		{ idx: 1, emoji: '🧓', text: '일반 노인', speed: '1.12 m/s' },
		{ idx: 2, emoji: '🦽', text: '보행보조 노인', speed: '0.88 m/s' },
		{ idx: 3, emoji: '♿', text: '보행보조 노인 하위15%', speed: '0.70 m/s' }
	];

	/** @param {number|null} sc */
	function gradePillClass(sc) {
		if (sc == null) return 'pna';
		if (sc >= 90) return 'phi';
		if (sc >= 60) return 'pmd';
		return 'plo';
	}
	/** @param {number|null} sc */
	function gradeText(sc) {
		if (sc == null) return '-';
		if (sc >= 90) return '양호';
		if (sc >= 60) return '보통';
		return '미흡';
	}
	/** @param {number|null} sc */
	function scoreBarStyle(sc) {
		if (sc == null) return 'display:none';
		const col = sc >= 70 ? '#2E7D32' : sc >= 50 ? '#F57F17' : '#C62828';
		const w = Math.round((sc * 40) / 100);
		return `background:${col};width:${w}px`;
	}

	const mapLegend = [
		{ color: '#1a9850', label: '90점+' },
		{ color: '#91cf60', label: '80–90점' },
		{ color: '#d9ef8b', label: '70–80점' },
		{ color: '#fee08b', label: '60–70점' },
		{ color: '#fdae61', label: '50–60점' },
		{ color: '#d73027', label: '40–50점' },
		{ color: '#a50026', label: '40점 미만' }
	];

	const facilityLegend = [
		{ color: '#f472b6', label: '의원' },
		{ color: '#e11d48', label: '병원' },
		{ color: '#7c3aed', label: '보건소' },
		{ color: '#1d4ed8', label: '종합병원' },
		{ color: '#10b981', label: '약국' }
	];
</script>

<svelte:head>
	<title>의료 — 노인 보행일상권 의료 접근성 분석</title>
</svelte:head>

<section class="mx-auto max-w-[1340px] px-[18px] pb-[60px] pt-6">
	<!-- 헤더 -->
	<div class="mb-3.5">
		<KickerLabel text={meta.kicker} />
		<h1 class="serif-h text-3xl mt-2" style:color={meta.accent}>{meta.title}</h1>
		<p class="text-[13px] mt-1" style:color="var(--color-text2)">
			병의원·보건소·약국 대상 · 서울 426개 행정동 · OSM 보행 네트워크 + Tobler 경사 보정 (EPSG:5179)
		</p>
	</div>

	<!-- 컨트롤 -->
	<div class="ctrl">
		<div class="crow">
			<span class="lbl">비교 속도</span>
			{#each compareLabels as c (c.idx)}
				<button type="button" class="btn bw" class:on={cB === c.idx} onclick={() => (cB = c.idx)}>
					{c.emoji} {c.text} &nbsp;{c.speed}
				</button>
			{/each}
			<span class="text-[11px] ml-1.5" style:color="var(--color-text4)">기준: 일반인 1.28 m/s 고정</span>
		</div>
		<div class="crow">
			<span class="lbl">경사 보정</span>
			<button type="button" class="chk-btn slope" class:on={cSlope} onclick={() => (cSlope = !cSlope)}>
				<span class="chk-dot" style="background:#8B5CF6"></span>경사로 보정 (Tobler · NASA SRTM)
			</button>
		</div>
		<div class="crow">
			<span class="lbl">시설 레이어</span>
			<button type="button" class="chk-btn" class:on={showHosp} onclick={() => (showHosp = !showHosp)}>
				<span class="chk-dot" style="background:#f472b6"></span>병의원
			</button>
			<button type="button" class="chk-btn" class:on={showPharm} onclick={() => (showPharm = !showPharm)}>
				<span class="chk-dot" style="background:#10b981"></span>약국
			</button>
		</div>
		<div class="crow">
			<span class="lbl">보행 시간</span>
			{#each [15, 30, 45] as t (t)}
				<button type="button" class="btn" class:on={cT === t} onclick={() => (cT = t)}>{t}분</button>
			{/each}
			<span class="lbl" style="margin-left:12px">시설 유형</span>
			{#each [{v:'all',l:'전체'},{v:'hosp',l:'병의원'},{v:'pharm',l:'약국'}] as f (f.v)}
				<button type="button" class="btn" class:on={cF === f.v} onclick={() => (cF = f.v)}>{f.l}</button>
			{/each}
		</div>

		<!-- 통계 4열 -->
		<div class="mt-3">
			<StatGrid>
				<StatCard
					label="일반인(기준) 반경"
					value="{statSummary.rYoung.toLocaleString()} m"
					sub="1.28 m/s · {cT}분{cSlope ? '·경사보정' : ''}"
				/>
				<StatCard
					label="비교 속도 반경"
					value="{statSummary.rB.toLocaleString()} m"
					sub="{SPEEDS[cB].speed} m/s · {cT}분{cSlope ? '·경사보정' : ''}"
				/>
				<StatCard
					label="평균 도달가능점수"
					value="{statSummary.meanScore.toFixed(1)}점"
					sub="이론값 {statSummary.theory.toFixed(1)}점 (속도비 제곱)"
				/>
				<StatCard
					label="영향 노인 수 (추정)"
					value="{(statSummary.totalImpact / 10000).toFixed(1)}만명"
					sub="(100−점수)/100 × 65세 이상 인구"
				/>
			</StatGrid>
		</div>

		<!-- 거리 비교 막대 -->
		<div class="mt-3.5 pt-3" style:border-top="0.5px solid var(--color-border-soft)">
			<div class="lbl mb-2.5">보행 가능 거리 비교 (경사 보정 평균 기준)</div>
			<div class="flex flex-col gap-2">
				{#each distBars as b (b.id)}
					<div class="flex items-center gap-2.5" style:opacity={b.opacity}>
						<div class="flex items-center gap-1.5" style:width="160px" style:flex-shrink="0">
							<span
								class="inline-block flex-shrink-0"
								style:width="9px"
								style:height="9px"
								style:border-radius="50%"
								style:background={b.color}
							></span>
							<span class="text-[11px] flex-1 whitespace-nowrap" style:color="var(--color-text2)">
								{b.label}
							</span>
							{#if b.isYoung}
								<span
									class="text-[10px] font-medium px-1.5 py-px rounded-[10px]"
									style:background="{b.color}20"
									style:color={b.color}
								>기준</span>
							{:else if b.isB}
								<span
									class="text-[10px] font-medium px-1.5 py-px rounded-[10px]"
									style:background="{b.color}20"
									style:color={b.color}
								>비교</span>
							{/if}
						</div>
						<div
							class="flex-1 overflow-hidden relative"
							style:background="#f0ede8"
							style:border-radius="4px"
							style:height="10px"
						>
							<div
								class="h-full transition-[width] duration-300"
								style:width="{b.pct}%"
								style:background={b.color}
								style:border-radius="4px"
							></div>
						</div>
						<span
							class="text-[11px] text-right flex-shrink-0"
							style:color="var(--color-text2)"
							style:width="72px"
						>{b.dist.toLocaleString()} m</span>
					</div>
				{/each}
			</div>
		</div>
	</div>

	<!--
	CHOROPLETH_MAP_ARCHIVED — 행정동 도달가능점수 등급별 choropleth 지도
	(언젠가 다시 쓸 일이 있을 때를 위해 보존)
	<div class="mt-3.5">
		<Card title={mapTitle}>
			<MapShell
				height="420px"
				legend={mapLegend}
				source="출처: 서울 열린데이터광장 병의원·약국 위치정보. 도달가능점수 = (비교속도 도달 시설 수 / 일반인 도달 시설 수) × 100"
			>
				<div bind:this={mapEl} class="absolute inset-0 h-full w-full"></div>
			</MapShell>
		</Card>
	</div>
	-->

	<!-- POI 지도: 병의원·약국 위치 -->
	<div class="mt-3.5">
		<Card title="병의원·약국 위치 (서울시 — 출처: 서울 열린데이터광장)">
			<MapShell
				height="460px"
				legend={facilityLegend}
				source="병의원 {facilities.HOSP.length.toLocaleString()}개 · 약국 {facilities.PHARM.length.toLocaleString()}개 · 의원/병원/보건소/종합병원 + 영업 중 약국"
			>
				<div bind:this={mapEl2} class="absolute inset-0 h-full w-full"></div>
			</MapShell>
		</Card>
	</div>

	<!-- 산점도 + 구별 차트 -->
	<div class="r2b mt-3.5">
		<Card title={scTitle}>
			<div class="relative w-full" style:height="400px">
				<canvas bind:this={scCanvas} class="block h-full w-full"></canvas>
			</div>
			<div class="mt-2 flex flex-wrap gap-2.5 text-[11px]" style:color="var(--color-text2)">
				<span class="flex items-center gap-1">
					<span class="inline-block w-2.5 h-2.5 rounded-sm" style:background="#1a9850"></span>90점+
				</span>
				<span class="flex items-center gap-1">
					<span class="inline-block w-2.5 h-2.5 rounded-sm" style:background="#91cf60"></span>80–90점
				</span>
				<span class="flex items-center gap-1">
					<span class="inline-block w-2.5 h-2.5 rounded-sm" style:background="#d9ef8b"></span>70–80점
				</span>
				<span class="flex items-center gap-1">
					<span class="inline-block w-2.5 h-2.5 rounded-sm" style:background="#fee08b"></span>60–70점
				</span>
				<span class="flex items-center gap-1">
					<span class="inline-block w-2.5 h-2.5 rounded-sm" style:background="#fdae61"></span>50–60점
				</span>
				<span class="flex items-center gap-1">
					<span class="inline-block w-2.5 h-2.5 rounded-sm" style:background="#d73027"></span>50점 미만
				</span>
				<span class="text-[10px]" style:color="var(--color-text3)">주황점선=이론선</span>
			</div>
		</Card>

		<Card title="구별 평균 의료 도달가능점수">
			<div class="relative w-full" style:height="400px">
				<canvas bind:this={gcCanvas} class="block h-full w-full"></canvas>
			</div>
		</Card>
	</div>

	<!-- Top 차트 -->
	<div class="mt-3.5">
		<Card>
			<div class="flex flex-wrap gap-1 mb-2.5">
				<button type="button" class="btn bw" class:on={cTop === 'impact'} onclick={() => (cTop = 'impact')}>
					영향 노인 수 TOP 10동
				</button>
				<button type="button" class="btn bw" class:on={cTop === 'score'} onclick={() => (cTop = 'score')}>
					도달가능점수 최하위 10동
				</button>
			</div>
			<div class="relative w-full" style:height="360px">
				<canvas bind:this={icCanvas} class="block h-full w-full"></canvas>
			</div>
		</Card>
	</div>

	<!-- 테이블 -->
	<Card title="행정동별 의료 접근성 상세 (도달가능점수 낮은 순)" class="mt-3.5">
		<div class="tbl-wrap">
			<table class="ktbl">
				<thead>
					<tr>
						<th>행정동</th>
						<th>도달가능점수</th>
						<th>일반인</th>
						<th>비교 속도</th>
						<th>영향 노인 수</th>
						<th>등급</th>
					</tr>
				</thead>
				<tbody>
					{#each tableRows as r (r.dc)}
						<tr>
							<td>{r.fn}</td>
							<td>
								<b style="color:{scoreColor(r.score)}">{r.score.toFixed(1)}점</b>
								<span class="score-bar" style={scoreBarStyle(r.score)}></span>
							</td>
							<td>{r.nYoung}</td>
							<td>{r.nB}</td>
							<td>{r.el > 0 ? r.impact.toLocaleString() + '명' : '-'}</td>
							<td><span class="pill {gradePillClass(r.score)}">{gradeText(r.score)}</span></td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="text-[11px] mt-2" style:color="var(--color-text3)" style:line-height="1.7">
			도달가능점수(점) = (비교속도 도달 시설 수 / 일반인 도달 시설 수) × 100
		</p>
	</Card>

	<!-- 노트 -->
	<Note tone="cool" class="mt-3">
		※ <b>일반인 (1.28 m/s)</b>를 기준으로 <b>{SPEEDS[cB].label} ({SPEEDS[cB].speed} m/s)</b>의
		도달가능점수를 표시합니다.<br />
		※ 도달가능점수 = (비교속도 도달 시설 수 / 일반인 도달 시설 수) × 100 — 이론값
		<b>{statSummary.theory.toFixed(1)}점</b><br />
		※ 경사 보정: {cSlope
			? 'Tobler hiking function 기반 동별 속도 보정 (tobler_ratio_LEE.csv)'
			: '평지 기준 (보정 없음)'}<br />
		※ 거리 측정: 동 centroid 기준 OSM 보행 네트워크(다익스트라)
	</Note>
</section>

<style>
	.serif-h {
		font-family: var(--font-serif);
		font-weight: 500;
	}

	/* 컨트롤 패널 */
	.ctrl {
		background: var(--color-card);
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 16px 20px;
		margin-bottom: 14px;
	}
	.crow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
	.crow:last-child { margin-bottom: 0; }
	.lbl {
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.06em;
		color: var(--color-text3);
		white-space: nowrap;
		margin-right: 2px;
	}

	/* 버튼 */
	.btn {
		font-size: 12px; padding: 5px 14px; border-radius: 20px;
		border: 0.5px solid var(--color-text4); background: transparent;
		color: var(--color-text2); cursor: pointer; transition: all 0.14s;
		font-family: inherit; white-space: nowrap;
	}
	.btn:hover { border-color: var(--color-text2); color: var(--color-text); }
	.btn.on {
		background: var(--pill-accent, var(--color-dark));
		color: var(--pill-on-text, var(--color-dark-text));
		border-color: var(--pill-accent, var(--color-dark));
	}
	.btn.on:hover { filter: brightness(1.08); }
	.btn.bw { border-radius: 8px; }

	.chk-btn {
		font-size: 12px; padding: 5px 13px; border-radius: 20px;
		border: 0.5px solid var(--color-text4); background: transparent;
		color: var(--color-text2); cursor: pointer; transition: all 0.14s;
		font-family: inherit; white-space: nowrap; display: flex; align-items: center; gap: 5px;
	}
	.chk-btn:hover { border-color: var(--color-text2); color: var(--color-text); }
	.chk-btn.slope.on { background: #f0eafd; border-color: #8b5cf6; color: #5b21b6; }
	.chk-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

	/* 레이아웃 */
	.r2b { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
	@media (max-width: 900px) { .r2b { grid-template-columns: 1fr; } }

	/* 테이블 */
	.tbl-wrap { overflow-x: auto; }
	.ktbl { width: 100%; border-collapse: collapse; font-size: 12px; table-layout: fixed; }
	.ktbl th {
		background: var(--color-card-soft); padding: 8px 10px; text-align: right;
		font-weight: 500; color: var(--color-text2); border-bottom: 1px solid var(--color-border);
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
	.ktbl th:first-child { text-align: left; width: 88px; }
	.ktbl th:last-child { text-align: center; }
	.ktbl td {
		padding: 7px 10px; border-bottom: 0.5px solid var(--color-border-soft);
		color: var(--color-text); text-align: right; white-space: nowrap; overflow: hidden;
	}
	.ktbl td:first-child { text-align: left; }
	.ktbl td:last-child { text-align: center; }
	.ktbl tr:hover td { background: #fafaf8; }
	.score-bar { display: inline-block; height: 5px; border-radius: 3px; vertical-align: middle; margin-left: 4px; }

	/* 등급 필 */
	.pill { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
	.phi { background: #d4edda; color: #155724; }
	.pmd { background: #fff3cd; color: #856404; }
	.plo { background: #f8d7da; color: #721c24; }
	.pna { background: #ebebeb; color: #666; }

	:global(.leaflet-container) {
		background: #e8e4db !important;
	}
</style>
