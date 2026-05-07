<script>
	import { onMount, onDestroy } from 'svelte';
	import bokji from '$lib/data/bokji.json';
	import Card from '$lib/components/Card.svelte';
	import ChartCard from '$lib/components/ChartCard.svelte';
	import MapShell from '$lib/components/MapShell.svelte';
	import Note from '$lib/components/Note.svelte';
	import PillButton from '$lib/components/PillButton.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import StatCard from '$lib/components/StatCard.svelte';

	const meta = {
		title: '복지·녹지 인프라',
		kicker: 'YANG · 노인복지관·경로당·공원',
		accent: 'var(--color-purple)'
	};

	const { DONG, WELFARE, PARK, GU_CENTER, SPEEDS, TC } = bokji;

	// ── 상태 (Svelte 5 runes) ──────────────────────────────────────
	let cW = $state(0); // 보행자 인덱스
	let cF = $state('both'); // 시설 유형: both / welfare / park
	let cLayer = $state('both'); // 지도 레이어 토글
	let cG = $state('종로구'); // 자치구
	let cSlope = $state(false);
	let cDong = $state(false);

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
		return Math.round((getW(d) / base) * 100);
	}
	function pScore(d) {
		const base = d.p[0];
		if (base === 0) return null;
		return Math.round((getP(d) / base) * 100);
	}
	function combinedScore(d) {
		const ws = wScore(d),
			ps = pScore(d);
		if (ws === null && ps === null) return null;
		if (ws === null) return ps;
		if (ps === null) return ws;
		return Math.round((ws + ps) / 2);
	}
	function curScore(d) {
		if (cF === 'welfare') return wScore(d);
		if (cF === 'park') return pScore(d);
		return combinedScore(d);
	}
	function scoreColor(s) {
		if (s === null) return '#9E9E9E';
		if (s >= 80) return '#2E7D32';
		if (s >= 50) return '#F57F17';
		return '#C62828';
	}

	// ── 통계 카드 ──────────────────────────────────────────────────
	const stats = $derived.by(() => {
		const gd = DONG.filter((d) => d.gu === cG);
		const n = gd.length || 1;
		const isNormal = cW === 0;
		const avgW = (gd.reduce((s, d) => s + getW(d), 0) / n).toFixed(1);
		const avgP = (gd.reduce((s, d) => s + getP(d), 0) / n).toFixed(1);
		let avgWS = null,
			avgPS = null;
		if (!isNormal) {
			const validW = gd.filter((d) => d.w[0] > 0);
			const validP = gd.filter((d) => d.p[0] > 0);
			avgWS = validW.length
				? Math.round(validW.reduce((s, d) => s + wScore(d), 0) / validW.length)
				: null;
			avgPS = validP.length
				? Math.round(validP.reduce((s, d) => s + pScore(d), 0) / validP.length)
				: null;
		}
		return { gd, isNormal, avgW, avgP, avgWS, avgPS };
	});

	// ── 취약 동 (취약도 ≥ 0.5) ─────────────────────────────────────
	const vulnCount = $derived(DONG.filter((d) => d.vuln >= 0.5).length);

	// ── 테이블: 정렬된 동 목록 ────────────────────────────────────
	const sortedDong = $derived.by(() => {
		const isNormal = cW === 0;
		if (isNormal) {
			return [...DONG].filter((d) => d.pop65 > 0).sort((a, b) => b.vuln - a.vuln);
		}
		return [...DONG]
			.filter((d) => d.pop65 > 0)
			.sort((a, b) => {
				const sa = curScore(a),
					sb = curScore(b);
				if (sa === null && sb === null) return 0;
				if (sa === null) return 1;
				if (sb === null) return -1;
				return sa - sb;
			});
	});

	// ── Leaflet ────────────────────────────────────────────────────
	let mapEl = $state();
	let mapReady = $state(false);
	let map;
	let L;
	let welfareGroup;
	let parkGroup;
	let radiusCircle = null;
	let dongCircleGroup = null;

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

		mapReady = true;
	});

	// 레이어 토글 (cLayer)
	$effect(() => {
		if (!mapReady) return;
		if (cLayer === 'welfare') {
			map.addLayer(welfareGroup);
			map.removeLayer(parkGroup);
		} else if (cLayer === 'park') {
			map.removeLayer(welfareGroup);
			map.addLayer(parkGroup);
		} else {
			map.addLayer(welfareGroup);
			map.addLayer(parkGroup);
		}
	});

	// 자치구 중심 반경원 + 뷰 이동
	$effect(() => {
		if (!mapReady) return;
		// react to cG, cW, cSlope
		const center = GU_CENTER[cG];
		if (radiusCircle) {
			map.removeLayer(radiusCircle);
			radiusCircle = null;
		}
		if (!center) return;
		let radiusM = Math.round(SPEEDS[cW].mps * 30 * 60);
		let tooltipExtra = '';
		if (cSlope && cW > 0) {
			const gd = DONG.filter((d) => d.gu === cG);
			const avgTobler = gd.length ? gd.reduce((s, d) => s + d.tobler, 0) / gd.length : 1.0;
			radiusM = Math.round(SPEEDS[cW].mps * avgTobler * 30 * 60);
			tooltipExtra = ` (경사보정 · 구평균 tobler ${avgTobler.toFixed(3)})`;
		}
		radiusCircle = L.circle(center, {
			radius: radiusM,
			color: '#FF6F00',
			weight: 2,
			dashArray: '8,5',
			fillColor: '#FF6F00',
			fillOpacity: 0.04
		})
			.bindTooltip(
				`${cG} 중심 · ${SPEEDS[cW].key} 30분 반경 ~${(radiusM / 1000).toFixed(2)} km${tooltipExtra}`
			)
			.addTo(map);
		map.setView(center, 12, { animate: true, duration: 0.4 });
	});

	// 동별 반경 원
	$effect(() => {
		if (!mapReady) return;
		// react to cDong, cG, cW, cSlope, cF
		if (dongCircleGroup) {
			map.removeLayer(dongCircleGroup);
			dongCircleGroup = null;
		}
		if (!cDong) return;
		dongCircleGroup = L.layerGroup().addTo(map);
		const gd = DONG.filter((d) => d.gu === cG && d.clat !== null && d.clng !== null);
		gd.forEach((d) => {
			const tobler = cSlope && cW > 0 ? d.tobler : 1.0;
			const radiusM = Math.round(SPEEDS[cW].mps * tobler * 30 * 60);
			const s = curScore(d);
			const col = scoreColor(s);
			const scoreText = s !== null ? s + '점' : 'N/A';
			const slopeTip = cSlope && cW > 0 ? `<br>Tobler: ${d.tobler.toFixed(3)}` : '';

			L.circle([d.clat, d.clng], {
				radius: radiusM,
				color: col,
				weight: 1.2,
				dashArray: '5,4',
				fillColor: col,
				fillOpacity: 0.06
			})
				.bindTooltip(
					`<b>${d.gu} ${d.dong}</b><br>보행반경: ~${(radiusM / 1000).toFixed(2)} km<br>도달가능점수: ${scoreText}<br>복지 도달: ${getW(d)}개 · 공원 도달: ${getP(d)}개${slopeTip}`
				)
				.addTo(dongCircleGroup);

			L.circleMarker([d.clat, d.clng], {
				radius: 3,
				color: col,
				weight: 1,
				fillColor: col,
				fillOpacity: 0.9
			}).addTo(dongCircleGroup);

			if (s !== null && s < 50) {
				L.marker([d.clat, d.clng], {
					icon: L.divIcon({
						className: '',
						html: `<div style="font-size:9px;font-weight:600;color:${col};white-space:nowrap;text-shadow:0 0 2px #fff">${d.dong}</div>`,
						iconAnchor: [0, 0]
					})
				}).addTo(dongCircleGroup);
			}
		});
	});

	onDestroy(() => map?.remove());

	// ── Chart.js ──────────────────────────────────────────────────
	let Chart;
	let guChart;
	let speedChart;
	let top10Chart;

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

	async function setupSpeedChart(canvas) {
		const C = await ensureChart();
		speedChart = new C(canvas, {
			type: 'bar',
			data: { labels: [], datasets: [] },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 200 },
				plugins: {
					legend: { position: 'top', labels: { font: { size: 10 }, boxWidth: 12 } },
					tooltip: {
						callbacks: { label: (c) => ` ${parseFloat(c.raw).toFixed(2)}개 (평균)` }
					}
				},
				scales: {
					x: { grid: { display: false }, ticks: { font: { size: 10 } } },
					y: {
						grid: { color: '#f1efe8' },
						title: { display: true, text: '평균 도달 수', font: { size: 10 } }
					}
				}
			}
		});
		updateSpeedChart();
	}

	async function setupTop10Chart(canvas) {
		const C = await ensureChart();
		top10Chart = new C(canvas, {
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
							label: (c) => {
								const v = parseFloat(c.raw);
								return cW === 0 ? ` 취약도: ${v.toFixed(3)}` : ` 도달가능점수: ${v}점`;
							}
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
		updateTop10Chart();
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
			if (cF === 'welfare') v = dongs.reduce((s, d) => s + getW(d), 0) / dongs.length;
			else if (cF === 'park') v = dongs.reduce((s, d) => s + getP(d), 0) / dongs.length;
			else v = dongs.reduce((s, d) => s + getW(d) + getP(d), 0) / dongs.length;
			return { gu: g, val: v };
		});
		vals.sort((a, b) => b.val - a.val);
		guChart.data.labels = vals.map((v) => v.gu);
		guChart.data.datasets = [
			{
				data: vals.map((v) => +v.val.toFixed(2)),
				backgroundColor: vals.map((v) => (v.gu === cG ? '#D85A30' : SPEEDS[cW].color + 'aa')),
				borderRadius: 3
			}
		];
		guChart.update('none');
	}

	function updateSpeedChart() {
		if (!speedChart) return;
		const gd = DONG.filter((d) => d.gu === cG);
		if (!gd.length) return;
		const n = gd.length;
		const wOrig = SPEEDS.map((_, i) => +(gd.reduce((s, d) => s + d.w[i], 0) / n).toFixed(2));
		const pOrig = SPEEDS.map((_, i) => +(gd.reduce((s, d) => s + d.p[i], 0) / n).toFixed(2));
		const wCorr = SPEEDS.map((_, i) => +(gd.reduce((s, d) => s + d.wc[i], 0) / n).toFixed(2));
		const pCorr = SPEEDS.map((_, i) => +(gd.reduce((s, d) => s + d.pc[i], 0) / n).toFixed(2));
		const wData = cSlope ? wCorr : wOrig;
		const pData = cSlope ? pCorr : pOrig;
		const slopeSuffix = cSlope ? ' (경사보정)' : '';
		speedChart.data.labels = SPEEDS.map((s) => s.key);
		speedChart.data.datasets = [
			{
				label: `복지시설${slopeSuffix}`,
				data: wData,
				backgroundColor: '#185FA5cc',
				borderRadius: 4
			},
			{ label: `공원${slopeSuffix}`, data: pData, backgroundColor: '#2E7D32cc', borderRadius: 4 }
		];
		speedChart.update('none');
	}

	function updateTop10Chart() {
		if (!top10Chart) return;
		if (cW === 0) {
			top10Chart.options.scales.x.max = 1.05;
			top10Chart.options.scales.x.title.text = '취약도 지수';
			const top10 = [...DONG]
				.filter((d) => d.pop65 > 0)
				.sort((a, b) => b.vuln - a.vuln)
				.slice(0, 10)
				.reverse();
			const colors = top10.map((_, i) => {
				const t = i / 9;
				const r = Math.round(180 + 75 * t);
				const g = Math.round(120 * (1 - t));
				return `rgba(${r},${g},0,0.85)`;
			});
			top10Chart.data.labels = top10.map((d) => `${d.gu} ${d.dong}`);
			top10Chart.data.datasets = [
				{ data: top10.map((d) => d.vuln), backgroundColor: colors, borderRadius: 3 }
			];
		} else {
			top10Chart.options.scales.x.max = undefined;
			top10Chart.options.scales.x.title.text = '도달가능점수 (점)';
			const scored = DONG.filter((d) => d.pop65 > 0 && curScore(d) !== null)
				.map((d) => ({ d, s: curScore(d) }))
				.sort((a, b) => a.s - b.s)
				.slice(0, 10);
			const colors = scored.map(({ s }) => {
				if (s >= 80) return 'rgba(15,110,86,0.8)';
				if (s >= 50) return 'rgba(133,79,11,0.8)';
				return 'rgba(163,45,45,0.85)';
			});
			top10Chart.data.labels = scored.map(({ d }) => `${d.gu} ${d.dong}`);
			top10Chart.data.datasets = [
				{ data: scored.map(({ s }) => s), backgroundColor: colors, borderRadius: 3 }
			];
		}
		top10Chart.update('none');
	}

	// 컨트롤 변경 시 차트 재그리기
	$effect(() => {
		// reactive deps
		void cW;
		void cF;
		void cG;
		void cSlope;
		updateGuChart();
		updateSpeedChart();
		updateTop10Chart();
	});

	// 점수 → 등급 pill 클래스
	function pillClass(s) {
		if (s === null) return 'pna';
		if (s >= 80) return 'phi';
		if (s >= 50) return 'pmd';
		return 'plo';
	}

	const top10TitleText = $derived(
		cW === 0 ? '취약도 TOP 10 행정동' : `도달가능점수 하위 10 행정동${cSlope ? ' (경사보정)' : ''}`
	);

	const tblLabel = $derived(
		cW === 0
			? '취약도 내림차순 · 취약도 = (복지박탈 50% + 공원박탈 50%) Min-Max 정규화'
			: `도달가능점수 오름차순 · ${SPEEDS[cW].key} 기준 · 일반인 도달 수 = 0 시 N/A${cSlope ? ' · 경사로 보정 적용' : ''}`
	);
</script>

<section class="wrap mx-auto px-[18px] pt-[18px] pb-[52px]" style:max-width="1320px">
	<!-- 페이지 타이틀 -->
	<div class="mb-4">
		<p class="kicker mb-1.5">{meta.kicker}</p>
		<h1 class="serif-h text-[26px] font-medium" style:color={meta.accent}>{meta.title}</h1>
		<p class="text-[12px]" style:color="var(--color-text3)">
			OSM 보행 네트워크 기반 · 노인여가복지시설 {WELFARE.length}개소 + 공원 {PARK.length}개소 · 30분 기준 ·
			Tobler 경사 보정
		</p>
	</div>

	<!-- ── 컨트롤 패널 ── -->
	<div class="ctrl">
		<div class="crow">
			<span class="lbl">보행자 유형</span>
			{#each SPEEDS as s, i}
				<PillButton variant="wide" active={cW === i} onclick={() => (cW = i)}>
					{['🚶', '🧓', '🦽', '♿'][i]} {s.key} &nbsp;{s.mps} m/s
				</PillButton>
			{/each}
			<span class="flex-1"></span>
			<span class="lbl">시설 유형</span>
			<PillButton active={cF === 'both'} onclick={() => (cF = 'both')}>복지 + 공원</PillButton>
			<PillButton active={cF === 'welfare'} onclick={() => (cF = 'welfare')}>복지시설만</PillButton>
			<PillButton active={cF === 'park'} onclick={() => (cF = 'park')}>공원만</PillButton>
		</div>
		<div class="crow">
			<span class="lbl">경사로 보정</span>
			<button
				type="button"
				class="pill-btn"
				class:slope-on={cSlope}
				onclick={() => (cSlope = !cSlope)}
			>
				{cSlope ? '경사로 보정 적용 중' : '경사로 보정 적용'}
			</button>
			<span class="ml-1 text-[11px]" style:color="var(--color-text3)">
				· Tobler 보행속도 모델 · OSM 기반 동별 경사도 반영 · 일반인 속도 제외
			</span>
		</div>
		<div class="crow">
			<span class="lbl">동 단위 반경</span>
			<button
				type="button"
				class="pill-btn"
				class:slope-on={cDong}
				onclick={() => (cDong = !cDong)}
			>
				{cDong ? '동별 반경 표시 중' : '동별 반경 표시'}
			</button>
			<span class="ml-1 text-[11px]" style:color="var(--color-text3)">
				· 선택 자치구 내 각 행정동 중심점 기준 · 점수 색상 반영
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
			<StatGrid cols={4}>
				<StatCard
					label="평균 도달 복지시설 수"
					value={`${stats.avgW}개소`}
					sub={`${cG} · ${SPEEDS[cW].key} · 30분${cSlope && cW > 0 ? ' · 경사보정' : ''}`}
				/>
				<StatCard
					label="평균 도달 공원 수"
					value={`${stats.avgP}개소`}
					sub={`${cG} · ${SPEEDS[cW].key} · 30분${cSlope && cW > 0 ? ' · 경사보정' : ''}`}
				/>
				{#if stats.isNormal}
					<StatCard label="복지 도달가능점수" value="일반인 기준" sub="선택 시 항상 100점 (숨김)" />
					<StatCard label="공원 도달가능점수" value="일반인 기준" sub="선택 시 항상 100점 (숨김)" />
				{:else}
					<StatCard
						label={`복지 도달가능점수${cSlope ? ' (경사보정)' : ''}`}
						value={stats.avgWS !== null ? `${stats.avgWS}점` : 'N/A'}
						sub={`${cG} · ${SPEEDS[cW].key} · 일반인 대비`}
						tone="blue"
					/>
					<StatCard
						label={`공원 도달가능점수${cSlope ? ' (경사보정)' : ''}`}
						value={stats.avgPS !== null ? `${stats.avgPS}점` : 'N/A'}
						sub={`${cG} · ${SPEEDS[cW].key} · 일반인 대비`}
						tone="green"
					/>
				{/if}
			</StatGrid>
			<div class="mt-2 text-[11px]" style:color="var(--color-text3)">
				서울 전체 취약 동 ({vulnCount}개) · 취약도 ≥ 0.5 기준
			</div>
		</div>
	</div>

	<!-- ── 지도 + 속도 비교 차트 ── -->
	<div class="r2 mt-3.5">
		<Card title="서울시 복지·녹지 시설 분포 지도">
			<div class="tabs mb-2.5">
				<button
					type="button"
					class="tab"
					class:on={cLayer === 'both'}
					onclick={() => (cLayer = 'both')}>복지시설 + 공원</button
				>
				<button
					type="button"
					class="tab"
					class:on={cLayer === 'welfare'}
					onclick={() => (cLayer = 'welfare')}>복지시설만</button
				>
				<button
					type="button"
					class="tab"
					class:on={cLayer === 'park'}
					onclick={() => (cLayer = 'park')}>공원만</button
				>
			</div>
			<MapShell
				height="420px"
				legend={[
					{ color: '#185FA5', label: '노인복지관', shape: 'circle' },
					{ color: '#E8A838', label: '노인교실', shape: 'circle' },
					{ color: '#8AAFD4', label: '소규모복지관', shape: 'circle' },
					{ color: '#4CAF50', label: '공원', shape: 'circle' },
					{ color: '#FF6F00', label: '30분 보행반경 (점선)' }
				]}
				source="출처: 서울시 사회복지시설(노인여가복지시설) 목록 · 서울시 주요 공원현황(2026 상반기) · 반경은 자치구 중심점 기준 직선거리"
			>
				<div bind:this={mapEl} class="absolute inset-0 h-full w-full"></div>
			</MapShell>
		</Card>

		<ChartCard
			title={`선택 자치구 4속도 비교 — ${cG}`}
			height="300px"
			onmount={setupSpeedChart}
		/>
	</div>

	<!-- ── 자치구별 차트 + TOP10 ── -->
	<div class="r2b mt-3.5">
		<ChartCard
			title="자치구별 평균 도달 시설 수 (현재 보행자·시설 기준)"
			height="300px"
			onmount={setupGuChart}
		/>
		<ChartCard title={top10TitleText} height="300px" onmount={setupTop10Chart} />
	</div>

	<!-- ── 상세 테이블 ── -->
	<div class="card-shell mt-3.5">
		<div class="ct-label mb-2">행정동별 복지·녹지 접근성 상세표 (TOP 10)</div>
		<p class="mb-1.5 text-[11px]" style:color="var(--color-text3)">{tblLabel}</p>
		<div class="tbl-wrap">
			<table>
				<thead>
					<tr>
						<th>구명</th>
						<th>동명</th>
						<th>65세이상</th>
						<th>고령화율</th>
						{#if stats.isNormal}
							<th>취약도</th>
						{:else}
							<th>복지점수{cSlope ? ' (경사)' : ''}</th>
							<th>공원점수{cSlope ? ' (경사)' : ''}</th>
						{/if}
						<th>복지 도달수</th>
						<th>공원 도달수</th>
						<th>Tobler</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedDong.slice(0, 10) as d (d.key)}
						{@const ws = wScore(d)}
						{@const ps = pScore(d)}
						{@const wCnt = getW(d)}
						{@const pCnt = getP(d)}
						<tr>
							<td>{d.gu}</td>
							<td>{d.dong}</td>
							<td>{d.pop65.toLocaleString()}</td>
							<td>{d.aging}%</td>
							{#if stats.isNormal}
								<td>
									<span
										class="pill"
										class:phi={d.vuln < 0.4}
										class:pmd={d.vuln >= 0.4 && d.vuln < 0.7}
										class:plo={d.vuln >= 0.7}>{d.vuln.toFixed(3)}</span
									>
								</td>
							{:else}
								<td>
									<span class="pill {pillClass(ws)}">{ws === null ? 'N/A' : ws + '점'}</span>
								</td>
								<td>
									<span class="pill {pillClass(ps)}">{ps === null ? 'N/A' : ps + '점'}</span>
								</td>
							{/if}
							<td
								class:bad={wCnt === 0 && d.w[0] > 0}>{wCnt}</td
							>
							<td
								class:bad={pCnt === 0 && d.p[0] > 0}>{pCnt}</td
							>
							<td class="text-[11px]" style:color="var(--color-text3)">{d.tobler.toFixed(3)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>

	<Note tone="warm" class="mt-3">
		※ 도달가능점수 = (선택 속도 도달 시설 수 / 일반인 속도 도달 시설 수) × 100<br />
		※ 일반인 선택 시 점수는 항상 100이므로 숨김 처리 · 분모(일반인 도달 수) = 0이면 N/A 표시<br />
		※ 경사로 보정: Tobler 보행속도 모델 적용 · 동별 OSM 경사도 기반 · 일반인 속도는 보정 대상 제외<br
		/>
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
	}
	.pill-btn.slope-on {
		background: #2e5a88;
		color: #f1efe8;
		border-color: #2e5a88;
	}
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
	.tabs {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}
	.tab {
		font-size: 12px;
		padding: 4px 12px;
		border-radius: 6px;
		border: 0.5px solid transparent;
		background: transparent;
		color: var(--color-text3);
		cursor: pointer;
		font-family: inherit;
	}
	.tab:hover {
		background: var(--color-card-soft);
	}
	.tab.on {
		background: #f1efe8;
		color: var(--color-text);
		font-weight: 500;
		border-color: var(--color-border);
	}
	.tbl-wrap {
		overflow-x: auto;
		max-height: 480px;
		overflow-y: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 12px;
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
		background: var(--color-card);
		z-index: 1;
	}
	td {
		padding: 7px 10px;
		border-bottom: 0.5px solid var(--color-border-soft);
	}
	tr:hover td {
		background: #fafaf8;
	}
	td.bad {
		font-weight: 600;
		color: #a32d2d;
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
	.pna {
		background: #ebebeb;
		color: #666;
	}
	.serif-h {
		font-family: var(--font-serif);
	}
	@media (max-width: 900px) {
		.r2,
		.r2b {
			grid-template-columns: 1fr;
		}
	}

	/* Leaflet 컨테이너 클릭 캡처 */
	:global(.leaflet-container) {
		font-family: inherit;
		background: #e8e4db;
	}
</style>
