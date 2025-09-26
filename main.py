from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import hashlib
from datetime import datetime

app = FastAPI()

# Enable CORS for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost/mysafety"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"charset": "utf8mb4"})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = 'appuser'
    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), unique=True, index=True)
    password_hash = Column(String(255))
    username = Column(String(255))
    role_hint = Column(String(50), default="User")
    station_id = Column(Integer, nullable=True)
    status = Column(String(20), default="Active")
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_password, provided_password):
    return stored_password == hash_password(provided_password)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register")
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = hash_password(user.password)
    new_user = User(
        email=user.email,
        username=user.username,
        password_hash=hashed_password,
        role_hint="User",
        status="Active",
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}

@app.post("/login")
async def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user:
        print(f"Login failed: email {user.email} not found")
        raise HTTPException(status_code=400, detail="Email not registered")
    if not verify_password(db_user.password_hash, user.password):
        print(f"Login failed: wrong password for {user.email}")
        raise HTTPException(status_code=400, detail="Incorrect password")
    print(f"Login success for {user.email}")
    return {
        "message": "Login successful",
        "user": {
            "email": db_user.email,
            "username": db_user.username,
            "role_hint": db_user.role_hint,
            "station_id": db_user.station_id,
            "status": db_user.status,
            "created_at": db_user.created_at
        }
    }

@app.get("/")
def read_root():
    return {"message": "Welcome to Safe Route App API"}