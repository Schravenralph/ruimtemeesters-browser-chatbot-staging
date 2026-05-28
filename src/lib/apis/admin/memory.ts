import { WEBUI_API_BASE_URL } from '$lib/constants';

export interface CountedOwner {
	owner_user_id: string;
	count: number;
}

export interface BankStats {
	bank_id: string;
	document_count: number;
	/** Upstream-computed count of LLM-extracted facts. May be larger
	 *  than document_count when documents are chunked. Null when the
	 *  bank doesn't exist upstream or the /v1/default/banks call failed. */
	fact_count: number | null;
	last_document_at: string | null;
	by_owner: CountedOwner[];
	by_type: Record<string, number>;
	truncated: boolean;
}

export interface AdoptionStats {
	measured_at: string;
	banks: BankStats[];
	bopa_sessions: { total: number; active: number };
	projects: number;
	users: number;
}

/** GET /api/v1/admin/memory/stats — admin-only memory adoption snapshot. */
export const getAdoptionStats = async (token: string): Promise<AdoptionStats> => {
	// `error` and `caught` together: an empty-string detail is still an error
	// (a truthy-only check would let `null` leak as AdoptionStats — Bugbot
	// finding on PR #57).
	let error: { detail?: string } | string | null = null;
	let caught = false;

	const url = `${WEBUI_API_BASE_URL}/admin/memory/stats`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (r) => {
			if (!r.ok) throw await r.json();
			return r.json();
		})
		.catch((err) => {
			console.error(err);
			error = err?.detail ?? err;
			caught = true;
			return null;
		});

	if (caught) {
		// Use truthy check so an empty-string `detail` doesn't throw "" —
		// an empty string would hit the page's `{:else if errorMsg}` as
		// falsy and blank the whole panel (Bugbot finding on PR #59).
		throw error || 'request failed';
	}
	return res as AdoptionStats;
};
