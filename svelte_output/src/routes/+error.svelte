<script>
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import { ROUTES } from '$lib/nav.js';

	const domains = ROUTES.filter((r) => r.kind === 'domain');
</script>

<svelte:head>
	<title>페이지를 찾을 수 없습니다 — Seoul Elder Walkability</title>
</svelte:head>

<section class="mx-auto max-w-[860px] px-[18px] py-16 text-center">
	<div class="mb-3 text-[72px] leading-none" style:color="var(--color-text4)">🔍</div>

	<h1
		class="mb-3 text-[56px] leading-none sm:text-[72px]"
		style:color="var(--color-accent)"
		style:font-family="var(--font-display)"
	>
		{$page.status === 404 ? '404' : $page.status}
	</h1>

	<p class="mb-2 text-[18px] font-medium" style:color="var(--color-text)">
		{$page.status === 404 ? '페이지를 찾을 수 없습니다' : '문제가 발생했습니다'}
	</p>
	<p class="mb-8 text-[13px]" style:color="var(--color-text3)">
		{$page.error?.message ?? '주소가 잘못되었거나 페이지가 이동·삭제되었을 수 있어요.'}
	</p>

	<a
		href="{base}/"
		class="pill-btn pill-btn-on inline-block no-underline"
		style:padding="10px 28px"
		style:font-size="13px"
	>
		🏠 메인으로 돌아가기
	</a>

	<div class="kicker mt-10 mb-4" style:color="var(--color-text2)">
		<span style:color="var(--color-accent)">5축</span> 도메인 둘러보기
	</div>

	<div class="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
		{#each domains as d}
			<a
				href="{base}/{d.slug}"
				class="card-shell group relative block overflow-hidden no-underline transition-shadow duration-200 hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)]"
				style:padding="14px 14px"
			>
				<span
					class="absolute inset-x-0 top-0 h-[2.5px] origin-left scale-x-0 transition-transform duration-300 group-hover:scale-x-100"
					style:background={d.accent}
				></span>
				<div class="mb-1 text-[22px] leading-none">{d.emoji}</div>
				<div class="text-[13px] font-medium" style:color="var(--color-text)">
					{d.label}
				</div>
				{#if d.author}
					<div class="kicker mt-1.5" style:color={d.accent} style:opacity="0.7">{d.author}</div>
				{/if}
			</a>
		{/each}
	</div>
</section>
