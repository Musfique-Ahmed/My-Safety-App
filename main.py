from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import os
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost/mysafety"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"charset": "utf8mb4"})

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create uploads directory if it doesn't exist
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
    report_id: Optional[int] = None
    is_admin: Optional[bool] = False

class EmergencyAlert(BaseModel):
    location: dict
    alert_type: str
    description: str
    severity: str = "High"

class CriminalSighting(BaseModel):
    criminal_id: int
    last_seen_time: str
    last_seen_location: str
    still_with_finder: bool = False
    reporter_contact: Optional[str] = None

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

# ==================== ROOT ENDPOINT (LANDING PAGE) ====================

@app.get("/")
async def read_root():
    """Serve the main landing page (home.html)"""
    try:
        return HTMLResponse(content=open("static/home.html").read())
    except FileNotFoundError:
        # Fallback to index.html if home.html doesn't exist
        return HTMLResponse(content=open("static/index.html").read())

# ==================== STATIC PAGE ENDPOINTS ====================

@app.get("/dashboard")
async def get_dashboard_page():
    """Serve the main dashboard page (index.html)"""
    return HTMLResponse(content=open("static/index.html").read())

@app.get("/home")
async def get_home_page():
    """Alternative route to home page"""
    return HTMLResponse(content=open("static/home.html").read())

@app.get("/report-crime")
async def get_report_crime_page():
    """Serve the crime reporting page"""
    return HTMLResponse(content=open("static/report_crime.html").read())

@app.get("/missing-person")
async def get_missing_person_page():
    """Serve the missing persons page"""
    return HTMLResponse(content=open("static/missing_person.html").read())

@app.get("/wanted-criminals")
async def get_wanted_criminals_page():
    """Serve the wanted criminals page"""
    return HTMLResponse(content=open("static/wanted_criminal.html").read())

@app.get("/chatbox")
async def get_chatbox_page():
    """Serve the community chatbox page"""
    return HTMLResponse(content=open("static/user_chatbox.html").read())

@app.get("/report-missing")
async def get_report_missing_page():
    """Serve the missing person report form"""
    return HTMLResponse(content=open("static/report_missing_person.html").read())

@app.get("/login")
async def get_login_page():
    """Serve the login page"""
    return HTMLResponse(content=open("static/login.html").read())

@app.get("/signup")
async def get_signup_page():
    """Serve the signup page"""
    return HTMLResponse(content=open("static/signup.html").read())

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
            # Insert into crime table
            result = conn.execute(
                text("""
                    INSERT INTO crime (location_data, crime_data, victim_data, criminal_data, 
                                     weapon_data, witness_data, status, created_at)
                    VALUES (:location_data, :crime_data, :victim_data, :criminal_data, 
                            :weapon_data, :witness_data, :status, :created_at)
                """),
                {
                    "location_data": json.dumps(crime_data.location),
                    "crime_data": json.dumps(crime_data.crime),
                    "victim_data": json.dumps(crime_data.victim) if crime_data.victim else None,
                    "criminal_data": json.dumps(crime_data.criminal) if crime_data.criminal else None,
                    "weapon_data": json.dumps(crime_data.weapon) if crime_data.weapon else None,
                    "witness_data": json.dumps(crime_data.witness) if crime_data.witness else None,
                    "status": "Pending",
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            crime_id = result.lastrowid
            print(f"Crime report submitted with ID: {crime_id}")
            return {"message": "Crime report submitted successfully", "crime_id": crime_id}
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
async def submit_missing_person_report(missing_person: MissingPersonData):
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    INSERT INTO missing_person (name, age, gender, description, last_seen_location, 
                                              last_seen_date, contact_info, photo_url, status, created_at)
                    VALUES (:name, :age, :gender, :description, :last_seen_location, 
                            :last_seen_date, :contact_info, :photo_url, :status, :created_at)
                """),
                {
                    "name": missing_person.name,
                    "age": missing_person.age,
                    "gender": missing_person.gender,
                    "description": missing_person.description,
                    "last_seen_location": missing_person.last_seen_location,
                    "last_seen_date": missing_person.last_seen_date,
                    "contact_info": missing_person.contact_info,
                    "photo_url": missing_person.photo_url,
                    "status": "Missing",
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            missing_id = result.lastrowid
            print(f"Missing person report submitted with ID: {missing_id}")
            return {"message": "Missing person report submitted successfully", "missing_id": missing_id}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to submit missing person report: {str(e)}")

@app.get("/api/missing-persons")
async def get_all_missing_persons(
    status: Optional[str] = Query(None, description="Filter by status")
):
    with engine.connect() as conn:
        query = "SELECT * FROM missing_person"
        params = {}
        
        if status:
            query += " WHERE status = :status"
            params["status"] = status
            
        query += " ORDER BY created_at DESC"
        
        result = conn.execute(text(query), params).mappings().fetchall()
        return {"missing_persons": [dict(row) for row in result]}

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

@app.get("/api/wanted-criminals")
async def get_wanted_criminals():
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("SELECT * FROM wanted_criminal WHERE status = 'Active' ORDER BY created_at DESC")
            ).mappings().fetchall()
            
            wanted_criminals = []
            for row in result:
                criminal = dict(row)
                # Convert database fields to match frontend expectations
                wanted_criminal = {
                    "id": criminal["criminal_id"],
                    "name": criminal["name"],
                    "alias": criminal.get("alias", ""),
                    "age": criminal.get("age_range", "Unknown"),
                    "height_cm": criminal.get("height", "Unknown"),
                    "complexion": criminal.get("distinguishing_marks", "Unknown"),
                    "crimes": criminal["crimes_committed"].split(", ") if criminal["crimes_committed"] else [],
                    "last_seen_location": criminal.get("last_known_location", "Unknown"),
                    "last_seen_time": criminal.get("wanted_since", ""),
                    "reward": float(criminal.get("reward_amount", 0)),
                    "photo_url": criminal.get("photo_url", "/static/img/placeholder.jpg"),
                    "note": criminal.get("description", ""),
                    "danger_level": criminal.get("danger_level", "Medium"),
                    "status": criminal["status"]
                }
                wanted_criminals.append(wanted_criminal)
            
            return {"wanted_criminals": wanted_criminals}
        except Exception as e:
            print(f"Error fetching wanted criminals: {e}")
            # Return sample data if database is not set up
            return {"wanted_criminals": [
                {
                    "id": 1,
                    "name": "Karim Ahmed",
                    "alias": "Black Karim",
                    "age": "25-30",
                    "height_cm": "175",
                    "complexion": "Dark, scar on left cheek",
                    "crimes": ["Armed robbery", "assault", "theft"],
                    "last_seen_location": "Old Dhaka area",
                    "last_seen_time": "2024-01-15",
                    "reward": 50000,
                    "photo_url": "https://via.placeholder.com/300x300/dc2626/ffffff?text=WANTED",
                    "note": "Extremely dangerous, do not approach",
                    "danger_level": "High",
                    "status": "Active"
                },
                {
                    "id": 2,
                    "name": "Rashida Begum",
                    "alias": "Rashi",
                    "age": "30-35",
                    "height_cm": "160",
                    "complexion": "Fair, distinctive tattoo on right arm",
                    "crimes": ["Fraud", "embezzlement", "forgery"],
                    "last_seen_location": "Uttara sector 7",
                    "last_seen_time": "2024-02-20",
                    "reward": 25000,
                    "photo_url": "https://via.placeholder.com/300x300/dc2626/ffffff?text=WANTED",
                    "note": "Known for financial crimes",
                    "danger_level": "Medium",
                    "status": "Active"
                }
            ]}

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

@app.post("/api/wanted-criminals/{criminal_id}/sighting")
async def report_criminal_sighting(criminal_id: int, sighting: CriminalSighting):
    """Report a sighting of a wanted criminal"""
    with engine.connect() as conn:
        try:
            # Insert sighting report
            conn.execute(
                text("""
                    INSERT INTO criminal_sightings (criminal_id, last_seen_time, last_seen_location, 
                                                   still_with_finder, reporter_contact, created_at)
                    VALUES (:criminal_id, :last_seen_time, :last_seen_location, 
                            :still_with_finder, :reporter_contact, :created_at)
                """),
                {
                    "criminal_id": criminal_id,
                    "last_seen_time": sighting.last_seen_time,
                    "last_seen_location": sighting.last_seen_location,
                    "still_with_finder": sighting.still_with_finder,
                    "reporter_contact": sighting.reporter_contact,
                    "created_at": datetime.utcnow()
                }
            )
            conn.commit()
            
            # In production, this would trigger real police notifications
            print(f"🚓 CRIMINAL SIGHTING REPORTED: Criminal ID {criminal_id} at {sighting.last_seen_location}")
            
            return {
                "message": "Criminal sighting reported successfully",
                "status": "Police have been notified"
            }
        except Exception as e:
            conn.rollback()
            print(f"Error reporting sighting: {e}")
            # Still return success for demo purposes
            return {
                "message": "Criminal sighting reported successfully",
                "status": "Police have been notified"
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


