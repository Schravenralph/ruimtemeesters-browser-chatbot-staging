#!/usr/bin/env python3
"""
Register all Ruimtemeesters tools with OpenWebUI.

Usage:
    python rm-tools/register_tools.py --url http://localhost:3333 --token <admin-jwt>

The admin JWT can be obtained from the browser after logging in (localStorage.token
or the 'token' cookie).
"""

import argparse
import os
import re
import sys

import requests

TOOL_FILES = [
    ("rm_databank", "Ruimtemeesters Databank", "rm-tools/databank.py"),
    ("rm_geoportaal", "Ruimtemeesters Geoportaal", "rm-tools/geoportaal.py"),
    ("rm_tsa", "Ruimtemeesters TSA", "rm-tools/tsa.py"),
    ("rm_dashboarding", "Ruimtemeesters Dashboarding", "rm-tools/dashboarding.py"),
    ("rm_riens", "Ruimtemeesters Sales Viewer", "rm-tools/riens.py"),
    ("rm_sales_predictor", "Ruimtemeesters Sales Predictor", "rm-tools/sales_predictor.py"),
    ("rm_opdrachten", "Ruimtemeesters Opdrachten Scanner", "rm-tools/opdrachten.py"),
]


def extract_description(content: str) -> str:
    """Extract description from tool frontmatter."""
    match = re.search(r"description:\s*(.+)", content)
    return match.group(1).strip() if match else ""


def register_tool(base_url: str, token: str, tool_id: str, name: str, filepath: str) -> bool:
    """Register or update a single tool."""
    with open(filepath, "r") as f:
        content = f.read()

    description = extract_description(content)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "id": tool_id,
        "name": name,
        "content": content,
        "meta": {
            "description": description,
        },
    }

    # Try to create first
    resp = requests.post(f"{base_url}/api/v1/tools/create", headers=headers, json=payload)

    if resp.status_code == 200:
        print(f"  + Registered: {name} ({tool_id})")
        return True

    if resp.status_code == 400 and "already registered" in resp.text.lower():
        # Update existing tool
        resp = requests.post(
            f"{base_url}/api/v1/tools/id/{tool_id}/update",
            headers=headers,
            json=payload,
        )
        if resp.status_code == 200:
            print(f"  ~ Updated: {name} ({tool_id})")
            return True

    print(f"  x Failed: {name} -- {resp.status_code}: {resp.text[:200]}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Register RM tools with OpenWebUI")
    parser.add_argument("--url", default="http://localhost:3333", help="OpenWebUI base URL")
    parser.add_argument("--token", required=True, help="Admin JWT token")
    args = parser.parse_args()

    print(f"Registering {len(TOOL_FILES)} tools at {args.url}...\n")

    success = 0
    for tool_id, name, filepath in TOOL_FILES:
        if not os.path.exists(filepath):
            print(f"  x File not found: {filepath}")
            continue
        if register_tool(args.url, args.token, tool_id, name, filepath):
            success += 1

    print(f"\n{success}/{len(TOOL_FILES)} tools registered successfully.")
    return 0 if success == len(TOOL_FILES) else 1


if __name__ == "__main__":
    sys.exit(main())
