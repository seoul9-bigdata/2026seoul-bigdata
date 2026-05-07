<script>
	import './layout.css';
	import { page } from '$app/state';
	import { base } from '$app/paths';
	import { ROUTES } from '$lib/nav.js';
	import Header from '$lib/components/Header.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();

	/** 현재 라우트의 도메인 액센트를 --pill-accent로 root-wrap에 inject */
	const path = $derived(
		page.url.pathname.replace(base, '').replace(/^\//, '').split('/')[0] || ''
	);
	const route = $derived(ROUTES.find((r) => r.slug === path));
	const accent = $derived(route?.accent || 'var(--color-dark)');
</script>

<svelte:head>
	<title>분(分)의 격차 — 서울 노인 도보 생활권 진단</title>
</svelte:head>

<Header />

<main class="min-h-[calc(100vh-58px)]" style:--pill-accent={accent}>
	{@render children()}
</main>

<Footer />
