from datetime import datetime, date
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from src.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, index=True)
    current_weight = Column(Float, nullable=False, default=70.0)
    target_weight = Column(Float, nullable=False, default=65.0)
    height = Column(Float, nullable=False, default=170.0)
    age = Column(Integer, nullable=False, default=30)
    gender = Column(String, nullable=False, default="unknown")
    
    daily_calorie_target = Column(Integer, nullable=False, default=1800)
    target_protein = Column(Float, nullable=False, default=112.5)  # grams (25%)
    target_carbs = Column(Float, nullable=False, default=225.0)   # grams (50%)
    target_fat = Column(Float, nullable=False, default=50.0)      # grams (25%)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    daily_logs = relationship("DailyLog", back_populates="user", cascade="all, delete-orphan")


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    log_date = Column(String, nullable=False, index=True, default=lambda: date.today().isoformat())

    breakfast_completed = Column(Boolean, default=False)
    lunch_completed = Column(Boolean, default=False)
    dinner_completed = Column(Boolean, default=False)

    total_calories = Column(Float, default=0.0)
    total_protein = Column(Float, default=0.0)
    total_carbs = Column(Float, default=0.0)
    total_fat = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="daily_logs")
    meals = relationship("MealRecord", back_populates="daily_log", cascade="all, delete-orphan")


class MealRecord(Base):
    __tablename__ = "meal_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    daily_log_id = Column(Integer, ForeignKey("daily_logs.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False)

    meal_type = Column(String, nullable=False)  # breakfast, lunch, dinner, snack
    food_description = Column(Text, nullable=False)
    
    calories = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)

    image_path = Column(String, nullable=True)
    ai_analysis = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    daily_log = relationship("DailyLog", back_populates="meals")
