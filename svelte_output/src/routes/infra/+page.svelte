<script>
	import { onMount, onDestroy, untrack } from 'svelte';
	import infraData from '$lib/data/infra.json';
	import Card from '$lib/components/Card.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MapShell from '$lib/components/MapShell.svelte';
	import StatGrid from '$lib/components/StatGrid.svelte';
	import PillTabs from '$lib/components/PillTabs.svelte';
	import Note from '$lib/components/Note.svelte';
	import CountUp from '$lib/components/CountUp.svelte';
	import { loadGraph, computeIsochrone } from '$lib/util/isochrone.js';
	import { applySort, compareBy } from '$lib/util/sortable.js';

	const {
		ALL_DONG_DATA, BANK_SERIES, GU_BANK, GU_BANK_YEARS, CENTERS, CENTER_BY_GU,
		DONG_REACH, MKT, SUP, SEOUL_BANKS, TOBLER_DONG, WS
	} = infraData;

	const GU_ORDER = [
		'종로구', '중구', '용산구', '성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '도봉구', '노원구', '은평구', '서대문구', '마포구', '양천구', '강서구', '구로구', '금천구', '영등포구', '동작구', '관악구', '서초구', '강남구', '송파구', '강동구'
	];

	let cW = $state(0);
	let cT = $state(30);
	let cG = $state('종로구');
	let cD = $state('종로구_사직동');
	let cSlope = $state(false);
	let cUnit = $state('dong');
	let cLayer = $state('all');
	let sortKeyGu = $state('score');
	let sortDirGu = $state(/** @type {'asc' | 'desc'} */ ('desc'));
	let sortKeyDong = $state('score');
	let sortDirDong = $state(/** @type {'asc' | 'desc'} */ ('desc'));

	function getToblerRatio(dongKey) {
		if (TOBLER_DONG[dongKey] != null) return TOBLER_DONG[dongKey];
		if (!dongKey) return 0.85;
		const gu = dongKey.split('_')[0];
		const vals = Object.entries(TOBLER_DONG).filter(([k]) => k.startsWith(gu + '_')).map(([, v]) => v);
		return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0.85;
	}

	function calcScore(loss, dongKey) {
		if (typeof loss !== 'number') return null;
		const flatScore = 100 - loss;
		if (!cSlope || !dongKey) return Math.round(flatScore * 10) / 10;
		const r = getToblerRatio(dongKey);
		const effSpeed = WS[cW].speed * r;
		const dr = DONG_REACH[dongKey];
		if (!dr) return Math.round(Math.max(0, Math.min(100, flatScore * r)) * 10) / 10;
		const t30 = String(30);
		const pts = [
			{ s: 1.28, sc: 100 - (/** @type {any} */ (dr.general)?.[t30]?.loss ?? 0) },
			{ s: 1.12, sc: 100 - (/** @type {any} */ (dr.senior)?.[t30]?.loss ?? 0) },
			{ s: 0.88, sc: 100 - (/** @type {any} */ (dr.aided)?.[t30]?.loss ?? 0) },
			{ s: 0.7,  sc: 100 - (/** @type {any} */ (dr.aided15)?.[t30]?.loss ?? 0) }
		].sort((a, b) => a.s - b.s);
		if (effSpeed <= pts[0].s) return Math.round(Math.max(0, pts[0].sc) * 10) / 10;
		if (effSpeed >= pts[pts.length - 1].s) return Math.round(Math.max(0, pts[pts.length - 1].sc) * 10) / 10;
		for (let i = 0; i < pts.length - 1; i++) {
			if (effSpeed >= pts[i].s && effSpeed <= pts[i + 1].s) {
				const t = (effSpeed - pts[i].s) / (pts[i + 1].s - pts[i].s);
				const sc = pts[i].sc + t * (pts[i + 1].sc - pts[i].sc);
				return Math.round(Math.max(0, Math.min(100, sc)) * 10) / 10;
			}
		}
		return Math.round(flatScore * 10) / 10;
	}

	const currentW = $derived(WS[cW]);
	const currentDong = $derived(ALL_DONG_DATA[cD] || null);
	const currentReach = $derived(DONG_REACH[cD] || null);
	const wReach = $derived.by(() => {
		if (!currentReach) return null;
		const wid = currentW.id;
		const t = String(cT);
		const wd = currentReach[wid]?.[t];
		if (!wd) return null;
		if (wd.loss != null) return wd;
		const genTot = currentReach['general']?.[t]?.tot ?? 0;
		const loss = genTot > 0 ? Math.max(0, (1 - (wd.tot ?? 0) / genTot) * 100) : null;
		return { ...wd, loss };
	});
	const ratio = $derived(cSlope ? getToblerRatio(cD) : 1.0);
	const effSpeedDisplay = $derived((currentW.speed * ratio).toFixed(2));
	const score = $derived(wReach ? calcScore(wReach.loss, cD) : null);

	const guReach = $derived.by(() => {
		if (cUnit !== 'gu') return null;
		const gc = guCenter(cG);
		if (!gc) return null;
		const w = WS[cW];
		const r = w.speed * cT * 60;
		const mkt    = MKT.filter((m) => m.lat && hav(gc.lat, gc.lng, m.lat, m.lng) <= r).length;
		const sup    = SUP.filter((s) => s.lat && hav(gc.lat, gc.lng, s.lat, s.lng) <= r).length;
		const center = CENTERS.filter((c) => c.lat && hav(gc.lat, gc.lng, c.lat, c.lng) <= r).length;
		const bank   = SEOUL_BANKS.filter((b) => b.lat && hav(gc.lat, gc.lng, b.lat, b.lng) <= r).length;
		const tot = mkt + sup + center + bank;
		const rGen = (WS.find((w) => w.id === 'general')?.speed ?? 1.28) * cT * 60;
		const genTot = MKT.filter((m) => m.lat && hav(gc.lat, gc.lng, m.lat, m.lng) <= rGen).length
			+ SUP.filter((s) => s.lat && hav(gc.lat, gc.lng, s.lat, s.lng) <= rGen).length
			+ CENTERS.filter((c) => c.lat && hav(gc.lat, gc.lng, c.lat, c.lng) <= rGen).length
			+ SEOUL_BANKS.filter((b) => b.lat && hav(gc.lat, gc.lng, b.lat, b.lng) <= rGen).length;
		const isGeneral = WS[cW].id === 'general';
		const sc = isGeneral ? 100 : (genTot > 0 ? Math.round(Math.max(0, (tot / genTot) * 100) * 10) / 10 : null);
		return { mkt, sup, center, bank, tot, score: sc };
	});

	function scoreBarStyle(sc) {
		if (sc == null) return 'display:none';
		const col = sc >= 70 ? '#0f6e56' : sc >= 45 ? '#854f0b' : '#9B1C1C';
		return `background:${col};width:${Math.round((sc * 40) / 100)}px`;
	}
	function scoreTextColor(sc) {
		return sc == null ? 'var(--color-text3)' : sc >= 70 ? '#0f6e56' : sc >= 45 ? '#854f0b' : '#9B1C1C';
	}

	const dongList = $derived(
		Object.entries(DONG_REACH).filter(([, v]) => v['구'] === cG)
			.map(([k, v]) => ({ key: k, dong: v['동'] }))
			.sort((a, b) => a.dong.localeCompare(b.dong, 'ko'))
	);

	function onGuChange(e) {
		const g = e.target.value;
		cG = g;
		const list = Object.entries(DONG_REACH).filter(([, v]) => v['구'] === g);
		if (list.length) cD = list[0][0];
	}
	function onDongChange(e) {
		cD = e.target.value;
		cG = (ALL_DONG_DATA[cD] || {}).gu || cG;
	}

	let mapEl = $state();
	let map;
	let L;
	let mktLyr, supLyr, bankLyr, centerLyr, radLyr;
	let cMark = null;
	/** @type {any} */
	let clickMark = null;
	/** @type {{lat:number, lng:number}|null} */
	let clickPoint = $state(null);
	/** @type {{mkt:number, sup:number, center:number, bank:number, tot:number, score:number|null}|null} */
	let clickReach = $state(null);
	/** @type {any} */
	let isoLayer = null;
	/** @type {any} */
	let graph = null;
	let graphLoading = $state(false);
	let graphError = $state('');
	let isoMeta = $state(/** @type {{count:number, ms:number}|null} */ (null));

	const layerTabs = [
		{ key: 'all', emoji: '🗺', label: '전체' },
		{ key: 'center', emoji: '🏛', label: '주민센터' },
		{ key: 'bank', emoji: '🏦', label: '은행' },
		{ key: 'market', emoji: '🛒', label: '전통시장' },
		{ key: 'super', emoji: '🏪', label: '슈퍼마켓' }
	];

	onMount(async () => {
		if (typeof window === 'undefined') return;
		L = (await import('leaflet')).default;
		await import('leaflet/dist/leaflet.css');
		map = L.map(mapEl, { zoomControl: true }).setView([37.5665, 126.978], 12);
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			attribution: '© CARTO', subdomains: 'abcd', maxZoom: 19, detectRetina: true
		}).addTo(map);

		mktLyr = L.layerGroup();
		supLyr = L.layerGroup();
		bankLyr = L.layerGroup();
		centerLyr = L.layerGroup();
		radLyr = L.layerGroup().addTo(map);

		MKT.forEach((m) => L.circleMarker([m.lat, m.lng], {
			radius: Math.max(4, Math.min(10, 4 + (m.stores || 0) / 200)),
			fillColor: '#1D9E75', color: '#fff', weight: 1.5, fillOpacity: 0.9
		}).bindPopup('<b>' + m.name + '</b><br>' + (m.type || '') + ' · ' + (m.stores || 0) + '개').addTo(mktLyr));

		SUP.forEach((s) => L.circleMarker([s.lat, s.lng], {
			radius: 3, fillColor: '#E8A838', color: '#fff', weight: 0.5, fillOpacity: 0.6
		}).bindPopup('<b>' + s.name + '</b><br>' + (s.type || '')).addTo(supLyr));

		SEOUL_BANKS.forEach((b) => L.circleMarker([b.lat, b.lng], {
			radius: 4, fillColor: '#7B5EA7', color: '#fff', weight: 0.8, fillOpacity: 0.85
		}).bindPopup('<b>' + b.name + '</b><br>' + (b.bank || '') + ' · ' + (b.gu || '')).addTo(bankLyr));

		CENTERS.forEach((c) => L.circleMarker([c.lat, c.lng], {
			radius: 5, fillColor: '#2563a8', color: '#fff', weight: 0.8, fillOpacity: 0.85
		}).bindPopup('<b>' + c.dong + '</b><br>' + c.gu + ' 주민센터').addTo(centerLyr));

		// 지도 클릭 → 클릭 지점 반경/isochrone + 가장 가까운 행정동 선택
		map.on('click', (e) => {
			const { lat, lng } = e.latlng;
			clickPoint = { lat, lng };
			if (clickMark) { map.removeLayer(clickMark); clickMark = null; }
			clickMark = L.circleMarker([lat, lng], {
				radius: 9, fillColor: '#ff3b30', color: '#fff',
				weight: 2.5, fillOpacity: 1, pane: 'markerPane'
			})
				.bindTooltip(`클릭 지점<br>${lat.toFixed(5)}, ${lng.toFixed(5)}`)
				.addTo(map);
			buildCanvasNearby(lat, lng, '클릭 지점');
			const w = WS[cW];
			const r = w.speed * (cSlope ? getToblerRatio(cD) : 1.0) * cT * 60;
			map.fitBounds(L.latLng(lat, lng).toBounds(r * 2), { padding: [30, 30], animate: true });
			radLyr.clearLayers();
			L.circle([lat, lng], {
				radius: r, color: w.color, weight: 1.2, dashArray: '5,5',
				fill: false, fillOpacity: 0
			})
				.bindTooltip('직선 반경 ' + Math.round(r).toLocaleString() + 'm (참고)')
				.addTo(radLyr);
			drawIsochrone(lat, lng, r, w.color);
			// 가장 가까운 행정동 선택 (click 마커는 유지)
			let minDist = Infinity, nearestKey = null;
			for (const [k, d] of Object.entries(/** @type {any} */ (ALL_DONG_DATA))) {
				if (!d.lat) continue;
				const dist = hav(lat, lng, d.lat, d.lng);
				if (dist < minDist) { minDist = dist; nearestKey = k; }
			}
			if (nearestKey) {
				fromMapClick = true;
				cG = /** @type {any} */ (ALL_DONG_DATA)[nearestKey].gu;
				cD = nearestKey;
			}
		});

		updateMap();
		setTimeout(() => map.invalidateSize(), 150);
	});

	onDestroy(() => {
		if (isoLayer) { isoLayer = null; }
		map?.remove();
	});

	function updateMap() {
		if (!map || !L) return;
		[mktLyr, supLyr, bankLyr, centerLyr].forEach((l) => { if (l && l._map) map.removeLayer(l); });
		if (cLayer === 'market' || cLayer === 'all') mktLyr.addTo(map);
		if (cLayer === 'super' || cLayer === 'all') supLyr.addTo(map);
		if (cLayer === 'bank' || cLayer === 'all') bankLyr.addTo(map);
		if (cLayer === 'center' || cLayer === 'all') centerLyr.addTo(map);

		radLyr.clearLayers();
		if (cMark) { map.removeLayer(cMark); cMark = null; }

		const w = WS[cW];
		let origin;

		if (untrack(() => cUnit) === 'gu') {
			const gc = guCenter(untrack(() => cG));
			if (!gc) return;
			const cp = untrack(() => clickPoint);
			origin = cp ?? gc;
			cMark = L.circleMarker([gc.lat, gc.lng], {
				radius: 10, fillColor: '#2c2c2a', color: '#fff', weight: 2.5, fillOpacity: 1
			}).bindPopup('<b>' + untrack(() => cG) + '</b><br>구 중심점').addTo(map);
		} else {
			const d = ALL_DONG_DATA[cD];
			if (!d || !d.lat) return;
			cMark = L.circleMarker([d.lat, d.lng], {
				radius: 10, fillColor: '#2c2c2a', color: '#fff', weight: 2.5, fillOpacity: 1
			}).bindPopup('<b>' + d.dong + '</b><br>65세+ ' + d.elder.toLocaleString() + '명').addTo(map);
			const cp = untrack(() => clickPoint);
			origin = cp ?? { lat: d.lat, lng: d.lng };
		}

		const r = w.speed * (cSlope ? getToblerRatio(cD) : 1.0) * cT * 60;
		map.fitBounds(L.latLng(origin.lat, origin.lng).toBounds(r * 2), { padding: [30, 30], animate: true });
		L.circle([origin.lat, origin.lng], {
			radius: r, color: w.color, weight: 1.2, dashArray: '5,5',
			fill: false, fillOpacity: 0
		}).bindTooltip('직선 반경 ' + Math.round(r).toLocaleString() + 'm (참고)').addTo(radLyr);

		// OSM 보행망 기반 실제 도달 폴리곤 (Convex Hull) — 비동기
		drawIsochrone(origin.lat, origin.lng, r, w.color);
	}

	/** OSM 그래프 → Dijkstra → Convex Hull 도달 폴리곤 */
	async function drawIsochrone(lat, lng, maxDistM, color) {
		if (!map || !L) return;
		// 이전 폴리곤 제거
		if (isoLayer) { map.removeLayer(isoLayer); isoLayer = null; }
		isoMeta = null;
		try {
			if (!graph) {
				graphLoading = true;
				graphError = '';
				graph = await loadGraph();
				graphLoading = false;
			}
			const { ring, count, ms } = computeIsochrone(graph, lat, lng, maxDistM);
			if (!ring) {
				graphError = '도달 노드 부족 — 다른 지점 선택';
				return;
			}
			isoLayer = L.polygon(ring, {
				color, weight: 2.5, opacity: 0.9,
				fillColor: color, fillOpacity: 0.18,
				smoothFactor: 1.2
			})
				.bindTooltip(
					`OSM 보행망 ${count.toLocaleString()} 노드 도달 · 폴리곤 계산 ${ms}ms`
				)
				.addTo(map);
			isoMeta = { count, ms };
			graphError = '';
		} catch (e) {
			console.error('[infra] isochrone failed', e);
			graphError = '그래프 로드 실패 — 직선 반경만 표시';
			graphLoading = false;
		}
	}

	let fromMapClick = false; // 지도 클릭으로 인한 cD 변경 시 click 마커 유지

	// 행정동 변경 또는 단위(자치구↔행정동) 전환 시 클릭 해제 (지도 클릭으로 인한 변경 제외)
	$effect(() => {
		cD; cUnit;
		if (fromMapClick) { fromMapClick = false; return; }
		if (clickMark && map) { map.removeLayer(clickMark); clickMark = null; }
		clickPoint = null;
	});

	function resetToCenter() {
		if (clickMark && map) { map.removeLayer(clickMark); clickMark = null; }
		clickPoint = null;
		if (map) updateMap();
	}

	// 클릭 지점 도달 가능 지점 계산 (직선 반경 기준)
	$effect(() => {
		const cp = clickPoint;
		cW; cT; cSlope;
		if (!cp) { clickReach = null; return; }
		const dongKey = untrack(() => cD);
		const r = WS[cW].speed * (cSlope ? getToblerRatio(dongKey) : 1.0) * cT * 60;
		const mkt    = MKT.filter(m => m.lat && hav(cp.lat, cp.lng, m.lat, m.lng) <= r).length;
		const sup    = SUP.filter(s => s.lat && hav(cp.lat, cp.lng, s.lat, s.lng) <= r).length;
		const center = CENTERS.filter(c => c.lat && hav(cp.lat, cp.lng, c.lat, c.lng) <= r).length;
		const bank   = SEOUL_BANKS.filter(b => b.lat && hav(cp.lat, cp.lng, b.lat, b.lng) <= r).length;
		const tot = mkt + sup + center + bank;
		// 일반인 기준 카운트 (score 분모)
		const generalWS = WS.find(w => w.id === 'general');
		const rGen = (generalWS?.speed ?? 1.28) * cT * 60;
		const genTot = MKT.filter(m => m.lat && hav(cp.lat, cp.lng, m.lat, m.lng) <= rGen).length
			+ SUP.filter(s => s.lat && hav(cp.lat, cp.lng, s.lat, s.lng) <= rGen).length
			+ CENTERS.filter(c => c.lat && hav(cp.lat, cp.lng, c.lat, c.lng) <= rGen).length
			+ SEOUL_BANKS.filter(b => b.lat && hav(cp.lat, cp.lng, b.lat, b.lng) <= rGen).length;
		const isGeneral = WS[cW].id === 'general';
		const score = isGeneral ? 100 : (genTot > 0 ? Math.round(Math.max(0, (tot / genTot) * 100) * 10) / 10 : null);
		clickReach = { mkt, sup, center, bank, tot, score };
	});

	$effect(() => {
		cLayer; cD; cW; cT; cSlope; cUnit; cG;
		if (map) updateMap();
	});

	let radarCanvas = $state();
	let radarZoom = $state(1);
	let panOffset = $state({ x: 0, y: 0 });
	/** @type {{ active: boolean, startX: number, startY: number, origX: number, origY: number }} */
	const _drag = { active: false, startX: 0, startY: 0, origX: 0, origY: 0 };
	let canvasNearby = $state({ markets: [], supers: [], banks: [], centers: [] });
	let canvasSrcLabel = $state('');

	function hav(lat1, lng1, lat2, lng2) {
		const R = 6371000, toR = Math.PI / 180;
		const dlat = (lat2 - lat1) * toR, dlng = (lng2 - lng1) * toR;
		const a = Math.sin(dlat/2)**2 + Math.cos(lat1*toR)*Math.cos(lat2*toR)*Math.sin(dlng/2)**2;
		return R * 2 * Math.asin(Math.sqrt(Math.min(a, 1)));
	}
	function brng(lat1, lng1, lat2, lng2) {
		const toR = Math.PI / 180, dLng = (lng2 - lng1) * toR;
		const y = Math.sin(dLng) * Math.cos(lat2*toR);
		const x = Math.cos(lat1*toR)*Math.sin(lat2*toR) - Math.sin(lat1*toR)*Math.cos(lat2*toR)*Math.cos(dLng);
		return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
	}
	function buildCanvasNearby(lat, lng, label) {
		canvasSrcLabel = label || '';
		const maxD = WS[0].speed * 45 * 60 * 1.2;
		const pick = (arr, n) => [...arr].sort((a, b) => a.dist - b.dist).slice(0, n);
		const mkts = [], sups = [], banks = [], centers = [];
		for (const m of MKT) { if (!m.lat || !m.lng) continue; const d = hav(lat, lng, m.lat, m.lng); if (d <= maxD) mkts.push({ name: m.name, dist: d, angle: brng(lat, lng, m.lat, m.lng) }); }
		for (const s of SUP) { if (!s.lat || !s.lng) continue; const d = hav(lat, lng, s.lat, s.lng); if (d <= maxD) sups.push({ name: s.name, dist: d, angle: brng(lat, lng, s.lat, s.lng) }); }
		for (const b of SEOUL_BANKS) { if (!b.lat || !b.lng) continue; const d = hav(lat, lng, b.lat, b.lng); if (d <= maxD) banks.push({ name: b.name + (b.bank ? ' (' + b.bank + ')' : ''), dist: d, angle: brng(lat, lng, b.lat, b.lng) }); }
		for (const cc of CENTERS) { if (!cc.lat || !cc.lng) continue; const d = hav(lat, lng, cc.lat, cc.lng); if (d <= maxD) centers.push({ name: cc.dong, dist: d, angle: brng(lat, lng, cc.lat, cc.lng) }); }
		canvasNearby = { markets: pick(mkts, 12), supers: pick(sups, 25), banks: pick(banks, 8), centers: pick(centers, 5) };
	}

	function drawRadar() {
		const cv = radarCanvas;
		if (!cv) return;
		const ctx = cv.getContext('2d');
		const W = cv.width, H = cv.height, cx = W/2, cy = H/2 + 10;
		ctx.clearRect(0, 0, W, H);
		ctx.save();
		ctx.translate(panOffset.x, panOffset.y);
		const w = WS[cW];
		const r_avg = w.speed * (cSlope ? getToblerRatio(cD) : 1.0) * cT * 60;
		const nb = canvasNearby;
		const allDists = [...nb.markets, ...nb.supers, ...nb.banks, ...nb.centers].map((x) => x.dist);
		const displayMax = Math.max(r_avg * 1.5, allDists.length > 2 ? [...allDists].sort((a, b) => a - b)[Math.min(10, allDists.length - 1)] * 1.2 : r_avg * 1.8);
		const sc = (Math.min(W, H) * 0.43) / displayMax * radarZoom;

		const gs = displayMax > 2000 ? 500 : displayMax > 1000 ? 300 : 150;
		for (let r = gs; r <= displayMax * 1.05; r += gs) {
			ctx.beginPath();
			ctx.arc(cx, cy, r * sc, 0, Math.PI * 2);
			ctx.strokeStyle = 'rgba(100,100,100,.07)';
			ctx.lineWidth = 0.7;
			ctx.stroke();
			ctx.font = '8px sans-serif';
			ctx.fillStyle = 'rgba(100,100,100,.4)';
			ctx.textAlign = 'left';
			ctx.fillText(r >= 1000 ? (r/1000).toFixed(1) + 'km' : r + 'm', cx + r*sc + 2, cy - 2);
		}

		const rt = cSlope ? getToblerRatio(cD) : 1.0;
		WS.forEach((ws, i) => {
			const ra = ws.speed * rt * cT * 60 * sc, sel = i === cW;
			ctx.beginPath();
			ctx.arc(cx, cy, ra, 0, Math.PI * 2);
			ctx.fillStyle = ws.color + (sel ? '15' : '07');
			ctx.fill();
			ctx.beginPath();
			ctx.arc(cx, cy, ra, 0, Math.PI * 2);
			ctx.strokeStyle = ws.color + (sel ? 'cc' : '33');
			ctx.lineWidth = sel ? 2 : 0.8;
			ctx.setLineDash(sel ? [] : [4, 3]);
			ctx.stroke();
			ctx.setLineDash([]);
			if (sel) {
				ctx.font = 'bold 10px sans-serif';
				ctx.fillStyle = ws.color;
				ctx.textAlign = 'right';
				ctx.fillText(Math.round(ws.speed * rt * cT * 60).toLocaleString() + 'm', cx + ra - 3, cy - 4);
			}
		});

		const placed = [];
		function noOverlap(x, y, w2, h2) {
			for (const p of placed) if (x < p[0]+p[2]+2 && x+w2 > p[0]-2 && y < p[1]+p[3]+2 && y+h2 > p[1]-2) return false;
			return true;
		}
		function drawLabel(text, x, y, color) {
			ctx.font = '8.5px sans-serif';
			const tw = ctx.measureText(text).width;
			const lx = x - tw/2, ly = y - 5;
			if (!noOverlap(lx, ly, tw, 10)) return;
			placed.push([lx, ly, tw, 10]);
			ctx.fillStyle = 'rgba(255,255,255,.88)';
			ctx.beginPath();
			if (ctx.roundRect) ctx.roundRect(lx-2, ly-1, tw+4, 11, 3); else ctx.rect(lx-2, ly-1, tw+4, 11);
			ctx.fill();
			ctx.fillStyle = color;
			ctx.textAlign = 'center';
			ctx.fillText(text, x, y + 5);
		}

		nb.supers.forEach((s) => {
			const ang = ((s.angle - 90) * Math.PI) / 180, r = s.dist * sc;
			const mx = cx + Math.cos(ang)*r, my = cy + Math.sin(ang)*r, reach = s.dist <= r_avg;
			ctx.beginPath();
			ctx.arc(mx, my, 2.5, 0, Math.PI * 2);
			ctx.fillStyle = reach ? '#E8A838' : '#E8A83855';
			ctx.fill();
		});
		nb.markets.forEach((m) => {
			const ang = ((m.angle - 90) * Math.PI) / 180, r = m.dist * sc;
			const mx = cx + Math.cos(ang)*r, my = cy + Math.sin(ang)*r, reach = m.dist <= r_avg;
			ctx.beginPath();
			ctx.arc(mx, my, reach ? 5.5 : 4, 0, Math.PI * 2);
			ctx.fillStyle = reach ? '#1D9E75' : '#aaa';
			ctx.fill();
			ctx.strokeStyle = '#fff';
			ctx.lineWidth = 1.2;
			ctx.stroke();
			drawLabel(m.name.length > 6 ? m.name.slice(0, 5) + '…' : m.name, mx, my + (my < cy ? -10 : 10), reach ? '#0a5240' : '#666');
		});
		nb.banks.forEach((b, i) => {
			const ang = ((b.angle - 90) * Math.PI) / 180, r = b.dist * sc;
			const mx = cx + Math.cos(ang)*r, my = cy + Math.sin(ang)*r, reach = b.dist <= r_avg, sz = 4;
			ctx.beginPath();
			ctx.rect(mx - sz, my - sz, sz * 2, sz * 2);
			ctx.fillStyle = reach ? '#7B5EA7' : '#7B5EA755';
			ctx.fill();
			ctx.strokeStyle = '#fff';
			ctx.lineWidth = 1;
			ctx.stroke();
			if (i < 5) drawLabel(b.name.split('(')[0].trim().slice(0, 6), mx, my + (my < cy ? -10 : 10), reach ? '#4a2080' : '#888');
		});
		nb.centers.forEach((cc) => {
			const ang = ((cc.angle - 90) * Math.PI) / 180, r = cc.dist * sc;
			const mx = cx + Math.cos(ang)*r, my = cy + Math.sin(ang)*r, reach = cc.dist <= r_avg, sz = 4.5;
			ctx.beginPath();
			ctx.rect(mx - sz, my - sz, sz * 2, sz * 2);
			ctx.fillStyle = reach ? '#2563a8' : '#2563a855';
			ctx.fill();
			ctx.strokeStyle = '#fff';
			ctx.lineWidth = 1;
			ctx.stroke();
			drawLabel(cc.name, mx, my + (my < cy ? -12 : 12), reach ? '#1a3d6e' : '#888');
		});

		ctx.beginPath();
		ctx.arc(cx, cy, 7, 0, Math.PI * 2);
		ctx.fillStyle = '#2c2c2a';
		ctx.fill();
		ctx.strokeStyle = '#fff';
		ctx.lineWidth = 2;
		ctx.stroke();

		const srcLabel = canvasSrcLabel || (cUnit === 'gu' ? cG : (/** @type {any} */ (ALL_DONG_DATA)[cD]?.dong || cG));
		ctx.font = 'bold 11px sans-serif';
		const tw2 = ctx.measureText(srcLabel).width;
		ctx.fillStyle = 'rgba(255,255,255,.88)';
		ctx.beginPath();
		if (ctx.roundRect) ctx.roundRect(cx - tw2/2 - 4, cy - 24, tw2 + 8, 14, 3); else ctx.rect(cx - tw2/2 - 4, cy - 24, tw2 + 8, 14);
		ctx.fill();
		ctx.fillStyle = '#2c2c2a';
		ctx.textAlign = 'center';
		ctx.fillText(srcLabel, cx, cy - 13);
		ctx.restore();
	}

	$effect(() => {
		const d = ALL_DONG_DATA[cD];
		const label = cUnit === 'gu' ? (d?.gu || cG) : d?.dong;
		if (d && d.lat) buildCanvasNearby(d.lat, d.lng, label);
	});
	$effect(() => {
		canvasNearby; cW; cT; cSlope; radarZoom; panOffset;
		if (radarCanvas) drawRadar();
	});

	$effect(() => {
		const cv = radarCanvas;
		if (!cv) return;
		const onWheel = (e) => {
			e.preventDefault();
			const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
			radarZoom = Math.max(0.2, Math.min(8, radarZoom * factor));
		};
		cv.addEventListener('wheel', onWheel, { passive: false });
		return () => cv.removeEventListener('wheel', onWheel);
	});

	$effect(() => {
		const cv = radarCanvas;
		if (!cv) return;
		cv.style.cursor = 'grab';
		const onDown = (e) => {
			_drag.active = true;
			_drag.startX = e.clientX;
			_drag.startY = e.clientY;
			_drag.origX = panOffset.x;
			_drag.origY = panOffset.y;
			cv.style.cursor = 'grabbing';
		};
		const onMove = (e) => {
			if (!_drag.active) return;
			panOffset = {
				x: _drag.origX + (e.clientX - _drag.startX),
				y: _drag.origY + (e.clientY - _drag.startY)
			};
		};
		const onUp = () => {
			if (!_drag.active) return;
			_drag.active = false;
			cv.style.cursor = 'grab';
		};
		cv.addEventListener('mousedown', onDown);
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
		return () => {
			cv.removeEventListener('mousedown', onDown);
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
	});

	let Chart;
	let gcChart, bankChart;
	let gcCanvas = $state();
	let bankCanvas = $state();

	onMount(async () => {
		const mod = await import('chart.js/auto');
		Chart = mod.default;
		renderBankChart();
		renderGc();
	});

	onDestroy(() => {
		gcChart?.destroy();
		bankChart?.destroy();
	});

	function renderGc() {
		if (!Chart || !gcCanvas) return;
		const w = WS[cW];
		const rows = Object.entries(DONG_REACH).filter(([, v]) => v['구'] === cG)
			.map(([k, v]) => {
				const wd = /** @type {any} */ (v)[w.id]?.[String(cT)] || {};
				return { key: k, dong: v['동'], mkt: wd.mkt || 0, sup: wd.sup || 0, bank: wd.bank || 0, center: wd.center || 0 };
			})
			.sort((a, b) => (b.mkt + b.sup + b.bank + b.center) - (a.mkt + a.sup + a.bank + a.center));
		const sel = cUnit === 'gu' ? null : (cD.split('_')[1] || '');
		gcChart?.destroy();
		gcChart = new Chart(gcCanvas, {
			type: 'bar',
			data: {
				labels: rows.map((r) => r.dong),
				datasets: [
					{ label: '전통시장', data: rows.map((r) => r.mkt), backgroundColor: rows.map((r) => !sel || r.dong === sel ? '#1D9E75' : '#1D9E754D'), stack: 'a' },
					{ label: '슈퍼마켓', data: rows.map((r) => r.sup), backgroundColor: rows.map((r) => !sel || r.dong === sel ? '#E8A838' : '#E8A8384D'), stack: 'a' },
					{ label: '은행', data: rows.map((r) => r.bank), backgroundColor: rows.map((r) => !sel || r.dong === sel ? '#7B5EA7' : '#7B5EA74D'), stack: 'a' },
					{ label: '주민센터', data: rows.map((r) => r.center), backgroundColor: rows.map((r) => !sel || r.dong === sel ? '#2563a8' : '#2563a84D'), stack: 'a' }
				]
			},
			options: {
				responsive: true, maintainAspectRatio: false, indexAxis: 'y', animation: false,
				plugins: { legend: { labels: { font: { size: 11 }, boxWidth: 12 } } },
				scales: {
					x: { stacked: true, beginAtZero: true, title: { display: true, text: '도달 시설 수', font: { size: 10 } } },
					y: { stacked: true, ticks: { font: { size: 9 } } }
				}
			}
		});
	}

	function renderBankChart() {
		if (!Chart || !bankCanvas) return;
		bankChart?.destroy();
		const datasets = [
			{ label: '서울 전체', data: BANK_SERIES.counts, borderColor: '#7B5EA7', backgroundColor: '#7B5EA715', fill: true, tension: 0.3, pointRadius: 2, pointBackgroundColor: '#7B5EA7', yAxisID: 'y' }
		];
		if (GU_BANK[cG]) {
			datasets.push({ label: cG, data: GU_BANK[cG], borderColor: '#D85A30', backgroundColor: '#D85A3015', fill: false, tension: 0.3, pointRadius: 2, pointBackgroundColor: '#D85A30', yAxisID: 'y1' });
		}
		bankChart = new Chart(bankCanvas, {
			type: 'line',
			data: { labels: GU_BANK_YEARS.map(String), datasets },
			options: {
				responsive: true, maintainAspectRatio: false, animation: false,
				plugins: { legend: { display: true, position: 'top', labels: { font: { size: 10 }, boxWidth: 10, padding: 6 } } },
				scales: {
					y: { beginAtZero: false, position: 'left', ticks: { callback: (v) => v.toLocaleString(), font: { size: 10 } }, title: { display: true, text: '서울 전체', font: { size: 9 } } },
					y1: { beginAtZero: false, position: 'right', grid: { drawOnChartArea: false }, ticks: { font: { size: 10 } }, title: { display: true, text: cG, font: { size: 9 } } },
					x: { ticks: { font: { size: 10 } } }
				}
			}
		});
	}

	$effect(() => { cW; cT; cG; cD; if (Chart && gcCanvas) renderGc(); });
	$effect(() => { cG; if (Chart && bankCanvas) renderBankChart(); });

	const tableRows = $derived.by(() => {
		const w = WS[cW];
		const rows = Object.entries(DONG_REACH).filter(([, v]) => v['구'] === cG)
			.map(([k, v]) => {
				const wd = /** @type {any} */ (v)[w.id]?.[String(cT)] || {};
				const genTot = /** @type {any} */ (v['general'])?.[String(cT)]?.tot ?? 0;
				const loss = wd.loss != null ? wd.loss : (genTot > 0 ? Math.max(0, (1 - (wd.tot || 0) / genTot) * 100) : null);
				return {
					key: k, dong: v['동'], gu: v['구'], elder: v['elder'],
					mkt: wd.mkt || 0, sup: wd.sup || 0, center: wd.center || 0, bank: wd.bank || 0,
					tot: wd.tot || 0, loss,
					score: calcScore(loss, k)
				};
			});
		rows.sort(compareBy(sortKeyDong, sortDirDong));
		return rows;
	});

	function setSortGu(/** @type {string} */ k) {
		({ sortKey: sortKeyGu, sortDir: sortDirGu } = applySort(k, sortKeyGu, sortDirGu, ['gu']));
	}
	function setSortDong(/** @type {string} */ k) {
		({ sortKey: sortKeyDong, sortDir: sortDirDong } = applySort(k, sortKeyDong, sortDirDong, ['gu', 'dong']));
	}

	const guRankRows = $derived.by(() => {
		const w = WS[cW];
		/** @type {Record<string, {scores: number[], elder: number, dongCount: number, mkt: number, sup: number, bank: number, center: number, tot: number}>} */
		const byGu = {};
		for (const [k, v] of Object.entries(DONG_REACH)) {
			const gu = /** @type {any} */ (v)['구'];
			if (!byGu[gu]) byGu[gu] = { scores: [], elder: 0, dongCount: 0, mkt: 0, sup: 0, bank: 0, center: 0, tot: 0 };
			const wd = /** @type {any} */ (v)[w.id]?.[String(cT)] || {};
			const genTot = /** @type {any} */ (v['general'])?.[String(cT)]?.tot ?? 0;
			const loss = wd.loss != null ? wd.loss : (genTot > 0 ? Math.max(0, (1 - (wd.tot || 0) / genTot) * 100) : null);
			const sc = calcScore(loss, k);
			if (sc != null) byGu[gu].scores.push(sc);
			byGu[gu].elder += (/** @type {any} */ (v)['elder'] || 0);
			byGu[gu].mkt += (wd.mkt || 0);
			byGu[gu].sup += (wd.sup || 0);
			byGu[gu].bank += (wd.bank || 0);
			byGu[gu].center += (wd.center || 0);
			byGu[gu].tot += (wd.tot || 0);
			byGu[gu].dongCount++;
		}
		const rows = Object.entries(byGu)
			.map(([gu, d]) => ({
				gu,
				score: d.scores.length ? parseFloat((d.scores.reduce((/** @type {number} */ a, /** @type {number} */ b) => a + b, 0) / d.scores.length).toFixed(1)) : null,
				elder: d.elder,
				dongCount: d.dongCount,
				mkt: Math.round(d.mkt / d.dongCount * 10) / 10,
				sup: Math.round(d.sup / d.dongCount * 10) / 10,
				bank: Math.round(d.bank / d.dongCount * 10) / 10,
				center: Math.round(d.center / d.dongCount * 10) / 10,
				tot: Math.round(d.tot / d.dongCount * 10) / 10,
			}));
		rows.sort(compareBy(sortKeyGu, sortDirGu));
		return rows;
	});

	function panToRow(r) {
		if (!map || !L) return;
		const d = ALL_DONG_DATA[r.key];
		if (!d || !d.lat) return;
		cD = r.key;
		map.setView([d.lat, d.lng], 14, { animate: true });
	}

	function guCenter(/** @type {string} */ gu) {
		const dongs = Object.values(ALL_DONG_DATA).filter((d) => /** @type {any} */ (d).gu === gu && d.lat && d.lng);
		if (!dongs.length) return null;
		const lat = dongs.reduce((s, d) => s + d.lat, 0) / dongs.length;
		const lng = dongs.reduce((s, d) => s + d.lng, 0) / dongs.length;
		return { lat, lng };
	}

	const bankPeak = $derived.by(() => {
		const c = BANK_SERIES.counts;
		const idx = c.indexOf(Math.max(...c));
		return { year: BANK_SERIES.years[idx], count: c[idx] };
	});
	const bankNow = $derived.by(() => {
		const n = BANK_SERIES.counts.length;
		return { year: BANK_SERIES.years[n - 1], count: BANK_SERIES.counts[n - 1] };
	});
	const bankDropPct = $derived((((bankPeak.count - bankNow.count) / bankPeak.count) * 100).toFixed(1));
</script>

<svelte:head>
	<title>③ 인프라 — 노인 생활인프라 접근성 분석</title>
</svelte:head>

<section class="infra-hero">
	<div class="hero-glow"></div>
	<div class="infra-hero-inner">
		<div class="hero-text">
			<p class="hero-kicker">③ 인프라 · 심재현</p>
			<h1 class="hero-title">
				노인 <em>생활인프라</em> 접근성
			</h1>
			<div class="hero-chips">
				<span class="chip teal">🛒 전통시장 195개소</span>
				<span class="chip teal">🏦 은행 1,579개소</span>
				<span class="chip teal">🏛 주민센터 426개소</span>
				<span class="chip teal">🏪 슈퍼마켓 31,024개소</span>
			</div>
		</div>
	</div>
</section>

<section class="wrap mx-auto px-[18px] pt-[18px] pb-[60px]" style:max-width="1340px">
	<div class="ctrl mb-4">
		<div class="crow">
			<span class="lbl">보행자 유형</span>
			{#each WS as w, i}
				<button type="button" class="btn bw" class:on={cW === i} onclick={() => (cW = i)}>
					{i === 0 ? '🚶' : i === 1 ? '🧓' : i === 2 ? '🦯' : '🦽'}
					{w.label} {w.speed} m/s
				</button>
			{/each}
		</div>

		<div class="crow">
			<span class="lbl">보행 시간</span>
			<button type="button" class="btn" class:on={cT === 15} onclick={() => (cT = 15)}>15분</button>
			<button type="button" class="btn" class:on={cT === 30} onclick={() => (cT = 30)}>30분</button>
			<button type="button" class="btn" class:on={cT === 45} onclick={() => (cT = 45)}>45분</button>
		</div>

		<div class="crow">
			<span class="lbl">행정 단위</span>
			<button type="button" class="btn" class:on={cUnit === 'gu'} onclick={() => (cUnit = 'gu')}>자치구</button>
			<button type="button" class="btn" class:on={cUnit === 'dong'} onclick={() => (cUnit = 'dong')}>행정동</button>
			<span class="crow-sep">|</span>
			<span class="lbl">레이어</span>
			<button type="button" class="chk-btn slope" class:on={cSlope} onclick={() => (cSlope = !cSlope)}>
				<span class="chk-dot" style="background:#3ecfa0"></span>경사 보정 (Tobler)
			</button>
			{#if cSlope && currentDong}
				<span class="text-[11px] tobler-tag">ratio {ratio.toFixed(3)} · {effSpeedDisplay} m/s</span>
			{/if}
		</div>

		<div class="crow">
			<span class="lbl">기준 지역</span>
			<select value={cG} onchange={onGuChange}>
				{#each GU_ORDER as g}
					<option value={g}>{g}</option>
				{/each}
			</select>
			{#if cUnit === 'dong'}
				<select value={cD} onchange={onDongChange}>
					{#each dongList as d}
						<option value={d.key}>{d.dong}</option>
					{/each}
				</select>
				{#if currentDong}
					<span class="text-[11px]" style:color="var(--color-text3)">
						65세+ {currentDong.elder.toLocaleString()}명 · centroid({currentDong.lat?.toFixed(4)}, {currentDong.lng?.toFixed(4)})
					</span>
				{/if}
			{/if}
		</div>

		<div class="mt-3">
			{#key cUnit + '|' + cG + '|' + cW + '|' + cSlope + '|' + (clickReach?.tot ?? '_')}
			<StatGrid cols={4}>
				{#if cUnit === 'gu'}
					<StatCard
						label="도달 가능 지점 (클릭 지점)"
						sub={clickReach ? '시장 ' + clickReach.mkt + ' · 슈퍼 ' + clickReach.sup + ' · 은행 ' + clickReach.bank + ' · 센터 ' + clickReach.center : '지도 클릭 시 표시'}
					>
						{#snippet children()}
							{#if clickReach}
								<CountUp value={+clickReach.tot} suffix="개소" />{#if cW !== 0 && clickReach.score != null}
									<span class="text-[14px] opacity-70"> (<CountUp value={+clickReach.score} decimals={1} suffix="점" />)</span>
								{/if}
							{:else}—{/if}
						{/snippet}
					</StatCard>
					<StatCard
						label={'도달 가능 지점 (' + cG + ' 중심점)'}
						sub={guReach ? '시장 ' + guReach.mkt + ' · 슈퍼 ' + guReach.sup + ' · 은행 ' + guReach.bank + ' · 센터 ' + guReach.center : '—'}
					>
						{#snippet children()}
							{#if guReach}<CountUp value={+guReach.tot} suffix="개소" />{:else}—{/if}
						{/snippet}
					</StatCard>
					<StatCard
						label="도달 가능 점수"
						sub={cW === 0 ? '노인 보행자 선택 시 표시' : '일반인 대비 도달가능 비율 (구 중심점)'}
						tone="green"
					>
						{#snippet children()}
							{#if cW === 0 || guReach?.score == null}—{:else}<CountUp value={+guReach.score} decimals={1} suffix="점" />{/if}
						{/snippet}
					</StatCard>
					<StatCard
						label="65세+ 인구"
						sub={cG + ' 주민센터 ' + (CENTER_BY_GU[cG] || 0) + '개소'}
						tone="blue"
					>
						{#snippet children()}
							{@const el = guRankRows.find((r) => r.gu === cG)?.elder}
							{#if el != null}<CountUp value={+el} suffix="명" />{:else}—{/if}
						{/snippet}
					</StatCard>
				{:else}
					<StatCard
						label="도달 가능 지점 (클릭 지점)"
						sub={clickReach ? '시장 ' + clickReach.mkt + ' · 슈퍼 ' + clickReach.sup + ' · 은행 ' + clickReach.bank + ' · 센터 ' + clickReach.center : '지도 클릭 시 표시'}
					>
						{#snippet children()}
							{#if clickReach}
								<CountUp value={+clickReach.tot} suffix="개소" />{#if cW !== 0 && clickReach.score != null}
									<span class="text-[14px] opacity-70"> (<CountUp value={+clickReach.score} decimals={1} suffix="점" />)</span>
								{/if}
							{:else}—{/if}
						{/snippet}
					</StatCard>
					<StatCard
						label="도달 가능 지점 (동 중심점)"
						sub={'시장 ' + (wReach?.mkt ?? 0) + ' · 슈퍼 ' + (wReach?.sup ?? 0) + ' · 은행 ' + (wReach?.bank ?? 0) + ' · 센터 ' + (wReach?.center ?? 0)}
					>
						{#snippet children()}
							{#if wReach}<CountUp value={+(wReach.tot ?? 0)} suffix="개소" />{:else}—{/if}
						{/snippet}
					</StatCard>
					<StatCard
						label="도달 가능 점수"
						sub={cW === 0 ? '노인 보행자 선택 시 표시' : (cSlope ? '경사 보정 반영' : '일반인 대비 도달가능 비율')}
						tone="green"
					>
						{#snippet children()}
							{#if cW === 0 || score == null}—{:else}<CountUp value={+score} decimals={1} suffix="점" />{/if}
						{/snippet}
					</StatCard>
					<StatCard
						label="65세+ 인구"
						sub={cG + ' 주민센터 ' + (CENTER_BY_GU[cG] || 0) + '개소'}
						tone="blue"
					>
						{#snippet children()}
							{#if currentDong}<CountUp value={+currentDong.elder} suffix="명" />{:else}—{/if}
						{/snippet}
					</StatCard>
				{/if}
			</StatGrid>
			{/key}
		</div>
	</div>

	<div class="r-map mb-4">
		<Card title="서울시 생활 인프라 분포">
			<div class="iso-meta-row">
				<PillTabs tabs={layerTabs} value={cLayer} onChange={(k) => (cLayer = k)} class="mb-2" />
				<div class="iso-meta">
					{#if graphLoading}
						<span class="iso-loading">⚙ OSM 보행망 로드 중…</span>
					{:else if graphError}
						<span class="iso-err">⚠ {graphError}</span>
					{:else if isoMeta}
						<span class="iso-ok">OSM 보행망 <b>{isoMeta.count.toLocaleString()}</b> 노드 도달 · {isoMeta.ms}ms</span>
					{/if}
				</div>
			</div>
			<MapShell
				height="460px"
				legend={[
					{ color: '#1D9E75', label: '전통시장', shape: 'circle' },
					{ color: '#E8A838', label: '슈퍼마켓', shape: 'circle' },
					{ color: '#7B5EA7', label: '은행', shape: 'circle' },
					{ color: '#2563a8', label: '주민센터', shape: 'circle' }
				]}
				source={"출처: 소상공인시장진흥공단 · 금융감독원 · 행정안전부 · OpenStreetMap (266,780 노드)\n점선 = 직선 반경 · 채워진 폴리곤 = OSM 보행망 Dijkstra + Convex Hull 도달 범위"}
			>
				<div bind:this={mapEl} class="absolute inset-0"></div>
				{#if clickPoint}
					<button type="button" class="map-reset-btn" onclick={resetToCenter}>중심점</button>
				{/if}
			</MapShell>
		</Card>

		<Card title="보행 반경 모식도">
			<div class="radar-sub">
				{canvasSrcLabel || (cUnit === 'gu' ? cG : (currentDong ? currentDong.dong : cG))} · {cT}분 보행반경{cSlope ? ' · 경사보정' : ''}
			</div>
			<div class="radar-radius">
				{currentW.label} · {Math.round(currentW.speed * ratio * cT * 60).toLocaleString()} m
			</div>
			<canvas bind:this={radarCanvas} width="340" height="340" class="radar-canvas"></canvas>
			<div class="radar-zoom-row">
				{#if radarZoom !== 1 || panOffset.x !== 0 || panOffset.y !== 0}
					{#if radarZoom !== 1}<span class="radar-zoom-pct">{Math.round(radarZoom * 100)}%</span>{/if}
					<button type="button" class="radar-zoom-reset" onclick={() => { radarZoom = 1; panOffset = { x: 0, y: 0 }; }}>초기화</button>
				{:else}
					<span class="radar-zoom-hint">휠 줌 · 드래그 이동</span>
				{/if}
			</div>
			<div class="radar-leg">
				<div class="leg-row">
					{#each WS as ws, i}
						<div class="leg-it">
							<span class="leg-dot" style:background={ws.color} style:opacity={i === cW ? 1 : 0.3}></span>{ws.label}
						</div>
					{/each}
				</div>
				<div class="leg-row">
					<div class="leg-it"><span class="leg-dot" style:background="#1D9E75"></span>전통시장</div>
					<div class="leg-it"><span class="leg-dot" style:background="#E8A838"></span>슈퍼마켓</div>
					<div class="leg-it"><span class="leg-dot" style:background="#7B5EA7"></span>은행</div>
					<div class="leg-it"><span class="leg-dot" style:background="#2563a8"></span>주민센터</div>
				</div>
			</div>
		</Card>
	</div>

	<div class="r-charts mb-4">
		<Card title={'행정동 도달 시설 수 — ' + cG + ' 행정동별'}>
			<div class="chart-h">
				<canvas bind:this={gcCanvas} class="block h-full w-full"></canvas>
			</div>
		</Card>

		<Card title={'서울 은행 점포 감소 ' + BANK_SERIES.years[0] + '→' + bankNow.year}>
			<div class="bstats">
				<div class="bst">
					<div class="bst-n" style:color="#185FA5">{bankPeak.count.toLocaleString()}</div>
					<div class="bst-l">{bankPeak.year}년 피크</div>
				</div>
				<div class="bst">
					<div class="bst-n" style:color="#9B1C1C">{bankNow.count.toLocaleString()}</div>
					<div class="bst-l">{bankNow.year}년 현재</div>
				</div>
				<div class="bst">
					<div class="bst-n" style:color="#D85A30">▼{bankDropPct}%</div>
					<div class="bst-l">피크 대비 감소</div>
				</div>
			</div>
			<div class="bank-chart-h">
				<canvas bind:this={bankCanvas} class="block h-full w-full"></canvas>
			</div>
			<p class="src-note">
				출처: 금융감독원 주요금융기관별 점포수 · 일반+특수은행 서울 합산 / 자치구별 보조축
			</p>
		</Card>
	</div>

	<Card title={cUnit === 'gu' ? '자치구별 접근가능 점수 순위 — ' + currentW.label + ' · ' + cT + '분' : '서울 행정동 생활인프라 접근성 — ' + currentW.label + ' · ' + cG + ' 행정동'} class="mb-4">
		<div class="tbl-outer" style="position:relative">
			{#if cUnit === 'gu'}
				<div class="tbl-wrap">
					<table>
						<thead>
							<tr>
								<th class="rank-th">순위</th>
								{#each [{ k: 'gu', label: '자치구' },{ k: 'mkt', label: '전통시장' },{ k: 'sup', label: '슈퍼' },{ k: 'bank', label: '은행' },{ k: 'center', label: '주민센터' },{ k: 'tot', label: '합계' },{ k: 'elder', label: '65세+' },{ k: 'score', label: '도달가능점수 (동 평균)' }] as col}
									<th class="th-sort" class:active={sortKeyGu === col.k} onclick={() => setSortGu(col.k)}>
										{col.label}
										{#if sortKeyGu === col.k}<span class="sort-arr">{sortDirGu === 'desc' ? '▼' : '▲'}</span>{/if}
									</th>
								{/each}
								<th>도달가능</th>
							</tr>
						</thead>
						<tbody>
							{#each guRankRows as r, i}
								{@const accessCls = (r.score ?? 0) >= 70 ? 'phi' : (r.score ?? 0) >= 45 ? 'pmd' : 'plo'}
								{@const accessLabel = (r.score ?? 0) >= 70 ? '양호' : (r.score ?? 0) >= 45 ? '보통' : '미흡'}
								<tr class:hl={r.gu === cG} onclick={() => (cG = r.gu)}>
									<td class="rank-num" style:color={i === 0 ? 'var(--color-teal)' : i < 3 ? 'var(--color-text2)' : undefined}>{i + 1}</td>
									<td style="font-weight:500">{r.gu}</td>
									<td>{r.mkt}</td>
									<td>{r.sup}</td>
									<td>{r.bank}</td>
									<td>{r.center}</td>
									<td>{r.tot}</td>
									<td>{r.elder.toLocaleString()}</td>
									<td>
										<b class="score-val" style:color={scoreTextColor(r.score)}>{r.score != null ? r.score.toFixed(1) + '점' : 'N/A'}</b>
										<span class="score-bar" style={scoreBarStyle(r.score)}></span>
									</td>
									<td><span class="pill {accessCls}">{accessLabel}</span></td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div class="tbl-wrap">
					<table>
						<thead>
							<tr>
								{#each [{ k: 'gu', label: '자치구' },{ k: 'dong', label: '행정동' },{ k: 'mkt', label: '전통시장' },{ k: 'sup', label: '슈퍼' },{ k: 'bank', label: '은행' },{ k: 'center', label: '주민센터' },{ k: 'tot', label: '합계' },{ k: 'elder', label: '65세+' },{ k: 'score', label: '도달 가능 점수' }] as col}
									<th class="th-sort" class:active={sortKeyDong === col.k} onclick={() => setSortDong(col.k)}>
										{col.label}
										{#if sortKeyDong === col.k}<span class="sort-arr">{sortDirDong === 'desc' ? '▼' : '▲'}</span>{/if}
									</th>
								{/each}
								<th>도달가능</th>
							</tr>
						</thead>
						<tbody>
							{#each tableRows as r}
								{@const accessCls = (r.score ?? 0) >= 70 ? 'phi' : (r.score ?? 0) >= 45 ? 'pmd' : 'plo'}
								{@const accessLabel = (r.score ?? 0) >= 70 ? '양호' : (r.score ?? 0) >= 45 ? '보통' : '미흡'}
								<tr class:hl={r.key === cD} onclick={() => panToRow(r)}>
									<td>{r.gu}</td>
									<td>{r.dong}</td>
									<td>{r.mkt}</td>
									<td>{r.sup}</td>
									<td>{r.bank}</td>
									<td>{r.center}</td>
									<td>{r.tot}</td>
									<td>{r.elder.toLocaleString()}</td>
									<td>
										<b class="score-val" style:color={scoreTextColor(r.score)}>{r.score != null ? r.score.toFixed(1) + '점' : 'N/A'}</b>
										<span class="score-bar" style={scoreBarStyle(r.score)}></span>
									</td>
									<td><span class="pill {accessCls}">{accessLabel}</span></td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
			{#if cW === 0}
				<div class="tbl-overlay">
					<div style="font-size:28px">📋</div>
					<div style="font-size:13px;font-weight:500;color:#5f5e5a">보행자 유형을 선택하세요</div>
					<div class="tbl-overlay-sub">일반인은 비교 기준값(분모)이므로<br />모든 구가 <b>100점</b> — 비교 의미 없음</div>
				</div>
			{/if}
		</div>
	</Card>

	<Note tone="cool" class="mb-4">
		※ 도달가능점수 = (선택 유형 도달 시설 수 / 일반인 도달 시설 수) × 100<br />
		※ 보행자 유형: 일반인 1.28 · 일반 노인 1.12 · 보행보조 노인 0.88 · 보행보조 하위15% 0.70 m/s<br />
		※ 경사 보정: {cSlope ? 'Tobler hiking function 기반 동별 속도 보정 (tobler_ratio_LEE.csv, LEE 2026)' : '평지 기준 (보정 없음)'}<br />
		※ 거리 측정: 행정동 centroid 기준 OSM 보행 네트워크(다익스트라) · 시설: 전통시장 · 슈퍼마켓 · 은행 · 주민센터
	</Note>
</section>

<style>
	.iso-meta-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		flex-wrap: wrap;
	}
	.iso-meta {
		font-family: var(--font-mono);
		font-size: 10.5px;
		color: var(--color-text3);
		letter-spacing: 0.04em;
		min-height: 16px;
	}
	.iso-loading {
		color: var(--color-text3);
		opacity: 0.85;
	}
	.iso-err {
		color: #c0392b;
	}
	.iso-ok b {
		color: var(--color-text);
		font-weight: 600;
	}
	.infra-hero {
		position: relative;
		background: var(--color-dark);
		color: var(--color-dark-text);
		padding: 22px 28px;
		overflow: hidden;
	}
	.hero-glow {
		pointer-events: none;
		position: absolute;
		top: -60px;
		right: -80px;
		width: 340px;
		height: 340px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(62,207,160,0.18), transparent 65%);
	}
	.infra-hero-inner {
		position: relative;
		max-width: 1340px;
		margin: 0 auto;
	}
	.hero-kicker {
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-teal);
		opacity: 0.85;
		margin-bottom: 8px;
	}
	.hero-title {
		font-family: var(--font-display);
		font-size: 26px;
		line-height: 1.2;
		margin-bottom: 12px;
		color: var(--color-dark-text);
	}
	.hero-title em {
		font-style: normal;
		color: var(--color-teal);
	}
	.hero-chips {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}
	.chip {
		font-size: 11px;
		padding: 3px 9px;
		border-radius: 12px;
		background: rgba(255,255,255,0.07);
		color: rgba(241,239,232,0.65);
		white-space: nowrap;
	}
	.chip.teal {
		background: rgba(62,207,160,0.15);
		color: #3ecfa0;
		border: 0.5px solid rgba(62,207,160,0.3);
	}
	.chip.muted {
		background: transparent;
		color: rgba(241,239,232,0.35);
	}
	.chip-sep {
		color: rgba(241,239,232,0.25);
		font-size: 11px;
	}
	.ctrl {
		background: var(--color-card);
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 16px 20px;
	}
	.crow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
	.crow:last-child { margin-bottom: 0; }
	.crow-sep { color: var(--color-border); margin: 0 2px; font-size: 14px; }
	.lbl { font-size: 11px; font-weight: 500; letter-spacing: 0.06em; color: var(--color-text3); white-space: nowrap; margin-right: 2px; }
	select { font-size: 12px; padding: 5px 10px; border-radius: 8px; border: 0.5px solid var(--color-text4); background: #fff; color: var(--color-text); font-family: inherit; cursor: pointer; outline: none; }
	select:focus { border-color: var(--color-text2); }
	.btn { font-size: 12px; padding: 5px 14px; border-radius: 20px; border: 0.5px solid var(--color-text4); background: transparent; color: var(--color-text2); cursor: pointer; transition: all 0.14s; font-family: inherit; white-space: nowrap; }
	.btn:hover { border-color: var(--color-text2); color: var(--color-text); }
	.btn.on { background: var(--pill-accent, var(--color-dark)); color: var(--pill-on-text, var(--color-dark-text)); border-color: var(--pill-accent, var(--color-dark)); }
	.btn.bw { border-radius: 8px; }
	.chk-btn { font-size: 12px; padding: 5px 13px; border-radius: 20px; border: 0.5px solid var(--color-text4); background: transparent; color: var(--color-text2); cursor: pointer; transition: all 0.14s; font-family: inherit; white-space: nowrap; display: inline-flex; align-items: center; gap: 5px; }
	.chk-btn:hover { border-color: var(--color-text2); color: var(--color-text); }
	.chk-btn.slope.on { background: #edfaf5; border-color: #3ecfa0; color: #0f6e56; }
	.chk-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.tobler-tag { font-family: var(--font-mono); padding: 2px 8px; border-radius: 10px; color: var(--color-slope); background: color-mix(in srgb, var(--color-slope) 10%, transparent); }

	.r-map { display: grid; grid-template-columns: 1.4fr 1fr; gap: 12px; }
	@media (max-width: 1100px) { .r-map { grid-template-columns: 1fr; } }
	.radar-sub { font-size: 12px; color: var(--color-text2); margin-bottom: 4px; }
	.radar-radius { font-family: var(--font-mono); font-size: 13px; font-weight: 600; color: var(--color-text); text-align: center; margin-bottom: 8px; }
	.radar-canvas { display: block; width: 100%; max-width: 340px; margin: 0 auto; cursor: grab; }
	.radar-zoom-row { display: flex; align-items: center; justify-content: center; gap: 6px; margin: 4px 0 2px; min-height: 20px; }
	.radar-zoom-hint { font-size: 10px; color: var(--color-text4); letter-spacing: 0.04em; }
	.radar-zoom-pct { font-family: var(--font-mono); font-size: 11px; color: var(--color-teal); font-weight: 600; }
	.radar-zoom-reset { font-size: 10px; padding: 2px 8px; border-radius: 8px; border: 0.5px solid var(--color-text4); background: transparent; color: var(--color-text3); cursor: pointer; font-family: inherit; transition: all 0.12s; }
	.radar-zoom-reset:hover { border-color: var(--color-text2); color: var(--color-text); }
	.radar-leg { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; align-items: center; }
	.leg-row { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; font-size: 11px; color: var(--color-text2); }
	.leg-it { display: inline-flex; align-items: center; gap: 4px; }
	.leg-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.leg-dot.leg-sq { border-radius: 2px; }

	.r-charts { display: grid; grid-template-columns: 1.4fr 1fr; gap: 12px; }
	@media (max-width: 1100px) { .r-charts { grid-template-columns: 1fr; } }
	.chart-h { position: relative; height: 380px; }
	.bank-chart-h { position: relative; height: 200px; margin-top: 12px; }
	.bstats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
	.bst { text-align: center; padding: 10px 6px; background: var(--color-card-soft); border-radius: 6px; }
	.bst-n { font-family: var(--font-mono); font-size: 22px; font-weight: 500; line-height: 1.2; }
	.bst-l { font-size: 10px; color: var(--color-text3); margin-top: 2px; }
	.src-note { margin-top: 8px; font-size: 11px; color: var(--color-text3); }

	.tbl-wrap { max-height: 520px; overflow-y: auto; }
	table { width: 100%; font-size: 12px; border-collapse: collapse; }
	thead { position: sticky; top: 0; background: #fff; z-index: 1; }
	th { text-align: left; font-weight: 500; font-size: 11px; color: var(--color-text3); padding: 8px 10px; border-bottom: 0.5px solid var(--color-border); white-space: nowrap; }
	/* 정렬 화살표 공간 확보 — Svelte scoped CSS 가 layout.css .th-sort 보다 specific */
	th.th-sort { padding-right: 24px; position: relative; }
	td { padding: 7px 10px; border-bottom: 0.5px solid var(--color-border-soft); }
	tbody tr { cursor: pointer; }
	tr:hover td { background: #fafaf8; }
	tr.hl td { background: var(--color-bg2); font-weight: 500; }
	.map-reset-btn {
		position: absolute;
		top: 10px;
		right: 10px;
		z-index: 1000;
		padding: 5px 12px;
		border-radius: 6px;
		border: 0.5px solid var(--color-border);
		background: rgba(255,255,255,0.92);
		backdrop-filter: blur(4px);
		font-size: 12px;
		font-family: inherit;
		color: var(--color-text);
		cursor: pointer;
		box-shadow: 0 1px 4px rgba(0,0,0,0.12);
		transition: background 0.14s;
	}
	.map-reset-btn:hover { background: #fff; }

	.tbl-overlay {
		position: absolute;
		inset: 0;
		border-radius: 8px;
		background: rgba(245, 244, 240, 0.92);
		backdrop-filter: blur(3px);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 10px;
		padding: 20px;
	}
	.tbl-overlay-sub {
		font-size: 11px;
		color: #aaa9a5;
		text-align: center;
		line-height: 1.7;
		background: #fff;
		border-radius: 8px;
		padding: 8px 14px;
	}

	.rank-th { width: 36px; text-align: center; }
	.rank-num { text-align: center; font-family: var(--font-mono); font-size: 11px; color: var(--color-text3); font-weight: 600; }

	.score-val { display: inline-block; min-width: 46px; font-family: var(--font-mono); font-size: 11px; }
	.score-bar { display: inline-block; height: 5px; border-radius: 3px; margin-left: 4px; vertical-align: middle; }
	.pill { display: inline-block; font-size: 11px; padding: 1px 8px; border-radius: 10px; font-weight: 500; }
	.pill.phi { background: #2e7d3218; color: #2e7d32; }
	.pill.pmd { background: #f57f1718; color: #f57f17; }
	.pill.plo { background: #c6282818; color: #c62828; }
</style>
