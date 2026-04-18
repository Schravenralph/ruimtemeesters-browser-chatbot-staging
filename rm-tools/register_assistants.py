#!/usr/bin/env python3
"""
Register Ruimtemeesters assistant models and prompt templates with OpenWebUI.

Usage:
    python rm-tools/register_assistants.py --url http://localhost:3333 --token <admin-jwt>
"""

import argparse
import json
import sys

import requests

# Base model to use for all assistants (must exist in OpenWebUI)
BASE_MODEL = 'llama3.1:latest'

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
            ],
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
]


def register_model(base_url: str, token: str, assistant: dict) -> bool:
    """Register or update an assistant model."""
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {
        'id': assistant['id'],
        'name': assistant['name'],
        'base_model_id': assistant['base_model_id'],
        'meta': assistant['meta'],
        'params': assistant['params'],
        'is_active': True,
    }

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


def main():
    parser = argparse.ArgumentParser(description='Register RM assistants and prompts')
    parser.add_argument('--url', default='http://localhost:3333', help='OpenWebUI base URL')
    parser.add_argument('--token', required=True, help='Admin JWT token')
    args = parser.parse_args()

    print(f'=== Registering {len(ASSISTANTS)} assistants ===\n')
    model_success = sum(1 for a in ASSISTANTS if register_model(args.url, args.token, a))

    print(f'\n=== Registering {len(PROMPTS)} prompts ===\n')
    prompt_success = sum(1 for p in PROMPTS if register_prompt(args.url, args.token, p))

    print(f'\nModels: {model_success}/{len(ASSISTANTS)}')
    print(f'Prompts: {prompt_success}/{len(PROMPTS)}')

    return 0 if model_success == len(ASSISTANTS) and prompt_success == len(PROMPTS) else 1


if __name__ == '__main__':
    sys.exit(main())
