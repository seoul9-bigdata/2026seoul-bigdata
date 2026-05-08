/**
 * 네비게이션 메타 — 5개 도메인 + 상위 3개 페이지 (원형 흐름 순서).
 * 도메인 색상 / 메타는 theme.js 의 DOMAIN_THEME 에서 가져옴 (단일 진실 원천).
 */
import { DOMAIN_THEME } from './theme.js';

const domainRoute = (key, slug, desc) => ({
	slug,
	label: DOMAIN_THEME[key].label,
	kind: 'domain',
	emoji: DOMAIN_THEME[key].emoji,
	accent: DOMAIN_THEME[key].accent,
	author: DOMAIN_THEME[key].author,
	desc
});

export const ROUTES = [
	{
		slug: '',
		label: '메인',
		kind: 'main',
		emoji: '🌌',
		accent: 'var(--color-accent)',
		desc: '분(分)의 격차 — 5축 시각화 진단 시작'
	},
	{
		slug: 'introduce',
		label: '인트로',
		kind: 'main',
		emoji: '✨',
		accent: 'var(--color-coral)',
		desc: '왜 노인 도보 생활권인가 — 2040 인구 변화 + 문제 정의'
	},
	domainRoute('transit', 'transit', '환승·정류장·OD 흐름 — 노인 카드 trip 505K 분석'),
	domainRoute('climate', 'climate', '폭염·한파·결빙 — 도보 30분 내 쉼터 도달성'),
	domainRoute('infra', 'infra', '시장·마트·은행·주민센터 도달가능 점수'),
	domainRoute('bokji', 'bokji', '경로당·노인복지관·공원 분포와 보행 도달성'),
	domainRoute('medical', 'medical', '1차 진료·약국·응급 30분 도달 반경'),
	{
		slug: 'conclusion',
		label: '결론',
		kind: 'main',
		emoji: '📊',
		accent: 'var(--color-accent)',
		desc: '5축 결합 — 25구 종합 진단 + 정책 제안'
	}
];
