import i18next from 'i18next';
import resourcesToBackend from 'i18next-resources-to-backend';
import LanguageDetector from 'i18next-browser-languagedetector';
import type { i18n as i18nType } from 'i18next';
import { writable } from 'svelte/store';

const createI18nStore = (i18n: i18nType) => {
	const i18nWritable = writable(i18n);

	i18n.on('initialized', () => {
		i18nWritable.set(i18n);
	});
	i18n.on('loaded', () => {
		i18nWritable.set(i18n);
	});
	i18n.on('added', () => i18nWritable.set(i18n));
	i18n.on('languageChanged', (lang) => {
		i18nWritable.set(i18n);
		if (typeof document !== 'undefined') {
			document.documentElement.setAttribute('lang', lang);
		}
	});
	return i18nWritable;
};

const createIsLoadingStore = (i18n: i18nType) => {
	const isLoading = writable(false);

	// if loaded resources are empty || {}, set loading to true
	i18n.on('loaded', (resources) => {
		// console.log('loaded:', resources);
		isLoading.set(Object.keys(resources).length === 0);
	});

	// if resources failed loading, set loading to true
	i18n.on('failedLoading', () => {
		isLoading.set(true);
	});

	return isLoading;
};

export const initI18n = (defaultLocale?: string | undefined) => {
	// When DEFAULT_LOCALE is set on the server (compose env), the product
	// chooses the language for users instead of letting per-browser locale
	// detection win. Without this override, a user whose browser was set to
	// en-US during a previous visit (or whose localStorage `locale` was
	// auto-cached as en-US) keeps seeing English even after we ship full
	// Dutch translations. We don't want that here — the UI is meant to be
	// Dutch by default, with the language picker still available for
	// explicit per-user override (which writes localStorage and survives).
	if (defaultLocale && typeof localStorage !== 'undefined') {
		const stored = localStorage.getItem('locale');
		// Treat en-US as "the OWUI shipped default that was never explicitly
		// chosen", and override to defaultLocale. Any other localStorage
		// value (e.g. user picked en-GB or fr-FR) is preserved.
		if (!stored || stored === 'en-US') {
			localStorage.setItem('locale', defaultLocale);
		}
	}

	const detectionOrder = defaultLocale
		? ['querystring', 'localStorage']
		: ['querystring', 'localStorage', 'navigator'];
	const fallbackDefaultLocale = defaultLocale ? [defaultLocale] : ['en-US'];

	const loadResource = (language: string, namespace: string) =>
		import(`./locales/${language}/${namespace}.json`);

	i18next
		.use(resourcesToBackend(loadResource))
		.use(LanguageDetector)
		.init({
			debug: false,
			detection: {
				order: detectionOrder,
				caches: ['localStorage'],
				lookupQuerystring: 'lang',
				lookupLocalStorage: 'locale'
			},
			fallbackLng: {
				fr: ['fr-FR'],
				default: fallbackDefaultLocale
			},
			ns: 'translation',
			returnEmptyString: false,
			interpolation: {
				escapeValue: false // not needed for svelte as it escapes by default
			}
		});
};

const i18n = createI18nStore(i18next);
const isLoadingStore = createIsLoadingStore(i18next);

export const getLanguages = async () => {
	const languages = (await import(`./locales/languages.json`)).default;
	return languages;
};
export const changeLanguage = (lang: string) => {
	document.documentElement.setAttribute('lang', lang);
	i18next.changeLanguage(lang);
};

export default i18n;
export const isLoading = isLoadingStore;
