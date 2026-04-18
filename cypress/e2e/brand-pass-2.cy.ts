/// <reference path="../support/index.d.ts" />

// Brand Pass 2 smoke tests. Covers spec criteria B, C, D, F, G, H.
// (A is static asset content-type — covered by scripts/measure-brand.sh.
//  E is DB-level — covered by measure-brand.sh.
//  I is file presence — covered by measure-brand.sh.)
//
// Prerequisites: rm-chatbot running at Cypress baseUrl with brand-pass-2
// env applied. RM assistants seeded (via rm-tools/register_assistants.py).
describe('Brand Pass 2', () => {
	after(() => {
		// eslint-disable-next-line cypress/no-unnecessary-waiting
		cy.wait(2000);
	});

	context('PWA manifest (B)', () => {
		it('serves RM-branded manifest.json', () => {
			cy.request('/manifest.json').then((resp) => {
				expect(resp.status).to.eq(200);
				expect(resp.body.name).to.not.contain('Open WebUI');
				expect(resp.body.background_color).to.be.oneOf(['#F7F4EF', '#161620']);
				expect(resp.body.icons).to.have.length.greaterThan(0);
				expect(resp.body.icons[0].src).to.match(/^\/brand-assets\//);
			});
		});
	});

	context('Trust banner (C)', () => {
		beforeEach(() => {
			cy.loginAdmin();
		});

		it('exposes the non-dismissible Dutch trust banner in /api/v1/configs', () => {
			cy.request({
				url: '/api/v1/configs',
				headers: {
					Authorization: `Bearer ${Cypress.env('TOKEN') || localStorage.getItem('token') || ''}`
				}
			}).then((resp) => {
				const banners = resp.body?.ui?.banners ?? resp.body?.banners ?? [];
				const match = banners.find((b: { content?: string }) =>
					(b?.content ?? '').includes('Besloten werkomgeving voor Ruimtemeesters')
				);
				expect(match, 'trust banner present').to.exist;
				expect(match.dismissible, 'banner is non-dismissible').to.eq(false);
			});
		});
	});

	context('Personalized greeting (D)', () => {
		beforeEach(() => {
			cy.loginAdmin();
			cy.visit('/');
		});

		it('renders a Dutch greeting with the logged-in user first name', () => {
			// Admin user name from seed is "Ralph Schraven" — first name is "Ralph".
			cy.contains(/Hoi\s+Ralph,\s+waarmee kan ik je vandaag helpen\?/i, {
				timeout: 10_000
			}).should('exist');
		});
	});

	context('Community sharing disabled (F)', () => {
		beforeEach(() => {
			cy.loginAdmin();
		});

		it('reports enable_community_sharing=false in configs', () => {
			cy.request({
				url: '/api/v1/configs',
				headers: {
					Authorization: `Bearer ${Cypress.env('TOKEN') || localStorage.getItem('token') || ''}`
				}
			}).then((resp) => {
				const flag =
					resp.body?.features?.enable_community_sharing ?? resp.body?.enable_community_sharing;
				expect(flag).to.eq(false);
			});
		});
	});

	context('Default model (G)', () => {
		beforeEach(() => {
			cy.loginAdmin();
		});

		it('returns gemini.gemini-2.5-flash-lite as default in configs', () => {
			cy.request({
				url: '/api/v1/configs',
				headers: {
					Authorization: `Bearer ${Cypress.env('TOKEN') || localStorage.getItem('token') || ''}`
				}
			}).then((resp) => {
				const dm = resp.body?.default_models ?? resp.body?.ui?.default_models ?? '';
				expect(dm).to.eq('gemini.gemini-2.5-flash-lite');
			});
		});
	});

	context('About modal copy (H)', () => {
		beforeEach(() => {
			cy.loginAdmin();
			cy.visit('/');
		});

		it('About tab contains RM attribution line', () => {
			// Open user menu → Settings → About
			cy.get('button[aria-label="User menu"], button[aria-label="Open user menu"]')
				.first()
				.click({ force: true });
			cy.contains('Settings', { matchCase: false }).click({ force: true });
			cy.contains(/^About$/).click({ force: true });
			cy.contains('Gebouwd op Open WebUI').should('exist');
		});
	});
});
