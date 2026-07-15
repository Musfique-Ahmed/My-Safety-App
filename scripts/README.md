# Scripts

Operational + end-to-end scripts. Run with the project root on PYTHONPATH:

```
# DB-side scripts (no app needed; talk to MySQL directly)
python scripts/db/apply_migration.py
python scripts/db/run_migration_and_db_test.py
python scripts/db/create_role_credentials.py
python scripts/db/test_db.py

# End-to-end scripts (HTTP only — start uvicorn in another terminal first)
python scripts/e2e/e2e_smoke.py
python scripts/e2e/e2e_chat.py
python scripts/e2e/browser_smoke.py
python scripts/e2e/per_role_browser_test.py
python scripts/e2e/test_post_crime.py
```

Most of these read from `CREDENTIALS.txt` for role credentials and use
`BASE = http://127.0.0.1:8000` for the API. Override with `BASE` env var.
