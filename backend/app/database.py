from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
import os

DATABASE_URL = "sqlite:///./data/satsa.db"

os.makedirs(os.path.dirname("./data/satsa.db"), exist_ok=True)

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    """Initializes tables and automatically performs lightweight SQLite column migrations if needed."""
    Base.metadata.create_all(bind=engine)
    
    # Ensure SQLite schema contains any recently added model columns
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            # Check findings table
            if "findings" in tables:
                cols = {c["name"] for c in inspector.get_columns("findings")}
                if "decision_status" not in cols:
                    conn.execute(text("ALTER TABLE findings ADD COLUMN decision_status VARCHAR DEFAULT 'OPEN'"))
                if "modified_assessment" not in cols:
                    conn.execute(text("ALTER TABLE findings ADD COLUMN modified_assessment TEXT"))
                if "adjudicated_by" not in cols:
                    conn.execute(text("ALTER TABLE findings ADD COLUMN adjudicated_by VARCHAR"))
                if "adjudicated_at" not in cols:
                    conn.execute(text("ALTER TABLE findings ADD COLUMN adjudicated_at DATETIME"))
                if "assessment_validity" not in cols:
                    conn.execute(text("ALTER TABLE findings ADD COLUMN assessment_validity VARCHAR DEFAULT 'HIGH'"))
                if "validity_rationale" not in cols:
                    conn.execute(text("ALTER TABLE findings ADD COLUMN validity_rationale TEXT"))
                if "risk_contribution" not in cols:
                    conn.execute(text("ALTER TABLE findings ADD COLUMN risk_contribution FLOAT DEFAULT 0.0"))
            
            # Check dataset_uploads table
            if "dataset_uploads" in tables:
                cols = {c["name"] for c in inspector.get_columns("dataset_uploads")}
                if "source_hash" not in cols:
                    conn.execute(text("ALTER TABLE dataset_uploads ADD COLUMN source_hash VARCHAR"))
                if "hash_algorithm" not in cols:
                    conn.execute(text("ALTER TABLE dataset_uploads ADD COLUMN hash_algorithm VARCHAR DEFAULT 'SHA-256'"))
                if "hash_created_at" not in cols:
                    conn.execute(text("ALTER TABLE dataset_uploads ADD COLUMN hash_created_at DATETIME"))
                if "declared_population" not in cols:
                    conn.execute(text("ALTER TABLE dataset_uploads ADD COLUMN declared_population JSON"))

            conn.commit()
    except Exception as e:
        # Ignore or log in test environments with in-memory SQLite
        pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

