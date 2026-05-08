<script>
	import { base } from '$app/paths';
	import { ROUTES } from '$lib/nav.js';
	import CountUp from '$lib/components/CountUp.svelte';
	import { viewport } from '$lib/actions/viewport.js';

	const domains = ROUTES.filter((r) => r.kind === 'domain');

	/** 도메인별 한 줄 설명 (메인 카드 부제) */
	const domainBlurb = {
		transit: '환승·정류장·OD 흐름 진단',
		climate: '폭염·한파쉼터 접근성',
		infra: '시장·마트·약국 도달성',
		bokji: '경로당·복지관·녹지 분포',
		medical: '1차 진료·응급 도달 시간'
	};

	/** Hero 영역에 띄울 핵심 수치 */
	const heroStats = [
		{ num: 0.88, decimals: 2, unit: 'm/s', label: '보행보조 노인 평균 보행속도' },
		{ num: 44, decimals: 0, unit: '분+', label: '청년 30분 → 노인 도달 시간' },
		{ num: 32, decimals: 0, unit: '%', label: '2040 서울 노인 인구 비율' },
		{ num: 5, decimals: 0, unit: '축', label: '환승·기후·인프라·복지·의료' }
	];
</script>

<section class="mx-auto max-w-[1340px] px-[18px] pb-[60px] pt-8">
	<!-- ── HERO ── -->
	<div class="card-shell relative mb-3.5 overflow-hidden px-7 py-10">
		<!-- 옅은 액센트 글로우 (라이트 톤 유지) -->
		<div
			class="pointer-events-none absolute -right-24 -top-24 h-[360px] w-[360px] rounded-full"
			style:background="radial-gradient(circle, rgba(216,90,48,0.10), transparent 65%)"
		></div>

		<p class="kicker mb-4">2026 Seoul Big-Data Visualization · 시각화 부문</p>

		<h1
			class="mb-4 font-serif text-[34px] font-light leading-[1.22] sm:text-[46px]"
			style:color="var(--color-text)"
		>
			노인이 동네를 벗어날 때<br />
			<span style:color="var(--color-accent)">잃는 시간</span>의 지도
		</h1>

		<p class="mb-7 max-w-[640px] text-[13.5px] leading-[1.85]" style:color="var(--color-text2)">
			서울시는 도보 30분 생활권을 핵심 비전으로 내걸었다. 그러나 그 30분은 청장년(1.28&nbsp;m/s)의 시간이다.<br
			/>
			환승·기후·인프라·복지·의료 5축으로 본 서울 노인 교통약자성 종합 진단.
		</p>

		<!-- 핵심 수치 (HS 스타일을 라이트 톤으로) -->
		<div class="grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
			{#each heroStats as s, i}
				<div
					class="hero-stat border-l-2 pl-4"
					style:border-color="rgba(216,90,48,0.32)"
					style:--ad="{i * 90}ms"
				>
					<div
						class="font-mono text-[26px] font-medium leading-none tabular-nums sm:text-[30px]"
						style:color="var(--color-text)"
					>
						<CountUp value={s.num} decimals={s.decimals} duration={1100 + i * 80} />
						<span class="ml-[3px] text-[0.42em] font-normal" style:color="var(--color-accent)">
							{s.unit}
						</span>
					</div>
					<div class="mt-1.5 text-[11px]" style:color="var(--color-text3)">{s.label}</div>
				</div>
			{/each}
		</div>
	</div>

	<!-- ── 5 도메인 카드 ── -->
	<div class="ct-label mb-2.5 px-1">5축 도메인 · 본론 대시보드</div>
	<div class="mb-3.5 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
		{#each domains as d}
			<a
				href="{base}/{d.slug}"
				class="card-shell group relative block overflow-hidden no-underline transition-shadow duration-200 hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)]"
				style:padding="16px 16px"
			>
				<!-- 호버 시 상단 액센트 라인 -->
				<span
					class="absolute inset-x-0 top-0 h-[3px] origin-left scale-x-0 transition-transform duration-300 group-hover:scale-x-100"
					style:background={d.accent}
				></span>
				<div class="mb-2 text-[26px] leading-none">{d.emoji}</div>
				<div class="text-[15px] font-medium" style:color="var(--color-text)">{d.label}</div>
				<div class="mt-1 text-[11.5px] leading-snug" style:color="var(--color-text3)">
					{domainBlurb[d.slug]}
				</div>
				{#if d.author}
					<div class="kicker mt-2.5">{d.author}</div>
				{/if}
			</a>
		{/each}
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
