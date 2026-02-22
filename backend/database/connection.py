"""
Database Configuration & Session Management
Handles PostgreSQL connections with connection pooling
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== DATABASE CONFIGURATION ====================

DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "thai_alpr"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

# Connection string
DATABASE_URL = (
    f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
    f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
)

# ==================== ENGINE CONFIGURATION ====================

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,  # Number of connections to maintain
    max_overflow=10,  # Additional connections when pool is full
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False,  # Set to True for SQL query logging (dev only)
    connect_args={
        "options": "-c timezone=utc",
        "connect_timeout": 10,
    }
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ==================== DATABASE DEPENDENCY ====================

def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI
    Usage in endpoint: def endpoint(db: Session = Depends(get_db))
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions outside FastAPI
    Usage:
        with get_db_context() as db:
            result = db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ==================== DATABASE INITIALIZATION ====================

def init_database():
    """Initialize database tables"""
    from .models import Base
    Base.metadata.create_all(bind=engine)
    _apply_schema_patches()
    print("✅ Database tables created successfully")


def _apply_schema_patches():
    """Apply lightweight schema patches for existing deployments."""
    patch_statements = [
        """
        ALTER TABLE plate_records
        ADD COLUMN IF NOT EXISTS plate_type plate_type_enum DEFAULT 'UNKNOWN'
        """
    ]

    with engine.begin() as conn:
        for statement in patch_statements:
            conn.execute(text(statement))


def drop_all_tables():
    """Drop all tables - USE WITH CAUTION!"""
    from .models import Base
    Base.metadata.drop_all(bind=engine)
    print("⚠️  All tables dropped")


# ==================== HEALTH CHECK ====================

def check_database_connection() -> bool:
    """Check if database is accessible"""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
