#!/usr/bin/env python3
"""
Empty the database completely (all data removed; tables/schema kept).

Uses Django's flush: deletes every row in every table. Works with both
SQLite and PostgreSQL. Does not drop tables or migrations.

Usage (from project root, with venv activated):

  PRODUCTION (intended use):
    # Load production env (e.g. DATABASE_URL) then run with --production
    export $(grep -v '^#' .env.production | xargs)   # if you use .env.production
    python scripts/empty_database.py --production    # asks for confirmation
    python scripts/empty_database.py --production --yes

  LOCAL (default):
    python scripts/empty_database.py
    python scripts/empty_database.py --yes
"""

import argparse
import os
import sys

# Run from project root (parent of scripts/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(
        description="Empty the database completely (all data removed)."
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Use production settings (store.settings_production). Requires production DATABASE_URL etc.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    if args.production:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "store.settings_production")
        os.environ["DJANGO_ENV"] = "production"
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "store.settings")

    import django

    django.setup()
    from django.conf import settings
    from django.core.management import call_command

    db_engine = settings.DATABASES["default"]["ENGINE"]
    db_name = settings.DATABASES["default"].get("NAME", "?")
    db_host = settings.DATABASES["default"].get("HOST", "?")
    if "sqlite" in db_engine:
        db_label = str(db_name)
    else:
        db_label = f"{db_name} @ {db_host}"

    if not args.yes:
        if args.production:
            print("*** PRODUCTION DATABASE ***")
            print(f"Target: {db_label}")
            print("This will DELETE ALL DATA on PRODUCTION. Schema will remain.")
            try:
                answer = input('Type "empty production" to continue: ').strip().lower()
            except EOFError:
                answer = ""
            if answer != "empty production":
                print("Aborted.")
                sys.exit(1)
        else:
            print(f"Database: {db_label}")
            print("This will DELETE ALL DATA (all tables will be emptied). Schema will remain.")
            try:
                answer = input("Type 'yes' to continue: ").strip().lower()
            except EOFError:
                answer = ""
            if answer != "yes":
                print("Aborted.")
                sys.exit(1)

    call_command("flush", verbosity=2, interactive=False)
    print("Database emptied successfully.")

    # Verify: count rows in all Django-managed tables
    from django.apps import apps

    non_empty = []
    for model in apps.get_models(include_auto_created=True, include_swapped=True):
        try:
            n = model.objects.count()
            if n > 0:
                non_empty.append((model._meta.label, n))
        except Exception:
            pass
    if non_empty:
        print("Warning: some tables still have rows:")
        for label, n in non_empty:
            print(f"  {label}: {n}")
        sys.exit(1)
    print("Verified: all tables are empty.")


if __name__ == "__main__":
    main()
