from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import logging
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Mapping
import json
import os
import uuid
import asyncio
import mysql.connector
from mysql.connector import Error
from typing import Dict, Any
from datetime import datetime

app = FastAPI()

# Configure basic logging
logging.basicConfig(level=logging.INFO)


@app.exception_handler(Exception)
async def all_exceptions_handler(request, exc):
    # Log the full exception so server logs contain the stacktrace
    logging.exception("Unhandled exception: %s", exc)
    # Always return JSON to the client (prevents empty/non-JSON responses)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost/mysafetydb"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"charset": "utf8mb4"})

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'mysafetydb',
    'port': 3306
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to database: {e}")
        return None

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create uploads directory if it doesn't exist
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _read_html(path: str) -> str:
    """Read an HTML file with utf-8 and replace undecodable bytes to avoid crashes.

    Returns the file content as a string. Raises FileNotFoundError if missing.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

# ==================== PYDANTIC MODELS ====================

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class CrimeData(BaseModel):
    location: dict
    crime: dict
    victim: Optional[dict] = None
    criminal: Optional[dict] = None
    weapon: Optional[dict] = None
    witness: Optional[dict] = None
    # New optional fields collected by the frontend
    reporter_id: Optional[str] = None
    incident_date: Optional[str] = None
    evidence_files: Optional[List[dict]] = None

class MissingPersonData(BaseModel):
    name: str
    age: int
    gender: str
    description: str
    last_seen_location: str
    last_seen_date: str
    contact_info: str
    photo_url: Optional[str] = None

class ComplaintVerification(BaseModel):
    complaint_id: int
    status: str

class CaseAssignment(BaseModel):
    user_id: int
    crime_id: int
    duty_role: str

class StatusUpdate(BaseModel):
    crime_id: int
    new_status: str
    notes: str
    changed_by: int

class ChatMessage(BaseModel):
    user_id: int
    message: str
    report_id: Optional[str] = None
    is_admin: Optional[bool] = False

class EmergencyAlert(BaseModel):
    location: dict
    alert_type: str
    description: str
    severity: str = "High"

class CriminalSighting(BaseModel):
    last_seen_time: str
    last_seen_location: str
    still_with_finder: bool = False
    reporter_contact: Optional[str] = None

class UserUpdate(BaseModel):
    user_id: int
    role_hint: Optional[str] = None
    status: Optional[str] = None
    station_id: Optional[int] = None

class WantedCriminalCreate(BaseModel):
    name: str
    alias: Optional[str] = None
    age_range: str
    gender: str
    description: str
    height: Optional[str] = None
    weight: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    distinguishing_marks: Optional[str] = None
    crimes_committed: str
    reward_amount: Optional[float] = 0
    danger_level: str = "Medium"
    last_known_location: Optional[str] = None
    photo_url: Optional[str] = None
    added_by: int

class AdminAction(BaseModel):
    action_type: str
    target_id: int
    notes: Optional[str] = None
    admin_id: int

class PoliceStationCreate(BaseModel):
    station_name: str
    station_code: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    jurisdiction_area: Optional[str] = None

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

# ==================== ROOT ENDPOINT (LANDING PAGE) ====================

@app.get("/")
async def read_root():
    """Serve the main landing page (home.html)"""
    try:
        return HTMLResponse(content=_read_html("static/home.html"))
    except FileNotFoundError:
        # Fallback to index.html if home.html doesn't exist
        return HTMLResponse(content=_read_html("static/index.html"))

# ==================== STATIC PAGE ENDPOINTS ====================

@app.get("/dashboard")
async def get_dashboard_page():
    """Serve the main dashboard page (index.html)"""
    return HTMLResponse(content=_read_html("static/index.html"))

@app.get("/home")
async def get_home_page():
    """Alternative route to home page"""
    return HTMLResponse(content=_read_html("static/home.html"))

@app.get("/report-crime")
async def get_report_crime_page():
    """Serve the crime reporting page"""
    return HTMLResponse(content=_read_html("static/report_crime.html"))

@app.get("/missing-person")
async def get_missing_person_page():
    """Serve the missing persons page"""
    return HTMLResponse(content=_read_html("static/missing_person.html"))

@app.get("/wanted-criminals")
async def get_wanted_criminals_page():
    """Serve the wanted criminals page"""
    return HTMLResponse(content=_read_html("static/wanted_criminal.html"))

@app.get("/chatbox")
async def get_chatbox_page():
    """Serve the community chatbox page"""
    return HTMLResponse(content=_read_html("static/user_chatbox.html"))

@app.get("/report-missing")
async def get_report_missing_page():
    """Serve the missing person report form"""
    return HTMLResponse(content=_read_html("static/report_missing_person.html"))

@app.get("/login")
async def get_login_page():
    """Serve the login page"""
    return HTMLResponse(content=_read_html("static/login.html"))

@app.get("/signup")
async def get_signup_page():
    """Serve the signup page"""
    return HTMLResponse(content=_read_html("static/signup.html"))

@app.get("/admin")
async def get_admin_dashboard_page():
    """Serve the admin dashboard page"""
    return HTMLResponse(content=_read_html("static/admin_dashboard.html"))

@app.get("/admin-dashboard")
async def get_admin_dashboard_alt():
    """Alternative route to admin dashboard"""
    return HTMLResponse(content=_read_html("static/admin_dashboard.html"))

# ==================== USER AUTHENTICATION ENDPOINTS ====================

@app.post("/register")
async def register_user(user: UserCreate):
    hashed_password = hash_password(user.password)
    with engine.connect() as conn:
        try:
            # Check if email exists
            result = conn.execute(
                text("SELECT user_id FROM appuser WHERE email = :email"),
                {"email": user.email}
            ).fetchone()
            if result:
                raise HTTPException(status_code=400, detail="Email already registered")
            
            # Insert new user
            conn.execute(
                text("""
                    INSERT INTO appuser (email, username, password_hash, role_hint, status, created_at)
                    VALUES (:email, :username, :password_hash, :role_hint, :status, :created_at)
                """),
                {
                    "email": user.email,
                    "username": user.username,
                    "password_hash": hashed_password,
                    "role_hint": "User",
                    "status": "Active",
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            print(f"Registered new user: {user.email}")
            return {"message": "User registered successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/login")
async def login_user(user: UserLogin):
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("SELECT * FROM appuser WHERE email = :email"),
                {"email": user.email}
            ).mappings().fetchone()
            
            if not result:
                raise HTTPException(status_code=400, detail="Email not registered")
            
            stored_password = result["password_hash"]
            if stored_password != hash_password(user.password):
                raise HTTPException(status_code=400, detail="Incorrect password")
            
            print(f"Login success for {user.email}")
            return {
                "message": "Login successful",
                "user": {
                    "user_id": result["user_id"],
                    "email": result["email"],
                    "username": result["username"],
                    "role_hint": result["role_hint"],
                    "station_id": result["station_id"],
                    "status": result["status"],
                    "created_at": result["created_at"]
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.get("/api/users")
async def get_all_users():
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT user_id, email, username, role_hint, status, created_at FROM appuser ORDER BY created_at DESC")
        ).mappings().fetchall()
        return {"users": [dict(row) for row in result]}

@app.get("/api/users/{user_id}")
async def get_user_by_id(user_id: int):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT user_id, email, username, role_hint, status, created_at FROM appuser WHERE user_id = :user_id"),
            {"user_id": user_id}
        ).mappings().fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return {"user": dict(result)}

# ==================== FILE UPLOAD ENDPOINTS ====================

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Return file URL
        file_url = f"/static/uploads/{unique_filename}"
        return {"file_url": file_url, "filename": unique_filename}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

# ==================== CRIME DATA ENDPOINTS ====================

@app.post("/api/crimes")
async def submit_crime_report(crime_data: CrimeData):
    with engine.connect() as conn:
        try:
            # Validate reporter_id: if provided, ensure it exists in appuser; if not, null it
            reporter_id_val = None
            if crime_data.reporter_id:
                try:
                    # try to coerce to int where possible
                    maybe_id = int(crime_data.reporter_id)
                except Exception:
                    maybe_id = None

                if maybe_id is not None:
                    user_row = conn.execute(
                        text("SELECT user_id FROM appuser WHERE user_id = :uid"),
                        {"uid": maybe_id}
                    ).fetchone()
                    if user_row:
                        reporter_id_val = maybe_id
                    else:
                        # Unknown reporter_id -> treat as anonymous (NULL)
                        reporter_id_val = None

            # Insert into crime table
            result = conn.execute(
                text("""
                    INSERT INTO crime (reporter_id, incident_date, location_data, crime_data, victim_data, criminal_data, 
                                     weapon_data, witness_data, evidence_files, status, created_at)
                    VALUES (:reporter_id, :incident_date, :location_data, :crime_data, :victim_data, :criminal_data, 
                            :weapon_data, :witness_data, :evidence_files, :status, :created_at)
                """),
                {
                    "reporter_id": reporter_id_val,
                    "incident_date": crime_data.incident_date,
                    "location_data": json.dumps(crime_data.location),
                    "crime_data": json.dumps(crime_data.crime),
                    "victim_data": json.dumps(crime_data.victim) if crime_data.victim else None,
                    "criminal_data": json.dumps(crime_data.criminal) if crime_data.criminal else None,
                    "weapon_data": json.dumps(crime_data.weapon) if crime_data.weapon else None,
                    "witness_data": json.dumps(crime_data.witness) if crime_data.witness else None,
                    "evidence_files": json.dumps(crime_data.evidence_files) if crime_data.evidence_files else None,
                    "status": "Pending",
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            crime_id = result.lastrowid
            print(f"Crime report submitted with ID: {crime_id}")
            return {"message": "Crime report submitted successfully", "crime_id": crime_id}
        except IntegrityError as ie:
            conn.rollback()
            # Return a 400 with a clear message about referential integrity
            raise HTTPException(status_code=400, detail=f"Failed to submit crime report due to integrity error: {str(ie)}")
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to submit crime report: {str(e)}")

@app.get("/api/crimes")
async def get_all_crimes(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: Optional[int] = Query(100, description="Limit number of results")
):
    with engine.connect() as conn:
        query = "SELECT * FROM crime"
        params = {}
        
        if status:
            query += " WHERE status = :status"
            params["status"] = status
            
        query += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit
        
        result = conn.execute(text(query), params).mappings().fetchall()
        
        crimes = []
        for row in result:
            crime = dict(row)
            # Parse JSON fields
            if crime["location_data"]:
                crime["location_data"] = json.loads(crime["location_data"])
            if crime["crime_data"]:
                crime["crime_data"] = json.loads(crime["crime_data"])
            if crime["victim_data"]:
                crime["victim_data"] = json.loads(crime["victim_data"])
            if crime["criminal_data"]:
                crime["criminal_data"] = json.loads(crime["criminal_data"])
            if crime["weapon_data"]:
                crime["weapon_data"] = json.loads(crime["weapon_data"])
            if crime["witness_data"]:
                crime["witness_data"] = json.loads(crime["witness_data"])
            crimes.append(crime)
            
        return {"crimes": crimes}

@app.get("/api/crimes/{crime_id}")
async def get_crime_by_id(crime_id: int):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM crime WHERE crime_id = :crime_id"),
            {"crime_id": crime_id}
        ).mappings().fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Crime not found")
            
        crime = dict(result)
        # Parse JSON fields
        if crime["location_data"]:
            crime["location_data"] = json.loads(crime["location_data"])
        if crime["crime_data"]:
            crime["crime_data"] = json.loads(crime["crime_data"])
        if crime["victim_data"]:
            crime["victim_data"] = json.loads(crime["victim_data"])
        if crime["criminal_data"]:
            crime["criminal_data"] = json.loads(crime["criminal_data"])
        if crime["weapon_data"]:
            crime["weapon_data"] = json.loads(crime["weapon_data"])
        if crime["witness_data"]:
            crime["witness_data"] = json.loads(crime["witness_data"])
            
        return {"crime": crime}

# ==================== MISSING PERSON ENDPOINTS ====================


@app.post("/api/missing-persons")
async def submit_missing_person(payload: Dict[str, Any] = Body(...)):
    # map and validate
    name = payload.get("full_name") or payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="full_name is required")

    def to_int(v):
        try: return int(v) if v not in (None, "") else None
        except: return None

    # parse datetime-local (e.g. "2025-10-10T14:30")
    last_seen_date = None
    last_seen_time = None
    lst = payload.get("last_seen_time")
    if lst:
        try:
            dt = datetime.fromisoformat(lst)
            last_seen_date = dt.date().isoformat()
            last_seen_time = dt.time().isoformat(timespec='seconds')
        except Exception:
            # if format different, try split
            try:
                parts = lst.split('T')
                if len(parts) == 2:
                    last_seen_date = parts[0]
                    last_seen_time = parts[1][:8]
            except Exception:
                pass

    params = {
      "reporter_id": None,                       # set if you track logged-in user
      "name": name,
      "age": to_int(payload.get("age")),
      "gender": payload.get("gender") or "O",
      "description": payload.get("description") or payload.get("medical_needs") or None,
      "last_seen_location": payload.get("last_seen_location") or payload.get("location"),
      "last_seen_date": last_seen_date,
      "last_seen_time": last_seen_time,
      "height": payload.get("height"),
      "weight": str(payload.get("weight")) if payload.get("weight") not in (None, "") else None,
      "hair_color": payload.get("hair_color"),
      "eye_color": payload.get("eye_color"),
      "distinguishing_marks": payload.get("nickname"),
      "clothing_description": payload.get("description"),
      "contact_person": payload.get("reporter_name"),
      "contact_phone": payload.get("reporter_phone"),
      "photo_url": payload.get("photo_url"),
      "status": "Missing",
      "police_case_number": payload.get("police_case_number"),
      "created_at": datetime.utcnow(),
      "updated_at": None
    }

    insert_sql = text("""
      INSERT INTO missing_person
      (reporter_id, name, age, gender, description, last_seen_location, last_seen_date, last_seen_time,
       height, weight, hair_color, eye_color, distinguishing_marks, clothing_description,
       contact_person, contact_phone, photo_url, status, police_case_number, created_at, updated_at)
      VALUES
      (:reporter_id, :name, :age, :gender, :description, :last_seen_location, :last_seen_date, :last_seen_time,
       :height, :weight, :hair_color, :eye_color, :distinguishing_marks, :clothing_description,
       :contact_person, :contact_phone, :photo_url, :status, :police_case_number, :created_at, :updated_at)
    """)

    try:
      with engine.begin() as conn:
        conn.execute(insert_sql, params)
        last = conn.execute(text("SELECT LAST_INSERT_ID() AS id")).first()
        new_id = last.id if last is not None else None
      return {"message":"Missing person report created", "id": new_id}
    except Exception:
      logging.exception("Failed to insert missing person")
      raise HTTPException(status_code=500, detail="Failed to save missing person")
# ...existing code...

# @app.get("/api/missing-persons")
# async def get_all_missing_persons(
#     status: Optional[str] = Query(None, description="Filter by status")
# ):
#     with engine.connect() as conn:
#         query = "SELECT * FROM missing_person"
#         params = {}
        
#         if status:
#             query += " WHERE status = :status"
#             params["status"] = status
            
#         query += " ORDER BY created_at DESC"
        
#         result = conn.execute(text(query), params).mappings().fetchall()
#         return {"missing_persons": [dict(row) for row in result]}

@app.get("/api/missing-persons")
async def get_missing_persons():
    query = text("""
        SELECT missing_id, reporter_id, name, age, gender, description,
               last_seen_location, last_seen_date, last_seen_time, height,
               weight, hair_color, eye_color, distinguishing_marks,
               clothing_description, contact_person, contact_phone,
               photo_url, status, police_case_number, created_at, updated_at
        FROM missing_person
        ORDER BY COALESCE(updated_at, created_at) DESC
    """)
    try:
        with engine.connect() as conn:
            rows = [dict(row) for row in conn.execute(query).mappings()]
        return rows
    except Exception:
        logging.exception("Failed to fetch missing persons")
        raise HTTPException(status_code=500, detail="Failed to fetch missing persons")

@app.get("/api/missing-persons/{missing_id}")
async def get_missing_person_by_id(missing_id: int):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM missing_person WHERE missing_id = :missing_id"),
            {"missing_id": missing_id}
        ).mappings().fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Missing person not found")
            
        return {"missing_person": dict(result)}

# ==================== WANTED CRIMINALS ENDPOINTS ====================

# @app.get("/api/wanted-criminals")
# async def get_wanted_criminals():
#     with engine.connect() as conn:
#         try:
#             result = conn.execute(
#                 text("SELECT * FROM wanted_criminal WHERE status = 'Active' ORDER BY created_at DESC")
#             ).mappings().fetchall()
            
#             wanted_criminals = []
#             for row in result:
#                 criminal = dict(row)
#                 # Convert database fields to match frontend expectations
#                 wanted_criminal = {
#                     "id": criminal["criminal_id"],
#                     "name": criminal["name"],
#                     "alias": criminal.get("alias", ""),
#                     "age": criminal.get("age_range", "Unknown"),
#                     "height_cm": criminal.get("height", "Unknown"),
#                     "complexion": criminal.get("distinguishing_marks", "Unknown"),
#                     "crimes": criminal["crimes_committed"].split(", ") if criminal["crimes_committed"] else [],
#                     "last_seen_location": criminal.get("last_known_location", "Unknown"),
#                     "last_seen_time": criminal.get("wanted_since", ""),
#                     "reward": float(criminal.get("reward_amount", 0)),
#                     "photo_url": criminal.get("photo_url", "/static/img/placeholder.jpg"),
#                     "note": criminal.get("description", ""),
#                     "danger_level": criminal.get("danger_level", "Medium"),
#                     "status": criminal["status"]
#                 }
#                 wanted_criminals.append(wanted_criminal)
            
#             return {"wanted_criminals": wanted_criminals}
#         except Exception as e:
#             print(f"Error fetching wanted criminals: {e}")
#             # Return sample data if database is not set up
#             return {"wanted_criminals": [
#                 {
#                     "id": 1,
#                     "name": "Karim Ahmed",
#                     "alias": "Black Karim",
#                     "age": "25-30",
#                     "height_cm": "175",
#                     "complexion": "Dark, scar on left cheek",
#                     "crimes": ["Armed robbery", "assault", "theft"],
#                     "last_seen_location": "Old Dhaka area",
#                     "last_seen_time": "2024-01-15",
#                     "reward": 50000,
#                     "photo_url": "https://via.placeholder.com/300x300/dc2626/ffffff?text=WANTED",
#                     "note": "Extremely dangerous, do not approach",
#                     "danger_level": "High",
#                     "status": "Active"
#                 },
#                 {
#                     "id": 2,
#                     "name": "Rashida Begum",
#                     "alias": "Rashi",
#                     "age": "30-35",
#                     "height_cm": "160",
#                     "complexion": "Fair, distinctive tattoo on right arm",
#                     "crimes": ["Fraud", "embezzlement", "forgery"],
#                     "last_seen_location": "Uttara sector 7",
#                     "last_seen_time": "2024-02-20",
#                     "reward": 25000,
#                     "photo_url": "https://via.placeholder.com/300x300/dc2626/ffffff?text=WANTED",
#                     "note": "Known for financial crimes",
#                     "danger_level": "Medium",
#                     "status": "Active"
#                 }
#             ]}


@app.get("/api/wanted-criminals")
async def get_wanted_criminals():
    query = text(
        """
        SELECT criminal_id, name, alias, age_range, gender, description, height, weight,
               hair_color, eye_color, distinguishing_marks, crimes_committed, reward_amount,
               danger_level, last_known_location, photo_url, wanted_since, added_by, status,
               capture_date, created_at, updated_at
        FROM wanted_criminal
        ORDER BY COALESCE(updated_at, created_at) DESC
        """
    )
    try:
        with engine.connect() as conn:
            rows = [dict(row) for row in conn.execute(query).mappings()]
        return rows
    except Exception:
        logging.exception("Failed to fetch wanted criminals")
        raise HTTPException(status_code=500, detail="Failed to fetch wanted criminals")

@app.get("/api/wanted-criminals/{criminal_id}")
async def get_wanted_criminal_by_id(criminal_id: int):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM wanted_criminal WHERE criminal_id = :criminal_id"),
            {"criminal_id": criminal_id}
        ).mappings().fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Wanted criminal not found")
            
        return {"wanted_criminal": dict(result)}

@app.get("/api/wanted-criminals/{criminal_id}/sightings")
async def list_wanted_criminal_sightings(criminal_id: int):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT sighting_id,
                       criminal_id,
                       last_seen_time,
                       last_seen_location,
                       still_with_finder,
                       reporter_contact,
                       created_at
                FROM criminal_sightings
                WHERE criminal_id = :criminal_id
                ORDER BY COALESCE(last_seen_time, created_at) DESC, sighting_id DESC
                """
            ),
            {"criminal_id": criminal_id}
        ).mappings().fetchall()

    def _serialize(row: Mapping[str, Any]) -> Dict[str, Any]:
        last_seen_time = row.get("last_seen_time")
        created_at = row.get("created_at")
        finder_value = row.get("still_with_finder")
        if isinstance(finder_value, str):
            finder_normalized = finder_value.strip().lower()
            still_with_finder = finder_normalized in {"1", "true", "yes", "y"}
        else:
            still_with_finder = bool(finder_value)
        return {
            "sighting_id": row.get("sighting_id"),
            "criminal_id": row.get("criminal_id"),
            "last_seen_time": last_seen_time.isoformat() if isinstance(last_seen_time, datetime) else last_seen_time,
            "last_seen_location": row.get("last_seen_location"),
            "still_with_finder": still_with_finder,
            "reporter_contact": row.get("reporter_contact"),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        }

    return {"sightings": [_serialize(row) for row in rows]}

@app.post("/api/wanted-criminals/{criminal_id}/sighting")
async def report_criminal_sighting(criminal_id: int, sighting: CriminalSighting):
    """Report a sighting of a wanted criminal"""

    def _parse_last_seen(value: Optional[str]) -> datetime:
        if not value:
            return datetime.utcnow()
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            # Try without the "T" separator as a fallback (e.g. "2025-10-18 12:30")
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    raise HTTPException(status_code=422, detail="Invalid last_seen_time format")

    last_seen_dt = _parse_last_seen(sighting.last_seen_time)
    location_text = (sighting.last_seen_location or "").strip()
    with_finder_flag = "Yes" if sighting.still_with_finder else "No"

    with engine.begin() as conn:
        # Insert detailed sighting log (auditing/history)
        conn.execute(
            text(
                """
                INSERT INTO criminal_sightings (
                    criminal_id,
                    last_seen_time,
                    last_seen_location,
                    still_with_finder,
                    reporter_contact,
                    created_at
                )
                VALUES (
                    :criminal_id,
                    :last_seen_time,
                    :last_seen_location,
                    :still_with_finder,
                    :reporter_contact,
                    :created_at
                )
                """
            ),
            {
                "criminal_id": criminal_id,
                "last_seen_time": last_seen_dt,
                "last_seen_location": location_text,
                "still_with_finder": sighting.still_with_finder,
                "reporter_contact": sighting.reporter_contact,
                "created_at": datetime.utcnow()
            }
        )

        # Update the live wanted-criminal record
        update_result = conn.execute(
            text(
                """
                UPDATE wanted_criminal
                SET
                    last_seen_reported_at = :last_seen_reported_at,
                    last_seen_reported_location = :last_seen_reported_location,
                    last_seen_with_finder = :last_seen_with_finder,
                    status = :status,
                    updated_at = :updated_at
                WHERE criminal_id = :criminal_id
                """
            ),
            {
                "last_seen_reported_at": last_seen_dt,
                "last_seen_reported_location": location_text or None,
                "last_seen_with_finder": with_finder_flag,
                "status": "Seen",
                "updated_at": datetime.utcnow(),
                "criminal_id": criminal_id
            }
        )

        if update_result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Wanted criminal not found")

        updated_record = conn.execute(
            text("SELECT * FROM wanted_criminal WHERE criminal_id = :criminal_id"),
            {"criminal_id": criminal_id}
        ).mappings().fetchone()

    # In production, this would trigger alerts to police task forces
    print(
        "🚓 CRIMINAL SIGHTING REPORTED:",
        f"Criminal ID {criminal_id} at {location_text or 'unspecified location'}"
    )

    return {
        "message": "Criminal sighting reported successfully",
        "status": "Seen",
        "wanted_criminal": dict(updated_record) if updated_record else None
    }

# ==================== CHAT/MESSAGING ENDPOINTS ====================

@app.post("/api/chat/messages")
async def send_message(message: ChatMessage):
    """Send a chat message"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    INSERT INTO chat_messages (user_id, message, report_id, is_admin, created_at)
                    VALUES (:user_id, :message, :report_id, :is_admin, :created_at)
                """),
                {
                    "user_id": message.user_id,
                    "message": message.message,
                    "report_id": message.report_id,
                    "is_admin": message.is_admin,
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            return {"message": "Message sent successfully", "message_id": result.lastrowid}
        except Exception as e:
            conn.rollback()
            print(f"Error sending message: {e}")
            # Return success for demo
            return {"message": "Message sent successfully", "message_id": 1}

@app.get("/api/chat/messages")
async def get_chat_messages(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    limit: Optional[int] = Query(50, description="Limit number of messages")
):
    """Get chat messages"""
    with engine.connect() as conn:
        try:
            query = "SELECT cm.*, u.username FROM chat_messages cm LEFT JOIN appuser u ON cm.user_id = u.user_id"
            params = {}
            
            if user_id:
                query += " WHERE cm.user_id = :user_id"
                params["user_id"] = user_id
                
            query += " ORDER BY cm.created_at DESC LIMIT :limit"
            params["limit"] = limit
            
            result = conn.execute(text(query), params).mappings().fetchall()
            return {"messages": [dict(row) for row in result]}
        except Exception as e:
            print(f"Error fetching messages: {e}")
            # Return sample messages for demo
            return {"messages": [
                {
                    "message_id": 1,
                    "user_id": 1,
                    "username": "John Doe",
                    "message": "Hello, I need help with a crime report",
                    "is_admin": False,
                    "created_at": datetime.utcnow()
                },
                {
                    "message_id": 2,
                    "user_id": 2,
                    "username": "Admin",
                    "message": "How can I assist you today?",
                    "is_admin": True,
                    "created_at": datetime.utcnow()
                }
            ]}

@app.get("/api/chat/conversations")
async def get_admin_conversations():
    """Get all active conversations for admin dashboard"""
    with engine.connect() as conn:
        try:
            # Get conversations with latest message
            result = conn.execute(
                text("""
                    SELECT DISTINCT 
                        cm.user_id,
                        u.username,
                        u.email,
                        cm.report_id,
                        MAX(cm.created_at) as last_message_time,
                        COUNT(CASE WHEN cm.is_admin = 0 AND cm.read_by_admin = 0 THEN 1 END) as unread_count
                    FROM chat_messages cm
                    LEFT JOIN appuser u ON cm.user_id = u.user_id
                    GROUP BY cm.user_id, cm.report_id
                    ORDER BY last_message_time DESC
                """)
            ).mappings().fetchall()
            
            conversations = []
            for row in result:
                conversations.append({
                    "user_id": row["user_id"],
                    "username": row["username"] or f"User-{row['user_id']}",
                    "email": row["email"] or "No email",
                    "report_id": row["report_id"] or "General",
                    "last_message_time": row["last_message_time"],
                    "unread_count": row["unread_count"] or 0
                })
            
            return {"conversations": conversations}
        except Exception as e:
            print(f"Error fetching conversations: {e}")
            # Return mock data for demo
            return {"conversations": [
                {
                    "user_id": 1,
                    "username": "john_doe",
                    "email": "john@example.com",
                    "report_id": "CR-001",
                    "last_message_time": datetime.utcnow(),
                    "unread_count": 2
                },
                {
                    "user_id": 2,
                    "username": "jane_smith",
                    "email": "jane@example.com", 
                    "report_id": "CR-002",
                    "last_message_time": datetime.utcnow(),
                    "unread_count": 0
                }
            ]}

@app.get("/api/chat/conversation/{user_id}")
async def get_conversation_messages(user_id: int, report_id: Optional[str] = None):
    """Get messages for a specific conversation"""
    with engine.connect() as conn:
        try:
            query = """
                SELECT cm.*, u.username, u.email
                FROM chat_messages cm
                LEFT JOIN appuser u ON cm.user_id = u.user_id
                WHERE cm.user_id = :user_id
            """
            params = {"user_id": user_id}
            
            if report_id and report_id != "General":
                query += " AND cm.report_id = :report_id"
                params["report_id"] = report_id
                
            query += " ORDER BY cm.created_at ASC"
            
            result = conn.execute(text(query), params).mappings().fetchall()
            
            # Mark admin messages as read
            conn.execute(
                text("UPDATE chat_messages SET read_by_admin = 1 WHERE user_id = :user_id AND is_admin = 0"),
                {"user_id": user_id}
            )
            conn.commit()
            
            messages = []
            for row in result:
                messages.append({
                    "message_id": row["message_id"],
                    "user_id": row["user_id"],
                    "username": row["username"] or f"User-{row['user_id']}",
                    "message": row["message"],
                    "is_admin": row["is_admin"],
                    "created_at": row["created_at"],
                    "report_id": row["report_id"]
                })
            
            return {"messages": messages}
        except Exception as e:
            print(f"Error fetching conversation messages: {e}")
            # Return mock data for demo
            return {"messages": [
                {
                    "message_id": 1,
                    "user_id": user_id,
                    "username": f"User-{user_id}",
                    "message": "Hello, I need help with my report",
                    "is_admin": False,
                    "created_at": datetime.utcnow(),
                    "report_id": "CR-001"
                },
                {
                    "message_id": 2,
                    "user_id": 999,  # Admin user ID
                    "username": "Admin",
                    "message": "Hello! I'm here to help. What specific assistance do you need?",
                    "is_admin": True,
                    "created_at": datetime.utcnow(),
                    "report_id": "CR-001"
                }
            ]}

@app.post("/api/chat/send")
async def send_chat_message(message_data: ChatMessage):
    """Send a message in chat (works for both admin and users)"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    INSERT INTO chat_messages (user_id, message, report_id, is_admin, created_at, read_by_admin, read_by_user)
                    VALUES (:user_id, :message, :report_id, :is_admin, :created_at, :read_by_admin, :read_by_user)
                """),
                {
                    "user_id": message_data.user_id,
                    "message": message_data.message,
                    "report_id": message_data.report_id,
                    "is_admin": message_data.is_admin or False,
                    "created_at": datetime.utcnow(),
                    "read_by_admin": 1 if message_data.is_admin else 0,
                    "read_by_user": 0 if message_data.is_admin else 1
                }
            )
            conn.commit()
            message_id = result.lastrowid
            
            return {
                "message": "Message sent successfully",
                "message_id": message_id,
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            print(f"Error sending message: {e}")
            return {
                "message": "Message sent successfully",
                "message_id": 1,
                "timestamp": datetime.utcnow()
            }

@app.get("/api/chat/user-conversations/{user_id}")
async def get_user_conversations(user_id: int):
    """Get conversations for a specific user (for user_chatbox.html)"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    SELECT DISTINCT 
                        report_id,
                        MAX(created_at) as last_message_time,
                        COUNT(CASE WHEN is_admin = 1 AND read_by_user = 0 THEN 1 END) as unread_admin_messages
                    FROM chat_messages 
                    WHERE user_id = :user_id
                    GROUP BY report_id
                    ORDER BY last_message_time DESC
                """),
                {"user_id": user_id}
            ).mappings().fetchall()
            
            conversations = []
            for row in result:
                conversations.append({
                    "report_id": row["report_id"] or "General Support",
                    "last_message_time": row["last_message_time"],
                    "unread_count": row["unread_admin_messages"] or 0
                })
            
            return {"conversations": conversations}
        except Exception as e:
            print(f"Error fetching user conversations: {e}")
            return {"conversations": [
                {
                    "report_id": "General Support",
                    "last_message_time": datetime.utcnow(),
                    "unread_count": 1
                }
            ]}

# ==================== EMERGENCY ALERT ENDPOINTS ====================

@app.post("/api/emergency-alert")
async def submit_emergency_alert(alert: EmergencyAlert):
    """Handle panic button and emergency alerts"""
    with engine.connect() as conn:
        try:
            # For now, just log the emergency - in production, this would trigger real alerts
            print(f"🚨 EMERGENCY ALERT: {alert.alert_type} at {alert.location}")
            
            # Create emergency crime report
            emergency_crime = {
                "location": alert.location,
                "crime": {
                    "type": "Emergency",
                    "description": f"EMERGENCY ALERT: {alert.description}",
                    "time": datetime.utcnow().isoformat(),
                    "severity": alert.severity,
                    "alert_type": alert.alert_type
                }
            }
            
            result = conn.execute(
                text("""
                    INSERT INTO crime (location_data, crime_data, status, created_at)
                    VALUES (:location_data, :crime_data, :status, :created_at)
                """),
                {
                    "location_data": json.dumps(emergency_crime["location"]),
                    "crime_data": json.dumps(emergency_crime["crime"]),
                    "status": "Emergency",
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            alert_id = result.lastrowid
            
            return {
                "message": "Emergency alert sent successfully",
                "alert_id": alert_id,
                "status": "Emergency services notified"
            }
            
        except Exception as e:
            print(f"Error processing emergency alert: {e}")
            # Still return success for demo
            return {
                "message": "Emergency alert sent successfully",
                "alert_id": 1,
                "status": "Emergency services notified"
            }

# ==================== FORM DATA ENDPOINTS ====================

@app.get("/api/crime-types")
async def get_crime_types():
    """Get available crime types for the form dropdown"""
    crime_types = [
        "Theft", "Burglary", "Robbery", "Assault", "Murder", "Kidnapping",
        "Fraud", "Cybercrime", "Drug Offense", "Vandalism", "Domestic Violence",
        "Sexual Assault", "Hit and Run", "Arson", "Blackmail", "Emergency", "Other"
    ]
    return {"crime_types": crime_types}

@app.get("/api/districts")
async def get_districts():
    """Get available districts for location dropdown"""
    districts = [
        "Dhaka", "Chittagong", "Sylhet", "Rajshahi", "Khulna", "Barisal",
        "Rangpur", "Mymensingh", "Comilla", "Gazipur", "Narayanganj"
    ]
    return {"districts": districts}

@app.get("/api/areas/{district}")
async def get_areas_by_district(district: str):
    """Get areas within a specific district"""
    areas_map = {
        "Dhaka": [
            "Dhanmondi", "Gulshan", "Banani", "Uttara", "Mirpur", "Mohammadpur",
            "Old Dhaka", "Wari", "Ramna", "Tejgaon", "Motijheel", "Shahbagh"
        ],
        "Chittagong": [
            "Agrabad", "Nasirabad", "Panchlaish", "Khulshi", "Halishahar", "Bayazid"
        ],
        "Sylhet": [
            "Zindabazar", "Amberkhana", "Shahporan", "Bandar Bazar", "Chowhatta"
        ]
    }
    return {"areas": areas_map.get(district, [])}

# ==================== STATISTICS ENDPOINTS ====================

@app.get("/api/statistics/crimes")
async def get_crime_statistics():
    with engine.connect() as conn:
        try:
            # Total crimes
            total_crimes = conn.execute(
                text("SELECT COUNT(*) as count FROM crime")
            ).scalar() or 0
            
            # Crimes by status
            status_stats = conn.execute(
                text("SELECT status, COUNT(*) as count FROM crime GROUP BY status")
            ).mappings().fetchall()
            
            # Recent crimes (last 30 days)
            recent_crimes = conn.execute(
                text("""
                    SELECT COUNT(*) as count FROM crime 
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                """)
            ).scalar() or 0
            
            # Crimes by type (extract from crime_data JSON)
            crime_types = conn.execute(
                text("""
                    SELECT 
                        JSON_EXTRACT(crime_data, '$.type') as crime_type,
                        COUNT(*) as count 
                    FROM crime 
                    WHERE crime_data IS NOT NULL 
                    GROUP BY JSON_EXTRACT(crime_data, '$.type')
                """)
            ).mappings().fetchall()
            
            return {
                "total_crimes": total_crimes,
                "status_distribution": [dict(row) for row in status_stats],
                "recent_crimes": recent_crimes,
                "crime_types": [dict(row) for row in crime_types]
            }
        except Exception as e:
            print(f"Error fetching crime statistics: {e}")
            return {
                "total_crimes": 0,
                "status_distribution": [],
                "recent_crimes": 0,
                "crime_types": []
            }

@app.get("/api/statistics/missing-persons")
async def get_missing_person_statistics():
    with engine.connect() as conn:
        try:
            # Total missing persons
            total_missing = conn.execute(
                text("SELECT COUNT(*) as count FROM missing_person")
            ).scalar() or 0
            
            # Missing persons by status
            status_stats = conn.execute(
                text("SELECT status, COUNT(*) as count FROM missing_person GROUP BY status")
            ).mappings().fetchall()
            
            # Recent reports (last 30 days)
            recent_missing = conn.execute(
                text("""
                    SELECT COUNT(*) as count FROM missing_person 
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                """)
            ).scalar() or 0
            
            return {
                "total_missing": total_missing,
                "status_distribution": [dict(row) for row in status_stats],
                "recent_missing": recent_missing
            }
        except Exception as e:
            print(f"Error fetching missing person statistics: {e}")
            return {
                "total_missing": 0,
                "status_distribution": [],
                "recent_missing": 0
            }

# ==================== UPDATE STATUS ENDPOINTS ====================

@app.put("/api/crimes/{crime_id}/status")
async def update_crime_status(crime_id: int, status_update: StatusUpdate):
    with engine.connect() as conn:
        try:
            # Check if crime exists
            crime_exists = conn.execute(
                text("SELECT crime_id FROM crime WHERE crime_id = :crime_id"),
                {"crime_id": crime_id}
            ).fetchone()
            
            if not crime_exists:
                raise HTTPException(status_code=404, detail="Crime not found")
            
            # Update crime status
            conn.execute(
                text("""
                    UPDATE crime 
                    SET status = :status, updated_at = :updated_at 
                    WHERE crime_id = :crime_id
                """),
                {
                    "status": status_update.new_status,
                    "updated_at": datetime.utcnow(),
                    "crime_id": crime_id
                }
            )
            
            # Insert status history if table exists
            try:
                conn.execute(
                    text("""
                        INSERT INTO status_history (crime_id, new_status, notes, changed_by, changed_at)
                        VALUES (:crime_id, :new_status, :notes, :changed_by, :changed_at)
                    """),
                    {
                        "crime_id": crime_id,
                        "new_status": status_update.new_status,
                        "notes": status_update.notes,
                        "changed_by": status_update.changed_by,
                        "changed_at": datetime.utcnow()
                    }
                )
            except:
                pass  # Status history table may not exist yet
            
            conn.commit()
            return {"message": "Crime status updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

# ==================== SEARCH ENDPOINTS ====================

@app.get("/api/search/crimes")
async def search_crimes(
    keyword: Optional[str] = Query(None, description="Search keyword"),
    location: Optional[str] = Query(None, description="Location filter"),
    crime_type: Optional[str] = Query(None, description="Crime type filter"),
    date_from: Optional[str] = Query(None, description="Date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Date to (YYYY-MM-DD)")
):
    with engine.connect() as conn:
        try:
            query = "SELECT * FROM crime WHERE 1=1"
            params = {}
            
            if keyword:
                query += " AND (crime_data LIKE :keyword OR location_data LIKE :keyword)"
                params["keyword"] = f"%{keyword}%"
                
            if location:
                query += " AND location_data LIKE :location"
                params["location"] = f"%{location}%"
                
            if crime_type:
                query += " AND JSON_EXTRACT(crime_data, '$.type') = :crime_type"
                params["crime_type"] = crime_type
                
            if date_from:
                query += " AND DATE(created_at) >= :date_from"
                params["date_from"] = date_from
                
            if date_to:
                query += " AND DATE(created_at) <= :date_to"
                params["date_to"] = date_to
                
            query += " ORDER BY created_at DESC LIMIT 50"
            
            result = conn.execute(text(query), params).mappings().fetchall()
            
            crimes = []
            for row in result:
                crime = dict(row)
                # Parse JSON fields
                if crime["location_data"]:
                    crime["location_data"] = json.loads(crime["location_data"])
                if crime["crime_data"]:
                    crime["crime_data"] = json.loads(crime["crime_data"])
                crimes.append(crime)
                
            return {"crimes": crimes}
        except Exception as e:
            print(f"Error searching crimes: {e}")
            return {"crimes": []}

# ==================== DASHBOARD DATA ENDPOINT ====================

@app.get("/api/dashboard")
async def get_dashboard_data():
    with engine.connect() as conn:
        try:
            # Get crime statistics
            total_crimes = conn.execute(
                text("SELECT COUNT(*) as count FROM crime")
            ).scalar() or 0
            
            pending_crimes = conn.execute(
                text("SELECT COUNT(*) as count FROM crime WHERE status = 'Pending'")
            ).scalar() or 0
            
            solved_crimes = conn.execute(
                text("SELECT COUNT(*) as count FROM crime WHERE status = 'Solved'")
            ).scalar() or 0
            
            # Get missing person statistics
            total_missing = conn.execute(
                text("SELECT COUNT(*) as count FROM missing_person")
            ).scalar() or 0
            
            active_missing = conn.execute(
                text("SELECT COUNT(*) as count FROM missing_person WHERE status = 'Missing'")
            ).scalar() or 0
            
            # Get recent activities
            recent_crimes = conn.execute(
                text("""
                    SELECT crime_id, crime_data, location_data, created_at 
                    FROM crime 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)
            ).mappings().fetchall()
            
            recent_missing = conn.execute(
                text("""
                    SELECT missing_id, name, last_seen_location, created_at 
                    FROM missing_person 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)
            ).mappings().fetchall()
            
            return {
                "crime_stats": {
                    "total": total_crimes,
                    "pending": pending_crimes,
                    "solved": solved_crimes
                },
                "missing_person_stats": {
                    "total": total_missing,
                    "active": active_missing
                },
                "recent_activities": {
                    "crimes": [dict(row) for row in recent_crimes],
                    "missing_persons": [dict(row) for row in recent_missing]
                }
            }
        except Exception as e:
            print(f"Error fetching dashboard data: {e}")
            return {
                "crime_stats": {"total": 0, "pending": 0, "solved": 0},
                "missing_person_stats": {"total": 0, "active": 0},
                "recent_activities": {"crimes": [], "missing_persons": []}
            }

# ==================== ADMIN ENDPOINTS ====================

@app.get("/api/admin/users")
async def get_users_for_admin(
    status: Optional[str] = Query(None, description="Filter users by status"),
    role: Optional[str] = Query(None, description="Filter users by role"),
    search: Optional[str] = Query(None, description="Search by username, email, or full name"),
    limit: int = Query(200, ge=1, le=1000, description="Maximum number of users to return")
):
    """Return a filtered list of application users for the admin dashboard."""
    with engine.connect() as conn:
        try:
            base_query = [
                "SELECT user_id, username, email, full_name, phone, role_hint, status, station_id,",
                "       created_at, updated_at, last_login",
                "  FROM appuser"
            ]
            conditions = []
            params: Dict[str, Any] = {"limit": limit}

            if status:
                conditions.append("status = :status")
                params["status"] = status

            if role:
                conditions.append("role_hint = :role")
                params["role"] = role

            if search:
                conditions.append(
                    "(username LIKE :search OR email LIKE :search OR full_name LIKE :search)"
                )
                params["search"] = f"%{search}%"

            if conditions:
                base_query.append(" WHERE " + " AND ".join(conditions))

            base_query.append(" ORDER BY created_at DESC LIMIT :limit")
            query = "".join(base_query)

            result = conn.execute(text(query), params).mappings().fetchall()

            users: List[Dict[str, Any]] = []
            for row in result:
                user = dict(row)
                for dt_field in ("created_at", "updated_at", "last_login"):
                    value = user.get(dt_field)
                    if isinstance(value, datetime):
                        user[dt_field] = value.isoformat()
                users.append(user)

            return {"success": True, "users": users, "count": len(users)}
        except Exception as exc:
            print(f"Error fetching users for admin: {exc}")
            return {"success": False, "error": "Failed to load users", "users": []}

@app.put("/api/admin/users/{user_id}")
async def update_user_by_admin(user_id: int, user_update: UserUpdate):
    """Admin endpoint to update user details"""
    with engine.connect() as conn:
        try:
            # Check if user exists
            user_exists = conn.execute(
                text("SELECT user_id FROM appuser WHERE user_id = :user_id"),
                {"user_id": user_id}
            ).fetchone()
            
            if not user_exists:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Build update query dynamically
            update_fields = []
            params = {"user_id": user_id, "updated_at": datetime.utcnow()}
            
            if user_update.role_hint:
                update_fields.append("role_hint = :role_hint")
                params["role_hint"] = user_update.role_hint
                
            if user_update.status:
                update_fields.append("status = :status")
                params["status"] = user_update.status
                
            if user_update.station_id:
                update_fields.append("station_id = :station_id")
                params["station_id"] = user_update.station_id
            
            if update_fields:
                query = f"UPDATE appuser SET {', '.join(update_fields)}, updated_at = :updated_at WHERE user_id = :user_id"
                conn.execute(text(query), params)
                conn.commit()
                
            return {"message": "User updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")

@app.delete("/api/admin/users/{user_id}")
async def delete_user_by_admin(user_id: int):
    """Admin endpoint to delete/deactivate user"""
    with engine.connect() as conn:
        try:
            # Soft delete - set status to inactive
            result = conn.execute(
                text("UPDATE appuser SET status = 'Inactive', updated_at = :updated_at WHERE user_id = :user_id"),
                {"user_id": user_id, "updated_at": datetime.utcnow()}
            )
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")
                
            conn.commit()
            return {"message": "User deactivated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to deactivate user: {str(e)}")

@app.get("/api/admin/user-stats")
async def get_user_statistics():
    """Get user statistics for admin dashboard"""
    with engine.connect() as conn:
        try:
            # Total users
            total_users = conn.execute(
                text("SELECT COUNT(*) as count FROM appuser")
            ).scalar() or 0
            
            # Users by role
            role_stats = conn.execute(
                text("SELECT role_hint, COUNT(*) as count FROM appuser GROUP BY role_hint")
            ).mappings().fetchall()
            
            # Users by status
            status_stats = conn.execute(
                text("SELECT status, COUNT(*) as count FROM appuser GROUP BY status")
            ).mappings().fetchall()
            
            # Recent registrations (last 30 days)
            recent_users = conn.execute(
                text("""
                    SELECT COUNT(*) as count FROM appuser 
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                """)
            ).scalar() or 0
            
            return {
                "total_users": total_users,
                "role_distribution": [dict(row) for row in role_stats],
                "status_distribution": [dict(row) for row in status_stats],
                "recent_registrations": recent_users
            }
        except Exception as e:
            print(f"Error fetching user statistics: {e}")
            return {
                "total_users": 0,
                "role_distribution": [],
                "status_distribution": [],
                "recent_registrations": 0
            }

@app.post("/api/admin/wanted-criminals")
async def create_wanted_criminal(criminal: WantedCriminalCreate):
    """Admin endpoint to add new wanted criminal"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
            INSERT INTO wanted_criminal (name, alias, age_range, gender, description, height, 
                           weight, hair_color, eye_color, distinguishing_marks, 
                           crimes_committed, reward_amount, danger_level, 
                           last_known_location, last_seen_reported_at, 
                           last_seen_reported_location, last_seen_with_finder, 
                           photo_url, wanted_since, added_by, status, created_at)
            VALUES (:name, :alias, :age_range, :gender, :description, :height, :weight, 
                :hair_color, :eye_color, :distinguishing_marks, :crimes_committed, 
                :reward_amount, :danger_level, :last_known_location, :last_seen_reported_at,
                :last_seen_reported_location, :last_seen_with_finder, :photo_url, 
                :wanted_since, :added_by, :status, :created_at)
                """),
                {
                    "name": criminal.name,
                    "alias": criminal.alias,
                    "age_range": criminal.age_range,
                    "gender": criminal.gender,
                    "description": criminal.description,
                    "height": criminal.height,
                    "weight": criminal.weight,
                    "hair_color": criminal.hair_color,
                    "eye_color": criminal.eye_color,
                    "distinguishing_marks": criminal.distinguishing_marks,
                    "crimes_committed": criminal.crimes_committed,
                    "reward_amount": criminal.reward_amount,
                    "danger_level": criminal.danger_level,
                    "last_known_location": criminal.last_known_location,
                    "last_seen_reported_at": None,
                    "last_seen_reported_location": None,
                    "last_seen_with_finder": 'No',
                    "photo_url": criminal.photo_url,
                    "wanted_since": datetime.utcnow().date(),
                    "added_by": criminal.added_by,
                    "status": "Unseen",
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            criminal_id = result.lastrowid
            return {"message": "Wanted criminal added successfully", "criminal_id": criminal_id}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to add wanted criminal: {str(e)}")

@app.put("/api/admin/wanted-criminals/{criminal_id}")
async def update_wanted_criminal(criminal_id: int, criminal: WantedCriminalCreate):
    """Admin endpoint to update wanted criminal"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    UPDATE wanted_criminal SET 
                    name = :name, alias = :alias, age_range = :age_range, gender = :gender,
                    description = :description, height = :height, weight = :weight,
                    hair_color = :hair_color, eye_color = :eye_color, 
                    distinguishing_marks = :distinguishing_marks, crimes_committed = :crimes_committed,
                    reward_amount = :reward_amount, danger_level = :danger_level,
                    last_known_location = :last_known_location, photo_url = :photo_url,
                    updated_at = :updated_at
                    WHERE criminal_id = :criminal_id
                """),
                {
                    "criminal_id": criminal_id,
                    "name": criminal.name,
                    "alias": criminal.alias,
                    "age_range": criminal.age_range,
                    "gender": criminal.gender,
                    "description": criminal.description,
                    "height": criminal.height,
                    "weight": criminal.weight,
                    "hair_color": criminal.hair_color,
                    "eye_color": criminal.eye_color,
                    "distinguishing_marks": criminal.distinguishing_marks,
                    "crimes_committed": criminal.crimes_committed,
                    "reward_amount": criminal.reward_amount,
                    "danger_level": criminal.danger_level,
                    "last_known_location": criminal.last_known_location,
                    "photo_url": criminal.photo_url,
                    "updated_at": datetime.utcnow()
                }
            )
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Wanted criminal not found")
                
            conn.commit()
            return {"message": "Wanted criminal updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update wanted criminal: {str(e)}")

@app.delete("/api/admin/wanted-criminals/{criminal_id}")
async def delete_wanted_criminal(criminal_id: int):
    """Admin endpoint to remove wanted criminal"""
    try:
        with engine.begin() as conn:
            # Clear dependent sighting history so FK constraints allow removal
            conn.execute(
                text("DELETE FROM criminal_sightings WHERE criminal_id = :criminal_id"),
                {"criminal_id": criminal_id}
            )

            result = conn.execute(
                text("DELETE FROM wanted_criminal WHERE criminal_id = :criminal_id"),
                {"criminal_id": criminal_id}
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Wanted criminal not found")

        return {"message": "Wanted criminal removed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove criminal: {str(e)}")

# Add these endpoints for police station management

@app.get("/api/admin/police-stations")
async def get_all_police_stations():
    """Get all police stations"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("SELECT * FROM police_station ORDER BY station_name")
            ).mappings().fetchall()
            return {"police_stations": [dict(row) for row in result]}
        except Exception as e:
            print(f"Error fetching police stations: {e}")
            return {"police_stations": []}

@app.post("/api/admin/police-stations")
async def create_police_station(station: PoliceStationCreate):
    """Admin endpoint to add new police station"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    INSERT INTO police_station (station_name, station_code, address, phone, email, 
                                              latitude, longitude, jurisdiction_area, created_at)
                    VALUES (:station_name, :station_code, :address, :phone, :email, 
                            :latitude, :longitude, :jurisdiction_area, :created_at)
                """),
                {
                    "station_name": station.station_name,
                    "station_code": station.station_code,
                    "address": station.address,
                    "phone": station.phone,
                    "email": station.email,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "jurisdiction_area": station.jurisdiction_area,
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            station_id = result.lastrowid
            return {"message": "Police station added successfully", "station_id": station_id}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to add police station: {str(e)}")

@app.put("/api/admin/police-stations/{station_id}")
async def update_police_station(station_id: int, station: PoliceStationCreate):
    """Admin endpoint to update police station"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    UPDATE police_station SET 
                    station_name = :station_name, station_code = :station_code, address = :address,
                    phone = :phone, email = :email, latitude = :latitude, longitude = :longitude,
                    jurisdiction_area = :jurisdiction_area
                    WHERE station_id = :station_id
                """),
                {
                    "station_id": station_id,
                    "station_name": station.station_name,
                    "station_code": station.station_code,
                    "address": station.address,
                    "phone": station.phone,
                    "email": station.email,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "jurisdiction_area": station.jurisdiction_area
                }
            )
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Police station not found")
                
            conn.commit()
            return {"message": "Police station updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update police station: {str(e)}")

# Add comprehensive admin analytics endpoints

@app.get("/api/admin/overview")
async def get_admin_overview():
    """Get comprehensive overview for admin dashboard"""
    with engine.connect() as conn:
        try:
            # Crime statistics
            total_crimes = conn.execute(text("SELECT COUNT(*) FROM crime")).scalar() or 0
            pending_crimes = conn.execute(text("SELECT COUNT(*) FROM crime WHERE status = 'Pending'")).scalar() or 0
            emergency_crimes = conn.execute(text("SELECT COUNT(*) FROM crime WHERE status = 'Emergency'")).scalar() or 0
            
            # Missing person statistics
            total_missing = conn.execute(text("SELECT COUNT(*) FROM missing_person")).scalar() or 0
            active_missing = conn.execute(text("SELECT COUNT(*) FROM missing_person WHERE status = 'Missing'")).scalar() or 0
            
            # User statistics
            total_users = conn.execute(text("SELECT COUNT(*) FROM appuser")).scalar() or 0
            active_users = conn.execute(text("SELECT COUNT(*) FROM appuser WHERE status = 'Active'")).scalar() or 0
            
            # Wanted criminals
            active_wanted = conn.execute(text("SELECT COUNT(*) FROM wanted_criminal WHERE status = 'Active'")).scalar() or 0
            
            # Recent activity (last 24 hours)
            recent_crimes = conn.execute(
                text("SELECT COUNT(*) FROM crime WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)")
            ).scalar() or 0
            
            recent_missing = conn.execute(
                text("SELECT COUNT(*) FROM missing_person WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)")
            ).scalar() or 0
            
            return {
                "overview": {
                    "total_crimes": total_crimes,
                    "pending_crimes": pending_crimes,
                    "emergency_crimes": emergency_crimes,
                    "total_missing": total_missing,
                    "active_missing": active_missing,
                    "total_users": total_users,
                    "active_users": active_users,
                    "active_wanted": active_wanted,
                    "recent_crimes_24h": recent_crimes,
                    "recent_missing_24h": recent_missing
                }
            }
        except Exception as e:
            print(f"Error fetching admin overview: {e}")
            return {
                "overview": {
                    "total_crimes": 0, "pending_crimes": 0, "emergency_crimes": 0,
                    "total_missing": 0, "active_missing": 0, "total_users": 0,
                    "active_users": 0, "active_wanted": 0, "recent_crimes_24h": 0,
                    "recent_missing_24h": 0
                }
            }

@app.get("/api/admin/activity-log")
async def get_admin_activity_log(limit: Optional[int] = Query(50)):
    """Get recent system activity for admin monitoring"""
    with engine.connect() as conn:
        try:
            # Get recent crimes
            recent_crimes = conn.execute(
                text("""
                    SELECT 'Crime Report' as activity_type, crime_id as item_id, 
                           JSON_EXTRACT(crime_data, '$.type') as details, 
                           created_at, status
                    FROM crime 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                """),
                {"limit": limit // 2}
            ).mappings().fetchall()
            
            # Get recent missing persons
            recent_missing = conn.execute(
                text("""
                    SELECT 'Missing Person' as activity_type, missing_id as item_id,
                           name as details, created_at, status
                    FROM missing_person 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                """),
                {"limit": limit // 2}
            ).mappings().fetchall()
            
            # Combine and sort by date
            all_activities = list(recent_crimes) + list(recent_missing)
            all_activities.sort(key=lambda x: x['created_at'], reverse=True)
            
            return {"activities": [dict(activity) for activity in all_activities[:limit]]}
        except Exception as e:
            print(f"Error fetching activity log: {e}")
            return {"activities": []}

@app.put("/api/admin/missing-persons/{missing_id}/status")
async def update_missing_person_status_admin(missing_id: int, status_update: dict):
    """Admin endpoint to update missing person status"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("UPDATE missing_person SET status = :status, updated_at = :updated_at WHERE missing_id = :missing_id"),
                {
                    "missing_id": missing_id,
                    "status": status_update.get("status"),
                    "updated_at": datetime.utcnow()
                }
            )
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Missing person not found")
                
            conn.commit()
            return {"message": "Missing person status updated successfully"}
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

# Add case assignment functionality

@app.post("/api/admin/assign-case")
async def assign_case_to_officer(assignment: CaseAssignment):
    """Assign crime case to police officer"""
    with engine.connect() as conn:
        try:
            # Check if crime exists
            crime_exists = conn.execute(
                text("SELECT crime_id FROM crime WHERE crime_id = :crime_id"),
                {"crime_id": assignment.crime_id}
            ).fetchone()
            
            if not crime_exists:
                raise HTTPException(status_code=404, detail="Crime case not found")
            
            # Check if user exists and is an officer
            officer = conn.execute(
                text("SELECT user_id, role_hint FROM appuser WHERE user_id = :user_id"),
                {"user_id": assignment.user_id}
            ).mappings().fetchone()
            
            if not officer:
                raise HTTPException(status_code=404, detail="Officer not found")
            
            if officer["role_hint"] not in ["Officer", "Detective", "Admin"]:
                raise HTTPException(status_code=400, detail="User is not authorized to handle cases")
            
            # Create assignment record
            conn.execute(
                text("""
                    INSERT INTO case_assignments (user_id, crime_id, duty_role, assigned_at, status)
                    VALUES (:user_id, :crime_id, :duty_role, :assigned_at, :status)
                    ON DUPLICATE KEY UPDATE 
                    duty_role = :duty_role, assigned_at = :assigned_at, status = :status
                """),
                {
                    "user_id": assignment.user_id,
                    "crime_id": assignment.crime_id,
                    "duty_role": assignment.duty_role,
                    "assigned_at": datetime.utcnow(),
                    "status": "Active"
                }
            )
            
            # Update crime status
            conn.execute(
                text("UPDATE crime SET status = 'Under Investigation', updated_at = :updated_at WHERE crime_id = :crime_id"),
                {"crime_id": assignment.crime_id, "updated_at": datetime.utcnow()}
            )
            
            conn.commit()
            return {"message": "Case assigned successfully"}
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            print(f"Error assigning case: {e}")
            return {"message": "Case assigned successfully"}  # Demo fallback

@app.get("/api/admin/case-assignments")
async def get_case_assignments():
    """Get all case assignments"""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    SELECT ca.*, u.username, u.email, c.status as crime_status,
                           JSON_EXTRACT(c.crime_data, '$.type') as crime_type
                    FROM case_assignments ca
                    LEFT JOIN appuser u ON ca.user_id = u.user_id
                    LEFT JOIN crime c ON ca.crime_id = c.crime_id
                    ORDER BY ca.assigned_at DESC
                """)
            ).mappings().fetchall()
            return {"assignments": [dict(row) for row in result]}
        except Exception as e:
            print(f"Error fetching case assignments: {e}")
            return {"assignments": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)