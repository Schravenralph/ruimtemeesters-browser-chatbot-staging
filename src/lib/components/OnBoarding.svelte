<script>
	import { getContext, onMount } from 'svelte';
	const i18n = getContext('i18n');

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME } from '$lib/stores';

	import Marquee from './common/Marquee.svelte';
	import ArrowRightCircle from './icons/ArrowRightCircle.svelte';

	export let show = true;
	export let getStartedHandler = () => {};

	let logoSrc = `${WEBUI_BASE_URL}/brand-assets/logo-blue.png`;

	function setLogoImage() {
		if (typeof document === 'undefined') return;
		const isDarkMode = document.documentElement.classList.contains('dark');
		logoSrc = isDarkMode
			? `${WEBUI_BASE_URL}/brand-assets/logo-white.png`
			: `${WEBUI_BASE_URL}/brand-assets/logo-blue.png`;
	}

	$: if (show) {
		setLogoImage();
	}
</script>

{#if show}
	<div
		class="w-full h-screen max-h-[100dvh] relative bg-rm-white text-rm-raisin dark:bg-rm-raisin dark:text-rm-white"
	>
		<div class="relative w-full h-screen max-h-[100dvh] flex z-10">
			<div class="flex flex-col w-full items-center justify-between py-16 lg:py-20 text-center">
				<!-- Big centered wordmark -->
				<div class="flex flex-col items-center gap-6 mt-8">
					<img
						crossorigin="anonymous"
						src={logoSrc}
						class="h-20 lg:h-28 w-auto"
						alt="{$WEBUI_NAME} logo"
					/>
				</div>

				<!-- Display title — Abhaya Libre Extra Bold -->
				<div class="flex flex-col items-center gap-3 max-w-3xl px-6">
					<h1 class="brand-display text-5xl lg:text-7xl leading-[1.05]">
						{$WEBUI_NAME}
					</h1>
					<div class="font-secondary text-3xl lg:text-4xl text-rm-blue dark:text-rm-pumpkin">
						<Marquee
							duration={4000}
							words={[
								$i18n.t('Ruimtelijke onderbouwingen, sneller.'),
								$i18n.t('Beleid lezen. Antwoorden geven.'),
								$i18n.t('Toetsen, motiveren, doorzetten.'),
								$i18n.t('Van regelwerk naar besluit.'),
								$i18n.t('Een collega die meekijkt — 24/7.')
							]}
						/>
					</div>
					<p class="font-primary text-base lg:text-lg opacity-80 mt-2">
						{$i18n.t('Kleine acties. Grote impact.')}
					</p>
				</div>

				<!-- CTA -->
				<div class="flex flex-col items-center">
					<button
						aria-label={$i18n.t('Get started')}
						class="relative z-20 inline-flex items-center justify-center w-14 h-14 rounded-full bg-rm-blue text-white hover:bg-rm-pumpkin transition-colors shadow-lg"
						on:click={() => {
							getStartedHandler();
						}}
					>
						<ArrowRightCircle className="size-7" aria-hidden="true" />
					</button>
					<div class="mt-2 font-primary text-sm uppercase tracking-widest" aria-hidden="true">
						{$i18n.t(`Get started`)}
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
