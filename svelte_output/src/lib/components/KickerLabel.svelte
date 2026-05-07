<script>
	/**
	 * @typedef {Object} Props
	 * @property {string} text - 라벨 텍스트
	 * @property {string} [class] - 외부 클래스
	 */

	/** @type {Props} */
	let { text, class: className = '' } = $props();
</script>

<div class="kicker {className}">{text}</div>
