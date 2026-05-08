<script>
	import { onMount, onDestroy } from 'svelte';
	import infraData from '$lib/data/infra.json';
	import Card from '$lib/components/Card.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MapShell from '$lib/components/MapShell.svelte';
	import PillButton from '$lib/components/PillButton.svelte';
	import PillTabs from '$lib/components/PillTabs.svelte';
	import Note from '$lib/components/Note.svelte';

	const {
		ALL_DONG_DATA, BANK_SERIES, GU_BANK, GU_BANK_YEARS, CENTERS, CENTER_BY_GU,
		DONG_REACH, MKT, SUP, SEOUL_BANKS, TOBLER_DONG, TOP10_VULNERABLE, WS
	} = infraData;

	const GU_ORDER = [
		'종로구', '중구', '용산구', '성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '도봉구', '노원구', '은평구', '서대문구', '마포구', '양천구', '강서구', '구로구', '금천구', '영등포구', '동작구', '관악구', '서초구', '강남구', '송파구', '강동구'
	];

	let cW = $state(0);
	let cT = $state(15);
	let cG = $state('중구');
	let cD = $state('중구_소공동');
	let cSlope = $state(false);
	let cLayer = $state('all');
	let sortKey = $state('tot');
	let sortDir = $state('desc');

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
		const pts = [
			{ s: 1.28, sc: 100 - (dr.general?.loss ?? 0) },
			{ s: 1.12, sc: 100 - (dr.senior?.loss ?? 0) },
			{ s: 0.88, sc: 100 - (dr.aided?.loss ?? 0) },
			{ s: 0.7, sc: 100 - (dr.aided15?.loss ?? 0) }
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
	const wReach = $derived(currentReach ? currentReach[currentW.id] : null);
	const ratio = $derived(cSlope ? getToblerRatio(cD) : 1.0);
	const radiusM = $derived(Math.round(currentW.speed * ratio * cT * 60));
	const effSpeedDisplay = $derived((currentW.speed * ratio).toFixed(2));
	const score = $derived(wReach ? calcScore(wReach.loss, cD) : null);
	const scoreColor = $derived(score == null ? '#2c2c2a' : score >= 70 ? '#0f6e56' : score >= 45 ? '#854f0b' : '#9B1C1C');

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
		map = L.map(mapEl, { zoomControl: true }).setView([37.5665, 126.978], 11);
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

		updateMap();
		setTimeout(() => map.invalidateSize(), 150);
	});

	onDestroy(() => map?.remove());

	function updateMap() {
		if (!map || !L) return;
		[mktLyr, supLyr, bankLyr, centerLyr].forEach((l) => { if (l && l._map) map.removeLayer(l); });
		if (cLayer === 'market' || cLayer === 'all') mktLyr.addTo(map);
		if (cLayer === 'super' || cLayer === 'all') supLyr.addTo(map);
		if (cLayer === 'bank' || cLayer === 'all') bankLyr.addTo(map);
		if (cLayer === 'center' || cLayer === 'all') centerLyr.addTo(map);

		radLyr.clearLayers();
		if (cMark) { map.removeLayer(cMark); cMark = null; }
		const d = ALL_DONG_DATA[cD];
		if (!d || !d.lat) return;
		cMark = L.circleMarker([d.lat, d.lng], {
			radius: 10, fillColor: '#2c2c2a', color: '#fff', weight: 2.5, fillOpacity: 1
		}).bindPopup('<b>' + d.dong + '</b><br>65세+ ' + d.elder.toLocaleString() + '명').addTo(map);
		map.panTo([d.lat, d.lng]);

		const w = WS[cW];
		const r = w.speed * (cSlope ? getToblerRatio(cD) : 1.0) * cT * 60;
		L.circle([d.lat, d.lng], {
			radius: r, color: w.color, weight: 2, fill: true, fillColor: w.color, fillOpacity: 0.07
		}).bindTooltip(w.label + ' ' + Math.round(r).toLocaleString() + 'm' + (cSlope ? ' (경사보정)' : '')).addTo(radLyr);
	}

	$effect(() => {
		cLayer; cD; cW; cT; cSlope;
		if (map) updateMap();
	});

	let radarCanvas = $state();
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
		const w = WS[cW];
		const r_avg = w.speed * (cSlope ? getToblerRatio(cD) : 1.0) * cT * 60;
		const nb = canvasNearby;
		const allDists = [...nb.markets, ...nb.supers, ...nb.banks, ...nb.centers].map((x) => x.dist);
		const displayMax = Math.max(r_avg * 1.5, allDists.length > 2 ? [...allDists].sort((a, b) => a - b)[Math.min(10, allDists.length - 1)] * 1.2 : r_avg * 1.8);
		const sc = (Math.min(W, H) * 0.43) / displayMax;

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

		const srcLabel = canvasSrcLabel || (ALL_DONG_DATA[cD] ? ALL_DONG_DATA[cD].dong : cG);
		ctx.font = 'bold 11px sans-serif';
		const tw2 = ctx.measureText(srcLabel).width;
		ctx.fillStyle = 'rgba(255,255,255,.88)';
		ctx.beginPath();
		if (ctx.roundRect) ctx.roundRect(cx - tw2/2 - 4, cy - 24, tw2 + 8, 14, 3); else ctx.rect(cx - tw2/2 - 4, cy - 24, tw2 + 8, 14);
		ctx.fill();
		ctx.fillStyle = '#2c2c2a';
		ctx.textAlign = 'center';
		ctx.fillText(srcLabel, cx, cy - 13);
		ctx.font = 'bold 10px sans-serif';
		ctx.fillStyle = w.color;
		ctx.textAlign = 'center';
		ctx.fillText(w.label + ' ' + Math.round(r_avg).toLocaleString() + 'm', cx, 12);
	}

	$effect(() => {
		const d = ALL_DONG_DATA[cD];
		if (d && d.lat) buildCanvasNearby(d.lat, d.lng, d.dong);
	});
	$effect(() => {
		canvasNearby; cW; cT; cSlope;
		if (radarCanvas) drawRadar();
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
			.map(([k, v]) => { const wd = v[w.id] || {}; return { key: k, dong: v['동'], mkt: wd.mkt || 0, sup: wd.sup || 0 }; })
			.sort((a, b) => b.mkt + b.sup - (a.mkt + a.sup));
		const sel = cD.split('_')[1] || '';
		gcChart?.destroy();
		gcChart = new Chart(gcCanvas, {
			type: 'bar',
			data: {
				labels: rows.map((r) => r.dong),
				datasets: [
					{ label: '전통시장', data: rows.map((r) => r.mkt), backgroundColor: rows.map((r) => r.dong === sel ? '#1D9E75' : '#1D9E7540'), stack: 'a' },
					{ label: '슈퍼마켓', data: rows.map((r) => r.sup), backgroundColor: rows.map((r) => r.dong === sel ? '#E8A838' : '#E8A83840'), stack: 'a' }
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

	$effect(() => { cW; cG; cD; if (Chart && gcCanvas) renderGc(); });
	$effect(() => { cG; if (Chart && bankCanvas) renderBankChart(); });

	const tableRows = $derived.by(() => {
		const w = WS[cW];
		const rows = Object.entries(DONG_REACH).filter(([, v]) => v['구'] === cG)
			.map(([k, v]) => {
				const wd = v[w.id] || {};
				return {
					key: k, dong: v['동'], gu: v['구'], elder: v['elder'],
					mkt: wd.mkt || 0, sup: wd.sup || 0, tot: wd.tot || 0, loss: wd.loss || 0,
					score: calcScore(wd.loss || 0, k)
				};
			});
		const dir = sortDir === 'desc' ? -1 : 1;
		rows.sort((a, b) => {
			const av = a[sortKey], bv = b[sortKey];
			if (typeof av === 'string') return av.localeCompare(bv, 'ko') * dir;
			return ((av || 0) - (bv || 0)) * dir;
		});
		return rows;
	});

	function setSort(k) {
		if (sortKey === k) sortDir = sortDir === 'desc' ? 'asc' : 'desc';
		else { sortKey = k; sortDir = (k === 'dong' || k === 'gu') ? 'asc' : 'desc'; }
	}

	function panToRow(r) {
		if (!map || !L) return;
		const d = ALL_DONG_DATA[r.key];
		if (!d || !d.lat) return;
		cD = r.key;
		map.setView([d.lat, d.lng], 14, { animate: true });
	}

	const top10MaxImpact = TOP10_VULNERABLE[0]?.impact || 1;
	const top10Colors = ['#9B1C1C','#b02020','#c03030','#c54040','#ca5050','#7c2d12','#922f12','#a33515','#b34018','#c04c20'];

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
	<title>④ 생활 인프라 — 노인 보행일상권 분석</title>
</svelte:head>

<section class="infra-hero">
	<div class="infra-hero-inner">
		<div class="hero-text">
			<p class="hero-kicker">SHIM · 행정동 단위 · 도달가능점수</p>
			<h1 class="hero-title">④ 생활 인프라 — 노인 보행일상권 분석</h1>
			<p class="hero-sub">
				전통시장 195개소 · 슈퍼/식료품 31,024개소 · 은행 1,579개소 · 주민센터 426개소 · 서울 428개 행정동
			</p>
		</div>
	</div>
</section>

<div class="wrap">
	<div class="ctrl-bar mb-4">
		<div class="ctrl-left card-shell">
			<div class="ctrl-row">
				<span class="ct-label">보행자 유형</span>
				{#each WS as w, i}
					<PillButton active={cW === i} onclick={() => (cW = i)}>
						{i === 0 ? '🧓' : i === 1 ? '🦯' : '🦽'}
						{w.label}
						{w.speed} m/s
					</PillButton>
				{/each}
			</div>

			<div class="ctrl-row mt-2.5">
				<span class="ct-label">보행 시간</span>
				<PillButton active={cT === 15} onclick={() => (cT = 15)}>15분</PillButton>
				<PillButton active={cT === 30} onclick={() => (cT = 30)}>30분</PillButton>
				<PillButton active={cT === 45} onclick={() => (cT = 45)}>45분</PillButton>
				<span class="flex-1"></span>
				<span class="ct-label">환경 보정</span>
				<button type="button" class="switch" class:on={cSlope} onclick={() => (cSlope = !cSlope)} aria-label="경사도 보정 (Tobler)">
					<span class="switch-knob"></span>
					<span class="switch-label">경사 보정 (Tobler)</span>
				</button>
			</div>

			<div class="ctrl-row mt-2.5">
				<span class="ct-label">기준 행정동</span>
				<select class="sel" value={cG} onchange={onGuChange}>
					{#each GU_ORDER as g}
						<option value={g}>{g}</option>
					{/each}
				</select>
				<select class="sel" value={cD} onchange={onDongChange}>
					{#each dongList as d}
						<option value={d.key}>{d.dong}</option>
					{/each}
				</select>
				<span class="text-[11px]" style:color="var(--color-text3)">
					{#if currentDong}
						65세+ {currentDong.elder.toLocaleString()}명 · centroid({currentDong.lat?.toFixed(4)}, {currentDong.lng?.toFixed(4)})
					{/if}
				</span>
				{#if cSlope && currentDong}
					<span class="text-[11px] tobler-tag">
						ratio {ratio.toFixed(3)} · 유효속도 {effSpeedDisplay} m/s
					</span>
				{/if}
			</div>
		</div>

		<div class="ctrl-right">
			<div class="big-stat">
				<div class="bs-label">도달가능점수</div>
				<div class="bs-val" style:color={scoreColor}>{score != null ? score + '점' : '—'}</div>
				<div class="bs-sub">{cSlope ? '경사 보정 반영' : '일반인 대비 도달가능 비율'}</div>
			</div>
			<StatCard
				label="65세+ 인구"
				value={(currentDong ? currentDong.elder.toLocaleString() : '-') + '명'}
				sub={cG + ' 주민센터 ' + (CENTER_BY_GU[cG] || 0) + '개소'}
				tone="blue"
			/>
		</div>
	</div>

	<div class="r-map mb-4">
		<Card title="서울시 생활 인프라 분포 — 행정동 단위">
			<PillTabs tabs={layerTabs} value={cLayer} onChange={(k) => (cLayer = k)} class="mb-2" />
			<MapShell
				height="460px"
				legend={[
					{ color: '#1D9E75', label: '전통시장', shape: 'circle' },
					{ color: '#E8A838', label: '슈퍼마켓', shape: 'circle' },
					{ color: '#7B5EA7', label: '은행', shape: 'square' },
					{ color: '#2563a8', label: '주민센터', shape: 'square' }
				]}
				source="출처: 소상공인시장진흥공단 · 소상공인 상가정보 · 금융감독원 · 행정안전부 / 행정동 centroid 기준 보행반경 · SUP 31,024개소 중 샘플 3,000개 표시"
			>
				<div bind:this={mapEl} class="absolute inset-0"></div>
			</MapShell>
		</Card>

		<Card title="보행 반경 모식도">
			<div class="radar-sub">
				{canvasSrcLabel || (currentDong ? currentDong.dong : cG)} · {cT}분 보행반경{cSlope ? ' · 경사보정' : ''}
			</div>
			<canvas bind:this={radarCanvas} width="340" height="340" class="radar-canvas"></canvas>
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
					<div class="leg-it"><span class="leg-dot leg-sq" style:background="#7B5EA7"></span>은행</div>
					<div class="leg-it"><span class="leg-dot leg-sq" style:background="#2563a8"></span>주민센터</div>
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

	<Card title="인프라 확충 우선순위 — 영향 노인 수 TOP 10 동" class="mb-4">
		<p class="mb-2.5 text-[11px]" style:color="var(--color-text3)">
			손실률(하위15% vs 일반인) × 65세+ 인구 = 영향받는 노인 수 · 30분 기준
		</p>
		<div class="space-y-1.5">
			{#each TOP10_VULNERABLE as d, i}
				{@const pct = Math.round((d.impact / top10MaxImpact) * 100)}
				{@const lossColor = d.loss > 80 ? '#9B1C1C' : d.loss > 60 ? '#D85A30' : '#854f0b'}
				{@const sc = Math.round(100 - d.loss)}
				<div class="t10r">
					<div class="t10l" title={d['구'] + ' ' + d['동']}>
						{d['구']} <b>{d['동']}</b>
					</div>
					<div class="t10bg">
						<div class="t10bar" style:width={pct + '%'} style:background={top10Colors[i]}></div>
					</div>
					<div class="t10v">{d.impact.toLocaleString()}명</div>
					<div class="t10loss" style:background={lossColor + '18'} style:color={lossColor}>
						{sc}점
					</div>
				</div>
			{/each}
		</div>
		<p class="mt-2.5 text-[11px]" style:color="var(--color-text3)">
			방법론: 행정동 centroid 기준 30분 보행반경 내 POI 카운트 · OSM 보행그래프 + 경사보정 (LEE 2026)<br />
			출처: 통계청 등록인구 2025.4Q
		</p>
	</Card>

	<Card title={'서울 행정동 생활인프라 접근성 — ' + currentW.label + ' · ' + cG + ' 행정동'} class="mb-4">
		<div class="tbl-wrap">
			<table>
				<thead>
					<tr>
						{#each [{ k: 'gu', label: '자치구' },{ k: 'dong', label: '행정동' },{ k: 'mkt', label: '전통시장' },{ k: 'sup', label: '슈퍼' },{ k: 'tot', label: '합계' },{ k: 'elder', label: '65세+' },{ k: 'score', label: '도달가능점수' }] as col}
							<th class="th-sort" class:active={sortKey === col.k} onclick={() => setSort(col.k)}>
								{col.label}
								{#if sortKey === col.k}<span class="sort-arr">{sortDir === 'desc' ? '▼' : '▲'}</span>{/if}
							</th>
						{/each}
						<th>접근성</th>
					</tr>
				</thead>
				<tbody>
					{#each tableRows as r}
						{@const accessCls = r.score >= 70 ? 'phi' : r.score >= 40 ? 'pmd' : 'plo'}
						{@const accessLabel = r.score >= 70 ? '양호' : r.score >= 40 ? '보통' : '미흡'}
						<tr class:hl={r.key === cD} onclick={() => panToRow(r)}>
							<td>{r.gu}</td>
							<td>{r.dong}</td>
							<td>{r.mkt}</td>
							<td>{r.sup}</td>
							<td>{r.tot}</td>
							<td>{r.elder.toLocaleString()}</td>
							<td><span class="pill {accessCls}">{r.score}점</span></td>
							<td><span class="pill {accessCls}">{accessLabel}</span></td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</Card>

	<Note tone="cool" class="mb-4">
		<b>방법론 (v6):</b> 보행자 유형(일반노인 1.12 / 보행보조 0.88 / 하위15% 0.70 m/s)과 시간(15·30·45분)에 따라 행정동 centroid에서 도달 가능한 시설 수를 OSM 보행그래프로 카운트. 경사보정(Tobler) 토글 시 동별 실측 ratio (tobler_ratio_LEE.csv, LEE 2026)를 유효속도에 반영하여 도달가능점수를 선형 보간으로 추정.
	</Note>
</div>

<style>
	.infra-hero { background: var(--color-dark); color: var(--color-dark-text); padding: 18px 28px; }
	.infra-hero-inner { max-width: 1340px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
	.hero-kicker { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.55; margin-bottom: 6px; }
	.hero-title { font-size: 17px; font-weight: 500; margin-bottom: 4px; }
	.hero-sub { font-size: 12px; opacity: 0.55; }
	.wrap { max-width: 1340px; margin: 0 auto; padding: 18px 18px 60px; }

	.ctrl-bar { display: grid; grid-template-columns: 1fr 320px; gap: 12px; align-items: stretch; }
	@media (max-width: 1100px) { .ctrl-bar { grid-template-columns: 1fr; } }
	.ctrl-right { display: flex; flex-direction: column; gap: 8px; }
	.big-stat { background: var(--color-card-soft); border-radius: 8px; padding: 14px 16px; }
	.bs-label { font-size: 11px; color: var(--color-text3); margin-bottom: 4px; }
	.bs-val { font-family: var(--font-mono); font-size: 32px; font-weight: 500; line-height: 1.1; }
	.bs-sub { font-size: 11px; color: var(--color-text3); margin-top: 4px; }
	.ctrl-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
	.sel { font-size: 12px; padding: 4px 10px; border-radius: 6px; border: 0.5px solid var(--color-border); background: #fff; color: var(--color-text); font-family: inherit; }
	select.sel:focus { outline: none; border-color: var(--color-text2); }
	.tobler-tag { font-family: var(--font-mono); padding: 2px 8px; border-radius: 10px; color: var(--color-slope); background: color-mix(in srgb, var(--color-slope) 10%, transparent); }

	.switch { display: inline-flex; align-items: center; gap: 8px; padding: 4px 12px 4px 6px; border-radius: 18px; border: 0.5px solid var(--color-border); background: #fff; cursor: pointer; font-family: inherit; font-size: 12px; color: var(--color-text2); transition: all 0.16s; }
	.switch-knob { display: inline-block; width: 28px; height: 16px; border-radius: 12px; background: var(--color-border); position: relative; transition: background 0.18s; }
	.switch-knob::after { content: ''; position: absolute; top: 2px; left: 2px; width: 12px; height: 12px; border-radius: 50%; background: #fff; transition: transform 0.18s; }
	.switch.on { border-color: var(--color-slope); color: var(--color-text); background: color-mix(in srgb, var(--color-slope) 8%, white); }
	.switch.on .switch-knob { background: var(--color-slope); }
	.switch.on .switch-knob::after { transform: translateX(12px); }

	.r-map { display: grid; grid-template-columns: 1.4fr 1fr; gap: 12px; }
	@media (max-width: 1100px) { .r-map { grid-template-columns: 1fr; } }
	.radar-sub { font-size: 12px; color: var(--color-text2); margin-bottom: 6px; }
	.radar-canvas { display: block; width: 100%; max-width: 340px; margin: 0 auto; }
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

	.t10r { display: grid; grid-template-columns: 130px 1fr 80px 50px; align-items: center; gap: 8px; font-size: 12px; }
	.t10l { color: var(--color-text2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.t10l b { color: var(--color-text); font-weight: 500; }
	.t10bg { height: 16px; border-radius: 3px; background: var(--color-border-soft); overflow: hidden; }
	.t10bar { height: 100%; border-radius: 3px; transition: width 0.3s; }
	.t10v { font-family: var(--font-mono); text-align: right; font-size: 11px; color: var(--color-text2); }
	.t10loss { font-size: 11px; text-align: center; padding: 2px 0; border-radius: 3px; font-weight: 500; }

	.tbl-wrap { max-height: 520px; overflow-y: auto; }
	table { width: 100%; font-size: 12px; border-collapse: collapse; }
	thead { position: sticky; top: 0; background: #fff; z-index: 1; }
	th { text-align: left; font-weight: 500; font-size: 11px; color: var(--color-text3); padding: 8px 10px; border-bottom: 0.5px solid var(--color-border); white-space: nowrap; }
	.th-sort { cursor: pointer; user-select: none; }
	.th-sort:hover { color: var(--color-text); }
	.th-sort.active { color: var(--color-text); }
	.sort-arr { font-size: 9px; margin-left: 2px; color: var(--color-teal); }
	td { padding: 7px 10px; border-bottom: 0.5px solid var(--color-border-soft); }
	tbody tr { cursor: pointer; }
	tr:hover td { background: #fafaf8; }
	tr.hl td { background: var(--color-bg2); font-weight: 500; }
	.pill { display: inline-block; font-size: 11px; padding: 1px 8px; border-radius: 10px; font-weight: 500; }
	.pill.phi { background: #2e7d3218; color: #2e7d32; }
	.pill.pmd { background: #f57f1718; color: #f57f17; }
	.pill.plo { background: #c6282818; color: #c62828; }
</style>
