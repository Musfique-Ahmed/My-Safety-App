import os
from datetime import datetime, date
from typing import Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import fetch_all, fetch_one, execute, parse_json_field, insert_and_get_id


app = FastAPI(title="My Safety App API")

# CORS (allow local dev)
origins = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins including file:// (origin "null")
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return {"message": "My Safety App API running"}


def _normalize_status(value: str | None) -> str:
    if not value:
        return "pending"
    return value.replace(" ", "_").lower()


def _parse_json_fields(rows: list[dict], keys: list[str]) -> list[dict]:
    if not rows:
        return rows
    out: list[dict] = []
    for r in rows:
        new_r = dict(r)
        for k in keys:
            if k in new_r:
                new_r[k] = parse_json_field(new_r.get(k))
        out.append(new_r)
    return out


@app.get("/api/crimes")
def get_crimes():
    sql = (
        "SELECT crime_id, status, crime_data, location_data "
        "FROM crime ORDER BY created_at DESC LIMIT 200"
    )
    rows = fetch_all(sql)
    crimes: list[dict[str, Any]] = []
    for r in rows:
        crimes.append(
            {
                "crime_id": r["crime_id"],
                "status": _normalize_status(r.get("status")),
                "crime_data": parse_json_field(r.get("crime_data")),
                "location_data": parse_json_field(r.get("location_data")),
            }
        )
    return {"crimes": crimes}


@app.get("/api/admin/users")
def get_users():
    sql = (
        "SELECT user_id, username, email, role_hint, status, created_at "
        "FROM appuser ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "users": fetch_all(sql)}


@app.get("/api/admin/wanted-criminals")
def get_wanted_criminals():
    sql = (
        "SELECT criminal_id, name, alias, crimes_committed, danger_level, reward_amount, status "
        "FROM wanted_criminal ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "criminals": fetch_all(sql)}


@app.get("/api/admin/police-stations")
def get_police_stations():
    sql = (
        "SELECT station_id, station_name, station_code, address, phone, email, jurisdiction_area "
        "FROM police_station ORDER BY station_name"
    )
    return {"success": True, "stations": fetch_all(sql)}


@app.get("/api/admin/missing-persons")
def get_missing_persons():
    sql = (
        "SELECT missing_id, name, age, gender, last_seen_location, last_seen_date, status "
        "FROM missing_person ORDER BY updated_at DESC LIMIT 200"
    )
    persons = fetch_all(sql)
    # Normalize status for UI badge class
    for p in persons:
        p["status"] = p.get("status") or "Missing"
    return {"success": True, "missing_persons": persons}


@app.get("/api/admin/complaints")
def get_complaints():
    sql = (
        "SELECT complaint_id, reporter_contact, channel, status, created_at "
        "FROM user_complaints ORDER BY created_at DESC LIMIT 200"
    )
    comps = fetch_all(sql)
    # Map status to lowercase expected by UI
    for c in comps:
        c["status"] = (c.get("status") or "Pending").lower()
        c["reported_at"] = c.pop("created_at")
    return {"success": True, "complaints": comps}


@app.post("/api/admin/complaints/{complaint_id}/verify")
def verify_complaint(complaint_id: int):
    rowcount = execute(
        "UPDATE user_complaints SET status='Verified', updated_at=NOW() WHERE complaint_id=%s",
        (complaint_id,),
    )
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {"success": True}


@app.post("/api/admin/complaints/{complaint_id}/reject")
def reject_complaint(complaint_id: int):
    rowcount = execute(
        "UPDATE user_complaints SET status='Rejected', updated_at=NOW() WHERE complaint_id=%s",
        (complaint_id,),
    )
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {"success": True}


@app.get("/api/admin/case-assignments")
def get_case_assignments():
    sql = (
        "SELECT ca.assignment_id, ca.crime_id, ca.duty_role, ca.assigned_at, ca.status, "
        "       u.full_name, u.username "
        "FROM case_assignments ca LEFT JOIN appuser u ON ca.user_id = u.user_id "
        "ORDER BY ca.assigned_at DESC LIMIT 200"
    )
    assigns = fetch_all(sql)
    # Normalize status for UI class
    for a in assigns:
        a["status"] = (a.get("status") or "Active").replace(" ", "_")
    return {"success": True, "assignments": assigns}


@app.get("/api/admin/analytics")
def get_analytics():
    total_crimes = fetch_one("SELECT COUNT(*) AS c FROM crime")["c"]
    pending_crimes = fetch_one(
        "SELECT COUNT(*) AS c FROM crime WHERE status IN ('Pending','Under Investigation','Emergency')"
    )["c"]
    total_users = fetch_one("SELECT COUNT(*) AS c FROM appuser")["c"]
    total_missing = fetch_one("SELECT COUNT(*) AS c FROM missing_person")["c"]
    total_wanted = fetch_one("SELECT COUNT(*) AS c FROM wanted_criminal WHERE status='Active'")["c"]

    recent_activity = fetch_all(
        "SELECT activity_type, details, created_at FROM activity_log ORDER BY created_at DESC LIMIT 10"
    )
    return {
        "success": True,
        "analytics": {
            "total_crimes": total_crimes,
            "pending_crimes": pending_crimes,
            "total_users": total_users,
            "total_missing": total_missing,
            "total_wanted": total_wanted,
            "recent_activity": recent_activity,
        },
    }


# ---------------- Additional datasets (read-only) ----------------

@app.get("/api/admin/activity-log")
def get_activity_log():
    sql = (
        "SELECT log_id, activity_type, item_id, details, performed_by, created_at "
        "FROM activity_log ORDER BY created_at DESC LIMIT 200"
    )
    rows = fetch_all(sql)
    return {"success": True, "activity_log": rows}


@app.get("/api/admin/admin-activity-log")
def get_admin_activity_log():
    sql = (
        "SELECT log_id, admin_id, action_type, target_table, target_id, action_details, ip_address, user_agent, created_at "
        "FROM admin_activity_log ORDER BY created_at DESC LIMIT 200"
    )
    rows = _parse_json_fields(fetch_all(sql), ["action_details"])
    return {"success": True, "admin_activity_log": rows}


@app.get("/api/admin/api-logs")
def get_api_logs():
    sql = (
        "SELECT log_id, endpoint, method, user_id, ip_address, request_data, response_status, response_time_ms, error_message, created_at "
        "FROM api_logs ORDER BY created_at DESC LIMIT 200"
    )
    rows = _parse_json_fields(fetch_all(sql), ["request_data"])
    return {"success": True, "api_logs": rows}


@app.get("/api/admin/appusers")
def get_appusers():
    sql = (
        "SELECT user_id, username, email, full_name, phone, address, role_hint, status, station_id, profile_picture_url, date_of_birth, gender, emergency_contact, created_at, updated_at, last_login "
        "FROM appuser ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "users": fetch_all(sql)}


@app.get("/api/admin/chat-messages")
def get_chat_messages():
    sql = (
        "SELECT message_id, user_id, message, report_id, is_admin, read_by_admin, read_by_user, created_at "
        "FROM chat_messages ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "chat_messages": fetch_all(sql)}


@app.get("/api/admin/complaints-legacy")
def get_complaints_legacy():
    sql = (
        "SELECT complaint_id, reporter_contact, complaint_text, channel, status, verified_by, created_at, verified_at "
        "FROM complaints ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "complaints": fetch_all(sql)}


@app.get("/api/admin/criminal-sightings")
def get_criminal_sightings():
    sql = (
        "SELECT sighting_id, criminal_id, last_seen_time, last_seen_location, still_with_finder, reporter_contact, verified, created_at "
        "FROM criminal_sightings ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "criminal_sightings": fetch_all(sql)}


@app.get("/api/admin/evidence-files")
def get_evidence_files():
    sql = (
        "SELECT file_id, crime_id, file_name, file_path, file_type, file_size, uploaded_by, description, created_at "
        "FROM evidence_files ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "evidence_files": fetch_all(sql)}


@app.get("/api/admin/file-uploads")
def get_file_uploads():
    sql = (
        "SELECT upload_id, original_filename, stored_filename, file_path, file_type, file_size, uploaded_by, related_table, related_id, upload_purpose, created_at "
        "FROM file_uploads ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "file_uploads": fetch_all(sql)}


@app.get("/api/admin/notifications")
def get_notifications():
    sql = (
        "SELECT notification_id, user_id, title, message, type, is_read, related_table, related_id, created_at "
        "FROM notifications ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "notifications": fetch_all(sql)}


@app.get("/api/admin/status-history")
def get_status_history():
    sql = (
        "SELECT history_id, crime_id, new_status, notes, changed_by, changed_at "
        "FROM status_history ORDER BY changed_at DESC LIMIT 200"
    )
    return {"success": True, "status_history": fetch_all(sql)}


@app.get("/api/admin/system-settings")
def get_system_settings():
    sql = (
        "SELECT setting_id, setting_key, setting_value, setting_type, description, is_public, updated_by, created_at, updated_at "
        "FROM system_settings ORDER BY setting_key LIMIT 500"
    )
    return {"success": True, "system_settings": fetch_all(sql)}


@app.get("/api/admin/user-complaints")
def get_user_complaints():
    sql = (
        "SELECT complaint_id, reporter_contact, complaint_data, channel, status, priority, assigned_to, verification_notes, created_at, updated_at "
        "FROM user_complaints ORDER BY created_at DESC LIMIT 200"
    )
    rows = _parse_json_fields(fetch_all(sql), ["complaint_data"])
    # normalize status to lowercase for UI if needed
    for c in rows:
        c["status"] = (c.get("status") or "Pending").lower()
    return {"success": True, "user_complaints": rows}


@app.get("/api/admin/user-sessions")
def get_user_sessions():
    sql = (
        "SELECT session_id, user_id, login_time, logout_time, ip_address, user_agent, is_active, expires_at "
        "FROM user_sessions ORDER BY login_time DESC LIMIT 200"
    )
    return {"success": True, "user_sessions": fetch_all(sql)}


@app.get("/api/admin/active-cases")
def get_active_cases_view():
    sql = (
        "SELECT crime_id, reporter_id, reporter_name, crime_type, city, area, status, priority_level, incident_date, created_at "
        "FROM active_cases ORDER BY created_at DESC LIMIT 200"
    )
    return {"success": True, "active_cases": fetch_all(sql)}


@app.get("/api/admin/officer-workload")
def get_officer_workload_view():
    sql = (
        "SELECT user_id, full_name, role_hint, station_name, active_assignments "
        "FROM officer_workload ORDER BY active_assignments DESC, full_name LIMIT 200"
    )
    return {"success": True, "officer_workload": fetch_all(sql)}


from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, MetaData, Column, Integer, String, Enum, DateTime, Text, Date, Time, JSON
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import pymysql

# Pydantic models for request bodies
class PoliceStationCreate(BaseModel):
    station_name: str
    station_code: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    jurisdiction_area: str | None = None

class WantedCriminalCreate(BaseModel):
    name: str
    alias: str | None = None
    age_range: str | None = None
    gender: str | None = None
    description: str = ""
    crimes_committed: str = ""
    danger_level: str = "Medium"
    reward_amount: int | None = None
    last_known_location: str | None = None
    photo_url: str | None = None
    added_by: int = 1
    status: str = "Active"

class CaseAssignmentCreate(BaseModel):
    crime_id: int
    user_id: int
    duty_role: str

class CrimeCreate(BaseModel):
    reporter_id: int | None = None
    crime_data: str
    location_data: str
    status: str = "Pending"
    priority_level: str = "Medium"

# Database Configuration
DATABASE_URL = "mysql+pymysql://root:@localhost/mysafetydb"  # Modify as per your database credentials

# FastAPI App Initialization
# Reuse the previously created FastAPI app instance above

# SQLAlchemy Database Setup
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define the table models (using SQLAlchemy ORM) for all the tables
# Example for "activity_log" table:
class ActivityLog(Base):
    __tablename__ = "activity_log"
    log_id = Column(Integer, primary_key=True, index=True)
    activity_type = Column(Enum('Crime Report', 'Missing Person', 'User Registration', 'Status Update', 'Verification'), nullable=False)
    item_id = Column(Integer, nullable=False)
    details = Column(Text, nullable=True)
    performed_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())

class AdminActivityLog(Base):
    __tablename__ = "admin_activity_log"
    log_id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, nullable=False)
    action_type = Column(String(100), nullable=False)
    target_table = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    action_details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

class CaseAssignments(Base):
    __tablename__ = "case_assignments"
    assignment_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    crime_id = Column(Integer, nullable=False)
    duty_role = Column(String(100), nullable=False)
    assigned_at = Column(DateTime, default=func.now())
    assigned_by = Column(Integer, nullable=True)
    status = Column(Enum('Active', 'Completed', 'Reassigned', 'Cancelled'), default='Active')
    notes = Column(Text, nullable=True)
    completion_date = Column(DateTime, nullable=True)

class ChatMessages(Base):
    __tablename__ = "chat_messages"
    message_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    message = Column(Text, nullable=False)
    report_id = Column(String(50), nullable=True)
    is_admin = Column(Integer, default=0)
    read_by_admin = Column(Integer, default=0)
    read_by_user = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())

class Complaints(Base):
    __tablename__ = "complaints"
    complaint_id = Column(Integer, primary_key=True, index=True)
    reporter_contact = Column(String(255), nullable=False)
    complaint_text = Column(Text, nullable=False)
    channel = Column(Enum('Web Form', 'Phone Call', 'Mobile App', 'Email'), default='Web Form')
    status = Column(Enum('pending', 'verified', 'rejected'), default='pending')
    verified_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    verified_at = Column(DateTime, nullable=True)

class Crime(Base):
    __tablename__ = "crime"
    crime_id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, nullable=True)
    crime_data = Column(Text, nullable=False)
    victim_data = Column(Text, nullable=True)
    criminal_data = Column(Text, nullable=True)
    weapon_data = Column(Text, nullable=True)
    location_data = Column(Text, nullable=False)
    status = Column(Enum('Pending', 'Under Investigation', 'Resolved', 'Closed', 'Emergency', 'Reported'), default='Pending')
    priority_level = Column(Enum('Low', 'Medium', 'High', 'Critical'), default='Medium')
    incident_date = Column(DateTime, nullable=True)
    evidence_files = Column(Text, nullable=True)
    witness_info = Column(Text, nullable=True)
    witness_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class CriminalSightings(Base):
    __tablename__ = "criminal_sightings"
    sighting_id = Column(Integer, primary_key=True, index=True)
    criminal_id = Column(Integer, nullable=False)
    last_seen_time = Column(DateTime, nullable=False)
    last_seen_location = Column(Text, nullable=False)
    still_with_finder = Column(Integer, default=0)
    reporter_contact = Column(String(255), nullable=True)
    verified = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())

class EvidenceFiles(Base):
    __tablename__ = "evidence_files"
    file_id = Column(Integer, primary_key=True, index=True)
    crime_id = Column(Integer, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

class FileUploads(Base):
    __tablename__ = "file_uploads"
    upload_id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_by = Column(Integer, nullable=False)
    related_table = Column(String(50), nullable=True)
    related_id = Column(Integer, nullable=True)
    upload_purpose = Column(Enum('crime_evidence', 'profile_picture', 'missing_person_photo', 'criminal_photo', 'other'), default='other')
    created_at = Column(DateTime, default=func.now())

class MissingPerson(Base):
    __tablename__ = "missing_person"
    missing_id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, nullable=True)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(Enum('M', 'F', 'O'), nullable=True)
    description = Column(Text, nullable=True)
    last_seen_location = Column(String(500), nullable=True)
    last_seen_date = Column(Date, nullable=True)
    last_seen_time = Column(Time, nullable=True)
    height = Column(String(20), nullable=True)
    weight = Column(String(20), nullable=True)
    hair_color = Column(String(50), nullable=True)
    eye_color = Column(String(50), nullable=True)
    distinguishing_marks = Column(Text, nullable=True)
    clothing_description = Column(Text, nullable=True)
    contact_person = Column(String(200), nullable=True)
    contact_phone = Column(String(30), nullable=True)
    contact_info = Column(String(255), nullable=True)
    photo_url = Column(String(500), nullable=True)
    evidence_files = Column(Text, nullable=True)
    status = Column(String(50), default='Missing', nullable=False)
    police_case_number = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class PoliceStation(Base):
    __tablename__ = "police_station"
    station_id = Column(Integer, primary_key=True, index=True)
    station_name = Column(String(200), nullable=False)
    station_code = Column(String(20), nullable=False)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(150), nullable=True)
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    jurisdiction_area = Column(Text, nullable=True)
    officer_in_charge = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class WantedCriminal(Base):
    __tablename__ = "wanted_criminal"
    criminal_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    alias = Column(String(200), nullable=True)
    age_range = Column(String(20), nullable=True)
    gender = Column(Enum('M','F','O'), nullable=True)
    description = Column(Text, nullable=False)
    height = Column(String(20), nullable=True)
    weight = Column(String(20), nullable=True)
    hair_color = Column(String(50), nullable=True)
    eye_color = Column(String(50), nullable=True)
    distinguishing_marks = Column(Text, nullable=True)
    crimes_committed = Column(Text, nullable=False)
    reward_amount = Column(Integer, nullable=True)
    danger_level = Column(Enum('Low','Medium','High','Extreme'), default='Medium')
    last_known_location = Column(String(500), nullable=True)
    photo_url = Column(String(500), nullable=True)
    wanted_since = Column(Date, nullable=True)
    added_by = Column(Integer, nullable=False, default=1)
    status = Column(Enum('Active','Captured','Inactive'), default='Active')
    capture_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# --- CRUD for ActivityLog Table ---
@app.get("/activity_log/{log_id}")
def read_activity_log(log_id: int, db: Session = Depends(get_db)):
    db_log = db.query(ActivityLog).filter(ActivityLog.log_id == log_id).first()
    if db_log is None:
        raise HTTPException(status_code=404, detail="Activity log not found")
    return db_log

@app.post("/activity_log/")
def create_activity_log(activity_type: str, item_id: int, details: str, performed_by: int, db: Session = Depends(get_db)):
    db_activity_log = ActivityLog(
        activity_type=activity_type, item_id=item_id, details=details, performed_by=performed_by
    )
    db.add(db_activity_log)
    db.commit()
    db.refresh(db_activity_log)
    return db_activity_log

@app.put("/activity_log/{log_id}")
def update_activity_log(log_id: int, activity_type: str, details: str, db: Session = Depends(get_db)):
    db_log = db.query(ActivityLog).filter(ActivityLog.log_id == log_id).first()
    if db_log is None:
        raise HTTPException(status_code=404, detail="Activity log not found")
    
    db_log.activity_type = activity_type
    db_log.details = details
    db.commit()
    db.refresh(db_log)
    return db_log

@app.delete("/activity_log/{log_id}")
def delete_activity_log(log_id: int, db: Session = Depends(get_db)):
    db_log = db.query(ActivityLog).filter(ActivityLog.log_id == log_id).first()
    if db_log is None:
        raise HTTPException(status_code=404, detail="Activity log not found")
    
    db.delete(db_log)
    db.commit()
    return {"message": "Activity log deleted successfully"}


# --- CRUD for AdminActivityLog Table ---
@app.get("/admin_activity_log/{log_id}")
def read_admin_activity_log(log_id: int, db: Session = Depends(get_db)):
    db_log = db.query(AdminActivityLog).filter(AdminActivityLog.log_id == log_id).first()
    if db_log is None:
        raise HTTPException(status_code=404, detail="Admin activity log not found")
    return db_log

@app.post("/admin_activity_log/")
def create_admin_activity_log(admin_id: int, action_type: str, target_table: str, target_id: int, action_details: str, db: Session = Depends(get_db)):
    db_admin_log = AdminActivityLog(
        admin_id=admin_id, action_type=action_type, target_table=target_table, target_id=target_id, action_details=action_details
    )
    db.add(db_admin_log)
    db.commit()
    db.refresh(db_admin_log)
    return db_admin_log

@app.put("/admin_activity_log/{log_id}")
def update_admin_activity_log(log_id: int, action_type: str, action_details: str, db: Session = Depends(get_db)):
    db_log = db.query(AdminActivityLog).filter(AdminActivityLog.log_id == log_id).first()
    if db_log is None:
        raise HTTPException(status_code=404, detail="Admin activity log not found")
    
    db_log.action_type = action_type
    db_log.action_details = action_details
    db.commit()
    db.refresh(db_log)
    return db_log

@app.delete("/admin_activity_log/{log_id}")
def delete_admin_activity_log(log_id: int, db: Session = Depends(get_db)):
    db_log = db.query(AdminActivityLog).filter(AdminActivityLog.log_id == log_id).first()
    if db_log is None:
        raise HTTPException(status_code=404, detail="Admin activity log not found")
    
    db.delete(db_log)
    db.commit()
    return {"message": "Admin activity log deleted successfully"}


# --- CRUD for CaseAssignments Table ---
@app.get("/case_assignments/{assignment_id}")
def read_case_assignment(assignment_id: int, db: Session = Depends(get_db)):
    db_assignment = db.query(CaseAssignments).filter(CaseAssignments.assignment_id == assignment_id).first()
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Case assignment not found")
    return db_assignment

@app.post("/case_assignments/")
def create_case_assignment(data: CaseAssignmentCreate):
    assignment_id = insert_and_get_id(
        """
        INSERT INTO case_assignments (user_id, crime_id, duty_role)
        VALUES (%s, %s, %s)
        """,
        (data.user_id, data.crime_id, data.duty_role),
    )
    return {"success": True, "assignment_id": assignment_id}

@app.put("/case_assignments/{assignment_id}")
def update_case_assignment(assignment_id: int, status: str, notes: str, db: Session = Depends(get_db)):
    db_assignment = db.query(CaseAssignments).filter(CaseAssignments.assignment_id == assignment_id).first()
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Case assignment not found")
    
    db_assignment.status = status
    db_assignment.notes = notes
    db.commit()
    db.refresh(db_assignment)
    return db_assignment

@app.delete("/case_assignments/{assignment_id}")
def delete_case_assignment(assignment_id: int, db: Session = Depends(get_db)):
    db_assignment = db.query(CaseAssignments).filter(CaseAssignments.assignment_id == assignment_id).first()
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Case assignment not found")
    
    db.delete(db_assignment)
    db.commit()
    return {"message": "Case assignment deleted successfully"}


# --- CRUD for ChatMessages Table ---
@app.get("/chat_messages/{message_id}")
def read_chat_message(message_id: int, db: Session = Depends(get_db)):
    db_message = db.query(ChatMessages).filter(ChatMessages.message_id == message_id).first()
    if db_message is None:
        raise HTTPException(status_code=404, detail="Chat message not found")
    return db_message

@app.post("/chat_messages/")
def create_chat_message(user_id: int, message: str, report_id: str, is_admin: int, db: Session = Depends(get_db)):
    db_chat_message = ChatMessages(
        user_id=user_id, message=message, report_id=report_id, is_admin=is_admin
    )
    db.add(db_chat_message)
    db.commit()
    db.refresh(db_chat_message)
    return db_chat_message

@app.put("/chat_messages/{message_id}")
def update_chat_message(message_id: int, message: str, is_admin: int, db: Session = Depends(get_db)):
    db_message = db.query(ChatMessages).filter(ChatMessages.message_id == message_id).first()
    if db_message is None:
        raise HTTPException(status_code=404, detail="Chat message not found")
    
    db_message.message = message
    db_message.is_admin = is_admin
    db.commit()
    db.refresh(db_message)
    return db_message

@app.delete("/chat_messages/{message_id}")
def delete_chat_message(message_id: int, db: Session = Depends(get_db)):
    db_message = db.query(ChatMessages).filter(ChatMessages.message_id == message_id).first()
    if db_message is None:
        raise HTTPException(status_code=404, detail="Chat message not found")
    
    db.delete(db_message)
    db.commit()
    return {"message": "Chat message deleted successfully"}


# --- CRUD for Complaints Table ---
@app.get("/complaints/{complaint_id}")
def read_complaint(complaint_id: int, db: Session = Depends(get_db)):
    db_complaint = db.query(Complaints).filter(Complaints.complaint_id == complaint_id).first()
    if db_complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return db_complaint

@app.post("/complaints/")
def create_complaint(reporter_contact: str, complaint_text: str, channel: str, db: Session = Depends(get_db)):
    db_complaint = Complaints(
        reporter_contact=reporter_contact, complaint_text=complaint_text, channel=channel
    )
    db.add(db_complaint)
    db.commit()
    db.refresh(db_complaint)
    return db_complaint

@app.put("/complaints/{complaint_id}")
def update_complaint(complaint_id: int, status: str, db: Session = Depends(get_db)):
    db_complaint = db.query(Complaints).filter(Complaints.complaint_id == complaint_id).first()
    if db_complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    db_complaint.status = status
    db.commit()
    db.refresh(db_complaint)
    return db_complaint

@app.delete("/complaints/{complaint_id}")
def delete_complaint(complaint_id: int, db: Session = Depends(get_db)):
    db_complaint = db.query(Complaints).filter(Complaints.complaint_id == complaint_id).first()
    if db_complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    db.delete(db_complaint)
    db.commit()
    return {"message": "Complaint deleted successfully"}


# --- CRUD for Crime Table ---
@app.get("/crime/{crime_id}")
def read_crime(crime_id: int, db: Session = Depends(get_db)):
    db_crime = db.query(Crime).filter(Crime.crime_id == crime_id).first()
    if db_crime is None:
        raise HTTPException(status_code=404, detail="Crime not found")
    return db_crime

@app.post("/crime/")
def create_crime(data: CrimeCreate):
    crime_id = insert_and_get_id(
        """
        INSERT INTO crime (reporter_id, crime_data, location_data, status, priority_level)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            data.reporter_id,
            data.crime_data,
            data.location_data,
            data.status,
            data.priority_level,
        ),
    )
    return {"success": True, "crime_id": crime_id}


@app.put("/crime/{crime_id}")
def update_crime(crime_id: int, status: str, priority_level: str, db: Session = Depends(get_db)):
    db_crime = db.query(Crime).filter(Crime.crime_id == crime_id).first()
    if db_crime is None:
        raise HTTPException(status_code=404, detail="Crime not found")
    
    db_crime.status = status
    db_crime.priority_level = priority_level
    db.commit()
    db.refresh(db_crime)
    return db_crime

@app.delete("/crime/{crime_id}")
def delete_crime(crime_id: int, db: Session = Depends(get_db)):
    db_crime = db.query(Crime).filter(Crime.crime_id == crime_id).first()
    if db_crime is None:
        raise HTTPException(status_code=404, detail="Crime not found")
    
    db.delete(db_crime)
    db.commit()
    return {"message": "Crime deleted successfully"}

# --- CRUD for CriminalSightings Table ---
@app.get("/criminal_sightings/{sighting_id}")
def read_criminal_sighting(sighting_id: int, db: Session = Depends(get_db)):
    db_row = db.query(CriminalSightings).filter(CriminalSightings.sighting_id == sighting_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Criminal sighting not found")
    return db_row


@app.post("/criminal_sightings/")
def create_criminal_sighting(
    criminal_id: int,
    last_seen_time: datetime,
    last_seen_location: str,
    still_with_finder: int = 0,
    reporter_contact: str | None = None,
    verified: int = 0,
    db: Session = Depends(get_db),
):
    db_obj = CriminalSightings(
        criminal_id=criminal_id,
        last_seen_time=last_seen_time,
        last_seen_location=last_seen_location,
        still_with_finder=still_with_finder,
        reporter_contact=reporter_contact,
        verified=verified,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


@app.put("/criminal_sightings/{sighting_id}")
def update_criminal_sighting(
    sighting_id: int,
    last_seen_location: str | None = None,
    still_with_finder: int | None = None,
    verified: int | None = None,
    db: Session = Depends(get_db),
):
    db_row = db.query(CriminalSightings).filter(CriminalSightings.sighting_id == sighting_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Criminal sighting not found")
    if last_seen_location is not None:
        db_row.last_seen_location = last_seen_location
    if still_with_finder is not None:
        db_row.still_with_finder = still_with_finder
    if verified is not None:
        db_row.verified = verified
    db.commit()
    db.refresh(db_row)
    return db_row


@app.delete("/criminal_sightings/{sighting_id}")
def delete_criminal_sighting(sighting_id: int, db: Session = Depends(get_db)):
    db_row = db.query(CriminalSightings).filter(CriminalSightings.sighting_id == sighting_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Criminal sighting not found")
    db.delete(db_row)
    db.commit()
    return {"message": "Criminal sighting deleted successfully"}


# --- CRUD for EvidenceFiles Table ---
@app.get("/evidence_files/{file_id}")
def read_evidence_file(file_id: int, db: Session = Depends(get_db)):
    db_row = db.query(EvidenceFiles).filter(EvidenceFiles.file_id == file_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Evidence file not found")
    return db_row


@app.post("/evidence_files/")
def create_evidence_file(
    crime_id: int,
    file_name: str,
    file_path: str,
    uploaded_by: int,
    file_type: str | None = None,
    file_size: int | None = None,
    description: str | None = None,
    db: Session = Depends(get_db),
):
    db_obj = EvidenceFiles(
        crime_id=crime_id,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        uploaded_by=uploaded_by,
        description=description,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


@app.put("/evidence_files/{file_id}")
def update_evidence_file(
    file_id: int,
    file_type: str | None = None,
    file_size: int | None = None,
    description: str | None = None,
    db: Session = Depends(get_db),
):
    db_row = db.query(EvidenceFiles).filter(EvidenceFiles.file_id == file_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Evidence file not found")
    if file_type is not None:
        db_row.file_type = file_type
    if file_size is not None:
        db_row.file_size = file_size
    if description is not None:
        db_row.description = description
    db.commit()
    db.refresh(db_row)
    return db_row


@app.delete("/evidence_files/{file_id}")
def delete_evidence_file(file_id: int, db: Session = Depends(get_db)):
    db_row = db.query(EvidenceFiles).filter(EvidenceFiles.file_id == file_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Evidence file not found")
    db.delete(db_row)
    db.commit()
    return {"message": "Evidence file deleted successfully"}


# --- CRUD for FileUploads Table ---
@app.get("/file_uploads/{upload_id}")
def read_file_upload(upload_id: int, db: Session = Depends(get_db)):
    db_row = db.query(FileUploads).filter(FileUploads.upload_id == upload_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="File upload not found")
    return db_row


@app.post("/file_uploads/")
def create_file_upload(
    original_filename: str,
    stored_filename: str,
    file_path: str,
    uploaded_by: int,
    file_type: str | None = None,
    file_size: int | None = None,
    related_table: str | None = None,
    related_id: int | None = None,
    upload_purpose: str = "other",
    db: Session = Depends(get_db),
):
    db_obj = FileUploads(
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        uploaded_by=uploaded_by,
        related_table=related_table,
        related_id=related_id,
        upload_purpose=upload_purpose,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


@app.put("/file_uploads/{upload_id}")
def update_file_upload(
    upload_id: int,
    related_table: str | None = None,
    related_id: int | None = None,
    upload_purpose: str | None = None,
    db: Session = Depends(get_db),
):
    db_row = db.query(FileUploads).filter(FileUploads.upload_id == upload_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="File upload not found")
    if related_table is not None:
        db_row.related_table = related_table
    if related_id is not None:
        db_row.related_id = related_id
    if upload_purpose is not None:
        db_row.upload_purpose = upload_purpose
    db.commit()
    db.refresh(db_row)
    return db_row


@app.delete("/file_uploads/{upload_id}")
def delete_file_upload(upload_id: int, db: Session = Depends(get_db)):
    db_row = db.query(FileUploads).filter(FileUploads.upload_id == upload_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="File upload not found")
    db.delete(db_row)
    db.commit()
    return {"message": "File upload deleted successfully"}


# --- CRUD for MissingPerson Table ---
@app.get("/missing_person/{missing_id}")
def read_missing_person(missing_id: int, db: Session = Depends(get_db)):
    db_row = db.query(MissingPerson).filter(MissingPerson.missing_id == missing_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Missing person not found")
    return db_row


@app.post("/missing_person/")
def create_missing_person(
    name: str,
    reporter_id: int | None = None,
    age: int | None = None,
    gender: str | None = None,
    description: str | None = None,
    last_seen_location: str | None = None,
    last_seen_date: date | None = None,
    contact_phone: str | None = None,
    status: str = "Missing",
    db: Session = Depends(get_db),
):
    db_obj = MissingPerson(
        name=name,
        reporter_id=reporter_id,
        age=age,
        gender=gender,
        description=description,
        last_seen_location=last_seen_location,
        last_seen_date=last_seen_date,
        contact_phone=contact_phone,
        status=status,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


@app.put("/missing_person/{missing_id}")
def update_missing_person(
    missing_id: int,
    status: str | None = None,
    contact_phone: str | None = None,
    last_seen_location: str | None = None,
    db: Session = Depends(get_db),
):
    db_row = db.query(MissingPerson).filter(MissingPerson.missing_id == missing_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Missing person not found")
    if status is not None:
        db_row.status = status
    if contact_phone is not None:
        db_row.contact_phone = contact_phone
    if last_seen_location is not None:
        db_row.last_seen_location = last_seen_location
    db.commit()
    db.refresh(db_row)
    return db_row


@app.delete("/missing_person/{missing_id}")
def delete_missing_person(missing_id: int, db: Session = Depends(get_db)):
    db_row = db.query(MissingPerson).filter(MissingPerson.missing_id == missing_id).first()
    if db_row is None:
        raise HTTPException(status_code=404, detail="Missing person not found")
    db.delete(db_row)
    db.commit()
    return {"message": "Missing person deleted successfully"}
Base.metadata.create_all(bind=engine)

# --- Minimal create endpoints for PoliceStation and WantedCriminal ---

@app.post("/police_stations/")
def create_police_station(
    data: PoliceStationCreate,
):
    station_id = insert_and_get_id(
        """
        INSERT INTO police_station (station_name, station_code, address, phone, email, latitude, longitude, jurisdiction_area)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            data.station_name,
            data.station_code,
            data.address,
            data.phone,
            data.email,
            data.latitude,
            data.longitude,
            data.jurisdiction_area,
        ),
    )
    return {"success": True, "station_id": station_id}


@app.post("/wanted_criminals/")
def create_wanted_criminal(
    data: WantedCriminalCreate,
):
    criminal_id = insert_and_get_id(
        """
        INSERT INTO wanted_criminal (name, alias, age_range, gender, description, crimes_committed, danger_level, reward_amount, last_known_location, photo_url, added_by, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            data.name,
            data.alias,
            data.age_range,
            data.gender,
            data.description,
            data.crimes_committed,
            data.danger_level,
            data.reward_amount,
            data.last_known_location,
            data.photo_url,
            data.added_by,
            data.status,
        ),
    )
    return {"success": True, "criminal_id": criminal_id}


# python -m uvicorn main_admin:app --reload --host 127.0.0.1 --port 8001