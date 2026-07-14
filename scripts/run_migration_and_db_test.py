"""Apply all migrations in migrations/ in alphabetical order, then run a smoke test insert.

This replaces the previous one-shot migration runner. After migrations 001-004 are
applied, status_history, emergency_alerts, police_station, chat_messages,
criminal_sightings, case_assignments, and user_complaints will exist and the
columns referenced by code will be in place.
"""
import glob
import os
import json
from datetime import datetime

import mysql.connector

CFG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'mysafetydb',
    'port': 3306,
}

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'migrations')


def split_statements(sql: str):
    """Split a SQL script on top-level semicolons. Naive but adequate for these files."""
    out, buf = [], []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('--'):
            continue
        buf.append(line)
        if stripped.endswith(';'):
            out.append('\n'.join(buf).rstrip(';').strip())
            buf = []
    if buf:
        leftover = '\n'.join(buf).strip().rstrip(';').strip()
        if leftover:
            out.append(leftover)
    return out


def apply_migrations(cur) -> None:
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, '*.sql')))
    for path in files:
        name = os.path.basename(path)
        print(f'--- applying {name} ---')
        with open(path, 'r', encoding='utf-8') as f:
            sql = f.read()
        for stmt in split_statements(sql):
            try:
                cur.execute(stmt)
                print(f'  ok: {stmt.splitlines()[0][:80]}')
            except mysql.connector.Error as e:
                # Allow "already exists" / "duplicate column" / "duplicate key"
                msg = str(e).lower()
                if any(tok in msg for tok in ('already exists', 'duplicate', '1060', '1061', '1091')):
                    print(f'  skip (already applied): {e}')
                    continue
                print(f'  FAIL: {stmt.splitlines()[0][:80]}\n    {e}')
                raise


def insert_test_row(cur):
    location = {'city': 'TestCity', 'area': 'UnitArea', 'district': 'Dhaka',
                'latitude': '23.7', 'longitude': '90.3'}
    crime = {'type': 'Assault', 'description': 'DB test insert',
             'incident_date': '2025-10-10T22:00:00'}
    victim = {'name': 'DB Victim'}
    criminal = {'name': 'DB Criminal'}
    witness = {'name': 'DB Witness', 'phone': '0123456789'}
    evidence = [{'filename': 'test.jpg', 'url': '/static/uploads/test.jpg'}]

    sql = ("INSERT INTO crime (reporter_id, incident_date, location_data, crime_data, "
           "victim_data, criminal_data, weapon_data, witness_data, evidence_files, "
           "status, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
    params = (
        'db-tester',
        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        json.dumps(location),
        json.dumps(crime),
        json.dumps(victim),
        json.dumps(criminal),
        None,
        json.dumps(witness),
        json.dumps(evidence),
        'Pending',
        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
    )
    cur.execute(sql, params)
    print('Inserted ID', cur.lastrowid)
    return cur.lastrowid


def fetch_row(cur, row_id):
    cur.execute(
        'SELECT crime_id, reporter_id, incident_date, evidence_files, '
        'witness_data, victim_data, crime_data FROM crime WHERE crime_id = %s',
        (row_id,),
    )
    r = cur.fetchone()
    if not r:
        print('Row not found')
        return
    cols = [d[0] for d in cur.description]
    obj = dict(zip(cols, r))
    for k in ('evidence_files', 'witness_data', 'victim_data', 'crime_data'):
        if obj.get(k):
            try:
                obj[k] = json.loads(obj[k])
            except Exception:
                pass
    print('Fetched row:')
    print(json.dumps(obj, indent=2, default=str))


def main():
    try:
        cn = mysql.connector.connect(**CFG)
        cur = cn.cursor()
        apply_migrations(cur)
        cn.commit()

        row_id = insert_test_row(cur)
        cn.commit()
        cur2 = cn.cursor()
        fetch_row(cur2, row_id)
        cur.close()
        cur2.close()
        cn.close()
    except Exception as e:
        print('ERROR', e)


if __name__ == '__main__':
    main()