from pathlib import Path
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

PROJECT_ROOT = Path(__file__).parent
DATABASE_FILE = PROJECT_ROOT / "warehouse" / "sensor_warehouse.db"
OUTPUT_DIR = PROJECT_ROOT / "grafik"
OUTPUT_DIR.mkdir(exist_ok=True)

sns.set_theme(style="whitegrid", context="talk")
COLORS = {
    "blue": "#2563EB",
    "teal": "#0F766E",
    "orange": "#EA580C",
    "red": "#DC2626",
    "purple": "#7C3AED",
}


def save_chart(fig: plt.Figure, filename: str) -> None:
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / f"{filename}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / f"{filename}.svg", bbox_inches="tight")
    plt.close(fig)


with sqlite3.connect(DATABASE_FILE) as connection:
    location = pd.read_sql_query(
        """
        SELECT l.location_name,
               AVG(f.air_quality_aqi) AS avg_aqi,
               AVG(f.temperature_celsius) AS avg_temperature,
               AVG(f.humidity_percent) AS avg_humidity,
               COUNT(*) AS reading_count
        FROM fact_sensor_readings f
        JOIN dim_locations l ON f.location_key = l.location_key
        GROUP BY l.location_name
        ORDER BY avg_aqi
        """,
        connection,
    )
    temporal = pd.read_sql_query(
        """
        SELECT t.time_period,
               AVG(f.air_quality_aqi) AS avg_aqi,
               AVG(f.temperature_celsius) AS avg_temperature,
               COUNT(*) AS reading_count
        FROM fact_sensor_readings f
        JOIN dim_time t ON f.time_key = t.time_key
        GROUP BY t.time_period
        ORDER BY avg_aqi
        """,
        connection,
    )
    sensors = pd.read_sql_query(
        """
        SELECT s.sensor_id, COUNT(*) AS reading_count
        FROM fact_sensor_readings f
        JOIN dim_sensors s ON f.sensor_key = s.sensor_key
        GROUP BY s.sensor_id
        ORDER BY s.sensor_id
        """,
        connection,
    )

fig, ax = plt.subplots(figsize=(12, 7))
bars = ax.bar(location["location_name"], location["avg_aqi"], color=COLORS["blue"])
ax.set_title("Rata-rata AQI Berdasarkan Lokasi", weight="bold")
ax.set_xlabel("Lokasi")
ax.set_ylabel("Rata-rata AQI")
ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=10)
save_chart(fig, "01_rata_rata_aqi_per_lokasi")

fig, ax = plt.subplots(figsize=(12, 7))
x = range(len(location))
width = 0.36
bars_temp = ax.bar(
    [i - width / 2 for i in x],
    location["avg_temperature"],
    width,
    label="Suhu (°C)",
    color=COLORS["orange"],
)
bars_humidity = ax.bar(
    [i + width / 2 for i in x],
    location["avg_humidity"],
    width,
    label="Kelembapan (%)",
    color=COLORS["teal"],
)
ax.set_title("Rata-rata Suhu dan Kelembapan Berdasarkan Lokasi", weight="bold")
ax.set_xlabel("Lokasi")
ax.set_ylabel("Nilai rata-rata")
ax.set_xticks(list(x), location["location_name"])
ax.legend()
ax.bar_label(bars_temp, fmt="%.1f", padding=2, fontsize=9)
ax.bar_label(bars_humidity, fmt="%.1f", padding=2, fontsize=9)
save_chart(fig, "02_suhu_dan_kelembapan_per_lokasi")

fig, ax = plt.subplots(figsize=(12, 7))
bars = ax.bar(temporal["time_period"], temporal["avg_aqi"], color=COLORS["purple"])
ax.set_title("Rata-rata AQI Berdasarkan Periode Waktu", weight="bold")
ax.set_xlabel("Periode waktu")
ax.set_ylabel("Rata-rata AQI")
ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=10)
save_chart(fig, "03_rata_rata_aqi_periode_waktu")

fig, ax = plt.subplots(figsize=(12, 7))
bars = ax.bar(sensors["sensor_id"], sensors["reading_count"], color=COLORS["teal"])
ax.set_title("Jumlah Pembacaan per Sensor", weight="bold")
ax.set_xlabel("Sensor")
ax.set_ylabel("Jumlah pembacaan")
ax.tick_params(axis="x", rotation=45)
ax.bar_label(bars, fmt="%d", padding=3, fontsize=9)
save_chart(fig, "04_jumlah_pembacaan_per_sensor")

summary = OUTPUT_DIR / "README.txt"
summary.write_text(
    "Grafik hasil analisis data warehouse\n"
    "====================================\n"
    "PNG: 300 DPI untuk laporan dan presentasi.\n"
    "SVG: format vektor untuk hasil paling tajam saat diperbesar.\n"
    "Sumber data: warehouse/sensor_warehouse.db\n",
    encoding="utf-8",
)
print(f"Generated charts in {OUTPUT_DIR}")
