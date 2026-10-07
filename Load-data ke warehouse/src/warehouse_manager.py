"""
Data Warehouse Manager - Handles database operations
"""

import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path
import logging
from typing import Dict, List, Optional
from .config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WarehouseManager:
    """Manages data warehouse operations"""

    def __init__(self, database_url: str = DATABASE_URL):
        """Initialize warehouse manager"""
        self.database_url = database_url
        self.engine = None

        # Ensure warehouse directory exists
        WAREHOUSE_DIR.mkdir(exist_ok=True)

    def connect(self):
        """Create database connection"""
        try:
            self.engine = create_engine(self.database_url)
            logger.info(f"Connected to database: {self.database_url}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def create_tables(self):
        """Create warehouse tables"""
        if not self.engine:
            self.connect()

        # DDL for dimension tables
        ddl_statements = [
            # Dimension: Sensors
            f"""
            CREATE TABLE IF NOT EXISTS {DIM_SENSOR_TABLE} (
                sensor_key INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id VARCHAR(50) UNIQUE NOT NULL,
                status VARCHAR(20),
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # Dimension: Locations
            f"""
            CREATE TABLE IF NOT EXISTS {DIM_LOCATION_TABLE} (
                location_key INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name VARCHAR(100) UNIQUE NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # Dimension: Time
            f"""
            CREATE TABLE IF NOT EXISTS {DIM_TIME_TABLE} (
                time_key INTEGER PRIMARY KEY AUTOINCREMENT,
                full_date DATE NOT NULL,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                hour INTEGER,
                day_of_week INTEGER,
                is_weekend BOOLEAN,
                time_period VARCHAR(20),
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (full_date, hour)
            )
            """,

            # Fact Table: Sensor Readings
            f"""
            CREATE TABLE IF NOT EXISTS {FACT_TABLE} (
                reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_key INTEGER,
                location_key INTEGER,
                time_key INTEGER,
                timestamp TIMESTAMP,
                temperature_celsius REAL,
                humidity_percent REAL,
                pressure_hpa REAL,
                air_quality_aqi REAL,
                temperature_fahrenheit REAL,
                temperature_kelvin REAL,
                heat_index_f REAL,
                heat_index_c REAL,
                aqi_category VARCHAR(20),
                comfort_index REAL,
                temperature_celsius_normalized REAL,
                humidity_percent_normalized REAL,
                pressure_hpa_normalized REAL,
                air_quality_aqi_normalized REAL,
                load_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sensor_key) REFERENCES {DIM_SENSOR_TABLE}(sensor_key),
                FOREIGN KEY (location_key) REFERENCES {DIM_LOCATION_TABLE}(location_key),
                FOREIGN KEY (time_key) REFERENCES {DIM_TIME_TABLE}(time_key)
            )
            """
        ]

        # Create indexes
        index_statements = [
            f"CREATE INDEX IF NOT EXISTS idx_fact_timestamp ON {FACT_TABLE}(timestamp)",
            f"CREATE INDEX IF NOT EXISTS idx_fact_sensor_key ON {FACT_TABLE}(sensor_key)",
            f"CREATE INDEX IF NOT EXISTS idx_fact_location_key ON {FACT_TABLE}(location_key)",
            f"CREATE INDEX IF NOT EXISTS idx_fact_time_key ON {FACT_TABLE}(time_key)",
        ]

        try:
            with self.engine.connect() as conn:
                # Create tables
                for ddl in ddl_statements:
                    conn.execute(text(ddl))

                # Create indexes
                for idx in index_statements:
                    conn.execute(text(idx))

                conn.commit()
                logger.info("Tables and indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def get_table_info(self) -> Dict:
        """Get information about warehouse tables"""
        if not self.engine:
            self.connect()

        info = {}
        tables = [FACT_TABLE, DIM_SENSOR_TABLE, DIM_LOCATION_TABLE, DIM_TIME_TABLE]

        try:
            with self.engine.connect() as conn:
                for table in tables:
                    # Get row count
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
                    count = result[0] if result else 0

                    # Get table schema
                    schema = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()

                    info[table] = {
                        'row_count': count,
                        'schema': schema
                    }

        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            raise

        return info

    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute SQL query and return results as DataFrame"""
        if not self.engine:
            self.connect()

        try:
            return pd.read_sql_query(query, self.engine)
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            raise

    def bulk_insert(self, df: pd.DataFrame, table_name: str, if_exists: str = 'append'):
        """Bulk insert DataFrame to table"""
        if not self.engine:
            self.connect()

        try:
            df.to_sql(table_name, self.engine, if_exists=if_exists, index=False)
            logger.info(f"Successfully inserted {len(df)} rows to {table_name}")
        except Exception as e:
            logger.error(f"Failed to insert data to {table_name}: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")