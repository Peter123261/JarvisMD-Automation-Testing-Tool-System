"""
Database Connection and Initialization
Handles SQLite and PostgreSQL database setup and connections for the automation testing tool
"""

import os
from typing import List
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, QueuePool
from pathlib import Path
import logging

# Import our models
from .models import Base, TestJob, EvaluationResult, SystemMetric, AlertQueue

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages database connections and initialization
    Handles all database operations for the automation testing tool
    Supports both SQLite (development) and PostgreSQL (production)
    """
    
    def __init__(self, database_url: str = None):
        """
        Initialize database manager
        
        Args:
            database_url: Database URL (SQLite or PostgreSQL)
                         Defaults to SQLite if not provided
                         PostgreSQL: postgresql://user:pass@host:port/dbname
                         SQLite: sqlite:///path/to/database.db
        """
        if database_url is None:
            # Try to get from environment
            database_url = os.getenv("DATABASE_URL")
        
        if database_url is None:
            # Default to SQLite for local development
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / "jarvismd_automation.db"
            database_url = f"sqlite:///{db_path}"
            logger.info("Using SQLite database (development mode)")
        
        self.database_url = database_url
        self.is_postgres = database_url.startswith("postgresql://")
        
        # Create engine with database-specific settings
        if self.is_postgres:
            # PostgreSQL configuration
            logger.info("Using PostgreSQL database (production mode)")
            self.engine = create_engine(
                database_url,
                echo=False,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
            )
        else:
            # SQLite configuration
            logger.info("Using SQLite database")
            self.engine = create_engine(
                database_url,
                echo=False,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20
                }
            )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        logger.info(f"Database manager initialized with URL: {database_url}")
    
    def create_tables(self):
        """
        Create all database tables based on our models
        This is like building the actual database structure
        """
        try:
            # Create all tables defined in our models
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ Database tables created successfully")
            
            # Verify tables were created
            self._verify_tables()
            self._ensure_legacy_columns()
            
        except Exception as e:
            logger.error(f"❌ Error creating database tables: {e}")
            raise
    
    def _verify_tables(self):
        """
        Verify that all expected tables exist in the database
        Supports both SQLite and PostgreSQL
        """
        with self.engine.connect() as connection:
            # Check if all our tables exist (database-agnostic query)
            if self.is_postgres:
                # PostgreSQL query
                result = connection.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
                ))
            else:
                # SQLite query
                result = connection.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table';"
                ))
            
            existing_tables = [row[0] for row in result]
            expected_tables = ['test_jobs', 'evaluation_results', 'system_metrics', 'alert_queue']
            
            logger.info(f"Existing tables: {existing_tables}")
            
            for table in expected_tables:
                if table in existing_tables:
                    logger.info(f"✅ Table '{table}' exists")
                else:
                    logger.warning(f"⚠️ Table '{table}' missing")

    def _ensure_legacy_columns(self):
        """
        Ensure newly introduced columns exist on legacy databases.
        Adds token usage columns, trace_id column to evaluation_results and Celery task column to test_jobs when missing.
        """
        try:
            inspector = inspect(self.engine)
            alterations: List[str] = []

            eval_columns = {col["name"] for col in inspector.get_columns("evaluation_results")}
            if "prompt_tokens" not in eval_columns:
                alterations.append("ALTER TABLE evaluation_results ADD COLUMN prompt_tokens INTEGER")
            if "completion_tokens" not in eval_columns:
                alterations.append("ALTER TABLE evaluation_results ADD COLUMN completion_tokens INTEGER")
            if "total_tokens" not in eval_columns:
                alterations.append("ALTER TABLE evaluation_results ADD COLUMN total_tokens INTEGER")
            if "trace_id" not in eval_columns:
                alterations.append("ALTER TABLE evaluation_results ADD COLUMN trace_id VARCHAR(255)")

            job_columns = {col["name"] for col in inspector.get_columns("test_jobs")}
            if "celery_task_id" not in job_columns:
                alterations.append("ALTER TABLE test_jobs ADD COLUMN celery_task_id VARCHAR(255)")

            if alterations:
                logger.info(f"🔧 Applying {len(alterations)} database migration(s)...")
                with self.engine.begin() as connection:
                    for statement in alterations:
                        try:
                            connection.execute(text(statement))
                            logger.info(f"✅ Applied migration: {statement}")
                        except Exception as exc:
                            logger.error(f"❌ Could not apply migration '{statement}': {exc}", exc_info=True)
                            # Re-raise for critical migrations like trace_id
                            if "trace_id" in statement:
                                raise
            else:
                logger.info("✅ All legacy columns already exist, no migrations needed")
        except Exception as exc:
            logger.error(f"❌ Unable to verify/apply legacy columns: {exc}", exc_info=True)
            raise
    
    def get_session(self) -> Session:
        """
        Get a database session for performing operations
        This is like opening a connection to work with data
        """
        return self.SessionLocal()
    
    def reset_database(self):
        """
        Drop all tables and recreate them (useful for development)
        WARNING: This deletes all data!
        """
        try:
            logger.info("🔄 Resetting database (dropping all tables)")
            Base.metadata.drop_all(bind=self.engine)
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ Database reset completed")
        except Exception as e:
            logger.error(f"❌ Error resetting database: {e}")
            raise
    
    def test_connection(self):
        """
        Test database connection and basic operations
        """
        try:
            # Test basic connection
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                logger.info("✅ Database connection successful")
            
            # Test session creation
            session = self.get_session()
            session.close()
            logger.info("✅ Session creation successful")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            return False

# Global database manager instance
db_manager = None

def get_database():
    """
    Get the global database manager instance
    Creates it if it doesn't exist
    """
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager

def init_database():
    """
    Initialize the database for the first time
    Call this when setting up the application
    """
    logger.info("🚀 Initializing JarvisMD Automation database...")
    
    db = get_database()
    
    # Test connection first
    if not db.test_connection():
        raise Exception("Failed to connect to database")
    
    # Create tables
    db.create_tables()
    
    logger.info("✅ Database initialization completed!")
    
    return db

def get_session():
    """
    Convenience function to get a database session
    Use this in your API endpoints
    """
    db = get_database()
    return db.get_session()

if __name__ == "__main__":
    # Run this script directly to initialize the database
    init_database()