<script>
	import PillTabs from '$lib/components/PillTabs.svelte';
	import ConstellationTab from '$lib/components/transit/ConstellationTab.svelte';
	import HeatTab from '$lib/components/transit/HeatTab.svelte';
	import AnchorTab from '$lib/components/transit/AnchorTab.svelte';
	import CrosswalkTab from '$lib/components/transit/CrosswalkTab.svelte';
	import ODTab from '$lib/components/transit/ODTab.svelte';

	const tabs = [
		{ key: 'constellation', label: '환승 별자리', emoji: '🌌' },
		{ key: 'heat', label: '폭염 정류장', emoji: '🌡️' },
		{ key: 'anchor', label: '거점 시설', emoji: '🛒' },
		{ key: 'crosswalk', label: '횡단보도 안전', emoji: '🚦' },
		{ key: 'od', label: '환승 OD', emoji: '🔀' }
	];

	let activeTab = $state('constellation');
</script>

<svelte:head>
	<title>① 교통·이동 — 노인 환승·OD·거점·횡단보도</title>
</svelte:head>

<section class="transit-hero">
	<div class="transit-hero-inner">
		<div class="hero-text">
			<p class="hero-kicker">YOO · 환승·OD·거점·횡단보도</p>
			<h1 class="hero-title">① 교통·이동 — 노인 대중교통 동선 분석</h1>
			<p class="hero-sub">
				버스·지하철 정류장 3,290 · 노인 환승 OD · 거점 시설 347 · 노인 보행사고 1,963 ·
				서울시 2025
			</p>
		</div>
	</div>
</section>

<div class="wrap">
	<div class="main-tabs">
		<PillTabs {tabs} value={activeTab} onChange={(k) => (activeTab = k)} />
	</div>

	<div style:display={activeTab === 'constellation' ? 'block' : 'none'}>
		<ConstellationTab active={activeTab === 'constellation'} />
	</div>
	<div style:display={activeTab === 'heat' ? 'block' : 'none'}>
		<HeatTab active={activeTab === 'heat'} />
	</div>
	<div style:display={activeTab === 'anchor' ? 'block' : 'none'}>
		<AnchorTab active={activeTab === 'anchor'} />
	</div>
	<div style:display={activeTab === 'crosswalk' ? 'block' : 'none'}>
		<CrosswalkTab active={activeTab === 'crosswalk'} />
	</div>
	<div style:display={activeTab === 'od' ? 'block' : 'none'}>
		<ODTab active={activeTab === 'od'} />
	</div>
</div>

<style>
	.transit-hero {
		background: var(--color-dark);
		color: var(--color-dark-text);
		padding: 18px 28px;
		border-bottom: 1px solid #1a1a18;
	}
	.transit-hero-inner {
		max-width: 1340px;
		margin: 0 auto;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 14px;
		flex-wrap: wrap;
	}
	.hero-kicker {
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		opacity: 0.55;
		margin-bottom: 6px;
		color: var(--color-blue);
	}
	.hero-title {
		font-size: 17px;
		font-weight: 500;
		margin-bottom: 4px;
	}
	.hero-sub {
		font-size: 12px;
		opacity: 0.55;
	}
	.wrap {
		max-width: 1340px;
		margin: 0 auto;
		padding: 18px 18px 60px;
	}
	.main-tabs {
		margin-bottom: 14px;
	}
</style>
