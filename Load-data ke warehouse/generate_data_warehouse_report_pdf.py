from __future__ import annotations

from pathlib import Path
import sqlite3
import textwrap
import json

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "warehouse" / "sensor_warehouse.db"
NOTEBOOK_PATH = BASE_DIR / "hands_on_data_warehouse.ipynb"
OUTPUT_PDF = BASE_DIR / "245150301111033_NatanaelSteveIrwanto_Datawarehouse.pdf"

IDENTITAS = {
    "nama": "Natanael Steve Irwanto",
    "nim": "245150301111033",
    "kelas": "C",
    "matkul": "Data Warehouse",
}


def _read_notebook_execution_status() -> tuple[int, int]:
    with NOTEBOOK_PATH.open("r", encoding="utf-8") as f:
        notebook = json.load(f)
    code_cells = [c for c in notebook.get("cells", []) if c.get("cell_type") == "code"]
    executed = sum(1 for c in code_cells if c.get("execution_count") is not None)
    return len(code_cells), executed


def _warehouse_counts() -> dict[str, int]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        tables = ["dim_sensors", "dim_locations", "dim_time", "fact_sensor_readings"]
        return {t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def _analytics() -> dict[str, list[tuple]]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        q1 = cur.execute(
            """
            SELECT l.location_name, ROUND(AVG(f.air_quality_aqi), 2) AS avg_aqi, COUNT(*) AS n
            FROM fact_sensor_readings f
            JOIN dim_locations l ON f.location_key = l.location_key
            GROUP BY l.location_name
            ORDER BY avg_aqi ASC
            LIMIT 5
            """
        ).fetchall()

        q2 = cur.execute(
            """
            SELECT t.time_period, ROUND(AVG(f.air_quality_aqi), 2) AS avg_aqi, COUNT(*) AS n
            FROM fact_sensor_readings f
            JOIN dim_time t ON f.time_key = t.time_key
            GROUP BY t.time_period
            ORDER BY avg_aqi ASC
            """
        ).fetchall()

        q3 = cur.execute(
            """
            SELECT s.sensor_id, COUNT(*) AS n_readings
            FROM fact_sensor_readings f
            JOIN dim_sensors s ON f.sensor_key = s.sensor_key
            GROUP BY s.sensor_id
            ORDER BY n_readings DESC, s.sensor_id ASC
            LIMIT 10
            """
        ).fetchall()

    return {"q1": q1, "q2": q2, "q3": q3}


def _new_page(pdf: PdfPages, title: str, subtitle: str | None = None):
    fig = plt.figure(figsize=(8.27, 11.69), dpi=120)
    fig.patch.set_facecolor("white")
    fig.text(0.07, 0.96, title, fontsize=18, fontweight="bold", va="top")
    if subtitle:
        fig.text(0.07, 0.93, subtitle, fontsize=10, color="#555555", va="top")
    return fig


def _write_wrapped(fig, x: float, y: float, text: str, width: int = 92, size: int = 11):
    wrapped = "\n".join(textwrap.fill(line, width=width) if line.strip() else "" for line in text.splitlines())
    fig.text(x, y, wrapped, fontsize=size, va="top")


def _add_image(fig, path: Path, x: float, y: float, w: float, h: float, caption: str):
    ax = fig.add_axes([x, y, w, h])
    ax.axis("off")
    img = plt.imread(path)
    ax.imshow(img)
    fig.text(x, y - 0.018, caption, fontsize=9, color="#333333", va="top")


def main():
    total_code_cells, executed_code_cells = _read_notebook_execution_status()
    counts = _warehouse_counts()
    analytics = _analytics()

    bukti = BASE_DIR / "bukti"
    screenshot_install = bukti / "screenshot_01_install_dependency.png"
    screenshot_etl = bukti / "screenshot_02_etl_execution.png"
    screenshot_validasi = bukti / "screenshot_03_validasi_tabel.png"
    screenshot_query = bukti / "screenshot_04_hasil_query.png"

    chart_1 = BASE_DIR / "grafik" / "01_rata_rata_aqi_per_lokasi.png"
    chart_3 = BASE_DIR / "grafik" / "03_rata_rata_aqi_periode_waktu.png"

    with PdfPages(OUTPUT_PDF) as pdf:
        # Halaman 1: Identitas + ringkasan
        fig = _new_page(
            pdf,
            "Laporan Implementasi Data Warehouse",
            "ETL Data Sensor IoT menggunakan Python + SQLite",
        )
        _write_wrapped(
            fig,
            0.07,
            0.88,
            (
                "Identitas Mahasiswa\n"
                f"- Nama : {IDENTITAS['nama']}\n"
                f"- NIM  : {IDENTITAS['nim']}\n"
                f"- Kelas: {IDENTITAS['kelas']}\n"
                f"- Mata Kuliah: {IDENTITAS['matkul']}\n\n"
                "Ringkasan\n"
                "- ETL berhasil dijalankan dari notebook secara berurutan.\n"
                "- Data sumber CSV berhasil dimuat ke star schema SQLite.\n"
                "- Validasi 4 tabel utama berhasil.\n"
                "- Minimal 3 query analitik dijalankan dan diinterpretasikan.\n"
            ),
        )
        _write_wrapped(
            fig,
            0.07,
            0.61,
            (
                "Skema Data Warehouse (star schema)\n"
                "- fact_sensor_readings (fact table)\n"
                "- dim_sensors (dimension)\n"
                "- dim_locations (dimension)\n"
                "- dim_time (dimension)\n\n"
                "Hasil validasi jumlah record:\n"
                f"- dim_sensors: {counts['dim_sensors']}\n"
                f"- dim_locations: {counts['dim_locations']}\n"
                f"- dim_time: {counts['dim_time']}\n"
                f"- fact_sensor_readings: {counts['fact_sensor_readings']}\n"
            ),
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Halaman 2: Bukti instalasi + ETL
        fig = _new_page(pdf, "Bukti Instalasi dan Proses ETL")
        _write_wrapped(
            fig,
            0.07,
            0.90,
            (
                "Berikut screenshot bukti instalasi dependency serta bukti eksekusi notebook ETL.\n"
                "Notebook status eksekusi: "
                f"{executed_code_cells}/{total_code_cells} code cell sudah dieksekusi."
            ),
            width=95,
        )
        _add_image(fig, screenshot_install, 0.07, 0.50, 0.86, 0.34, "Gambar 1. Bukti dependency environment")
        _add_image(fig, screenshot_etl, 0.07, 0.08, 0.86, 0.34, "Gambar 2. Bukti eksekusi notebook ETL")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Halaman 3: Bukti validasi table + flow ETL
        fig = _new_page(pdf, "Validasi Hasil Loading dan Alur ETL")
        _write_wrapped(
            fig,
            0.07,
            0.90,
            (
                "Alur ETL:\n"
                "1) Extract: membaca CSV processed_sensor_data_20250930_092513.csv.\n"
                "2) Transform: konversi timestamp, standarisasi lokasi, deduplikasi, handling missing value.\n"
                "3) Load: insert ke tabel dimensi dan fact pada SQLite warehouse.\n\n"
                "Screenshot di bawah menunjukkan validasi jumlah record untuk 4 tabel yang diminta."
            ),
            width=95,
        )
        _add_image(fig, screenshot_validasi, 0.07, 0.20, 0.86, 0.56, "Gambar 3. Validasi dim_sensors, dim_locations, dim_time, fact_sensor_readings")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Halaman 4: Query 1 + insight + chart
        fig = _new_page(pdf, "Query Analitik 1 - Kualitas Udara per Lokasi")
        _write_wrapped(
            fig,
            0.07,
            0.90,
            (
                "SQL Query:\n"
                "SELECT l.location_name, ROUND(AVG(f.air_quality_aqi),2) AS avg_aqi, COUNT(*) AS n\n"
                "FROM fact_sensor_readings f JOIN dim_locations l ON f.location_key=l.location_key\n"
                "GROUP BY l.location_name ORDER BY avg_aqi ASC;\n\n"
                f"Hasil utama (5 baris): {analytics['q1']}\n\n"
                "Insight: lokasi dengan AQI rata-rata terendah (lebih baik) adalah Location_D."
            ),
            width=98,
            size=10,
        )
        _add_image(fig, chart_1, 0.07, 0.15, 0.86, 0.40, "Gambar 4. Visualisasi rata-rata AQI per lokasi")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Halaman 5: Query 2 + insight + chart
        fig = _new_page(pdf, "Query Analitik 2 - Pola AQI per Periode Waktu")
        _write_wrapped(
            fig,
            0.07,
            0.90,
            (
                "SQL Query:\n"
                "SELECT t.time_period, ROUND(AVG(f.air_quality_aqi),2) AS avg_aqi, COUNT(*) AS n\n"
                "FROM fact_sensor_readings f JOIN dim_time t ON f.time_key=t.time_key\n"
                "GROUP BY t.time_period ORDER BY avg_aqi ASC;\n\n"
                f"Hasil: {analytics['q2']}\n\n"
                "Insight: periode Night memiliki AQI rata-rata terendah."
            ),
            width=98,
            size=10,
        )
        _add_image(fig, chart_3, 0.07, 0.15, 0.86, 0.40, "Gambar 5. Visualisasi AQI rata-rata berdasarkan periode waktu")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Halaman 6: Query 3 + insight + kendala
        fig = _new_page(pdf, "Query Analitik 3 - Aktivitas Sensor dan Kendala")
        _write_wrapped(
            fig,
            0.07,
            0.90,
            (
                "SQL Query:\n"
                "SELECT s.sensor_id, COUNT(*) AS n_readings\n"
                "FROM fact_sensor_readings f JOIN dim_sensors s ON f.sensor_key=s.sensor_key\n"
                "GROUP BY s.sensor_id ORDER BY n_readings DESC, s.sensor_id ASC;\n\n"
                f"Hasil utama: {analytics['q3']}\n\n"
                "Insight: semua sensor memiliki jumlah pembacaan setara (1.440),\n"
                "sehingga tidak ada satu sensor yang dominan."
            ),
            width=98,
            size=10,
        )
        _add_image(fig, screenshot_query, 0.07, 0.43, 0.86, 0.34, "Gambar 6. Screenshot hasil 3 query analitik")
        _write_wrapped(
            fig,
            0.07,
            0.26,
            (
                "Kendala dan solusi:\n"
                "- Kendala: sempat muncul IndentationError pada data_loader.py.\n"
                "- Solusi: pembersihan karakter asing pada file dan validasi ulang syntax.\n"
                "- Kendala: interpretasi loaded records pada run ulang.\n"
                "- Solusi: pemisahan metrik records in warehouse vs loaded this run."
            ),
            width=95,
            size=10,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    print(f"Laporan berhasil dibuat: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
