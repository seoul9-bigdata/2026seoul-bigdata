<script>
	/**
	 * @typedef {Object} Props
	 * @property {string} [class] - 외부 클래스 (cols 변경 시 사용)
	 * @property {number} [cols] - 열 개수 (기본 4)
	 * @property {import('svelte').Snippet} [children] - StatCard 들
	 */

	/** @type {Props} */
	let { class: className = '', cols = 4, children } = $props();
</script>

<div
	class="grid gap-2.5 {className}"
	style:grid-template-columns="repeat({cols}, minmax(0, 1fr))"
>
	{@render children?.()}
</div>
