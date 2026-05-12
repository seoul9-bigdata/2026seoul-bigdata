<script>
	import { base } from '$app/paths';
	import { ROUTES } from '$lib/nav.js';
	import CountUp from '$lib/components/CountUp.svelte';
	import { viewport } from '$lib/actions/viewport.js';

	const domains = ROUTES.filter((r) => r.kind === 'domain');

	/** 도메인별 한 줄 설명 (메인 카드 부제) */
	const domainBlurb = {
		transit: '환승·정류장·OD 흐름 진단',
		climate: '폭염쉼터·한파쉼터·결빙위험구역',
		infra: '시장·마트·약국 도달성',
		bokji: '경로당·복지관·공원 분포',
		medical: '병의원·약국 접근성'
	};

	/**
	 * Hero 영역 핵심 수치
	 * dual 타입: 두 수치를 나란히 표시 (일반 노인 vs 보행보조기 노인)
	 */
	const heroStats = [
		{
			dual: [
				{ num: 1.12, decimals: 2, unit: 'm/s', label: '일반 노인', color: 'var(--color-text)' },
				{
					num: 0.88,
					decimals: 2,
					unit: 'm/s',
					label: '보행보조기 노인',
					color: 'var(--color-accent)'
				}
			],
			header: '노인 보행속도'
		},
		{
			dual: [
				{ num: 76.7, decimals: 1, unit: '개', label: '일반 노인 도달 구역', color: 'var(--color-blue)' },
				{
					num: 46.9,
					decimals: 1,
					unit: '개',
					label: '보행보조기 노인 도달 구역',
					color: 'var(--color-accent)'
				}
			],
			header: '일반인 100 기준'
		},
		{
			dual: [
				{ num: 20.7, decimals: 1, unit: '%', label: '2026년 서울 고령화율', color: 'var(--color-text)' },
				{
					num: 29.1,
					decimals: 1,
					unit: '%',
					label: '2040년 서울 고령화율',
					color: 'var(--color-accent)'
				}
			],
			header: '서울 고령화 추이'
		},
		{
			dual: [
				{ num: 1, decimals: 0, unit: '축', label: '교통 심층 분석', color: 'var(--color-blue)' },
				{
					num: 4,
					decimals: 0,
					unit: '축',
					label: '기후·인프라·복지·의료',
					color: 'var(--color-accent)'
				}
			],
			header: '분석 구조'
		}
	];
</script>

<section class="mx-auto max-w-[1340px] px-[18px] pb-[16px] pt-8">
	<!-- ── HERO ── -->
	<div class="card-shell relative mb-3.5 overflow-hidden px-7 py-10">
		<!-- 배경 글로우 -->
		<div
			class="pointer-events-none absolute -right-24 -top-24 h-[360px] w-[360px] rounded-full"
			style:background="radial-gradient(circle, rgba(216,90,48,0.10), transparent 65%)"
		></div>
		<div
			class="pointer-events-none absolute -bottom-16 -left-16 h-[260px] w-[260px] rounded-full"
			style:background="radial-gradient(circle, rgba(90,173,255,0.07), transparent 65%)"
		></div>

		<p class="kicker mb-4" style:color="var(--color-accent)" style:opacity="0.8">
			2026 Seoul Big-Data Visualization · 시각화 부문
		</p>

		<h1
			class="mb-4 text-[34px] leading-[1.22] sm:text-[46px]"
			style:font-family="var(--font-display)"
			style:color="var(--color-text)"
		>
			노인의 발이 그리는<br />
			<span style:color="var(--color-accent)">서울의 경계</span>
		</h1>

		<p class="mb-7 max-w-[640px] text-[13.5px] leading-[1.85]" style:color="var(--color-text2)">
			서울시가 내건 <span class="font-medium" style:color="var(--color-text)">30분 보행일상권</span>.
			그 기준은 <span class="font-medium" style:color="var(--color-text)">청장년(1.28&nbsp;m/s)</span>의 걸음으로 설계되어 있습니다.<br />
			일반 노인(<span class="font-medium" style:color="var(--color-blue)">1.12&nbsp;m/s</span>)은 같은 시간에
			청년 도달 구역의 <span class="font-semibold" style:color="var(--color-blue)">76.7%</span>를,
			보행보조기를 사용하는 노인(<span class="font-medium" style:color="var(--color-accent)">0.88&nbsp;m/s</span>)은
			<span class="font-semibold" style:color="var(--color-accent)">46.9%</span>를 이동할 수 있습니다.<br />
			교통 심층 분석 1축과 기후·인프라·복지·의료 도달 분석 4축으로, 서울 노인의 보행 생활권 격차를 들여다봅니다.
		</p>

		<!-- 핵심 수치 -->
		<div class="grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
			{#each heroStats as s, i}
				<div
					class="hero-stat border-l-2 pl-4"
					style:border-color="rgba(216,90,48,0.32)"
					style:--ad="{i * 90}ms"
				>
					{#if s.dual}
						<!-- 이중 수치 (일반 노인 vs 보행보조기 노인) -->
						<div
							class="mb-1.5 text-[9.5px] font-medium uppercase tracking-widest"
							style:color="var(--color-text4)"
						>
							{s.header}
						</div>
						{#each s.dual as d, j}
							<div class="flex items-baseline gap-0 {j > 0 ? 'mt-[5px]' : ''}">
								<div
									class="font-mono text-[20px] font-semibold leading-none tabular-nums sm:text-[22px]"
									style:color={d.color}
								>
									<CountUp value={d.num} decimals={d.decimals} />
									<span
										class="ml-[2px] text-[0.38em] font-normal"
										style:color={d.color}
										style:opacity="0.75"
									>
										{d.unit}
									</span>
								</div>
							</div>
							<div
								class="text-[10px] leading-tight"
								style:color={d.color}
								style:opacity={j === 0 ? '0.55' : '0.75'}
							>
								{d.label}
							</div>
						{/each}
					{:else}
						<!-- 단일 수치 -->
						<div
							class="font-mono text-[26px] font-medium leading-none tabular-nums sm:text-[30px]"
							style:color="var(--color-text)"
						>
							<CountUp value={s.num} decimals={s.decimals} />
							<span class="ml-[3px] text-[0.42em] font-normal" style:color="var(--color-accent)">
								{s.unit}
							</span>
						</div>
						<div class="mt-1.5 text-[11px]" style:color="var(--color-text3)">{s.label}</div>
					{/if}
				</div>
			{/each}
		</div>
	</div>

</section>

<style>
	.hero-stat {
		animation: stat-reveal 0.7s cubic-bezier(0.16, 0.84, 0.36, 1) both;
		animation-delay: var(--ad, 0ms);
	}
	@keyframes stat-reveal {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.hero-stat {
			animation: none;
		}
	}
</style>
