/**
 * Svelte action: 요소가 뷰포트 진입하면 `data-in-view` 속성 추가.
 * 로드 시 이미 보이면 즉시 트리거.
 *
 * @param {HTMLElement} node
 * @param {{ threshold?: number, once?: boolean, rootMargin?: string }} [opts]
 */
export function viewport(node, opts = {}) {
	const { threshold = 0, once = true, rootMargin = '0px' } = opts;

	// SSR / 미지원 환경 → 즉시 in-view
	if (typeof IntersectionObserver === 'undefined') {
		node.dataset.inView = '';
		return {};
	}

	/** @type {IntersectionObserver | undefined} */
	let io;

	// 레이아웃 안정화 후 observe — 일부 환경에서 즉시 observe 시 콜백 누락 방지
	requestAnimationFrame(() => {
		io = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					if (e.isIntersecting) {
						node.dataset.inView = '';
						if (once) {
							io?.disconnect();
							break;
						}
					} else if (!once) {
						delete node.dataset.inView;
					}
				}
			},
			{ threshold, rootMargin }
		);
		io.observe(node);
	});

	// 폴백 — 600ms 안에 IO가 발화 못 했고 화면에 이미 보이면 강제 활성
	setTimeout(() => {
		if ('inView' in node.dataset) return;
		const r = node.getBoundingClientRect();
		const vh = window.innerHeight || document.documentElement.clientHeight;
		const vw = window.innerWidth || document.documentElement.clientWidth;
		if (r.top < vh && r.bottom > 0 && r.left < vw && r.right > 0) {
			node.dataset.inView = '';
		}
	}, 600);

	return {
		destroy() {
			io?.disconnect();
		}
	};
}
