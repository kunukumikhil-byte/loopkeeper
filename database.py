from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "loopkeeper.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_sqlite():
    """Safe additive migration for earlier LoopKeeper ZIPs."""
    with engine.begin() as conn:
        user_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
        if user_columns:
            if "google_sub" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255)"))
            if "avatar_url" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(1000)"))

        task_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tasks)"))}
        if task_columns:
            additions = {
                "submission_filename": "VARCHAR(255)",
                "submission_stored_name": "VARCHAR(255)",
                "submission_content_type": "VARCHAR(255)",
<<<<<<< HEAD
                "deadline_at": "DATETIME",
                "deadline_status": "VARCHAR(50) DEFAULT 'OnTrack'",
                "ai_review_status": "VARCHAR(50) DEFAULT 'NotReviewed'",
                "ai_review_reason": "TEXT",
                "ai_corrected_submission": "TEXT",
                "ai_reviewed_at": "DATETIME",
                "ai_confidence": "VARCHAR(20)",
                "completion_declared_at": "DATETIME",
                "completion_statement": "TEXT",
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
            }
            for name, sql_type in additions.items():
                if name not in task_columns:
                    conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {sql_type}"))
