<script>
	import { base } from '$app/paths';
	import { ROUTES } from '$lib/nav.js';
	import Card from '$lib/components/Card.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import Note from '$lib/components/Note.svelte';

	const domains = ROUTES.filter((r) => r.kind === 'domain');

	/**
	 * 2026 / 2040 자치구별 고령화율 (%) — introduce_ver2.html 동일 데이터
	 * 출처: 서울시 자치구별장래인구추계, 2024.12 발표
	 */
	const AGING_2026 = {
		강남구: 17.8, 강동구: 19.3, 강북구: 26.2, 강서구: 20.8, 관악구: 19.2,
		광진구: 18.7, 구로구: 23.5, 금천구: 23.2, 노원구: 21.9, 도봉구: 26.3,
		동대문구: 20.2, 동작구: 20.4, 마포구: 16.9, 서대문구: 19.9, 서초구: 17.4,
		성동구: 19.1, 성북구: 20.1, 송파구: 18.8, 양천구: 20.4, 영등포구: 20.4,
		용산구: 18.3, 은평구: 22.9, 종로구: 20.5, 중구: 21.8, 중랑구: 23.3
	};
	const AGING_2040 = {
		강남구: 27.4, 강동구: 31.2, 강북구: 34.3, 강서구: 28.8, 관악구: 25.7,
		광진구: 26.4, 구로구: 33.6, 금천구: 33.3, 노원구: 31.2, 도봉구: 36.0,
		동대문구: 27.7, 동작구: 27.5, 마포구: 23.8, 서대문구: 27.9, 서초구: 24.7,
		성동구: 25.1, 성북구: 28.0, 송파구: 27.5, 양천구: 30.1, 영등포구: 28.6,
		용산구: 24.1, 은평구: 32.8, 종로구: 27.6, 중구: 30.3, 중랑구: 32.9
	};

	/** 4종 보행 유형 — introduce_ver2.html 동일 (출처 한음 외 2020) */
	const SPEEDS = [
		{ label: '일반인',           mps: 1.28, color: '#4a9eff', emoji: '🚶', score: 100, note: '기준선' },
		{ label: '일반 노인',        mps: 1.12, color: '#1D9E75', emoji: '🧓', score: 77,  note: '평균' },
		{ label: '보행보조 노인',    mps: 0.88, color: '#f5b740', emoji: '🦯', score: 47,  note: '−53%' },
		{ label: '보행보조 하위 15%', mps: 0.70, color: '#ef5555', emoji: '🦽', score: 30, note: '−70%' }
	];

	/** 5축 분석 프레임 — 인트로에서 도메인 페이지 5개를 짧게 미리보기 */
	const FRAMES = [
		{ slug: 'transit',  no: '01', emoji: '🚇', title: '교통·이동',     desc: '환승 대기·정류장·OD 흐름. 노인 교통카드 trip 505K 분석.' },
		{ slug: 'climate',  no: '02', emoji: '🌡️', title: '기후 재난',     desc: '폭염·한파쉼터 100m 내 정류장·시설 연계율 진단.' },
		{ slug: 'infra',    no: '03', emoji: '🏪', title: '생활 인프라',   desc: '시장·마트·약국 등 생활 기점 도달가능 점수.' },
		{ slug: 'bokji',    no: '04', emoji: '🏛️', title: '복지·녹지',     desc: '경로당·노인복지관·공원 분포와 보행 도달성.' },
		{ slug: 'medical',  no: '05', emoji: '🏥', title: '의료 접근성',   desc: '1차 진료기관·약국·보건소 30분 도달 반경.' }
	];

	/* ── 2040 그래프용: 25구 정렬 (높은 순) ── */
	const sorted2040 = Object.entries(AGING_2040)
		.map(([name, v]) => ({
			name,
			y2040: v,
			y2026: AGING_2026[name],
			delta: +(v - AGING_2026[name]).toFixed(1)
		}))
		.sort((a, b) => b.y2040 - a.y2040);

	const max2040 = Math.max(...sorted2040.map((d) => d.y2040)); // ≈ 36.0

	/** 도시 평균 (2026 / 2040) */
	const avg2026 = (
		Object.values(AGING_2026).reduce((s, v) => s + v, 0) / 25
	).toFixed(1);
	const avg2040 = (
		Object.values(AGING_2040).reduce((s, v) => s + v, 0) / 25
	).toFixed(1);

	/** 색상 분류 (introduce_ver2 legend와 일치) */
	function colorOf(v) {
		if (v < 18) return '#fef3cd';
		if (v < 22) return '#f5b740';
		if (v < 25) return '#e87f2a';
		return '#c0391b';
	}

	/* ── 토글: 2026 / 2040 ── */
	let year = $state(2040);
	const yearData = $derived(year === 2026 ? AGING_2026 : AGING_2040);
	const yearMax = $derived(Math.max(...Object.values(yearData)));
	const yearAvg = $derived(year === 2026 ? avg2026 : avg2040);

	const sortedByYear = $derived(
		Object.entries(yearData)
			.map(([name, v]) => ({ name, value: v }))
			.sort((a, b) => b.value - a.value)
	);
</script>

<section class="mx-auto max-w-[1340px] px-[18px] pb-[60px] pt-8">
	<!-- ── HERO ── -->
	<div class="card-shell relative mb-3.5 overflow-hidden px-7 py-10">
		<div
			class="pointer-events-none absolute -right-32 -top-32 h-[420px] w-[420px] rounded-full"
			style:background="radial-gradient(circle, rgba(245,183,64,0.16), transparent 65%)"
		></div>

		<p class="kicker mb-4" style:color="var(--color-gold)">서론 · 시각화 배경</p>

		<h1
			class="mb-4 font-serif text-[34px] font-light leading-[1.2] sm:text-[44px]"
			style:color="var(--color-text)"
		>
			노인의 걸음으로<br />
			<span style:color="var(--color-accent)">좁아진 서울</span>
		</h1>

		<p class="mb-6 max-w-[640px] text-[13.5px] leading-[1.85]" style:color="var(--color-text2)">
			일반인이 30분이면 닿는 병원이, 마트가, 지하철역이 — 노인에게는 닿지 않는다.<br />
			서울 25개 자치구, 5개 분야 시설의 도보 접근성을 노인 보행속도 기준으로 진단한다.
		</p>

		<StatGrid class="sm:grid-cols-3" cols={3}>
			<StatCard label="서울 65세+ 인구 (2026)" value="194만 명" sub="자치구별장래인구추계" />
			<StatCard label="서울 고령화율 (2026 평균)" value="{avg2026}%" sub="2040 → {avg2040}%" tone="orange" />
			<StatCard label="보행보조 노인 시설 손실률" value="−53%" sub="일반인 대비 도달가능 점수" tone="red" />
		</StatGrid>
	</div>

	<!-- ── SECTION 1: 2040 노인 인구 변화 ── -->
	<Card title="현황 파악 · 서울 25개 자치구 고령화율" class="mb-3.5">
		<div class="mb-3 flex flex-wrap items-end justify-between gap-3">
			<div>
				<h2
					class="mb-1.5 font-serif text-[22px] font-medium leading-[1.3]"
					style:color="var(--color-text)"
				>
					서울, 이미 고령사회 — 2040년 초고령사회 진입
				</h2>
				<p class="text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
					서울시 노인 인구는 2026년 기준 약 194만 명. 강북·도봉 등 구도심 고령화율은 26%를 상회한다.
					2040년에는 서울 전체 평균이 28.8%까지 상승할 것으로 전망된다.
				</p>
			</div>

			<!-- 토글 -->
			<div class="inline-flex rounded-[20px] border border-[var(--color-border)] bg-white p-[3px]">
				{#each [2026, 2040] as y}
					<button
						type="button"
						class="px-4 py-1 text-[12px] font-medium transition-colors"
						style:border-radius="18px"
						style:background={year === y ? 'var(--color-dark)' : 'transparent'}
						style:color={year === y ? 'var(--color-dark-text)' : 'var(--color-text2)'}
						onclick={() => (year = y)}
					>
						{y}{y === 2040 ? ' 전망' : ''}
					</button>
				{/each}
			</div>
		</div>

		<!-- 25구 막대 그래프 -->
		<div class="mb-3 rounded-[8px] p-4" style:background="var(--color-card-soft)">
			<div class="flex flex-col gap-[5px]">
				{#each sortedByYear as d (d.name)}
					{@const w = (d.value / yearMax) * 100}
					{@const bg = colorOf(d.value)}
					<div class="grid grid-cols-[80px_1fr_60px] items-center gap-2.5">
						<div class="text-[11.5px] font-medium" style:color="var(--color-text)">{d.name}</div>
						<div class="relative h-[14px] rounded-[3px]" style:background="rgba(0,0,0,0.04)">
							<div
								class="h-full rounded-[3px] transition-all duration-500"
								style:width="{w}%"
								style:background={bg}
							></div>
						</div>
						<div
							class="text-right font-mono text-[11.5px] tabular-nums"
							style:color="var(--color-text2)"
						>
							{d.value.toFixed(1)}%
						</div>
					</div>
				{/each}
			</div>
		</div>

		<!-- 범례 -->
		<div class="flex flex-wrap items-center gap-4">
			<span class="kicker">고령화율 구간</span>
			{#each [{ c: '#fef3cd', l: '~18%' }, { c: '#f5b740', l: '18~22%' }, { c: '#e87f2a', l: '22~25%' }, { c: '#c0391b', l: '25%+' }] as l}
				<div class="flex items-center gap-1.5">
					<div class="h-3 w-3 rounded-[3px]" style:background={l.c}></div>
					<span class="text-[11px]" style:color="var(--color-text2)">{l.l}</span>
				</div>
			{/each}
		</div>

		<Note tone="cool" class="mt-3.5">
			출처 — 서울시 자치구별장래인구추계 (2024.12 발표). 2040년 도봉(36.0%)·강북(34.3%)·구로(33.6%)·금천(33.3%)·중랑(32.9%)·은평(32.8%) 6개구가 30%대 진입.
		</Note>
	</Card>

	<!-- ── SECTION 2: 4개 보행 유형 ── -->
	<Card title="분석 기준 · 4개 보행 속도 유형" class="mb-3.5">
		<h2 class="mb-1.5 font-serif text-[22px] font-medium leading-[1.3]" style:color="var(--color-text)">
			같은 30분, 4개의 다른 세상
		</h2>
		<p class="mb-4 text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
			노인의 보행속도는 단일하지 않다. 보행보조기를 쓰는 하위 15% 노인은 일반인 대비 도달 노드 수가 70% 가까이 줄어든다.
			네 가지 속도 기준으로 같은 지도 위 다른 반경을 측정한다.
		</p>

		<div class="overflow-x-auto rounded-[8px]" style:background="var(--color-card-soft)">
			<table class="w-full text-[12px]">
				<thead>
					<tr style:border-bottom="0.5px solid var(--color-border)">
						<th class="ct-label px-3 py-2.5 text-left">보행자 유형</th>
						<th class="ct-label px-3 py-2.5 text-left">보행 속도</th>
						<th class="ct-label px-3 py-2.5 text-left">30분 도달 반경</th>
						<th class="ct-label px-3 py-2.5 text-left">도달가능 점수</th>
						<th class="ct-label px-3 py-2.5 text-left">비고</th>
					</tr>
				</thead>
				<tbody>
					{#each SPEEDS as s, i}
						{@const radius = Math.round(s.mps * 60 * 30)}
						<tr style:border-bottom="0.5px solid var(--color-border-soft)">
							<td class="px-3 py-2.5">
								<span class="mr-1.5 text-[15px]">{s.emoji}</span>
								<span class="font-medium" style:color="var(--color-text)">{s.label}</span>
							</td>
							<td class="px-3 py-2.5 font-mono tabular-nums" style:color={s.color}>
								{s.mps.toFixed(2)} m/s
							</td>
							<td class="px-3 py-2.5">
								<div class="flex items-center gap-2">
									<div
										class="h-[6px] rounded-full"
										style:background={s.color}
										style:width="{(s.mps / 1.28) * 120}px"
										style:opacity={0.55 + i * 0.1}
									></div>
									<span class="font-mono text-[11.5px] tabular-nums" style:color="var(--color-text2)">
										약 {(radius / 1000).toFixed(2)} km
									</span>
								</div>
							</td>
							<td class="px-3 py-2.5">
								<span
									class="inline-block rounded-[4px] px-2 py-[3px] font-mono text-[11.5px] font-medium"
									style:background="{s.color}22"
									style:color={s.color}
								>
									{s.score}점
								</span>
							</td>
							<td class="px-3 py-2.5 text-[11.5px]" style:color="var(--color-text3)">
								{s.note}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<p class="mt-3 text-[11px] leading-[1.7]" style:color="var(--color-text3)">
			* 출처: 한음·조혜림·문성철·윤성범·박순용 (2020), 「노인보호구역 보행자녹색시간 산정을 위한 보행속도 기준 개선」, <em>한국ITS학회논문지</em> 19(4), 45–54. 서울·경기·충북 20개소 횡단보도 보행자 4,857명 실측. 보행보조장치 사용자 하위 15%는 0.70 m/s로 현행 노인보호구역 기준(0.8 m/s)보다 낮음.<br />
			** 도달가능 점수 = (해당 속도 도달 노드 수 / 일반인 도달 노드 수) × 100. 일반인 = 100점.
		</p>
	</Card>

	<!-- ── SECTION 3: 왜 노인 도보 생활권인가 (문제 정의) ── -->
	<Card title="문제 정의 · 왜 노인 도보 생활권인가" class="mb-3.5">
		<div class="grid gap-3.5 md:grid-cols-3">
			<div class="rounded-[8px] p-4" style:background="var(--color-card-soft)">
				<div class="kicker mb-2">2040 비전의 균열</div>
				<p class="text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
					서울시 2040 도시기본계획은 <strong style:color="var(--color-accent)">'도보 30분 생활권'</strong>을 핵심 비전으로 제시한다. 그러나 그 30분은 청장년 1.28&nbsp;m/s의 시간으로 설계되었다.
				</p>
			</div>
			<div class="rounded-[8px] p-4" style:background="var(--color-card-soft)">
				<div class="kicker mb-2">시간의 격차</div>
				<p class="text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
					청년이 30분에 닿는 거리를 보행보조 노인은 <strong style:color="var(--color-accent)">약 44분</strong>, 하위 15% 노인은 <strong style:color="var(--color-accent)">약 55분</strong>이 걸린다. 같은 동네 같은 지도 위 시간이 다르다.
				</p>
			</div>
			<div class="rounded-[8px] p-4" style:background="var(--color-card-soft)">
				<div class="kicker mb-2">데이터의 부재</div>
				<p class="text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
					기존 생활권 분석은 단일 보행속도와 직선거리에 의존한다. 본 분석은 OSM 보행 네트워크 + 4단계 속도 + Tobler 경사 보정으로 <strong style:color="var(--color-text)">실측 도달가능성</strong>을 정량화한다.
				</p>
			</div>
		</div>
	</Card>

	<!-- ── SECTION 4: 5축 분석 프레임 ── -->
	<Card title="분석 프레임 · 5축 도메인" class="mb-3.5">
		<h2 class="mb-1.5 font-serif text-[22px] font-medium leading-[1.3]" style:color="var(--color-text)">
			5개 축으로 다시 측정하는 서울
		</h2>
		<p class="mb-4 text-[12.5px] leading-[1.7]" style:color="var(--color-text2)">
			교통·기후·인프라·복지·의료 5개 도메인에서 같은 보행속도 기준으로 측정한다.
			각 축의 점수와 25구 분포가 결합되어 결론 페이지의 종합 진단을 구성한다.
		</p>

		<div class="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
			{#each FRAMES as f}
				<a
					href="{base}/{f.slug}"
					class="card-shell group relative block overflow-hidden no-underline transition-all duration-200 hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)]"
				>
					<span
						class="absolute inset-x-0 top-0 h-[2.5px] origin-left scale-x-0 transition-transform duration-300 group-hover:scale-x-100"
						style:background={domains.find((d) => d.slug === f.slug)?.accent ?? 'var(--color-accent)'}
					></span>
					<div class="kicker mb-1">{f.no}</div>
					<div class="mb-1.5 text-[22px] leading-none">{f.emoji}</div>
					<div class="mb-1 text-[14.5px] font-medium" style:color="var(--color-text)">
						{f.title}
					</div>
					<div class="text-[11.5px] leading-[1.55]" style:color="var(--color-text3)">
						{f.desc}
					</div>
				</a>
			{/each}
		</div>
	</Card>

</section>
