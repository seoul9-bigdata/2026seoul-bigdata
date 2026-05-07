<script>
	import { page } from '$app/state';
	import { base } from '$app/paths';
	import { ROUTES } from '$lib/nav.js';

	const path = $derived(
		page.url.pathname.replace(base, '').replace(/^\//, '').split('/')[0] || ''
	);
</script>

<header>
	<a class="title-block" href="{base}/">
		<h1>분(分)의 격차</h1>
		<p>Seoul Elder Mobility · 노인 도보 생활권 진단</p>
	</a>

	<nav>
		{#each ROUTES as r}
			{@const active = path === r.slug}
			<a
				class="pill"
				class:on={active}
				href="{base}/{r.slug}"
				style:--pill-color={r.accent}
				title={r.author ? `${r.label} · ${r.author}` : r.label}
			>
				<span class="emoji">{r.emoji}</span><span>{r.label}</span>
			</a>
		{/each}
	</nav>
</header>

<style>
	header {
		position: sticky;
		top: 0;
		/* Leaflet `.leaflet-top` 컨트롤 컨테이너 자체가 z-index:1000 — 헤더는 그 위로. */
		z-index: 2000;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 16px 28px;
		padding: 16px 28px;
		background: var(--color-dark);
		color: var(--color-dark-text);
		isolation: isolate;
	}

	.title-block {
		display: flex;
		flex-direction: column;
		gap: 4px;
		text-decoration: none;
		color: inherit;
		flex-shrink: 0;
	}
	.title-block h1 {
		margin: 0;
		font-size: 18px;
		font-weight: 600;
		letter-spacing: 0.01em;
		color: var(--color-dark-text);
		font-family: var(--font-serif);
	}
	.title-block p {
		margin: 0;
		font-size: 12px;
		opacity: 0.55;
		font-family: var(--font-mono);
		letter-spacing: 0.04em;
	}

	nav {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}

	.pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 7px 13px;
		font-size: 12px;
		font-weight: 500;
		letter-spacing: 0.02em;
		text-decoration: none;
		white-space: nowrap;
		border: 1px solid rgba(255, 255, 255, 0.18);
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.05);
		color: rgba(241, 239, 232, 0.82);
		transition:
			border-color 0.15s,
			background 0.15s,
			color 0.15s,
			transform 0.15s;
	}
	.pill:hover {
		color: var(--color-dark-text);
		border-color: var(--pill-color, rgba(255, 255, 255, 0.45));
		background: color-mix(in srgb, var(--pill-color, #fff) 18%, transparent);
		transform: translateY(-1px);
	}
	.pill.on {
		background: var(--pill-color);
		border-color: var(--pill-color);
		color: var(--color-dark);
	}
	.pill .emoji {
		font-size: 13px;
		line-height: 1;
	}

	@media (max-width: 720px) {
		header {
			padding: 12px 16px;
		}
		.title-block h1 {
			font-size: 16px;
		}
		.pill {
			padding: 6px 11px;
			font-size: 11.5px;
		}
	}
</style>
