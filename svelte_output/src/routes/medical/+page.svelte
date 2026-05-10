<script>
	import { onMount, onDestroy } from 'svelte';
	import medical from '$lib/data/medical.json';
	import facilities from '$lib/data/medical_facilities.json';
	import bokji from '$lib/data/bokji.json';
	import Card from '$lib/components/Card.svelte';
	import MapShell from '$lib/components/MapShell.svelte';
	import Note from '$lib/components/Note.svelte';

	/** @type {{ COUNTS: Record<string, Record<string, number>>, DONG_META: Record<string, {fn:string,gu:string,el:number}>, GEOJSON: any, SPEEDS: {id:string,label:string,speed:number,color:string}[] }} */
	const { COUNTS, DONG_META, GEOJSON, SPEEDS } = medical;
	const { GU_CENTER } = bokji;

	const gus = [...new Set(Object.values(DONG_META).map((d) => d.gu))].sort();

	// 자치구별 시설 수 (Python으로 전처리된 정적 데이터)
	const GU_FAC_COUNTS = {"강남구":{"의원":2459,"병원":43,"보건소":1,"종합병원":5,"약국":562},"강동구":{"의원":529,"병원":17,"보건소":1,"종합병원":3,"약국":304},"강북구":{"의원":264,"병원":10,"보건소":1,"종합병원":2,"약국":167},"강서구":{"의원":554,"병원":21,"보건소":1,"종합병원":4,"약국":291},"관악구":{"의원":384,"병원":14,"보건소":2,"종합병원":1,"약국":241},"광진구":{"의원":343,"병원":4,"보건소":3,"종합병원":2,"약국":181},"구로구":{"의원":325,"병원":9,"보건소":3,"종합병원":2,"약국":203},"금천구":{"의원":199,"병원":6,"보건소":1,"종합병원":1,"약국":147},"노원구":{"의원":436,"병원":6,"보건소":2,"종합병원":3,"약국":235},"도봉구":{"의원":191,"병원":7,"보건소":1,"종합병원":1,"약국":124},"동대문구":{"의원":307,"병원":13,"보건소":1,"종합병원":4,"약국":291},"동작구":{"의원":336,"병원":7,"보건소":1,"종합병원":2,"약국":204},"마포구":{"의원":481,"병원":6,"보건소":1,"종합병원":0,"약국":225},"서대문구":{"의원":249,"병원":5,"보건소":2,"종합병원":2,"약국":163},"서초구":{"의원":1077,"병원":16,"보건소":3,"종합병원":2,"약국":299},"성동구":{"의원":287,"병원":4,"보건소":1,"종합병원":2,"약국":166},"성북구":{"의원":307,"병원":6,"보건소":3,"종합병원":1,"약국":204},"송파구":{"의원":736,"병원":28,"보건소":2,"종합병원":2,"약국":405},"양천구":{"의원":360,"병원":5,"보건소":1,"종합병원":3,"약국":200},"영등포구":{"의원":478,"병원":9,"보건소":1,"종합병원":7,"약국":279},"용산구":{"의원":194,"병원":2,"보건소":1,"종합병원":1,"약국":115},"은평구":{"의원":380,"병원":11,"보건소":4,"종합병원":2,"약국":217},"종로구":{"의원":240,"병원":2,"보건소":1,"종합병원":4,"약국":196},"중구":{"의원":358,"병원":4,"보건소":1,"종합병원":2,"약국":195},"중랑구":{"의원":308,"병원":16,"보건소":1,"종합병원":3,"약국":194}};

	// 동→구 역인덱스 (정적)
	/** @type {Record<string, string[]>} */
	const dongsByGu = {};
	Object.keys(DONG_META).forEach((dc) => {
		const g = DONG_META[dc].gu;
		if (!dongsByGu[g]) dongsByGu[g] = [];
		dongsByGu[g].push(dc);
	});

	const AVG_TOBLER = 0.8006;

	// ─── 상태 (Svelte 5 runes) ───
	let cB = $state(2); // 비교 속도 인덱스 (1/2/3)
	let cT = $state(30); // 시간(분) 15/30/45
	let cF = $state('all'); // 시설 유형 all/hosp/pharm
	let cSlope = $state(false);
	let cTop = $state('impact'); // impact | score

	// ─── 자치구 선택 ───
	let cG = $state('종로구');

	// ─── 지도 레이어 토글 상태 ───
	let showChoropleth = $state(true);
	let showUiwon = $state(true);    // 의원
	let showHospital = $state(true); // 병원
	let showBogeon = $state(true);   // 보건소
	let showJonghap = $state(true);  // 종합병원
	let showPharm = $state(true);    // 약국
	let showDongCircle = $state(false);

	// ─── 헬퍼 ───
	/**
	 * @param {string} speedId
	 * @param {number} time
	 * @param {string} ftype
	 * @param {string} dc
	 * @param {boolean} isSlope
	 */
	function getN(speedId, time, ftype, dc, isSlope) {
		const s = isSlope ? 'slope' : 'flat';
		if (ftype === 'all') {
			return (
				(COUNTS[`${speedId}_${time}_hosp_${s}`]?.[dc] || 0) +
				(COUNTS[`${speedId}_${time}_pharm_${s}`]?.[dc] || 0)
			);
		}
		return COUNTS[`${speedId}_${time}_${ftype}_${s}`]?.[dc] || 0;
	}

	/** @param {string} dc */
	function dongScore(dc) {
		const nYoung = getN('young', cT, cF, dc, cSlope);
		const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
		return nYoung > 0 ? (nB / nYoung) * 100 : 100;
	}

	/** @param {number} v */
	function scoreColor(v) {
		if (v >= 90) return '#1a9850';
		if (v >= 80) return '#91cf60';
		if (v >= 70) return '#d9ef8b';
		if (v >= 60) return '#fee08b';
		if (v >= 50) return '#fdae61';
		if (v >= 40) return '#d73027';
		return '#a50026';
	}
	/** @param {number} v */
	function ptScoreColor(v) {
		if (v >= 90) return 'rgba(26,152,80,.8)';
		if (v >= 80) return 'rgba(145,207,96,.8)';
		if (v >= 70) return 'rgba(217,239,139,.9)';
		if (v >= 60) return 'rgba(254,224,139,.9)';
		if (v >= 50) return 'rgba(253,174,97,.8)';
		if (v >= 40) return 'rgba(215,48,39,.8)';
		return 'rgba(165,0,38,.8)';
	}

	// ─── 통계 계산 (반응형 derived) ───
	const allDongStats = $derived.by(() => {
		// cB / cT / cF / cSlope 변경 시 재계산
		void cB;
		void cT;
		void cF;
		void cSlope;
		return Object.keys(DONG_META).map((dc) => {
			const nYoung = getN('young', cT, cF, dc, cSlope);
			const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
			const score = nYoung > 0 ? (nB / nYoung) * 100 : 100;
			const m = DONG_META[dc];
			const impact = Math.round((Math.max(0, 100 - score) / 100) * m.el);
			return { dc, fn: m.fn, gu: m.gu, el: m.el, nYoung, nB, score, impact };
		});
	});

	const guStats = $derived.by(() => {
		/** @type {Record<string,{sum:number,cnt:number,impact:number}>} */
		const byGu = {};
		allDongStats
			.filter((r) => r.nYoung > 0)
			.forEach((r) => {
				if (!byGu[r.gu]) byGu[r.gu] = { sum: 0, cnt: 0, impact: 0 };
				byGu[r.gu].sum += r.score;
				byGu[r.gu].cnt += 1;
				byGu[r.gu].impact += r.impact;
			});
		return Object.entries(byGu)
			.map(([gu, v]) => ({ gu, sc: v.sum / v.cnt, im: v.impact }))
			.sort((a, b) => a.sc - b.sc);
	});

	const statSummary = $derived.by(() => {
		const valid = allDongStats.filter((r) => r.nYoung > 0);
		const meanScore = valid.length ? valid.reduce((s, r) => s + r.score, 0) / valid.length : 0;
		const totalImpact = allDongStats.reduce((s, r) => s + r.impact, 0);
		const tr = cSlope ? AVG_TOBLER : 1.0;
		const rYoung = Math.round(1.28 * cT * 60 * tr);
		const rB = Math.round(SPEEDS[cB].speed * cT * 60 * tr);
		const theory = (SPEEDS[cB].speed / 1.28) ** 2 * 100;

		// 병의원/약국 개별 평균 및 점수
		let hospYoungSum = 0, pharmYoungSum = 0, hospCBSum = 0, pharmCBSum = 0;
		let hospCnt = 0, pharmCnt = 0;
		let hospScoreSum = 0, pharmScoreSum = 0;
		const sid = SPEEDS[cB].id;
		Object.keys(DONG_META).forEach((dc) => {
			const hY = getN('young', cT, 'hosp', dc, cSlope);
			const pY = getN('young', cT, 'pharm', dc, cSlope);
			const hB = getN(sid, cT, 'hosp', dc, cSlope);
			const pB = getN(sid, cT, 'pharm', dc, cSlope);
			if (hY > 0) { hospYoungSum += hY; hospCBSum += hB; hospScoreSum += (hB / hY) * 100; hospCnt++; }
			if (pY > 0) { pharmYoungSum += pY; pharmCBSum += pB; pharmScoreSum += (pB / pY) * 100; pharmCnt++; }
		});
		const avgHospYoung = hospCnt > 0 ? hospYoungSum / hospCnt : 0;
		const avgPharmYoung = pharmCnt > 0 ? pharmYoungSum / pharmCnt : 0;
		const avgHospCB = hospCnt > 0 ? hospCBSum / hospCnt : 0;
		const avgPharmCB = pharmCnt > 0 ? pharmCBSum / pharmCnt : 0;
		const hospScore = hospCnt > 0 ? hospScoreSum / hospCnt : 0;
		const pharmScore = pharmCnt > 0 ? pharmScoreSum / pharmCnt : 0;

		return { meanScore, totalImpact, rYoung, rB, theory, avgHospYoung, avgPharmYoung, avgHospCB, avgPharmCB, hospScore, pharmScore };
	});

	// 선택된 구의 병의원·약국 평균 도달개수 및 점수
	const guStat = $derived.by(() => {
		void cG; void cB; void cT; void cSlope;
		const sid = SPEEDS[cB].id;
		let hYS = 0, hBS = 0, hCnt = 0, hScS = 0;
		let pYS = 0, pBS = 0, pCnt = 0, pScS = 0;
		(dongsByGu[cG] || []).forEach((dc) => {
			const hY = getN('young', cT, 'hosp', dc, cSlope);
			const pY = getN('young', cT, 'pharm', dc, cSlope);
			const hB = getN(sid, cT, 'hosp', dc, cSlope);
			const pB = getN(sid, cT, 'pharm', dc, cSlope);
			if (hY > 0) { hYS += hY; hBS += hB; hScS += (hB / hY) * 100; hCnt++; }
			if (pY > 0) { pYS += pY; pBS += pB; pScS += (pB / pY) * 100; pCnt++; }
		});
		return {
			hospYoung: hCnt > 0 ? hYS / hCnt : 0,
			hospCB:    hCnt > 0 ? hBS / hCnt : 0,
			hospScore: hCnt > 0 ? hScS / hCnt : 0,
			pharmYoung: pCnt > 0 ? pYS / pCnt : 0,
			pharmCB:    pCnt > 0 ? pBS / pCnt : 0,
			pharmScore: pCnt > 0 ? pScS / pCnt : 0,
		};
	});

	// 자치구별 상세표 행
	const guTableRows = $derived.by(() => {
		void cB; void cT; void cSlope;
		const sid = SPEEDS[cB].id;
		const rows = gus.map((gu) => {
			let hYS = 0, hBS = 0, hCnt = 0;
			let pYS = 0, pBS = 0, pCnt = 0;
			(dongsByGu[gu] || []).forEach((dc) => {
				const hY = getN('young', cT, 'hosp', dc, cSlope);
				const pY = getN('young', cT, 'pharm', dc, cSlope);
				const hB = getN(sid, cT, 'hosp', dc, cSlope);
				const pB = getN(sid, cT, 'pharm', dc, cSlope);
				if (hY > 0) { hYS += hY; hBS += hB; hCnt++; }
				if (pY > 0) { pYS += pY; pBS += pB; pCnt++; }
			});
			const hospScore = hCnt > 0 ? (hBS / hYS) * 100 : 100;
			const pharmScore = pCnt > 0 ? (pBS / pYS) * 100 : 100;
			const avgScore = (hospScore + pharmScore) / 2;
			const fac = /** @type {any} */ (GU_FAC_COUNTS)[gu] || {};
			return { gu, uiwon: fac['의원'] || 0, byeong: fac['병원'] || 0, bogeon: fac['보건소'] || 0, jonghap: fac['종합병원'] || 0, pharm: fac['약국'] || 0, hospScore, pharmScore, avgScore, sel: gu === cG };
		});
		return rows.map((r) => ({
			...r,
			grade: r.avgScore >= 80 ? 'phi' : r.avgScore >= 50 ? 'pmd' : 'plo',
			gradeText: r.avgScore >= 80 ? '양호' : r.avgScore >= 50 ? '보통' : '미흡'
		})).sort((a, b) => b.avgScore - a.avgScore);
	});

	const tableRows = $derived(
		allDongStats
			.filter((r) => r.nYoung > 0)
			.sort((a, b) => a.score - b.score)
			.slice(0, 100)
	);

	const topRows = $derived.by(() => {
		const isImpact = cTop === 'impact';
		return isImpact
			? allDongStats
					.filter((r) => r.impact > 0)
					.sort((a, b) => b.impact - a.impact)
					.slice(0, 10)
			: allDongStats
					.filter((r) => r.nYoung > 0)
					.sort((a, b) => a.score - b.score)
					.slice(0, 10);
	});

	const mapTitle = $derived.by(() => {
		const b = SPEEDS[cB];
		const slopeNote = cSlope ? ' · 경사 보정 적용' : ' · 평지 기준';
		return `행정동별 의료 도달가능점수 — ${b.label} (${b.speed} m/s)${slopeNote}`;
	});

	const scTitle = $derived(`일반인 vs ${SPEEDS[cB].label} 접근 가능 시설 수`);

	// ─── Leaflet ───
	/** @type {HTMLDivElement | undefined} */
	let mapEl = $state();
	let mapReady = $state(false);
	/** @type {any} */
	let map = null;
	/** @type {any} */
	let L = null;
	/** @type {any} */
	let geoLayer = null;
	// POI 레이어 — 5개 분류별
	/** @type {any} */
	let grpUiwon = null;
	/** @type {any} */
	let grpHospital = null;
	/** @type {any} */
	let grpBogeon = null;
	/** @type {any} */
	let grpJonghap = null;
	/** @type {any} */
	let grpPharm = null;
	/** @type {any} */
	let guCircle = null;
	/** @type {any} */
	let dongCircleGroup = null;

	/** @type {Record<string, string>} 병의원 분류별 색상 */
	const HOSP_COLOR = {
		'의원': '#f472b6',
		'병원': '#e11d48',
		'보건소': '#7c3aed',
		'종합병원': '#1d4ed8'
	};

	/** @param {any} geometry */
	function polygonCentroid(geometry) {
		const ring = geometry.type === 'MultiPolygon'
			? geometry.coordinates[0][0]
			: geometry.coordinates[0];
		let lat = 0, lng = 0;
		ring.forEach(/** @param {number[]} c */([lo, la]) => { lng += lo; lat += la; });
		return [lat / ring.length, lng / ring.length];
	}

	/** @type {Record<string, number[]>} */
	const dongCentroids = {};
	GEOJSON.features.forEach(/** @param {any} f */(f) => {
		dongCentroids[f.properties.dc] = polygonCentroid(f.geometry);
	});

	/** @param {number} v */
	function choroColor(v) {
		if (v >= 80) return '#1D9E75';
		if (v >= 50) return '#f5a623';
		return '#E74C3C';
	}

	/** @param {any} feat */
	function styleFeature(feat) {
		const score = dongScore(feat.properties.dc);
		return {
			fillColor: choroColor(score),
			color: '#c0bcb4',
			weight: 0.8,
			fillOpacity: 0.22
		};
	}

	/** @param {any} feat */
	function tooltipContent(feat) {
		const dc = feat.properties.dc;
		const m = DONG_META[dc];
		if (!m) return '';
		const nYoung = getN('young', cT, cF, dc, cSlope);
		const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
		const score = nYoung > 0 ? (nB / nYoung) * 100 : 100;
		const impact = Math.round((Math.max(0, 100 - score) / 100) * m.el);
		return (
			`<b>${m.fn}</b><br>` +
			`도달가능점수: <b>${score.toFixed(1)}점</b><br>` +
			`일반인 ${nYoung}개 → ${SPEEDS[cB].label} ${nB}개<br>` +
			`영향 노인 수: 약 ${impact.toLocaleString()}명`
		);
	}

	onMount(async () => {
		L = (await import('leaflet')).default;
		await import('leaflet/dist/leaflet.css');

		map = L.map(mapEl, { zoomControl: true, attributionControl: false })
			.setView([37.5665, 126.978], 11);
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			subdomains: 'abcd',
			maxZoom: 18
		}).addTo(map);

		// Layer 1: Choropleth
		geoLayer = L.geoJSON(GEOJSON, {
			style: styleFeature,
			onEachFeature: (/** @type {any} */ feat, /** @type {any} */ layer) => {
				layer.bindTooltip(tooltipContent(feat), { sticky: true });
				layer.on('mouseover', /** @param {any} e */ (e) => {
					e.target.setStyle({ weight: 2, color: '#FFD700', fillOpacity: 0.85 });
				});
				layer.on('mouseout', /** @param {any} e */ (e) => {
					geoLayer?.resetStyle(e.target);
				});
			}
		}).addTo(map);

		// Layer 2: 병의원 5종 그룹
		grpUiwon   = L.layerGroup().addTo(map);
		grpHospital = L.layerGroup().addTo(map);
		grpBogeon  = L.layerGroup().addTo(map);
		grpJonghap = L.layerGroup().addTo(map);
		grpPharm   = L.layerGroup().addTo(map);

		/** @type {Record<string,any>} */
		const grpMap = { '의원': grpUiwon, '병원': grpHospital, '보건소': grpBogeon, '종합병원': grpJonghap };

		facilities.HOSP.forEach((/** @type {any} */ h) => {
			const col = HOSP_COLOR[h.sub] || '#f472b6';
			const grp = grpMap[h.sub] || grpUiwon;
			L.circleMarker([h.lat, h.lng], {
				radius: 4, fillColor: col, color: '#fff', weight: 0.8, fillOpacity: 0.85
			})
				.bindTooltip(`<b>${h.name}</b><br><span style="color:#888780">${h.sub}</span>`, {
					direction: 'top', offset: [0, -4]
				})
				.addTo(grp);
		});

		facilities.PHARM.forEach((/** @type {any} */ p) => {
			L.circleMarker([p.lat, p.lng], {
				radius: 3.5, fillColor: '#10b981', color: '#fff', weight: 0.8, fillOpacity: 0.85
			})
				.bindTooltip(`<b>${p.name}</b><br><span style="color:#888780">약국</span>`, {
					direction: 'top', offset: [0, -4]
				})
				.addTo(grpPharm);
		});

		mapReady = true;
		await initCharts();
	});

	onDestroy(() => {
		if (map) { try { map.remove(); } catch (e) {} }
		[scChart, icChart, gcuChart, impChart, bblChart].forEach((c) => c?.destroy?.());
	});

	// Effect 1: Choropleth 스타일 갱신 (컨트롤 변경 시)
	$effect(() => {
		void cB; void cT; void cF; void cSlope;
		if (!mapReady) return;
		geoLayer.setStyle(styleFeature);
		geoLayer.eachLayer((/** @type {any} */ l) => {
			// @ts-ignore
			l.setTooltipContent(tooltipContent(l.feature));
		});
	});

	// Effect 2: Choropleth 토글
	$effect(() => {
		if (!mapReady) return;
		showChoropleth ? geoLayer.addTo(map) : geoLayer.remove();
	});

	// Effect 3: POI 5종 토글 + 시설 유형(cF) 연동
	$effect(() => {
		void showUiwon; void showHospital; void showBogeon; void showJonghap; void showPharm; void cF;
		if (!mapReady) return;
		const hosOn = cF !== 'pharm'; // pharm 선택 시 병의원 계열 숨김
		const phOn  = cF !== 'hosp';  // hosp 선택 시 약국 숨김
		(showUiwon   && hosOn) ? grpUiwon.addTo(map)   : grpUiwon.remove();
		(showHospital && hosOn) ? grpHospital.addTo(map) : grpHospital.remove();
		(showBogeon  && hosOn) ? grpBogeon.addTo(map)  : grpBogeon.remove();
		(showJonghap && hosOn) ? grpJonghap.addTo(map) : grpJonghap.remove();
		(showPharm   && phOn)  ? grpPharm.addTo(map)   : grpPharm.remove();
	});

	// Effect 4: 자치구 중심 반경원 + 뷰 이동
	$effect(() => {
		if (!mapReady) return;
		const center = /** @type {Record<string,number[]>} */ (GU_CENTER)[cG];
		if (guCircle) { map.removeLayer(guCircle); guCircle = null; }
		if (!center) return;
		const tr = cSlope ? AVG_TOBLER : 1.0;
		const radiusM = Math.round(SPEEDS[cB].speed * cT * 60 * tr);
		guCircle = L.circle(center, {
			radius: radiusM,
			color: '#FF6F00',
			weight: 2,
			dashArray: '8,5',
			fillColor: '#FF6F00',
			fillOpacity: 0.15
		})
			.bindTooltip(`${cG} 중심 · ${SPEEDS[cB].label} ${cT}분 반경 ~${(radiusM / 1000).toFixed(2)} km`)
			.addTo(map);
		map.setView(center, 12, { animate: true, duration: 0.4 });
	});

	// Effect 5: 동 반경 원 (선택 자치구만)
	$effect(() => {
		void showDongCircle; void cG; void cB; void cT; void cSlope; void cF;
		if (!mapReady) return;

		if (dongCircleGroup) { map.removeLayer(dongCircleGroup); dongCircleGroup = null; }
		if (!showDongCircle) return;

		const tr = cSlope ? AVG_TOBLER : 1.0;
		const radiusM = Math.round(SPEEDS[cB].speed * cT * 60 * tr);

		dongCircleGroup = L.layerGroup().addTo(map);

		Object.entries(DONG_META)
			.filter(([, /** @type {any} */ m]) => m.gu === cG)
			.forEach(([dc, /** @type {any} */ meta]) => {
				const centroid = dongCentroids[dc];
				if (!centroid) return;
				const score = dongScore(dc);
				const col = scoreColor(score);
				const nYoung = getN('young', cT, cF, dc, cSlope);
				const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
				const impact = Math.round((Math.max(0, 100 - score) / 100) * meta.el);
				const slopeTip = cSlope ? `<br>경사 보정 (Tobler: ${AVG_TOBLER})` : '';

				L.circle(centroid, {
					radius: radiusM,
					color: col,
					weight: 1.2,
					dashArray: '5,4',
					fillColor: col,
					fillOpacity: 0.15
				})
					.bindTooltip(
						`<b>${meta.fn}</b><br>` +
						`반경: ~${(radiusM / 1000).toFixed(2)} km<br>` +
						`도달가능점수: ${score.toFixed(1)}점<br>` +
						`일반인 ${nYoung}개 → ${SPEEDS[cB].label} ${nB}개<br>` +
						`영향 노인: 약 ${impact.toLocaleString()}명` +
						slopeTip
					)
					.addTo(dongCircleGroup);

				L.circleMarker(centroid, {
					radius: 3, color: col, weight: 1, fillColor: col, fillOpacity: 0.9
				})
					.bindTooltip(meta.fn, {
						permanent: true, className: 'dong-label',
						direction: 'top', offset: [0, -5]
					})
					.addTo(dongCircleGroup);
			});
	});

	// ─── Chart.js ───
	/** @type {HTMLCanvasElement | undefined} */
	let scCanvas = $state();
/** @type {HTMLCanvasElement | undefined} */
	let gcuCanvas = $state(); // 선택 구 동별 점수
	/** @type {HTMLCanvasElement | undefined} */
	let impCanvas = $state(); // 구별 영향 노인 수
	/** @type {HTMLCanvasElement | undefined} */
	let bblCanvas = $state(); // 점수×노인인구 버블
	/** @type {HTMLCanvasElement | undefined} */
	let icCanvas = $state();

	/** @type {any} */
	let scChart = null;
/** @type {any} */
	let icChart = null;
	/** @type {any} */
	let gcuChart = null;
	/** @type {any} */
	let impChart = null;
	/** @type {any} */
	let bblChart = null;
	/** @type {any} */
	let ChartLib = null;

	async function initCharts() {
		if (!gcuCanvas) return;
		const mod = await import('chart.js/auto');
		ChartLib = mod.default;

		buildGcuChart();
		buildImpChart();
		buildBblChart();
	}

	function buildTopChart() {
		if (!ChartLib || !icCanvas) return;
		const isImpact = cTop === 'impact';
		const sorted = topRows;
		const labels = sorted.map((r) => r.fn);
		const vals = isImpact ? sorted.map((r) => r.impact) : sorted.map((r) => r.score);
		const colors = isImpact
			? sorted.map((_, i) => `hsl(${10 + i * 4},68%,${42 + i * 3}%)`)
			: sorted.map((r) => scoreColor(r.score));

		if (icChart) icChart.destroy();
		icChart = new ChartLib(icCanvas, {
			type: 'bar',
			data: {
				labels,
				datasets: [{ data: vals, backgroundColor: colors, borderWidth: 0 }]
			},
			options: {
				indexAxis: 'y',
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label: (ctx) =>
								isImpact
									? `약 ${Number(ctx.raw).toLocaleString()}명`
									: `${Number(ctx.raw).toFixed(1)}점`
						}
					}
				},
				scales: {
					x: {
						grid: { color: '#f0f0ee' },
						min: 0,
						max: isImpact ? undefined : 100,
						title: {
							display: true,
							text: isImpact ? '영향 노인 수(명)' : '도달가능점수(점)',
							font: { size: 11 }
						}
					},
					y: { ticks: { font: { size: 11 } } }
				}
			}
		});
	}

	function buildGcuChart() {
		if (!ChartLib || !gcuCanvas) return;
		const base = allDongStats.filter((r) => r.gu === cG);

		if (cB === 0) {
			// 일반인 선택 시 → 동별 시설 개수 표시 (개수 기준 3분위 색상)
			const rows = [...base].sort((a, b) => a.nYoung - b.nYoung);
			const vals = rows.map((r) => r.nYoung);
			const sortedV = [...vals].sort((a, b) => a - b);
			const cq1 = sortedV[Math.floor(sortedV.length / 3)] ?? 0;
			const cq2 = sortedV[Math.floor((sortedV.length * 2) / 3)] ?? 0;
			const colors = vals.map((v) => v >= cq2 ? 'rgba(15,110,86,0.82)' : v >= cq1 ? 'rgba(133,79,11,0.82)' : 'rgba(163,45,45,0.85)');
			const facLabel = cF === 'all' ? '전체 시설' : cF === 'hosp' ? '병의원' : '약국';
			if (gcuChart) gcuChart.destroy();
			gcuChart = new ChartLib(gcuCanvas, {
				type: 'bar',
				data: {
					labels: rows.map((r) => r.fn),
					datasets: [{ data: vals, backgroundColor: colors, borderRadius: 3, minBarLength: 4, borderWidth: 0 }]
				},
				options: {
					indexAxis: 'y',
					responsive: true,
					maintainAspectRatio: false,
					animation: { duration: 200 },
					plugins: {
						legend: { display: false },
						tooltip: { callbacks: { label: (/** @type {any} */ ctx) => `${facLabel}: ${ctx.raw}개` } }
					},
					scales: {
						x: { grid: { color: '#f1efe8' }, ticks: { font: { size: 10 } }, title: { display: true, text: `${facLabel} 개수 (개)`, font: { size: 10 } } },
						y: { ticks: { font: { size: 9 } } }
					}
				}
			});
		} else {
			// 비교 속도 선택 시 → 동별 도달가능점수 (quantile 색상)
			const rows = [...base].sort((a, b) => a.score - b.score);
			const scores = rows.map((r) => r.score);
			const colors = scores.map((v) => barColor(v));
			if (gcuChart) gcuChart.destroy();
			gcuChart = new ChartLib(gcuCanvas, {
				type: 'bar',
				data: {
					labels: rows.map((r) => r.fn),
					datasets: [{ data: rows.map((r) => +r.score.toFixed(1)), backgroundColor: colors, borderRadius: 3, minBarLength: 4, borderWidth: 0 }]
				},
				options: {
					indexAxis: 'y',
					responsive: true,
					maintainAspectRatio: false,
					animation: { duration: 200 },
					plugins: {
						legend: { display: false },
						tooltip: {
							callbacks: {
								label: (/** @type {any} */ ctx) =>
									`점수: ${Number(ctx.raw).toFixed(1)}점 · 영향 노인: ${rows[ctx.dataIndex]?.impact.toLocaleString()}명`
							}
						}
					},
					scales: {
						x: { min: 0, max: 100, grid: { color: '#f1efe8' }, ticks: { font: { size: 10 }, callback: (/** @type {any} */ v) => v + '점' }, title: { display: true, text: '도달가능점수 (점)', font: { size: 10 } } },
						y: { ticks: { font: { size: 9 } } }
					}
				}
			});
		}
	}

	function buildImpChart() {
		if (!ChartLib || !impCanvas) return;
		const rows = [...guStats].sort((a, b) => b.im - a.im);
		if (impChart) impChart.destroy();
		impChart = new ChartLib(impCanvas, {
			type: 'bar',
			data: {
				labels: rows.map((r) => r.gu),
				datasets: [{ data: rows.map((r) => r.im), backgroundColor: rows.map((_, i) => `hsl(${8 + i * 3},65%,${45 + i * 2}%)`), borderWidth: 0 }]
			},
			options: {
				indexAxis: 'y',
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: { callbacks: { label: (/** @type {any} */ ctx) => `약 ${Number(ctx.raw).toLocaleString()}명` } }
				},
				scales: {
					x: { grid: { color: '#f0f0ee' }, ticks: { callback: (/** @type {any} */ v) => Math.round(v / 10000) + '만' }, title: { display: true, text: '접근손실 가중 노인 수(명)', font: { size: 10 } } },
					y: { ticks: { font: { size: 10 } } }
				}
			}
		});
	}

	function buildBblChart() {
		if (!ChartLib || !bblCanvas) return;
		const sData = allDongStats.filter((r) => r.gu === cG && r.nYoung > 0 && r.el > 0);
		const maxImpact = Math.max(...sData.map((r) => r.impact), 1);
		if (bblChart) bblChart.destroy();
		bblChart = new ChartLib(bblCanvas, {
			type: 'bubble',
			data: {
				datasets: [{
					label: '행정동',
					data: sData.map((r) => ({
						x: r.el,
						y: r.score,
						r: Math.max(2, Math.sqrt(r.impact / maxImpact) * 16),
						fn: r.fn,
						impact: r.impact
					})),
					backgroundColor: sData.map((r) => ptScoreColor(r.score))
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							label: (/** @type {any} */ ctx) => {
								const p = /** @type {any} */ (ctx.raw);
								return [p.fn, `65세이상: ${p.x.toLocaleString()}명`, `점수: ${p.y.toFixed(1)}점`, `영향 노인: ${p.impact.toLocaleString()}명`];
							}
						}
					}
				},
				scales: {
					x: { grid: { color: '#f0f0ee' }, title: { display: true, text: '65세이상 인구(명)', font: { size: 10 } } },
					y: { min: 0, max: 100, grid: { color: '#f0f0ee' }, title: { display: true, text: '도달가능점수(점)', font: { size: 10 } }, ticks: { callback: (/** @type {any} */ v) => v + '점' } }
				}
			}
		});
	}


	// 선택 구 변경 시 동별 점수 차트 갱신
	$effect(() => {
		void cG; void cB; void cT; void cF; void cSlope;
		if (ChartLib) buildGcuChart();
	});

	// cB/cT/cF/cSlope/cG 변경 시 영향 노인·버블 갱신
	$effect(() => {
		void cB; void cT; void cF; void cSlope; void cG;
		if (ChartLib) { buildImpChart(); buildBblChart(); }
	});

	// ─── 버튼 라벨/상태 ───
	const compareLabels = [
		{ idx: 0, emoji: '🚶', text: '일반인', speed: '1.28 m/s' },
		{ idx: 1, emoji: '🧓', text: '건강 노인', speed: '1.12 m/s' },
		{ idx: 2, emoji: '🦽', text: '보행보조 노인', speed: '0.88 m/s' },
		{ idx: 3, emoji: '♿', text: '보행보조 노인 하위15%', speed: '0.70 m/s' }
	];

	/** 80점 이상 녹색, 50점 이상 황색, 그 이하 적색
	 * @param {number} v
	 */
	function barColor(v) {
		if (v >= 80) return 'rgba(15,110,86,0.82)';
		if (v >= 50) return 'rgba(133,79,11,0.82)';
		return 'rgba(163,45,45,0.85)';
	}

	/** @param {number} sc */
	function statScoreClass(sc) {
		if (sc >= 80) return 'green';
		if (sc >= 50) return 'orange';
		return 'red';
	}

	/** @param {number|null} sc */
	function gradePillClass(sc) {
		if (sc == null) return 'pna';
		if (sc >= 90) return 'phi';
		if (sc >= 60) return 'pmd';
		return 'plo';
	}
	/** @param {number|null} sc */
	function gradeText(sc) {
		if (sc == null) return '-';
		if (sc >= 90) return '양호';
		if (sc >= 60) return '보통';
		return '미흡';
	}
	/** @param {number|null} sc */
	function scoreBarStyle(sc) {
		if (sc == null) return 'display:none';
		// 색상은 guTableRows 내부의 quantile 등급과 무관하게 절대값 기반 (bar 길이 표시용)
		const col = sc >= 80 ? '#0f6e56' : sc >= 60 ? '#8a5117' : '#a32d2d';
		const w = Math.round((sc * 40) / 100);
		return `background:${col};width:${w}px`;
	}

	const mapLegend = [
		{ color: '#1a9850', label: '90점+' },
		{ color: '#91cf60', label: '80–90점' },
		{ color: '#d9ef8b', label: '70–80점' },
		{ color: '#fee08b', label: '60–70점' },
		{ color: '#fdae61', label: '50–60점' },
		{ color: '#d73027', label: '40–50점' },
		{ color: '#a50026', label: '40점 미만' }
	];

	const facilityLegend = [
		{ color: '#1D9E75', label: '80점+ (의료접근 양호)' },
		{ color: '#f5a623', label: '50–80점 (보통)' },
		{ color: '#E74C3C', label: '50점 미만 (취약)' },
		{ color: '#f472b6', label: '의원' },
		{ color: '#e11d48', label: '병원' },
		{ color: '#7c3aed', label: '보건소' },
		{ color: '#1d4ed8', label: '종합병원' },
		{ color: '#10b981', label: '약국' }
	];
</script>

<svelte:head>
	<title>⑤ 의료 — 노인 병의원·약국 접근성 분석</title>
</svelte:head>

<section class="medical-hero">
	<div class="hero-glow"></div>
	<div class="medical-hero-inner">
		<div class="hero-text">
			<p class="hero-kicker">⑤ 의료 · 이정태</p>
			<h1 class="hero-title">
				노인 <em>병의원·약국</em> 접근성
			</h1>
			<div class="hero-chips">
				<span class="chip pink">🏥 병의원 {facilities.HOSP.length.toLocaleString()}개</span>
				<span class="chip pink">💊 약국 {facilities.PHARM.length.toLocaleString()}개</span>
				<span class="chip-sep">·</span>
				<span class="chip muted">서울 426개 행정동 · OSM 보행 네트워크 · Tobler 경사보정 · 건강보험심사평가원 2025</span>
			</div>
		</div>
	</div>
</section>

<section class="mx-auto max-w-[1340px] px-[18px] pb-[60px] pt-6">
	<!-- 컨트롤 -->
	<div class="ctrl">
		<div class="crow">
			<span class="lbl">비교 속도</span>
			{#each compareLabels as c (c.idx)}
				<button type="button" class="btn bw" class:on={cB === c.idx} onclick={() => (cB = c.idx)}>
					{c.emoji} {c.text} &nbsp;{c.speed}
				</button>
			{/each}
			{#if cB !== 0}<span class="text-[11px] ml-1.5" style:color="var(--color-text4)">기준: 일반인 1.28 m/s 고정</span>{/if}
		</div>
		<div class="crow">
			<span class="lbl">경사 보정</span>
			<button type="button" class="chk-btn slope" class:on={cSlope} onclick={() => (cSlope = !cSlope)}>
				<span class="chk-dot" style="background:#8B5CF6"></span>경사로 보정 (Tobler · NASA SRTM)
			</button>
		</div>
		<div class="crow">
			<span class="lbl">지도 레이어</span>
			<button type="button" class="chk-btn choropleth" class:on={showChoropleth}
				onclick={() => (showChoropleth = !showChoropleth)}>
				<span class="chk-dot" style="background:#1D9E75"></span>점수 채색
			</button>
			<button type="button" class="chk-btn" class:on={showUiwon}
				onclick={() => (showUiwon = !showUiwon)}>
				<span class="chk-dot" style="background:#f472b6"></span>의원
			</button>
			<button type="button" class="chk-btn" class:on={showHospital}
				onclick={() => (showHospital = !showHospital)}>
				<span class="chk-dot" style="background:#e11d48"></span>병원
			</button>
			<button type="button" class="chk-btn" class:on={showBogeon}
				onclick={() => (showBogeon = !showBogeon)}>
				<span class="chk-dot" style="background:#7c3aed"></span>보건소
			</button>
			<button type="button" class="chk-btn" class:on={showJonghap}
				onclick={() => (showJonghap = !showJonghap)}>
				<span class="chk-dot" style="background:#1d4ed8"></span>종합병원
			</button>
			<button type="button" class="chk-btn" class:on={showPharm}
				onclick={() => (showPharm = !showPharm)}>
				<span class="chk-dot" style="background:#10b981"></span>약국
			</button>
		</div>
		<div class="crow">
			<span class="lbl">기준 자치구</span>
			<select bind:value={cG}>
				{#each gus as g}
					<option value={g}>{g}</option>
				{/each}
			</select>
			<button type="button" class="chk-btn dong" class:on={showDongCircle}
				onclick={() => (showDongCircle = !showDongCircle)}>
				<span class="chk-dot" style="background:#ff6f00"></span>동 반경 원
			</button>
			<span class="text-[11px]" style:color="var(--color-text3)">
				자치구 중심 반경 + 선택 자치구 내 각 동 반경
			</span>
		</div>
		<div class="crow">
			<span class="lbl">보행 시간</span>
			{#each [15, 30, 45] as t (t)}
				<button type="button" class="btn" class:on={cT === t} onclick={() => (cT = t)}>{t}분</button>
			{/each}
			<span class="lbl" style="margin-left:12px">시설 유형</span>
			{#each [{v:'all',l:'전체'},{v:'hosp',l:'병의원'},{v:'pharm',l:'약국'}] as f (f.v)}
				<button type="button" class="btn" class:on={cF === f.v} onclick={() => (cF = f.v)}>{f.l}</button>
			{/each}
		</div>

		<!-- 통계 카드 (일반인 선택 시 2열, 비교 속도 선택 시 4열) -->
		<div class="sgrid" class:sgrid-2={cB === 0}>
			<div class="sc">
				<div class="sl" style:color="#db2777">🏥 {cG} 병의원 도달개수</div>
				{#if cB === 0}
					<div class="sv pink">{guStat.hospYoung.toFixed(1)}<span class="sv-unit"> 개</span></div>
					<div class="ss">일반인 {cT}분 기준</div>
				{:else}
					<div class="sv pink">{guStat.hospCB.toFixed(1)}<span class="sv-unit"> 개</span></div>
					<div class="ss">일반인 기준 {guStat.hospYoung.toFixed(1)}개 · {SPEEDS[cB].label} {cT}분</div>
				{/if}
			</div>
			<div class="sc">
				<div class="sl" style:color="#059669">💊 {cG} 약국 도달개수</div>
				{#if cB === 0}
					<div class="sv green">{guStat.pharmYoung.toFixed(1)}<span class="sv-unit"> 개</span></div>
					<div class="ss">일반인 {cT}분 기준</div>
				{:else}
					<div class="sv green">{guStat.pharmCB.toFixed(1)}<span class="sv-unit"> 개</span></div>
					<div class="ss">일반인 기준 {guStat.pharmYoung.toFixed(1)}개 · {SPEEDS[cB].label} {cT}분</div>
				{/if}
			</div>
			{#if cB !== 0}
			<div class="sc">
				<div class="sl">병의원 도달점수</div>
				<div class="sv {statScoreClass(guStat.hospScore)}">{guStat.hospScore.toFixed(1)}<span class="sv-unit"> 점</span></div>
				<div class="ss">{SPEEDS[cB].label} · {cG} 평균</div>
			</div>
			<div class="sc">
				<div class="sl">약국 도달점수</div>
				<div class="sv {statScoreClass(guStat.pharmScore)}">{guStat.pharmScore.toFixed(1)}<span class="sv-unit"> 점</span></div>
				<div class="ss">{SPEEDS[cB].label} · {cG} 평균</div>
			</div>
			{/if}
		</div>
	</div>

	<!-- r2: 지도 + 동별 도달가능점수 (선택 구) -->
	<div class="r2 mt-3.5">
		<Card title="병의원·약국 위치 및 의료 도달가능점수 (서울시)">
			<MapShell
				height="460px"
				legend={facilityLegend}
				source="병의원 {facilities.HOSP.length.toLocaleString()}개 · 약국 {facilities.PHARM.length.toLocaleString()}개"
			>
				<div bind:this={mapEl} class="absolute inset-0 h-full w-full"></div>
			</MapShell>
		</Card>
		<Card title="{cB === 0 ? `${cG} 동별 ${cF === 'all' ? '전체' : cF === 'hosp' ? '병의원' : '약국'} 시설 개수` : `${cG} 동별 도달가능점수`}">
			<div class="relative w-full" style:height="460px">
				<canvas bind:this={gcuCanvas} class="block h-full w-full"></canvas>
			</div>
		</Card>
	</div>

	<!-- r2b: 구별 영향 노인 수 + 점수×노인인구 버블 -->
	<div class="r2b mt-3.5">
		<Card title="구별 접근손실 가중 노인 수">
			<div class="relative w-full" style:height="420px">
				<canvas bind:this={impCanvas} class="block h-full w-full"></canvas>
			</div>
			<p class="text-[11px] mt-2" style:color="var(--color-text3)">
				접근손실 가중 노인 수 = 접근격차비율(1−점수/100) × 65세이상 인구 합산 — 접근성 손실을 인구 단위로 환산
			</p>
		</Card>
		<Card title="{cG} 점수 × 노인인구 버블">
			<div class="relative w-full" style:height="420px">
				<canvas bind:this={bblCanvas} class="block h-full w-full"></canvas>
			</div>
			<p class="text-[11px] mt-2" style:color="var(--color-text3)">
				버블 크기 = 접근손실 가중 노인 수 · 오른쪽 하단(노인 많고 점수 낮음)이 가장 취약
			</p>
		</Card>
	</div>

<!-- [주석처리] 산점도 (일반인 vs 보행보조 노인 접근 가능 시설 수) -->
	<!-- <div class="r2b mt-3.5">
		<Card title={scTitle}>
			<canvas bind:this={scCanvas} ...></canvas>
		</Card>
	</div> -->

	<!-- [주석처리] Top 차트 (영향 노인 수 TOP 10동 / 도달가능점수 최하위 10동) -->
	<!-- <div class="mt-3.5">
		<Card>
			<canvas bind:this={icCanvas} ...></canvas>
		</Card>
	</div> -->

	<!-- 자치구별 상세표 (기후 대시보드 동일 형식) -->
	<div class="mt-3.5">
		<div class="card-tbl">
			<div class="ct">자치구별 의료 접근성 상세표</div>
			<div class="tbl-wrap">
				<table class="ktbl">
					<thead>
						<tr>
							<th>자치구</th>
							<th>의원</th>
							<th>병원</th>
							<th>보건소</th>
							<th>종합병원</th>
							<th>약국</th>
							<th>병의원 점수</th>
							<th>약국 점수</th>
							<th>합산 점수</th>
							<th>접근성</th>
						</tr>
					</thead>
					<tbody>
						{#each guTableRows as r (r.gu)}
							<tr class:sel={r.sel}>
								<td style="text-align:left">{r.gu}</td>
								<td>{r.uiwon.toLocaleString()}</td>
								<td>{r.byeong}</td>
								<td>{r.bogeon}</td>
								<td>{r.jonghap}</td>
								<td>{r.pharm.toLocaleString()}</td>
								<td>
									<b style="color:#db2777">{r.hospScore.toFixed(1)}</b>
									<span class="score-bar" style={scoreBarStyle(r.hospScore)}></span>
								</td>
								<td>
									<b style="color:#059669">{r.pharmScore.toFixed(1)}</b>
									<span class="score-bar" style={scoreBarStyle(r.pharmScore)}></span>
								</td>
								<td>
									<b>{r.avgScore.toFixed(1)}</b>
									<span class="score-bar" style={scoreBarStyle(r.avgScore)}></span>
								</td>
								<td><span class="pill {r.grade}">{r.gradeText}</span></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<div class="tbl-src">
				합산 점수 = (병의원 도달가능점수 + 약국 도달가능점수) / 2 · 구 내 동 평균 · 합산 점수 내림차순
			</div>
		</div>
	</div>

	<!-- 노트 -->
	<Note tone="cool" class="mt-3">
		※ <b>일반인 (1.28 m/s)</b>를 기준으로 <b>{SPEEDS[cB].label} ({SPEEDS[cB].speed} m/s)</b>의
		도달가능점수를 표시합니다.<br />
		※ 도달가능점수 = (비교속도 도달 시설 수 / 일반인 도달 시설 수) × 100<br />
		※ 경사 보정: {cSlope
			? 'Tobler hiking function 기반 동별 속도 보정 (tobler_ratio_LEE.csv)'
			: '평지 기준 (보정 없음)'}<br />
		※ 거리 측정: 동 centroid 기준 OSM 보행 네트워크(다익스트라)
	</Note>
</section>

<style>
	/* 히어로 */
	.medical-hero {
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
		background: radial-gradient(circle, rgba(244,114,182,0.18), transparent 65%);
	}
	.medical-hero-inner {
		position: relative;
		max-width: 1340px;
		margin: 0 auto;
	}
	.hero-kicker {
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-pink);
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
		color: var(--color-pink);
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
	.chip.pink {
		background: rgba(244,114,182,0.15);
		color: #f472b6;
		border: 0.5px solid rgba(244,114,182,0.3);
	}
	.chip.muted {
		background: transparent;
		color: rgba(241,239,232,0.35);
	}
	.chip-sep {
		color: rgba(241,239,232,0.25);
		font-size: 11px;
	}

	/* 통계 카드 그리드 */
	.sgrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 10px; }
	.sgrid.sgrid-2 { grid-template-columns: repeat(2, 1fr); }
	.sc { background: var(--color-card-soft); padding: 12px 14px; border-radius: 8px; }
	.sl { font-size: 11px; color: var(--color-text3); margin-bottom: 3px; }
	.sv { font-size: 22px; font-weight: 500; color: var(--color-text); line-height: 1.2; }
	.sv.pink   { color: #db2777; }
	.sv.green  { color: #059669; }
	.sv.orange { color: #d97706; }
	.sv.red    { color: #c0392b; }
	.sv-unit { font-size: 12px; color: var(--color-text3); font-weight: 400; }
	.ss { font-size: 11px; color: var(--color-text3); margin-top: 2px; }

	/* 컨트롤 패널 */
	.ctrl {
		background: var(--color-card);
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 16px 20px;
		margin-bottom: 14px;
	}
	.crow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
	.crow:last-child { margin-bottom: 0; }
	.lbl {
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.06em;
		color: var(--color-text3);
		white-space: nowrap;
		margin-right: 2px;
	}

	/* 버튼 */
	.btn {
		font-size: 12px; padding: 5px 14px; border-radius: 20px;
		border: 0.5px solid var(--color-text4); background: transparent;
		color: var(--color-text2); cursor: pointer; transition: all 0.14s;
		font-family: inherit; white-space: nowrap;
	}
	.btn:hover { border-color: var(--color-text2); color: var(--color-text); }
	.btn.on {
		background: var(--pill-accent, var(--color-dark));
		color: var(--pill-on-text, var(--color-dark-text));
		border-color: var(--pill-accent, var(--color-dark));
	}
	.btn.on:hover { filter: brightness(1.08); }
	.btn.bw { border-radius: 8px; }

	.chk-btn {
		font-size: 12px; padding: 5px 13px; border-radius: 20px;
		border: 0.5px solid var(--color-text4); background: transparent;
		color: var(--color-text2); cursor: pointer; transition: all 0.14s;
		font-family: inherit; white-space: nowrap; display: flex; align-items: center; gap: 5px;
	}
	.chk-btn:hover { border-color: var(--color-text2); color: var(--color-text); }
	.chk-btn.on { background: rgba(0,0,0,0.06); border-color: var(--color-text3); color: var(--color-text); }
	.chk-btn.slope.on { background: #f0eafd; border-color: #8b5cf6; color: #5b21b6; }
	.chk-btn.choropleth.on { background: #e6f7f2; border-color: #1D9E75; color: #0d5c41; }
	.chk-btn.dong.on { background: #fff4e5; border-color: #ff6f00; color: #c05000; }

	select {
		font-size: 12px; padding: 5px 10px; border-radius: 8px;
		border: 0.5px solid var(--color-text4); background: var(--color-card);
		color: var(--color-text2); cursor: pointer; font-family: inherit;
	}
	select:focus { outline: none; border-color: var(--color-text2); }
	.chk-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

	/* 레이아웃 */
	.r2  { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; }
	.r2b { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
	@media (max-width: 900px) {
		.r2, .r2b { grid-template-columns: 1fr; }
		.sgrid { grid-template-columns: repeat(2, 1fr); }
	}

	/* 테이블 카드 */
	.card-tbl {
		background: var(--color-card);
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 16px 18px;
		position: relative;
	}
	.ct {
		font-size: 11px; font-weight: 500; letter-spacing: 0.06em;
		color: var(--color-text3); text-transform: uppercase; margin-bottom: 10px;
	}
	.tbl-src {
		font-size: 11px; color: var(--color-text3); margin-top: 8px; line-height: 1.7;
	}
	.tbl-wrap { overflow-x: auto; margin-top: 4px; }
	.ktbl { width: 100%; border-collapse: collapse; font-size: 12px; }
	.ktbl th {
		background: var(--color-card-soft); padding: 8px 10px; text-align: right;
		font-weight: 500; color: var(--color-text2); border-bottom: 1px solid var(--color-border);
		white-space: nowrap;
	}
	.ktbl th:first-child { text-align: left; }
	.ktbl th:last-child { text-align: center; }
	.ktbl td {
		padding: 7px 10px; border-bottom: 0.5px solid var(--color-border-soft);
		color: var(--color-text); text-align: right; white-space: nowrap;
	}
	.ktbl td:first-child { text-align: left; }
	.ktbl td:last-child { text-align: center; }
	.ktbl tr:last-child td { border-bottom: none; }
	.ktbl tr.sel td { background: var(--color-card-soft); font-weight: 500; }
	.ktbl tr:hover td { background: #fafaf8; }
	.score-bar { display: inline-block; height: 5px; border-radius: 3px; vertical-align: middle; margin-left: 4px; }

	/* 등급 필 */
	.pill { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
	.phi { background: #d4edda; color: #155724; }
	.pmd { background: #fff3cd; color: #856404; }
	.plo { background: #f8d7da; color: #721c24; }
	.pna { background: #ebebeb; color: #666; }

	:global(.leaflet-container) {
		background: #e8e4db !important;
	}
	:global(.dong-label) {
		background: rgba(255,255,255,0.88) !important;
		border: none !important;
		box-shadow: 0 1px 3px rgba(0,0,0,.18) !important;
		font-size: 10px !important;
		font-weight: 500 !important;
		padding: 2px 6px !important;
		border-radius: 4px !important;
		color: #2c2c2a !important;
		white-space: nowrap !important;
	}
	:global(.dong-label::before) { display: none !important; }
</style>
