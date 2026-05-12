<script>
	/**
	 * @typedef {{ color: string, label: string, shape?: 'square'|'circle' }} LegendItem
	 * @typedef {Object} Props
	 * @property {string} [height] - 지도 높이 (기본 420px)
	 * @property {LegendItem[]} [legend] - 범례 항목
	 * @property {string} [source] - 출처 / 보조 텍스트
	 * @property {string} [class] - 외부 클래스
	 * @property {import('svelte').Snippet} [children] - 지도 컨테이너 (Leaflet/Kakao 마운트용)
	 */

	/** @type {Props} */
	let {
		height = '420px',
		legend = [],
		source,
		class: className = '',
		children
	} = $props();
</script>

<div class={className}>
	<div
		class="relative overflow-hidden"
		style:height
		style:border-radius="8px"
		style:background="#e8e4db"
	>
		{@render children?.()}
	</div>

	{#if legend && legend.length > 0}
		<div class="mt-2 flex flex-wrap gap-3.5">
			{#each legend as item}
				<div class="flex items-center gap-1.5 text-[11px]" style:color="var(--color-text2)">
					<span
						class="inline-block flex-shrink-0"
						style:width="12px"
						style:height="12px"
						style:background={item.color}
						style:border-radius={item.shape === 'circle' ? '50%' : '2px'}
					></span>
					<span>{item.label}</span>
				</div>
			{/each}
		</div>
	{/if}

	{#if source}
		<div class="text-[11px] leading-relaxed" style:color="var(--color-text3)" style:margin-top="8px" style:white-space="pre-line">
			{source}
		</div>
	{/if}
</div>
