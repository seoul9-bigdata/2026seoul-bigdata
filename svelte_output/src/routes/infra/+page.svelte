<script>
	import { onMount, onDestroy } from 'svelte';
	import infraData from '$lib/data/infra.json';
	import Card from '$lib/components/Card.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import ChartCard from '$lib/components/ChartCard.svelte';
	import MapShell from '$lib/components/MapShell.svelte';
	import PillButton from '$lib/components/PillButton.svelte';
	import Note from '$lib/components/Note.svelte';

	const meta = { title: '인프라', kicker: 'SHIM · 시장·은행·주민센터', accent: 'var(--color-teal)' };

	const {
		ALL_DONG_DATA,
		BANK_SERIES,
		CENTERS,
		CENTER_BY_GU,
		DONG_REACH,
		GU_ORDER,
		MKT,
		SEOUL_BANKS,
		SUP,
		TOP10_VULNERABLE,
		WS
	} = infraData;

	// ── 상태 (Svelte 5 runes) ──
	let cW = $state(3); // 보행자 인덱스 (0=일반, 1=노인, 2=보조, 3=하위15%)
	let cT = $state(15); // 보행시간 (분)
	let cG = $state('중구'); // 자치구
	let cD = $state('중구_소공동'); // 행정동 키
	// 시설 토글 (시장/슈퍼/은행/주민센터) — chk-btn 패턴 (4개 독립 토글)
	let showMkt = $state(true);
	let showSup = $state(true);
	let showBank = $state(false);
	let showCenter = $state(false);

	// ── 파생 ──
	const currentW = $derived(WS[cW]);
	const currentDong = $derived(ALL_DONG_DATA[cD] || null);
	const currentReach = $derived(DONG_REACH[cD] || null);
	const wReach = $derived(currentReach ? currentReach[currentW.id] : null);
	const radiusM = $derived(Math.round(currentW.speed * cT * 60));
	const dongList = $derived(
		Object.entries(DONG_REACH)
			.filter(([, v]) => v['구'] === cG)
			.map(([k, v]) => ({ key: k, dong: v['동'] }))
			.sort((a, b) => a.dong.localeCompare(b.dong, 'ko'))
	);

	function onGuChange(e) {
		const g = e.target.value;
		cG = g;
		const list = Object.entries(DONG_REACH).filter(([, v]) => v['구'] === g);
		if (list.length) cD = list[0][0];
	}
	function onDongChange(e) {
		cD = e.target.value;
		cG = (ALL_DONG_DATA[cD] || {}).gu || cG;
	}

	// ══════════════════════════════════════════════
	// Leaflet
	// ══════════════════════════════════════════════
	let mapEl = $state();
	/** @type {any} */
	let map;
	/** @type {any} */
	let L;
	let mktLyr, supLyr, bankLyr, centerLyr, radLyr;
	let cMark = null;

	onMount(async () => {
		L = (await import('leaflet')).default;
		await import('leaflet/dist/leaflet.css');

		map = L.map(mapEl, { zoomControl: true }).setView([37.5665, 126.978], 11);
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			attribution: '© CARTO',
			subdomains: 'abcd',
			maxZoom: 19,
			detectRetina: true
		}).addTo(map);

		mktLyr = L.layerGroup();
		supLyr = L.layerGroup();
		bankLyr = L.layerGroup();
		centerLyr = L.layerGroup();
		radLyr = L.layerGroup().addTo(map);

		// 시설 마커 한번만 빌드
		MKT.forEach((m) =>
			L.circleMarker([m.lat, m.lng], {
				radius: Math.max(4, Math.min(10, 4 + m.stores / 200)),
				fillColor: m.type === '상설장' ? '#1D9E75' : m.type === '정기장' ? '#185FA5' : '#888',
				color: '#fff',
				weight: 1.5,
				fillOpacity: 0.9
			})
				.bindPopup(`<b>${m.name}</b><br>${m.type} · ${m.stores}개`)
				.addTo(mktLyr)
		);
		SUP.forEach((s) =>
			L.circleMarker([s.lat, s.lng], {
				radius: 3,
				fillColor: s.type === '편의점' ? '#D85A30' : '#E8A838',
				color: '#fff',
				weight: 0.5,
				fillOpacity: 0.6
			})
				.bindPopup(`<b>${s.name}</b><br>${s.type}`)
				.addTo(supLyr)
		);
		SEOUL_BANKS.forEach((b) =>
			L.circleMarker([b.lat, b.lng], {
				radius: 4,
				fillColor: '#7B5EA7',
				color: '#fff',
				weight: 0.8,
				fillOpacity: 0.85
			})
				.bindPopup(`<b>${b.name}</b><br>${b.bank} · ${b.gu}`)
				.addTo(bankLyr)
		);
		CENTERS.forEach((c) =>
			L.circleMarker([c.lat, c.lng], {
				radius: 5,
				fillColor: '#2563a8',
				color: '#fff',
				weight: 0.8,
				fillOpacity: 0.85
			})
				.bindPopup(`<b>${c.dong}</b><br>${c.gu} 주민센터`)
				.addTo(centerLyr)
		);

		updateMap();
		setTimeout(() => map.invalidateSize(), 150);
	});

	onDestroy(() => map?.remove());

	function updateMap() {
		if (!map || !L) return;
		// 토글
		[
			[mktLyr, showMkt],
			[supLyr, showSup],
			[bankLyr, showBank],
			[centerLyr, showCenter]
		].forEach(([lyr, on]) => {
			if (!lyr) return;
			if (on && !lyr._map) lyr.addTo(map);
			else if (!on && lyr._map) map.removeLayer(lyr);
		});

		// 반경 / 선택 마커
		radLyr.clearLayers();
		if (cMark) {
			map.removeLayer(cMark);
			cMark = null;
		}
		const d = ALL_DONG_DATA[cD];
		if (!d || !d.lat) return;
		cMark = L.circleMarker([d.lat, d.lng], {
			radius: 10,
			fillColor: '#2c2c2a',
			color: '#fff',
			weight: 2.5,
			fillOpacity: 1
		})
			.bindPopup(`<b>${d.name}</b><br>65세+ ${d.elder.toLocaleString()}명`)
			.addTo(map);
		map.panTo([d.lat, d.lng]);

		const w = WS[cW];
		const r = w.speed * cT * 60;
		L.circle([d.lat, d.lng], {
			radius: r,
			color: w.color,
			weight: 2,
			fill: true,
			fillColor: w.color,
			fillOpacity: 0.07
		})
			.bindTooltip(`${w.label} ${Math.round(r).toLocaleString()}m`)
			.addTo(radLyr);
	}

	// 컨트롤 상태 변경 시 지도 업데이트
	$effect(() => {
		// 의존성 추적
		showMkt;
		showSup;
		showBank;
		showCenter;
		cD;
		cW;
		cT;
		if (map) updateMap();
	});

	// ══════════════════════════════════════════════
	// Chart.js
	// ══════════════════════════════════════════════
	/** @type {any} */
	let Chart;
	let gcChart, wcChart, bankChart;
	let gcCanvas = $state();
	let wcCanvas = $state();
	let bankCanvas = $state();

	onMount(async () => {
		const mod = await import('chart.js/auto');
		Chart = mod.default;
		renderBankChart();
		renderGc();
		renderWc();
	});

	onDestroy(() => {
		gcChart?.destroy();
		wcChart?.destroy();
		bankChart?.destroy();
	});

	function renderGc() {
		if (!Chart || !gcCanvas) return;
		const w = WS[cW];
		const rows = Object.entries(DONG_REACH)
			.filter(([, v]) => v['구'] === cG)
			.map(([, v]) => {
				const wd = v[w.id] || {};
				return { dong: v['동'], mkt: wd.mkt || 0, sup: wd.sup || 0 };
			})
			.sort((a, b) => b.mkt + b.sup - (a.mkt + a.sup));
		const sel = (cD.split('_')[1] || '');
		gcChart?.destroy();
		gcChart = new Chart(gcCanvas, {
			type: 'bar',
			data: {
				labels: rows.map((r) => r.dong),
				datasets: [
					{
						label: '전통시장',
						data: rows.map((r) => r.mkt),
						backgroundColor: rows.map((r) => (r.dong === sel ? '#1D9E75' : '#1D9E7540')),
						stack: 'a'
					},
					{
						label: '슈퍼마켓',
						data: rows.map((r) => r.sup),
						backgroundColor: rows.map((r) => (r.dong === sel ? '#E8A838' : '#E8A83840')),
						stack: 'a'
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				indexAxis: 'y',
				animation: false,
				plugins: { legend: { labels: { font: { size: 11 }, boxWidth: 12 } } },
				scales: {
					x: {
						stacked: true,
						beginAtZero: true,
						title: { display: true, text: '도달 시설 수', font: { size: 10 } }
					},
					y: { stacked: true, ticks: { font: { size: 9 } } }
				}
			}
		});
	}

	function renderWc() {
		if (!Chart || !wcCanvas) return;
		const mins = [15, 30];
		const ds = WS.map((w) => {
			const dr = DONG_REACH[cD];
			const wd = dr ? dr[w.id] : null;
			const base = wd ? wd.tot : 0;
			return {
				label: w.label,
				data: mins.map((m) => (m === 30 ? base : Math.round(base * (m / 30) ** 2))),
				borderColor: w.color,
				backgroundColor: w.color + '20',
				fill: true,
				tension: 0.35,
				pointRadius: 5
			};
		});
		wcChart?.destroy();
		wcChart = new Chart(wcCanvas, {
			type: 'line',
			data: { labels: ['15분', '30분'], datasets: ds },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				plugins: { legend: { labels: { font: { size: 11 }, boxWidth: 12 } } },
				scales: {
					y: {
						beginAtZero: true,
						title: { display: true, text: '도달 시설 합계', font: { size: 10 } }
					},
					x: { ticks: { font: { size: 11 } } }
				}
			}
		});
	}

	function renderBankChart() {
		if (!Chart || !bankCanvas) return;
		bankChart?.destroy();
		bankChart = new Chart(bankCanvas, {
			type: 'line',
			data: {
				labels: BANK_SERIES.years.map(String),
				datasets: [
					{
						data: BANK_SERIES.counts,
						borderColor: '#7B5EA7',
						backgroundColor: '#7B5EA715',
						fill: true,
						tension: 0.3,
						pointRadius: 2,
						pointBackgroundColor: '#7B5EA7'
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				plugins: { legend: { display: false } },
				scales: {
					y: {
						beginAtZero: false,
						ticks: { callback: (v) => v.toLocaleString(), font: { size: 10 } }
					},
					x: { ticks: { font: { size: 10 } } }
				}
			}
		});
	}

	// 차트 자동 갱신
	$effect(() => {
		cW;
		cG;
		cD;
		if (Chart && gcCanvas) renderGc();
	});
	$effect(() => {
		cW;
		cD;
		if (Chart && wcCanvas) renderWc();
	});

	// 테이블 행
	const tableRows = $derived.by(() => {
		const w = WS[cW];
		const rows = Object.entries(DONG_REACH)
			.filter(([, v]) => v['구'] === cG)
			.map(([k, v]) => {
				const wd = v[w.id] || {};
				return {
					key: k,
					dong: v['동'],
					elder: v['elder'],
					mkt: wd.mkt || 0,
					sup: wd.sup || 0,
					tot: wd.tot || 0,
					loss: wd.loss || 0
				};
			})
			.sort((a, b) => b.tot - a.tot);
		const maxTot = rows[0]?.tot || 1;
		return rows.map((r) => ({
			...r,
			access: r.tot >= maxTot * 0.6 ? '양호' : r.tot >= maxTot * 0.3 ? '보통' : '미흡',
			accessCls: r.tot >= maxTot * 0.6 ? 'phi' : r.tot >= maxTot * 0.3 ? 'pmd' : 'plo',
			lossCls: r.loss < 30 ? 'phi' : r.loss < 60 ? 'pmd' : 'plo'
		}));
	});

	const top10MaxImpact = TOP10_VULNERABLE[0]?.impact || 1;
	const top10Colors = [
		'#9B1C1C',
		'#b02020',
		'#c03030',
		'#c54040',
		'#ca5050',
		'#7c2d12',
		'#922f12',
		'#a33515',
		'#b34018',
		'#c04c20'
	];
</script>

<section class="px-6 py-10">
	<p class="hd-kicker mb-3">{meta.kicker}</p>
	<h1 class="serif-h mb-2 text-3xl" style:color={meta.accent}>{meta.title}</h1>
	<p class="mb-6 text-[13px]" style:color="var(--color-text3)">
		전통시장 195개소 · 슈퍼/식료품 31,024개소 · 은행 점포 1,579개소(실좌표) · 주민센터 426개소 ·
		서울 428개 행정동
	</p>

	<!-- ══ 컨트롤 ══ -->
	<div class="card-shell mb-4">
		<!-- 보행자 유형 -->
		<div class="ctrl-row">
			<span class="ct-label">보행자 유형</span>
			{#each WS as w, i}
				<PillButton active={cW === i} onclick={() => (cW = i)}>
					{i === 0 ? '🚶' : i === 1 ? '🧓' : i === 2 ? '🦯' : '🦽'}
					{w.label}
					{w.speed} m/s
				</PillButton>
			{/each}
			<span class="flex-1"></span>
			<span class="ct-label">보행 시간</span>
			<PillButton active={cT === 15} onclick={() => (cT = 15)}>15분</PillButton>
			<PillButton active={cT === 30} onclick={() => (cT = 30)}>30분</PillButton>
		</div>

		<!-- 시설 종류 토글 -->
		<div class="ctrl-row mt-2.5">
			<span class="ct-label">시설 종류</span>
			<button
				type="button"
				class="chk-btn"
				class:on={showMkt}
				style:--chk-color="#1D9E75"
				onclick={() => (showMkt = !showMkt)}
			>
				<span class="chk-dot"></span>전통시장
			</button>
			<button
				type="button"
				class="chk-btn"
				class:on={showSup}
				style:--chk-color="#D85A30"
				onclick={() => (showSup = !showSup)}
			>
				<span class="chk-dot"></span>슈퍼/편의점
			</button>
			<button
				type="button"
				class="chk-btn"
				class:on={showBank}
				style:--chk-color="#7B5EA7"
				onclick={() => (showBank = !showBank)}
			>
				<span class="chk-dot"></span>은행
			</button>
			<button
				type="button"
				class="chk-btn"
				class:on={showCenter}
				style:--chk-color="#2563a8"
				onclick={() => (showCenter = !showCenter)}
			>
				<span class="chk-dot"></span>주민센터
			</button>
		</div>

		<!-- 자치구 / 행정동 -->
		<div class="ctrl-row mt-2.5">
			<span class="ct-label">기준 행정동</span>
			<select class="sel" value={cG} onchange={onGuChange}>
				{#each GU_ORDER as g}
					<option value={g}>{g}</option>
				{/each}
			</select>
			<select class="sel" value={cD} onchange={onDongChange}>
				{#each dongList as d}
					<option value={d.key}>{d.dong}</option>
				{/each}
			</select>
			<span class="text-[11px]" style:color="var(--color-text3)">
				{#if currentDong}
					65세+ {currentDong.elder.toLocaleString()}명 · centroid({currentDong.lat?.toFixed(4)}, {currentDong.lng?.toFixed(
						4
					)})
				{:else}
					행정동 centroid 기준
				{/if}
			</span>
		</div>
	</div>

	<!-- ══ 통계 4열 ══ -->
	<StatGrid class="mb-4">
		<StatCard
			label="전통시장 도달"
			value={wReach ? wReach.mkt : '-'}
			sub={`반경 ${radiusM.toLocaleString()}m (${cT}분)`}
			tone="green"
		/>
		<StatCard
			label="슈퍼마켓 도달"
			value={wReach ? wReach.sup : '-'}
			sub="행정동 centroid 기준"
			tone="orange"
		/>
		<StatCard
			label="합계 / 손실률"
			value={wReach ? `${wReach.tot} / ${wReach.loss}%` : '-'}
			sub="일반인 대비 접근성 손실"
			tone="red"
		/>
		<StatCard
			label="65세+ / 주민센터"
			value={`${currentDong ? currentDong.elder.toLocaleString() : '-'}명`}
			sub={`${cG} 주민센터 ${CENTER_BY_GU[cG] || 0}개소`}
			tone="blue"
		/>
	</StatGrid>

	<!-- ══ 지도 ══ -->
	<Card title="서울시 생활 인프라 분포 — 행정동 단위" class="mb-4">
		<MapShell
			height="460px"
			legend={[
				{ color: '#1D9E75', label: '상설장', shape: 'circle' },
				{ color: '#185FA5', label: '정기장', shape: 'circle' },
				{ color: '#E8A838', label: '슈퍼마켓', shape: 'circle' },
				{ color: '#D85A30', label: '편의점', shape: 'circle' },
				{ color: '#7B5EA7', label: '은행(실좌표)', shape: 'circle' },
				{ color: '#2563a8', label: '주민센터', shape: 'circle' }
			]}
			source="출처: 소상공인시장진흥공단 · 소상공인 상가정보 · 금융감독원 · 행정안전부 / 행정동 centroid 기준 보행반경 · 슈퍼 SUP 31,024개소 전체 중 샘플 3,000개 지도 표시"
		>
			<div bind:this={mapEl} class="absolute inset-0"></div>
		</MapShell>
	</Card>

	<!-- ══ 차트 2열 ══ -->
	<div class="r2b mb-4">
		<ChartCard title={`행정동 도달 시설 수 — ${cG}`} height="360px">
			<canvas bind:this={gcCanvas} class="block h-full w-full"></canvas>
		</ChartCard>
		<ChartCard title={`보행 시간별 도달 추이 — ${cD.split('_')[1] || ''}`} height="360px">
			<canvas bind:this={wcCanvas} class="block h-full w-full"></canvas>
		</ChartCard>
	</div>

	<!-- ══ TOP10 + 은행 시계열 ══ -->
	<div class="r2b mb-4">
		<Card title="인프라 확충 우선순위 — 영향 노인 수 TOP 10 동">
			<p class="mb-2.5 text-[11px]" style:color="var(--color-text3)">
				손실률(하위15% vs 일반인) × 65세+ 인구 = 영향받는 노인 수 · 30분 기준
			</p>
			<div class="space-y-1.5">
				{#each TOP10_VULNERABLE as d, i}
					{@const pct = Math.round((d.impact / top10MaxImpact) * 100)}
					{@const lossColor = d.loss > 80 ? '#9B1C1C' : d.loss > 60 ? '#D85A30' : '#854f0b'}
					<div class="t10r">
						<div class="t10l" title={`${d['구']} ${d['동']}`}>
							{d['구']} <b>{d['동']}</b>
						</div>
						<div class="t10bg">
							<div
								class="t10bar"
								style:width="{pct}%"
								style:background={top10Colors[i]}
							></div>
						</div>
						<div class="t10v">{d.impact.toLocaleString()}명</div>
						<div
							class="t10loss"
							style:background="{lossColor}18"
							style:color={lossColor}
						>
							{d.loss}%
						</div>
					</div>
				{/each}
			</div>
			<p class="mt-2.5 text-[11px]" style:color="var(--color-text3)">
				방법론: 행정동 centroid 기준 30분 보행반경 내 POI 카운트 · OSM 직선거리 근사<br />
				출처: 통계청 등록인구 2025.4Q
			</p>
		</Card>

		<Card title="서울 은행 점포 감소 1995→2024">
			<div class="bstats">
				<div class="bst">
					<div class="bst-n" style:color="#185FA5">2,691</div>
					<div class="bst-l">1997년 피크</div>
				</div>
				<div class="bst">
					<div class="bst-n" style:color="#9B1C1C">1,686</div>
					<div class="bst-l">2024년 현재</div>
				</div>
				<div class="bst">
					<div class="bst-n" style:color="#D85A30">▼37.3%</div>
					<div class="bst-l">피크 대비 감소</div>
				</div>
			</div>
			<div class="mt-3 h-[220px] relative">
				<canvas bind:this={bankCanvas} class="block h-full w-full"></canvas>
			</div>
			<p class="mt-2.5 text-[11px]" style:color="var(--color-text3)">
				출처: 금융감독원 주요금융기관별 점포수 · 일반+특수은행 서울 합산(실데이터)
			</p>
		</Card>
	</div>

	<!-- ══ 상세 테이블 ══ -->
	<Card title={`서울 행정동 생활인프라 접근성 — ${currentW.label} · ${cG} 행정동`}>
		<div class="tbl-wrap">
			<table>
				<thead>
					<tr>
						<th>행정동</th>
						<th>65세+</th>
						<th>전통시장</th>
						<th>슈퍼</th>
						<th>합계</th>
						<th>손실률</th>
						<th>접근성</th>
					</tr>
				</thead>
				<tbody>
					{#each tableRows as r}
						<tr class:hl={r.key === cD}>
							<td>{r.dong}</td>
							<td>{r.elder.toLocaleString()}</td>
							<td>{r.mkt}</td>
							<td>{r.sup}</td>
							<td>{r.tot}</td>
							<td><span class="pill {r.lossCls}">{r.loss}%</span></td>
							<td><span class="pill {r.accessCls}">{r.access}</span></td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</Card>

	<Note tone="cool" class="mt-4">
		<b>방법론:</b> 보행자 유형(일반/노인/보조/하위15%)과 시간(15·30분)에 따라
		행정동 centroid에서 도달 가능한 시설 수를 직선거리로 근사 카운트합니다.
		손실률 = 1 − (해당 보행자 도달 / 일반인 도달).
	</Note>
</section>

<style>
	/* ── 컨트롤 row ── */
	.ctrl-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}
	.sel {
		font-size: 12px;
		padding: 4px 10px;
		border-radius: 6px;
		border: 0.5px solid var(--color-border);
		background: #fff;
		color: var(--color-text);
		font-family: inherit;
	}

	/* ── 시설 토글 (chk-btn) ── */
	.chk-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		padding: 5px 12px;
		border-radius: 6px;
		border: 0.5px solid var(--color-border);
		background: #fff;
		color: var(--color-text2);
		cursor: pointer;
		transition: all 0.14s;
		font-family: inherit;
	}
	.chk-btn:hover {
		border-color: var(--color-text3);
	}
	.chk-btn .chk-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--color-border);
		flex-shrink: 0;
	}
	.chk-btn.on {
		border-color: var(--chk-color);
		background: color-mix(in srgb, var(--chk-color) 10%, white);
		color: var(--color-text);
	}
	.chk-btn.on .chk-dot {
		background: var(--chk-color);
	}

	/* ── 차트 2열 ── */
	.r2b {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	@media (max-width: 980px) {
		.r2b {
			grid-template-columns: 1fr;
		}
	}

	/* ── TOP10 ── */
	.t10r {
		display: grid;
		grid-template-columns: 130px 1fr 80px 50px;
		align-items: center;
		gap: 8px;
		font-size: 12px;
	}
	.t10l {
		color: var(--color-text2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.t10l b {
		color: var(--color-text);
		font-weight: 500;
	}
	.t10bg {
		height: 16px;
		border-radius: 3px;
		background: var(--color-border-soft);
		overflow: hidden;
	}
	.t10bar {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s;
	}
	.t10v {
		font-family: var(--font-mono);
		text-align: right;
		font-size: 11px;
		color: var(--color-text2);
	}
	.t10loss {
		font-size: 11px;
		text-align: center;
		padding: 2px 0;
		border-radius: 3px;
		font-weight: 500;
	}

	/* ── 은행 stats ── */
	.bstats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 8px;
	}
	.bst {
		text-align: center;
		padding: 8px;
		background: var(--color-card-soft);
		border-radius: 6px;
	}
	.bst-n {
		font-family: var(--font-mono);
		font-size: 22px;
		font-weight: 500;
		line-height: 1.2;
	}
	.bst-l {
		font-size: 10px;
		color: var(--color-text3);
		margin-top: 2px;
	}

	/* ── 테이블 ── */
	.tbl-wrap {
		max-height: 460px;
		overflow-y: auto;
	}
	table {
		width: 100%;
		font-size: 12px;
		border-collapse: collapse;
	}
	thead {
		position: sticky;
		top: 0;
		background: #fff;
		z-index: 1;
	}
	th {
		text-align: left;
		font-weight: 500;
		font-size: 11px;
		color: var(--color-text3);
		padding: 8px 10px;
		border-bottom: 0.5px solid var(--color-border);
		white-space: nowrap;
	}
	td {
		padding: 7px 10px;
		border-bottom: 0.5px solid var(--color-border-soft);
	}
	tr:hover td {
		background: #fafaf8;
	}
	tr.hl td {
		background: var(--color-bg2);
		font-weight: 500;
	}
	.pill {
		display: inline-block;
		font-size: 11px;
		padding: 1px 8px;
		border-radius: 10px;
		font-weight: 500;
	}
	.pill.phi {
		background: #1d9e7518;
		color: #1d9e75;
	}
	.pill.pmd {
		background: #d85a3018;
		color: #d85a30;
	}
	.pill.plo {
		background: #9b1c1c18;
		color: #9b1c1c;
	}

	/* ── kicker ── */
	.hd-kicker {
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		color: var(--color-text3);
		text-transform: uppercase;
	}
	.serif-h {
		font-family: var(--font-serif);
		font-weight: 500;
	}

	/* ── select tweaks ── */
	select.sel:focus {
		outline: none;
		border-color: var(--color-text2);
	}
</style>
