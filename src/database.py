from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import settings

from pathlib import Path

if "sqlite" in settings.DATABASE_URL:
    db_path_str = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path_str:
        Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy import text

def init_db():
    Base.metadata.create_all(bind=engine)
    # Lightweight migration for SQLite
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN preferred_exercises TEXT"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE daily_logs ADD COLUMN total_exercise_calories FLOAT DEFAULT 0.0"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN workout_days INTEGER DEFAULT 3"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_profile_set BOOLEAN DEFAULT 0"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("UPDATE users SET is_profile_set = 1 WHERE user_id IN (SELECT DISTINCT user_id FROM meal_records) OR daily_calorie_target != 1800"))
            conn.commit()
        except Exception:
            pass

