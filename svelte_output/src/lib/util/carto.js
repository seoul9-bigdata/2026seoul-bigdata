// CARTO 베이스맵 타일 URL (2026-09부터 API 키 필수)
// 키는 svelte_output/.env 의 PUBLIC_CARTO_KEY 에 넣는다. 빌드 시점에 번들에 박힘.
import * as env from '$env/static/public';

const KEY = env.PUBLIC_CARTO_KEY ?? '';

/** @param {'light_all' | 'light_nolabels' | 'dark_all' | 'dark_nolabels' | 'voyager'} style */
export function cartoTiles(style = 'light_all') {
	return `https://basemaps.cartocdn.com/rastertiles/${style}/{z}/{x}/{y}{r}.png?key=${KEY}`;
}
