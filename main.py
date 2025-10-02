from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import hashlib
from datetime import datetime
from typing import Optional, List
import json

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

# Pydantic Models
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

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

# ==================== EXISTING USER ENDPOINTS ====================

@app.post("/register")
async def register_user(user: UserCreate):
    hashed_password = hash_password(user.password)
    with engine.connect() as conn:
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

@app.post("/login")
async def login_user(user: UserLogin):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM appuser WHERE email = :email"),
            {"email": user.email}
        ).mappings().fetchone()
        if not result:
            raise HTTPException(status_code=400, detail="Email not registered")
        stored_password = result["password_hash"]
        if stored_password != hash_password(user.password):
            raise HTTPException(status_code=400, detail="Incorrect password")
        return {
            "message": "Login successful",
            "user": {
                "email": result["email"],
                "username": result["username"],
                "role_hint": result["role_hint"],
                "station_id": result["station_id"],
                "status": result["status"],
                "created_at": result["created_at"]
            }
        }
        print(f"Login success for {user.email}")

# ==================== ADMIN DASHBOARD ENDPOINTS ====================

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin dashboard HTML"""
    try:
        with open("admin_dashboard.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="Admin dashboard not found", status_code=404)

@app.post("/api/crimes")
async def create_crime(crime_data: CrimeData):
    """Create a new crime with all related information using hardcoded SQL"""
    try:
        print(f"Received crime data: {crime_data}")
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Step 1: Insert Location
                print("Inserting location...")
                location_result = conn.execute(
                    text("""
                        INSERT INTO location (district_id, area_name, city, latitude, longitude, created_at)
                        VALUES (:district_id, :area_name, :city, :latitude, :longitude, :created_at)
                    """),
                    {
                        "district_id": crime_data.location["district_id"],
                        "area_name": crime_data.location["area_name"],
                        "city": crime_data.location["city"],
                        "latitude": crime_data.location["latitude"],
                        "longitude": crime_data.location["longitude"],
                        "created_at": datetime.utcnow()
                    }
                )
                location_id = location_result.lastrowid
                print(f"Location inserted with ID: {location_id}")
                
                # Step 2: Insert Crime
                print("Inserting crime...")
                crime_result = conn.execute(
                    text("""
                        INSERT INTO crime (crime_type, description, date_time, location_id, station_id, case_status, created_at)
                        VALUES (:crime_type, :description, :date_time, :location_id, :station_id, :case_status, :created_at)
                    """),
                    {
                        "crime_type": crime_data.crime["crime_type"],
                        "description": crime_data.crime["description"],
                        "date_time": crime_data.crime["date_time"],
                        "location_id": location_id,
                        "station_id": crime_data.crime.get("station_id", 1),  # Default to station 1
                        "case_status": crime_data.crime["status"],  # Map status to case_status
                        "created_at": datetime.utcnow()
                    }
                )
                crime_id = crime_result.lastrowid
                print(f"Crime inserted with ID: {crime_id}")
                
                # Step 3: Insert Victim (if provided)
                victim_id = None
                if crime_data.victim and crime_data.victim.get("full_name"):
                    print("Inserting victim...")
                    victim_result = conn.execute(
                        text("""
                            INSERT INTO victim (full_name, dob, gender, address, phone_number, injury_details, created_at)
                            VALUES (:full_name, :dob, :gender, :address, :phone_number, :injury_details, :created_at)
                        """),
                        {
                            "full_name": crime_data.victim["full_name"],
                            "dob": crime_data.victim.get("dob"),
                            "gender": crime_data.victim.get("gender"),
                            "address": crime_data.victim.get("address"),
                            "phone_number": crime_data.victim.get("phone_number"),
                            "injury_details": crime_data.victim.get("injury_details"),
                            "created_at": datetime.utcnow()
                        }
                    )
                    victim_id = victim_result.lastrowid
                    print(f"Victim inserted with ID: {victim_id}")
                    
                    # Insert Crime-Victim relationship
                    conn.execute(
                        text("""
                            INSERT INTO crime_victim (crime_id, victim_id, harm_level)
                            VALUES (:crime_id, :victim_id, :harm_level)
                        """),
                        {
                            "crime_id": crime_id,
                            "victim_id": victim_id,
                            "harm_level": "minor"
                        }
                    )
                
                # Step 4: Insert Criminal (if provided)
                criminal_id = None
                if crime_data.criminal and crime_data.criminal.get("full_name"):
                    print("Inserting criminal...")
                    criminal_result = conn.execute(
                        text("""
                            INSERT INTO criminal (full_name, alias_name, dob, gender, address, marital_status, past_record, created_at)
                            VALUES (:full_name, :alias_name, :dob, :gender, :address, :marital_status, :past_record, :created_at)
                        """),
                        {
                            "full_name": crime_data.criminal["full_name"],
                            "alias_name": crime_data.criminal.get("alias_name"),
                            "dob": crime_data.criminal.get("dob"),
                            "gender": crime_data.criminal.get("gender"),
                            "address": crime_data.criminal.get("address"),
                            "marital_status": crime_data.criminal.get("marital_status"),
                            "past_record": crime_data.criminal.get("previous_crimes"),
                            "created_at": datetime.utcnow()
                        }
                    )
                    criminal_id = criminal_result.lastrowid
                    print(f"Criminal inserted with ID: {criminal_id}")
                    
                    # Insert Crime-Criminal relationship
                    conn.execute(
                        text("""
                            INSERT INTO crime_criminal (crime_id, criminal_id, role)
                            VALUES (:crime_id, :criminal_id, :role)
                        """),
                        {
                            "crime_id": crime_id,
                            "criminal_id": criminal_id,
                            "role": "Suspect"
                        }
                    )
                
                # Step 5: Insert Weapon (if provided)
                weapon_id = None
                if crime_data.weapon and crime_data.weapon.get("weapon_name"):
                    print("Inserting weapon...")
                    weapon_result = conn.execute(
                        text("""
                            INSERT INTO weapon (weapon_name, weapon_type, description, serial_number, created_at)
                            VALUES (:weapon_name, :weapon_type, :description, :serial_number, :created_at)
                        """),
                        {
                            "weapon_name": crime_data.weapon["weapon_name"],
                            "weapon_type": crime_data.weapon.get("weapon_type"),
                            "description": crime_data.weapon.get("description"),
                            "serial_number": crime_data.weapon.get("serial_number"),
                            "created_at": datetime.utcnow()
                        }
                    )
                    weapon_id = weapon_result.lastrowid
                    print(f"Weapon inserted with ID: {weapon_id}")
                    
                    # Insert Crime-Weapon relationship
                    conn.execute(
                        text("""
                            INSERT INTO crime_weapon (crime_id, weapon_id, usage_desc)
                            VALUES (:crime_id, :weapon_id, :usage_desc)
                        """),
                        {
                            "crime_id": crime_id,
                            "weapon_id": weapon_id,
                            "usage_desc": "Used in crime"
                        }
                    )
                
                # Step 6: Insert Witness (if provided)
                witness_id = None
                if crime_data.witness and crime_data.witness.get("full_name"):
                    print("Inserting witness...")
                    witness_result = conn.execute(
                        text("""
                            INSERT INTO witness (full_name, phone_number, protection_flag)
                            VALUES (:full_name, :phone_number, :protection_flag)
                        """),
                        {
                            "full_name": crime_data.witness["full_name"],
                            "phone_number": crime_data.witness.get("phone_number"),
                            "protection_flag": crime_data.witness.get("protection_flag", False)
                        }
                    )
                    witness_id = witness_result.lastrowid
                    print(f"Witness inserted with ID: {witness_id}")
                    
                    # Insert Crime-Witness relationship
                    conn.execute(
                        text("""
                            INSERT INTO crime_witness (crime_id, witness_id, statement_status)
                            VALUES (:crime_id, :witness_id, :statement_status)
                        """),
                        {
                            "crime_id": crime_id,
                            "witness_id": witness_id,
                            "statement_status": "pending"
                        }
                    )
                
                # Commit transaction
                trans.commit()
                print("Transaction committed successfully")
                
                return {
                    "success": True,
                    "message": "Crime created successfully",
                    "data": {
                        "crime_id": crime_id,
                        "location_id": location_id,
                        "victim_id": victim_id,
                        "criminal_id": criminal_id,
                        "weapon_id": weapon_id,
                        "witness_id": witness_id
                    }
                }
                
            except Exception as e:
                print(f"Error in transaction: {str(e)}")
                trans.rollback()
                raise e
                
    except Exception as e:
        print(f"Error creating crime: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to create crime"
        }

@app.get("/api/crimes")
async def get_crimes():
    """Get all crimes using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT c.crime_id, c.crime_type, c.description, c.date_time, c.status, c.created_at,
                           l.area_name, l.city, l.latitude, l.longitude,
                           d.district_name
                    FROM crime c
                    JOIN location l ON c.location_id = l.location_id
                    JOIN district d ON l.district_id = d.district_id
                    ORDER BY c.created_at DESC
                """)
            ).fetchall()
            
            crimes = []
            for row in result:
                crime_dict = {
                    "crime_id": row[0],
                    "crime_type": row[1],
                    "description": row[2],
                    "date_time": row[3].isoformat() if row[3] else None,
                    "status": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                    "area_name": row[6],
                    "city": row[7],
                    "latitude": float(row[8]) if row[8] else None,
                    "longitude": float(row[9]) if row[9] else None,
                    "district_name": row[10]
                }
                crimes.append(crime_dict)
            
            return {"success": True, "crimes": crimes}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/complaints")
async def get_complaints():
    """Get all complaints using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT complaint_id, reported_at, reporter_contact, description, channel, status
                    FROM complaint
                    ORDER BY reported_at DESC
                """)
            ).fetchall()
            
            complaints = []
            for row in result:
                complaint_dict = {
                    "complaint_id": row[0],
                    "reported_at": row[1].isoformat() if row[1] else None,
                    "reporter_contact": row[2],
                    "description": row[3],
                    "channel": row[4],
                    "status": row[5]
                }
                complaints.append(complaint_dict)
            
            return {"success": True, "complaints": complaints}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/complaints/{complaint_id}/verify")
async def verify_complaint(complaint_id: int):
    """Verify a complaint using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("UPDATE complaint SET status = 'verified' WHERE complaint_id = :complaint_id"),
                {"complaint_id": complaint_id}
            )
            
            if result.rowcount > 0:
                conn.commit()
                return {"success": True, "message": "Complaint verified successfully"}
            else:
                raise HTTPException(status_code=404, detail="Complaint not found")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/complaints/{complaint_id}/reject")
async def reject_complaint(complaint_id: int):
    """Reject a complaint using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("UPDATE complaint SET status = 'rejected' WHERE complaint_id = :complaint_id"),
                {"complaint_id": complaint_id}
            )
            
            if result.rowcount > 0:
                conn.commit()
                return {"success": True, "message": "Complaint rejected successfully"}
            else:
                raise HTTPException(status_code=404, detail="Complaint not found")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/case-assignments")
async def assign_case(assignment: CaseAssignment):
    """Assign case to officer using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO case_assignment (user_id, crime_id, duty_role, assigned_at)
                    VALUES (:user_id, :crime_id, :duty_role, :assigned_at)
                """),
                {
                    "user_id": assignment.user_id,
                    "crime_id": assignment.crime_id,
                    "duty_role": assignment.duty_role,
                    "assigned_at": datetime.utcnow()
                }
            )
            
            conn.commit()
            return {
                "success": True,
                "message": "Case assigned successfully",
                "assignment_id": result.lastrowid
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/crimes/{crime_id}/status")
async def update_crime_status(crime_id: int, status_update: StatusUpdate):
    """Update crime status and add to history using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            
            try:
                # Update crime status
                conn.execute(
                    text("UPDATE crime SET status = :new_status WHERE crime_id = :crime_id"),
                    {
                        "new_status": status_update.new_status,
                        "crime_id": crime_id
                    }
                )
                
                # Add to status history
                conn.execute(
                    text("""
                        INSERT INTO case_status_history (crime_id, status, notes, changed_at, changed_by)
                        VALUES (:crime_id, :status, :notes, :changed_at, :changed_by)
                    """),
                    {
                        "crime_id": crime_id,
                        "status": status_update.new_status,
                        "notes": status_update.notes,
                        "changed_at": datetime.utcnow(),
                        "changed_by": status_update.changed_by
                    }
                )
                
                trans.commit()
                return {"success": True, "message": "Status updated successfully"}
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/case-assignments")
async def get_case_assignments():
    """Get all case assignments using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT ca.assignment_id, ca.crime_id, ca.user_id, ca.duty_role, ca.assigned_at, ca.released_at,
                           c.crime_type, c.status,
                           u.username, u.full_name
                    FROM case_assignment ca
                    JOIN crime c ON ca.crime_id = c.crime_id
                    LEFT JOIN appuser u ON ca.user_id = u.user_id
                    ORDER BY ca.assigned_at DESC
                """)
            ).fetchall()
            
            assignments = []
            for row in result:
                assignment_dict = {
                    "assignment_id": row[0],
                    "crime_id": row[1],
                    "user_id": row[2],
                    "duty_role": row[3],
                    "assigned_at": row[4].isoformat() if row[4] else None,
                    "released_at": row[5].isoformat() if row[5] else None,
                    "crime_type": row[6],
                    "status": row[7],
                    "username": row[8],
                    "full_name": row[9]
                }
                assignments.append(assignment_dict)
            
            return {"success": True, "assignments": assignments}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/districts")
async def get_districts():
    """Get all districts using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT district_id, district_name, state FROM district ORDER BY district_name")
            ).fetchall()
            
            districts = []
            for row in result:
                district_dict = {
                    "district_id": row[0],
                    "district_name": row[1],
                    "state": row[2]
                }
                districts.append(district_dict)
            
            return {"success": True, "districts": districts}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users")
async def get_users():
    """Get all users using hardcoded SQL"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT user_id, username, email, full_name, role_hint, station_id, status, created_at
                    FROM appuser
                    ORDER BY created_at DESC
                """)
            ).fetchall()
            
            users = []
            for row in result:
                user_dict = {
                    "user_id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "full_name": row[3],
                    "role_hint": row[4],
                    "station_id": row[5],
                    "status": row[6],
                    "created_at": row[7].isoformat() if row[7] else None
                }
                users.append(user_dict)
            
            return {"success": True, "users": users}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-db")
async def test_database():
    """Test database connection"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test")).fetchone()
            return {"success": True, "message": "Database connection successful", "test": result[0]}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Database connection failed"}

@app.get("/test-crime", response_class=HTMLResponse)
async def test_crime_page():
    """Serve the test crime page"""
    try:
        with open("test_crime.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="Test page not found", status_code=404)

@app.get("/")
def read_root():
    return {"message": "Welcome to Safe Route App API", "admin_dashboard": "/admin"}