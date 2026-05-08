<script>
	/**
	 * IntersectionObserver 기반 숫자 카운트업.
	 * @typedef {Object} Props
	 * @property {number} value - 목표값
	 * @property {number} [from] - 시작값 (기본 0)
	 * @property {number} [duration] - 애니메이션 시간 ms (기본 1100)
	 * @property {number} [decimals] - 소수점 자리수 (기본 자동 추정: value가 정수면 0, 소수면 1)
	 * @property {string} [prefix] - 앞 (예: '−')
	 * @property {string} [suffix] - 뒤 (예: '%', '만 명')
	 * @property {string} [class] - 외부 클래스
	 * @property {boolean} [tabular] - tabular-nums (기본 true)
	 * @property {number} [threshold] - IO 임계 (기본 0.4)
	 */

	/** @type {Props} */
	let {
		value,
		from = 0,
		duration = 1100,
		decimals,
		prefix = '',
		suffix = '',
		class: className = '',
		tabular = true,
		threshold = 0.4
	} = $props();

	const dec = $derived(decimals != null ? decimals : Number.isInteger(value) ? 0 : 1);

	let display = $state(from);
	/** @type {HTMLSpanElement | undefined} */
	let el = $state();

	function animate() {
		if (typeof window === 'undefined' || !window.requestAnimationFrame) {
			display = value;
			return;
		}
		const start = performance.now();
		const delta = value - from;
		const tick = (t) => {
			const e = Math.min(1, (t - start) / duration);
			// ease-out cubic
			const v = from + delta * (1 - Math.pow(1 - e, 3));
			display = v;
			if (e < 1) requestAnimationFrame(tick);
			else display = value;
		};
		requestAnimationFrame(tick);
	}

	$effect(() => {
		if (!el || typeof IntersectionObserver === 'undefined') {
			display = value;
			return;
		}
		const io = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					if (entry.isIntersecting) {
						animate();
						io.disconnect();
						break;
					}
				}
			},
			{ threshold }
		);
		io.observe(el);
		return () => io.disconnect();
	});

	const formatted = $derived(
		dec > 0 ? display.toFixed(dec) : Math.round(display).toLocaleString()
	);
</script>

<span bind:this={el} class={className} class:tabular-nums={tabular}>
	{prefix}{formatted}{suffix}
</span>
