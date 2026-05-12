/**
 * 표 헤더 클릭 정렬 공통 유틸.
 * Svelte 5 runes 컴포넌트에서:
 *   let sortKey = $state('score');
 *   let sortDir = $state('desc');
 *   function setSort(k) { ({ sortKey, sortDir } = applySort(k, sortKey, sortDir, ['gu','dong','name'])); }
 *   const sorted = $derived([...rows].sort(compareBy(sortKey, sortDir)));
 */

/**
 * 같은 키 누르면 asc↔desc 토글, 다른 키 누르면 새로 정렬.
 * 디폴트 방향: stringKeys 에 포함된 키면 asc, 아니면 desc.
 *
 * @param {string} k - 새로 클릭된 헤더 키
 * @param {string} curKey - 현재 sortKey
 * @param {string} curDir - 현재 sortDir ('asc' | 'desc')
 * @param {string[]} [stringKeys] - 디폴트 asc 가 자연스러운 문자열 키 목록
 * @returns {{ sortKey: string, sortDir: 'asc' | 'desc' }}
 */
export function applySort(k, curKey, curDir, stringKeys = []) {
	if (curKey === k) return { sortKey: k, sortDir: curDir === 'desc' ? 'asc' : 'desc' };
	return { sortKey: k, sortDir: stringKeys.includes(k) ? 'asc' : 'desc' };
}

/**
 * sortKey/sortDir 기준 비교 함수 — Array.sort() 에 바로 사용.
 * null/undefined 는 항상 뒤로 보냄.
 *
 * @param {string} key
 * @param {'asc' | 'desc'} dir
 * @returns {(a: any, b: any) => number}
 */
export function compareBy(key, dir) {
	const sign = dir === 'desc' ? -1 : 1;
	return (a, b) => {
		const va = a[key];
		const vb = b[key];
		const aBad = va == null || (typeof va === 'number' && !Number.isFinite(va));
		const bBad = vb == null || (typeof vb === 'number' && !Number.isFinite(vb));
		if (aBad && bBad) return 0;
		if (aBad) return 1;
		if (bBad) return -1;
		if (typeof va === 'string') return sign * va.localeCompare(vb, 'ko');
		return sign * (va - vb);
	};
}
