<script>
	/**
	 * @typedef {Object} Props
	 * @property {boolean} [active] - on 상태
	 * @property {'default'|'wide'} [variant] - wide 는 .bw (8px radius)
	 * @property {(e: MouseEvent) => void} [onclick] - 클릭 핸들러
	 * @property {string} [class] - 외부 클래스
	 * @property {import('svelte').Snippet} [children] - 라벨 (이모지 가능)
	 */

	/** @type {Props} */
	let {
		active = false,
		variant = 'default',
		onclick,
		class: className = '',
		children
	} = $props();
</script>

<button
	type="button"
	class="pill-btn {active ? 'pill-btn-on' : ''} {variant === 'wide' ? 'rounded-[8px]' : ''} {className}"
	style:background={active ? 'var(--pill-accent, var(--color-dark))' : '#fff'}
	style:border-color={active ? 'var(--pill-accent, var(--color-dark))' : ''}
	style:color={active ? 'var(--pill-on-text, var(--color-dark-text))' : ''}
	{onclick}
>
	{@render children?.()}
</button>

<style>
	button:hover {
		border-color: var(--color-text2);
		color: var(--color-text);
	}
	button.pill-btn-on:hover {
		filter: brightness(1.08);
	}
</style>
