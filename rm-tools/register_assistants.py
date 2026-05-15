#!/usr/bin/env python3
"""
Register Ruimtemeesters assistant models and prompt templates with OpenWebUI.

Usage:
    python rm-tools/register_assistants.py --url http://localhost:3333 --token <admin-jwt>
    python rm-tools/register_assistants.py --dry-run
    python rm-tools/register_assistants.py --base-model llama3.1:latest --token <jwt>
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

# Base model to use for all assistants. Defaults to hosted Gemini Flash Lite —
# matches DEFAULT_MODELS in docker-compose.rm.yaml so assistants stay reachable
# even when the local Ollama is paused or doesn't have llama3.1 pulled.
# Override per-deployment with the --base-model CLI flag.
BASE_MODEL = 'gemini.gemini-2.5-flash-lite'

# Directory containing OpenWebUI Filter/Pipe modules registered by this script.
FILTERS_DIR = Path(__file__).resolve().parent / 'filters'

ASSISTANTS = [
    {
        'id': 'rm-beleidsadviseur',
        'name': 'Beleidsadviseur',
        'base_model_id': BASE_MODEL,
        'meta': {
            'profile_image_url': '/brand-assets/assistants/policy.svg',
            'description': 'Expert in Dutch policy documents. Searches beleidsstukken, explains policy implications, compares gemeente policies, and shows relevant rules on the map. Understands the Omgevingswet context.',
            'suggestion_prompts': [
                {
                    'content': 'Zoek alle beleidsstukken over luchtkwaliteit in Den Haag',
                    'title': ['Zoek beleidsstukken', 'over luchtkwaliteit'],
                },
                {
                    'content': 'Vergelijk het woningbouwbeleid van Utrecht en Amsterdam',
                    'title': ['Vergelijk beleid', 'woningbouw'],
                },
                {
                    'content': 'Welke omgevingsregels gelden er voor het centrum van Eindhoven?',
                    'title': ['Omgevingsregels', 'voor Eindhoven'],
                },
            ],
            'toolIds': ['server:mcp:rm-databank', 'server:mcp:rm-geoportaal', 'server:mcp:rm-aggregator'],
        },
        'params': {
            'system': """Je bent de Beleidsadviseur van Ruimtemeesters — een expert in Nederlands omgevingsbeleid.

Je hebt toegang tot de Ruimtemeesters Databank (beleidsdocumenten, kennisgraaf) en het Geoportaal (ruimtelijke regels, kaarten).

Richtlijnen:
- Antwoord altijd in het Nederlands
- Gebruik de Databank tools om beleidsdocumenten te zoeken en de kennisgraaf te raadplegen
- Gebruik het Geoportaal om ruimtelijke regels en kaartgegevens op te vragen
- Verwijs naar specifieke beleidsdocumenten met hun titel en bron
- Leg de relevantie van beleid uit in de context van de Omgevingswet
- Als je iets niet weet, zeg dat eerlijk en stel voor om een beleidsscan te starten""",
        },
    },
    {
        'id': 'rm-demografie-analist',
        'name': 'Demografie Analist',
        'base_model_id': BASE_MODEL,
        'meta': {
            'profile_image_url': '/brand-assets/assistants/chart.svg',
            'description': 'Specialist in population data and demographic forecasting. Queries Primos/CBS data, runs forecasts with different models, explains trends, and compares projections across gemeenten.',
            'suggestion_prompts': [
                {
                    'content': 'Wat is de bevolkingsprognose voor Utrecht in 2030?',
                    'title': ['Bevolkingsprognose', 'Utrecht 2030'],
                },
                {
                    'content': 'Vergelijk de demografische trends van de Randstad gemeenten',
                    'title': ['Demografische trends', 'Randstad'],
                },
                {
                    'content': 'Run een backtest voor Amsterdam om de nauwkeurigheid van het voorspelmodel te valideren',
                    'title': ['Backtest', 'Amsterdam'],
                },
            ],
            'toolIds': ['server:mcp:rm-dashboarding', 'server:mcp:rm-tsa'],
        },
        'params': {
            'system': """Je bent de Demografie Analist van Ruimtemeesters — specialist in bevolkingsdata en demografische prognoses.

Je hebt toegang tot het Dashboarding platform (Primos/CBS data) en de TSA engine (tijdreeksanalyse met Prophet, SARIMA, Holt-Winters, State-Space ensemble).

Richtlijnen:
- Antwoord altijd in het Nederlands
- Gebruik CBS gemeentecodes (bijv. GM0363 voor Amsterdam) bij het aanroepen van de TSA tools
- Leg prognoseresultaten uit in begrijpelijke taal met context
- Vergelijk altijd met CBS werkelijke cijfers waar mogelijk
- Noem het betrouwbaarheidsinterval bij prognoses
- Bij forecasts: leg uit welke modellen het beste presteren en waarom""",
        },
    },
    {
        'id': 'rm-ruimtelijk-adviseur',
        'name': 'Ruimtelijk Adviseur',
        'base_model_id': BASE_MODEL,
        'meta': {
            'profile_image_url': '/brand-assets/assistants/map-pin.svg',
            'description': 'Spatial planning expert. Queries 3D building data, air quality, weather, and spatial rules. Generates map exports and sets up monitoring alerts. Links spatial data to relevant policy context.',
            'suggestion_prompts': [
                {
                    'content': 'Hoe is de luchtkwaliteit in Rotterdam op dit moment?',
                    'title': ['Luchtkwaliteit', 'Rotterdam'],
                },
                {
                    'content': 'Welke gebouwen in Amsterdam Centrum zijn hoger dan 30 meter?',
                    'title': ['Gebouwdata', 'Amsterdam'],
                },
                {'content': 'Zoek PDOK datasets over bodemkwaliteit', 'title': ['PDOK zoeken', 'bodemkwaliteit']},
            ],
            'toolIds': ['server:mcp:rm-geoportaal', 'server:mcp:rm-databank', 'server:mcp:rm-aggregator'],
        },
        'params': {
            'system': """Je bent de Ruimtelijk Adviseur van Ruimtemeesters — expert in ruimtelijke planning en omgevingsdata.

Je hebt toegang tot het Geoportaal (3D gebouwdata, luchtkwaliteit, weer, ruimtelijke regels, PDOK) en de Databank (beleidsdocumenten).

Richtlijnen:
- Antwoord altijd in het Nederlands
- Gebruik het Geoportaal voor ruimtelijke data: luchtkwaliteit, weer, gebouwen, regels
- Koppel ruimtelijke data aan relevant beleid via de Databank
- Leg meetwaarden uit in context (bijv. WHO-normen voor luchtkwaliteit)
- Gebruik PDOK search voor nationale geo-datasets
- Adviseer over ruimtelijke gevolgen van beleidskeuzes""",
        },
    },
    {
        'id': 'rm-sales-adviseur',
        'name': 'Sales Adviseur',
        'base_model_id': BASE_MODEL,
        'meta': {
            'profile_image_url': '/brand-assets/assistants/currency.svg',
            'description': 'Business development assistant. Shows gemeente contract status, finds matching TenderNED assignments, runs sales forecasts, and provides market intelligence.',
            'suggestion_prompts': [
                {
                    'content': 'Welke gemeenten hebben actieve contracten met Ruimtemeesters?',
                    'title': ['Gemeente status', 'actieve contracten'],
                },
                {'content': 'Wat zijn de nieuwste opdrachten in de inbox?', 'title': ['Opdrachten inbox', 'nieuw']},
                {
                    'content': 'Hoe ziet de pipeline eruit? Welke deadlines komen eraan?',
                    'title': ['Pipeline', 'deadlines'],
                },
            ],
            'toolIds': ['server:mcp:rm-riens', 'server:mcp:rm-sales-predictor', 'server:mcp:rm-opdrachten'],
        },
        'params': {
            'system': """Je bent de Sales Adviseur van Ruimtemeesters — assistent voor business development en acquisitie.

Je hebt toegang tot de Riens Sales Viewer (gemeentestatus), Sales Predictor (verkoopprognoses), en Opdrachten Scanner (DAS/inhuur pipeline).

Richtlijnen:
- Antwoord altijd in het Nederlands
- Gebruik de Sales Viewer om contractstatus per gemeente te bekijken
- Gebruik de Opdrachten Scanner om de inbox, pipeline en deadlines te beheren
- Geef proactief advies over kansen en risico's
- Bij pipeline vragen: noem altijd aankomende deadlines
- Bij Sales Predictor: leg modelkeuze en nauwkeurigheid uit
- Ken de context van Servicedesk Leefomgeving""",
        },
    },
    {
        'id': 'rm-assistent',
        'name': 'Ruimtemeesters Assistent',
        'base_model_id': BASE_MODEL,
        'meta': {
            'profile_image_url': '/brand-assets/assistants/spark.svg',
            'description': 'General-purpose Ruimtemeesters assistant with access to all tools. Routes to the right app based on your question. The default assistant for any RM-related query.',
            'suggestion_prompts': [
                {
                    'content': 'Zoek beleidsstukken over luchtkwaliteit in Den Haag',
                    'title': ['Zoek beleidsstukken', 'luchtkwaliteit'],
                },
                {
                    'content': 'Wat is de bevolkingsprognose voor Utrecht in 2030?',
                    'title': ['Bevolkingsprognose', 'Utrecht'],
                },
                {'content': 'Welke gemeenten hebben actieve contracten?', 'title': ['Gemeente status', 'contracten']},
                {'content': 'Wat zijn de nieuwste opdrachten in de inbox?', 'title': ['Opdrachten', 'inbox']},
                {
                    'content': 'Start een BOPA-haalbaarheidstoets voor een nieuw project — gebruik /bopa-haalbaarheid',
                    'title': ['BOPA', 'haalbaarheidstoets'],
                },
            ],
            'toolIds': [
                'server:mcp:rm-databank',
                'server:mcp:rm-geoportaal',
                'server:mcp:rm-tsa',
                'server:mcp:rm-dashboarding',
                'server:mcp:rm-riens',
                'server:mcp:rm-sales-predictor',
                'server:mcp:rm-opdrachten',
                'server:mcp:rm-aggregator',
                'server:mcp:rm-memory',
            ],
            # Inlet filters: BOPA session context (priority 10) lands first,
            # memory recall (priority 11) lands second, save-prompt (priority 12)
            # last. The first two are read-only and fail-open — chat proceeds
            # unchanged if rm-memory is unreachable. The save-prompt filter
            # makes no RPCs; it only injects a system instruction at threshold
            # crossings. v1 attaches only here; extending to specialists is a follow-up.
            'filterIds': ['bopa_session_context', 'memory_recall_context', 'memory_save_prompt', 'skills_context'],
        },
        'params': {
            'system': """Je bent de Ruimtemeesters AI Assistent — de centrale toegangspoort tot alle Ruimtemeesters applicaties en data.

Je hebt toegang tot alle tools:
- Databank: beleidsdocumenten zoeken, kennisgraaf
- Geoportaal: ruimtelijke regels, luchtkwaliteit, weer, gebouwdata
- TSA: demografische prognoses (Prophet, SARIMA, ensemble)
- Dashboarding: CBS data, Primos bevolkingsgegevens
- Riens Sales Viewer: gemeentestatus en contracten
- Sales Predictor: verkoopprognoses
- Opdrachten Scanner: DAS/inhuur pipeline
- Aggregator: cross-app zoeken over beleid + ruimtelijke + demografische data
- Memory (rm-memory): sessiestate voor meerstapsworkflows zoals BOPA — bewaart per project_id en gemeente_code de fases en bevindingen

Persoonlijk geheugen (rm-memory):
- Roep `save_memory` aan wanneer de gebruiker een terugkerend feit, voorkeur of werkafspraak deelt die volgende sessies relevant blijft (bv. "ik werk vooral aan project X", "noem me bij m'n voornaam", "voor gemeente Y gebruik altijd bron Z"). Kies een korte, kebab-case `name` en zet `scope='user'` voor persoonlijke voorkeuren of `scope='project'` met `project_id` voor projectgebonden feiten.
- Roep `save_memory` NIET aan voor losse vragen, eenmalige opdrachten, of berichten zonder duurzame waarde.
- Het systeem injecteert al automatisch relevante memories bovenaan deze prompt (sectie "EERDER OPGESLAGEN MEMORIES"); roep `get_memory(name)` aan voor de volledige inhoud van een specifieke entry.
- Voor zware downstream-tools (bv. `beleidsscan_query`, `ruimtelijke_toets`, `evaluate_rules`, `compliance_scan`, `search_artikelen`, `search_documents`): roep eerst `prepare_tool_call({target_tool, target_server, project_id?, hint})` aan op rm-memory. Die geeft je het JSON-schema van de doel-tool plus alle eerder opgeslagen memories die voor deze call relevant zijn (FTS-gerankt op tool-beschrijving + hint). Gebruik het om argumenten preciezer te kiezen, dubbel werk te vermijden, en gaten in je input expliciet aan de gebruiker voor te leggen. Sla dit over voor lichte read-only calls of vervolgvragen op een tool die je net hebt gebruikt.
- Bij een [Systeem-signaal] over gespreks-tokens (zie inlet-filter): rond je antwoord af met een korte vraag of de gebruiker de belangrijkste punten van dit gesprek wil opslaan. Bij bevestiging: roep `summarize_session` aan en volg de scaffold die je terugkrijgt; bij weigering: ga normaal door, wij vragen later opnieuw.
- **Tool-fouten eerlijk melden:** Als een aanroep van `save_memory`, `forget_memory`, `summarize_session`, `recall_memory` of een andere memory-tool een fout teruggeeft (bv. validation error, 401, timeout): vermeld dit expliciet aan de gebruiker — bijvoorbeeld "Het opslaan is helaas mislukt door een technische fout" — en bied aan om het opnieuw te proberen of de informatie tijdelijk anders vast te leggen. **Beweer nooit dat iets is opgeslagen wanneer de tool een error returnde.** Hetzelfde geldt voor andere tool-aanroepen: als de tool faalt, zeg dat tegen de gebruiker; doe geen alsof.

BOPA-workflow (Buitenplanse Omgevingsplanactiviteit):
- Nieuwe adviseur die de werkwijze niet kent? Verwijs naar `/bopa-help` voor een korte uitleg.
- De adviseur kan een evaluatie starten via `/bopa-haalbaarheid` (Fase 1), `/bopa-strijdigheid` (Fase 2) of `/bopa-beleid` (Fase 3)
- Volg de skill in `.claude/skills/bopa/SKILL.md`: geocode → list/create_bopa_session → fase-tools → update_bopa_session
- Respecteer de fase-prerequisites die de memory-server afdwingt (Fase 2/3 vereisen Fase 1, etc.)

Richtlijnen:
- Antwoord altijd in het Nederlands
- Kies automatisch de juiste tool(s) op basis van de vraag
- Combineer data uit meerdere bronnen wanneer relevant
- Wees proactief: als een vraag over beleid ook ruimtelijke context heeft, bied die aan
- Bij onduidelijke vragen, vraag om verduidelijking
- Verwijs naar specifieke bronnen en data waar mogelijk""",
        },
    },
]

PROMPTS = [
    {
        'command': 'beleidsscan',
        'name': 'Beleidsscan',
        'content': "Start een beleidsscan voor {{gemeente}}. Zoek alle relevante beleidsdocumenten en geef een samenvatting van de belangrijkste beleidsthema's, maatregelen, en hun status.",
    },
    {
        'command': 'prognose',
        'name': 'Bevolkingsprognose',
        'content': 'Geef de bevolkingsprognose voor gemeente {{gemeente}} (CBS code: {{geo_code}}). Vergelijk de prognose met de huidige situatie en benoem de belangrijkste demografische trends.',
    },
    {
        'command': 'vergelijk',
        'name': 'Vergelijk gemeenten',
        'content': 'Vergelijk {{gemeente_1}} en {{gemeente_2}} op het gebied van {{onderwerp}}. Gebruik zowel beleidsdata als demografische gegevens.',
    },
    {
        'command': 'opdrachten',
        'name': 'Opdrachten zoeken',
        'content': 'Doorzoek de opdrachten pipeline. Toon de huidige inbox, actieve pipeline items, en aankomende deadlines. Geef een samenvatting van de status.',
    },
    {
        'command': 'rapport',
        'name': 'Rapport genereren',
        'content': 'Genereer een rapport op basis van ons gesprek tot nu toe. Structureer het met een samenvatting, bevindingen, en aanbevelingen. Gebruik een professionele toon.',
    },
    {
        'command': 'luchtkwaliteit',
        'name': 'Luchtkwaliteit',
        'content': 'Geef de actuele luchtkwaliteitsgegevens voor {{locatie}}. Vergelijk met WHO-normen en nationaal beleid. Benoem eventuele aandachtspunten.',
    },
    {
        'command': 'gemeente-status',
        'name': 'Gemeente contractstatus',
        'content': 'Geef een overzicht van de contractstatus voor {{gemeente}}. Toon of het contract actief, gearchiveerd of prospect is, en welke diensten er lopen.',
    },
    {
        'command': 'help',
        'name': 'Help',
        'content': "Toon een overzicht van alle beschikbare commando's en wat de Ruimtemeesters AI Assistent kan doen. Organiseer per categorie: beleid, demografie, ruimtelijk, sales, en opdrachten.",
    },
    {
        'command': 'bopa-help',
        'name': 'BOPA — Hoe werkt het?',
        'content': (
            'Leg in het Nederlands en in maximaal 250 woorden uit wat een BOPA-evaluatie is en hoe '
            'de adviseur er een doet via deze chat. Geef geen tool-calls; dit is puur een uitleg. '
            'Structuur:\n\n'
            '1) Wat is een BOPA? — Buitenplanse Omgevingsplanactiviteit onder de Omgevingswet, een '
            'vergunning voor een initiatief dat afwijkt van het omgevingsplan.\n'
            '2) De 6 fasen — Fase 1 Haalbaarheid (kan dit hier?), Fase 2 Strijdigheid (botst dit met '
            'het omgevingsplan?), Fase 3 Beleid (welke beleidsstukken zijn relevant?), Fase 4 '
            'Omgevingsaspecten (lucht, geluid, bodem, …), Fase 5 Onderbouwing (juridische motivering), '
            'Fase 6 Toetsing (eindafweging). Fasen 2/3 vereisen Fase 1; 4/5 vereisen 1+2+3; 6 vereist '
            'alle voorgaande.\n'
            "3) Slash-commando's — vermeld dat de adviseur kan starten met `/bopa-haalbaarheid` (Fase 1), "
            'door kan met `/bopa-strijdigheid` (Fase 2), `/bopa-beleid` (Fase 3) en '
            '`/bopa-omgevingsaspecten` (Fase 4), en `/bopa-status` kan gebruiken voor een overzicht '
            "van lopende sessies. Fase 5–6 commando's zijn nog niet gepubliceerd (MCP-tools in de "
            'wacht).\n'
            '4) Automatische context — meld dat als de adviseur al een lopende BOPA-sessie heeft, '
            '`rm-assistent` die automatisch inlaadt aan het begin van elke chat (via de '
            'bopa_session_context inlet filter), zodat ze niet steeds `/bopa-status` hoeven te typen.\n'
            '5) Privacy — een korte regel: per-user opt-out is mogelijk via instellingen → filters → '
            'BOPA Session Context.\n\n'
            'Sluit af met de suggestie: "Wil je beginnen? Typ `/bopa-haalbaarheid` met het adres van '
            'je project."'
        ),
    },
    {
        'command': 'bopa-status',
        'name': 'BOPA — Lopende sessies',
        'content': (
            'Geef een overzicht van mijn lopende BOPA-sessies. '
            'Roep `list_bopa_sessions({})` aan op de rm-memory MCP server (laat het filter leeg om alle '
            'sessies van mijn account te zien — als het filter verplicht is, vraag dan om gemeente_code of '
            'project_id). Toon per sessie: project_id, adres/locatie, gemeente_code, welke fasen al zijn '
            'afgerond (1 t/m 6), welke fase de volgende logische stap is (gebruik `dependencies_met`), en '
            'eventuele blocked-by hints. Sortér op meest recent bijgewerkt. Geen verdere tool-calls — alleen '
            'de status, geen evaluatie.'
        ),
    },
    {
        'command': 'bopa-haalbaarheid',
        'name': 'BOPA — Fase 1: Haalbaarheid',
        'content': (
            'Start een BOPA-haalbaarheidstoets voor het adres {{adres}} (project: {{project_id}}). '
            'Volg de BOPA skill: geocode het adres, roep `list_bopa_sessions` aan om bestaande sessies te vinden, '
            'maak indien nodig een nieuwe sessie via `create_bopa_session`, en voer de Fase 1 (Haalbaarheid) checks uit '
            '(`activities_at_point`, bouwvlak/hoogte/BKL 8.0b). Schrijf het verdict terug via '
            '`update_bopa_session({phase: 1, ...})` en vat de uitkomst samen voor de adviseur.'
        ),
    },
    {
        'command': 'bopa-strijdigheid',
        'name': 'BOPA — Fase 2: Strijdigheid',
        'content': (
            'Voer de BOPA Fase 2 (Strijdigheid) toets uit voor sessie {{session_id}}. '
            'Vereist Fase 1 (Haalbaarheid) als prerequisite — als die nog niet is afgerond, leg dat uit en stel voor '
            '`/bopa-haalbaarheid` eerst te draaien. Gebruik `ruimtelijke_toets` en `evaluate_rules` om de strijdigheden '
            'met het omgevingsplan vast te stellen. Schrijf de bevindingen terug via '
            '`update_bopa_session({phase: 2, ...})` en geef per strijdigheid een korte juridische motivering.'
        ),
    },
    {
        'command': 'bopa-beleid',
        'name': 'BOPA — Fase 3: Beleid',
        'content': (
            'Voer de BOPA Fase 3 (Beleid) toets uit voor sessie {{session_id}}. '
            'Vereist Fase 1 (Haalbaarheid) als prerequisite — als die nog niet is afgerond, leg dat uit en stel voor '
            '`/bopa-haalbaarheid` eerst te draaien. Gebruik `search_policy({section, gemeente_code})` op de Databank '
            'om relevante beleidsstukken op te halen, en koppel ze aan de geometrie via het Geoportaal. Schrijf de '
            'gevonden beleidskaders terug via `update_bopa_session({phase: 3, ...})`. Citeer voor elke bewering de '
            'titel en bron van het beleidsstuk; geen ongedekte beweringen.'
        ),
    },
    {
        'command': 'bopa-omgevingsaspecten',
        'name': 'BOPA — Fase 4: Omgevingsaspecten',
        'content': (
            'Voer de BOPA Fase 4 (Omgevingsaspecten) toets uit voor sessie {{session_id}}. '
            'Vereist Fasen 1+2+3 als prerequisites — als één daarvan nog niet is afgerond, leg dat uit en stel voor '
            '`/bopa-haalbaarheid`, `/bopa-strijdigheid` of `/bopa-beleid` eerst te draaien (volg de volgorde uit '
            '`dependencies_met` op de sessie). De MCP weigert de schrijf-call op niet-vervulde prerequisites — '
            'lees die foutmelding goed en vertaal in het Nederlands wat de adviseur moet doen.\n\n'
            'Stappen:\n'
            '1) Haal de sessie op (`get_bopa_session({session_id})`) en lees `project_id`, `lon`, `lat`, '
            '`gemeente_code`.\n'
            "2) Roep op het Geoportaal MCP `sample_bopa_constraints_at_point({lon, lat})` aan voor de ruimtelijke "
            'constraints die over het projectpunt liggen (bodem, geluid, water, ecologie, archeologie, etc.).\n'
            "3) Roep op de Databank MCP `theme_profile_for_gemeente({gemeente_code})` aan voor het volledige "
            "themaprofiel van de gemeente (welke thema's gereguleerd zijn en hoe streng).\n"
            "4) Bereken de doorsnede tussen de geraakte ruimtelijke constraints en de gereguleerde thema's. "
            'Voor elk gedeeld thema, roep `rules_by_gemeente_and_theme({gemeente_code, theme})` aan voor de '
            'concrete artikelen + verwijzingen.\n'
            "5) Geef per thema een verdict: `present` (volledig geadresseerd in beleid + ruimtelijk relevant), "
            "`partial` (deels — leg uit wat ontbreekt), of `missing` (gereguleerd thema raakt het project "
            'maar geen beleidsdekking gevonden).\n'
            '6) Schrijf de bevindingen terug via `update_bopa_session({phase: 4, data: {themes: [...], '
            'verdicts: {...}, citations: [...]}})`.\n\n'
            'Citatie-eis: voor elke bewering verwijs je expliciet naar de bron — Geoportaal-laag '
            '(`layerKey` + `featureId`) voor ruimtelijke hits, en concreet artikel + naam van het '
            'beleidsstuk voor regulatoire verwijzingen. Geen ongedekte beweringen. Sluit af met een korte '
            'Nederlandse samenvatting voor de adviseur en stel `/bopa-status` voor om de bijgewerkte sessie '
            'te zien.'
        ),
    },
]


FILTERS = [
    {
        'id': 'bopa_session_context',
        'name': 'BOPA Session Context',
        'description': (
            "Inlet filter that injects the user's most-recent active BOPA session "
            'into the system prompt. Read-only context priming via rm-memory MCP. '
            'No-op when rm-memory is unreachable or the user has no active sessions.'
        ),
        'source_path': 'bopa_session_context.py',
        'needs_memory_token': True,
    },
    {
        'id': 'memory_recall_context',
        'name': 'Memory Recall Context',
        'description': (
            "Inlet filter that calls recall_memory with the user's latest message "
            'and injects matching memory descriptions into the system prompt. '
            'Read-only, fail-open. No-op for queries shorter than 4 chars or when '
            'no memories match.'
        ),
        'source_path': 'memory_recall_context.py',
        'needs_memory_token': True,
    },
    {
        'id': 'memory_save_prompt',
        'name': 'Memory Save Prompt',
        'description': (
            'Inlet filter that injects a one-shot instruction telling the assistant '
            'to ask the user about saving when conversation context crosses a '
            'configured threshold (default 100k / 250k / 500k / 1M tokens). '
            'No outbound RPCs; per-(user, chat) in-memory state.'
        ),
        'source_path': 'memory_save_prompt.py',
        'needs_memory_token': False,
    },
    {
        'id': 'skills_context',
        'name': 'Skills Context',
        'description': (
            "Inlet filter that fetches the active persona's mandatory skills from "
            'rm-skills (http://rm-skills:4101) at chat start and injects each body '
            "as a <skill name='...'> block in the system prompt. Read-only, "
            'fail-open. Cached per (persona, user_id) for 60s.'
        ),
        'source_path': 'skills_context.py',
        # rm-skills uses its own bearer token, distinct from the rm-memory
        # MEMORY_GATEWAY_TOKEN. Seed it via SKILLS_GATEWAY_TOKEN — see the
        # register_filter / _seed_filter_valves path below for the valve key.
        'needs_memory_token': False,
        'needs_skills_token': True,
    },
]


def _build_model_payload(assistant: dict) -> dict:
    """Single source of truth for the assistant POST payload (used by both
    live registration and --dry-run printing). Keep dry_run_model and
    register_model aligned by going through this helper."""
    return {
        'id': assistant['id'],
        'name': assistant['name'],
        'base_model_id': assistant['base_model_id'],
        'meta': assistant['meta'],
        'params': assistant['params'],
        'is_active': True,
    }


def register_model(base_url: str, token: str, assistant: dict) -> bool:
    """Register or update an assistant model."""
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = _build_model_payload(assistant)

    resp = requests.post(f'{base_url}/api/v1/models/create', headers=headers, json=payload)

    if resp.status_code == 200:
        print(f'  + Model: {assistant["name"]} ({assistant["id"]})')
        return True

    if 'already registered' in resp.text.lower():
        resp = requests.post(
            f'{base_url}/api/v1/models/model/update',
            headers=headers,
            json=payload,
        )
        if resp.status_code == 200:
            print(f'  ~ Updated model: {assistant["name"]} ({assistant["id"]})')
            return True

    print(f'  x Failed model: {assistant["name"]} -- {resp.status_code}: {resp.text[:200]}')
    return False


def register_prompt(base_url: str, token: str, prompt: dict) -> bool:
    """Register or update a prompt template."""
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {
        'command': prompt['command'],
        'name': prompt['name'],
        'content': prompt['content'],
    }

    resp = requests.post(f'{base_url}/api/v1/prompts/create', headers=headers, json=payload)

    if resp.status_code == 200:
        print(f'  + Prompt: /{prompt["command"]} — {prompt["name"]}')
        return True

    if resp.status_code != 200:
        # Find existing prompt ID by listing all prompts
        list_resp = requests.get(f'{base_url}/api/v1/prompts/', headers=headers)
        if list_resp.status_code == 200:
            for p in list_resp.json():
                if p.get('command') == prompt['command']:
                    resp = requests.post(
                        f'{base_url}/api/v1/prompts/id/{p["id"]}/update',
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 200:
                        print(f'  ~ Updated prompt: /{prompt["command"]}')
                        return True
                    break

    print(f'  x Failed prompt: /{prompt["command"]} -- {resp.status_code}: {resp.text[:200]}')
    return False


def _read_filter_source(filter_def: dict) -> str:
    """Load a filter's Python source from FILTERS_DIR. Raises FileNotFoundError
    on miss so the caller fails loudly rather than registering an empty body."""
    path = FILTERS_DIR / filter_def['source_path']
    return path.read_text(encoding='utf-8')


def _seed_filter_valves(
    base_url: str,
    token: str,
    filter_def: dict,
    memory_token: str,
    skills_token: str = '',
) -> bool:
    """Seed the filter's valves via /api/v1/functions/id/{id}/valves/update.

    Filters that talk to rm-memory (`bopa_session_context`,
    `memory_recall_context`) need an `mcp_token` valve set or every RPC
    401s — see Issue #49. We seed it on every registration run so the
    deploy step can't drift from the source.

    Filters that talk to rm-skills (`skills_context`) use a separate
    `skills_token` valve; rm-skills runs its own bearer (SKILLS_GATEWAY_TOKEN)
    rather than reusing the memory gateway secret.

    Filters that don't have a token field (e.g. `memory_save_prompt`,
    which makes no outbound calls) get `valves_extras` only or nothing at
    all — caller's choice via `valves_extras` in FILTERS entry.
    """
    extras = filter_def.get('valves_extras') or {}
    valves: dict = {**extras}
    if filter_def.get('needs_memory_token') and memory_token:
        valves['mcp_token'] = memory_token
    if filter_def.get('needs_skills_token') and skills_token:
        valves['skills_token'] = skills_token
    if not valves:
        return True
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    resp = requests.post(
        f'{base_url}/api/v1/functions/id/{filter_def["id"]}/valves/update',
        headers=headers,
        json=valves,
    )
    if resp.status_code == 200:
        keys = ', '.join(sorted(valves.keys()))
        print(f'    -> valves seeded ({keys})')
        return True
    print(f'    -> valves seed FAILED: {resp.status_code}: {resp.text[:200]}')
    return False


def register_filter(
    base_url: str,
    token: str,
    filter_def: dict,
    memory_token: str = '',
    skills_token: str = '',
) -> bool:
    """Register or update an OpenWebUI filter (Function with type='filter').

    The server infers `type` from the module's class definition (Pipe / Filter /
    Action), so the payload is just the FunctionForm: {id, name, content, meta}.
    Newly created functions are inactive by default — we toggle them on.
    After install/update we seed the filter's valves; this is the step that
    was missing pre-Issue #49 and caused all filter RPCs to silently 401.
    """
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        content = _read_filter_source(filter_def)
    except FileNotFoundError as e:
        print(f'  x Filter source missing: {filter_def["id"]} -- {e}')
        return False

    payload = {
        'id': filter_def['id'],
        'name': filter_def['name'],
        'content': content,
        'meta': {'description': filter_def.get('description', '')},
    }

    resp = requests.post(f'{base_url}/api/v1/functions/create', headers=headers, json=payload)
    created = False
    if resp.status_code == 200:
        print(f'  + Filter: {filter_def["name"]} ({filter_def["id"]})')
        created = True
    elif 'id_taken' in resp.text.lower() or resp.status_code in (400, 409):
        # Update path: PUT-like POST to /id/{id}/update.
        resp = requests.post(
            f'{base_url}/api/v1/functions/id/{filter_def["id"]}/update',
            headers=headers,
            json=payload,
        )
        if resp.status_code == 200:
            print(f'  ~ Updated filter: {filter_def["name"]} ({filter_def["id"]})')
        else:
            print(f'  x Failed filter update: {filter_def["id"]} -- {resp.status_code}: {resp.text[:200]}')
            return False
    else:
        print(f'  x Failed filter create: {filter_def["id"]} -- {resp.status_code}: {resp.text[:200]}')
        return False

    # Ensure the filter is active. Toggle is a flip-switch — only call it when
    # currently inactive, otherwise we'd disable a filter that admin already
    # enabled manually.
    get_resp = requests.get(
        f'{base_url}/api/v1/functions/id/{filter_def["id"]}',
        headers=headers,
    )
    if get_resp.status_code == 200:
        is_active = bool(get_resp.json().get('is_active'))
        if not is_active:
            tog = requests.post(
                f'{base_url}/api/v1/functions/id/{filter_def["id"]}/toggle',
                headers=headers,
            )
            if tog.status_code == 200:
                print('    -> activated')
            else:
                print(f'    -> activation failed: {tog.status_code}: {tog.text[:200]}')
                return False
        elif created:
            # Server-side: a freshly-created filter without a `toggle` attribute
            # comes back inactive. If we got here with is_active=True, OpenWebUI
            # already auto-enabled it (filter has the `toggle` flag). Either is fine.
            pass
    else:
        print(f'    -> could not verify is_active: {get_resp.status_code}')
        # Don't fail — best-effort activation; admin can flip via UI.

    # Seed valves (e.g. mcp_token). Done last so the filter is registered
    # and active before its config gets written. A valve-seed failure is
    # treated as a hard failure: a filter without its token will silently
    # 401 on every call.
    return _seed_filter_valves(base_url, token, filter_def, memory_token, skills_token)


def dry_run_model(assistant: dict) -> bool:
    """Print what would be POSTed for an assistant. Always succeeds."""
    payload = _build_model_payload(assistant)
    print(f'  ? Would register model: {assistant["name"]} ({assistant["id"]})')
    print(f'    base_model_id: {assistant["base_model_id"]}')
    print(f'    toolIds: {assistant["meta"].get("toolIds", [])}')
    if assistant['meta'].get('filterIds'):
        print(f'    filterIds: {assistant["meta"].get("filterIds")}')
    print(f'    suggestion_prompts: {len(assistant["meta"].get("suggestion_prompts", []))}')
    print(f'    payload bytes: {len(json.dumps(payload))}')
    return True


def dry_run_prompt(prompt: dict) -> bool:
    """Print what would be POSTed for a slash prompt. Always succeeds."""
    print(f'  ? Would register prompt: /{prompt["command"]} — {prompt["name"]}')
    print(f'    content preview: {prompt["content"][:80]}{"..." if len(prompt["content"]) > 80 else ""}')
    return True


def dry_run_filter(filter_def: dict) -> bool:
    """Print what would be POSTed for a filter. Surfaces missing source files
    early so the live registration doesn't fail mid-run."""
    try:
        content = _read_filter_source(filter_def)
    except FileNotFoundError as e:
        print(f'  ? Filter source MISSING: {filter_def["id"]} -- {e}')
        return False
    print(f'  ? Would register filter: {filter_def["name"]} ({filter_def["id"]})')
    print(f'    description: {filter_def.get("description", "")[:80]}')
    print(f'    source bytes: {len(content)}')
    return True


def main():
    parser = argparse.ArgumentParser(description='Register RM assistants and prompts')
    parser.add_argument('--url', default='http://localhost:3333', help='OpenWebUI base URL')
    parser.add_argument('--token', help='Admin JWT token (required unless --dry-run)')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print payloads instead of POSTing. No --token needed.',
    )
    parser.add_argument(
        '--base-model',
        default=None,
        help=f'Override base_model_id for all assistants (default: {BASE_MODEL})',
    )
    parser.add_argument(
        '--memory-token',
        default=None,
        help=(
            'Bearer token for the rm-memory MCP. Seeded into the mcp_token '
            'valve of inlet filters that talk to rm-memory. Falls back to '
            '$MEMORY_GATEWAY_TOKEN. Required for filter recall/BOPA-context '
            'to work — see Issue #49.'
        ),
    )
    parser.add_argument(
        '--skills-token',
        default=None,
        help=(
            'Bearer token for the rm-skills HTTP API. Seeded into the '
            'skills_token valve of the skills_context filter. Falls back '
            'to $SKILLS_GATEWAY_TOKEN. Optional — rm-skills currently '
            'allows unauthenticated reads, but seeding the token future-'
            'proofs against the Phase D scoping work.'
        ),
    )
    args = parser.parse_args()

    if not args.dry_run and not args.token:
        parser.error('--token is required unless --dry-run is set')

    memory_token = args.memory_token or os.environ.get('MEMORY_GATEWAY_TOKEN', '')
    if not args.dry_run and not memory_token and any(f.get('needs_memory_token') for f in FILTERS):
        print(
            '  ! WARNING: no --memory-token / MEMORY_GATEWAY_TOKEN set; '
            'filters that talk to rm-memory will silently 401 (Issue #49)',
            file=sys.stderr,
        )

    skills_token = args.skills_token or os.environ.get('SKILLS_GATEWAY_TOKEN', '')
    # Note: rm-skills currently allows unauthenticated reads, so no warning
    # when the token is absent — the filter just sends no Authorization
    # header. Set SKILLS_GATEWAY_TOKEN when the service starts enforcing it.

    if args.base_model:
        for a in ASSISTANTS:
            a['base_model_id'] = args.base_model

    suffix = ' (dry-run)' if args.dry_run else ''

    # Filters must register before models — a model that lists a filter ID in
    # meta.filterIds before the filter exists is harmless on save (OpenWebUI
    # accepts arbitrary IDs) but the filter won't run until it's installed and
    # active. Registering filters first keeps the order observable in admin
    # UIs and avoids a confusing "first chat after install has no injection"
    # window.
    print(f'=== Registering {len(FILTERS)} filters{suffix} ===\n')
    if args.dry_run:
        filter_success = sum(1 for f in FILTERS if dry_run_filter(f))
    else:
        filter_success = sum(
            1
            for f in FILTERS
            if register_filter(
                args.url,
                args.token,
                f,
                memory_token=memory_token,
                skills_token=skills_token,
            )
        )

    print(f'\n=== Registering {len(ASSISTANTS)} assistants{suffix} ===\n')
    if args.dry_run:
        model_success = sum(1 for a in ASSISTANTS if dry_run_model(a))
    else:
        model_success = sum(1 for a in ASSISTANTS if register_model(args.url, args.token, a))

    print(f'\n=== Registering {len(PROMPTS)} prompts{suffix} ===\n')
    if args.dry_run:
        prompt_success = sum(1 for p in PROMPTS if dry_run_prompt(p))
    else:
        prompt_success = sum(1 for p in PROMPTS if register_prompt(args.url, args.token, p))

    print(f'\nFilters: {filter_success}/{len(FILTERS)}{suffix}')
    print(f'Models: {model_success}/{len(ASSISTANTS)}{suffix}')
    print(f'Prompts: {prompt_success}/{len(PROMPTS)}{suffix}')

    return (
        0
        if model_success == len(ASSISTANTS) and prompt_success == len(PROMPTS) and filter_success == len(FILTERS)
        else 1
    )


if __name__ == '__main__':
    sys.exit(main())
