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
	<div class="hero-glow"></div>
	<div class="climate-hero-inner">
		<div class="hero-text">
			<p class="hero-kicker">② 기후 · 김성령</p>
			<h1 class="hero-title">
				노인 <em>기후안전권</em> 분석
			</h1>
			<div class="hero-chips">
				<span class="chip amber">☀️ 더위쉼터 4,107개</span>
				<span class="chip blue">❄️ 한파쉼터 1,642개</span>
				<span class="chip ice">🧊 결빙위험구역</span>
			</div>
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
		background: radial-gradient(circle, rgba(245,183,64,0.18), transparent 65%);
	}
	.climate-hero-inner {
		position: relative;
		max-width: 1340px;
		margin: 0 auto;
	}
	.hero-kicker {
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-amber);
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
		color: var(--color-amber);
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
	.chip.amber {
		background: rgba(245,183,64,0.15);
		color: #f5b740;
		border: 0.5px solid rgba(245,183,64,0.3);
	}
	.chip.blue {
		background: rgba(74,144,217,0.15);
		color: #82bcf0;
		border: 0.5px solid rgba(74,144,217,0.3);
	}
	.chip.ice {
		background: rgba(0,229,255,0.1);
		color: #7fecff;
		border: 0.5px solid rgba(0,229,255,0.25);
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
</style>
