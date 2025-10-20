from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import logging
from pydantic import BaseModel, validator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
import hashlib
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Mapping
import json
import os
import uuid
import asyncio
import mysql.connector
from mysql.connector import Error

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

class AdminCrimeCreate(BaseModel):
    crime_type: str
    status: str
    city: str
    area_name: str
    description: str
    incident_time: Optional[str] = None
    priority: Optional[str] = "medium"
    location_details: Optional[str] = None
    reporter_id: Optional[int] = None
    victim: Optional[Dict[str, Any]] = None
    criminal: Optional[Dict[str, Any]] = None
    weapon: Optional[Dict[str, Any]] = None
    witness: Optional[Dict[str, Any]] = None
    evidence_files: Optional[List[Dict[str, Any]]] = None
    witness_info: Optional[str] = None

class MissingPersonData(BaseModel):
    name: str
    age: int
    gender: str
    description: str
    last_seen_location: str
    last_seen_date: str
    contact_info: str
    photo_url: Optional[str] = None

class MissingPersonFinderUpdate(BaseModel):
    finding_location: str
    finder_name: str
    finder_phone: str
    finder_email: Optional[str] = None
    still_with_finder: Optional[bool] = False

    @validator("finding_location", "finder_name", "finder_phone")
    def validate_non_empty(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("Field cannot be empty")
        return str(value).strip()

    @validator("finder_email")
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

class ComplaintVerification(BaseModel):
    complaint_id: int
    status: str

class CaseAssignment(BaseModel):
    user_id: int
    crime_id: int
    duty_role: str

class StatusUpdate(BaseModel):
    new_status: str
    notes: Optional[str] = None
    changed_by: Optional[int] = None

class ChatMessage(BaseModel):
    user_id: int
    message: str
    report_id: Optional[str] = None
    is_admin: Optional[bool] = False

class EmergencyAlert(BaseModel):
    user_id: Optional[int] = None
    location: Optional[Dict[str, Any]] = None
    address_label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    alert_type: str
    description: str
    severity: str = "High"


class EmergencyAssignment(BaseModel):
    officer_id: int

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
    officer_in_charge: Optional[str] = None

    @validator("latitude")
    def validate_latitude(cls, value):
        if value is None:
            return value
        if not (-90.0 <= value <= 90.0):
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return value

    @validator("longitude")
    def validate_longitude(cls, value):
        if value is None:
            return value
        if not (-180.0 <= value <= 180.0):
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return value

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

@app.post("/api/admin/crimes")
async def create_admin_crime(payload: AdminCrimeCreate):
    """Allow administrators to log a new crime directly from the dashboard."""

    status_map = {
        "reported": "Reported",
        "pending": "Pending",
        "under_investigation": "Under Investigation",
        "under investigation": "Under Investigation",
        "in_progress": "In Progress",
        "in progress": "In Progress",
        "resolved": "Resolved",
        "case_closed": "Case Closed",
        "case closed": "Case Closed",
    }

    priority_map = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
    }

    def clean_structured_value(value: Optional[Any]) -> Optional[Any]:
        """Strip empty values from nested payloads before serializing."""
        if value is None:
            return None
        if isinstance(value, dict):
            cleaned: Dict[str, Any] = {}
            for key, item in value.items():
                if item is None:
                    continue
                if isinstance(item, str):
                    trimmed = item.strip()
                    if not trimmed:
                        continue
                    cleaned[key] = trimmed
                elif isinstance(item, (int, float, bool)):
                    cleaned[key] = item
                elif isinstance(item, list):
                    nested_list = clean_structured_value(item)
                    if nested_list is not None:
                        cleaned[key] = nested_list
                elif isinstance(item, dict):
                    nested_dict = clean_structured_value(item)
                    if nested_dict is not None:
                        cleaned[key] = nested_dict
            return cleaned or None
        if isinstance(value, list):
            cleaned_list: List[Any] = []
            for item in value:
                if item is None:
                    continue
                if isinstance(item, str):
                    trimmed = item.strip()
                    if trimmed:
                        cleaned_list.append(trimmed)
                elif isinstance(item, (int, float, bool)):
                    cleaned_list.append(item)
                else:
                    nested = clean_structured_value(item)
                    if nested is not None:
                        cleaned_list.append(nested)
            return cleaned_list or None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    normalized_status_key = (payload.status or "").strip().lower().replace("-", "_")
    status_value = status_map.get(normalized_status_key, (payload.status or "Pending").strip().title() or "Pending")

    normalized_priority_key = (payload.priority or "medium").strip().lower()
    priority_value = priority_map.get(normalized_priority_key, "Medium")

    incident_dt: Optional[datetime] = None
    if payload.incident_time:
        candidate = payload.incident_time.strip()
        try:
            incident_dt = datetime.fromisoformat(candidate)
        except ValueError:
            try:
                incident_dt = datetime.fromisoformat(candidate.replace(" ", "T"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="incident_time must be an ISO 8601 datetime string (e.g., 2025-10-18T15:30)") from exc

    location_payload = {
        "city": (payload.city or "").strip(),
        "area_name": (payload.area_name or "").strip(),
    }
    if payload.location_details:
        location_payload["details"] = payload.location_details.strip()

    crime_payload = {
        "type": (payload.crime_type or "").strip(),
        "description": (payload.description or "").strip(),
        "status": status_value,
        "priority_level": priority_value,
        "source": "admin-dashboard",
    }

    victim_struct = clean_structured_value(payload.victim)
    criminal_struct = clean_structured_value(payload.criminal)
    weapon_struct = clean_structured_value(payload.weapon)
    witness_struct = clean_structured_value(payload.witness)
    evidence_struct = clean_structured_value(payload.evidence_files)
    witness_info_value = clean_structured_value(payload.witness_info)

    witness_info_struct: Optional[Dict[str, Any]] = None
    if witness_info_value:
        if isinstance(witness_struct, dict):
            witness_struct.setdefault("statement", witness_info_value)
        else:
            witness_struct = {"statement": witness_info_value}
        witness_info_struct = {"statement": witness_info_value}

    created_at = datetime.utcnow()

    with engine.connect() as conn:
        reporter_id_val: Optional[int] = None
        if payload.reporter_id is not None:
            reporter_row = conn.execute(
                text("SELECT user_id FROM appuser WHERE user_id = :uid"),
                {"uid": payload.reporter_id}
            ).fetchone()
            if reporter_row:
                reporter_id_val = payload.reporter_id

        try:
            result = conn.execute(
                text(
                    """
                    INSERT INTO crime (
                        reporter_id,
                        incident_date,
                        location_data,
                        crime_data,
                        victim_data,
                        criminal_data,
                        weapon_data,
                        witness_data,
                        evidence_files,
                        witness_info,
                        status,
                        priority_level,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :reporter_id,
                        :incident_date,
                        :location_data,
                        :crime_data,
                        :victim_data,
                        :criminal_data,
                        :weapon_data,
                        :witness_data,
                        :evidence_files,
                        :witness_info,
                        :status,
                        :priority_level,
                        :created_at,
                        :updated_at
                    )
                    """
                ),
                {
                    "reporter_id": reporter_id_val,
                    "incident_date": incident_dt,
                    "location_data": json.dumps(location_payload),
                    "crime_data": json.dumps(crime_payload),
                    "victim_data": json.dumps(victim_struct) if victim_struct else None,
                    "criminal_data": json.dumps(criminal_struct) if criminal_struct else None,
                    "weapon_data": json.dumps(weapon_struct) if weapon_struct else None,
                    "witness_data": json.dumps(witness_struct) if witness_struct else None,
                    "evidence_files": json.dumps(evidence_struct) if evidence_struct else None,
                    "witness_info": json.dumps(witness_info_struct) if witness_info_struct else None,
                    "status": status_value,
                    "priority_level": priority_value,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )
            conn.commit()
            crime_id = result.lastrowid
            return {"message": "Crime report created", "crime_id": crime_id}
        except IntegrityError as ie:
            conn.rollback()
            raise HTTPException(status_code=400, detail=f"Failed to create crime record: {ie}") from ie
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create crime record: {exc}") from exc

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


@app.delete("/api/crimes/{crime_id}")
async def delete_crime_record(crime_id: int):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM case_assignments WHERE crime_id = :crime_id"),
            {"crime_id": crime_id}
        )
        result = conn.execute(
            text("DELETE FROM crime WHERE crime_id = :crime_id"),
            {"crime_id": crime_id}
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Crime not found")

    return {"message": "Crime report deleted"}

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
               photo_url, status, police_case_number,
               finding_location, finder_name, finder_phone, finder_email,
         still_with_finder, created_at, updated_at
        FROM missing_person
        ORDER BY COALESCE(updated_at, created_at) DESC
    """)
    try:
        with engine.connect() as conn:
            rows = [dict(row) for row in conn.execute(query).mappings()]
        return {"missing_persons": rows}
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


@app.put("/api/missing-persons/{missing_id}/found")
async def update_missing_person_finder(missing_id: int, payload: MissingPersonFinderUpdate):
    normalized_status = "Found" if payload.still_with_finder else "Missing"
    still_with_value = "Yes" if payload.still_with_finder else "No"
    timestamp = datetime.utcnow()

    update_sql = text(
        """
        UPDATE missing_person
        SET finding_location = :finding_location,
            finder_name = :finder_name,
            finder_phone = :finder_phone,
            finder_email = :finder_email,
            still_with_finder = :still_with_finder,
            status = :status,
            updated_at = :updated_at
        WHERE missing_id = :missing_id
        """
    )

    with engine.begin() as conn:
        result = conn.execute(update_sql, {
            "finding_location": payload.finding_location,
            "finder_name": payload.finder_name,
            "finder_phone": payload.finder_phone,
            "finder_email": payload.finder_email,
            "still_with_finder": still_with_value,
            "status": normalized_status,
            "updated_at": timestamp,
            "missing_id": missing_id,
        })

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Missing person not found")

        refreshed = conn.execute(
            text(
                """
                SELECT missing_id, reporter_id, name, age, gender, description,
                       last_seen_location, last_seen_date, last_seen_time, height,
                       weight, hair_color, eye_color, distinguishing_marks,
                       clothing_description, contact_person, contact_phone,
                       photo_url, status, police_case_number,
                       finding_location, finder_name, finder_phone, finder_email,
                       still_with_finder, created_at, updated_at
                FROM missing_person
                WHERE missing_id = :missing_id
                """
            ),
            {"missing_id": missing_id}
        ).mappings().fetchone()

    return {"missing_person": dict(refreshed)}


@app.delete("/api/missing-persons/{missing_id}")
async def delete_missing_person_record(missing_id: int):
    delete_sql = text("DELETE FROM missing_person WHERE missing_id = :missing_id")

    with engine.begin() as conn:
        result = conn.execute(delete_sql, {"missing_id": missing_id})

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Missing person not found")

    return {"message": "Missing person report deleted"}

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

def ensure_status_history_table(conn) -> None:
    """Create the status_history table if it does not already exist."""
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS status_history (
            history_id INT AUTO_INCREMENT PRIMARY KEY,
            crime_id INT NOT NULL,
            new_status VARCHAR(100) NOT NULL,
            notes TEXT NULL,
            changed_by INT NULL,
            changed_at DATETIME NOT NULL,
            INDEX idx_status_history_crime (crime_id),
            INDEX idx_status_history_changed (changed_at)
        )
        """
    ))

def ensure_emergency_alerts_table(conn) -> None:
    """Create the emergency_alerts table if it does not already exist."""
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS emergency_alerts (
            alert_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NULL,
            user_snapshot LONGTEXT NULL,
            linked_crime_id INT NULL,
            location_label VARCHAR(255) NULL,
            latitude DECIMAL(10, 7) NULL,
            longitude DECIMAL(10, 7) NULL,
            alert_type VARCHAR(100) NOT NULL,
            severity VARCHAR(50) NOT NULL DEFAULT 'High',
            description TEXT NULL,
            metadata LONGTEXT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'New',
            assigned_officer_id INT NULL,
            assigned_officer_snapshot LONGTEXT NULL,
            assigned_at DATETIME NULL,
            created_at DATETIME NOT NULL,
            resolved_at DATETIME NULL,
            INDEX idx_emergency_status (status),
            INDEX idx_emergency_created_at (created_at)
        )
        """
    ))

def parse_json_value(value):
    """Safely parse a JSON string into Python data structures."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None

@app.post("/api/emergency-alert")
async def submit_emergency_alert(alert: EmergencyAlert):
    """Handle panic button and emergency alerts."""

    def coerce_float(value):
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    try:
        with engine.begin() as conn:
            ensure_emergency_alerts_table(conn)

            user_snapshot = None
            if alert.user_id:
                user_row = conn.execute(
                    text("""
                        SELECT user_id, username, email, role_hint, status
                        FROM appuser
                        WHERE user_id = :user_id
                    """),
                    {"user_id": alert.user_id}
                ).mappings().fetchone()

                if not user_row:
                    raise HTTPException(status_code=404, detail="User not found for panic alert")

                user_snapshot = {
                    "user_id": user_row["user_id"],
                    "username": user_row.get("username"),
                    "email": user_row.get("email"),
                    "role_hint": user_row.get("role_hint"),
                    "status": user_row.get("status")
                }

            location_payload = alert.location or {}
            if not isinstance(location_payload, dict):
                try:
                    location_payload = dict(location_payload)
                except Exception:
                    location_payload = {}

            latitude = coerce_float(location_payload.get("latitude") or location_payload.get("lat"))
            longitude = coerce_float(location_payload.get("longitude") or location_payload.get("lng"))
            location_label = alert.address_label or location_payload.get("label") or location_payload.get("address")

            emergency_crime_payload = {
                "type": "Emergency",
                "description": f"EMERGENCY ALERT: {alert.description}",
                "time": datetime.utcnow().isoformat(),
                "severity": alert.severity,
                "alert_type": alert.alert_type
            }

            crime_result = conn.execute(
                text(
                    """
                    INSERT INTO crime (location_data, crime_data, status, reporter_id, created_at)
                    VALUES (:location_data, :crime_data, :status, :reporter_id, :created_at)
                    """
                ),
                {
                    "location_data": json.dumps(location_payload),
                    "crime_data": json.dumps(emergency_crime_payload),
                    "status": "Emergency",
                    "reporter_id": alert.user_id,
                    "created_at": datetime.utcnow()
                }
            )
            linked_crime_id = crime_result.lastrowid

            metadata_payload = alert.metadata or {}
            alert_result = conn.execute(
                text(
                    """
                    INSERT INTO emergency_alerts (
                        user_id,
                        user_snapshot,
                        linked_crime_id,
                        location_label,
                        latitude,
                        longitude,
                        alert_type,
                        severity,
                        description,
                        metadata,
                        status,
                        created_at
                    )
                    VALUES (
                        :user_id,
                        :user_snapshot,
                        :linked_crime_id,
                        :location_label,
                        :latitude,
                        :longitude,
                        :alert_type,
                        :severity,
                        :description,
                        :metadata,
                        :status,
                        :created_at
                    )
                    """
                ),
                {
                    "user_id": alert.user_id,
                    "user_snapshot": json.dumps(user_snapshot) if user_snapshot else None,
                    "linked_crime_id": linked_crime_id,
                    "location_label": location_label,
                    "latitude": latitude,
                    "longitude": longitude,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "description": alert.description,
                    "metadata": json.dumps(metadata_payload) if metadata_payload else None,
                    "status": "New",
                    "created_at": datetime.utcnow()
                }
            )

            alert_id = alert_result.lastrowid

        return {
            "message": "Emergency alert sent successfully",
            "alert_id": alert_id,
            "crime_id": linked_crime_id,
            "status": "Emergency services notified"
        }
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Error processing emergency alert: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to process emergency alert")


@app.get("/api/admin/emergencies")
async def get_admin_emergencies(status: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=500)):
    """Retrieve recent emergency alerts with enrichment for the admin dashboard."""
    with engine.connect() as conn:
        ensure_emergency_alerts_table(conn)

        params: Dict[str, Any] = {"limit": limit}
        base_query = (
            """
            SELECT alert_id, user_id, user_snapshot, linked_crime_id, location_label,
                   latitude, longitude, alert_type, severity, description, metadata,
                   status, assigned_officer_id, assigned_officer_snapshot, assigned_at,
                   created_at, resolved_at
            FROM emergency_alerts
            """
        )

        if status:
            base_query += " WHERE LOWER(status) = :status"
            params["status"] = status.lower()

        base_query += " ORDER BY created_at DESC LIMIT :limit"

        rows = conn.execute(text(base_query), params).mappings().fetchall()

    emergencies = []
    for row in rows:
        def decode_json(value):
            if not value:
                return None
            try:
                return json.loads(value)
            except Exception:
                return None

        emergency = {
            "alert_id": row["alert_id"],
            "user_id": row["user_id"],
            "user_snapshot": decode_json(row.get("user_snapshot")),
            "linked_crime_id": row.get("linked_crime_id"),
            "location_label": row.get("location_label") or "Unknown location",
            "latitude": float(row.get("latitude")) if row.get("latitude") is not None else None,
            "longitude": float(row.get("longitude")) if row.get("longitude") is not None else None,
            "alert_type": row.get("alert_type"),
            "severity": row.get("severity"),
            "description": row.get("description"),
            "metadata": decode_json(row.get("metadata")) or {},
            "status": row.get("status"),
            "assigned_officer_id": row.get("assigned_officer_id"),
            "assigned_officer_snapshot": decode_json(row.get("assigned_officer_snapshot")),
            "assigned_at": row.get("assigned_at"),
            "created_at": row.get("created_at"),
            "resolved_at": row.get("resolved_at")
        }

        emergencies.append(emergency)

    return {"emergencies": emergencies}


@app.put("/api/admin/emergencies/{alert_id}/assign")
async def assign_emergency(alert_id: int, assignment: EmergencyAssignment):
    """Assign an officer to a specific emergency alert."""
    try:
        with engine.begin() as conn:
            ensure_emergency_alerts_table(conn)

            alert_row = conn.execute(
                text(
                    """
                    SELECT alert_id, status, linked_crime_id
                    FROM emergency_alerts
                    WHERE alert_id = :alert_id
                    FOR UPDATE
                    """
                ),
                {"alert_id": alert_id}
            ).mappings().fetchone()

            if not alert_row:
                raise HTTPException(status_code=404, detail="Emergency alert not found")

            officer = conn.execute(
                text(
                    """
                    SELECT user_id, username, email, role_hint, status
                    FROM appuser
                    WHERE user_id = :user_id
                """
                ),
                {"user_id": assignment.officer_id}
            ).mappings().fetchone()

            if not officer:
                raise HTTPException(status_code=404, detail="Officer not found")

            role_hint = (officer.get("role_hint") or "").lower()
            if role_hint not in {"officer", "detective", "admin"}:
                raise HTTPException(status_code=400, detail="User is not authorized for emergency response")

            officer_snapshot = {
                "user_id": officer["user_id"],
                "username": officer.get("username"),
                "email": officer.get("email"),
                "role_hint": officer.get("role_hint"),
                "status": officer.get("status")
            }

            conn.execute(
                text(
                    """
                    UPDATE emergency_alerts
                    SET assigned_officer_id = :officer_id,
                        assigned_officer_snapshot = :snapshot,
                        assigned_at = :assigned_at,
                        status = :status
                    WHERE alert_id = :alert_id
                    """
                ),
                {
                    "officer_id": officer["user_id"],
                    "snapshot": json.dumps(officer_snapshot),
                    "assigned_at": datetime.utcnow(),
                    "status": "Dispatched",
                    "alert_id": alert_id
                }
            )

            linked_crime_id = alert_row.get("linked_crime_id")
            if linked_crime_id:
                conn.execute(
                    text(
                        """
                        UPDATE crime
                        SET status = 'Under Investigation', updated_at = :updated_at
                        WHERE crime_id = :crime_id
                        """
                    ),
                    {
                        "updated_at": datetime.utcnow(),
                        "crime_id": linked_crime_id
                    }
                )

        return {
            "message": "Emergency alert assigned successfully",
            "alert_id": alert_id,
            "officer_id": assignment.officer_id
        }
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Failed to assign officer to emergency: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to assign officer to emergency alert")

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
    try:
        with engine.begin() as conn:
            current = conn.execute(
                text("SELECT crime_id, status FROM crime WHERE crime_id = :crime_id FOR UPDATE"),
                {"crime_id": crime_id}
            ).mappings().fetchone()

            if not current:
                raise HTTPException(status_code=404, detail="Crime not found")

            ensure_status_history_table(conn)

            new_status_value = status_update.new_status.strip()
            notes_value = (status_update.notes or "").strip() or None
            changed_by_value = status_update.changed_by if status_update.changed_by is not None else None

            conn.execute(
                text(
                    """
                    UPDATE crime
                    SET status = :status, updated_at = :updated_at
                    WHERE crime_id = :crime_id
                    """
                ),
                {
                    "status": new_status_value,
                    "updated_at": datetime.utcnow(),
                    "crime_id": crime_id
                }
            )

            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO status_history (crime_id, new_status, notes, changed_by, changed_at)
                        VALUES (:crime_id, :new_status, :notes, :changed_by, :changed_at)
                        """
                    ),
                    {
                        "crime_id": crime_id,
                        "new_status": new_status_value,
                        "notes": notes_value,
                        "changed_by": changed_by_value,
                        "changed_at": datetime.utcnow()
                    }
                )
            except Exception:
                pass

        return {
            "message": "Crime status updated successfully",
            "crime_id": crime_id,
            "previous_status": current["status"],
            "new_status": new_status_value
        }
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Failed to update crime status: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(exc)}")

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

    def _sanitize_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    sanitized_name = _sanitize_text(station.station_name)
    sanitized_code = _sanitize_text(station.station_code)

    payload = {
        "station_name": sanitized_name,
        "station_code": sanitized_code,
        "address": _sanitize_text(station.address),
        "phone": _sanitize_text(station.phone),
        "email": _sanitize_text(station.email),
        "latitude": station.latitude,
        "longitude": station.longitude,
        "jurisdiction_area": _sanitize_text(station.jurisdiction_area),
        "officer_in_charge": _sanitize_text(station.officer_in_charge)
    }

    if not sanitized_name:
        raise HTTPException(status_code=422, detail="Station name is required")
    if not sanitized_code:
        raise HTTPException(status_code=422, detail="Station code is required")

    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT station_id FROM police_station WHERE station_code = :station_code LIMIT 1"),
                {"station_code": payload["station_code"]}
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="Station code already exists. Please use a unique code.")

            result = conn.execute(
                text(
                    """
                    INSERT INTO police_station (
                        station_name,
                        station_code,
                        address,
                        phone,
                        email,
                        latitude,
                        longitude,
                        jurisdiction_area,
                        officer_in_charge,
                        created_at
                    )
                    VALUES (
                        :station_name,
                        :station_code,
                        :address,
                        :phone,
                        :email,
                        :latitude,
                        :longitude,
                        :jurisdiction_area,
                        :officer_in_charge,
                        :created_at
                    )
                    """
                ),
                {
                    **payload,
                    "created_at": datetime.utcnow()
                }
            )

            station_id = result.lastrowid

        return {"message": "Police station added successfully", "station_id": station_id}
    except HTTPException:
        raise
    except IntegrityError as err:
        # Handle race condition duplicates gracefully
        if "station_code" in str(err.orig).lower():
            raise HTTPException(status_code=409, detail="Station code already exists. Please use a unique code.")
        raise HTTPException(status_code=500, detail="Failed to add police station due to database constraint")
    except Exception as e:
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
                    jurisdiction_area = :jurisdiction_area, officer_in_charge = :officer_in_charge
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
                    "jurisdiction_area": station.jurisdiction_area,
                    "officer_in_charge": station.officer_in_charge
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

@app.get("/api/admin/analytics")
async def get_admin_analytics(limit: int = Query(15, ge=1, le=100)):
    """Provide dashboard-ready analytics summary and recent activity."""
    limit = max(1, min(limit, 100))
    window_label = "30 days"
    open_statuses = ["Pending", "Under Investigation"]

    def summarize_change(current_window, previous_window):
        current_value = int(current_window or 0)
        previous_value = int(previous_window or 0)
        change = current_value - previous_value
        trend = "up" if change > 0 else "down" if change < 0 else "neutral"
        if previous_value > 0:
            percent = (change / previous_value) * 100
            delta_text = f"{change:+d} ({percent:+.1f}% vs prior {window_label})"
        else:
            if change > 0:
                delta_text = f"+{change} vs prior {window_label}"
            elif change < 0:
                delta_text = f"{change} vs prior {window_label}"
            else:
                delta_text = f"No change vs prior {window_label}"
        return delta_text, trend

    def serialize_timestamp(value):
        if isinstance(value, datetime):
            dt_value = value
        elif isinstance(value, date):
            dt_value = datetime.combine(value, datetime.min.time())
        else:
            try:
                dt_value = datetime.fromisoformat(str(value))
            except Exception:
                dt_value = datetime.utcnow()
        return dt_value, dt_value.isoformat()

    with engine.connect() as conn:
        try:
            # Crime metrics
            total_crimes = conn.execute(text("SELECT COUNT(*) FROM crime")).scalar() or 0
            crimes_recent_30 = conn.execute(
                text("SELECT COUNT(*) FROM crime WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
            ).scalar() or 0
            crimes_previous_30 = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM crime
                    WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
                      AND created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
                    """
                )
            ).scalar() or 0

            open_cases = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM crime
                    WHERE LOWER(status) IN ('pending', 'under investigation')
                    """
                )
            ).scalar() or 0
            open_recent_30 = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM crime
                    WHERE LOWER(status) IN ('pending', 'under investigation')
                      AND COALESCE(updated_at, created_at) >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                    """
                )
            ).scalar() or 0
            open_previous_30 = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM crime
                    WHERE LOWER(status) IN ('pending', 'under investigation')
                      AND COALESCE(updated_at, created_at) < DATE_SUB(NOW(), INTERVAL 30 DAY)
                      AND COALESCE(updated_at, created_at) >= DATE_SUB(NOW(), INTERVAL 60 DAY)
                    """
                )
            ).scalar() or 0

            # Missing persons
            active_missing = conn.execute(
                text("SELECT COUNT(*) FROM missing_person WHERE LOWER(status) = 'missing'")
            ).scalar() or 0
            missing_recent_30 = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM missing_person
                    WHERE LOWER(status) = 'missing'
                      AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                    """
                )
            ).scalar() or 0
            missing_previous_30 = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM missing_person
                    WHERE LOWER(status) = 'missing'
                      AND created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
                      AND created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
                    """
                )
            ).scalar() or 0

            # Users
            total_users = conn.execute(text("SELECT COUNT(*) FROM appuser")).scalar() or 0
            users_recent_30 = conn.execute(
                text("SELECT COUNT(*) FROM appuser WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
            ).scalar() or 0
            users_previous_30 = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM appuser
                    WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
                      AND created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
                    """
                )
            ).scalar() or 0

            # Wanted criminals
            active_wanted = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM wanted_criminal
                    WHERE COALESCE(LOWER(status), '') NOT IN ('captured', 'inactive')
                    """
                )
            ).scalar() or 0
            wanted_recent_30 = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM wanted_criminal
                    WHERE COALESCE(LOWER(status), '') NOT IN ('captured', 'inactive')
                      AND COALESCE(updated_at, created_at) >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                    """
                )
            ).scalar() or 0
            wanted_previous_30 = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM wanted_criminal
                    WHERE COALESCE(LOWER(status), '') NOT IN ('captured', 'inactive')
                      AND COALESCE(updated_at, created_at) < DATE_SUB(NOW(), INTERVAL 30 DAY)
                      AND COALESCE(updated_at, created_at) >= DATE_SUB(NOW(), INTERVAL 60 DAY)
                    """
                )
            ).scalar() or 0

            summary_cards = []

            delta_text, trend = summarize_change(crimes_recent_30, crimes_previous_30)
            summary_cards.append({
                "title": "Crime Reports",
                "value": int(total_crimes),
                "subtitle": f"Last {window_label}: {int(crimes_recent_30)} new",
                "delta": delta_text,
                "trend": trend,
                "icon": "🚨"
            })

            delta_text, trend = summarize_change(open_recent_30, open_previous_30)
            summary_cards.append({
                "title": "Open Cases",
                "value": int(open_cases),
                "subtitle": f"Active statuses: {', '.join(open_statuses)}",
                "delta": delta_text,
                "trend": trend,
                "icon": "📂"
            })

            delta_text, trend = summarize_change(users_recent_30, users_previous_30)
            summary_cards.append({
                "title": "Registered Users",
                "value": int(total_users),
                "subtitle": f"Last {window_label}: {int(users_recent_30)} joined",
                "delta": delta_text,
                "trend": trend,
                "icon": "👥"
            })

            delta_text, trend = summarize_change(missing_recent_30, missing_previous_30)
            summary_cards.append({
                "title": "Active Missing Persons",
                "value": int(active_missing),
                "subtitle": f"Last {window_label}: {int(missing_recent_30)} new",
                "delta": delta_text,
                "trend": trend,
                "icon": "🆘"
            })

            delta_text, trend = summarize_change(wanted_recent_30, wanted_previous_30)
            summary_cards.append({
                "title": "Wanted Individuals",
                "value": int(active_wanted),
                "subtitle": f"Last {window_label}: {int(wanted_recent_30)} updated",
                "delta": delta_text,
                "trend": trend,
                "icon": "🎯"
            })

            per_category = limit // 3
            if per_category < 3:
                per_category = min(limit, 3)
            if per_category < 1:
                per_category = 1
            activity_entries = []

            crime_rows = conn.execute(
                text(
                    """
                    SELECT crime_id, status, created_at, updated_at,
                           JSON_UNQUOTE(JSON_EXTRACT(crime_data, '$.type')) AS crime_type,
                           JSON_UNQUOTE(JSON_EXTRACT(crime_data, '$.description')) AS description,
                           JSON_UNQUOTE(JSON_EXTRACT(location_data, '$.area_name')) AS area_name
                    FROM crime
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": per_category}
            ).mappings().fetchall()

            for row in crime_rows:
                timestamp_obj, timestamp_iso = serialize_timestamp(row.get("updated_at") or row.get("created_at"))
                reference_id = row.get("crime_id")
                ref_int = int(reference_id) if reference_id is not None else None
                base_title = f"Case CR-{ref_int:03d}" if ref_int is not None else "Crime Report"
                description = row.get("description") or row.get("crime_type") or "Crime report"
                area_name = row.get("area_name")
                if area_name:
                    description = f"{description} in {area_name}"
                activity_entries.append((
                    timestamp_obj,
                    {
                        "type": "Crime Report",
                        "title": base_title,
                        "description": description,
                        "reference_id": ref_int,
                        "status": row.get("status") or "Pending",
                        "timestamp": timestamp_iso
                    }
                ))

            missing_rows = conn.execute(
                text(
                    """
                    SELECT missing_id, name, status, created_at, updated_at, last_seen_location
                    FROM missing_person
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": per_category}
            ).mappings().fetchall()

            for row in missing_rows:
                timestamp_obj, timestamp_iso = serialize_timestamp(row.get("updated_at") or row.get("created_at"))
                reference_id = row.get("missing_id")
                ref_int = int(reference_id) if reference_id is not None else None
                location_hint = row.get("last_seen_location") or "Location unknown"
                activity_entries.append((
                    timestamp_obj,
                    {
                        "type": "Missing Person",
                        "title": row.get("name") or "Missing report",
                        "description": f"Last seen at {location_hint}",
                        "reference_id": ref_int,
                        "status": row.get("status") or "Missing",
                        "timestamp": timestamp_iso
                    }
                ))

            wanted_rows = conn.execute(
                text(
                    """
                    SELECT criminal_id, name, status, created_at, updated_at, last_known_location, danger_level
                    FROM wanted_criminal
                    ORDER BY COALESCE(updated_at, created_at) DESC
                    LIMIT :limit
                    """
                ),
                {"limit": per_category}
            ).mappings().fetchall()

            for row in wanted_rows:
                timestamp_obj, timestamp_iso = serialize_timestamp(row.get("updated_at") or row.get("created_at"))
                reference_id = row.get("criminal_id")
                ref_int = int(reference_id) if reference_id is not None else None
                location_hint = row.get("last_known_location") or "Unknown location"
                danger = row.get("danger_level")
                description = f"Last known at {location_hint}" if location_hint else "Location unknown"
                if danger:
                    description = f"{description} - Danger: {danger}"
                activity_entries.append((
                    timestamp_obj,
                    {
                        "type": "Wanted Criminal",
                        "title": row.get("name") or "Wanted individual",
                        "description": description,
                        "reference_id": ref_int,
                        "status": row.get("status") or "Active",
                        "timestamp": timestamp_iso
                    }
                ))

            activity_entries.sort(key=lambda item: item[0], reverse=True)
            activity_payload = [entry for _, entry in activity_entries[:limit]]

            return {"summary_cards": summary_cards, "activity": activity_payload}
        except Exception as exc:
            logging.exception("Error building admin analytics: %s", exc)
            return {"summary_cards": [], "activity": []}

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

@app.get("/api/admin/cases/{crime_id}/history")
async def get_case_status_history(crime_id: int):
    """Return status history and assignment timeline for a given crime case."""
    with engine.connect() as conn:
        try:
            try:
                ensure_status_history_table(conn)
            except Exception as exc:  # pragma: no cover - table creation expected to succeed
                logging.warning("Failed to ensure status_history table exists: %s", exc)

            crime_row = conn.execute(
                text(
                    """
                    SELECT
                        c.crime_id,
                        c.status,
                        c.created_at,
                        c.updated_at,
                        JSON_UNQUOTE(JSON_EXTRACT(c.crime_data, '$.type')) AS crime_type,
                        JSON_UNQUOTE(JSON_EXTRACT(c.crime_data, '$.description')) AS crime_description,
                        JSON_UNQUOTE(JSON_EXTRACT(c.location_data, '$.area_name')) AS area_name
                    FROM crime c
                    WHERE c.crime_id = :crime_id
                    """
                ),
                {"crime_id": crime_id}
            ).mappings().fetchone()

            if not crime_row:
                raise HTTPException(status_code=404, detail="Crime case not found")

            status_rows = conn.execute(
                text(
                    """
                    SELECT
                        sh.history_id,
                        sh.new_status,
                        sh.notes,
                        sh.changed_by,
                        sh.changed_at,
                        u.full_name AS changed_by_name,
                        u.role_hint AS changed_by_role
                    FROM status_history sh
                    LEFT JOIN appuser u ON u.user_id = sh.changed_by
                    WHERE sh.crime_id = :crime_id
                    ORDER BY sh.changed_at ASC, sh.history_id ASC
                    """
                ),
                {"crime_id": crime_id}
            ).mappings().fetchall()

            assignment_rows = conn.execute(
                text(
                    """
                    SELECT
                        ca.assignment_id,
                        ca.user_id,
                        ca.duty_role,
                        ca.assigned_at,
                        ca.status,
                        ca.notes,
                        ca.completion_date,
                        u.full_name AS officer_name,
                        u.role_hint AS officer_role
                    FROM case_assignments ca
                    LEFT JOIN appuser u ON u.user_id = ca.user_id
                    WHERE ca.crime_id = :crime_id
                    ORDER BY ca.assigned_at ASC, ca.assignment_id ASC
                    """
                ),
                {"crime_id": crime_id}
            ).mappings().fetchall()

            def isoformat(value):
                if value is None:
                    return None
                if isinstance(value, datetime):
                    return value.isoformat()
                if isinstance(value, date):
                    return datetime.combine(value, datetime.min.time()).isoformat()
                return str(value)

            status_events = [
                {
                    "history_id": row.get("history_id"),
                    "new_status": row.get("new_status"),
                    "notes": row.get("notes"),
                    "changed_by": row.get("changed_by"),
                    "changed_by_name": row.get("changed_by_name"),
                    "changed_by_role": row.get("changed_by_role"),
                    "changed_at": isoformat(row.get("changed_at")),
                }
                for row in status_rows
            ]

            assignment_events = [
                {
                    "assignment_id": row.get("assignment_id"),
                    "user_id": row.get("user_id"),
                    "duty_role": row.get("duty_role"),
                    "assigned_at": isoformat(row.get("assigned_at")),
                    "status": row.get("status"),
                    "notes": row.get("notes"),
                    "completion_date": isoformat(row.get("completion_date")),
                    "officer_name": row.get("officer_name"),
                    "officer_role": row.get("officer_role"),
                }
                for row in assignment_rows
            ]

            timeline_entries = []
            for event in status_events:
                timeline_entries.append(
                    {
                        "kind": "status",
                        "label": event.get("new_status"),
                        "notes": event.get("notes"),
                        "actor": event.get("changed_by_name") or event.get("changed_by"),
                        "role": event.get("changed_by_role"),
                        "timestamp": event.get("changed_at"),
                    }
                )

            for event in assignment_events:
                officer_label = event.get("officer_name") or f"Officer #{event.get('user_id')}"
                timeline_entries.append(
                    {
                        "kind": "assignment",
                        "label": officer_label,
                        "notes": event.get("duty_role"),
                        "actor": officer_label,
                        "role": event.get("officer_role"),
                        "timestamp": event.get("assigned_at"),
                    }
                )

            def parse_ts(value):
                if not value:
                    return datetime.min
                try:
                    return datetime.fromisoformat(value)
                except Exception:
                    try:
                        return datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except Exception:
                        return datetime.min

            timeline_entries.sort(key=lambda item: (parse_ts(item.get("timestamp")), item.get("kind")))

            return {
                "crime": {
                    "crime_id": crime_row.get("crime_id"),
                    "status": crime_row.get("status"),
                    "reported_at": isoformat(crime_row.get("created_at")),
                    "updated_at": isoformat(crime_row.get("updated_at")),
                    "crime_type": crime_row.get("crime_type"),
                    "crime_description": crime_row.get("crime_description"),
                    "area_name": crime_row.get("area_name"),
                },
                "status_events": status_events,
                "assignment_events": assignment_events,
                "timeline": timeline_entries,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logging.exception("Failed to fetch status history for crime %s: %s", crime_id, exc)
            raise HTTPException(status_code=500, detail="Failed to fetch case history")

@app.get("/api/admin/complaints")
async def get_admin_complaints(limit: int = Query(200, ge=1, le=500)):
    """Fetch recent user complaints for verification workflow."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    complaint_id,
                    reporter_contact,
                    channel,
                    status,
                    priority,
                    assigned_to,
                    verification_notes,
                    complaint_data,
                    created_at,
                    updated_at
                FROM user_complaints
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit}
        ).mappings().fetchall()

    complaints = []
    for row in rows:
        item = dict(row)
        payload = parse_json_value(item.get("complaint_data")) or {}
        item["complaint_data"] = payload if payload else None
        item["status"] = item.get("status") or "Pending"
        # Provide normalized structures expected by the dashboard UI
        crime_payload = item.get("crime_data")
        if not isinstance(crime_payload, dict):
            item["crime_data"] = {
                "type": payload.get("subject") or payload.get("type") or "User Complaint",
                "description": payload.get("description") or payload.get("details") or "",
                "reporter_contact": item.get("reporter_contact") or payload.get("reporter_contact")
            }
        location_hint = (
            payload.get("location")
            or payload.get("location_label")
            or payload.get("address")
            or payload.get("area")
        )
        if location_hint and not item.get("location_data"):
            item["location_data"] = {"area_name": location_hint}
        complaints.append(item)

    return {"complaints": complaints}

@app.post("/api/admin/complaints/{complaint_id}/verify")
async def verify_user_complaint(complaint_id: int, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Mark a complaint as verified."""
    notes = None
    if payload:
        notes = payload.get("notes") or payload.get("verification_notes")

    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE user_complaints
                SET status = 'Verified',
                    verification_notes = COALESCE(:notes, verification_notes),
                    updated_at = :updated_at
                WHERE complaint_id = :complaint_id
                """
            ),
            {
                "complaint_id": complaint_id,
                "notes": notes,
                "updated_at": datetime.utcnow()
            }
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Complaint not found")

    return {"message": "Complaint verified"}

@app.post("/api/admin/complaints/{complaint_id}/reject")
async def reject_user_complaint(complaint_id: int, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Reject a complaint and record the reason if provided."""
    notes = None
    if payload:
        notes = payload.get("notes") or payload.get("verification_notes") or payload.get("reason")

    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE user_complaints
                SET status = 'Rejected',
                    verification_notes = COALESCE(:notes, verification_notes),
                    updated_at = :updated_at
                WHERE complaint_id = :complaint_id
                """
            ),
            {
                "complaint_id": complaint_id,
                "notes": notes,
                "updated_at": datetime.utcnow()
            }
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Complaint not found")

    return {"message": "Complaint rejected"}

@app.post("/api/admin/complaints/{complaint_id}/escalate")
async def escalate_complaint_to_case(complaint_id: int, payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Create a crime record from a verified complaint and mark it escalated."""
    with engine.begin() as conn:
        complaint = conn.execute(
            text(
                """
                SELECT complaint_id, reporter_contact, complaint_data, status, priority
                FROM user_complaints
                WHERE complaint_id = :complaint_id
                FOR UPDATE
                """
            ),
            {"complaint_id": complaint_id}
        ).mappings().fetchone()

        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        status_value = (complaint.get("status") or "").lower()
        if status_value == "escalated":
            return {"message": "Complaint already escalated"}

        if status_value not in {"verified", "pending"}:
            raise HTTPException(status_code=400, detail="Complaint cannot be escalated in its current status")

        complaint_payload = parse_json_value(complaint.get("complaint_data")) or {}
        subject = complaint_payload.get("subject") or complaint_payload.get("type") or "User Complaint"
        description = complaint_payload.get("description") or complaint_payload.get("details") or "Escalated user complaint"
        location_hint = (
            complaint_payload.get("location")
            or complaint_payload.get("address")
            or complaint_payload.get("area")
            or complaint_payload.get("location_label")
        )

        priority_raw = (complaint.get("priority") or payload.get("priority") if payload else "") or "Medium"
        priority_value = str(priority_raw).strip().title()
        if priority_value not in {"Low", "Medium", "High", "Critical"}:
            priority_value = "Medium"

        now = datetime.utcnow()
        crime_insert = conn.execute(
            text(
                """
                INSERT INTO crime (reporter_id, crime_data, location_data, status, priority_level, incident_date, created_at, updated_at)
                VALUES (:reporter_id, :crime_data, :location_data, :status, :priority_level, :incident_date, :created_at, :updated_at)
                """
            ),
            {
                "reporter_id": None,
                "crime_data": json.dumps({
                    "type": subject,
                    "description": description,
                    "source": "user-complaint",
                    "source_complaint_id": complaint_id,
                    "reporter_contact": complaint.get("reporter_contact") or complaint_payload.get("reporter_contact"),
                }),
                "location_data": json.dumps({"area_name": location_hint} if location_hint else {}),
                "status": "Escalated",
                "priority_level": priority_value,
                "incident_date": None,
                "created_at": now,
                "updated_at": now,
            }
        )

        new_crime_id = crime_insert.lastrowid

        ensure_status_history_table(conn)
        try:
            conn.execute(
                text(
                    """
                    INSERT INTO status_history (crime_id, new_status, notes, changed_by, changed_at)
                    VALUES (:crime_id, :new_status, :notes, :changed_by, :changed_at)
                    """
                ),
                {
                    "crime_id": new_crime_id,
                    "new_status": "Escalated",
                    "notes": "Escalated from user complaint",
                    "changed_by": payload.get("changed_by") if payload else None,
                    "changed_at": now,
                }
            )
        except Exception:
            pass

        conn.execute(
            text(
                """
                UPDATE user_complaints
                SET status = 'Escalated',
                    updated_at = :updated_at
                WHERE complaint_id = :complaint_id
                """
            ),
            {
                "complaint_id": complaint_id,
                "updated_at": now,
            }
        )

    return {
        "message": "Complaint escalated to case management",
        "crime_id": new_crime_id
    }


@app.post("/api/admin/complaints/from-crime/{crime_id}")
async def convert_crime_to_complaint(crime_id: int):
    """Create a user_complaints row from an existing crime so it can be verified/rejected via the complaints workflow."""
    with engine.begin() as conn:
        crime_row = conn.execute(
            text(
                "SELECT crime_id, reporter_id, crime_data, location_data, status, priority_level, created_at FROM crime WHERE crime_id = :crime_id FOR UPDATE"
            ),
            {"crime_id": crime_id}
        ).mappings().fetchone()

        if not crime_row:
            raise HTTPException(status_code=404, detail="Crime not found")

        # Build complaint_data from crime_data if possible
        crime_payload = parse_json_value(crime_row.get("crime_data")) or {}
        location_payload = parse_json_value(crime_row.get("location_data")) or {}

        complaint_data = {
            "subject": crime_payload.get("type") or crime_payload.get("subject") or "Mapped Crime",
            "description": crime_payload.get("description") or crime_payload.get("details") or "",
            "location": location_payload or crime_payload.get("location") or crime_payload.get("location_label")
        }

        now = datetime.utcnow()

        # Insert into user_complaints
        insert = conn.execute(
            text(
                "INSERT INTO user_complaints (reporter_contact, channel, status, priority, complaint_data, created_at, updated_at) VALUES (:reporter_contact, :channel, :status, :priority, :complaint_data, :created_at, :updated_at)"
            ),
            {
                "reporter_contact": crime_payload.get("reporter_contact") or None,
                "channel": crime_payload.get("source") or "Mapped",
                "status": "Pending",
                "priority": crime_row.get("priority_level") or crime_payload.get("priority") or "Medium",
                "complaint_data": json.dumps(complaint_data),
                "created_at": crime_row.get("created_at") or now,
                "updated_at": now
            }
        )

        new_complaint_id = insert.lastrowid

        return {
            "message": "Converted crime to complaint",
            "complaint_id": new_complaint_id
        }

@app.get("/api/admin/case-management")
async def get_case_management_cases():
    """Return crimes under investigation along with assignment details."""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text(
                    """
                    SELECT
                        c.crime_id,
                        c.status AS crime_status,
                        c.created_at,
                        c.updated_at,
                        JSON_UNQUOTE(JSON_EXTRACT(c.crime_data, '$.type')) AS crime_type,
                        JSON_UNQUOTE(JSON_EXTRACT(c.crime_data, '$.description')) AS crime_description,
                        JSON_UNQUOTE(JSON_EXTRACT(c.location_data, '$.area_name')) AS area_name,
                        ca.assignment_id,
                        ca.user_id,
                        ca.duty_role,
                        ca.assigned_at,
                        ca.status AS assignment_status,
                        u.username,
                        u.full_name,
                        u.email
                    FROM crime c
                    LEFT JOIN case_assignments ca ON ca.crime_id = c.crime_id
                    LEFT JOIN appuser u ON ca.user_id = u.user_id
                    WHERE LOWER(c.status) IN ('under investigation', 'investigating', 'in progress', 'assigned', 'escalated')
                    ORDER BY COALESCE(ca.assigned_at, c.updated_at, c.created_at) DESC
                    """
                )
            ).mappings().fetchall()

            return {"cases": [dict(row) for row in result]}
        except Exception as exc:
            logging.exception("Error fetching case management cases: %s", exc)
            return {"cases": []}

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