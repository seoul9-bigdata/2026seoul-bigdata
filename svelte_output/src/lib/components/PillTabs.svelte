<script>
	/**
	 * @typedef {{ key: string, label: string, emoji?: string }} Tab
	 * @typedef {Object} Props
	 * @property {Tab[]} tabs - 탭 정의
	 * @property {string} value - 현재 선택된 key
	 * @property {(key: string) => void} onChange - 변경 콜백
	 * @property {string} [class] - 외부 클래스
	 */

	/** @type {Props} */
	let { tabs, value, onChange, class: className = '' } = $props();
</script>

<div class="flex flex-wrap gap-1.5 {className}">
	{#each tabs as t (t.key)}
		{@const on = value === t.key}
		<button
			type="button"
			class="mtab font-sans font-medium whitespace-nowrap"
			class:on
			onclick={() => onChange(t.key)}
		>
			{#if t.emoji}<span class="mr-1">{t.emoji}</span>{/if}{t.label}
		</button>
	{/each}
</div>

<style>
	.mtab {
		font-size: 13px;
		padding: 8px 20px;
		border-radius: 24px;
		border: 0.5px solid var(--color-border);
		background: #fff;
		color: var(--color-text2);
		cursor: pointer;
		transition: all 0.14s;
		font-family: inherit;
	}
	.mtab:hover {
		border-color: var(--color-text2);
	}
	.mtab.on {
		background: var(--pill-accent, var(--color-dark));
		color: var(--pill-on-text, var(--color-dark-text));
		border-color: var(--pill-accent, var(--color-dark));
	}
	.mtab.on:hover {
		filter: brightness(1.08);
	}
</style>
