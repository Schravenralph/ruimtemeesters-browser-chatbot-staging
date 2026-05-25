#!/usr/bin/env python3
"""Backfill OpenWebUI user name + avatar from Clerk.

Designed to run inside the chatbot container so it can import OWUI models
directly. The container doesn't mount `scripts/`, so pipe the script in
over stdin:

    CLERK_KEY=$(grep ^CLERK_SECRET_KEY .env | cut -d= -f2-)
    docker exec -i -e CLERK_SECRET_KEY="$CLERK_KEY" rm-chatbot \\
        python3 - --dry-run < scripts/backfill_clerk_identity.py

Drop `--dry-run` to actually write. Container name is `rm-chatbot` in dev
and on prod (Hetzner mirrors the layout). Bare `python3 -` reads the
script from stdin; argv after `-` is forwarded as sys.argv.

It iterates every OWUI user, looks them up in Clerk by email, and writes
back `name` + `profile_image_url` when Clerk has a better value. Images
are fetched and inlined as base64 data URLs, matching the format used by
OAUTH_UPDATE_PICTURE_ON_LOGIN so backfill output is indistinguishable
from a fresh OIDC login.

Idempotent. Re-running on already-synced users is a no-op (rows match,
no writes issued).

Flags:
    --dry-run        Print the diff that *would* be written, no DB writes.
    --email ADDR     Restrict to a single user (handy for one-off fixes).
    --force-image    Re-fetch + re-inline avatars even if URL is unchanged.
"""

from __future__ import annotations

import argparse
import base64
import logging
import mimetypes
import os
import sys
from typing import Optional

import httpx

from open_webui.models.users import Users

log = logging.getLogger('backfill_clerk_identity')


def fetch_clerk_user_by_email(email: str, clerk_secret_key: str) -> Optional[dict]:
    """Look up a Clerk user by email.

    Returns the normalized fields we care about, or None if not found.
    """
    resp = httpx.get(
        'https://api.clerk.com/v1/users',
        params={'email_address': email},
        headers={'Authorization': f'Bearer {clerk_secret_key}'},
        timeout=10.0,
    )
    resp.raise_for_status()
    matches = resp.json()
    if not matches:
        return None

    user = matches[0]
    first = (user.get('first_name') or '').strip()
    last = (user.get('last_name') or '').strip()
    full_name = f'{first} {last}'.strip()
    return {
        'clerk_id': user['id'],
        'first_name': first,
        'last_name': last,
        'name': full_name,
        'image_url': user.get('image_url') or '',
    }


def inline_image(picture_url: str) -> Optional[str]:
    """Fetch picture_url and return a data:image/...;base64,... URL.

    Mirrors OAuthManager._process_picture_url() output format so backfill
    rows look identical to fresh OIDC-login rows. Returns None on failure
    (caller can decide whether to skip or fall through).
    """
    if not picture_url:
        return None
    try:
        resp = httpx.get(picture_url, timeout=15.0, follow_redirects=True)
        if not resp.is_success:
            log.warning('Failed to fetch %s: HTTP %s', picture_url, resp.status_code)
            return None
        mime = mimetypes.guess_type(picture_url)[0]
        if mime is None:
            # Match OAuthManager._process_picture_url: default to image/jpeg
            # when the URL has no recognisable extension. Same default keeps
            # backfill output byte-identical to OIDC sync, which preserves
            # idempotency (otherwise the next OIDC login would rewrite the
            # row with a different data: prefix).
            mime = 'image/jpeg'
        encoded = base64.b64encode(resp.content).decode('utf-8')
        return f'data:{mime};base64,{encoded}'
    except Exception as e:
        log.error('Error inlining %s: %s', picture_url, e)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Print diff; no writes.')
    parser.add_argument('--email', help='Restrict to a single user email.')
    parser.add_argument(
        '--force-image',
        action='store_true',
        help='Re-fetch + re-inline avatars even if Clerk URL is unchanged.',
    )
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s %(message)s',
    )

    clerk_secret_key = os.environ.get('CLERK_SECRET_KEY')
    if not clerk_secret_key:
        log.error('CLERK_SECRET_KEY not set in environment.')
        return 1

    users_result = Users.get_users()
    all_users = users_result.get('users') if isinstance(users_result, dict) else users_result
    if args.email:
        all_users = [u for u in all_users if u.email.lower() == args.email.lower()]
        if not all_users:
            log.error('No OWUI user found with email %s', args.email)
            return 1

    log.info('Backfilling identity for %d user(s) (dry_run=%s)', len(all_users), args.dry_run)

    stats = {'updated': 0, 'unchanged': 0, 'no_clerk_match': 0, 'errors': 0}

    for owui_user in all_users:
        try:
            clerk = fetch_clerk_user_by_email(owui_user.email, clerk_secret_key)
        except Exception as e:
            log.error('  %s: Clerk lookup failed: %s', owui_user.email, e)
            stats['errors'] += 1
            continue

        if not clerk:
            log.info('  %s: no Clerk user → skipped', owui_user.email)
            stats['no_clerk_match'] += 1
            continue

        # Reload user to get profile_image_url (get_users() defers that column).
        # If the user was deleted between get_users() and now, skip rather than
        # crashing the whole run on AttributeError.
        full_user = Users.get_user_by_id(owui_user.id)
        if full_user is None:
            log.warning('  %s: user %s disappeared mid-run → skipped', owui_user.email, owui_user.id)
            stats['errors'] += 1
            continue
        updates: dict[str, str] = {}

        # Name: Clerk wins if it has a non-empty value
        if clerk['name'] and clerk['name'] != full_user.name:
            updates['name'] = clerk['name']

        # Avatar: inline Clerk's URL → data URL, write if different (or forced)
        avatar_fetch_failed = False
        if clerk['image_url']:
            current = full_user.profile_image_url or ''
            already_inlined = current.startswith('data:')
            if args.force_image or not already_inlined or current == '/user.png':
                inlined = inline_image(clerk['image_url'])
                if inlined is None:
                    # Don't silently mask a transient fetch error as "in sync";
                    # log + count it so the operator can retry.
                    log.error('  %s: avatar fetch failed for %s', owui_user.email, clerk['image_url'])
                    avatar_fetch_failed = True
                elif inlined != current:
                    updates['profile_image_url'] = inlined

        if not updates:
            if avatar_fetch_failed:
                stats['errors'] += 1
            else:
                log.info('  %s: in sync', owui_user.email)
                stats['unchanged'] += 1
            continue

        before = {
            'name': full_user.name,
            'profile_image_url': (full_user.profile_image_url or '')[:60] + '…'
            if (full_user.profile_image_url or '') and len(full_user.profile_image_url or '') > 60
            else (full_user.profile_image_url or ''),
        }
        after = {
            'name': updates.get('name', full_user.name),
            'profile_image_url': (updates.get('profile_image_url', full_user.profile_image_url or '')[:60] + '…')
            if 'profile_image_url' in updates
            else before['profile_image_url'],
        }
        log.info('  %s:', owui_user.email)
        for k in updates:
            log.info('    %s: %r → %r', k, before[k], after[k])

        if not args.dry_run:
            # update_user_by_id returns the new UserModel on success, None on
            # any DB failure (it catches Exception and prints). We mustn't
            # count a None return as success, otherwise stats lie and the
            # exit code stays 0 on a fully-broken run.
            result = Users.update_user_by_id(owui_user.id, updates)
            if result is None:
                log.error('  %s: DB write returned None — failure', owui_user.email)
                stats['errors'] += 1
            else:
                stats['updated'] += 1
        else:
            stats['updated'] += 1  # counted as "would update"

    log.info('')
    log.info(
        'Done. updated=%d unchanged=%d no_clerk_match=%d errors=%d%s',
        stats['updated'],
        stats['unchanged'],
        stats['no_clerk_match'],
        stats['errors'],
        ' (dry-run)' if args.dry_run else '',
    )
    return 0 if stats['errors'] == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
