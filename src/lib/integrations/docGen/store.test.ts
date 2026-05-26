// Tests for the docGen store — focused on the WI-016 proposal-accepted
// event bus. The active-client singleton + panel-state writable are
// covered indirectly by panelLifecycle + executeToolDispatch tests; the
// piece that's new and worth testing in isolation is the subscription
// `openDocGenIframe` attaches and how it populates `proposalAcceptedEvent`.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

import type { DocGenIframeClient } from './iframeClient';

// Mock the iframe client so `openDocGenIframe` doesn't try to wire a
// real postMessage listener. We capture the handler the store passes
// to `client.on('proposal-accepted', ...)` so the test can fire events
// at will.

let lastProposalAcceptedHandler: ((detail: unknown) => void) | null = null;

vi.mock('./iframeClient', () => ({
	connectDocGenIframe: vi.fn(() => {
		const client: DocGenIframeClient = {
			ready: Promise.resolve(),
			proposeEdit: vi.fn(),
			acceptProposal: vi.fn(),
			rejectProposal: vi.fn(),
			getState: vi.fn(),
			call: vi.fn(),
			on: vi.fn((event: string, handler: (detail: unknown) => void) => {
				if (event === 'proposal-accepted') {
					lastProposalAcceptedHandler = handler;
				}
				return () => {};
			}) as DocGenIframeClient['on'],
			disconnect: vi.fn()
		};
		return client;
	})
}));

import { disconnectDocGenIframe, openDocGenIframe, proposalAcceptedEvent } from './store';

function makeFakeIframe(): HTMLIFrameElement {
	return { contentWindow: {} } as unknown as HTMLIFrameElement;
}

describe('proposalAcceptedEvent (WI-016)', () => {
	beforeEach(() => {
		lastProposalAcceptedHandler = null;
		disconnectDocGenIframe();
		proposalAcceptedEvent.set(null);
	});

	it('publishes an event with proposalId + chatId when the iframe fires proposal-accepted', () => {
		openDocGenIframe({ iframe: makeFakeIframe(), docId: 'doc-a', chatId: 'chat-1' });
		expect(lastProposalAcceptedHandler).not.toBeNull();
		lastProposalAcceptedHandler!({ proposalId: 'p1' });
		const event = get(proposalAcceptedEvent);
		expect(event).toMatchObject({ proposalId: 'p1', chatId: 'chat-1' });
		expect(event!.seq).toBeGreaterThan(0);
	});

	it('increments seq for each event so subscribers can dedupe', () => {
		openDocGenIframe({ iframe: makeFakeIframe(), docId: 'doc-a', chatId: 'chat-1' });
		lastProposalAcceptedHandler!({ proposalId: 'p1' });
		const firstSeq = get(proposalAcceptedEvent)!.seq;
		lastProposalAcceptedHandler!({ proposalId: 'p2' });
		const secondSeq = get(proposalAcceptedEvent)!.seq;
		expect(secondSeq).toBeGreaterThan(firstSeq);
	});

	it('ignores events with missing or non-string proposalId', () => {
		openDocGenIframe({ iframe: makeFakeIframe(), docId: 'doc-a', chatId: 'chat-1' });
		// Sanity: set a baseline so we can detect a (wrongly) re-fired update.
		lastProposalAcceptedHandler!({ proposalId: 'p1' });
		const baseline = get(proposalAcceptedEvent)!.seq;

		lastProposalAcceptedHandler!({}); // missing proposalId
		lastProposalAcceptedHandler!(null);
		lastProposalAcceptedHandler!({ proposalId: '' });

		expect(get(proposalAcceptedEvent)!.seq).toBe(baseline);
	});

	it('tags the event with the chatId the panel was opened against', () => {
		openDocGenIframe({ iframe: makeFakeIframe(), docId: 'doc-a', chatId: 'chat-A' });
		lastProposalAcceptedHandler!({ proposalId: 'p1' });
		expect(get(proposalAcceptedEvent)!.chatId).toBe('chat-A');

		// Reopen against a different chat — the new subscription should use the new chatId.
		disconnectDocGenIframe();
		openDocGenIframe({ iframe: makeFakeIframe(), docId: 'doc-b', chatId: 'chat-B' });
		lastProposalAcceptedHandler!({ proposalId: 'p2' });
		expect(get(proposalAcceptedEvent)!.chatId).toBe('chat-B');
	});
});
