#!/usr/bin/env python3
"""Seed OpenWebUI from scripts/personas.yaml.

Replaces both `scripts/seed-litellm-connection.sh` and
`rm-tools/register_assistants.py` per ADR-0018. Single Python script driven by
one declarative YAML manifest. Idempotent — safe to re-run after DB reset,
container rebuild, or `docker compose down -v`.

Order of operations:
  1. Connection config — POST /openai/config/update + configs/import for default
     model + provider disables.
  2. Filters — register Function rows with source files, seed valves, activate.
  3. Legacy persona cleanup — delete retired persona Model ids.
  4. Personas — register/update the three persona Model rows.
  5. Prompts — register/update the slash-command catalog.

Usage:
    scripts/seed_personas.py                       # live run, defaults
    scripts/seed_personas.py --dry-run             # print only, no API calls
    HOST=https://chatbot.datameesters.nl scripts/seed_personas.py --token "$JWT"

Env / flag fallbacks:
    HOST, APP_CONTAINER, DB_CONTAINER, ADMIN_USER_ID, MEMORY_GATEWAY_TOKEN,
    SKILLS_GATEWAY_TOKEN, MANIFEST.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from personas_schema import (  # noqa: E402
    FilterDef,
    Manifest,
    PersonaDef,
    PromptDef,
    load_manifest,
)


def _docker_exec(container: str, cmd: list[str], stdin: str | None = None) -> str:
    """Run a command in a container and return stdout, raising on failure."""
    full = ['docker', 'exec']
    if stdin is not None:
        full.append('-i')
    full.append(container)
    full.extend(cmd)
    res = subprocess.run(full, input=stdin, capture_output=True, text=True, check=True)
    return res.stdout


def _mint_admin_token(app_container: str, admin_user_id: str) -> str:
    """Mint a short-lived admin JWT inside the container using OWUI's signing key."""
    script = (
        'import os\n'
        'from datetime import timedelta\n'
        'from open_webui.utils.auth import create_token\n'
        "print(create_token({'id': os.environ['ADMIN_USER_ID']}, timedelta(minutes=15)))\n"
    )
    out = subprocess.run(
        ['docker', 'exec', '-i', '-e', f'ADMIN_USER_ID={admin_user_id}', app_container, 'python3', '-'],
        input=script,
        capture_output=True,
        text=True,
        check=True,
    )
    token = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ''
    if not token:
        raise RuntimeError(f'Failed to mint admin token in {app_container}: {out.stderr}')
    return token


def _resolve_admin_user_id(db_container: str) -> str:
    out = _docker_exec(
        db_container,
        [
            'psql',
            '-U',
            'rmchatbot',
            '-d',
            'rmchatbot',
            '-tAc',
            'SELECT id FROM "user" WHERE role=\'admin\' ORDER BY created_at LIMIT 1;',
        ],
    )
    uid = out.strip()
    if not uid:
        raise RuntimeError(f'No admin user in {db_container}. Sign in first or pass --admin-user-id.')
    return uid


def _resolve_litellm_key(app_container: str) -> str:
    out = _docker_exec(app_container, ['sh', '-c', 'printf "%s" "$OPENAI_API_KEYS"'])
    if not out:
        raise RuntimeError(
            f'OPENAI_API_KEYS empty in {app_container}. Set LITELLM_MASTER_KEY in .env and recreate the container.'
        )
    return out


def _post(base_url: str, token: str, path: str, json_body: dict) -> requests.Response:
    return requests.post(
        f'{base_url}{path}',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        json=json_body,
        timeout=30,
    )


def _get(base_url: str, token: str, path: str) -> requests.Response:
    return requests.get(
        f'{base_url}{path}',
        headers={'Authorization': f'Bearer {token}'},
        timeout=30,
    )


def seed_connection(base_url: str, token: str, manifest: Manifest, litellm_key: str) -> None:
    print('Seeding LiteLLM connection...')
    configs = {
        '0': {
            'enable': True,
            'tags': [],
            'prefix_id': '',
            'model_ids': [p.id for p in manifest.personas],
            'connection_type': 'external',
            'api_version': 'openai',
        },
    }
    resp = _post(
        base_url,
        token,
        '/openai/config/update',
        {
            'ENABLE_OPENAI_API': True,
            'OPENAI_API_BASE_URLS': manifest.connection.base_urls,
            'OPENAI_API_KEYS': [litellm_key],
            'OPENAI_API_CONFIGS': configs,
        },
    )
    resp.raise_for_status()
    print(f'  ~ openai connection: {", ".join(p.id for p in manifest.personas)}')

    export = _get(base_url, token, '/api/v1/configs/export')
    export.raise_for_status()
    cfg = export.json()

    # Defense in depth: refuse to mutate a response that doesn't look like an
    # OWUI config. /configs/import overwrites the full saved config, so a
    # malformed 200 here would wipe banners, branding, and MCP settings.
    # Bugbot caught this hazard on the legacy bash seeder (commit f0d07a8).
    if not isinstance(cfg, dict) or ('openai' not in cfg and 'ui' not in cfg):
        keys = list(cfg)[:10] if isinstance(cfg, dict) else type(cfg).__name__
        raise RuntimeError(f'/configs/export returned unexpected shape (top-level: {keys}); refusing to import')

    cfg.setdefault('ui', {})['default_models'] = manifest.connection.default_model
    for dotted in manifest.connection.disable:
        head, *tail = dotted.split('.')
        node = cfg.setdefault(head, {})
        for key in tail[:-1]:
            node = node.setdefault(key, {})
        node[tail[-1]] = False

    imp = _post(base_url, token, '/api/v1/configs/import', {'config': cfg})
    imp.raise_for_status()

    # Post-import verify: server echoes the new config — confirm the values
    # we care about actually landed.
    applied = imp.json()
    got_default = applied.get('ui', {}).get('default_models')
    if got_default != manifest.connection.default_model:
        raise RuntimeError(f'configs/import did not apply default_models (got {got_default!r})')
    for dotted in manifest.connection.disable:
        node: object = applied
        for key in dotted.split('.'):
            node = node.get(key) if isinstance(node, dict) else None
        if node is not False:
            raise RuntimeError(f'configs/import did not disable {dotted} (got {node!r})')

    print(f'  ~ default_models = {manifest.connection.default_model}')
    print(f'  ~ disabled: {", ".join(manifest.connection.disable) or "(none)"}')


def _read_filter_source(filter_def: FilterDef) -> str:
    path = REPO_ROOT / filter_def.source_path
    return path.read_text(encoding='utf-8')


def seed_filter(
    base_url: str,
    token: str,
    filter_def: FilterDef,
    memory_token: str,
    skills_token: str,
) -> bool:
    content = _read_filter_source(filter_def)
    payload = {
        'id': filter_def.id,
        'name': filter_def.name,
        'content': content,
        'meta': {'description': filter_def.description},
    }

    resp = _post(base_url, token, '/api/v1/functions/create', payload)
    if resp.status_code == 200:
        print(f'  + Filter: {filter_def.name} ({filter_def.id})')
    elif 'id_taken' in resp.text.lower() or resp.status_code in (400, 409):
        upd = _post(base_url, token, f'/api/v1/functions/id/{filter_def.id}/update', payload)
        if upd.status_code != 200:
            print(f'  x Filter update failed: {filter_def.id} -- {upd.status_code}: {upd.text[:200]}')
            return False
        print(f'  ~ Updated filter: {filter_def.name} ({filter_def.id})')
    else:
        print(f'  x Filter create failed: {filter_def.id} -- {resp.status_code}: {resp.text[:200]}')
        return False

    is_active_resp = _get(base_url, token, f'/api/v1/functions/id/{filter_def.id}')
    if is_active_resp.status_code == 200 and not is_active_resp.json().get('is_active'):
        tog = _post(base_url, token, f'/api/v1/functions/id/{filter_def.id}/toggle', {})
        if tog.status_code != 200:
            # A filter installed-but-inactive will silently never run; the
            # retired register_assistants.py treated this as hard failure too.
            print(f'    -> activation FAILED: {tog.status_code}: {tog.text[:200]}')
            return False
        print('    -> activated')

    valves: dict = dict(filter_def.valves_extras)
    if filter_def.needs_memory_token and memory_token:
        valves['mcp_token'] = memory_token
    if filter_def.needs_skills_token and skills_token:
        valves['skills_token'] = skills_token
    if valves:
        v = _post(base_url, token, f'/api/v1/functions/id/{filter_def.id}/valves/update', valves)
        if v.status_code == 200:
            print(f'    -> valves seeded ({", ".join(sorted(valves.keys()))})')
        else:
            print(f'    -> valves seed FAILED: {v.status_code}: {v.text[:200]}')
            return False
    return True


def delete_legacy_personas(base_url: str, token: str, ids: list[str]) -> None:
    if not ids:
        return
    print('Cleaning up legacy persona Model rows...')
    for legacy_id in ids:
        resp = _post(base_url, token, '/api/v1/models/model/delete', {'id': legacy_id})
        if resp.status_code == 200:
            print(f'  deleted legacy persona: {legacy_id}')


def _persona_payload(persona: PersonaDef) -> dict:
    # base_model_id=None is load-bearing: it puts the row in OWUI's override
    # branch (utils/models.py:150) which mutates the LiteLLM-discovered base
    # model's display name. Setting base_model_id=<persona.id> hits the
    # "new model" branch and the long display name never reaches the dropdown.
    meta: dict = {
        'profile_image_url': persona.profile_image_url,
        'description': persona.description,
        'capabilities': persona.capabilities or None,
        'toolIds': persona.tool_ids,
        # Per-tool-name allowlist read by the chatbot filter at
        # src/lib/integrations/toolAllowlist/. Strict default: an empty
        # list means no tools — every persona is expected to declare its
        # own list in personas.yaml. The pre-seed check below warns when
        # a persona ships with an empty allowlist.
        'toolAllowlist': persona.tools,
        'filterIds': persona.filter_ids,
    }
    if persona.suggestion_prompts:
        meta['suggestion_prompts'] = [sp.model_dump() for sp in persona.suggestion_prompts]
    if persona.default_feature_ids:
        meta['defaultFeatureIds'] = persona.default_feature_ids
    return {
        'id': persona.id,
        'name': persona.name,
        'base_model_id': None,
        'meta': meta,
        'params': {'system': persona.system_prompt},
        'is_active': True,
    }


def seed_persona(base_url: str, token: str, persona: PersonaDef) -> bool:
    _post(base_url, token, '/api/v1/models/model/delete', {'id': persona.id})
    payload = _persona_payload(persona)
    resp = _post(base_url, token, '/api/v1/models/create', payload)
    if resp.status_code == 200:
        print(f'  seeded persona: {persona.id} -> {persona.name}')
        return True
    print(f'  x persona seed failed: {persona.id} -- {resp.status_code}: {resp.text[:200]}')
    return False


def seed_prompt(base_url: str, token: str, prompt: PromptDef) -> bool:
    payload = {'command': prompt.command, 'name': prompt.name, 'content': prompt.content}
    resp = _post(base_url, token, '/api/v1/prompts/create', payload)
    if resp.status_code == 200:
        print(f'  + Prompt: /{prompt.command} — {prompt.name}')
        return True
    listing = _get(base_url, token, '/api/v1/prompts/')
    if listing.status_code == 200:
        for existing in listing.json():
            if existing.get('command') == prompt.command:
                upd = _post(base_url, token, f'/api/v1/prompts/id/{existing["id"]}/update', payload)
                if upd.status_code == 200:
                    print(f'  ~ Updated prompt: /{prompt.command}')
                    return True
                break
    print(f'  x Prompt seed failed: /{prompt.command} -- {resp.status_code}: {resp.text[:200]}')
    return False


def run_dry(manifest: Manifest) -> int:
    print(f'== DRY RUN @ {dt.datetime.now(tz=dt.UTC).isoformat()} ==\n')
    print(f'Connection: {", ".join(manifest.connection.base_urls)} default={manifest.connection.default_model}')
    print(f'  disable: {manifest.connection.disable}\n')
    print(f'Filters ({len(manifest.filters)}):')
    for f in manifest.filters:
        src = REPO_ROOT / f.source_path
        size = src.stat().st_size if src.exists() else -1
        print(f'  ? {f.id:30s} {size:6d}B  needs_memory={f.needs_memory_token} needs_skills={f.needs_skills_token}')
    print()
    if manifest.legacy_persona_ids:
        print(f'Legacy persona ids to delete: {manifest.legacy_persona_ids}\n')
    print(f'Personas ({len(manifest.personas)}):')
    for p in manifest.personas:
        allow = f'allowlist={len(p.tools)}' if p.tools else 'allowlist=EMPTY (no tools)'
        print(f'  ? {p.id:25s} filters={p.filter_ids} servers={len(p.tool_ids)} {allow} prompt={len(p.system_prompt)}B')
    print()
    print(f'Prompts ({len(manifest.prompts)}):')
    for pr in manifest.prompts:
        print(f'  ? /{pr.command:25s} {pr.name} ({len(pr.content)}B)')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Seed OpenWebUI from personas.yaml (ADR-0018)')
    parser.add_argument('--manifest', default=str(REPO_ROOT / 'scripts' / 'personas.yaml'))
    parser.add_argument('--url', default=os.environ.get('HOST', 'http://localhost:3333'))
    parser.add_argument('--token', help='Admin JWT. If omitted, minted from --app-container.')
    parser.add_argument('--app-container', default=os.environ.get('APP_CONTAINER', 'rm-chatbot'))
    parser.add_argument('--db-container', default=os.environ.get('DB_CONTAINER', 'rm-chatbot-db'))
    parser.add_argument('--admin-user-id', default=os.environ.get('ADMIN_USER_ID'))
    parser.add_argument('--memory-token', default=os.environ.get('MEMORY_GATEWAY_TOKEN', ''))
    parser.add_argument('--skills-token', default=os.environ.get('SKILLS_GATEWAY_TOKEN', ''))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--skip-connection',
        action='store_true',
        help='Skip the LiteLLM connection-config step (filters/personas/prompts only)',
    )
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))

    if args.dry_run:
        return run_dry(manifest)

    token = args.token
    if not token:
        admin_id = args.admin_user_id or _resolve_admin_user_id(args.db_container)
        token = _mint_admin_token(args.app_container, admin_id)

    if not args.skip_connection:
        litellm_key = _resolve_litellm_key(args.app_container)
        seed_connection(args.url, token, manifest, litellm_key)
        print()

    if manifest.filters:
        print(f'Seeding {len(manifest.filters)} filters...')
        if not args.memory_token and any(f.needs_memory_token for f in manifest.filters):
            print(
                '  ! WARNING: no --memory-token / MEMORY_GATEWAY_TOKEN — filters that call rm-memory will 401',
                file=sys.stderr,
            )
        ok = sum(1 for f in manifest.filters if seed_filter(args.url, token, f, args.memory_token, args.skills_token))
        print(f'  -> {ok}/{len(manifest.filters)} filters seeded\n')
        if ok != len(manifest.filters):
            return 1

    delete_legacy_personas(args.url, token, manifest.legacy_persona_ids)
    print()

    # Strict allowlist default: an empty `tools` list means the persona
    # has NO tools after seed (the chatbot filter drops everything).
    # That's intentional — we control infra and prefer "loud break" over
    # "silently revert to full exposure" — but loud means loud, so warn.
    for p in manifest.personas:
        if not p.tools:
            print(
                f'  ! WARNING: persona {p.id!r} has empty tools allowlist — model will see no tools',
                file=sys.stderr,
            )

    print(f'Seeding {len(manifest.personas)} personas...')
    ok = sum(1 for p in manifest.personas if seed_persona(args.url, token, p))
    print(f'  -> {ok}/{len(manifest.personas)} personas seeded\n')
    if ok != len(manifest.personas):
        return 1

    if manifest.prompts:
        print(f'Seeding {len(manifest.prompts)} prompts...')
        ok = sum(1 for pr in manifest.prompts if seed_prompt(args.url, token, pr))
        print(f'  -> {ok}/{len(manifest.prompts)} prompts seeded\n')
        if ok != len(manifest.prompts):
            return 1

    print('Done.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
