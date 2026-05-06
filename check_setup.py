#!/usr/bin/env python3
"""Validates that wb-logistics-toolkit is correctly configured.

Run: python check_setup.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_env_file() -> tuple[bool, str]:
    if not Path(".env").exists():
        return False, ".env file not found. Copy .env.example to .env and fill in your credentials."
    return True, ".env found"


def check_credentials() -> tuple[bool, str]:
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if not Path(creds_path).exists():
        return False, (
            f"Google credentials file not found at '{creds_path}'. "
            "Download your Service Account JSON from Google Cloud Console "
            "and set GOOGLE_CREDENTIALS_PATH in .env."
        )
    return True, f"Google credentials found at '{creds_path}'"


def check_credentials_not_staged() -> tuple[bool, str]:
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        staged = result.stdout.strip().splitlines()
        if creds_path in staged:
            return False, (
                f"DANGER: '{creds_path}' is staged for commit! "
                f"Run: git reset HEAD {creds_path}"
            )
    except Exception:
        pass
    return True, f"'{creds_path}' not staged"


def check_cabinets_yaml() -> tuple[bool, str]:
    if not Path("cabinets.yaml").exists():
        return False, "cabinets.yaml not found. Copy the example and configure your cabinets."
    return True, "cabinets.yaml found"


def check_wb_tokens() -> tuple[bool, str]:
    import yaml
    if not Path("cabinets.yaml").exists():
        return False, "cabinets.yaml missing, cannot check WB tokens"
    try:
        with open("cabinets.yaml") as f:
            data = yaml.safe_load(f)
        if not data or "cabinets" not in data:
            return False, "cabinets.yaml has invalid structure: missing 'cabinets' key"
        missing = []
        for cab in data["cabinets"]:
            name = cab["name"]
            key = f"WB_TOKEN_{name.upper()}"
            if not os.environ.get(key):
                missing.append(key)
        if missing:
            return False, f"Missing WB tokens in .env: {', '.join(missing)}"
        return True, "All WB tokens found"
    except (KeyError, TypeError) as e:
        return False, f"cabinets.yaml has invalid structure: {e}"
    except Exception as e:
        return False, f"Error reading cabinets.yaml: {e}"


def check_supabase() -> tuple[bool, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return False, "SUPABASE_URL or SUPABASE_KEY missing in .env"
    try:
        from supabase import create_client
        client = create_client(url, key)
        client.table("wb_coeff_table").select("id").limit(1).execute()
        return True, "Supabase connection OK, wb_coeff_table accessible"
    except Exception as e:
        return False, f"Supabase connection failed: {e}"


def check_warehouse_status_yaml() -> tuple[bool, str]:
    if not Path("warehouse_status.yaml").exists():
        return False, "warehouse_status.yaml not found"
    return True, "warehouse_status.yaml found"


CHECKS = [
    ("📄 .env file", check_env_file),
    ("🔑 Google credentials", check_credentials),
    ("🚫 Credentials not staged", check_credentials_not_staged),
    ("📋 cabinets.yaml", check_cabinets_yaml),
    ("🏭 warehouse_status.yaml", check_warehouse_status_yaml),
    ("🔐 WB API tokens", check_wb_tokens),
    ("🗄️  Supabase connection", check_supabase),
]


def main() -> int:
    print("\n=== WB Logistics Toolkit — Setup Check ===\n")
    all_ok = True
    for label, check_fn in CHECKS:
        ok, msg = check_fn()
        icon = "✅" if ok else "❌"
        print(f"{icon}  {label}: {msg}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("✅ All checks passed. Ready to run!")
        return 0
    else:
        print("❌ Some checks failed. Fix the issues above before running.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
