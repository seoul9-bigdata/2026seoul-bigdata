<script>
	/**
	 * @typedef {Object} Props
	 * @property {string} title - 카드 ct-label
	 * @property {string} [height] - 차트 높이 (기본 260px)
	 * @property {string} [class] - 외부 클래스
	 * @property {(el: HTMLCanvasElement) => void} [onmount] - canvas DOM이 준비되면 호출 (Chart.js 인스턴스 연결용)
	 * @property {import('svelte').Snippet} [children] - 사용자가 직접 차트 markup을 넣고 싶을 때 (canvas 대신 사용)
	 */

	/** @type {Props} */
	let { title, height = '260px', class: className = '', onmount, children } = $props();

	/** @type {HTMLCanvasElement | undefined} */
	let canvasEl = $state();

	$effect(() => {
		if (canvasEl && onmount) onmount(canvasEl);
	});
</script>

<section class="card-shell {className}">
	<div class="ct-label mb-2.5">{title}</div>
	<div class="relative w-full" style:height>
		{#if children}
			{@render children()}
		{:else}
			<canvas bind:this={canvasEl} class="block h-full w-full"></canvas>
		{/if}
	</div>
</section>
