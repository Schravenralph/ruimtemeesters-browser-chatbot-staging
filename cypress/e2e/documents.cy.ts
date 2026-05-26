// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference path="../support/index.d.ts" />

// Smoke coverage for the Document-Generator toggle button (WI-014).
// The full open-lifecycle (mint docId, mount iframe, postMessage handshake)
// is covered by manual + the panelLifecycle vitest suite; this just
// verifies the button is wired into the chat navbar and the click path
// reaches the no-chat early-return.

describe('DocGen toggle button — smoke', () => {
	// Cypress video recording sometimes drops the last frames; mirror the
	// pattern used in chat.cy.ts so the closing assertion stays on tape.
	after(() => {
		// eslint-disable-next-line cypress/no-unnecessary-waiting
		cy.wait(2000);
	});

	beforeEach(() => {
		cy.loginAdmin();
		cy.visit('/');
	});

	it('renders for admin and starts in the closed state', () => {
		cy.get('button[aria-label="Document openen"]')
			.should('be.visible')
			.and('have.attr', 'aria-pressed', 'false');
	});

	it('shows the no-chat toast when clicked from the home page', () => {
		// Home page has no active chat; the click should hit the
		// `if (!initialChatId)` branch in openDocGenPanelForCurrentChat
		// and surface the Dutch toast instead of attempting to mint a doc.
		cy.get('button[aria-label="Document openen"]').click();
		cy.contains('Start een chat voordat je een document opent').should('be.visible');
		// Button must return to the closed state — busy guard releases.
		cy.get('button[aria-label="Document openen"]').should('have.attr', 'aria-pressed', 'false');
	});
});
