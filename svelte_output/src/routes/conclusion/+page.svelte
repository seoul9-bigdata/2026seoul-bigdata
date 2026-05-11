<script>
	import { base } from '$app/paths';
	import Card from '$lib/components/Card.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import Note from '$lib/components/Note.svelte';
	import CountUp from '$lib/components/CountUp.svelte';
	import { viewport } from '$lib/actions/viewport.js';
	import conclusionData from '$lib/data/conclusion.json';
	import {
		DOMAINS_4,
		scoreColor,
		scoreBg,
		applyChartTheme,
		CHART_THEME,
		COMPARE_COLORS
	} from '$lib/theme.js';
	import { onMount, onDestroy, untrack } from 'svelte';
	import { fade } from 'svelte/transition';

	/* ────────────────────────────────────────────────────────────
	 *  실데이터: final_output/ENSEMBLE/conclusion-csv/ 4 CSV → conclusion.json
	 *  컬럼: 노인_경사X / 노인_경사O / 보조_경사X / 보조_경사O / 하위15_경사X / 하위15_경사O
	 *  본 페이지는 "일반 노인(1.12 m/s) · 경사 미보정" 기준 = 노인_경사X
	 *  YOO 교통 도메인은 결론 CSV 미작성 → 4 도메인 결합
	 * ──────────────────────────────────────────────────────────── */

	/** 결론 4개 도메인 — theme.js 단일 진실 원천에서 import (네비/카드 동일 색) */
	const DOMAINS = DOMAINS_4;
	const DOMAIN_KEYS = DOMAINS.map((d) => d.key);

	/** 보행자 유형 (CSV 컬럼 prefix) — '일반인'은 CSV 없음 (기준선=100) */
	const SPEEDS = [
		{ key: '노인',     label: '건강 노인',     mps: 1.12, emoji: '🧓' },
		{ key: '보조',     label: '보행보조 노인', mps: 0.88, emoji: '🦯' },
		{ key: '하위15',   label: '보조 하위15%',  mps: 0.7,  emoji: '🦽' }
	];
	let speedIdx = $state(0); // 0:노인, 1:보조, 2:하위15
	let slopeOn = $state(false);
	const scoreKey = $derived(`${SPEEDS[speedIdx].key}_경사${slopeOn ? 'O' : 'X'}`);

	/** CSV에서 (도메인, 구) → 점수 lookup */
	function scoreOf(domainKey, gu, key) {
		const row = conclusionData.domains[domainKey].find((r) => r.gu === gu);
		return row ? row[key] : 0;
	}

	/** SCORES = 25구 × 4도메인 — scoreKey 변경 시 reactive */
	const SCORES = $derived(
		Object.fromEntries(
			conclusionData.gus.map((gu) => [gu, DOMAIN_KEYS.map((k) => scoreOf(k, gu, scoreKey))])
		)
	);

	/** 종합 점수 = 4개 도메인 평균 */
	const ranked = $derived(
		Object.entries(SCORES)
			.map(([name, arr]) => {
				const avg = arr.reduce((s, v) => s + v, 0) / arr.length;
				return {
					name,
					climate: arr[0],
					infra: arr[1],
					bokji: arr[2],
					medical: arr[3],
					composite: +avg.toFixed(1),
					min: Math.min(...arr),
					max: Math.max(...arr),
					weakest: DOMAINS[arr.indexOf(Math.min(...arr))]
				};
			})
			.sort((a, b) => b.composite - a.composite)
			.map((d, i) => ({ ...d, rank: i + 1 }))
	);

	const seoulAvg = $derived(+(ranked.reduce((s, d) => s + d.composite, 0) / ranked.length).toFixed(1));
	const best = $derived(ranked[0]);
	const worst = $derived(ranked[ranked.length - 1]);

	/** 도메인별 서울 평균 */
	const domainAvg = $derived(
		DOMAINS.map((d) => {
			const v = ranked.reduce((s, r) => s + r[d.key], 0) / ranked.length;
			return { ...d, avg: +v.toFixed(1) };
		})
	);

	/** 보행속도 유형별 평균 점수 (4 도메인 평균) — CSV 실데이터 기반 */
	function avgAcrossDomainsAndGus(scoreKey) {
		let sum = 0, n = 0;
		for (const k of DOMAIN_KEYS) {
			for (const r of conclusionData.domains[k]) {
				sum += r[scoreKey]; n++;
			}
		}
		return +(sum / n).toFixed(1);
	}
	const seniorAvg = avgAcrossDomainsAndGus('노인_경사X');
	const aidedAvg = avgAcrossDomainsAndGus('보조_경사X');
	const bottom15Avg = avgAcrossDomainsAndGus('하위15_경사X');
	function pctVsBaseline(score, base = 100) {
		return Math.round((score / base - 1) * 100);
	}

	/* scoreColor / scoreBg 는 $lib/theme.js 에서 import (5단계 색조 표준) */

	/** 정책 제안 — 도메인별 최저 구 자동 추출 */
	const policySuggestions = DOMAINS.map((d, idx) => {
		const key = ['climate', 'infra', 'bokji', 'medical'][idx];
		const sorted = [...ranked].sort((a, b) => a[key] - b[key]);
		const bottom3 = sorted.slice(0, 3);
		return { ...d, key, bottom3 };
	});

	/* ── 보행속도별 손실 비교 — 4 도메인 CSV 실데이터 평균 ── */
	const speedComparison = [
		{ label: '일반인',           score: 100,        color: '#4a9eff', emoji: '🚶', desc: '기준선' },
		{ label: '건강 노인',        score: seniorAvg,  color: '#3ecfa0', emoji: '🧓', desc: pctVsBaseline(seniorAvg) + '%' },
		{ label: '보행보조 노인',    score: aidedAvg,   color: '#f5b740', emoji: '🦯', desc: pctVsBaseline(aidedAvg) + '%' },
		{ label: '보행보조 하위 15%', score: bottom15Avg, color: '#ef5555', emoji: '🦽', desc: pctVsBaseline(bottom15Avg) + '%' }
	];

	/** 정렬 모드 */
	let sortKey = $state('composite');
	const sortedTable = $derived(
		[...ranked].sort((a, b) => {
			if (sortKey === 'name') return a.name.localeCompare(b.name);
			return b[sortKey] - a[sortKey];
		})
	);

	/* ── Leaflet choropleth (종합 점수) + 클릭 시 detail card ── */
	let mapEl = $state();
	/** @type {any} */
	let lmap;
	/** @type {any} */
	let geoData = null;
	/** @type {any} */
	let geoLayer = null;
	/** @type {any} */
	let L = null;
	let selectedGuName = $state(/** @type {string|null} */ (null));

	const rankedByName = $derived(Object.fromEntries(ranked.map((r) => [r.name, r])));
	/** 클릭한 구의 최신 데이터 — scoreKey 변경 시 자동 재계산 */
	const selectedGu = $derived(selectedGuName ? rankedByName[selectedGuName] : null);

	// scoreKey 변경 시 지도 색만 다시 그림 (selectedGu 는 derived 라 자동 갱신)
	$effect(() => {
		scoreKey;
		untrack(() => {
			if (lmap && geoData) drawGeoLayer();
		});
	});

	function getGuName(props) {
		return props.SIG_KOR_NM || props.name || props.NAME || props.sig_kor_nm || '';
	}

	function drawGeoLayer() {
		if (!lmap || !L || !geoData) return;
		if (geoLayer) lmap.removeLayer(geoLayer);
		geoLayer = L.geoJSON(geoData, {
			style: (feat) => {
				const nm = getGuName(feat.properties);
				const r = rankedByName[nm];
				const c = r ? scoreColor(r.composite) : '#ccc';
				return { fillColor: c, weight: 1.2, color: '#fff', fillOpacity: 0.78 };
			},
			onEachFeature: (feat, layer) => {
				const nm = getGuName(feat.properties);
				const r = rankedByName[nm];
				if (!r) return;
				layer.bindTooltip(
					`<b>${nm}</b><br>종합 ${r.composite}점 · ${r.rank}위<br>` +
						DOMAINS.map((d) => `${d.emoji} ${d.label} ${r[d.key].toFixed(1)}`).join('<br>'),
					{ sticky: true }
				);
				layer.on({
					mouseover: (e) => e.target.setStyle({ fillOpacity: 0.95, weight: 2 }),
					mouseout: (e) => {
						if (selectedGuName !== nm) {
							e.target.setStyle({ fillOpacity: 0.78, weight: 1.2 });
						}
					},
					click: () => {
						selectedGuName = nm;
					}
				});
			}
		}).addTo(lmap);
	}

	/** @type {any} */
	let radarChartEl = $state();
	/** @type {any} */
	let radarChart = null;
	/** @type {any} */
	let Chart = null;

	function drawRadar() {
		if (!Chart || !radarChartEl || !selectedGu) return;
		const seoulAvg = DOMAINS.map((d) => +(domainAvg.find((x) => x.key === d.key)?.avg ?? 0));
		const data = DOMAINS.map((d) => +selectedGu[d.key].toFixed(1));
		if (radarChart) radarChart.destroy();
		radarChart = new Chart(radarChartEl, {
			type: 'radar',
			data: {
				labels: DOMAINS.map((d) => d.label),
				datasets: [
					{
						label: selectedGu.name,
						data,
						backgroundColor: COMPARE_COLORS.primary.fill,
						borderColor: COMPARE_COLORS.primary.stroke,
						pointBackgroundColor: COMPARE_COLORS.primary.point,
						pointBorderColor: '#fff',
						pointHoverRadius: 6,
						pointRadius: 4,
						borderWidth: 2
					},
					{
						label: '서울 평균',
						data: seoulAvg,
						backgroundColor: COMPARE_COLORS.reference.fill,
						borderColor: COMPARE_COLORS.reference.stroke,
						pointBackgroundColor: COMPARE_COLORS.reference.point,
						pointBorderColor: '#fff',
						pointHoverRadius: 5,
						pointRadius: 3,
						borderWidth: 1.6,
						borderDash: [5, 3]
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				scales: {
					r: {
						min: 0,
						max: 100,
						ticks: { stepSize: 25, font: { size: 9 }, color: CHART_THEME.textColorMuted },
						pointLabels: { font: { size: 11, weight: '500' }, color: CHART_THEME.textColor },
						grid: { color: CHART_THEME.gridColor },
						angleLines: { color: CHART_THEME.gridColor }
					}
				},
				plugins: {
					legend: { labels: { font: { size: 11 }, boxWidth: 12, usePointStyle: true } },
					tooltip: {
						backgroundColor: CHART_THEME.tooltipBg,
						titleColor: CHART_THEME.textColor,
						bodyColor: CHART_THEME.textColor,
						borderColor: CHART_THEME.tooltipBorder,
						borderWidth: 1,
						padding: 8,
						titleFont: { size: 12, weight: '500' },
						bodyFont: { size: 11 }
					}
				}
			}
		});
	}

	let mapInited = false;
	async function initMap() {
		if (mapInited || !mapEl) return;
		mapInited = true;
		await import('leaflet/dist/leaflet.css');
		L = (await import('leaflet')).default;
		Chart = await applyChartTheme();
		lmap = L.map(mapEl, {
			zoomControl: true,
			attributionControl: false,
			scrollWheelZoom: false
		}).setView([37.555, 127.0], 11);
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
			subdomains: 'abcd',
			maxZoom: 18
		}).addTo(lmap);
		try {
			const res = await fetch(
				'https://raw.githubusercontent.com/southkorea/seoul-maps/master/kostat/2013/json/seoul_municipalities_geo_simple.json'
			);
			geoData = await res.json();
			drawGeoLayer();
		} catch (e) {
			console.error('[conclusion] GeoJSON load failed', e);
		}
	}

	$effect(() => {
		// mapEl 바인딩되면 초기화
		if (mapEl && !mapInited && typeof window !== 'undefined') {
			initMap();
		}
	});

	onDestroy(() => {
		radarChart?.destroy();
		lmap?.remove();
	});

	$effect(() => {
		// selectedGu 변경 시 radar 재그리기 (untrack 로 cycle 방지)
		const sel = selectedGu;
		untrack(() => {
			if (Chart && radarChartEl && sel) drawRadar();
		});
	});
</script>

<section class="mx-auto max-w-[1340px] px-[18px] pb-[60px] pt-8">
	<!-- ── HERO ── -->
	<div class="card-shell relative mb-3.5 overflow-hidden px-7 py-10">
		<div
			class="pointer-events-none absolute -right-32 -top-32 h-[420px] w-[420px] rounded-full"
			style:background="radial-gradient(circle, rgba(216,90,48,0.10), transparent 65%)"
		></div>

		<div class="mb-4 flex flex-wrap items-center gap-2">
			<p class="kicker" style:color="var(--color-accent)">결론 · 종합 진단 대시보드</p>
			{#each DOMAINS as d}
				<span
					class="rounded-full px-2 py-[2px] font-mono text-[10px] uppercase tracking-[0.06em]"
					style:background="{d.color}1A"
					style:color={d.color}
					style:border="0.5px solid {d.color}33"
				>{d.emoji} {d.label}</span>
			{/each}
		</div>

		<h1
			class="mb-4 text-[34px] leading-[1.2] sm:text-[44px]"
			style:color="var(--color-text)"
			style:font-family="var(--font-display)"
		>
			서울 25개 구,<br />
			<span style:color="var(--color-accent)">노인 도보 생활권</span> 종합 성적표
		</h1>

		<p class="mb-7 max-w-[640px] text-[13.5px] leading-[1.85]" style:color="var(--color-text2)">
			기후·인프라·복지/녹지·의료 4개 도메인 도달가능 점수를 결합한 25개 자치구 종합 진단.<br />
			건강 노인(1.12&nbsp;m/s) 기준, 경사 미보정 점수.
		</p>

		<StatGrid class="sm:grid-cols-4" cols={4}>
			<StatCard label="분석 도메인" sub="기후·인프라·복지/녹지·의료">
				{#snippet children()}
					<CountUp value={4} suffix="개" />
				{/snippet}
			</StatCard>
			<StatCard label="서울 평균 종합 점수" sub="점 (0~100)" tone="orange">
				{#snippet children()}
					<CountUp value={seoulAvg} decimals={1} />
				{/snippet}
			</StatCard>
			<StatCard label="최고 구" value={best.name} sub="{best.composite}점" tone="green" />
			<StatCard label="최저 구" value={worst.name} sub="{worst.composite}점" tone="red" />
		</StatGrid>
	</div>

	<!-- ── 보행 속도별 손실 비교 ── -->
	<Card title="속도별 손실 · 일반인 대비 평균 도달가능 점수" class="mb-3.5">
		<p class="mb-4 text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
			보행속도가 떨어질수록 시설 도달 노드가 급감합니다. 본 페이지의 표·랭킹은 <strong>건강 노인 1.12&nbsp;m/s</strong>를 기준으로 합니다.
		</p>
		<div class="space-y-2.5">
			{#each speedComparison as s, i}
				<div class="grid grid-cols-[140px_1fr_60px] items-center gap-3">
					<div class="flex items-center gap-1.5">
						<span class="text-[14px]">{s.emoji}</span>
						<span class="text-[12.5px] font-medium" style:color="var(--color-text)">{s.label}</span>
					</div>
					<div class="relative h-[18px] rounded-[4px]" style:background="var(--color-card-soft)">
						<div
							class="bar-fill h-full rounded-[4px]"
							style:width="{s.score}%"
							style:background={s.color}
							style:opacity="0.85"
							style:--ad="{i * 110}ms"
						></div>
						<span
							class="absolute right-2 top-1/2 -translate-y-1/2 font-mono text-[10.5px]"
							style:color="var(--color-text3)"
						>
							{s.desc}
						</span>
					</div>
					<div class="text-right font-mono text-[13px] font-medium tabular-nums" style:color={s.color}>
						<CountUp value={+s.score} decimals={Number.isInteger(s.score) ? 0 : 1} />점
					</div>
				</div>
			{/each}
		</div>
	</Card>

	<!-- ── 도메인 평균 — 보행자/경사 토글 변경 시 재애니메이션 ── -->
	<Card title="도메인별 서울 전체 평균 · {SPEEDS[speedIdx].label}{slopeOn ? ' · 경사 보정' : ''}" class="mb-3.5">
		{#key scoreKey}
			<div class="grid gap-2.5 sm:grid-cols-2 md:grid-cols-4" in:fade={{ duration: 220 }}>
				{#each domainAvg as d, i}
					<div
						class="rounded-[8px] p-4 transition-shadow hover:shadow-[0_4px_14px_rgba(0,0,0,0.05)]"
						style:background={d.light}
						style:border="0.5px solid {d.color}55"
					>
						<div class="mb-1 text-[20px]">{d.emoji}</div>
						<div class="text-[11px]" style:color="var(--color-text3)">{d.label} 도메인 평균</div>
						<div
							class="mt-1 font-mono text-[26px] font-medium leading-none tabular-nums"
							style:color={d.color}
						>
							<CountUp value={d.avg} decimals={1} />
						</div>
						<div class="mt-0.5 text-[10.5px]" style:color="var(--color-text3)">점 (0~100)</div>
					</div>
				{/each}
			</div>
		{/key}
	</Card>

	<!-- ── 보행자 / 경사 토글 (모든 점수·지도·표 동시 갱신) ── -->
	<Card title="분석 조건 · 보행자 유형 + 경사도 보정" class="mb-3.5">
		<div class="flex flex-wrap items-center gap-x-4 gap-y-2">
			<div class="flex items-center gap-1.5">
				<span class="kicker mr-1">보행자</span>
				{#each SPEEDS as s, i}
					<button
						type="button"
						class="pill-btn"
						class:pill-btn-on={speedIdx === i}
						style:background={speedIdx === i ? 'var(--pill-accent, var(--color-dark))' : '#fff'}
						style:border-color={speedIdx === i ? 'var(--pill-accent, var(--color-dark))' : ''}
						style:color={speedIdx === i ? 'var(--pill-on-text, var(--color-dark-text))' : ''}
						onclick={() => (speedIdx = i)}
					>
						{s.emoji} {s.label} {s.mps}&nbsp;m/s
					</button>
				{/each}
			</div>
			<label class="toggle-item" title="Tobler 보행함수 기반 구별 경사도 보정">
				<span class="kicker">경사도</span>
				<span class="toggle-switch" class:on={slopeOn}>
					<input type="checkbox" bind:checked={slopeOn} />
					<span class="toggle-slider"></span>
				</span>
				<span class="toggle-label">⛰ 경사 보정 (Tobler)</span>
				{#if slopeOn}
					<span class="slope-tag">반영 중</span>
				{/if}
			</label>
			<div class="ml-auto flex flex-wrap items-baseline gap-x-3 gap-y-1 font-mono text-[11px]">
				{#key scoreKey}
					<span style:color="var(--color-text3)" in:fade={{ duration: 220 }}>
						서울 평균
						<b class="ml-0.5 text-[13px] tabular-nums" style:color="var(--color-text)">
							<CountUp value={seoulAvg} decimals={1} />
						</b>점
					</span>
					<span class="opacity-50">·</span>
					<span style:color="var(--color-text3)" in:fade={{ duration: 220, delay: 60 }}>
						🟢 최고 <b style:color="#3ecfa0">{best?.name}</b>
						<b class="ml-0.5 tabular-nums" style:color="#3ecfa0">
							<CountUp value={best?.composite ?? 0} decimals={1} />
						</b>
					</span>
					<span class="opacity-50">·</span>
					<span style:color="var(--color-text3)" in:fade={{ duration: 220, delay: 120 }}>
						🔴 최저 <b style:color="#C62828">{worst?.name}</b>
						<b class="ml-0.5 tabular-nums" style:color="#C62828">
							<CountUp value={worst?.composite ?? 0} decimals={1} />
						</b>
					</span>
				{/key}
			</div>
		</div>
	</Card>

	<!-- ── 25구 종합 점수 지도 + 상세 ── -->
	<div class="mb-3.5 grid gap-3 lg:grid-cols-[1.4fr_1fr]">
		<Card title="서울 25개 구 종합 도달가능 점수 · 클릭하면 상세">
			<div bind:this={mapEl} class="conclusion-map rounded-[6px]"></div>
			<div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px]" style:color="var(--color-text2)">
				<span style:color="var(--color-text3)">도달가능 점수:</span>
				<div class="flex items-center gap-1"><span class="h-2.5 w-2.5 rounded-sm" style:background="#9B1C1C"></span>~50 최저</div>
				<div class="flex items-center gap-1"><span class="h-2.5 w-2.5 rounded-sm" style:background="#D85A30"></span>50~58</div>
				<div class="flex items-center gap-1"><span class="h-2.5 w-2.5 rounded-sm" style:background="#f5b740"></span>58~65</div>
				<div class="flex items-center gap-1"><span class="h-2.5 w-2.5 rounded-sm" style:background="#1D9E75"></span>65~73</div>
				<div class="flex items-center gap-1"><span class="h-2.5 w-2.5 rounded-sm" style:background="#0f6e56"></span>73+ 양호</div>
			</div>
		</Card>

		<Card title="구 상세 분석">
			{#if !selectedGu}
				<div class="flex h-[380px] flex-col items-center justify-center gap-2 text-center" style:color="var(--color-text3)">
					<div class="text-[34px] opacity-70">🗺</div>
					<div class="text-[13px] font-medium" style:color="var(--color-text2)">지도에서 구를 클릭하세요</div>
					<div class="text-[11.5px]">4개 도메인 점수 + 서울 평균과 비교 (radar)</div>
				</div>
			{:else}
				{#key selectedGuName + '|' + scoreKey}
					<div class="flex flex-col gap-3" in:fade={{ duration: 220 }}>
						<div>
							<div class="font-sans text-[22px] font-medium leading-tight" style:color="var(--color-text)">
								{selectedGu.name}
							</div>
							<div class="mt-0.5 flex items-baseline gap-2">
								<span
									class="font-mono text-[28px] font-medium tabular-nums"
									style:color={scoreColor(selectedGu.composite)}
								>
									<CountUp value={selectedGu.composite} decimals={1} />
								</span>
								<span class="text-[12px]" style:color="var(--color-text3)">
									점 · <b style:color="var(--color-text)">{selectedGu.rank}위</b>
								</span>
							</div>
						</div>

						<div class="space-y-1.5">
							{#each DOMAINS as d, i}
								{@const v = +selectedGu[d.key].toFixed(1)}
								<div class="grid grid-cols-[78px_1fr_50px] items-center gap-2">
									<div class="text-[11.5px]" style:color="var(--color-text2)">
										{d.emoji} {d.label}
									</div>
									<div class="relative h-[8px] rounded-full" style:background="rgba(0,0,0,0.05)">
										<div
											class="domain-bar h-full rounded-full"
											style:width="{v}%"
											style:background="{d.color}cc"
											style:--ad="{i * 80}ms"
										></div>
									</div>
									<div class="text-right font-mono text-[11.5px] tabular-nums" style:color={d.color}>
										<CountUp value={v} decimals={1} />
									</div>
								</div>
							{/each}
						</div>

						<div class="radar-fade relative h-[200px]">
							<canvas bind:this={radarChartEl}></canvas>
						</div>
					</div>
				{/key}
			{/if}
		</Card>
	</div>

	<!-- ── 25구 랭킹 ── -->
	<div class="mb-3.5 grid gap-3.5 lg:grid-cols-2">
		<!-- 상위 5 -->
		<Card title="종합 점수 상위 5개 구 · 양호">
			<div class="space-y-1.5">
				{#each ranked.slice(0, 5) as d}
					{@const w = ((d.composite - worst.composite) / (best.composite - worst.composite)) * 100}
					<div class="grid grid-cols-[28px_70px_1fr_56px] items-center gap-2.5">
						<div
							class="rounded-[4px] py-[3px] text-center font-mono text-[11px] font-medium"
							style:background="var(--color-card-soft)"
							style:color="var(--color-text3)"
						>
							{d.rank}
						</div>
						<div class="text-[12.5px] font-medium" style:color="var(--color-text)">{d.name}</div>
						<div class="relative h-[12px] rounded-[3px]" style:background="rgba(0,0,0,0.04)">
							<div
								class="h-full rounded-[3px]"
								style:width="{Math.max(8, w)}%"
								style:background={scoreColor(d.composite)}
							></div>
						</div>
						<div
							class="text-right font-mono text-[12px] font-medium tabular-nums"
							style:color={scoreColor(d.composite)}
						>
							{d.composite}
						</div>
					</div>
				{/each}
			</div>
		</Card>

		<!-- 하위 5 (취약) -->
		<Card title="종합 점수 하위 5개 구 · 취약 (정책 우선순위)">
			<div class="space-y-1.5">
				{#each ranked.slice(-5).reverse() as d}
					{@const w = ((d.composite - worst.composite) / (best.composite - worst.composite)) * 100}
					<div class="grid grid-cols-[28px_70px_1fr_56px] items-center gap-2.5">
						<div
							class="rounded-[4px] py-[3px] text-center font-mono text-[11px] font-medium"
							style:background="#fde8e8"
							style:color="#9B1C1C"
						>
							{d.rank}
						</div>
						<div class="text-[12.5px] font-medium" style:color="var(--color-text)">{d.name}</div>
						<div class="relative h-[12px] rounded-[3px]" style:background="rgba(0,0,0,0.04)">
							<div
								class="h-full rounded-[3px]"
								style:width="{Math.max(8, w)}%"
								style:background={scoreColor(d.composite)}
							></div>
						</div>
						<div
							class="text-right font-mono text-[12px] font-medium tabular-nums"
							style:color={scoreColor(d.composite)}
						>
							{d.composite}
						</div>
					</div>
				{/each}
			</div>
			<Note tone="warm" class="mt-3">
				하위 5개 구는 4개 도메인 평균이 서울 평균({seoulAvg}점)에 못 미칩니다. 도메인별 가장 약한 축이 어디인가에 따라 정책 우선순위가 달라집니다 (아래 정책 제안 표 참고).
			</Note>
		</Card>
	</div>

	<!-- ── 25구 상세 데이터 테이블 ── -->
	<Card title="전체 25개 구 상세 점수 · 건강 노인 1.12 m/s · 경사 미보정" class="mb-3.5">
		<div class="mb-3 flex flex-wrap items-center gap-2">
			<span class="kicker">정렬</span>
			{#each [
				{ key: 'composite', label: '종합' },
				{ key: 'climate',   label: '기후' },
				{ key: 'infra',     label: '인프라' },
				{ key: 'bokji',     label: '복지' },
				{ key: 'medical',   label: '의료' },
				{ key: 'name',      label: '가나다' }
			] as t}
				<button
					type="button"
					class="rounded-[6px] px-3 py-1 text-[11.5px] transition-colors"
					style:background={sortKey === t.key ? 'var(--color-dark)' : '#fff'}
					style:color={sortKey === t.key ? 'var(--color-dark-text)' : 'var(--color-text2)'}
					style:border="0.5px solid {sortKey === t.key ? 'var(--color-dark)' : 'var(--color-border)'}"
					onclick={() => (sortKey = t.key)}
				>
					{t.label}
				</button>
			{/each}
		</div>

		<div class="overflow-x-auto rounded-[8px]" style:background="var(--color-card-soft)">
			<table class="w-full text-[12px]">
				<thead>
					<tr style:border-bottom="0.5px solid var(--color-border)">
						<th class="ct-label px-3 py-2 text-left">순위</th>
						<th class="ct-label px-3 py-2 text-left">자치구</th>
						{#each DOMAINS as d}
							<th class="ct-label px-3 py-2 text-left" style:color={d.color}>
								{d.emoji} {d.label}
							</th>
						{/each}
						<th class="ct-label px-3 py-2 text-left">종합</th>
						<th class="ct-label px-3 py-2 text-left">최약축</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedTable as d, i (d.name)}
						<tr style:border-bottom="0.5px solid var(--color-border-soft)">
							<td class="px-3 py-2 font-mono tabular-nums" style:color="var(--color-text3)">
								{i + 1}
							</td>
							<td class="px-3 py-2 font-medium" style:color="var(--color-text)">{d.name}</td>
							{#each ['climate', 'infra', 'bokji', 'medical'] as k}
								<td class="px-3 py-2">
									<span
										class="inline-block rounded-[4px] px-2 py-[2px] font-mono text-[11.5px] tabular-nums"
										style:background={scoreBg(d[k])}
										style:color={scoreColor(d[k])}
									>
										{d[k].toFixed(1)}
									</span>
								</td>
							{/each}
							<td class="px-3 py-2">
								<strong
									class="font-mono text-[13px] tabular-nums"
									style:color={scoreColor(d.composite)}
								>
									{d.composite}
								</strong>
							</td>
							<td class="px-3 py-2 text-[11.5px]" style:color="var(--color-text3)">
								{d.weakest.emoji} {d.weakest.label}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<p class="mt-3 text-[11px] leading-[1.7]" style:color="var(--color-text3)">
			* 도메인 점수 = (건강 노인 도달 노드 수 / 일반인 도달 노드 수) × 100. 기준 시간 30분 고정.<br />
			** 종합 점수 = 4개 도메인 산술 평균. 본 페이지는 경사 미보정 기준이며, 경사 보정 적용 시 강북·도봉·관악·성북 등 가파른 구는 추가 하락합니다.<br />
			*** 교통·이동 도메인은 결론 CSV가 별도 분석 단계에 있어 본 종합 점수에서 제외됨 (도메인 페이지에서 별도 살펴봅니다).
		</p>
	</Card>

	<!-- ── 정책 제안 ── -->
	<Card title="정책 제안 · 도메인별 우선 투입 자치구" class="mb-3.5">
		<h2 class="mb-2 font-sans text-[22px] font-medium leading-[1.3]" style:color="var(--color-text)">
			같은 예산이면 어디부터 — 도메인별 최저 3개 구
		</h2>
		<p class="mb-4 text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
			종합 점수가 평균 이상이라도 특정 도메인이 약한 구가 있습니다. 4개 도메인 각각의 하위 3개 구를 제시합니다.
			같은 노인 인구라도 어느 축이 무너졌는지에 따라 처방이 달라집니다.
		</p>

		<div class="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
			{#each policySuggestions as p}
				<div
					class="rounded-[10px] p-4"
					style:background="var(--color-card-soft)"
					style:border="0.5px solid {p.color}22"
				>
					<div class="mb-2 flex items-center gap-2">
						<span class="text-[20px]">{p.emoji}</span>
						<span class="text-[14px] font-medium" style:color={p.color}>{p.label}</span>
					</div>
					<div class="kicker mb-2">우선 투입 ↓</div>
					<div class="space-y-1.5">
						{#each p.bottom3 as b, i}
							<div
								class="flex items-center justify-between rounded-[6px] px-2.5 py-1.5"
								style:background="#fff"
								style:border="0.5px solid var(--color-border-soft)"
							>
								<div class="flex items-center gap-2">
									<span
										class="font-mono text-[10.5px] font-medium"
										style:color="var(--color-text3)"
									>
										{i + 1}
									</span>
									<span class="text-[12.5px]" style:color="var(--color-text)">{b.name}</span>
								</div>
								<span
									class="font-mono text-[11.5px] tabular-nums"
									style:color={scoreColor(b[p.key])}
								>
									{b[p.key].toFixed(1)}
								</span>
							</div>
						{/each}
					</div>
					<div class="kicker mt-3">정책 키워드</div>
					<p class="mt-1 text-[11.5px] leading-[1.6]" style:color="var(--color-text2)">
						{#if p.key === 'climate'}
							폭염쉼터·한파쉼터 추가 배치, 정류장 100m 내 쉼터 연계, 그늘막·보행쉘터 보강.
						{:else if p.key === 'infra'}
							전통시장·약국·생활편의 시설 보행 접근성 개선, 보행 네트워크 연속성 확보.
						{:else if p.key === 'bokji'}
							경로당·노인복지관 신설 또는 이전, 공원·녹지 보행로 정비.
						{:else if p.key === 'medical'}
							병의원·약국 접근성 보완, 응급 도달 사각지대 해소 (방문 의료·셔틀).
						{/if}
					</p>
				</div>
			{/each}
		</div>
	</Card>

	<!-- ── 종합 결론 ── -->
	<Card title="결론 · 절반의 서울" class="mb-3.5">
		<div class="grid gap-3 md:grid-cols-3">
			<div>
				<div class="kicker mb-1.5">발견 1 · 종합 격차</div>
				<p class="text-[12.5px] leading-[1.75]" style:color="var(--color-text2)">
					최고({best.name} {best.composite}점) ↔ 최저({worst.name} {worst.composite}점) 사이의 종합 격차는
					<strong style:color="var(--color-accent)">
						{(best.composite - worst.composite).toFixed(1)}점
					</strong>.
					같은 서울 안에서 4개 축 평균 도달가능성이 가시적인 차이로 갈립니다.
				</p>
			</div>
			<div>
				<div class="kicker mb-1.5">발견 2 · 보행보조 시 절벽</div>
				<p class="text-[12.5px] leading-[1.75]" style:color="var(--color-text2)">
					일반 노인 평균 77점이 보행보조 노인 기준에서는 <strong style:color="var(--color-accent)">47점</strong>으로 떨어진다.
					기준 보행속도 0.24&nbsp;m/s 차이가 도달 노드 수의 절반을 잘라냅니다.
				</p>
			</div>
			<div>
				<div class="kicker mb-1.5">발견 3 · 도메인 비대칭</div>
				<p class="text-[12.5px] leading-[1.75]" style:color="var(--color-text2)">
					같은 자치구라도 도메인별 점수는 비대칭입니다. 종합 점수만으로는 보이지 않는 약한 축(기후/인프라/복지/녹지/의료)이 정책의 진짜 진입점입니다.
				</p>
			</div>
		</div>

		<Note tone="warm" class="mt-4">
			<strong>다음 분석 → 경사 보정.</strong>
			Tobler's Hiking Function 기반 경사 감쇄를 적용하면 강북·도봉·관악·성북 등 구도심 가파른 구의 실질 도달가능성은 추가로 하락합니다.
			도메인별 페이지에서 경사 보정 토글을 확인할 수 있습니다.
		</Note>
	</Card>

</section>

<style>
	.conclusion-map {
		height: 380px;
		width: 100%;
		background: #e8e4db;
	}

	/* iOS 스타일 토글 스위치 */
	.toggle-item {
		display: inline-flex;
		align-items: center;
		gap: 9px;
		cursor: pointer;
		user-select: none;
	}
	.toggle-switch {
		position: relative;
		display: inline-block;
		width: 38px;
		height: 22px;
		flex-shrink: 0;
	}
	.toggle-switch input {
		opacity: 0;
		width: 0;
		height: 0;
		position: absolute;
	}
	.toggle-slider {
		position: absolute;
		inset: 0;
		background: #d3d1c7;
		border-radius: 999px;
		transition:
			background 0.22s,
			box-shadow 0.22s;
	}
	.toggle-slider::before {
		content: '';
		position: absolute;
		left: 2px;
		top: 2px;
		width: 18px;
		height: 18px;
		background: #fff;
		border-radius: 50%;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
		transition: transform 0.22s cubic-bezier(0.16, 0.84, 0.36, 1);
	}
	.toggle-switch.on .toggle-slider {
		background: var(--pill-accent, var(--color-dark));
	}
	.toggle-switch.on .toggle-slider::before {
		transform: translateX(16px);
	}
	.toggle-label {
		font-size: 12.5px;
		color: var(--color-text2);
		font-weight: 500;
		white-space: nowrap;
	}
	.slope-tag {
		display: inline-block;
		padding: 2px 8px;
		font-family: var(--font-mono);
		font-size: 10px;
		letter-spacing: 0.04em;
		color: var(--color-accent);
		background: rgba(216, 90, 48, 0.1);
		border-radius: 999px;
	}

	.bar-fill,
	.domain-bar {
		animation: bar-reveal 0.85s cubic-bezier(0.16, 0.84, 0.36, 1) both;
		animation-delay: var(--ad, 0ms);
		transform-origin: left center;
		will-change: transform;
		backface-visibility: hidden;
		transform: translateZ(0);
	}
	.radar-fade {
		animation: radar-in 0.55s ease-out 0.4s both;
	}
	@keyframes radar-in {
		from {
			opacity: 0;
			transform: scale(0.92);
		}
		to {
			opacity: 1;
			transform: scale(1);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.radar-fade {
			animation: none;
		}
	}
	@keyframes bar-reveal {
		from {
			transform: translateZ(0) scaleX(0);
		}
		to {
			transform: translateZ(0) scaleX(1);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.bar-fill {
			animation: none;
		}
	}
</style>
