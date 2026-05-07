<script>
	import { onMount, onDestroy } from 'svelte';
	import medical from '$lib/data/medical.json';
	import Card from '$lib/components/Card.svelte';
	import MapShell from '$lib/components/MapShell.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import PillButton from '$lib/components/PillButton.svelte';
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

	// ─── Leaflet ───
	/** @type {HTMLDivElement | undefined} */
	let mapEl = $state();
	/** @type {any} */
	let leafletMap = null;
	/** @type {any} */
	let geoLayer = null;

	/** @param {any} feat */
	function styleFeature(feat) {
		return {
			fillColor: scoreColor(dongScore(feat.properties.dc)),
			color: 'rgba(80,80,80,0.25)',
			weight: 0.5,
			fillOpacity: 0.82
		};
	}

	/** @param {any} feat */
	function tooltipContent(feat) {
		const dc = feat.properties.dc;
		const m = DONG_META[dc];
		if (!m) return '';
		const nYoung = getN('young', cT, cF, dc, cSlope);
		const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
		const score = nYoung > 0 ? (nB / nYoung) * 100 : 100;
		const impact = Math.round((Math.max(0, 100 - score) / 100) * m.el);
		return (
			`<b>${m.fn}</b><br>` +
			`도달가능점수: <b>${score.toFixed(1)}점</b><br>` +
			`일반인 ${nYoung}개 → ${SPEEDS[cB].label} ${nB}개<br>` +
			`영향 노인 수: 약 ${impact.toLocaleString()}명`
		);
	}

	onMount(async () => {
		if (!mapEl) return;
		const L = (await import('leaflet')).default;
		await import('leaflet/dist/leaflet.css');

		leafletMap = L.map(mapEl, { zoomControl: true, attributionControl: false }).setView(
			[37.5665, 126.978],
			11
		);
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			subdomains: 'abcd',
			maxZoom: 18
		}).addTo(leafletMap);

		geoLayer = L.geoJSON(GEOJSON, {
			style: styleFeature,
			onEachFeature: (feat, layer) => {
				layer.bindTooltip(tooltipContent(feat), { sticky: true });
				layer.on('mouseover', function () {
					// @ts-ignore Leaflet 컨텍스트
					this.setStyle({ weight: 2, color: '#FFD700', fillOpacity: 0.95 });
				});
				layer.on('mouseout', function () {
					// @ts-ignore Leaflet 컨텍스트
					geoLayer?.resetStyle(this);
				});
			}
		}).addTo(leafletMap);

		// 첫 렌더 직후 차트도 초기화
		await initCharts();
	});

	onDestroy(() => {
		if (leafletMap) {
			try {
				leafletMap.remove();
			} catch (e) {
				// noop
			}
		}
		[scChart, gcChart, icChart].forEach((c) => c?.destroy?.());
	});

	// 컨트롤 변경 시 지도 재스타일 + 툴팁 업데이트
	$effect(() => {
		// 의존: cB cT cF cSlope
		void cB;
		void cT;
		void cF;
		void cSlope;
		if (!geoLayer) return;
		geoLayer.setStyle(styleFeature);
		geoLayer.eachLayer((l) => l.setTooltipContent(tooltipContent(l.feature)));
	});

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

	const mapLegend = [
		{ color: '#1a9850', label: '90점+' },
		{ color: '#91cf60', label: '80–90점' },
		{ color: '#d9ef8b', label: '70–80점' },
		{ color: '#fee08b', label: '60–70점' },
		{ color: '#fdae61', label: '50–60점' },
		{ color: '#d73027', label: '40–50점' },
		{ color: '#a50026', label: '40점 미만' }
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
	<Card class="mb-3.5">
		<div class="flex flex-wrap items-center gap-2 mb-2.5">
			<span class="ct-label" style:width="72px">비교 속도</span>
			{#each compareLabels as c (c.idx)}
				<PillButton
					variant="wide"
					active={cB === c.idx}
					onclick={() => (cB = c.idx)}
					class={cB === c.idx ? 'speed-on' : ''}
				>
					{c.emoji} {c.text} &nbsp;{c.speed}
				</PillButton>
			{/each}
			<span class="text-[11px] ml-1.5" style:color="var(--color-text4)">
				기준: 일반인 1.28 m/s 고정
			</span>
		</div>

		<div class="flex flex-wrap items-center gap-2 mb-2.5">
			<span class="ct-label" style:width="72px">경사 보정</span>
			<PillButton variant="wide" active={!cSlope} onclick={() => (cSlope = false)}>
				경사 없음 (평지)
			</PillButton>
			<PillButton variant="wide" active={cSlope} onclick={() => (cSlope = true)}>
				경사 보정 (Tobler · NASA SRTM)
			</PillButton>
		</div>

		<div class="my-2 h-px" style:background="var(--color-border-soft)"></div>

		<div class="flex flex-wrap items-center gap-2">
			<span class="ct-label">보행 시간</span>
			{#each [15, 30, 45] as t (t)}
				<PillButton active={cT === t} onclick={() => (cT = t)}>{t}분</PillButton>
			{/each}
			<span class="flex-1"></span>
			<span class="ct-label">시설 유형</span>
			<PillButton variant="wide" active={cF === 'all'} onclick={() => (cF = 'all')}>전체</PillButton>
			<PillButton variant="wide" active={cF === 'hosp'} onclick={() => (cF = 'hosp')}>
				병의원
			</PillButton>
			<PillButton variant="wide" active={cF === 'pharm'} onclick={() => (cF = 'pharm')}>
				약국
			</PillButton>
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
			<div class="ct-label mb-2.5">보행 가능 거리 비교 (경사 보정 평균 기준)</div>
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
								>
									기준
								</span>
							{:else if b.isB}
								<span
									class="text-[10px] font-medium px-1.5 py-px rounded-[10px]"
									style:background="{b.color}20"
									style:color={b.color}
								>
									비교
								</span>
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
						>
							{b.dist.toLocaleString()} m
						</span>
					</div>
				{/each}
			</div>
		</div>
	</Card>

	<!-- 지도 + 산점도 -->
	<div class="grid gap-3.5 mb-3.5" style:grid-template-columns="1.45fr 1fr">
		<Card title={mapTitle}>
			<MapShell
				height="420px"
				legend={mapLegend}
				source="출처: 서울 열린데이터광장 병의원·약국 위치정보. 도달가능점수 = (비교속도 도달 시설 수 / 일반인 도달 시설 수) × 100"
			>
				<div bind:this={mapEl} class="absolute inset-0 h-full w-full"></div>
			</MapShell>
		</Card>

		<Card title={scTitle}>
			<div class="relative w-full" style:height="360px">
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
	</div>

	<!-- 자치구별 + Top 차트 -->
	<div class="grid gap-3.5 mb-3.5" style:grid-template-columns="1fr 1fr">
		<Card title="구별 평균 의료 도달가능점수">
			<div class="relative w-full" style:height="560px">
				<canvas bind:this={gcCanvas} class="block h-full w-full"></canvas>
			</div>
		</Card>

		<Card>
			<div class="flex flex-wrap gap-1 mb-2.5">
				<button
					type="button"
					class="topbtn"
					class:on={cTop === 'impact'}
					onclick={() => (cTop = 'impact')}
				>
					영향 노인 수 TOP 10동
				</button>
				<button
					type="button"
					class="topbtn"
					class:on={cTop === 'score'}
					onclick={() => (cTop = 'score')}
				>
					도달가능점수 최하위 10동
				</button>
			</div>
			<div class="relative w-full" style:height="520px">
				<canvas bind:this={icCanvas} class="block h-full w-full"></canvas>
			</div>
		</Card>
	</div>

	<!-- 테이블 -->
	<Card title="행정동별 의료 접근성 상세 (도달가능점수 낮은 순)">
		<div class="overflow-x-auto overflow-y-auto" style:max-height="360px">
			<table class="w-full border-collapse text-[12px]">
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
							<td><b>{r.score.toFixed(1)}점</b></td>
							<td>{r.nYoung}</td>
							<td>{r.nB}</td>
							<td>{r.el > 0 ? r.impact.toLocaleString() + '명' : '-'}</td>
							<td>
								{#if r.score < 40}
									<span class="pill plo">취약</span>
								{:else if r.score < 60}
									<span class="pill pmd">주의</span>
								{:else if r.score >= 90}
									<span class="pill phi">양호</span>
								{:else}
									<span class="pill phi">보통</span>
								{/if}
							</td>
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
	th {
		padding: 6px 10px;
		text-align: left;
		font-weight: 500;
		color: var(--color-text3);
		border-bottom: 0.5px solid var(--color-border);
		white-space: nowrap;
		position: sticky;
		top: 0;
		background: #fff;
		z-index: 1;
	}
	td {
		padding: 7px 10px;
		border-bottom: 0.5px solid #f1efe8;
	}
	tbody tr:hover td {
		background: #fafaf8;
	}
	.pill {
		display: inline-block;
		font-size: 10px;
		font-weight: 500;
		padding: 2px 8px;
		border-radius: 10px;
	}
	.phi {
		background: #e1f5ee;
		color: #0f6e56;
	}
	.pmd {
		background: #faeeda;
		color: #854f0b;
	}
	.plo {
		background: #fcebeb;
		color: #a32d2d;
	}
	.topbtn {
		font-size: 12px;
		padding: 4px 12px;
		border-radius: 6px;
		border: 0.5px solid transparent;
		background: transparent;
		color: var(--color-text3);
		cursor: pointer;
		font-family: inherit;
	}
	.topbtn:hover {
		background: var(--color-card-soft);
	}
	.topbtn.on {
		background: #f1efe8;
		color: var(--color-text);
		font-weight: 500;
		border-color: var(--color-border);
	}
	:global(.leaflet-container) {
		background: #e8e4db !important;
	}
</style>
