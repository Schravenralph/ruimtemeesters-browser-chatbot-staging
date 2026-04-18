# Phase A1 + A2: Fork, Brand & Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get a branded Ruimtemeesters fork of OpenWebUI running with Clerk authentication and role-based access.

**Architecture:** Fork OpenWebUI (SvelteKit + Python/FastAPI), customize branding via Tailwind CSS + static assets, integrate Clerk as OIDC identity provider using OpenWebUI's built-in OAuth support, add custom role mapping middleware to translate Clerk metadata to OpenWebUI roles, and add a token-forwarding utility for future app integrations.

**Tech Stack:** SvelteKit (Svelte 4), Python 3.11+ (FastAPI), Tailwind CSS, Docker Compose, PostgreSQL, Ollama, Clerk (OIDC)

**Licensing note:** OpenWebUI's license (modified BSD 3-Clause) allows rebranding for deployments with ≤50 users in a rolling 30-day period. The internal RM team is within this limit. For external clients later, an enterprise license will be needed for white-labeling. See: https://github.com/open-webui/open-webui/blob/main/LICENSE

**Spec reference:** `docs/superpowers/specs/2026-03-31-browser-chatbot-design.md` — Sections 2, 3, 4, 7.

---

## File Structure

### New files (created in this plan)

| File                                               | Responsibility                                            |
| -------------------------------------------------- | --------------------------------------------------------- |
| `docker-compose.yml`                               | RM-specific compose: OpenWebUI fork + Ollama + PostgreSQL |
| `.env`                                             | Environment configuration (LLM keys, Clerk, DB, branding) |
| `.env.example`                                     | Template for environment variables                        |
| `.gitignore`                                       | Already exists, will be extended                          |
| `src/lib/themes/ruimtemeesters.css`                | RM brand colors and CSS overrides                         |
| `static/brand-assets/logo.svg`                     | RM logo (landscape, klein blue on transparent)            |
| `static/brand-assets/logo-white.svg`               | RM logo (landscape, smart white on transparent)           |
| `static/brand-assets/favicon.ico`                  | RM favicon                                                |
| `static/brand-assets/favicon.svg`                  | RM favicon SVG                                            |
| `backend/open_webui/routers/rm_auth.py`            | Clerk role mapping middleware                             |
| `backend/open_webui/utils/token_forwarding.py`     | Utility to forward Clerk JWT to app endpoints             |
| `backend/open_webui/test/test_rm_auth.py`          | Tests for role mapping                                    |
| `backend/open_webui/test/test_token_forwarding.py` | Tests for token forwarding                                |

### Modified files

| File                           | What changes                               |
| ------------------------------ | ------------------------------------------ |
| `tailwind.config.js`           | Add RM brand colors to theme.extend.colors |
| `src/app.css`                  | Import ruimtemeesters.css theme overrides  |
| `src/lib/constants.ts`         | Update APP_NAME to 'Ruimtemeesters AI'     |
| `backend/open_webui/config.py` | Add RM-specific config variables           |
| `backend/open_webui/main.py`   | Mount rm_auth router, add middleware       |

---

## Task 1: Fork and Set Up Repository

**Files:**

- Modify: `.gitignore`

- [ ] **Step 1: Fork OpenWebUI on GitHub**

Go to https://github.com/open-webui/open-webui and click "Fork". Name it `ruimtemeesters-browser-chatbot` or use your existing repo. Clone it locally:

```bash
cd /home/ralph/Projects
# If you already have the empty Ruimtemeesters-Browser-Chatbot dir, remove it first
rm -rf Ruimtemeesters-Browser-Chatbot
# Clone your fork
git clone https://github.com/YOUR_ORG/ruimtemeesters-browser-chatbot.git Ruimtemeesters-Browser-Chatbot
cd Ruimtemeesters-Browser-Chatbot
```

- [ ] **Step 2: Set up upstream remote**

```bash
git remote add upstream https://github.com/open-webui/open-webui.git
git remote -v
```

Expected output:

```
origin    https://github.com/YOUR_ORG/ruimtemeesters-browser-chatbot.git (fetch)
origin    https://github.com/YOUR_ORG/ruimtemeesters-browser-chatbot.git (push)
upstream  https://github.com/open-webui/open-webui.git (fetch)
upstream  https://github.com/open-webui/open-webui.git (push)
```

- [ ] **Step 3: Create development branch**

```bash
git checkout -b rm/fork-brand-auth
```

- [ ] **Step 4: Verify the existing file structure matches expectations**

```bash
# Confirm key directories exist
ls src/lib/constants.ts
ls tailwind.config.js
ls backend/open_webui/config.py
ls backend/open_webui/routers/auths.py
ls backend/open_webui/main.py
ls docker-compose.yaml
```

All files should exist. If any are missing, the fork may be on a different version — check `git log --oneline -1` and note the commit hash.

- [ ] **Step 5: Update .gitignore**

Add these entries to the existing `.gitignore`:

```
# RM-specific
.env
.superpowers/
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore
git commit -m "chore: set up RM fork with upstream remote and gitignore"
```

---

## Task 2: Set Up Docker Compose with PostgreSQL

**Files:**

- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.env`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  ollama:
    image: ollama/ollama:${OLLAMA_DOCKER_TAG:-latest}
    container_name: rm-ollama
    volumes:
      - ollama-data:/root/.ollama
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  open-webui:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rm-chatbot
    volumes:
      - open-webui-data:/app/backend/data
    depends_on:
      ollama:
        condition: service_started
      chatbot-db:
        condition: service_healthy
    ports:
      - '${OPEN_WEBUI_PORT:-3333}:8080'
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - DATABASE_URL=postgresql://${POSTGRES_USER:-rmchatbot}:${POSTGRES_PASSWORD:-rmchatbot}@chatbot-db:5432/${POSTGRES_DB:-rmchatbot}
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
      - WEBUI_NAME=${WEBUI_NAME:-Ruimtemeesters AI}
      - WEBUI_FAVICON_URL=/brand-assets/favicon.svg
      - ENABLE_OAUTH_SIGNUP=true
      - OPENID_PROVIDER_URL=${CLERK_OIDC_DISCOVERY_URL}
      - OAUTH_CLIENT_ID=${CLERK_OAUTH_CLIENT_ID}
      - OAUTH_CLIENT_SECRET=${CLERK_OAUTH_CLIENT_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
    extra_hosts:
      - host.docker.internal:host-gateway
    restart: unless-stopped
    networks:
      - rm-internal
      - rm-network

  chatbot-db:
    image: postgres:16-alpine
    container_name: rm-chatbot-db
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-rmchatbot}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-rmchatbot}
      - POSTGRES_DB=${POSTGRES_DB:-rmchatbot}
    volumes:
      - chatbot-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U ${POSTGRES_USER:-rmchatbot}']
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - rm-internal

volumes:
  ollama-data:
  open-webui-data:
  chatbot-db-data:

networks:
  rm-internal:
    driver: bridge
  rm-network:
    external: true
    name: rm-network
```

- [ ] **Step 2: Create .env.example**

```env
# === Ruimtemeesters Browser Chatbot ===

# Port (default 3333)
OPEN_WEBUI_PORT=3333

# Secret key for JWT signing (generate with: openssl rand -hex 32)
WEBUI_SECRET_KEY=

# App branding
WEBUI_NAME=Ruimtemeesters AI

# --- Database ---
POSTGRES_USER=rmchatbot
POSTGRES_PASSWORD=rmchatbot
POSTGRES_DB=rmchatbot

# --- LLM Providers ---
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# --- Clerk OIDC ---
# Create an OAuth Application in Clerk Dashboard → OAuth applications
# Set redirect URI to: http://localhost:3333/oauth/oidc/callback
CLERK_OIDC_DISCOVERY_URL=
CLERK_OAUTH_CLIENT_ID=
CLERK_OAUTH_CLIENT_SECRET=

# --- Ollama ---
OLLAMA_DOCKER_TAG=latest
```

- [ ] **Step 3: Create .env from template**

```bash
cp .env.example .env
# Edit .env with your actual values:
# - Generate WEBUI_SECRET_KEY: openssl rand -hex 32
# - Add your OPENAI_API_KEY
# - Clerk values will be added in Task 8
```

- [ ] **Step 4: Create the shared Docker network (if it doesn't exist)**

```bash
docker network create rm-network 2>/dev/null || true
```

- [ ] **Step 5: Build and start the stack (without Clerk for now)**

```bash
docker compose up -d --build
```

- [ ] **Step 6: Verify all services are running**

```bash
docker compose ps
```

Expected: all three containers (rm-chatbot, rm-ollama, rm-chatbot-db) with status "Up".

```bash
# Verify PostgreSQL is being used (check logs)
docker compose logs open-webui 2>&1 | grep -i "database"
```

- [ ] **Step 7: Open http://localhost:3333 and verify the default OpenWebUI loads**

Create an initial admin account through the UI to confirm the stack works.

- [ ] **Step 8: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: add Docker Compose with PostgreSQL, Ollama, and OpenWebUI"
```

---

## Task 3: Pull Initial Ollama Models

- [ ] **Step 1: Pull llama3.1 (general purpose)**

```bash
docker compose exec ollama ollama pull llama3.1
```

This may take several minutes depending on bandwidth.

- [ ] **Step 2: Pull mistral (fast responses)**

```bash
docker compose exec ollama ollama pull mistral
```

- [ ] **Step 3: Verify models are available**

```bash
docker compose exec ollama ollama list
```

Expected: both `llama3.1` and `mistral` listed.

- [ ] **Step 4: Verify models appear in OpenWebUI**

Open http://localhost:3333, click the model selector dropdown. Both models should appear.

---

## Task 4: Configure Tailwind with RM Brand Colors

**Files:**

- Modify: `tailwind.config.js`

- [ ] **Step 1: Read the current tailwind.config.js**

```bash
cat tailwind.config.js
```

Note the existing `theme.extend` structure.

- [ ] **Step 2: Add RM brand colors to tailwind.config.js**

Add the following to the `theme.extend` section inside the existing config. Do NOT replace the entire file — add to the `extend` block:

```javascript
// Inside theme.extend, add:
colors: {
  rm: {
    raisin: '#161620',
    blue: '#002EA3',
    white: '#F7F4EF',
    violet: '#7F00FF',
    pumpkin: '#F37021',
    lion: '#9C885C',
    mystified: '#C3D7C1',
  },
},
```

- [ ] **Step 3: Rebuild and verify**

```bash
docker compose up -d --build
```

Open http://localhost:3333 — the UI should still load (we haven't applied the colors yet, just registered them).

- [ ] **Step 4: Commit**

```bash
git add tailwind.config.js
git commit -m "feat: add Ruimtemeesters brand colors to Tailwind config"
```

---

## Task 5: Apply CSS Theme Overrides

**Files:**

- Create: `src/lib/themes/ruimtemeesters.css`
- Modify: `src/app.css`

- [ ] **Step 1: Read the current src/app.css to understand existing theme structure**

```bash
cat src/app.css
```

Note how CSS variables and dark mode are structured.

- [ ] **Step 2: Create src/lib/themes/ruimtemeesters.css**

```css
/*
 * Ruimtemeesters Brand Theme
 *
 * Overrides OpenWebUI's default CSS variables with RM brand colors.
 * This file is imported at the end of app.css to take precedence.
 *
 * Brand palette:
 *   Raisin Black: #161620 (dark surfaces)
 *   Klein Blue:   #002EA3 (primary actions)
 *   Smart White:  #F7F4EF (backgrounds)
 *   Violet:       #7F00FF (accents)
 *   Pumpkin:      #F37021 (warnings, secondary)
 *   Lion:         #9C885C (tertiary)
 *   Mystified:    #C3D7C1 (success)
 */

/* Light mode overrides */
:root {
	--color-primary: #002ea3;
	--color-primary-hover: #0038c7;
	--color-primary-foreground: #f7f4ef;
}

/* Dark mode overrides */
.dark {
	--color-primary: #002ea3;
	--color-primary-hover: #0038c7;
	--color-primary-foreground: #f7f4ef;
}

/* Sidebar dark background — RM raisin black */
aside,
[data-sidebar],
nav.sidebar,
#sidebar {
	background-color: #161620 !important;
}

/* Primary buttons and accents — RM klein blue */
button.primary,
[data-primary-button],
.bg-primary {
	background-color: #002ea3 !important;
}

button.primary:hover,
[data-primary-button]:hover {
	background-color: #0038c7 !important;
}

/* User message bubbles */
.user-message,
[data-role='user'] .message-content {
	background-color: #002ea3 !important;
	color: #f7f4ef !important;
}

/* Main background — RM smart white (light mode) */
:root {
	--color-background: #f7f4ef;
}

.dark {
	--color-background: #0f0f17;
}

/* Accent highlights — RM violet */
a:hover,
.text-accent {
	color: #7f00ff;
}

/* Selection indicator */
::selection {
	background-color: rgba(0, 46, 163, 0.3);
}
```

**Note:** The exact CSS variable names depend on the OpenWebUI version at fork time. After forking, inspect the browser DevTools to identify the actual CSS variable names used and adjust this file accordingly. The selectors above are a starting point — refine by inspecting the running app.

- [ ] **Step 3: Import the theme in src/app.css**

Add this line at the END of `src/app.css`:

```css
@import './lib/themes/ruimtemeesters.css';
```

- [ ] **Step 4: Rebuild and verify**

```bash
docker compose up -d --build
```

Open http://localhost:3333 — verify the color scheme has shifted toward RM brand colors. The sidebar should be dark raisin, primary buttons should be klein blue.

- [ ] **Step 5: Refine CSS variables by inspecting the running app**

Open browser DevTools (F12) → Elements tab → inspect the `<html>` element for CSS custom properties. Compare with the variables in `ruimtemeesters.css` and adjust any that don't match the actual variable names used by OpenWebUI.

- [ ] **Step 6: Commit**

```bash
git add src/lib/themes/ruimtemeesters.css src/app.css
git commit -m "feat: apply Ruimtemeesters brand theme CSS overrides"
```

---

## Task 6: Replace Logos, Favicon, and App Name

**Files:**

- Create: `static/brand-assets/` directory with logo files
- Modify: `src/lib/constants.ts`

- [ ] **Step 1: Create brand-assets directory**

```bash
mkdir -p static/brand-assets
```

- [ ] **Step 2: Copy RM logos from the Databank repo**

```bash
# Copy logos from Databank's dist/logos/ directory
# List available logos first:
ls /home/ralph/Projects/Ruimtemeesters-Databank/dist/logos/

# Copy the most appropriate ones:
cp /home/ralph/Projects/Ruimtemeesters-Databank/dist/logos/rm-logo-landscape-payoff-kleinblue.svg static/brand-assets/logo.svg
cp /home/ralph/Projects/Ruimtemeesters-Databank/dist/logos/rm-logo-landscape-payoff-smartwhite.svg static/brand-assets/logo-white.svg
cp /home/ralph/Projects/Ruimtemeesters-Databank/dist/logos/rm-icon-kleinblue.svg static/brand-assets/favicon.svg
```

**Note:** Exact filenames depend on what's in the Databank logos directory. Adjust the `cp` commands to match actual filenames. If an `.ico` favicon is needed, generate one from the SVG using a tool like `convert` (ImageMagick) or an online converter.

- [ ] **Step 3: Generate favicon.ico from SVG (if needed)**

```bash
# If ImageMagick is available:
convert static/brand-assets/favicon.svg -resize 32x32 static/brand-assets/favicon.ico
# Otherwise, use the SVG directly (modern browsers support SVG favicons)
```

- [ ] **Step 4: Update APP_NAME in src/lib/constants.ts**

Find the line:

```typescript
export const APP_NAME = 'Open WebUI';
```

Replace with:

```typescript
export const APP_NAME = 'Ruimtemeesters AI';
```

- [ ] **Step 5: Find and update any other hardcoded "Open WebUI" references in the frontend**

```bash
grep -r "Open WebUI" src/ --include="*.ts" --include="*.svelte" -l
```

Review each file and replace user-visible strings with "Ruimtemeesters AI". Do NOT change license notices, attribution comments, or technical identifiers — only user-facing UI text.

- [ ] **Step 6: Update the app.html to use RM favicon**

Read `src/app.html` and update the favicon link tag to point to `/brand-assets/favicon.svg`.

- [ ] **Step 7: Rebuild and verify**

```bash
docker compose up -d --build
```

Open http://localhost:3333 — verify:

- Page title says "Ruimtemeesters AI"
- Favicon is the RM icon
- Logo appears in the sidebar/header

- [ ] **Step 8: Commit**

```bash
git add static/brand-assets/ src/lib/constants.ts src/app.html
git commit -m "feat: replace logos, favicon, and app name with Ruimtemeesters branding"
```

---

## Task 7: Customize Welcome Page

**Files:**

- Files depend on OpenWebUI version; the main chat page is likely in `src/routes/+page.svelte` or similar

- [ ] **Step 1: Identify the welcome/landing page component**

```bash
# Find the main chat page that shows the welcome message
grep -r "Welcome" src/routes/ --include="*.svelte" -l
grep -r "How can I help" src/ --include="*.svelte" -l
grep -r "greeting" src/lib/components/ --include="*.svelte" -l
```

- [ ] **Step 2: Read the identified component**

Read the file and identify where the welcome message text, suggested prompts, and landing graphic are rendered.

- [ ] **Step 3: Update the welcome message**

Replace the default welcome text with RM-specific content:

```
Welkom bij Ruimtemeesters AI

Stel een vraag over beleid, data, kaarten, of prognoses
```

Replace any default suggested prompts with RM-relevant examples:

- "Zoek beleidsstukken over luchtkwaliteit in Den Haag"
- "Wat is de bevolkingsprognose voor Utrecht in 2030?"
- "Welke gemeenten hebben actieve contracten?"
- "Toon de regels voor dit adres op de kaart"

- [ ] **Step 4: Rebuild and verify**

```bash
docker compose up -d --build
```

Open http://localhost:3333 — verify the welcome screen shows RM branding and Dutch prompt suggestions.

- [ ] **Step 5: Commit**

```bash
git add -A src/routes/ src/lib/components/
git commit -m "feat: customize welcome page with RM branding and Dutch prompt suggestions"
```

---

## Task 8: Create Clerk OAuth Application

This task happens in the Clerk Dashboard, not in code.

- [ ] **Step 1: Go to Clerk Dashboard**

Navigate to https://dashboard.clerk.com → select your Ruimtemeesters organization.

- [ ] **Step 2: Create OAuth Application**

Go to "OAuth applications" in the sidebar → "Add OAuth application".

- Name: `Ruimtemeesters AI Chatbot`
- Scopes: `openid`, `profile`, `email`
- Redirect URI: `http://localhost:3333/oauth/oidc/callback`

**Note:** The callback URL format depends on OpenWebUI's OAuth implementation. Check `backend/open_webui/routers/auths.py` for the exact callback path. Common patterns: `/oauth/oidc/callback`, `/auth/callback`, `/api/v1/auths/callback`.

- [ ] **Step 3: Copy credentials**

Save the following values — the Client Secret is shown only once:

- Client ID
- Client Secret
- Discovery URL (format: `https://<your-clerk-domain>/.well-known/openid-configuration`)

- [ ] **Step 4: Configure role metadata in Clerk**

For each Clerk user, set their `public_metadata` to include an RM role:

```json
{
	"rm_role": "admin"
}
```

Valid values: `admin`, `consultant`, `analyst`, `sales`.

Do this for at least your own user account (set to `admin`).

- [ ] **Step 5: Update .env with Clerk credentials**

```env
CLERK_OIDC_DISCOVERY_URL=https://your-clerk-domain/.well-known/openid-configuration
CLERK_OAUTH_CLIENT_ID=your_client_id_here
CLERK_OAUTH_CLIENT_SECRET=your_client_secret_here
```

- [ ] **Step 6: Restart the stack**

```bash
docker compose up -d
```

---

## Task 9: Configure OpenWebUI to Use Clerk OIDC

**Files:**

- Modify: `backend/open_webui/config.py` (if needed beyond env vars)

- [ ] **Step 1: Verify OpenWebUI's OAuth configuration via env vars**

The `docker-compose.yml` already passes these env vars to the container:

- `ENABLE_OAUTH_SIGNUP=true`
- `OPENID_PROVIDER_URL=${CLERK_OIDC_DISCOVERY_URL}`
- `OAUTH_CLIENT_ID=${CLERK_OAUTH_CLIENT_ID}`
- `OAUTH_CLIENT_SECRET=${CLERK_OAUTH_CLIENT_SECRET}`

- [ ] **Step 2: Check which additional OAuth env vars are needed**

```bash
grep -i "oauth\|openid\|oidc" backend/open_webui/config.py | head -40
```

Review the output and ensure any required variables are set. Common ones to check:

- `OAUTH_SCOPES` — should be `openid profile email`
- `OAUTH_PROVIDER_NAME` — set to `Clerk` for the button label
- `OAUTH_USERNAME_CLAIM` — likely `preferred_username` or `email`
- `OAUTH_EMAIL_CLAIM` — likely `email`

- [ ] **Step 3: Add any missing OAuth env vars to docker-compose.yml**

Update the `environment` section of the `open-webui` service:

```yaml
- OAUTH_PROVIDER_NAME=Clerk
- OAUTH_SCOPES=openid profile email
- OAUTH_USERNAME_CLAIM=email
- OAUTH_EMAIL_CLAIM=email
```

- [ ] **Step 4: Restart and test OAuth login**

```bash
docker compose up -d
```

Open http://localhost:3333 → click the "Sign in with Clerk" button (or similar OAuth login button) → verify it redirects to Clerk login → verify it creates a user in OpenWebUI after successful auth.

- [ ] **Step 5: Verify the user was created in OpenWebUI**

After logging in via Clerk, check the OpenWebUI admin panel (Settings → Users) to confirm the user appears.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: configure Clerk as OIDC provider for OpenWebUI"
```

---

## Task 10: Add Role Mapping Middleware

**Files:**

- Create: `backend/open_webui/test/test_rm_auth.py`
- Create: `backend/open_webui/routers/rm_auth.py`
- Modify: `backend/open_webui/main.py`

- [ ] **Step 1: Write the failing test for role mapping**

Create `backend/open_webui/test/test_rm_auth.py`:

```python
"""Tests for Ruimtemeesters role mapping from Clerk metadata."""

import pytest
from open_webui.routers.rm_auth import map_clerk_role_to_webui_role


class TestClerkRoleMapping:
    def test_admin_maps_to_admin(self):
        metadata = {"rm_role": "admin"}
        assert map_clerk_role_to_webui_role(metadata) == "admin"

    def test_consultant_maps_to_user(self):
        metadata = {"rm_role": "consultant"}
        assert map_clerk_role_to_webui_role(metadata) == "user"

    def test_analyst_maps_to_user(self):
        metadata = {"rm_role": "analyst"}
        assert map_clerk_role_to_webui_role(metadata) == "user"

    def test_sales_maps_to_user(self):
        metadata = {"rm_role": "sales"}
        assert map_clerk_role_to_webui_role(metadata) == "user"

    def test_missing_role_maps_to_pending(self):
        metadata = {}
        assert map_clerk_role_to_webui_role(metadata) == "pending"

    def test_unknown_role_maps_to_pending(self):
        metadata = {"rm_role": "unknown"}
        assert map_clerk_role_to_webui_role(metadata) == "pending"

    def test_none_metadata_maps_to_pending(self):
        assert map_clerk_role_to_webui_role(None) == "pending"


class TestExtractRmRole:
    def test_extracts_rm_role_from_metadata(self):
        from open_webui.routers.rm_auth import extract_rm_role
        metadata = {"rm_role": "consultant"}
        assert extract_rm_role(metadata) == "consultant"

    def test_returns_none_for_missing(self):
        from open_webui.routers.rm_auth import extract_rm_role
        assert extract_rm_role({}) is None

    def test_returns_none_for_none(self):
        from open_webui.routers.rm_auth import extract_rm_role
        assert extract_rm_role(None) is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend
python -m pytest open_webui/test/test_rm_auth.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.routers.rm_auth'`

- [ ] **Step 3: Implement the role mapping module**

Create `backend/open_webui/routers/rm_auth.py`:

```python
"""
Ruimtemeesters Auth — Clerk role mapping for OpenWebUI.

Maps Clerk public_metadata.rm_role to OpenWebUI internal roles.

OpenWebUI role values:
  - "admin"   — full admin access
  - "user"    — standard user (tools/models filtered by RM role separately)
  - "pending" — awaiting approval

The RM-specific role (consultant, analyst, sales) is stored as user metadata
in OpenWebUI for tool/model filtering. OpenWebUI only knows admin/user/pending.
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

# RM roles that map to OpenWebUI "user" (active, non-admin)
ACTIVE_ROLES = {"consultant", "analyst", "sales"}


def extract_rm_role(public_metadata: Optional[dict]) -> Optional[str]:
    """Extract the rm_role from Clerk public_metadata."""
    if not public_metadata:
        return None
    return public_metadata.get("rm_role")


def map_clerk_role_to_webui_role(public_metadata: Optional[dict]) -> str:
    """
    Map Clerk public_metadata to an OpenWebUI role string.

    Returns "admin", "user", or "pending".
    """
    rm_role = extract_rm_role(public_metadata)

    if rm_role is None:
        log.info("No rm_role in Clerk metadata — assigning 'pending'")
        return "pending"

    if rm_role == "admin":
        return "admin"

    if rm_role in ACTIVE_ROLES:
        return "user"

    log.warning("Unknown rm_role '%s' — assigning 'pending'", rm_role)
    return "pending"
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd backend
python -m pytest open_webui/test/test_rm_auth.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/rm_auth.py backend/open_webui/test/test_rm_auth.py
git commit -m "feat: add Clerk-to-OpenWebUI role mapping with tests"
```

---

## Task 11: Integrate Role Mapping into OAuth Flow

**Files:**

- Modify: `backend/open_webui/routers/auths.py` (or wherever OAuth callback is handled)
- Modify: `backend/open_webui/main.py`

- [ ] **Step 1: Find where OAuth users are created after OIDC login**

```bash
grep -n "oauth\|create_user\|signup\|role" backend/open_webui/routers/auths.py | head -30
```

Identify the function that handles the OAuth callback and creates/updates the user.

- [ ] **Step 2: Read the OAuth callback handler**

Read the relevant section of `backend/open_webui/routers/auths.py` to understand how it:

- Extracts user info from the OIDC token
- Creates or finds the user in OpenWebUI
- Assigns a role

- [ ] **Step 3: Add role mapping to the OAuth flow**

In the OAuth callback handler, after extracting user info from Clerk's OIDC response, add:

```python
from open_webui.routers.rm_auth import map_clerk_role_to_webui_role

# After extracting userinfo from OIDC token:
# The Clerk OIDC response includes public_metadata if the scope is configured
public_metadata = userinfo.get("public_metadata", {})
webui_role = map_clerk_role_to_webui_role(public_metadata)
```

Use `webui_role` when creating or updating the user record instead of the default role.

**Note:** The exact integration point depends on the OpenWebUI version. The key principle is: intercept user creation/update during OAuth flow, extract `public_metadata` from the OIDC userinfo response, and call `map_clerk_role_to_webui_role()` to determine the role.

- [ ] **Step 4: Rebuild and test**

```bash
docker compose up -d --build
```

Log out, then log in via Clerk. Check the admin panel to verify your user has the "admin" role (matching your Clerk `public_metadata.rm_role`).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/auths.py
git commit -m "feat: integrate Clerk role mapping into OAuth login flow"
```

---

## Task 12: Add Token Forwarding Utility

**Files:**

- Create: `backend/open_webui/test/test_token_forwarding.py`
- Create: `backend/open_webui/utils/token_forwarding.py`

- [ ] **Step 1: Write failing tests for token forwarding**

Create `backend/open_webui/test/test_token_forwarding.py`:

```python
"""Tests for token forwarding utility."""

import pytest
from unittest.mock import AsyncMock, patch
from open_webui.utils.token_forwarding import build_forwarding_headers, forward_request


class TestBuildForwardingHeaders:
    def test_includes_authorization_header(self):
        headers = build_forwarding_headers(clerk_token="test-jwt-token")
        assert headers["Authorization"] == "Bearer test-jwt-token"

    def test_includes_content_type(self):
        headers = build_forwarding_headers(clerk_token="test-jwt-token")
        assert headers["Content-Type"] == "application/json"

    def test_includes_custom_headers(self):
        headers = build_forwarding_headers(
            clerk_token="test-jwt-token",
            extra_headers={"X-Request-ID": "abc123"},
        )
        assert headers["X-Request-ID"] == "abc123"
        assert headers["Authorization"] == "Bearer test-jwt-token"

    def test_empty_token_raises(self):
        with pytest.raises(ValueError, match="clerk_token"):
            build_forwarding_headers(clerk_token="")

    def test_none_token_raises(self):
        with pytest.raises(ValueError, match="clerk_token"):
            build_forwarding_headers(clerk_token=None)


class TestForwardRequest:
    @pytest.mark.asyncio
    async def test_forward_get_request(self):
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {"data": "test"}

        with patch("open_webui.utils.token_forwarding.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await forward_request(
                method="GET",
                url="http://databank-api:3001/api/v1/policies",
                clerk_token="test-jwt",
            )

            assert result == {"data": "test"}
            mock_client.request.assert_called_once()
            call_kwargs = mock_client.request.call_args
            assert call_kwargs[1]["headers"]["Authorization"] == "Bearer test-jwt"
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd backend
python -m pytest open_webui/test/test_token_forwarding.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement token forwarding utility**

Create `backend/open_webui/utils/token_forwarding.py`:

```python
"""
Token forwarding utility for Ruimtemeesters app integrations.

Forwards the user's Clerk JWT to downstream app endpoints so that
each app can independently validate the token and enforce its own RBAC.

Usage in OpenWebUI Functions:

    from open_webui.utils.token_forwarding import forward_request

    result = await forward_request(
        method="GET",
        url="http://databank-api:3001/api/v1/policies/search",
        clerk_token=user_token,
        params={"q": "luchtkwaliteit", "gemeente": "Den Haag"},
    )
"""

import logging
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


def build_forwarding_headers(
    clerk_token: Optional[str],
    extra_headers: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """
    Build HTTP headers for forwarding requests to RM apps.

    Always includes the Clerk JWT as Bearer token and Content-Type.
    """
    if not clerk_token:
        raise ValueError("clerk_token is required for forwarding requests to apps")

    headers = {
        "Authorization": f"Bearer {clerk_token}",
        "Content-Type": "application/json",
    }

    if extra_headers:
        headers.update(extra_headers)

    return headers


async def forward_request(
    method: str,
    url: str,
    clerk_token: str,
    params: Optional[dict[str, Any]] = None,
    json_body: Optional[dict[str, Any]] = None,
    extra_headers: Optional[dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """
    Forward an authenticated request to an RM app endpoint.

    Returns the parsed JSON response body.
    Raises httpx.HTTPStatusError on 4xx/5xx responses.
    """
    headers = build_forwarding_headers(clerk_token, extra_headers)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python -m pytest open_webui/test/test_token_forwarding.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Verify httpx is in dependencies**

```bash
grep "httpx" pyproject.toml
```

If httpx is not listed, add it to the dependencies in `pyproject.toml`. OpenWebUI likely already includes it.

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/utils/token_forwarding.py backend/open_webui/test/test_token_forwarding.py
git commit -m "feat: add token forwarding utility for RM app integrations"
```

---

## Task 13: Disable Password Auth (Clerk-Only Login)

**Files:**

- Modify: `docker-compose.yml`

- [ ] **Step 1: Add env var to disable password-based signup**

Once Clerk OIDC is confirmed working, add to the `open-webui` environment in `docker-compose.yml`:

```yaml
- ENABLE_PASSWORD_AUTH=false
```

This ensures all users authenticate through Clerk. The initial admin account created in Task 2 remains functional for emergency access.

- [ ] **Step 2: Restart and verify**

```bash
docker compose up -d
```

Open http://localhost:3333 — verify:

- The login page shows only the "Sign in with Clerk" button
- No email/password form is visible
- Clicking the button redirects to Clerk and back

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: disable password auth, enforce Clerk-only login"
```

---

## Task 14: End-to-End Verification

- [ ] **Step 1: Full clean restart**

```bash
docker compose down
docker compose up -d --build
```

- [ ] **Step 2: Verify branding checklist**

Open http://localhost:3333 and confirm:

- [ ] Page title is "Ruimtemeesters AI"
- [ ] Favicon is the RM icon
- [ ] Sidebar background is raisin black (#161620)
- [ ] Primary buttons are klein blue (#002EA3)
- [ ] Welcome message is in Dutch with RM-specific prompts
- [ ] RM logo appears in sidebar/header

- [ ] **Step 3: Verify auth flow**

- [ ] Click "Sign in with Clerk"
- [ ] Clerk login page loads
- [ ] After login, redirected back to chatbot
- [ ] User appears in admin panel with correct role

- [ ] **Step 4: Verify LLM providers**

- [ ] Ollama models (llama3.1, mistral) appear in model selector
- [ ] Can send a message and get a response from Ollama
- [ ] If OpenAI key is set, OpenAI models also appear

- [ ] **Step 5: Verify PostgreSQL is being used**

```bash
docker compose exec chatbot-db psql -U rmchatbot -d rmchatbot -c "\dt"
```

Expected: OpenWebUI tables are listed (users, chats, etc.)

- [ ] **Step 6: Merge branch**

```bash
git checkout main
git merge rm/fork-brand-auth
```

---

## Summary

After completing this plan, you have:

1. A forked OpenWebUI repo with upstream tracking
2. Docker Compose stack: OpenWebUI + Ollama (GPU) + PostgreSQL
3. Full Ruimtemeesters branding (colors, logos, favicon, app name, welcome page)
4. Clerk OIDC authentication (Clerk-only login, no password auth)
5. Role mapping (Clerk metadata → OpenWebUI roles)
6. Token forwarding utility ready for Phase A3 (tool integration)
7. Tests for role mapping and token forwarding

**Next plan:** Phase A3 + A4 — Tool Layer + Aggregator Integration
