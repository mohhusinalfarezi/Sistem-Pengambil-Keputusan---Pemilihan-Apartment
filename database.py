"""
database.py - Inisialisasi SQLite dan seed data awal
SPK Pemilihan Apartemen di Semarang
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "spk_apartemen.db")


def get_connection():
    """Mengembalikan koneksi SQLite dengan row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Membuat tabel dan mengisi data awal jika belum ada."""
    conn = get_connection()
    cur = conn.cursor()

    # ------------------------------------------------------------------ #
    #  DDL - Buat tabel jika belum ada
    # ------------------------------------------------------------------ #
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS kriteria (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            kode    TEXT    NOT NULL UNIQUE,
            nama    TEXT    NOT NULL,
            tipe    TEXT    NOT NULL CHECK(tipe IN ('benefit','cost')),
            bobot   REAL    NOT NULL CHECK(bobot > 0 AND bobot <= 1)
        );

        CREATE TABLE IF NOT EXISTS alternatif (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_apartemen  TEXT    NOT NULL,
            lokasi          TEXT    NOT NULL,
            deskripsi       TEXT
        );

        CREATE TABLE IF NOT EXISTS nilai_alternatif (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            alternatif_id   INTEGER NOT NULL REFERENCES alternatif(id) ON DELETE CASCADE,
            kriteria_id     INTEGER NOT NULL REFERENCES kriteria(id)   ON DELETE CASCADE,
            nilai           REAL    NOT NULL,
            UNIQUE(alternatif_id, kriteria_id)
        );

        CREATE TABLE IF NOT EXISTS hasil_keputusan (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            alternatif_id       INTEGER NOT NULL REFERENCES alternatif(id) ON DELETE CASCADE,
            nilai_preferensi    REAL    NOT NULL,
            peringkat           INTEGER NOT NULL,
            tanggal             TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)

    # ------------------------------------------------------------------ #
    #  Seed data - hanya jika tabel masih kosong
    # ------------------------------------------------------------------ #
    if cur.execute("SELECT COUNT(*) FROM kriteria").fetchone()[0] == 0:
        kriteria_data = [
            ("C1", "Sewa per Tahun (Juta Rp)",                "cost",    0.20),
            ("C2", "Luas Unit (m²)",                          "benefit", 0.10),
            ("C3", "Fasilitas Gedung & Unit (1-5)",            "benefit", 0.10),
            ("C4", "Jarak ke Pusat Kota (km)",                 "cost",    0.20),
            ("C5", "Tingkat Keamanan (1-5)",                   "benefit", 0.15),
            ("C6", "Biaya Tambahan IPL/Listrik/Air (Juta Rp)", "cost",    0.10),
            ("C7", "Jumlah Kamar Tidur",                       "benefit", 0.15),
        ]
        cur.executemany(
            "INSERT INTO kriteria (kode, nama, tipe, bobot) VALUES (?,?,?,?)",
            kriteria_data,
        )

    if cur.execute("SELECT COUNT(*) FROM alternatif").fetchone()[0] == 0:
        alternatif_data = [
            ("Alton Residence",  "Jl. Pemuda, Semarang Tengah",    "Apartemen premium di pusat kota dengan fasilitas lengkap."),
            ("Warhol Residence", "Jl. Pandanaran, Semarang Tengah","Apartemen modern bertema seni dengan lokasi strategis."),
            ("The Pinnacle",     "Jl. Gajahmada, Semarang Tengah", "Apartemen mewah setinggi 32 lantai dengan pemandangan kota."),
            ("MG Suites",        "Jl. MH Thamrin, Semarang Tengah","Apartemen bintang lima bersebelahan dengan MGM Hotel."),
            ("Cordova",          "Jl. Siliwangi, Semarang Barat",  "Apartemen keluarga dengan lingkungan asri di kawasan barat."),
            ("Candiland",        "Jl. Teuku Umar, Semarang Barat", "Apartemen berkonsep cluster eksklusif di area tenang."),
            ("Paltrow City",     "Jl. Paltrow, Ngaliyan",          "Apartemen terjangkau di kawasan berkembang Semarang Barat."),
        ]
        cur.executemany(
            "INSERT INTO alternatif (nama_apartemen, lokasi, deskripsi) VALUES (?,?,?)",
            alternatif_data,
        )

    # Seed nilai alternatif jika belum ada
    if cur.execute("SELECT COUNT(*) FROM nilai_alternatif").fetchone()[0] == 0:
        # Urutan kolom: (nama, C1-sewa, C2-luas, C3-fasilitas, C4-jarak, C5-keamanan, C6-biaya_tambahan, C7-kamar)
        nilai_data = {
            "Alton Residence":  [75, 36, 4, 1.5, 4, 2.5, 2],
            "Warhol Residence": [65, 32, 4, 2.0, 4, 2.0, 1],
            "The Pinnacle":     [90, 48, 5, 1.0, 5, 3.0, 2],
            "MG Suites":        [120, 60, 5, 1.2, 5, 4.0, 3],
            "Cordova":          [45, 40, 3, 5.0, 3, 1.5, 2],
            "Candiland":        [50, 38, 3, 4.5, 3, 1.8, 2],
            "Paltrow City":     [35, 28, 2, 7.0, 3, 1.2, 1],
        }
        alt_rows = cur.execute("SELECT id, nama_apartemen FROM alternatif").fetchall()
        krt_rows = cur.execute("SELECT id FROM kriteria ORDER BY id").fetchall()

        for alt in alt_rows:
            vals = nilai_data.get(alt["nama_apartemen"])
            if vals:
                for idx, krt in enumerate(krt_rows):
                    cur.execute(
                        "INSERT OR IGNORE INTO nilai_alternatif (alternatif_id, kriteria_id, nilai) VALUES (?,?,?)",
                        (alt["id"], krt["id"], vals[idx]),
                    )

    conn.commit()
    conn.close()
    print("[DB] Database diinisialisasi:", DB_PATH)


if __name__ == "__main__":
    init_db()
