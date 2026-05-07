<script>
	/**
	 * @typedef {Object} Props
	 * @property {string} [title] - 카드 상단 ct-label (uppercase mono)
	 * @property {string} [class] - 외부 layout/grid 클래스
	 * @property {import('svelte').Snippet} [children] - 카드 내용
	 */

	/** @type {Props} */
	let { title, class: className = '', children } = $props();
</script>

<section class="card-shell {className}">
	{#if title}
		<div class="ct-label mb-2.5">{title}</div>
	{/if}
	{@render children?.()}
</section>
