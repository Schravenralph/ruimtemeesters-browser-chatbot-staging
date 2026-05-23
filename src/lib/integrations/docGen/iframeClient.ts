// Typed postMessage RPC client for the Document-Generator iframe (WI-014).
//
// The DG iframe (`https://doc-gen.datameesters.nl/iframe-embed.html?...`)
// runs WI-013's bridge: accepts `rmdg:request` messages from a trusted
// parent origin, dispatches to the embed's Web-Component methods, posts
// `rmdg:response` and `rmdg:event` back. This module is the parent side
// of that conversation.
//
// API shape: typed methods (`proposeEdit`, `acceptProposal`, ...) wrap
// the wire protocol. Compile-time safety via DocGenToolArgs from
// `./tools` — refactor a method's signature in DG and this client (and
// its callers) refuse to compile.
//
// Lifecycle: one client per iframe instance. `ready` resolves on the
// one-shot `rmdg:ready` handshake from WI-013's bridge. `disconnect()`
// tears down the window listener and rejects in-flight calls.

import {
	bridgeMethodFor,
	type DocGenProposalInput,
	type DocGenStateForModel,
	type DocGenToolName
} from './tools';

// ─── Wire protocol (mirror of WI-013's iframePostMessageBridge.ts) ─────

interface RmdgRequest {
	type: 'rmdg:request';
	requestId: string;
	method: string;
	args: unknown[];
}

interface RmdgResponse {
	type: 'rmdg:response';
	requestId: string;
	success: boolean;
	value?: unknown;
	error?: { name: string; message: string };
}

interface RmdgEvent {
	type: 'rmdg:event';
	name: string;
	detail: unknown;
}

interface RmdgReady {
	type: 'rmdg:ready';
}

type RmdgInbound = RmdgResponse | RmdgEvent | RmdgReady;

// ─── Event names the bridge re-broadcasts ──────────────────────────────

export type DocGenEventName =
	| 'ready'
	| 'change'
	| 'save'
	| 'save-error'
	| 'download'
	| 'title-change'
	| 'proposal-pending'
	| 'proposal-accepted'
	| 'proposal-rejected'
	| 'proposal-rejected-overlap';

// ─── Public client surface ──────────────────────────────────────────────

export interface DocGenIframeClient {
	/** Resolves on the one-shot `rmdg:ready` handshake. Reject only on
	 *  `disconnect()` before ready. */
	ready: Promise<void>;
	/** Typed dispatch. Args + result types come from DocGenToolArgs/Results;
	 *  signatures live on the client surface below. */
	proposeEdit(p: DocGenProposalInput): Promise<{ proposalId: string; status: 'pending' }>;
	acceptProposal(proposalId: string): Promise<{ applied: true }>;
	rejectProposal(proposalId: string): Promise<{ applied: true }>;
	getState(): Promise<DocGenStateForModel>;
	/** Generic escape hatch for non-LLM-callable bridge methods (e.g.
	 *  `download`, `updateTitle`, `save`, `getVersions`). Keep typed call
	 *  sites preferring the named methods above; this is for the rare
	 *  consumer that needs the full bridge surface. */
	call<T = unknown>(method: string, args?: unknown[]): Promise<T>;
	/** Subscribe to embed events. Returns an unsubscribe fn. */
	on(event: DocGenEventName, handler: (detail: unknown) => void): () => void;
	/** Tear down the window listener, reject pending calls, drop subscribers. */
	disconnect(): void;
}

// ─── Config ─────────────────────────────────────────────────────────────

export interface ConnectOptions {
	/** The iframe element. We post to `iframe.contentWindow` and gate
	 *  inbound messages on `event.source === iframe.contentWindow`. */
	iframe: { contentWindow: Window | null };
	/** Origin of the iframe. We use this both as the postMessage
	 *  targetOrigin and as the inbound `event.origin` allowlist (exact
	 *  match, default-deny). */
	iframeOrigin: string;
	/** Per-call timeout. Default 15s — generous for a slow chain (auth
	 *  + bundle load + first ready) but short enough to surface bugs. */
	timeoutMs?: number;
	/** Window for the listener. Defaults to `globalThis.window`; tests
	 *  inject a fake. */
	window?: Pick<Window, 'addEventListener' | 'removeEventListener'>;
	/** Override for logging. Defaults to `console.warn`. */
	warn?: (message: string, ...args: unknown[]) => void;
}

// ─── Implementation ─────────────────────────────────────────────────────

interface PendingCall {
	resolve: (value: unknown) => void;
	reject: (err: Error) => void;
	timer: ReturnType<typeof setTimeout>;
}

export function connectDocGenIframe(opts: ConnectOptions): DocGenIframeClient {
	const {
		iframe,
		iframeOrigin,
		timeoutMs = 15_000,
		window: win = globalThis.window,
		warn = (msg, ...args) => console.warn(msg, ...args)
	} = opts;

	const pending = new Map<string, PendingCall>();
	const subscribers = new Map<DocGenEventName, Set<(detail: unknown) => void>>();

	let disconnected = false;
	let readyResolve: (() => void) | null = null;
	let readyReject: ((err: Error) => void) | null = null;
	const ready = new Promise<void>((resolve, reject) => {
		readyResolve = resolve;
		readyReject = reject;
	});

	function handleMessage(event: MessageEvent): void {
		// Source check — drop anything not from our iframe. Prevents a
		// rogue popup or sibling iframe from impersonating responses.
		if (iframe.contentWindow && event.source !== iframe.contentWindow) return;
		if (event.origin !== iframeOrigin) return;
		const data = event.data as RmdgInbound | undefined;
		if (!data || typeof data !== 'object') return;
		if (data.type === 'rmdg:ready') {
			readyResolve?.();
			return;
		}
		if (data.type === 'rmdg:response') {
			const call = pending.get(data.requestId);
			if (!call) {
				// Late response (timed out + cleaned up, or duplicate). Drop.
				return;
			}
			pending.delete(data.requestId);
			clearTimeout(call.timer);
			if (data.success) {
				call.resolve(data.value);
			} else {
				const err = data.error ?? { name: 'Error', message: 'unknown bridge error' };
				const e = new Error(err.message);
				e.name = err.name;
				call.reject(e);
			}
			return;
		}
		if (data.type === 'rmdg:event') {
			const set = subscribers.get(data.name as DocGenEventName);
			if (!set) return;
			for (const handler of set) {
				try {
					handler(data.detail);
				} catch (err) {
					warn(`docGenIframeClient: event handler for '${data.name}' threw`, err);
				}
			}
			return;
		}
	}

	win.addEventListener('message', handleMessage as EventListener);

	function call<T>(method: string, args: unknown[] = []): Promise<T> {
		if (disconnected) return Promise.reject(new Error('docGenIframeClient: disconnected'));
		const target = iframe.contentWindow;
		if (!target)
			return Promise.reject(new Error('docGenIframeClient: iframe has no contentWindow'));
		const requestId = mintRequestId();
		const req: RmdgRequest = { type: 'rmdg:request', requestId, method, args };
		return new Promise<T>((resolve, reject) => {
			const timer = setTimeout(() => {
				pending.delete(requestId);
				reject(new Error(`docGenIframeClient: '${method}' timed out after ${timeoutMs}ms`));
			}, timeoutMs);
			pending.set(requestId, {
				resolve: resolve as (v: unknown) => void,
				reject,
				timer
			});
			try {
				target.postMessage(req, iframeOrigin);
			} catch (err) {
				clearTimeout(timer);
				pending.delete(requestId);
				reject(err instanceof Error ? err : new Error(String(err)));
			}
		});
	}

	function on(event: DocGenEventName, handler: (detail: unknown) => void): () => void {
		let set = subscribers.get(event);
		if (!set) {
			set = new Set();
			subscribers.set(event, set);
		}
		set.add(handler);
		return () => {
			subscribers.get(event)?.delete(handler);
		};
	}

	function disconnect(): void {
		if (disconnected) return;
		disconnected = true;
		win.removeEventListener('message', handleMessage as EventListener);
		// Reject in-flight calls — caller awaiting them gets a clear
		// disconnect error rather than silently hanging until timeout.
		for (const [, call] of pending) {
			clearTimeout(call.timer);
			call.reject(new Error('docGenIframeClient: disconnected'));
		}
		pending.clear();
		subscribers.clear();
		readyReject?.(new Error('docGenIframeClient: disconnected before ready'));
	}

	// Typed convenience wrappers — names map 1:1 to DocGenToolName modulo
	// the docgen_ prefix (bridgeMethodFor is the canonical strip).
	const m = (toolName: DocGenToolName): string => bridgeMethodFor(toolName);

	return {
		ready,
		proposeEdit: (p) =>
			call<{ proposalId: string; status: 'pending' }>(m('docgen_proposeEdit'), [p]),
		acceptProposal: (id) => call<{ applied: true }>(m('docgen_acceptProposal'), [id]),
		rejectProposal: (id) => call<{ applied: true }>(m('docgen_rejectProposal'), [id]),
		getState: () => call<DocGenStateForModel>(m('docgen_getState'), []),
		call,
		on,
		disconnect
	};
}

function mintRequestId(): string {
	// crypto.randomUUID is available in modern browsers + Node 19+.
	// Fall back to a timestamp+random combo for ancient runtimes (the
	// chatbot supports modern browsers, but tests run in Node — both
	// have randomUUID, this is belt-and-suspenders).
	const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
	if (c?.randomUUID) return c.randomUUID();
	return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
