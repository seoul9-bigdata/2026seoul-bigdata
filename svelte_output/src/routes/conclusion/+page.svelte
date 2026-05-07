<script>
	import { base } from '$app/paths';
	import Card from '$lib/components/Card.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import Note from '$lib/components/Note.svelte';

	/* ────────────────────────────────────────────────────────────
	 *  4개 도메인 결론 CSV 데이터 (final_output/ENSEMBLE/conclusion-csv/)
	 *  컬럼: 점수_노인_경사X, 점수_노인_경사O,
	 *        점수_보행보조_경사X, 점수_보행보조_경사O,
	 *        점수_하위15_경사X, 점수_하위15_경사O
	 *  본 페이지는 "일반 노인(1.12 m/s) · 경사 미보정" 기준만 사용 → 점수_노인_경사X
	 *  YOO 교통 도메인은 결론 CSV가 아직 없음 → 본 페이지에서는 4개 도메인만 결합
	 * ──────────────────────────────────────────────────────────── */

	/** [기후, 인프라, 복지, 의료] — 일반 노인(경사 미보정) 점수 */
	const SCORES = {
		종로구:    [75.6, 75.3, 77.6, 68.9],
		중구:      [76.7, 77.8, 75.2, 77.7],
		용산구:    [76.6, 77.6, 74.9, 74.1],
		성동구:    [77.1, 72.9, 77.8, 76.0],
		광진구:    [77.4, 78.5, 74.1, 79.7],
		동대문구:  [72.3, 75.7, 71.9, 75.9],
		중랑구:    [76.9, 80.2, 76.8, 76.6],
		성북구:    [76.9, 77.1, 69.9, 77.7],
		강북구:    [76.1, 79.9, 72.9, 76.7],
		도봉구:    [77.8, 75.5, 76.4, 72.3],
		노원구:    [76.0, 76.2, 75.9, 75.6],
		은평구:    [80.8, 82.9, 75.8, 75.8],
		서대문구:  [77.6, 75.7, 75.6, 74.5],
		마포구:    [78.1, 79.9, 70.3, 74.9],
		양천구:    [81.6, 78.8, 81.7, 77.2],
		강서구:    [76.2, 80.1, 77.9, 77.5],
		구로구:    [76.2, 78.9, 78.3, 74.4],
		금천구:    [80.2, 81.3, 82.7, 78.2],
		영등포구:  [77.0, 77.5, 75.6, 75.8],
		동작구:    [76.0, 78.1, 82.5, 70.9],
		관악구:    [76.6, 74.8, 71.1, 71.4],
		서초구:    [76.9, 75.6, 84.1, 75.3],
		강남구:    [76.1, 76.4, 68.6, 72.7],
		송파구:    [77.8, 78.9, 80.7, 78.1],
		강동구:    [79.9, 83.3, 76.0, 79.2]
	};

	const DOMAINS = [
		{ key: 'climate', label: '기후',     emoji: '🌡️', color: '#555452', accent: 'var(--color-amber)' },
		{ key: 'infra',   label: '인프라',   emoji: '🏪', color: '#D85A30', accent: 'var(--color-accent)' },
		{ key: 'bokji',   label: '복지',     emoji: '🌳', color: '#7B5EA7', accent: 'var(--color-purple)' },
		{ key: 'medical', label: '의료',     emoji: '🏥', color: '#185FA5', accent: 'var(--color-blue)' }
	];

	/** 종합 점수 = 4개 도메인 평균 */
	const ranked = Object.entries(SCORES)
		.map(([name, arr]) => {
			const avg = arr.reduce((s, v) => s + v, 0) / arr.length;
			return {
				name,
				climate: arr[0],
				infra:   arr[1],
				bokji:   arr[2],
				medical: arr[3],
				composite: +avg.toFixed(1),
				min: Math.min(...arr),
				max: Math.max(...arr),
				weakest: DOMAINS[arr.indexOf(Math.min(...arr))]
			};
		})
		.sort((a, b) => b.composite - a.composite)
		.map((d, i) => ({ ...d, rank: i + 1 }));

	const seoulAvg = +(
		ranked.reduce((s, d) => s + d.composite, 0) / ranked.length
	).toFixed(1);
	const best = ranked[0];
	const worst = ranked[ranked.length - 1];

	/** 도메인별 서울 평균 */
	const domainAvg = DOMAINS.map((d, idx) => {
		const key = ['climate', 'infra', 'bokji', 'medical'][idx];
		const v = ranked.reduce((s, r) => s + r[key], 0) / ranked.length;
		return { ...d, avg: +v.toFixed(1) };
	});

	/** 점수 색상 (conclusion_ver2 와 동일 5단계) */
	function scoreColor(s) {
		if (s < 50) return '#9B1C1C';
		if (s < 58) return '#D85A30';
		if (s < 65) return '#f5b740';
		if (s < 73) return '#1D9E75';
		return '#0f6e56';
	}
	function scoreBg(s) {
		if (s < 50) return '#fde8e8';
		if (s < 58) return '#fdecd9';
		if (s < 65) return '#fef3cd';
		if (s < 73) return '#dcf3ea';
		return '#d1ede0';
	}

	/** 정책 제안 — 도메인별 최취약 구 자동 추출 */
	const policySuggestions = DOMAINS.map((d, idx) => {
		const key = ['climate', 'infra', 'bokji', 'medical'][idx];
		const sorted = [...ranked].sort((a, b) => a[key] - b[key]);
		const bottom3 = sorted.slice(0, 3);
		return { ...d, key, bottom3 };
	});

	/* ── 보행보조 노인 / 일반 노인 손실 비교 (기후 CSV 평균 기준) ── */
	// 평균 일반 노인(경사X) vs 평균 보행보조(경사X) — 기후 CSV: 노인 76.7 → 보조 47.0 (대표 격차 시각화)
	const speedComparison = [
		{ label: '일반인',           score: 100, color: '#4a9eff', emoji: '🚶', desc: '기준선' },
		{ label: '일반 노인',        score: 77,  color: '#1D9E75', emoji: '🧓', desc: '평균' },
		{ label: '보행보조 노인',    score: 47,  color: '#f5b740', emoji: '🦯', desc: '−53%' },
		{ label: '보행보조 하위 15%', score: 30, color: '#ef5555', emoji: '🦽', desc: '−70%' }
	];

	/** 정렬 모드 */
	let sortKey = $state('composite');
	const sortedTable = $derived(
		[...ranked].sort((a, b) => {
			if (sortKey === 'name') return a.name.localeCompare(b.name);
			return b[sortKey] - a[sortKey];
		})
	);
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
			class="mb-4 font-serif text-[34px] font-light leading-[1.2] sm:text-[44px]"
			style:color="var(--color-text)"
		>
			서울 25개 구,<br />
			<span style:color="var(--color-accent)">노인 도보 생활권</span> 종합 성적표
		</h1>

		<p class="mb-7 max-w-[640px] text-[13.5px] leading-[1.85]" style:color="var(--color-text2)">
			기후·인프라·복지·의료 4개 도메인 도달가능 점수를 결합한 25개 자치구 종합 진단.<br />
			일반 노인(1.12&nbsp;m/s) 기준, 경사 미보정 점수.
		</p>

		<StatGrid class="sm:grid-cols-4" cols={4}>
			<StatCard label="분석 도메인" value="4개" sub="기후·인프라·복지·의료" />
			<StatCard label="서울 평균 종합 점수" value="{seoulAvg}" sub="점 (0~100)" tone="orange" />
			<StatCard label="최양호 구" value={best.name} sub="{best.composite}점" tone="green" />
			<StatCard label="최취약 구" value={worst.name} sub="{worst.composite}점" tone="red" />
		</StatGrid>
	</div>

	<!-- ── 보행 속도별 손실 비교 ── -->
	<Card title="속도별 손실 · 일반인 대비 평균 도달가능 점수" class="mb-3.5">
		<p class="mb-4 text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
			보행속도가 떨어질수록 시설 도달 노드가 급감한다. 본 페이지의 표·랭킹은 <strong>일반 노인 1.12&nbsp;m/s</strong>를 기준으로 한다.
		</p>
		<div class="space-y-2.5">
			{#each speedComparison as s}
				<div class="grid grid-cols-[140px_1fr_60px] items-center gap-3">
					<div class="flex items-center gap-1.5">
						<span class="text-[14px]">{s.emoji}</span>
						<span class="text-[12.5px] font-medium" style:color="var(--color-text)">{s.label}</span>
					</div>
					<div class="relative h-[18px] rounded-[4px]" style:background="var(--color-card-soft)">
						<div
							class="h-full rounded-[4px] transition-all duration-500"
							style:width="{s.score}%"
							style:background={s.color}
							style:opacity="0.85"
						></div>
						<span
							class="absolute right-2 top-1/2 -translate-y-1/2 font-mono text-[10.5px]"
							style:color="var(--color-text3)"
						>
							{s.desc}
						</span>
					</div>
					<div
						class="text-right font-mono text-[13px] font-medium tabular-nums"
						style:color={s.color}
					>
						{s.score}점
					</div>
				</div>
			{/each}
		</div>
	</Card>

	<!-- ── 도메인 평균 ── -->
	<Card title="도메인별 서울 전체 평균 · 일반 노인 기준" class="mb-3.5">
		<div class="grid gap-2.5 sm:grid-cols-2 md:grid-cols-4">
			{#each domainAvg as d}
				<div
					class="rounded-[8px] p-4 transition-shadow hover:shadow-[0_2px_10px_rgba(0,0,0,0.04)]"
					style:background="var(--color-card-soft)"
					style:border="0.5px solid {d.color}22"
				>
					<div class="mb-1 text-[20px]">{d.emoji}</div>
					<div class="text-[11px]" style:color="var(--color-text3)">{d.label} 도메인 평균</div>
					<div class="mt-1 font-mono text-[26px] font-medium leading-none tabular-nums" style:color={d.color}>
						{d.avg}
					</div>
					<div class="mt-0.5 text-[10.5px]" style:color="var(--color-text3)">점 (0~100)</div>
				</div>
			{/each}
		</div>
	</Card>

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
				하위 5개 구는 4개 도메인 평균이 서울 평균({seoulAvg}점)에 못 미친다. 도메인별 가장 약한 축이 어디인가에 따라 정책 우선순위가 달라진다 (아래 정책 제안 표 참고).
			</Note>
		</Card>
	</div>

	<!-- ── 25구 상세 데이터 테이블 ── -->
	<Card title="전체 25개 구 상세 점수 · 일반 노인 1.12 m/s · 경사 미보정" class="mb-3.5">
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
					{#each sortedTable as d (d.name)}
						<tr style:border-bottom="0.5px solid var(--color-border-soft)">
							<td class="px-3 py-2 font-mono tabular-nums" style:color="var(--color-text3)">
								{d.rank}
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
			* 도메인 점수 = (일반 노인 도달 노드 수 / 일반인 도달 노드 수) × 100. 기준 시간 30분 고정.<br />
			** 종합 점수 = 4개 도메인 산술 평균. 본 페이지는 경사 미보정 기준이며, 경사 보정 적용 시 강북·도봉·관악·성북 등 가파른 구는 추가 하락한다.<br />
			*** 교통·이동 도메인은 결론 CSV가 별도 분석 단계에 있어 본 종합 점수에서 제외됨 (도메인 페이지 별도 진단).
		</p>
	</Card>

	<!-- ── 정책 제안 ── -->
	<Card title="정책 제안 · 도메인별 우선 투입 자치구" class="mb-3.5">
		<h2 class="mb-2 font-serif text-[22px] font-medium leading-[1.3]" style:color="var(--color-text)">
			같은 예산이면 어디부터 — 도메인별 최취약 3개 구
		</h2>
		<p class="mb-4 text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
			종합 점수가 평균 이상이라도 특정 도메인이 약한 구가 있다. 4개 도메인 각각의 하위 3개 구를 제시한다.
			같은 노인 인구라도 어느 축이 무너졌는지에 따라 처방이 달라진다.
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
							무더위·한파쉼터 추가 배치, 정류장 100m 내 쉼터 연계, 그늘막·보행쉘터 보강.
						{:else if p.key === 'infra'}
							전통시장·약국·생활편의 시설 보행 접근성 개선, 보행 네트워크 연속성 확보.
						{:else if p.key === 'bokji'}
							경로당·노인복지관 신설 또는 이전, 공원·녹지 보행로 정비.
						{:else if p.key === 'medical'}
							1차 진료기관·보건소 접근성 보완, 응급 도달 사각지대 해소 (방문 의료·셔틀).
						{/if}
					</p>
				</div>
			{/each}
		</div>
	</Card>

	<!-- ── 종합 결론 ── -->
	<Card title="결론 · 분(分)의 격차" class="mb-3.5">
		<div class="grid gap-3 md:grid-cols-3">
			<div>
				<div class="kicker mb-1.5">발견 1 · 종합 격차</div>
				<p class="text-[12.5px] leading-[1.75]" style:color="var(--color-text2)">
					최양호({best.name} {best.composite}점) ↔ 최취약({worst.name} {worst.composite}점) 사이의 종합 격차는
					<strong style:color="var(--color-accent)">
						{(best.composite - worst.composite).toFixed(1)}점
					</strong>.
					같은 서울 안에서 4개 축 평균 도달가능성이 가시적인 차이로 갈린다.
				</p>
			</div>
			<div>
				<div class="kicker mb-1.5">발견 2 · 보행보조 시 절벽</div>
				<p class="text-[12.5px] leading-[1.75]" style:color="var(--color-text2)">
					일반 노인 평균 77점이 보행보조 노인 기준에서는 <strong style:color="var(--color-accent)">47점</strong>으로 떨어진다.
					기준 보행속도 0.24&nbsp;m/s 차이가 도달 노드 수의 절반을 잘라낸다.
				</p>
			</div>
			<div>
				<div class="kicker mb-1.5">발견 3 · 도메인 비대칭</div>
				<p class="text-[12.5px] leading-[1.75]" style:color="var(--color-text2)">
					같은 자치구라도 도메인별 점수는 비대칭이다. 종합 점수만으로는 보이지 않는 약한 축(기후/인프라/복지/의료)이 정책의 진짜 진입점이다.
				</p>
			</div>
		</div>

		<Note tone="warm" class="mt-4">
			<strong>다음 분석 → 경사 보정.</strong>
			Tobler's Hiking Function 기반 경사 감쇄를 적용하면 강북·도봉·관악·성북 등 구도심 가파른 구의 실질 도달가능성은 추가로 하락한다.
			도메인별 페이지에서 경사 보정 토글을 확인할 수 있다 (확인 필요 — 도메인 페이지 작업 진행 중).
		</Note>
	</Card>

	<!-- ── 다음 / 처음으로 ── -->
	<div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
		<a
			href="{base}/"
			class="card-shell group flex items-center gap-4 no-underline transition-colors hover:border-[var(--color-accent)]"
		>
			<div class="text-[22px]">🌌</div>
			<div class="flex-1">
				<div class="kicker mb-0.5">처음으로 ←</div>
				<div class="text-[14px] font-medium" style:color="var(--color-text)">메인 허브로 돌아가기</div>
				<div class="text-[12px]" style:color="var(--color-text3)">5축 도메인 카드 다시 보기</div>
			</div>
		</a>
		<a
			href="{base}/introduce"
			class="card-shell group flex items-center gap-4 no-underline transition-colors hover:border-[var(--color-accent)]"
		>
			<div class="text-[22px]" style:color="var(--color-gold)">✨</div>
			<div class="flex-1">
				<div class="kicker mb-0.5">서론 다시 보기 ←</div>
				<div class="text-[14px] font-medium" style:color="var(--color-text)">왜 노인 도보 생활권인가</div>
				<div class="text-[12px]" style:color="var(--color-text3)">2040 인구 변화 + 4종 보행 속도 기준</div>
			</div>
		</a>
	</div>
</section>
