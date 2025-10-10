import requests
import json

url = 'http://127.0.0.1:8000/api/crimes'
payload = {
    'location': {'city':'UnitCity','area':'UnitArea','district':'Dhaka','latitude':'23.7','longitude':'90.3'},
    'crime': {'type':'Assault','description':'Automated test with new fields','incident_date':'2025-10-10T22:00:00'},
    'victim': {'name':'Unit Victim'},
    'criminal': {'name':'Unit Criminal'},
    'weapon': None,
    'witness': {'name':'Unit Witness','phone':'0123456789'},
    'reporter_id': 'tester-1',
    'incident_date': '2025-10-10 22:00:00',
    'evidence_files': [{'filename':'e1.jpg','url':'/static/uploads/e1.jpg'}]
}

try:
    r = requests.post(url, json=payload, timeout=10)
    print('status', r.status_code)
    try:
        print(r.json())
    except Exception:
        print('response text', r.text)
except Exception as e:
    print('request error', e)

# Fetch recent crimes to verify data stored
try:
    g = requests.get('http://127.0.0.1:8000/api/crimes?limit=5', timeout=10)
    print('\nGET /api/crimes status', g.status_code)
    try:
        data = g.json()
        for c in data.get('crimes', []):
            print('crime_id', c.get('crime_id'), 'reporter_id', c.get('reporter_id'), 'incident_date', c.get('incident_date'), 'evidence_files', c.get('evidence_files'))
    except Exception:
        print('GET response text', g.text)
except Exception as e:
    print('GET request error', e)
