/**
 * 단일 진실 원천 (single source of truth) — 도메인 / 점수 / 차트 theme.
 * CSS 변수는 src/routes/layout.css 의 @theme 블록에서 정의됨.
 *
 * 사용 패턴:
 *   import { DOMAIN_THEME, DOMAINS_4, scoreColor, CHART_THEME } from '$lib/theme.js';
 *   const climateHex = DOMAIN_THEME.climate.color;       // '#f5b740'
 *   const climateVar = DOMAIN_THEME.climate.accent;      // 'var(--color-amber)'
 */

/** 5개 도메인 통합 theme — nav 액센트, 카드 색, 차트 색 모두 여기서 가져옴 */
export const DOMAIN_THEME = {
	transit: {
		key: 'transit',
		label: '교통·이동',
		emoji: '🚇',
		author: '유호준',
		color: '#5aadff',
		accent: 'var(--color-blue)',
		light: 'rgba(90,173,255,0.10)',
		soft: '#dbeefe'
	},
	climate: {
		key: 'climate',
		label: '기후',
		emoji: '🌡️',
		author: '김',
		color: '#f5b740',
		accent: 'var(--color-amber)',
		light: 'rgba(245,183,64,0.10)',
		soft: '#fef3cd'
	},
	infra: {
		key: 'infra',
		label: '인프라',
		emoji: '🏪',
		author: '심',
		color: '#3ecfa0',
		accent: 'var(--color-teal)',
		light: 'rgba(62,207,160,0.10)',
		soft: '#d1f3e6'
	},
	bokji: {
		key: 'bokji',
		label: '복지',
		emoji: '🏛️',
		author: '양',
		color: '#b48ef4',
		accent: 'var(--color-purple)',
		light: 'rgba(180,142,244,0.10)',
		soft: '#ebe1fb'
	},
	medical: {
		key: 'medical',
		label: '의료',
		emoji: '🏥',
		author: '이',
		color: '#f472b6',
		accent: 'var(--color-pink)',
		light: 'rgba(244,114,182,0.10)',
		soft: '#fbe1ed'
	}
};

/** 결론에서 결합되는 4개 도메인 (transit 제외 — CSV 미작성) */
export const DOMAINS_4 = ['climate', 'infra', 'bokji', 'medical'].map((k) => DOMAIN_THEME[k]);

/** 5개 전체 (메인/네비) */
export const DOMAINS_5 = ['transit', 'climate', 'infra', 'bokji', 'medical'].map(
	(k) => DOMAIN_THEME[k]
);

/** 도달가능 점수 5단계 색조 (conclusion choropleth + ranking bars) */
export const SCORE_TIERS = [
	{ max: 50, color: '#9B1C1C', bg: '#fde8e8', label: '~50 최취약' },
	{ max: 58, color: '#D85A30', bg: '#fdecd9', label: '50~58' },
	{ max: 65, color: '#f5b740', bg: '#fef3cd', label: '58~65' },
	{ max: 73, color: '#1D9E75', bg: '#dcf3ea', label: '65~73' },
	{ max: 101, color: '#0f6e56', bg: '#d1ede0', label: '73+ 양호' }
];

export function scoreColor(s) {
	for (const t of SCORE_TIERS) if (s < t.max) return t.color;
	return SCORE_TIERS[SCORE_TIERS.length - 1].color;
}
export function scoreBg(s) {
	for (const t of SCORE_TIERS) if (s < t.max) return t.bg;
	return SCORE_TIERS[SCORE_TIERS.length - 1].bg;
}

/** 보행자 유형 4종 — speed 토글에 사용 */
export const WALK_TYPES = [
	{ key: '일반인', label: '일반인', mps: 1.28, color: '#4a9eff', emoji: '🚶' },
	{ key: '노인', label: '일반 노인', mps: 1.12, color: '#1D9E75', emoji: '🧓' },
	{ key: '보조', label: '보행보조 노인', mps: 0.88, color: '#f5b740', emoji: '🦯' },
	{ key: '하위15', label: '보조 하위15%', mps: 0.7, color: '#ef5555', emoji: '🦽' }
];

/** 고령화율 색조 (intro choropleth) */
export const AGING_TIERS_2026 = [
	{ max: 18, color: '#fef3cd' },
	{ max: 22, color: '#f5b740' },
	{ max: 25, color: '#e87f2a' },
	{ max: 101, color: '#c0391b' }
];
export const AGING_TIERS_2040 = [
	{ max: 15, color: '#fff5e0' },
	{ max: 18, color: '#fef3cd' },
	{ max: 22, color: '#f5b740' },
	{ max: 25, color: '#e87f2a' },
	{ max: 28, color: '#c0391b' },
	{ max: 31, color: '#7a1a08' },
	{ max: 34, color: '#4d1006' },
	{ max: 101, color: '#200703' }
];

/** Radar 등 비교 차트의 두 시리즈 색상 — 보색 관계 (orange ↔ teal-cyan) */
export const COMPARE_COLORS = {
	primary: {
		stroke: '#D85A30',
		point: '#D85A30',
		fill: 'rgba(216,90,48,0.14)'
	},
	reference: {
		stroke: '#1B95B5',
		point: '#1B95B5',
		fill: 'rgba(27,149,181,0.14)'
	}
};

/** Chart.js 공통 theme */
export const CHART_THEME = {
	fontFamily: "'Noto Sans KR', 'Apple SD Gothic Neo', system-ui, sans-serif",
	textColor: '#2c2c2a',
	textColorMuted: '#888780',
	borderColor: 'rgba(0,0,0,0.06)',
	gridColor: 'rgba(0,0,0,0.04)',
	tooltipBg: 'rgba(255,255,255,0.96)',
	tooltipBorder: 'rgba(0,0,0,0.08)',

	/** 차트 인스턴스에 펼쳐 쓸 기본 옵션 */
	baseOptions: {
		responsive: true,
		maintainAspectRatio: false,
		animation: { duration: 700, easing: 'easeOutCubic' },
		plugins: {
			legend: { labels: { font: { size: 11 }, boxWidth: 12 } }
		}
	}
};

/**
 * Chart.js 글로벌 디폴트 적용 (앱 시작 시 한 번만 호출).
 * Svelte 페이지에서 onMount 안에서 실행:
 *   onMount(async () => { await applyChartTheme(); ... });
 */
export async function applyChartTheme() {
	if (typeof window === 'undefined') return null;
	const ChartMod = await import('chart.js/auto');
	const Chart = ChartMod.default;
	Chart.defaults.font.family = CHART_THEME.fontFamily;
	Chart.defaults.font.size = 11;
	Chart.defaults.color = CHART_THEME.textColor;
	Chart.defaults.borderColor = CHART_THEME.borderColor;
	return Chart;
}

/** 도메인 키 배열로 Chart.js 데이터셋 색상 */
export function domainColors(keys) {
	return keys.map((k) => DOMAIN_THEME[k]?.color ?? '#888');
}
