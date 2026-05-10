<script>
	import { page } from '$app/state';
	import { base } from '$app/paths';
	import { ROUTES } from '$lib/nav.js';

	const path = $derived(
		page.url.pathname.replace(base, '').replace(/^\//, '').split('/')[0] || ''
	);
	const idx = $derived(ROUTES.findIndex((r) => r.slug === path));
	const prev = $derived(ROUTES[(idx - 1 + ROUTES.length) % ROUTES.length] ?? ROUTES[0]);
	const next = $derived(ROUTES[(idx + 1) % ROUTES.length] ?? ROUTES[0]);
</script>

<footer>
	<div class="wrap">
		<div class="kicker-row">
			<span class="kicker">{idx + 1} / {ROUTES.length}</span>
			<span class="dot-sep">·</span>
			<span class="kicker">서론 → 5 도메인 → 결론</span>
		</div>

		<div class="flow">
			<a class="flow-card prev" href="{base}/{prev.slug}" style:--accent={prev.accent}>
				<span class="dir-tag">← 이전</span>
				<div class="emo">{prev.emoji}</div>
				<div class="body">
					<div class="label">{prev.label}{#if prev.author}<span class="author"> · {prev.author}</span>{/if}</div>
					<div class="desc">{prev.desc}</div>
				</div>
			</a>

			<a class="flow-card next" href="{base}/{next.slug}" style:--accent={next.accent}>
				<span class="dir-tag right">다음 →</span>
				<div class="body">
					<div class="label">{next.label}{#if next.author}<span class="author"> · {next.author}</span>{/if}</div>
					<div class="desc">{next.desc}</div>
				</div>
				<div class="emo">{next.emoji}</div>
			</a>
		</div>

		<div class="meta">
			<a href="{base}/" class="home-link">🌌 메인으로</a>
			<span class="dot-sep">·</span>
			<span>2026 Seoul Big-Data · 시각화 부문</span>
			<span class="dot-sep">·</span>
			<span>분(分)의 격차</span>
		</div>
	</div>
</footer>

<style>
	footer {
		margin-top: 12px;
		padding: 40px 28px 48px;
		border-top: 0.5px solid var(--color-border);
		background: var(--color-card-soft);
		font-family: var(--font-sans);
	}
	.wrap {
		max-width: 1340px;
		margin: 0 auto;
	}
	.kicker-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 14px;
	}
	.kicker {
		font-family: var(--font-mono);
		font-size: 10.5px;
		letter-spacing: 0.08em;
		color: var(--color-text3);
		text-transform: uppercase;
	}
	.dot-sep {
		color: var(--color-text4);
		font-size: 10.5px;
	}

	.flow {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
		margin-bottom: 22px;
	}

	.flow-card {
		display: grid;
		gap: 14px;
		align-items: center;
		padding: 18px 22px;
		background: #fff;
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		text-decoration: none;
		color: var(--color-text);
		transition: all 0.2s;
		min-width: 0;
		position: relative;
		overflow: hidden;
	}
	.flow-card.prev {
		grid-template-columns: auto auto 1fr;
		text-align: left;
	}
	.flow-card.next {
		grid-template-columns: 1fr auto auto;
		text-align: right;
	}
	.flow-card::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 2px;
		background: var(--accent, var(--color-text3));
		transform: scaleX(0);
		transform-origin: left;
		transition: transform 0.3s;
	}
	.flow-card.next::before {
		transform-origin: right;
	}
	.flow-card:hover {
		border-color: var(--accent, var(--color-text3));
		transform: translateY(-2px);
		box-shadow: 0 4px 18px rgba(0, 0, 0, 0.06);
	}
	.flow-card:hover::before {
		transform: scaleX(1);
	}

	.dir-tag {
		grid-row: 1 / 2;
		font-family: var(--font-mono);
		font-size: 10.5px;
		letter-spacing: 0.08em;
		color: var(--color-text3);
		text-transform: uppercase;
		white-space: nowrap;
		align-self: start;
		justify-self: start;
	}
	.dir-tag.right {
		justify-self: end;
		grid-column: 1 / -1;
	}
	.flow-card.prev .dir-tag {
		grid-column: 1 / -1;
	}

	.emo {
		font-size: 26px;
		line-height: 1;
		grid-row: 2 / 3;
	}
	.flow-card.prev .emo {
		grid-column: 2 / 3;
	}
	.flow-card.next .emo {
		grid-column: 3 / 4;
	}

	.body {
		grid-row: 2 / 3;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.flow-card.prev .body {
		grid-column: 3 / 4;
	}
	.flow-card.next .body {
		grid-column: 1 / 2;
	}

	.label {
		font-size: 15px;
		font-weight: 500;
		font-family: var(--font-sans);
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.author {
		font-family: var(--font-mono);
		font-size: 11px;
		color: var(--color-text3);
		font-weight: 400;
		letter-spacing: 0.02em;
	}
	.desc {
		font-size: 12px;
		color: var(--color-text2);
		line-height: 1.55;
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
	}

	.meta {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		flex-wrap: wrap;
		font-family: var(--font-mono);
		font-size: 10.5px;
		color: var(--color-text3);
		letter-spacing: 0.04em;
	}
	.home-link {
		color: var(--color-text3);
		text-decoration: none;
		padding: 4px 10px;
		border-radius: 999px;
		border: 0.5px solid var(--color-border);
		background: #fff;
		transition: all 0.18s;
	}
	.home-link:hover {
		color: var(--color-accent);
		border-color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 6%, #fff);
	}

	@media (max-width: 720px) {
		footer {
			padding: 28px 16px 36px;
		}
		.flow {
			grid-template-columns: 1fr;
			gap: 10px;
		}
		.flow-card.next {
			grid-template-columns: auto auto 1fr;
			text-align: left;
		}
		.flow-card.next .body {
			grid-column: 3 / 4;
		}
		.flow-card.next .emo {
			grid-column: 2 / 3;
		}
		.flow-card.next .dir-tag {
			justify-self: start;
		}
	}
</style>
