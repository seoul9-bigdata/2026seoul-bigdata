<script>
	import PillTabs from '$lib/components/PillTabs.svelte';
	import ConstellationTab from '$lib/components/transit/ConstellationTab.svelte';
	import HeatTab from '$lib/components/transit/HeatTab.svelte';
	import AnchorTab from '$lib/components/transit/AnchorTab.svelte';
	import CrosswalkTab from '$lib/components/transit/CrosswalkTab.svelte';
	import ODTab from '$lib/components/transit/ODTab.svelte';
	import transitData from '$lib/data/transit.json';

	const tabs = [
		{ key: 'constellation', label: '환승 별자리', emoji: '🌌' },
		{ key: 'heat', label: '폭염 정류장', emoji: '🌡️' },
		{ key: 'anchor', label: '거점 시설', emoji: '🛒' },
		{ key: 'crosswalk', label: '횡단보도 안전', emoji: '🚦' },
		{ key: 'od', label: '환승 OD', emoji: '🔀' }
	];

	const ALL_GUS_SET = new Set();
	// 모든 데이터셋의 gu 필드에서 자치구 목록 추출 (anchors 의 gu 도 포함)
	for (const item of transitData.DATA.stations) if (item.gu) ALL_GUS_SET.add(item.gu);
	for (const item of transitData.DATA.anchors) if (item.gu) ALL_GUS_SET.add(item.gu);
	const ALL_GUS = [...ALL_GUS_SET].sort(); // 25개 자치구 (가나다순)

	let activeTab = $state('constellation');
	let cG = $state('전체'); // '전체' = 필터 없음
</script>

<svelte:head>
	<title>① 교통·이동 — 노인 대중교통 동선 분석</title>
</svelte:head>

<section class="transit-hero">
	<div class="hero-glow"></div>
	<div class="transit-hero-inner">
		<div class="hero-text">
			<p class="hero-kicker">① 교통·이동 · 유호준</p>
			<h1 class="hero-title">
				노인 대중교통 <em>동선</em> 분석
			</h1>
			<div class="hero-chips">
				<span class="chip blue">🚇 정류장 3,290개</span>
				<span class="chip blue">🛒 거점시설 347개</span>
				<span class="chip blue">🚦 보행사고 1,963건</span>
				<span class="chip-sep">·</span>
				<span class="chip muted">환승 OD · 서울 열린데이터광장 · 서울시 2025</span>
			</div>
		</div>
	</div>
</section>

<div class="gu-filter-wrap">
	<div class="gu-filter">
		<span class="gu-label">자치구</span>
		<select bind:value={cG} class="gu-select">
			<option value="전체">전체</option>
			{#each ALL_GUS as gu}
				<option value={gu}>{gu}</option>
			{/each}
		</select>
	</div>
</div>

<div class="wrap">
	<div class="main-tabs">
		<PillTabs {tabs} value={activeTab} onChange={(k) => (activeTab = k)} />
	</div>

	<div style:display={activeTab === 'constellation' ? 'block' : 'none'}>
		<ConstellationTab active={activeTab === 'constellation'} {cG} />
	</div>
	<div style:display={activeTab === 'heat' ? 'block' : 'none'}>
		<HeatTab active={activeTab === 'heat'} {cG} />
	</div>
	<div style:display={activeTab === 'anchor' ? 'block' : 'none'}>
		<AnchorTab active={activeTab === 'anchor'} {cG} />
	</div>
	<div style:display={activeTab === 'crosswalk' ? 'block' : 'none'}>
		<CrosswalkTab active={activeTab === 'crosswalk'} {cG} />
	</div>
	<div style:display={activeTab === 'od' ? 'block' : 'none'}>
		<ODTab active={activeTab === 'od'} {cG} />
	</div>
</div>

<style>
	.transit-hero {
		position: relative;
		background: var(--color-dark);
		color: var(--color-dark-text);
		padding: 22px 28px;
		overflow: hidden;
	}
	.hero-glow {
		pointer-events: none;
		position: absolute;
		top: -60px;
		right: -80px;
		width: 340px;
		height: 340px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(90,173,255,0.18), transparent 65%);
	}
	.transit-hero-inner {
		position: relative;
		max-width: 1340px;
		margin: 0 auto;
	}
	.hero-kicker {
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-blue);
		opacity: 0.85;
		margin-bottom: 8px;
	}
	.hero-title {
		font-family: var(--font-display);
		font-size: 26px;
		line-height: 1.2;
		margin-bottom: 12px;
		color: var(--color-dark-text);
	}
	.hero-title em {
		font-style: normal;
		color: var(--color-blue);
	}
	.hero-chips {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}
	.chip {
		font-size: 11px;
		padding: 3px 9px;
		border-radius: 12px;
		background: rgba(255,255,255,0.07);
		color: rgba(241,239,232,0.65);
		white-space: nowrap;
	}
	.chip.blue {
		background: rgba(90,173,255,0.15);
		color: #5aadff;
		border: 0.5px solid rgba(90,173,255,0.3);
	}
	.chip.muted {
		background: transparent;
		color: rgba(241,239,232,0.35);
	}
	.chip-sep {
		color: rgba(241,239,232,0.25);
		font-size: 11px;
	}
	.wrap {
		max-width: 1340px;
		margin: 0 auto;
		padding: 18px 18px 60px;
	}
	.main-tabs {
		margin-bottom: 14px;
	}
	.gu-filter-wrap {
		max-width: 1340px;
		margin: 0 auto;
		padding: 14px 18px 0;
	}
	.gu-filter {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		align-items: center;
	}
	.gu-label {
		font-size: 11px;
		letter-spacing: 0.08em;
		color: var(--color-text3);
		font-family: var(--font-mono);
		margin-right: 4px;
	}
	.gu-select {
		font-size: 12px;
		padding: 4px 10px;
		border: 0.5px solid var(--color-border);
		border-radius: 6px;
		background: var(--color-card);
		color: var(--color-text);
		min-width: 140px;
		cursor: pointer;
		font-family: inherit;
	}
	.gu-select:focus {
		outline: 1px solid var(--color-blue);
		outline-offset: 1px;
	}
</style>
