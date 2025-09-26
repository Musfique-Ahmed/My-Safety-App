from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import relationship
from .database import Base
import datetime

# Association Table for the many-to-many relationship between users (friends)
friendship_table = Table(
    'friendships', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('friend_id', Integer, ForeignKey('users.id'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    last_known_lat = Column(Float, nullable=True)
    last_known_lon = Column(Float, nullable=True)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)

    # Many-to-many relationship for friends (self-referential)
    friends = relationship(
        "User",
        secondary=friendship_table,
        primaryjoin=id == friendship_table.c.user_id,
        secondaryjoin=id == friendship_table.c.friend_id,
        backref="friend_of",
        remote_side=[id]
    )

    panic_alerts = relationship("PanicAlert", back_populates="user")
    notifications = relationship("Notification", back_populates="user")

class PanicAlert(Base):
    __tablename__ = "panic_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="panic_alerts")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String(255), nullable=False)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="notifications")

# --- Route planning models ---
class Location(Base):
    __tablename__ = "location"
    location_id = Column(Integer, primary_key=True, index=True)
    street_no = Column(Integer)
    street_dir = Column(String(10))
    street_name = Column(String(100))
    city = Column(String(50))
    latitude = Column(Float)
    longitude = Column(Float)
    crimes = relationship("Crime", back_populates="location")

class Crime(Base):
    __tablename__ = "crime"
    crime_id = Column(Integer, primary_key=True, index=True)
    start_date = Column(DateTime)
    location_id = Column(Integer, ForeignKey("location.location_id"))
    location = relationship("Location", back_populates="crimes")
    victims = relationship("Victim", back_populates="crime")

class Victim(Base):
    __tablename__ = "victim"
    victim_id = Column(Integer, primary_key=True, index=True)
    age = Column(Integer)
    sex = Column(String(1))
    crime_id = Column(Integer, ForeignKey("crime.crime_id"))
    crime = relationship("Crime", back_populates="victims")