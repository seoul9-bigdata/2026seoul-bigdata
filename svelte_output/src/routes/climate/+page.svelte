<script>
	import PillTabs from '$lib/components/PillTabs.svelte';
	import ShelterTab from '$lib/components/climate/ShelterTab.svelte';
	import IceTab from '$lib/components/climate/IceTab.svelte';

	const tabs = [
		{ key: 'shelter', label: '기후쉼터 접근성', emoji: '☀️❄️' },
		{ key: 'ice', label: '결빙위험구역', emoji: '🧊' }
	];

	let activeTab = $state('shelter');
</script>

<svelte:head>
	<title>③ 기후 — 노인 기후안전권 분석</title>
</svelte:head>

<section class="climate-hero">
	<div class="climate-hero-inner">
		<div class="hero-text">
			<p class="hero-kicker">KIM · 폭염·한파·빙결 취약</p>
			<h1 class="hero-title">③ 기후 — 노인 기후안전권 분석</h1>
			<p class="hero-sub">
				더위쉼터 4,107개 · 한파쉼터 1,642개 · 행정동 426개 · OSM 보행 네트워크 + 다익스트라 ·
				서울시 2025
			</p>
		</div>
	</div>
</section>

<div class="wrap">
	<div class="main-tabs">
		<PillTabs {tabs} value={activeTab} onChange={(k) => (activeTab = k)} />
	</div>

	<div style:display={activeTab === 'shelter' ? 'block' : 'none'}>
		<ShelterTab active={activeTab === 'shelter'} />
	</div>

	<div style:display={activeTab === 'ice' ? 'block' : 'none'}>
		<IceTab active={activeTab === 'ice'} />
	</div>
</div>

<style>
	.climate-hero {
		background: var(--color-dark);
		color: var(--color-dark-text);
		padding: 18px 28px;
	}
	.climate-hero-inner {
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
