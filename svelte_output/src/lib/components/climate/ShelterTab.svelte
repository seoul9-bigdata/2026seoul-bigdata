<script>
	import { onMount, onDestroy } from 'svelte';
	import data from '$lib/data/climate.json';
	import CountUp from '$lib/components/CountUp.svelte';
	import 'leaflet/dist/leaflet.css';

	const {
		SPEEDS,
		HEAT_LOC,
		COLD_LOC,
		DONG_GEO,
		DONG_META,
		GU_GEO,
		GU_META,
		GU_POP,
		HULLS_D,
		HULLS_G,
		HULLS_SD,
		HULLS_SG,
		REACH_D,
		REACH_G,
		REACH_SD,
		REACH_SG
	} = data;

	// ── 상태 (runes) ───────────────────────────────────────────
	let cW = $state(0); // 보행자 유형 (0–3)
	let cT = $state(30); // 보행 시간
	let cUnit = $state('gu'); // 'gu' | 'dong'
	let cSel = $state(GU_META[0].cd);
	let cSlope = $state(false);
	let layerOn = $state({ heat: true, cold: true, choro: true });

	// 외부에서 보내는 시그널
	let { active = true } = $props();

	// ── 데이터 helpers ────────────────────────────────────────
	const activeReach = () =>
		cUnit === 'gu' ? (cSlope ? REACH_SG : REACH_G) : (cSlope ? REACH_SD : REACH_D);
	const activeHulls = () =>
		cUnit === 'gu' ? (cSlope ? HULLS_SG : HULLS_G) : (cSlope ? HULLS_SD : HULLS_D);

	function calcScore(cnt, cnt0) {
		if (!cnt0) return null;
		if (!cnt) return 0;
		return Math.min(100, (cnt / cnt0) * 100);
	}
	function avgScore(hScore, cScore) {
		if (hScore == null && cScore == null) return null;
		const vals = [hScore, cScore].filter((v) => v != null);
		return vals.reduce((a, b) => a + b, 0) / vals.length;
	}
	function fmtScore(s) {
		if (s == null) return '-';
		return (+s).toFixed(1);
	}
	function scoreColor(s) {
		if (s == null) return '#cccccc';
		if (s >= 80) return '#1D9E75';
		if (s >= 50) return '#f5a623';
		return '#E74C3C';
	}
	function scoreColorCls(s) {
		if (s == null) return 'default';
		return s >= 80 ? 'green' : s >= 50 ? 'default' : 'red';
	}

	function getReach(code, sid, t) {
		const r = activeReach();
		return r[code]?.[sid]?.[String(t)] || { heat: 0, cold: 0, heat_m: null, cold_m: null };
	}
	function getSelMeta() {
		if (cUnit === 'gu') return GU_META.find((g) => g.cd === cSel) || GU_META[0];
		return DONG_META.find((d) => d.cd === cSel) || DONG_META[0];
	}

	const _guBoundsCache = {};
	function getGuBbox(code) {
		if (_guBoundsCache[code]) return _guBoundsCache[code];
		const guCd = code && code.length > 5 ? code.slice(0, 5) : code;
		const feat = GU_GEO.features.find(
			(f) => f.properties.cd === guCd || f.properties.cd === code
		);
		if (!feat) return null;
		const coords =
			feat.geometry.type === 'Polygon'
				? feat.geometry.coordinates[0]
				: feat.geometry.coordinates.flat(2);
		let minLng = Infinity,
			maxLng = -Infinity,
			minLat = Infinity,
			maxLat = -Infinity;
		coords.forEach(([lng, lat]) => {
			if (lng < minLng) minLng = lng;
			if (lng > maxLng) maxLng = lng;
			if (lat < minLat) minLat = lat;
			if (lat > maxLat) maxLat = lat;
		});
		const pad = 0.003;
		const bbox = {
			minLat: minLat - pad,
			maxLat: maxLat + pad,
			minLng: minLng - pad,
			maxLng: maxLng + pad
		};
		_guBoundsCache[code] = bbox;
		return bbox;
	}

	function haversineM(lat1, lng1, lat2, lng2) {
		const R = 6371000,
			r = Math.PI / 180;
		const dLat = (lat2 - lat1) * r,
			dLng = (lng2 - lng1) * r;
		const a =
			Math.sin(dLat / 2) ** 2 +
			Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLng / 2) ** 2;
		return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
	}

	// ── 통계 계산 (derived) ───────────────────────────────────
	const stats = $derived.by(() => {
		const sid = SPEEDS[cW].id;
		const d = getReach(cSel, sid, cT);
		const d0 = getReach(cSel, 'g0', cT);
		const meta = getSelMeta();
		const hScore = calcScore(d.heat, d0.heat);
		const cScore = calcScore(d.cold, d0.cold);
		const avg = avgScore(hScore, cScore);
		return { sid, d, d0, meta, hScore, cScore, avg, isBase: cW === 0 };
	});

	// ── Leaflet 지도 ──────────────────────────────────────────
	let mapEl = $state();
	let map;
	let L;
	let heatLayer, coldLayer, bothLayer, choroLayer, hullLayer, drillLayer, selPinLayer;

	function makeBothIcon() {
		return L.divIcon({
			html: `<div style="width:11px;height:11px;border-radius:50%;background:conic-gradient(#FF8C00 0deg 180deg,#4A90D9 180deg 360deg);border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,.35)"></div>`,
			className: '',
			iconSize: [11, 11],
			iconAnchor: [5, 5]
		});
	}

	function updateMap() {
		if (!map || !L) return;
		const sid = SPEEDS[cW].id;
		const rKey = activeReach();
		const geoSrc = cUnit === 'gu' ? GU_GEO : DONG_GEO;

		if (choroLayer) map.removeLayer(choroLayer);
		if (drillLayer) map.removeLayer(drillLayer);
		if (heatLayer) map.removeLayer(heatLayer);
		if (coldLayer) map.removeLayer(coldLayer);
		if (bothLayer) map.removeLayer(bothLayer);
		if (hullLayer) map.removeLayer(hullLayer);
		if (selPinLayer) map.removeLayer(selPinLayer);

		choroLayer = L.geoJSON(geoSrc, {
			style: (f) => {
				const cd = f.properties.cd;
				const d = rKey[cd]?.[sid]?.[String(cT)];
				const d0 = rKey[cd]?.g0?.[String(cT)];
				const hs = calcScore(d?.heat, d0?.heat);
				const cs = calcScore(d?.cold, d0?.cold);
				const sc = avgScore(hs, cs);
				return {
					fillColor: scoreColor(sc),
					fillOpacity: 0.22,
					color: '#c0bcb4',
					weight: 0.8,
					opacity: 0.8,
					smoothFactor: 1.5
				};
			},
			onEachFeature: (f, layer) => {
				const p = f.properties;
				const cd = p.cd;
				const d = rKey[cd]?.[sid]?.[String(cT)];
				const d0 = rKey[cd]?.g0?.[String(cT)];
				const hs = calcScore(d?.heat, d0?.heat);
				const cs = calcScore(d?.cold, d0?.cold);
				const avg = avgScore(hs, cs);
				layer.bindTooltip(
					`<b>${p.nm}</b><br>합산 ${fmtScore(avg)}점 · 더위 ${fmtScore(hs)}점 · 한파 ${fmtScore(cs)}점`,
					{ direction: 'top' }
				);
				layer.on('click', () => {
					cSel = cd;
				});
			}
		});
		if (layerOn.choro) choroLayer.addTo(map);

		// 구 단위 선택 시 — 동별 드릴다운
		drillLayer = null;
		if (cUnit === 'gu' && cSel) {
			const drillRKey = cSlope ? REACH_SD : REACH_D;
			const guFeats = DONG_GEO.features.filter(
				(f) => f.properties.cd && f.properties.cd.startsWith(cSel)
			);
			if (guFeats.length > 0) {
				drillLayer = L.geoJSON(
					{ type: 'FeatureCollection', features: guFeats },
					{
						style: (f) => {
							const cd = f.properties.cd;
							const dd = drillRKey[cd]?.[sid]?.[String(cT)];
							const dd0 = drillRKey[cd]?.g0?.[String(cT)];
							const sc = avgScore(
								calcScore(dd?.heat, dd0?.heat),
								calcScore(dd?.cold, dd0?.cold)
							);
							return {
								fillColor: scoreColor(sc),
								fillOpacity: 0.62,
								color: '#ffffffa0',
								weight: 0.6,
								opacity: 0.9,
								smoothFactor: 1.5
							};
						},
						onEachFeature: (f, layer) => {
							const cd = f.properties.cd;
							const dd = drillRKey[cd]?.[sid]?.[String(cT)];
							const dd0 = drillRKey[cd]?.g0?.[String(cT)];
							const hs = calcScore(dd?.heat, dd0?.heat);
							const cs = calcScore(dd?.cold, dd0?.cold);
							const avg = avgScore(hs, cs);
							const dm = DONG_META.find((d) => d.cd === cd);
							layer.bindTooltip(
								`<b>${dm?.nm || cd}</b><br>합산 ${fmtScore(avg)}점 · 더위 ${fmtScore(hs)}점 · 한파 ${fmtScore(cs)}점`,
								{ direction: 'top' }
							);
							layer.on('click', () => {
								cUnit = 'dong';
								cSel = cd;
							});
						}
					}
				);
				if (layerOn.choro) drillLayer.addTo(map);
			}
		}

		// bbox 필터링
		const bbox = getGuBbox(cSel);
		const inBbox = (s) => {
			if (!bbox) return true;
			return s.lat >= bbox.minLat && s.lat <= bbox.maxLat && s.lng >= bbox.minLng && s.lng <= bbox.maxLng;
		};

		// 더위+한파 동시 좌표
		const heatCoordMap = new Map(HEAT_LOC.map((s) => [`${s.lat},${s.lng}`, s]));
		const bothLocs = COLD_LOC.filter((c) => heatCoordMap.has(`${c.lat},${c.lng}`)).map((c) => ({
			...c,
			heatName: heatCoordMap.get(`${c.lat},${c.lng}`).name
		}));

		heatLayer = L.layerGroup();
		HEAT_LOC.filter(inBbox).forEach((s) => {
			L.circleMarker([s.lat, s.lng], {
				radius: 5,
				fillColor: '#FF8C00',
				color: '#fff',
				weight: 1.5,
				fillOpacity: 0.9,
				interactive: true
			})
				.bindTooltip(`<b>${s.name}</b><br><span style="color:#888780">더위쉼터</span>`, {
					direction: 'top',
					offset: [0, -4]
				})
				.addTo(heatLayer);
		});
		if (layerOn.heat) heatLayer.addTo(map);

		coldLayer = L.layerGroup();
		COLD_LOC.filter(inBbox).forEach((s) => {
			L.circleMarker([s.lat, s.lng], {
				radius: 5,
				fillColor: '#4A90D9',
				color: '#fff',
				weight: 1.5,
				fillOpacity: 0.9,
				interactive: true
			})
				.bindTooltip(`<b>${s.name}</b><br><span style="color:#888780">한파쉼터</span>`, {
					direction: 'top',
					offset: [0, -4]
				})
				.addTo(coldLayer);
		});
		if (layerOn.cold) coldLayer.addTo(map);

		const bIcon = makeBothIcon();
		bothLayer = L.layerGroup();
		bothLocs.filter(inBbox).forEach((s) => {
			L.marker([s.lat, s.lng], { icon: bIcon, interactive: true, zIndexOffset: 500 })
				.bindTooltip(
					`<b>${s.heatName}</b> / <b>${s.name}</b><br><span style="color:#888780">더위+한파쉼터</span>`,
					{ direction: 'top', offset: [0, -5] }
				)
				.addTo(bothLayer);
		});
		if (layerOn.heat && layerOn.cold) bothLayer.addTo(map);

		highlightSel();
	}

	function highlightSel() {
		if (!map || !L || !cSel) return;
		if (hullLayer) map.removeLayer(hullLayer);
		if (selPinLayer) map.removeLayer(selPinLayer);
		const geoSrc = cUnit === 'gu' ? GU_GEO : DONG_GEO;
		const feat = geoSrc.features.find((f) => f.properties.cd === cSel);
		if (feat) {
			hullLayer = L.geoJSON(feat, {
				style: {
					fillColor: 'transparent',
					color: '#2060c0',
					weight: 2.5,
					opacity: 0.9,
					smoothFactor: 0
				}
			}).addTo(map);
			if (cUnit === 'gu') map.fitBounds(hullLayer.getBounds(), { padding: [30, 30], maxZoom: 13 });
			else map.panTo(hullLayer.getBounds().getCenter(), { animate: true });
		}
		if (cUnit === 'gu') return;

		const meta = getSelMeta();
		if (meta && meta.lat) {
			const pinIcon = L.divIcon({
				html: `<div style="width:14px;height:14px;border-radius:50%;background:#2c2c2a;border:3px solid #fff;box-shadow:0 0 0 2px #2c2c2a"></div>`,
				className: '',
				iconSize: [14, 14],
				iconAnchor: [7, 7]
			});
			selPinLayer = L.marker([meta.lat, meta.lng], { icon: pinIcon, zIndexOffset: 1000 })
				.bindTooltip(`<b>${meta.nm}</b><br>보행권 시각화 기준점`, {
					direction: 'top',
					permanent: false
				})
				.addTo(map);
		}
		const hulls = activeHulls();
		const hdata = hulls[cSel];
		if (hdata && meta && meta.lat) {
			const tKey = String(cT);
			const th = hdata[tKey];
			if (th) {
				const R = 111111,
					cosLat = Math.cos((meta.lat * Math.PI) / 180);
				SPEEDS.slice()
					.reverse()
					.forEach((s, ri) => {
						const i = 3 - ri;
						const hull = th[s.id];
						if (!hull || hull.length < 3) return;
						const latlngs = hull.map(([dx, dy]) => [
							meta.lat + dy / R,
							meta.lng + dx / (R * cosLat)
						]);
						const poly = L.polygon(latlngs, {
							fillColor: s.color,
							fillOpacity: i === cW ? 0.18 : 0.07,
							color: s.color,
							weight: i === cW ? 2.2 : 0.7,
							opacity: i === cW ? 0.9 : 0.35,
							dashArray: i === cW ? null : '4,3'
						});
						if (hullLayer) poly.addTo(hullLayer);
					});
			}
		}
	}

	onMount(async () => {
		if (typeof window === 'undefined') return;
		const leaflet = await import('leaflet');
		L = leaflet.default;
		map = L.map(mapEl, { center: [37.5665, 126.978], zoom: 11 });
		L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
			attribution: '© OSM · © CartoDB',
			maxZoom: 19,
			subdomains: 'abcd'
		}).addTo(map);
		updateMap();

		// Chart.js — bar (구별 합산 점수) + line (시간대별)
		const ChartMod = await import('chart.js/auto');
		Chart = ChartMod.default;
		setupGcChart();
		setupWcChart();
		drawNetwork();
	});

	onDestroy(() => {
		if (map) {
			map.remove();
			map = null;
		}
		if (gcChart) gcChart.destroy();
		if (wcChart) wcChart.destroy();
	});

	// 활성 탭 전환 시 invalidateSize
	$effect(() => {
		if (active && map) {
			setTimeout(() => map.invalidateSize(), 0);
		}
	});

	// reactive: 컨트롤 변경 → 갱신
	$effect(() => {
		// 의존성: cW, cT, cUnit, cSel, cSlope, layerOn
		void cW;
		void cT;
		void cUnit;
		void cSel;
		void cSlope;
		void layerOn.heat;
		void layerOn.cold;
		void layerOn.choro;
		if (map && L) {
			updateMap();
		}
		if (Chart) {
			// gc chart: cW===0이면 destroy, 아니면 setup or update
			if (cW === 0) {
				if (gcChart) {
					gcChart.destroy();
					gcChart = null;
				}
			} else if (canvasGc) {
				if (!gcChart) setupGcChart();
				else updateGcChart();
			}
			// wc chart
			if (canvasWc) {
				if (!wcChart) setupWcChart();
				else updateWcChart();
			}
		}
		if (canvasNetwork) drawNetwork();
	});

	// ── Chart.js — 구별 합산 점수 바차트 ─────────────────────
	let canvasGc = $state();
	let canvasWc = $state();
	let canvasNetwork = $state();
	let gcChart, wcChart, Chart;

	function gcRows() {
		const sid = SPEEDS[cW].id;
		const rKey = cSlope ? REACH_SG : REACH_G;
		return GU_META.map((g) => {
			const d = rKey[g.cd]?.[sid]?.[String(cT)];
			const d0 = rKey[g.cd]?.g0?.[String(cT)];
			const sc = avgScore(calcScore(d?.heat, d0?.heat), calcScore(d?.cold, d0?.cold));
			return { nm: g.nm, val: sc ?? 0, cd: g.cd };
		}).sort((a, b) => b.val - a.val);
	}

	function setupGcChart() {
		if (!canvasGc || !Chart) return;
		const rows = gcRows();
		const labels = rows.map((r) => r.nm);
		const dataArr = rows.map((r) => +fmtScore(r.val));
		const bgs = rows.map((r) => (r.cd === cSel ? '#2c2c2a' : scoreColor(r.val) + 'cc'));
		gcChart = new Chart(canvasGc, {
			type: 'bar',
			data: { labels, datasets: [{ data: dataArr, backgroundColor: bgs, borderRadius: 3, borderSkipped: false }] },
			options: {
				indexAxis: 'y',
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: {
					x: {
						grid: { color: '#f1efe8' },
						ticks: { font: { size: 10 }, color: '#888780' },
						min: 0,
						max: 100,
						title: {
							display: true,
							text: '도달가능 합산 점수 (0–100)',
							font: { size: 10 },
							color: '#888780'
						}
					},
					y: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#2c2c2a' } }
				}
			}
		});
	}

	function updateGcChart() {
		if (cW === 0) {
			if (gcChart) {
				gcChart.destroy();
				gcChart = null;
			}
			return;
		}
		if (!gcChart) {
			setupGcChart();
			return;
		}
		const rows = gcRows();
		gcChart.data.labels = rows.map((r) => r.nm);
		gcChart.data.datasets[0].data = rows.map((r) => +fmtScore(r.val));
		gcChart.data.datasets[0].backgroundColor = rows.map((r) =>
			r.cd === cSel ? '#2c2c2a' : scoreColor(r.val) + 'cc'
		);
		gcChart.update('none');
	}

	function setupWcChart() {
		if (!canvasWc || !Chart) return;
		const code = cSel;
		const rKey = activeReach();
		const datasets = SPEEDS.map((s, i) => {
			const dataArr = [15, 30, 45].map((t) => {
				const d = rKey[code]?.[s.id]?.[String(t)];
				const d0 = rKey[code]?.g0?.[String(t)];
				return avgScore(calcScore(d?.heat, d0?.heat), calcScore(d?.cold, d0?.cold)) ?? 0;
			});
			return {
				label: s.label,
				data: dataArr,
				borderColor: s.color,
				backgroundColor: s.color + '22',
				fill: false,
				tension: 0.3,
				borderWidth: i === cW ? 2.5 : 1,
				pointRadius: i === cW ? 4 : 2
			};
		});
		wcChart = new Chart(canvasWc, {
			type: 'line',
			data: { labels: ['15분', '30분', '45분'], datasets },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { position: 'bottom', labels: { font: { size: 10 }, boxWidth: 12 } } },
				scales: {
					x: { grid: { color: '#f1efe8' }, ticks: { font: { size: 11 }, color: '#888780' } },
					y: {
						grid: { color: '#f1efe8' },
						ticks: { font: { size: 11 }, color: '#888780' },
						min: 0,
						max: 100,
						title: {
							display: true,
							text: '도달가능 합산 점수',
							font: { size: 10 },
							color: '#888780'
						}
					}
				}
			}
		});
	}

	function updateWcChart() {
		if (!wcChart) return;
		const code = cSel;
		const rKey = activeReach();
		const datasets = SPEEDS.map((s, i) => {
			const dataArr = [15, 30, 45].map((t) => {
				const d = rKey[code]?.[s.id]?.[String(t)];
				const d0 = rKey[code]?.g0?.[String(t)];
				return avgScore(calcScore(d?.heat, d0?.heat), calcScore(d?.cold, d0?.cold)) ?? 0;
			});
			return {
				label: s.label,
				data: dataArr,
				borderColor: s.color,
				backgroundColor: s.color + '22',
				fill: false,
				tension: 0.3,
				borderWidth: i === cW ? 2.5 : 1,
				pointRadius: i === cW ? 4 : 2
			};
		});
		wcChart.data.datasets = datasets;
		wcChart.update('none');
	}

	// ── 단절망 (다크 캔버스) ──────────────────────────────────
	let cv_guPoints = [];
	function drawNetwork() {
		const cv = canvasNetwork;
		if (!cv) return;
		const ctx = cv.getContext('2d');
		const W = cv.width,
			H = cv.height;
		ctx.clearRect(0, 0, W, H);

		if (cUnit === 'gu') {
			drawGuScatter(ctx, W, H);
			return;
		}

		ctx.fillStyle = '#06060f';
		ctx.fillRect(0, 0, W, H);

		const meta = getSelMeta();
		if (!meta || !meta.lat) return;
		const selDistM = SPEEDS[cW].mps * cT * 60;
		const maxDistM = selDistM * 1.25;
		const cx = W / 2,
			cy = H / 2;
		const scale = (Math.min(W, H) / 2 - 18) / maxDistM;
		const gridStep = selDistM > 2000 ? 1000 : 500;

		for (let d = gridStep; d <= maxDistM; d += gridStep) {
			ctx.beginPath();
			ctx.arc(cx, cy, d * scale, 0, Math.PI * 2);
			ctx.strokeStyle = '#ffffff08';
			ctx.lineWidth = 0.5;
			ctx.stroke();
		}
		ctx.beginPath();
		ctx.arc(cx, cy, selDistM * scale, 0, Math.PI * 2);
		ctx.strokeStyle = SPEEDS[cW].color + '55';
		ctx.lineWidth = 1.2;
		ctx.stroke();

		const dReach = getReach(cSel, SPEEDS[cW].id, cT);
		const dBase = getReach(cSel, 'g0', cT);
		const hCnt = Math.min(Math.round(dReach?.heat || 0), Math.round(dBase?.heat || 0));
		const cCnt = Math.min(Math.round(dReach?.cold || 0), Math.round(dBase?.cold || 0));

		const bbox = getGuBbox(cSel);
		const inBbox = (s) => {
			if (!bbox) return true;
			return (
				s.lat >= bbox.minLat && s.lat <= bbox.maxLat && s.lng >= bbox.minLng && s.lng <= bbox.maxLng
			);
		};

		function drawLocs(locs, cnt, color, dotColor) {
			const vis = [];
			locs.forEach((s) => {
				if (!inBbox(s)) return;
				const distM = haversineM(meta.lat, meta.lng, s.lat, s.lng);
				if (distM <= maxDistM * 1.05) vis.push({ s, distM });
			});
			vis.sort((a, b) => a.distM - b.distM);
			vis.forEach(({ s, distM }, idx) => {
				const bearing =
					Math.atan2(
						(s.lng - meta.lng) * Math.cos((meta.lat * Math.PI) / 180),
						s.lat - meta.lat
					);
				const rPx = Math.min(distM * scale, Math.min(W, H) / 2 - 5);
				const sx = cx + rPx * Math.sin(bearing),
					sy = cy - rPx * Math.cos(bearing);
				const reach = idx < cnt;
				if (reach) {
					const grad = ctx.createLinearGradient(cx, cy, sx, sy);
					grad.addColorStop(0, color + '50');
					grad.addColorStop(0.65, color + 'aa');
					grad.addColorStop(1, color + '20');
					ctx.beginPath();
					ctx.moveTo(cx, cy);
					ctx.lineTo(sx, sy);
					ctx.strokeStyle = grad;
					ctx.lineWidth = 1.2;
					ctx.shadowColor = color;
					ctx.shadowBlur = 4;
					ctx.stroke();
					ctx.shadowBlur = 0;
					ctx.beginPath();
					ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
					ctx.fillStyle = dotColor;
					ctx.shadowColor = color;
					ctx.shadowBlur = 7;
					ctx.fill();
					ctx.shadowBlur = 0;
				} else {
					const segs = 3 + Math.min(4, Math.floor(distM / 800));
					for (let seg = 0; seg < segs; seg++) {
						const t0 = seg / segs,
							t1 = (seg + 0.42) / segs;
						const jx = (Math.random() - 0.5) * 4,
							jy = (Math.random() - 0.5) * 4;
						ctx.beginPath();
						ctx.moveTo(cx + (sx - cx) * t0 + jx, cy + (sy - cy) * t0 + jy);
						ctx.lineTo(cx + (sx - cx) * t1 + jx, cy + (sy - cy) * t1 + jy);
						ctx.strokeStyle = '#E74C3C22';
						ctx.lineWidth = 0.5;
						ctx.stroke();
					}
					ctx.beginPath();
					ctx.arc(sx, sy, 1.2, 0, Math.PI * 2);
					ctx.fillStyle = '#E74C3C33';
					ctx.fill();
				}
			});
			return vis.length;
		}

		if (layerOn.heat) drawLocs(HEAT_LOC, hCnt, '#FF8C00', '#FFB04A');
		if (layerOn.cold) drawLocs(COLD_LOC, cCnt, '#4A90D9', '#82bcf0');

		const cgr = ctx.createRadialGradient(cx, cy, 0, cx, cy, 14);
		cgr.addColorStop(0, '#ffffff');
		cgr.addColorStop(0.45, SPEEDS[cW].color + '88');
		cgr.addColorStop(1, 'transparent');
		ctx.beginPath();
		ctx.arc(cx, cy, 12, 0, Math.PI * 2);
		ctx.fillStyle = cgr;
		ctx.shadowColor = SPEEDS[cW].color;
		ctx.shadowBlur = 22;
		ctx.fill();
		ctx.shadowBlur = 0;

		ctx.font = '10px system-ui';
		ctx.textAlign = 'left';
		ctx.fillStyle = '#FF8C00aa';
		ctx.fillText(`더위 ${hCnt}개 도달`, 8, H - 22);
		ctx.fillStyle = '#4A90D9aa';
		ctx.fillText(`한파 ${cCnt}개 도달`, 8, H - 8);
	}

	function drawGuScatter(ctx, W, H) {
		const BG = '#fafaf8',
			GRID = '#e0ddd7',
			AXIS = '#b0aca4',
			TXT = '#5f5e5a',
			TXT2 = '#2c2c2a';
		ctx.fillStyle = BG;
		ctx.fillRect(0, 0, W, H);
		cv_guPoints = [];

		const guMeta = GU_META.find((g) => g.cd === cSel);
		if (!cSel || !guMeta) {
			ctx.fillStyle = TXT;
			ctx.font = '12px system-ui';
			ctx.textAlign = 'center';
			ctx.fillText('구를 선택하세요', W / 2, H / 2);
			return;
		}
		if (cW === 0) {
			const cx = W / 2,
				cy = H / 2;
			ctx.fillStyle = TXT;
			ctx.font = '13px system-ui';
			ctx.textAlign = 'center';
			ctx.fillText('📊 일반인은 비교 기준값(분모)이므로', cx, cy - 18);
			ctx.fillText('모든 동이 100점 — 다른 보행자 유형을 선택하세요', cx, cy + 6);
			ctx.fillStyle = GRID;
			ctx.font = '11px system-ui';
			ctx.fillText(guMeta.nm, cx, cy + 32);
			return;
		}
		const drillRKey = cSlope ? REACH_SD : REACH_D;
		const sid = SPEEDS[cW].id;
		const dongs = DONG_META.filter((d) => d.gc === cSel);
		const pts = dongs.map((d) => {
			const r = drillRKey[d.cd]?.[sid]?.[String(cT)];
			const r0 = drillRKey[d.cd]?.g0?.[String(cT)];
			const sc = avgScore(calcScore(r?.heat, r0?.heat), calcScore(r?.cold, r0?.cold)) ?? 0;
			return { nm: d.nm, p65: d.p65, score: sc, cd: d.cd };
		});
		const maxP65 = Math.max(...pts.map((p) => p.p65), 1);
		const pad = { l: 44, r: 18, t: 30, b: 42 };
		const pw = W - pad.l - pad.r;
		const ph = H - pad.t - pad.b;

		ctx.fillStyle = TXT2;
		ctx.font = 'bold 11px system-ui';
		ctx.textAlign = 'left';
		ctx.fillText(`${guMeta.nm} · 동별 접근성 취약도 (${cT}분 / ${SPEEDS[cW].label})`, pad.l, 19);

		ctx.fillStyle = '#E74C3C0d';
		ctx.fillRect(pad.l, pad.t + ph * 0.5, pw, ph * 0.5);
		ctx.fillStyle = '#E74C3C55';
		ctx.font = '9px system-ui';
		ctx.textAlign = 'right';
		ctx.fillText('미흡 구간', pad.l + pw - 3, pad.t + ph - 6);

		[0, 25, 50, 75, 100].forEach((v) => {
			const py = pad.t + ph - (v / 100) * ph;
			ctx.beginPath();
			ctx.moveTo(pad.l, py);
			ctx.lineTo(pad.l + pw, py);
			ctx.strokeStyle = v === 50 ? '#c0bcb455' : GRID;
			ctx.lineWidth = v === 50 ? 1 : 0.7;
			ctx.stroke();
			ctx.fillStyle = TXT;
			ctx.font = '9px system-ui';
			ctx.textAlign = 'right';
			ctx.fillText(v, pad.l - 5, py + 3);
		});
		[0, 0.5, 1].forEach((r) => {
			const v = Math.round(maxP65 * r);
			const px = pad.l + r * pw;
			ctx.beginPath();
			ctx.moveTo(px, pad.t);
			ctx.lineTo(px, pad.t + ph);
			ctx.strokeStyle = GRID;
			ctx.lineWidth = 0.5;
			ctx.stroke();
			ctx.fillStyle = TXT;
			ctx.font = '9px system-ui';
			ctx.textAlign = 'center';
			ctx.fillText(v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v, px, pad.t + ph + 14);
		});
		ctx.strokeStyle = AXIS;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(pad.l, pad.t);
		ctx.lineTo(pad.l, pad.t + ph);
		ctx.lineTo(pad.l + pw, pad.t + ph);
		ctx.stroke();
		ctx.fillStyle = TXT;
		ctx.font = '9px system-ui';
		ctx.textAlign = 'center';
		ctx.fillText('65세 이상 인구수 →', pad.l + pw / 2, H - 5);
		ctx.save();
		ctx.translate(11, pad.t + ph / 2);
		ctx.rotate(-Math.PI / 2);
		ctx.fillText('접근성 점수 (0–100)', 0, 0);
		ctx.restore();

		pts.forEach((p) => {
			const x = pad.l + (p.p65 / maxP65) * pw;
			const y = pad.t + ph - (p.score / 100) * ph;
			const col = scoreColor(p.score);
			ctx.beginPath();
			ctx.arc(x, y, 5, 0, Math.PI * 2);
			ctx.fillStyle = col + 'cc';
			ctx.strokeStyle = col;
			ctx.lineWidth = 0.8;
			ctx.fill();
			ctx.stroke();
			cv_guPoints.push({ x, y, nm: p.nm, p65: p.p65, score: p.score });
		});
		const sorted = [...pts].sort((a, b) => a.score - b.score);
		const labeled = [...sorted.slice(0, 2), sorted[sorted.length - 1]];
		labeled.forEach((p) => {
			const x = pad.l + (p.p65 / maxP65) * pw;
			const y = pad.t + ph - (p.score / 100) * ph;
			ctx.fillStyle = TXT2;
			ctx.font = 'bold 9px system-ui';
			ctx.textAlign = x > pad.l + pw * 0.7 ? 'right' : 'left';
			ctx.fillText(p.nm, x + (x > pad.l + pw * 0.7 ? -8 : 8), y + 3);
		});
	}

	// ── 컨트롤 핸들러 ──────────────────────────────────────────
	function setW(i) {
		cW = i;
	}
	function setT(t) {
		cT = t;
	}
	function setUnit(u) {
		cUnit = u;
		// 기본 선택값 보정
		if (u === 'gu') {
			if (!GU_META.find((g) => g.cd === cSel)) cSel = GU_META[0].cd;
			else if (cSel.length > 5) cSel = cSel.slice(0, 5);
		} else {
			if (!DONG_META.find((d) => d.cd === cSel)) {
				const first = DONG_META.find((d) => d.gc === cSel) || DONG_META[0];
				cSel = first.cd;
			}
		}
	}
	function togHeat() {
		layerOn = { ...layerOn, heat: !layerOn.heat };
	}
	function togCold() {
		layerOn = { ...layerOn, cold: !layerOn.cold };
	}
	function togSlope() {
		cSlope = !cSlope;
	}
	function togChoro() {
		layerOn = { ...layerOn, choro: !layerOn.choro };
	}

	// 상세표 행
	const tableRows = $derived.by(() => {
		const sid = SPEEDS[cW].id;
		const rKey = cSlope ? REACH_SG : REACH_G;
		return GU_META.map((g) => {
			const d = rKey[g.cd]?.[sid]?.[String(cT)];
			const d0 = rKey[g.cd]?.g0?.[String(cT)];
			const hs = calcScore(d?.heat, d0?.heat);
			const cs = calcScore(d?.cold, d0?.cold);
			const avg = avgScore(hs, cs);
			const sel = g.cd === cSel && cUnit === 'gu';
			return { ...g, hs, cs, avg, sel };
		}).sort((a, b) => (b.avg ?? -1) - (a.avg ?? -1));
	});

	function gradePillClass(sc) {
		return sc == null ? 'plo' : sc >= 80 ? 'phi' : sc >= 50 ? 'pmd' : 'plo';
	}
	function gradeText(sc) {
		return sc == null ? '-' : sc >= 80 ? '양호' : sc >= 50 ? '보통' : '미흡';
	}
	function scoreBarStyle(sc) {
		if (sc == null) return 'display:none';
		const col = scoreColor(sc);
		const w = Math.round((sc * 40) / 100);
		return `background:${col};width:${w}px`;
	}
</script>

<!-- 컨트롤 패널 -->
<div class="ctrl">
	<div class="crow">
		<span class="lbl">보행자 유형</span>
		{#each ['🚶 일반인 1.28 m/s', '🧓 건강 노인 1.12 m/s', '🦽 보행보조 노인 0.88 m/s', '🦽 보행보조 하위 15% 0.70 m/s'] as label, i}
			<button
				type="button"
				class="btn bw"
				class:on={cW === i}
				onclick={() => setW(i)}
			>
				{label}
			</button>
		{/each}
	</div>
	<div class="crow">
		<span class="lbl">보행 시간</span>
		{#each [15, 30, 45] as t}
			<button type="button" class="btn" class:on={cT === t} onclick={() => setT(t)}>{t}분</button>
		{/each}
	</div>
	<div class="crow">
		<span class="lbl">행정 단위</span>
		<button type="button" class="btn" class:on={cUnit === 'gu'} onclick={() => setUnit('gu')}>자치구</button>
		<button type="button" class="btn" class:on={cUnit === 'dong'} onclick={() => setUnit('dong')}>행정동</button>
		<span style="margin-left:6px;color:#d3d1c7">|</span>
		<span class="lbl" style="margin-left:6px">레이어</span>
		<button type="button" class="chk-btn" class:on={layerOn.heat} onclick={togHeat}>
			<span class="chk-dot" style="background:#FF8C00"></span>더위쉼터
		</button>
		<button type="button" class="chk-btn cold" class:on={layerOn.cold} onclick={togCold}>
			<span class="chk-dot" style="background:#4A90D9"></span>한파쉼터
		</button>
		<button type="button" class="chk-btn slope" class:on={cSlope} onclick={togSlope}>
			<span class="chk-dot" style="background:#8B5CF6"></span>경사 보정
		</button>
		<button type="button" class="chk-btn" class:on={layerOn.choro} onclick={togChoro}>
			<span class="chk-dot" style="background:#1D9E75"></span>배경 폴리곤
		</button>
	</div>
	<div class="crow">
		<span class="lbl">기준 지역</span>
		<select bind:value={cSel} style="min-width:160px">
			{#if cUnit === 'gu'}
				{#each GU_META as g (g.cd)}
					<option value={g.cd}>{g.nm}</option>
				{/each}
			{:else}
				{#each DONG_META as d (d.cd)}
					<option value={d.cd}>{d.gnm} {d.nm}</option>
				{/each}
			{/if}
		</select>
	</div>

	<!-- 통계 4열 카드 -->
	<div class="sgrid">
		{#key cUnit + '|' + cSel + '|' + cW + '|' + cT + '|' + cSlope}
		{#if cUnit === 'gu'}
			{@const gu = GU_META.find((g) => g.cd === cSel)}
			{@const hTotal = gu?.heat ?? 0}
			{@const cTotal = gu?.cold ?? 0}
			{#if stats.isBase}
				<div class="sc">
					<div class="sl" style:color="#d46800">☀️ 더위쉼터</div>
					<div class="sv orange"><CountUp value={hTotal} /><span class="sv-unit"> 개소</span></div>
					<div class="ss">{stats.meta?.nm || ''} 구 내 등록 시설</div>
				</div>
				<div class="sc">
					<div class="sl" style:color="#1a5fa0">❄️ 한파쉼터</div>
					<div class="sv blue"><CountUp value={cTotal} /><span class="sv-unit"> 개소</span></div>
					<div class="ss">{stats.meta?.nm || ''} 구 내 등록 시설</div>
				</div>
				<div class="sc">
					<div class="sl">합산 접근성 점수</div>
					<div class="sv-msg">다른 보행자 유형을<br />선택하면 표시됩니다</div>
					<div class="ss">일반인은 비교 기준값 (분모)</div>
				</div>
				<div class="sc">
					<div class="sl">도달가능 점수란?</div>
					<div class="sl-info">
						<b>산식:</b> 선택 유형 동 평균 도달 수 ÷ 일반인 동 평균 × 100<br />
						<b>구 단위:</b> 구 내 동들의 도달 가능 개수 평균<br />
						<b>동 클릭:</b> 해당 동으로 드릴다운
					</div>
				</div>
			{:else}
				<div class="sc">
					<div class="sl" style:color="#d46800">☀️ 더위쉼터 접근성</div>
					<div class="sv {scoreColorCls(stats.hScore)}">
						{#if stats.hScore == null}-{:else}<CountUp value={+stats.hScore} decimals={1} />{/if}<span class="sv-unit"> 점</span>
					</div>
					<div class="ss">{SPEEDS[cW].label} · 구 내 동 평균</div>
				</div>
				<div class="sc">
					<div class="sl" style:color="#1a5fa0">❄️ 한파쉼터 접근성</div>
					<div class="sv {scoreColorCls(stats.cScore)}">
						{#if stats.cScore == null}-{:else}<CountUp value={+stats.cScore} decimals={1} />{/if}<span class="sv-unit"> 점</span>
					</div>
					<div class="ss">{SPEEDS[cW].label} · 구 내 동 평균</div>
				</div>
				<div class="sc">
					<div class="sl">합산 접근성 점수</div>
					<div class="sv {scoreColorCls(stats.avg)}" style:font-size="28px">
						{#if stats.avg == null}-{:else}<CountUp value={+stats.avg} decimals={1} />{/if}<span class="sv-unit"> 점</span>
					</div>
					<div class="ss">(더위 + 한파) / 2 · {stats.meta?.nm || ''}</div>
				</div>
				<div class="sc">
					<div class="sl">도달가능 점수란?</div>
					<div class="sl-info">
						<b>산식:</b> 선택 유형 동 평균 도달 수 ÷ 일반인 동 평균 × 100<br />
						<b>구 단위:</b> 구 내 동들의 도달 가능 개수 평균<br />
						<b>동 클릭:</b> 해당 동으로 드릴다운
					</div>
				</div>
			{/if}
		{:else}
			{@const h0 = Math.round(stats.d0.heat || 0)}
			{@const c0 = Math.round(stats.d0.cold || 0)}
			{@const hCnt = Math.min(Math.round(stats.d.heat || 0), h0)}
			{@const cCnt = Math.min(Math.round(stats.d.cold || 0), c0)}
			<div class="sc">
				<div class="sl" style:color="#d46800">☀️ 더위쉼터 도달가능</div>
				{#if stats.isBase}
					<div class="sv orange" style:font-size="18px"><CountUp value={hCnt} /><span class="sv-unit"> 개 도달 가능</span></div>
					<div class="ss">일반인 {cT}분 기준 도달 가능 개소</div>
				{:else}
					<div class="cnt-line">
						<b><CountUp value={hCnt} /></b><span class="sv-unit"> 개</span>
						<span class="sv-unit-sm">/ 일반인 {h0}개</span>
					</div>
					<div class="ss">{SPEEDS[cW].label} · {cT}분 도달 가능</div>
					<div class="score-line">
						<span class="sv-score {scoreColorCls(stats.hScore)}">
							{#if stats.hScore == null}-{:else}<CountUp value={+stats.hScore} decimals={1} />{/if}
						</span>
						<span class="sv-unit"> 점</span>
					</div>
				{/if}
			</div>
			<div class="sc">
				<div class="sl" style:color="#1a5fa0">❄️ 한파쉼터 도달가능</div>
				{#if stats.isBase}
					<div class="sv blue" style:font-size="18px"><CountUp value={cCnt} /><span class="sv-unit"> 개 도달 가능</span></div>
					<div class="ss">일반인 {cT}분 기준 도달 가능 개소</div>
				{:else}
					<div class="cnt-line">
						<b><CountUp value={cCnt} /></b><span class="sv-unit"> 개</span>
						<span class="sv-unit-sm">/ 일반인 {c0}개</span>
					</div>
					<div class="ss">{SPEEDS[cW].label} · {cT}분 도달 가능</div>
					<div class="score-line">
						<span class="sv-score {scoreColorCls(stats.cScore)}">
							{#if stats.cScore == null}-{:else}<CountUp value={+stats.cScore} decimals={1} />{/if}
						</span>
						<span class="sv-unit"> 점</span>
					</div>
				{/if}
			</div>
			{#if stats.isBase}
				<div class="sc">
					<div class="sl">합산 접근성 점수</div>
					<div class="sv-msg">다른 보행자 유형을<br />선택하면 표시됩니다</div>
					<div class="ss">일반인은 비교 기준값 (분모)</div>
				</div>
			{:else}
				<div class="sc">
					<div class="sl">합산 접근성 점수</div>
					<div class="sv {scoreColorCls(stats.avg)}">
						{#if stats.avg == null}-{:else}<CountUp value={+stats.avg} decimals={1} />{/if}<span class="sv-unit"> 점</span>
					</div>
					<div class="ss">(더위 + 한파) / 2 · {stats.meta?.nm || ''}</div>
				</div>
			{/if}
			<div class="sc">
				<div class="sl">도달가능 점수란?</div>
				<div class="sl-info">
					<b>산식:</b> 선택 유형 도달 개수 ÷ 일반인 도달 개수 × 100<br />
					<b>경사 보정:</b> 경사도별 속도 감소율 적용<br />
					<b>일반인 미표시:</b> 분모값이 곧 일반인 도달 수이므로 항상 100점
				</div>
			</div>
		{/if}
		{/key}
	</div>
</div>

<!-- 지도 + 단절망 -->
<div class="r2">
	<div class="card">
		<div class="ct">서울시 기후쉼터 접근성 — 합산 도달가능 점수</div>
		<div class="map-wrap">
			<div bind:this={mapEl} class="lmap"></div>
		</div>
		<div class="leg">
			<div class="li"><div class="ld" style="background:#1D9E75"></div>합산 점수 높음 (80+)</div>
			<div class="li"><div class="ld" style="background:#f5a623"></div>중간 (50–80)</div>
			<div class="li"><div class="ld" style="background:#E74C3C"></div>낮음 (&lt;50)</div>
			<div class="li" style:opacity={layerOn.heat ? 1 : 0.35}>
				<div class="ld" style="background:#FF8C00;border-radius:50%"></div>더위쉼터
			</div>
			<div class="li" style:opacity={layerOn.cold ? 1 : 0.35}>
				<div class="ld" style="background:#4A90D9;border-radius:50%"></div>한파쉼터
			</div>
		</div>
		<div class="src">
			합산 도달가능 점수 = (더위쉼터 점수 + 한파쉼터 점수) / 2 · 일반인 기준 100점<br />
			클릭: 해당 지역 선택 · Convex Hull 보행권 오버레이
		</div>
	</div>
	<div class="card">
		<div class="ct">{cUnit === 'gu' ? '구 내 동별 취약도 분포 — 65세 인구 × 접근성 점수' : '단절망 — 보행 도달 가능 연결 시각화'}</div>
		<canvas bind:this={canvasNetwork} class="dark-canvas" width="500" height="370" style:background={cUnit === 'gu' ? '#fafaf8' : '#080a10'}></canvas>
		<div class="src" style="margin-top:5px">
			{#if cUnit === 'gu'}
				각 점 = 동 · 색: 접근성 등급 · 좌하단 = 고령 많고 접근 낮음 (최취약)
			{:else}
				중심→쉼터 광섬유 연결 · 도달 가능=빛나는 라인 / 불가=단절된 파편 · 주황=더위쉼터 / 청=한파쉼터
			{/if}
		</div>
	</div>
</div>

<!-- 차트 2열 -->
<div class="r2b">
	<div class="card">
		<div class="ct">자치구별 기후쉼터 도달가능 합산 점수</div>
		<div class="chart-wrap">
			{#if cW === 0}
				<div class="chart-msg">
					<div style="font-size:28px">📊</div>
					<div style="font-size:13px;font-weight:500;color:#5f5e5a">보행자 유형을 선택하세요</div>
					<div class="chart-msg-sub">일반인은 비교 기준값(분모)이므로<br />모든 구가 <b>100점</b> — 비교 의미 없음</div>
				</div>
			{:else}
				<canvas bind:this={canvasGc}></canvas>
			{/if}
		</div>
	</div>
	<div class="card">
		<div class="ct">선택 지역 — 시간대별 도달가능 점수</div>
		<div class="chart-wrap"><canvas bind:this={canvasWc}></canvas></div>
	</div>
</div>

<!-- 상세표 -->
<div class="card" style="position:relative">
	<div class="ct">자치구별 기후쉼터 접근성 상세표</div>
	<div class="tbl-wrap">
		<table class="ktbl">
			<thead>
				<tr>
					<th>자치구</th>
					<th>더위쉼터</th>
					<th>한파쉼터</th>
					<th>더위 점수</th>
					<th>한파 점수</th>
					<th>합산 점수</th>
					<th>접근성</th>
				</tr>
			</thead>
			<tbody>
				{#each tableRows as r (r.cd)}
					<tr class:sel={r.sel}>
						<td style="text-align:left">{r.nm}</td>
						<td>{r.heat}</td>
						<td>{r.cold}</td>
						<td>
							<b style="color:#d46800">{fmtScore(r.hs)}</b>
							<span class="score-bar" style={scoreBarStyle(r.hs)}></span>
						</td>
						<td>
							<b style="color:#1a5fa0">{fmtScore(r.cs)}</b>
							<span class="score-bar" style={scoreBarStyle(r.cs)}></span>
						</td>
						<td>
							<b>{fmtScore(r.avg)}</b>
							<span class="score-bar" style={scoreBarStyle(r.avg)}></span>
						</td>
						<td><span class="pill {gradePillClass(r.avg)}">{gradeText(r.avg)}</span></td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if cW === 0}
		<div class="tbl-overlay">
			<div style="font-size:28px">📋</div>
			<div style="font-size:13px;font-weight:500;color:#5f5e5a">보행자 유형을 선택하세요</div>
			<div class="tbl-overlay-sub">일반인은 비교 기준값(분모)이므로<br />모든 구가 <b>100점</b> — 비교 의미 없음</div>
		</div>
	{/if}
</div>

<style>
	.ctrl {
		background: #fff;
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 14px 20px;
		margin-bottom: 14px;
	}
	.crow {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
		margin-bottom: 9px;
	}
	.crow:last-child {
		margin-bottom: 0;
	}
	.lbl {
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.06em;
		color: var(--color-text3);
		white-space: nowrap;
		margin-right: 2px;
	}
	.btn {
		font-size: 12px;
		padding: 5px 14px;
		border-radius: 20px;
		border: 0.5px solid var(--color-text4);
		background: transparent;
		color: var(--color-text2);
		cursor: pointer;
		transition: all 0.14s;
		font-family: inherit;
		white-space: nowrap;
	}
	.btn:hover {
		border-color: var(--color-text2);
		color: var(--color-text);
	}
	.btn.on {
		background: var(--pill-accent, var(--color-dark));
		color: var(--pill-on-text, var(--color-dark-text));
		border-color: var(--pill-accent, var(--color-dark));
	}
	.btn.on:hover {
		filter: brightness(1.08);
	}
	.btn.bw {
		border-radius: 8px;
	}
	.chk-btn {
		font-size: 12px;
		padding: 5px 13px;
		border-radius: 20px;
		border: 0.5px solid var(--color-text4);
		background: transparent;
		color: var(--color-text2);
		cursor: pointer;
		transition: all 0.14s;
		font-family: inherit;
		white-space: nowrap;
		display: flex;
		align-items: center;
		gap: 5px;
	}
	.chk-btn:hover {
		border-color: var(--color-text2);
		color: var(--color-text);
	}
	.chk-btn.on {
		background: #fff8ee;
		border-color: #ff8c00;
		color: #c06000;
	}
	.chk-btn.cold.on {
		background: #eaf3fd;
		border-color: #4a90d9;
		color: #1a5fa0;
	}
	.chk-btn.slope.on {
		background: #f0eafd;
		border-color: #8b5cf6;
		color: #5b21b6;
	}
	.chk-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	select {
		font-family: inherit;
		font-size: 12px;
		padding: 5px 10px;
		border: 0.5px solid var(--color-text4);
		border-radius: 6px;
		background: #fff;
		color: var(--color-text);
		cursor: pointer;
		outline: none;
	}
	select:focus {
		border-color: var(--color-text2);
	}
	.sgrid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 10px;
		margin-top: 10px;
	}
	.sc {
		background: var(--color-card-soft);
		border-radius: 8px;
		padding: 12px 14px;
	}
	.sl {
		font-size: 11px;
		color: var(--color-text3);
		margin-bottom: 3px;
	}
	.sv {
		font-size: 22px;
		font-weight: 500;
	}
	.sv.red {
		color: #c0392b;
	}
	.sv.green {
		color: #0f6e56;
	}
	.sv.blue {
		color: #185fa5;
	}
	.sv.orange {
		color: #d46800;
	}
	.ss {
		font-size: 11px;
		color: var(--color-text3);
		margin-top: 2px;
	}
	.sv-unit {
		font-size: 12px;
		color: var(--color-text3);
	}
	.sv-unit-sm {
		font-size: 11px;
		color: var(--color-text3);
		margin-left: 4px;
	}
	.sv-msg {
		font-size: 13px;
		color: var(--color-text3);
		line-height: 1.6;
	}
	.sl-info {
		font-size: 11px;
		color: var(--color-text2);
		line-height: 1.8;
	}
	.cnt-line {
		font-size: 15px;
		font-weight: 500;
		color: var(--color-text);
		line-height: 1.5;
	}
	.cnt-line b {
		font-weight: 500;
	}
	.score-line {
		margin-top: 5px;
	}
	.sv-score {
		font-size: 19px;
		font-weight: 500;
	}
	.sv-score.red {
		color: #c0392b;
	}
	.sv-score.green {
		color: #0f6e56;
	}
	.r2 {
		display: grid;
		grid-template-columns: 1.45fr 1fr;
		gap: 14px;
		margin-bottom: 14px;
	}
	.r2b {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 14px;
		margin-bottom: 14px;
	}
	.card {
		background: #fff;
		border: 0.5px solid var(--color-border);
		border-radius: 12px;
		padding: 16px 18px;
		min-width: 0;
		overflow: hidden;
	}
	.ct {
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.06em;
		color: var(--color-text3);
		text-transform: uppercase;
		margin-bottom: 10px;
	}
	.map-wrap {
		position: relative;
		height: 420px;
		border-radius: 8px;
		overflow: hidden;
		background: #e8e4db;
	}
	.lmap {
		position: absolute;
		inset: 0;
		height: 100% !important;
	}
	.leg {
		display: flex;
		gap: 14px;
		flex-wrap: wrap;
		margin-top: 9px;
	}
	.li {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 11px;
		color: var(--color-text2);
	}
	.ld {
		width: 12px;
		height: 12px;
		border-radius: 2px;
		flex-shrink: 0;
	}
	.dark-canvas {
		display: block;
		width: 100%;
		border-radius: 8px;
	}
	.chart-wrap {
		position: relative;
		height: 260px;
		width: 100%;
	}
	.chart-msg {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		height: 100%;
		gap: 10px;
		padding: 20px;
	}
	.chart-msg-sub {
		font-size: 11px;
		color: #aaa9a5;
		text-align: center;
		line-height: 1.7;
		background: var(--color-card-soft);
		border-radius: 8px;
		padding: 10px 16px;
	}
	.src {
		font-size: 11px;
		color: var(--color-text3);
		margin-top: 8px;
		line-height: 1.7;
	}
	.tbl-wrap {
		overflow-x: auto;
		margin-top: 14px;
	}
	.ktbl {
		width: 100%;
		border-collapse: collapse;
		font-size: 12px;
	}
	.ktbl th {
		background: var(--color-card-soft);
		padding: 8px 10px;
		text-align: right;
		font-weight: 500;
		color: var(--color-text2);
		border-bottom: 1px solid var(--color-border);
		white-space: nowrap;
	}
	.ktbl th:first-child {
		text-align: left;
	}
	.ktbl th:last-child {
		text-align: center;
	}
	.ktbl td {
		padding: 7px 10px;
		border-bottom: 0.5px solid var(--color-border-soft);
		color: var(--color-text);
		text-align: right;
		white-space: nowrap;
	}
	.ktbl td:first-child {
		text-align: left;
	}
	.ktbl td:last-child {
		text-align: center;
	}
	.ktbl tr:last-child td {
		border-bottom: none;
	}
	.ktbl tr.sel td {
		background: var(--color-bg2);
		font-weight: 500;
	}
	.ktbl tr:hover td {
		background: #fafaf8;
	}
	.pill {
		display: inline-block;
		padding: 2px 8px;
		border-radius: 10px;
		font-size: 11px;
		font-weight: 500;
	}
	.phi {
		background: #d4edda;
		color: #155724;
	}
	.pmd {
		background: #fff3cd;
		color: #856404;
	}
	.plo {
		background: #f8d7da;
		color: #721c24;
	}
	.score-bar {
		display: inline-block;
		height: 5px;
		border-radius: 3px;
		vertical-align: middle;
		margin-left: 4px;
	}
	.tbl-overlay {
		position: absolute;
		inset: 0;
		border-radius: 12px;
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
		padding: 10px 16px;
		border: 0.5px solid var(--color-border);
	}
	@media (max-width: 900px) {
		.r2,
		.r2b,
		.sgrid {
			grid-template-columns: 1fr;
		}
	}

	/* leaflet 컨트롤 위에서 색깔 보존 */
	:global(.leaflet-tile-pane) {
		filter: none;
	}
</style>
