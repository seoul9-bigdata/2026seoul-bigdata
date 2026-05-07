<script>
	/**
	 * @typedef {Object} Props
	 * @property {string} label - 작은 회색 라벨
	 * @property {string|number} value - 큰 숫자/값
	 * @property {string} [sub] - 보조 텍스트
	 * @property {'red'|'green'|'blue'|'orange'} [tone] - 값 색조
	 * @property {string} [class] - 외부 클래스
	 */

	/** @type {Props} */
	let { label, value, sub, tone, class: className = '' } = $props();

	const toneColor = $derived(
		tone === 'red'
			? '#c0392b'
			: tone === 'green'
				? '#0f6e56'
				: tone === 'blue'
					? '#185FA5'
					: tone === 'orange'
						? '#d46800'
						: 'var(--color-text)'
	);
</script>

<div
	class="rounded-[8px] {className}"
	style:background="var(--color-card-soft)"
	style:padding="12px 14px"
>
	<div class="text-[11px]" style:color="var(--color-text3)" style:margin-bottom="3px">{label}</div>
	<div class="text-[22px] font-medium leading-tight" style:color={toneColor}>{value}</div>
	{#if sub}
		<div class="text-[11px]" style:color="var(--color-text3)" style:margin-top="2px">{sub}</div>
	{/if}
</div>
