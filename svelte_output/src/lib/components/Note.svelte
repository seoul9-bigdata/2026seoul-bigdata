<script>
	/**
	 * @typedef {Object} Props
	 * @property {'warm'|'cool'} [tone] - warm = yellow(.note), cool = blue(.note-b)
	 * @property {string} [class] - 외부 클래스
	 * @property {import('svelte').Snippet} [children] - 본문
	 */

	/** @type {Props} */
	let { tone = 'warm', class: className = '', children } = $props();

	const bg = $derived(
		tone === 'cool' ? 'var(--color-note-cool-bg)' : 'var(--color-note-warm-bg)'
	);
	const border = $derived(
		tone === 'cool' ? 'var(--color-note-cool-border)' : 'var(--color-note-warm-border)'
	);
	const color = $derived(
		tone === 'cool' ? 'var(--color-note-cool-text)' : 'var(--color-note-warm-text)'
	);
</script>

<div
	class="text-[12px] {className}"
	style:background={bg}
	style:border="0.5px solid {border}"
	style:border-radius="8px"
	style:padding="10px 14px"
	style:line-height="1.7"
	style:color={color}
>
	{@render children?.()}
</div>
