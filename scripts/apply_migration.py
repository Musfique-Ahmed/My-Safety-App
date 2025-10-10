import mysql.connector
import os
import sys

MIGRATION_FILE = os.path.join(os.path.dirname(__file__), '..', 'migrations', '001_add_crime_fields.sql')

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'mysafetydb',
    'port': 3306
}

def apply_migration():
    if not os.path.exists(MIGRATION_FILE):
        print('Migration file not found:', MIGRATION_FILE)
        return 2

    with open(MIGRATION_FILE, 'r', encoding='utf-8') as f:
        sql = f.read()

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        # MySQL connector can't execute multiple statements by default; split by semicolon
        stmts = [s.strip() for s in sql.split(';') if s.strip()]
        for s in stmts:
            print('Executing:', s[:80])
            cur.execute(s)
        conn.commit()
        cur.close()
        conn.close()
        print('Migration applied successfully.')
        return 0
    except Exception as e:
        print('Migration failed:', e)
        return 1

if __name__ == '__main__':
    sys.exit(apply_migration())
