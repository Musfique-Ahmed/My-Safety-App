import mysql.connector
import json
from datetime import datetime

CFG = {'host':'localhost','user':'root','password':'','database':'mysafetydb','port':3306}

def apply_migration(cur):
    # Run safe ALTER statements; IF NOT EXISTS requires MySQL 8+, but we'll try and ignore errors
    statements = [
        "ALTER TABLE crime ADD COLUMN IF NOT EXISTS reporter_id VARCHAR(255) NULL AFTER crime_id",
        "ALTER TABLE crime ADD COLUMN IF NOT EXISTS incident_date DATETIME NULL AFTER reporter_id",
        "ALTER TABLE crime ADD COLUMN IF NOT EXISTS evidence_files LONGTEXT NULL AFTER witness_data"
    ]
    for s in statements:
        try:
            cur.execute(s)
            print('Executed:', s)
        except Exception as e:
            # Try the non-IF NOT EXISTS version if IF NOT EXISTS not supported
            if 'IF NOT EXISTS' in s:
                alt = s.replace(' ADD COLUMN IF NOT EXISTS', ' ADD COLUMN')
                try:
                    cur.execute(alt)
                    print('Executed fallback:', alt)
                except Exception as e2:
                    print('Could not run statement:', s, 'error:', e2)
            else:
                print('Could not run statement:', s, 'error:', e)

def insert_test_row(cur):
    location = {'city':'TestCity','area':'UnitArea','district':'Dhaka','latitude':'23.7','longitude':'90.3'}
    crime = {'type':'Assault','description':'DB test insert','incident_date':'2025-10-10T22:00:00'}
    victim = {'name':'DB Victim'}
    criminal = {'name':'DB Criminal'}
    witness = {'name':'DB Witness','phone':'0123456789'}
    evidence = [{'filename':'test.jpg','url':'/static/uploads/test.jpg'}]

    sql = ("INSERT INTO crime (reporter_id, incident_date, location_data, crime_data, victim_data, criminal_data, "
           "weapon_data, witness_data, evidence_files, status, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
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
        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )
    cur.execute(sql, params)
    print('Inserted ID', cur.lastrowid)
    return cur.lastrowid

def fetch_row(cur, row_id):
    cur.execute('SELECT crime_id, reporter_id, incident_date, evidence_files, witness_data, victim_data, crime_data FROM crime WHERE crime_id = %s', (row_id,))
    r = cur.fetchone()
    if not r:
        print('Row not found')
        return
    cols = [d[0] for d in cur.description]
    obj = dict(zip(cols, r))
    # Try to parse JSON fields
    for k in ('evidence_files','witness_data','victim_data','crime_data'):
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
        apply_migration(cur)
        cn.commit()

        row_id = insert_test_row(cur)
        cn.commit()
        # use a new cursor for fetch with dictionary results
        cur2 = cn.cursor()
        fetch_row(cur2, row_id)
        cur.close(); cur2.close(); cn.close()
    except Exception as e:
        print('ERROR', e)

if __name__ == '__main__':
    main()
