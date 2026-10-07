"""
ETL Data Loader - Handles extraction, transformation, and loading of sensor data
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from sqlalchemy import text
from .config import *
from .warehouse_manager import WarehouseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataLoader:
    """Handles ETL operations for sensor data"""

    def __init__(self, csv_path: str = CSV_PATH):
        """Initialize data loader"""
        self.csv_path = Path(csv_path)
        self.warehouse = WarehouseManager()
        self.raw_data = None
        self.clean_data = None

    def extract_data(self) -> pd.DataFrame:
        """Extract data from CSV file"""
        try:
            logger.info(f"Loading data from {self.csv_path}")
            self.raw_data = pd.read_csv(self.csv_path)
            logger.info(f"Loaded {len(self.raw_data)} rows with {len(self.raw_data.columns)} columns")
            return self.raw_data
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise

    def data_profiling(self) -> Dict:
        """Profile the raw data"""
        if self.raw_data is None:
            self.extract_data()

        profile = {
            'shape': self.raw_data.shape,
            'columns': list(self.raw_data.columns),
            'dtypes': self.raw_data.dtypes.to_dict(),
            'missing_values': self.raw_data.isnull().sum().to_dict(),
            'duplicates': self.raw_data.duplicated().sum(),
            'memory_usage': f"{self.raw_data.memory_usage(deep=True).sum() / 1024**2:.2f} MB"
        }

        # Numeric columns statistics
        numeric_cols = self.raw_data.select_dtypes(include=[np.number]).columns
        profile['numeric_stats'] = self.raw_data[numeric_cols].describe().to_dict()

        # Categorical columns statistics
        categorical_cols = self.raw_data.select_dtypes(include=['object']).columns
        profile['categorical_stats'] = {}
        for col in categorical_cols:
            profile['categorical_stats'][col] = {
                'unique_count': self.raw_data[col].nunique(),
                'top_values': self.raw_data[col].value_counts().head().to_dict()
            }

        return profile

    def validate_data(self) -> Dict:
        """Validate data quality"""
        if self.raw_data is None:
            self.extract_data()

        validation_results = {
            'total_records': len(self.raw_data),
            'errors': [],
            'warnings': []
        }

        # Check for required columns
        required_cols = ['timestamp', 'sensor_id', 'location', 'temperature_celsius',
                        'humidity_percent', 'pressure_hpa', 'air_quality_aqi']
        missing_cols = [col for col in required_cols if col not in self.raw_data.columns]
        if missing_cols:
            validation_results['errors'].append(f"Missing required columns: {missing_cols}")

        # Check data ranges
        if 'temperature_celsius' in self.raw_data.columns:
            temp_out_of_range = (
                (self.raw_data['temperature_celsius'] < TEMPERATURE_MIN) |
                (self.raw_data['temperature_celsius'] > TEMPERATURE_MAX)
            ).sum()
            if temp_out_of_range > 0:
                validation_results['warnings'].append(f"Temperature out of range: {temp_out_of_range} records")

        if 'humidity_percent' in self.raw_data.columns:
            humidity_out_of_range = (
                (self.raw_data['humidity_percent'] < HUMIDITY_MIN) |
                (self.raw_data['humidity_percent'] > HUMIDITY_MAX)
            ).sum()
            if humidity_out_of_range > 0:
                validation_results['warnings'].append(f"Humidity out of range: {humidity_out_of_range} records")

        if 'pressure_hpa' in self.raw_data.columns:
            pressure_out_of_range = (
                (self.raw_data['pressure_hpa'] < PRESSURE_MIN) |
                (self.raw_data['pressure_hpa'] > PRESSURE_MAX)
            ).sum()
            if pressure_out_of_range > 0:
                validation_results['warnings'].append(f"Pressure out of range: {pressure_out_of_range} records")

        if 'air_quality_aqi' in self.raw_data.columns:
            aqi_out_of_range = (
                (self.raw_data['air_quality_aqi'] < AQI_MIN) |
                (self.raw_data['air_quality_aqi'] > AQI_MAX)
            ).sum()
            if aqi_out_of_range > 0:
                validation_results['warnings'].append(f"AQI out of range: {aqi_out_of_range} records")

        # Check for duplicates
        duplicates = self.raw_data.duplicated().sum()
        if duplicates > 0:
            validation_results['warnings'].append(f"Duplicate records found: {duplicates}")

        # Check for missing values in critical columns
        for col in required_cols:
            if col in self.raw_data.columns:
                missing = self.raw_data[col].isnull().sum()
                if missing > 0:
                    validation_results['warnings'].append(f"Missing values in {col}: {missing}")

        validation_results['is_valid'] = len(validation_results['errors']) == 0

        return validation_results

    def transform_data(self) -> pd.DataFrame:
        """Transform and clean the data"""
        if self.raw_data is None:
            self.extract_data()

        logger.info("Starting data transformation...")

        # Make a copy for transformation
        self.clean_data = self.raw_data.copy()

        # Convert timestamp to datetime
        self.clean_data['timestamp'] = pd.to_datetime(self.clean_data['timestamp'])

        # Clean location names (standardize case)
        self.clean_data['location'] = self.clean_data['location'].str.title()

        # Handle duplicates - keep first occurrence
        duplicates_before = len(self.clean_data)
        self.clean_data = self.clean_data.drop_duplicates()
        duplicates_removed = duplicates_before - len(self.clean_data)
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate records")

        # Handle outliers (clip to reasonable ranges)
        self.clean_data['temperature_celsius'] = self.clean_data['temperature_celsius'].clip(
            TEMPERATURE_MIN, TEMPERATURE_MAX
        )
        self.clean_data['humidity_percent'] = self.clean_data['humidity_percent'].clip(
            HUMIDITY_MIN, HUMIDITY_MAX
        )
        self.clean_data['pressure_hpa'] = self.clean_data['pressure_hpa'].clip(
            PRESSURE_MIN, PRESSURE_MAX
        )
        self.clean_data['air_quality_aqi'] = self.clean_data['air_quality_aqi'].clip(
            AQI_MIN, AQI_MAX
        )

        # Fill missing values if any
        numeric_cols = self.clean_data.select_dtypes(include=[np.number]).columns
        self.clean_data[numeric_cols] = self.clean_data[numeric_cols].fillna(
            self.clean_data[numeric_cols].median()
        )

        logger.info(f"Data transformation completed. Clean dataset: {len(self.clean_data)} rows")
        return self.clean_data

    def prepare_dimension_data(self) -> Dict[str, pd.DataFrame]:
        """Prepare dimension tables data"""
        if self.clean_data is None:
            self.transform_data()

        dimensions = {}

        # Sensors dimension
        sensors_df = self.clean_data[['sensor_id', 'status']].drop_duplicates(
            subset=['sensor_id'], keep='last'
        )
        sensors_df = sensors_df.reset_index(drop=True)
        sensors_df.insert(0, 'sensor_key', sensors_df.index + 1)
        dimensions['sensors'] = sensors_df

        # Locations dimension
        locations_df = self.clean_data[['location']].drop_duplicates()
        locations_df.columns = ['location_name']
        locations_df = locations_df.reset_index(drop=True)
        locations_df.insert(0, 'location_key', locations_df.index + 1)
        dimensions['locations'] = locations_df

        # Time dimension
        time_df = self.clean_data[[
            'timestamp', 'year', 'month', 'day', 'hour',
            'day_of_week', 'is_weekend', 'time_period'
        ]].copy()

        # Create date column for time dimension
        time_df['full_date'] = time_df['timestamp'].dt.date
        time_df = time_df[['full_date', 'year', 'month', 'day', 'hour',
                          'day_of_week', 'is_weekend', 'time_period']].drop_duplicates()
        time_df = time_df.reset_index(drop=True)
        time_df.insert(0, 'time_key', time_df.index + 1)
        dimensions['time'] = time_df

        logger.info(f"Prepared dimensions: Sensors={len(dimensions['sensors'])}, "
                   f"Locations={len(dimensions['locations'])}, Time={len(dimensions['time'])}")

        return dimensions

    def prepare_fact_data(self, dimensions: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Prepare fact table data with foreign keys"""
        if self.clean_data is None:
            self.transform_data()

        # Create dimension lookup dictionaries
        sensor_lookup = dict(zip(dimensions['sensors']['sensor_id'],
                                dimensions['sensors'].index + 1))
        location_lookup = dict(zip(dimensions['locations']['location_name'],
                                  dimensions['locations'].index + 1))

        # For time dimension, create lookup based on the full date and hour.
        time_lookup = dict(zip(
            dimensions['time']['full_date'].astype(str) + ' ' +
            dimensions['time']['hour'].astype(str).str.zfill(2),
            dimensions['time']['time_key']
        ))

        # Prepare fact data
        fact_df = self.clean_data.copy()

        # Add foreign keys
        fact_df['sensor_key'] = fact_df['sensor_id'].map(sensor_lookup)
        fact_df['location_key'] = fact_df['location'].map(location_lookup)
        time_lookup_keys = fact_df['timestamp'].dt.strftime('%Y-%m-%d %H')
        fact_df['time_key'] = time_lookup_keys.map(time_lookup)

        # Select only required columns for fact table
        fact_columns = [
            'sensor_key', 'location_key', 'time_key', 'timestamp',
            'temperature_celsius', 'humidity_percent', 'pressure_hpa', 'air_quality_aqi',
            'temperature_fahrenheit', 'temperature_kelvin', 'heat_index_f', 'heat_index_c',
            'aqi_category', 'comfort_index', 'temperature_celsius_normalized',
            'humidity_percent_normalized', 'pressure_hpa_normalized', 'air_quality_aqi_normalized'
        ]

        fact_df = fact_df[fact_columns]

        # Remove rows with missing foreign keys
        initial_count = len(fact_df)
        fact_df = fact_df.dropna(subset=['sensor_key', 'location_key', 'time_key'])
        final_count = len(fact_df)

        if initial_count != final_count:
            logger.warning(f"Removed {initial_count - final_count} rows due to missing foreign keys")

        logger.info(f"Prepared fact data: {len(fact_df)} rows")
        return fact_df

    def load_to_warehouse(self, batch_size: int = BATCH_SIZE):
        """Load transformed data to warehouse"""
        # Connect to warehouse
        self.warehouse.connect()

        # Recreate the warehouse schema for a full ETL reload.
        with self.warehouse.engine.begin() as conn:
            for table_name in [FACT_TABLE, DIM_TIME_TABLE, DIM_LOCATION_TABLE, DIM_SENSOR_TABLE]:
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))

        self.warehouse.create_tables()

        # Prepare dimension and fact data
        dimensions = self.prepare_dimension_data()
        fact_data = self.prepare_fact_data(dimensions)

        try:
            with self.warehouse.engine.begin() as conn:
                for table_name in [FACT_TABLE, DIM_SENSOR_TABLE, DIM_LOCATION_TABLE, DIM_TIME_TABLE]:
                    conn.execute(text(f"DELETE FROM {table_name}"))

            # Load dimension tables
            logger.info("Loading dimension tables...")
            self.warehouse.bulk_insert(dimensions['sensors'], DIM_SENSOR_TABLE, if_exists='append')
            self.warehouse.bulk_insert(dimensions['locations'], DIM_LOCATION_TABLE, if_exists='append')
            self.warehouse.bulk_insert(dimensions['time'], DIM_TIME_TABLE, if_exists='append')

            # Load fact table in batches
            logger.info("Loading fact table...")
            total_batches = (len(fact_data) + batch_size - 1) // batch_size

            for i in range(0, len(fact_data), batch_size):
                batch = fact_data.iloc[i:i + batch_size]
                batch_num = (i // batch_size) + 1

                self.warehouse.bulk_insert(batch, FACT_TABLE, if_exists='append')

                logger.info(f"Loaded batch {batch_num}/{total_batches} ({len(batch)} rows)")

            logger.info("Data loading completed successfully!")

            # Print summary
            table_info = self.warehouse.get_table_info()
            for table, info in table_info.items():
                logger.info(f"{table}: {info['row_count']} rows")

        except Exception as e:
            logger.error(f"Failed to load data to warehouse: {e}")
            raise
        finally:
            self.warehouse.close()

    def get_load_summary(self) -> Dict:
        """Get summary of loaded data"""
        if self.clean_data is None:
            return {"error": "No data has been processed yet"}

        return {
            "raw_data_rows": len(self.raw_data) if self.raw_data is not None else 0,
            "clean_data_rows": len(self.clean_data),
            "data_quality_score": self._calculate_quality_score(),
            "load_timestamp": datetime.now().isoformat()
        }

    def _calculate_quality_score(self) -> float:
        """Calculate data quality score (0-100)"""
        if self.clean_data is None:
            return 0.0

        # Simple quality score based on completeness and validity
        total_cells = self.clean_data.size
        non_null_cells = total_cells - self.clean_data.isnull().sum().sum()
        completeness = (non_null_cells / total_cells) * 100

        return round(completeness, 2)