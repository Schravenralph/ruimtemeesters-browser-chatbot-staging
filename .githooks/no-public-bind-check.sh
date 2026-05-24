#!/usr/bin/env bash
# .githooks/no-public-bind-check.sh
#
# Refuse commits that introduce public-interface bindings. Inspects only
# NEWLY ADDED lines in the staged diff, so legacy code is grandfathered
# until it's touched.
#
# Escape hatch: put the literal string `public-bind-ok` on the same line
# (as a comment in YAML / JS / TS, or inside a string).
#
# Context: this is the code-time safety net for the 2026-04-17 AKIRA
# ransomware incident. See ADRs:
#   - security-never-expose-mongodb.md (the invariant)
#   - ADR-0004-enforce-no-public-docker-bindings-at-firewall.md (runtime)
#   - ADR-0005-no-public-bind-pre-commit.md (this hook)

set -euo pipefail

# Diff source: pre-commit defaults to staged (--cached) diff. CI sets
# NPB_DIFF_RANGE=<base>..<head> to scan the PR's added lines instead.
# Keeping the rule logic in one place avoids the workflow's inline
# regex drifting from the hook (the cause of the 2026-05-12 HIGH bug).
DIFF_ARGS=(--no-color -U0 --diff-filter=ACMR)
if [ -n "${NPB_DIFF_RANGE:-}" ]; then
  DIFF_ARGS+=("${NPB_DIFF_RANGE}")
else
  DIFF_ARGS+=(--cached)
fi

# Path exclusions: files that legitimately quote the dangerous patterns
# for documentation or testing purposes (the hook's own source, its ADR,
# and its test fixtures). Pathspecs with :(exclude,glob) magic let git
# drop those files at diff time, before we extract added lines.
#
# Diff errors are NOT silently swallowed: previously `2>/dev/null` plus
# `|| true` would let an invalid NPB_DIFF_RANGE (stale CI base SHA,
# shallow clone, typo) make `added` empty and the hook exit 0 — silently
# disabling the security check. Bugbot caught this. We now capture
# stderr and fail loudly if git diff itself errored.
diff_stderr=$(mktemp)
trap 'rm -f "$diff_stderr"' EXIT
# Capture the exit code without triggering `set -e`. A naked assignment
# inside $(...) propagates failure and would kill the script before we
# could print a useful error.
if diff_out=$(git diff "${DIFF_ARGS[@]}" -- \
  ':(exclude).githooks/no-public-bind-check.sh' \
  ':(exclude,glob)adr/ADR-0005*' \
  ':(exclude,glob)tests/hooks/**' \
  2>"$diff_stderr"); then
  diff_rc=0
else
  diff_rc=$?
fi
if [ "$diff_rc" -ne 0 ]; then
  echo "no-public-bind-check: 'git diff' failed (exit $diff_rc). Refusing rather than silently passing." >&2
  cat "$diff_stderr" >&2
  exit 2
fi
added=$(echo "$diff_out" | grep -E '^\+[^+]' | sed 's/^+//') || true
[ -z "${added:-}" ] && exit 0

violations=""
add_v() { violations+="  - $1"$'\n'; }

while IFS= read -r line; do
  [[ "$line" == *"public-bind-ok"* ]] && continue

  # 1) Literal 0.0.0.0 in quotes or backticks. Also catches "0.0.0.0:PORT…"
  #    (e.g. inline-array compose form ports: ["0.0.0.0:5000:5000"]).
  if echo "$line" | grep -qE "['\"\`]0\.0\.0\.0(['\"\`]|:)"; then
    add_v "literal 0.0.0.0 → ${line:0:140}"
    continue
  fi

  # 2) docker-compose 'ports:' short-form without loopback prefix.
  #    Accepts 127.0.0.1:X:Y, rejects X:Y / ${VAR}:Y / $VAR:Y / 0.0.0.0:X:Y.
  #    Bugbot remediations: single quotes, protocol suffix (/tcp /udp),
  #    port ranges (5000-5010:5000-5010), trailing YAML comments, and the
  #    bare $VAR form (Compose accepts both ${VAR} and $VAR).
  if echo "$line" | grep -qE "^[[:space:]]*-[[:space:]]*['\"]?([0-9]+(-[0-9]+)?|0\.0\.0\.0:[0-9]+(-[0-9]+)?|\\\$\{[A-Z_][^}]*\}|\\\$[A-Z_][A-Z0-9_]*):[0-9]+(-[0-9]+)?(/(tcp|udp|sctp))?['\"]?[[:space:]]*(#.*)?$"; then
    add_v "compose port without 127.0.0.1: prefix → ${line:0:140}"
    continue
  fi

  # 2b) docker-compose 'ports:' single-port short-form (no host mapping).
  #     Shapes "5000", "5000/udp", "5000-5010", "5000-5010/udp" publish the
  #     container port to an ephemeral host port on the wildcard interface
  #     ([::]/0.0.0.0), bypassing UFW. On 2026-05-12 this exact pattern left
  #     two unidentified services on [::]:32796-32797 reachable from the
  #     public internet. Require explicit 127.0.0.1: host-IP or use 'expose:'.
  #
  #     Requires BOTH opening and closing quotes (single or double) to
  #     restrict to the form unambiguously parsed as a port spec. Known
  #     limitation: this still false-positives on quoted `- "5432"` under
  #     `expose:` blocks (semantically safe — expose doesn't publish to the
  #     host). Workaround: add `# public-bind-ok` on the line. A full
  #     context-aware check would need YAML parsing, deferred (see ADR-0005).
  if echo "$line" | grep -qE "^[[:space:]]*-[[:space:]]*(\"[0-9]+(-[0-9]+)?(/(tcp|udp|sctp))?\"|'[0-9]+(-[0-9]+)?(/(tcp|udp|sctp))?')[[:space:]]*(#.*)?$"; then
    add_v "compose single-port short-form (random wildcard host port) → ${line:0:140}"
    continue
  fi

  # 2c) docker-compose 'ports:' YAML flow-sequence form.
  #     Rules 2 and 2b anchor on `^[[:space:]]*-`, which is block-sequence only.
  #     The equivalent flow form `ports: ["8080:80", "5432"]` binds to the
  #     wildcard interface identically but bypassed the earlier rules entirely
  #     (bugbot MEDIUM). Look for any quoted entry inside a `ports:` flow array
  #     whose host part is bare-numeric / range / $VAR (i.e. no 127.0.0.1: or
  #     0.0.0.0: prefix — 0.0.0.0 is already caught by Rule 1). We scan each
  #     quoted entry inside the array.
  #
  #     Strip from the first `#` to end-of-line so commented-out examples
  #     like `# Old config used ports: ["8080:80"]` don't false-positive
  #     (bugbot LOW). Rules 2 / 2b dodge this implicitly via their
  #     `^[[:space:]]*-` anchor; Rule 2c has no such anchor so we strip
  #     explicitly. Approximation: a `#` inside a quoted string would also
  #     be stripped, but YAML port specs don't contain `#`.
  uncommented="${line%%#*}"
  if echo "$uncommented" | grep -qE 'ports[[:space:]]*:[[:space:]]*\['; then
    # Extract quoted port entries (single or double) and reject any that
    # match the dangerous shapes.
    dangerous=$(echo "$uncommented" | grep -oE "['\"]([0-9]+(-[0-9]+)?|\\\$\{[A-Z_][^}]*\}|\\\$[A-Z_][A-Z0-9_]*)(:[0-9]+(-[0-9]+)?)?(/(tcp|udp|sctp))?['\"]" || true)
    if [ -n "${dangerous:-}" ]; then
      add_v "compose flow-sequence ports without 127.0.0.1: prefix → ${line:0:140}"
      continue
    fi
  fi

  # 3) package.json script flags: every `--host` occurrence must be
  #    followed by a loopback value (127.0.0.1 / localhost / ::1), either
  #    space-separated or =-attached. Count-based: if some `--host`s are
  #    safe and others bare, the bare ones still get flagged. Catches the
  #    `concurrently "vite --host" "node --host=localhost ..."` pattern.
  #
  #    Outer gate uses `.*--host` (not `[^"]*--host`) so JSON-escaped
  #    quotes inside the script string don't truncate the match. Real
  #    package.json one-liners look like
  #      "dev": "concurrently \"vite --host\" \"node server\""
  #    and `[^"]*` stops at the first `\"`, hiding the bare `--host`
  #    that follows. `--host` must be followed by a POSIX-safe delimiter
  #    (space, `=`, JSON-escape backslash-quote, closing quote, EOL) —
  #    never another word character — to avoid matching `--host-name`.
  #    Script-name regex also accepts colon-namespaced variants
  #    (`dev:server`, `start:dev`, `serve:ssr`) which are common in
  #    monorepos. All `\b` boundaries replaced (GNU-only, silent on BSD).
  if echo "$line" | grep -qE '"(dev|start|serve|server|preview)(:[^"]*)?"[[:space:]]*:[[:space:]]*".*--host([[:space:]=\\"'"'"']|$)'; then
    # grep -oE returns 1 when no matches; with `set -euo pipefail` that
    # would terminate the script before the violation message prints.
    # `|| true` keeps the pipeline successful.
    host_total=$(echo "$line" | grep -oE '\--host([[:space:]=\\"'"'"']|$)' | wc -l || true)
    # Anchor the loopback value on whitespace / quote / backslash / EOL,
    # not a plain word boundary. `\b` matches between `localhost` and `.`,
    # which made `--host=localhost.attacker.com` count as "safe".
    host_safe=$(echo "$line" | grep -oE '\--host[[:space:]=]+(127\.0\.0\.1|localhost|::1)([[:space:]\\"'"'"']|$)' | wc -l || true)
    if [ "${host_total:-0}" -gt "${host_safe:-0}" ]; then
      add_v "script uses --host without explicit loopback → ${line:0:140}"
      continue
    fi
  fi
done <<< "$added"

if [ -n "$violations" ]; then
  cat >&2 <<EOF

no-public-bind-check: commit refused.

Newly-added lines look like they'd expose a service on a public
interface. This is the class of mistake that led to the 2026-04-17
AKIRA ransomware wipe of the Transcriber MongoDB.

Violations:

$violations

Fix (pick one):
  - Bind to 127.0.0.1 and let Caddy reverse-proxy if the service
    speaks HTTP/WebSocket. Example: app.listen(PORT, '127.0.0.1').
  - Use 'expose:' in docker-compose for services that stay on the
    compose network.  Example: expose: ["5432"]
  - Keep a host-side binding but prefix with 127.0.0.1.
    Example: ports: ["127.0.0.1:5432:5432"]
  - If the exposure is genuinely intentional, add 'public-bind-ok'
    on the same line.  YAML: # public-bind-ok  |  JS: // public-bind-ok

Rules live in .githooks/no-public-bind-check.sh.
EOF
  exit 1
fi

exit 0
