#!/usr/bin/env python
import sys
import time
from urllib.parse import urlparse

import psycopg

def wait_for_db():
    """
    Waits for the database to be ready by attempting to connect to it
    in a loop.
    """
    if len(sys.argv) < 2:
        print("Usage: python wait-for-db.py <DATABASE_URL>", file=sys.stderr)
        sys.exit(1)

    db_url_str = sys.argv[1]
    url = urlparse(db_url_str)

    conn_params = {
        "host": url.hostname or "localhost",
        "port": url.port or 5432,
        "user": url.username,
        "password": url.password,
        "dbname": url.path[1:] if url.path else "",
    }

    max_attempts = 60
    for attempt in range(1, max_attempts + 1):
        try:
            with psycopg.connect(**conn_params) as conn:
                conn.close()
            print(f"Database ready after {attempt} attempts.")
            return
        except psycopg.OperationalError as e:
            print(f"Attempt {attempt}/{max_attempts}: Database not ready yet - {e}")
            time.sleep(1)

    print(f"Database not ready after {max_attempts} attempts. Exiting.")
    sys.exit(1)

if __name__ == "__main__":
    wait_for_db()
