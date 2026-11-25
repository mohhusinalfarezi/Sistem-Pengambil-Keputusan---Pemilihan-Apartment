"""
app.py - Flask Application untuk SPK Pemilihan Apartemen
Metode Simple Additive Weighting (SAW)
"""

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from database import init_db, get_connection
from saw import rank_alternatives, validate_input, hitung_saw
import json
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
app.secret_key = "spk-apartemen-semarang-2024"

# Inisialisasi database saat aplikasi pertama dijalankan
with app.app_context():
    init_db()


# ======================================================================== #
#  HELPERS
# ======================================================================== #

def fetch_kriterias(conn):
    return conn.execute("SELECT * FROM kriteria ORDER BY id").fetchall()


def fetch_alternatifs(conn):
    return conn.execute("SELECT * FROM alternatif ORDER BY id").fetchall()


def fetch_nilai_map(conn):
    rows = conn.execute("SELECT alternatif_id, kriteria_id, nilai FROM nilai_alternatif").fetchall()
    return {(r["alternatif_id"], r["kriteria_id"]): r["nilai"] for r in rows}


def total_bobot(conn):
    result = conn.execute("SELECT ROUND(SUM(bobot), 10) AS total FROM kriteria").fetchone()
    return result["total"] if result["total"] else 0.0


# ======================================================================== #
#  INDEX
# ======================================================================== #

@app.route("/")
def index():
    conn = get_connection()
    kriterias   = fetch_kriterias(conn)
    alternatifs = fetch_alternatifs(conn)
    nilai_map   = fetch_nilai_map(conn)

    n_kriteria   = len(kriterias)
    n_alternatif = len(alternatifs)
    n_nilai      = conn.execute("SELECT COUNT(*) AS c FROM nilai_alternatif").fetchone()["c"]

    # Hitung jumlah sesi tersimpan dari tabel hasil_keputusan (berdasarkan distinct timestamp/sesi)
    row_sesi = conn.execute("SELECT COUNT(DISTINCT tanggal) AS c FROM hasil_keputusan").fetchone()
    n_sesi   = row_sesi["c"] if row_sesi and row_sesi["c"] is not None else 0
    n_hasil  = n_sesi  # Kompatibilitas variabel n_hasil & n_sesi

    total = total_bobot(conn)

    # Validasi dan jalankan perhitungan SAW otomatis jika data lengkap & valid
    errors = validate_input(alternatifs, kriterias, nilai_map)
    saw_result = None
    results = []
    top = None
    skor_tertinggi = 0.0

    if not errors and alternatifs and kriterias:
        saw_result = hitung_saw(alternatifs, kriterias, nilai_map)
        results = saw_result.get("results", [])
        if results:
            top = results[0]
            skor_tertinggi = top["nilai_preferensi"]

    conn.close()

    return render_template(
        "index.html",
        n_kriteria=n_kriteria,
        n_alternatif=n_alternatif,
        n_nilai=n_nilai,
        n_hasil=n_hasil,
        n_sesi=n_sesi,
        total_bobot=total,
        saw=saw_result,
        results=results,
        top=top,
        top_alternatif=top,
        skor_tertinggi=skor_tertinggi,
        errors=errors
    )


# ======================================================================== #
#  KRITERIA
# ======================================================================== #

@app.route("/kriteria")
def kriteria_list():
    conn = get_connection()
    kriterias = fetch_kriterias(conn)
    total = total_bobot(conn)
    conn.close()
    return render_template("kriteria.html", kriterias=kriterias, total_bobot=total)


@app.route("/kriteria/tambah", methods=["GET", "POST"])
def kriteria_tambah():
    if request.method == "POST":
        kode  = request.form.get("kode", "").strip().upper()
        nama  = request.form.get("nama", "").strip()
        tipe  = request.form.get("tipe", "")
        bobot_str = request.form.get("bobot", "0")

        # Validasi
        errors = []
        if not kode:
            errors.append("Kode kriteria wajib diisi.")
        if not nama:
            errors.append("Nama kriteria wajib diisi.")
        if tipe not in ("benefit", "cost"):
            errors.append("Tipe harus 'benefit' atau 'cost'.")
        try:
            bobot = round(float(bobot_str), 10)
            if bobot <= 0 or bobot > 1:
                errors.append("Bobot harus antara 0 dan 1 (eksklusif 0).")
        except ValueError:
            errors.append("Bobot harus berupa angka desimal.")
            bobot = 0.0

        if not errors:
            conn = get_connection()
            # Cek duplikat kode
            if conn.execute("SELECT id FROM kriteria WHERE kode=?", (kode,)).fetchone():
                errors.append(f"Kode '{kode}' sudah digunakan.")
            else:
                new_total = round(total_bobot(conn) + bobot, 10)
                if new_total > 1.00001:
                    errors.append(f"Total bobot akan menjadi {new_total:.4f} (melebihi 1.00). Sesuaikan bobot.")
                else:
                    conn.execute(
                        "INSERT INTO kriteria (kode, nama, tipe, bobot) VALUES (?,?,?,?)",
                        (kode, nama, tipe, bobot)
                    )
                    conn.commit()
                    flash(f"Kriteria '{nama}' berhasil ditambahkan.", "success")
                    conn.close()
                    return redirect(url_for("kriteria_list"))
            conn.close()

        for e in errors:
            flash(e, "danger")
        return render_template("kriteria_form.html",
                               action="Tambah", form=request.form)

    return render_template("kriteria_form.html", action="Tambah", form={})


@app.route("/kriteria/edit/<int:kid>", methods=["GET", "POST"])
def kriteria_edit(kid):
    conn = get_connection()
    krt = conn.execute("SELECT * FROM kriteria WHERE id=?", (kid,)).fetchone()
    if not krt:
        conn.close()
        flash("Kriteria tidak ditemukan.", "warning")
        return redirect(url_for("kriteria_list"))

    if request.method == "POST":
        kode  = request.form.get("kode", "").strip().upper()
        nama  = request.form.get("nama", "").strip()
        tipe  = request.form.get("tipe", "")
        bobot_str = request.form.get("bobot", "0")

        errors = []
        if not kode:
            errors.append("Kode kriteria wajib diisi.")
        if not nama:
            errors.append("Nama kriteria wajib diisi.")
        if tipe not in ("benefit", "cost"):
            errors.append("Tipe harus 'benefit' atau 'cost'.")
        try:
            bobot = round(float(bobot_str), 10)
            if bobot <= 0 or bobot > 1:
                errors.append("Bobot harus antara 0 dan 1.")
        except ValueError:
            errors.append("Bobot harus berupa angka desimal.")
            bobot = 0.0

        if not errors:
            # Duplikat kode (selain dirinya sendiri)
            dup = conn.execute(
                "SELECT id FROM kriteria WHERE kode=? AND id<>?", (kode, kid)
            ).fetchone()
            if dup:
                errors.append(f"Kode '{kode}' sudah digunakan.")
            else:
                # Total bobot tanpa diri sendiri + bobot baru
                other_total = conn.execute(
                    "SELECT ROUND(SUM(bobot),10) AS t FROM kriteria WHERE id<>?", (kid,)
                ).fetchone()["t"] or 0.0
                new_total = round(other_total + bobot, 10)
                if new_total > 1.00001:
                    errors.append(f"Total bobot akan menjadi {new_total:.4f} (melebihi 1.00).")
                else:
                    conn.execute(
                        "UPDATE kriteria SET kode=?, nama=?, tipe=?, bobot=? WHERE id=?",
                        (kode, nama, tipe, bobot, kid)
                    )
                    conn.commit()
                    flash(f"Kriteria '{nama}' berhasil diperbarui.", "success")
                    conn.close()
                    return redirect(url_for("kriteria_list"))

        for e in errors:
            flash(e, "danger")
        conn.close()
        return render_template("kriteria_form.html", action="Edit",
                               form=request.form, krt=krt)

    conn.close()
    return render_template("kriteria_form.html", action="Edit", form=krt, krt=krt)


@app.route("/kriteria/hapus/<int:kid>", methods=["POST"])
def kriteria_hapus(kid):
    conn = get_connection()
    krt = conn.execute("SELECT nama FROM kriteria WHERE id=?", (kid,)).fetchone()
    if krt:
        conn.execute("DELETE FROM kriteria WHERE id=?", (kid,))
        conn.commit()
        flash(f"Kriteria '{krt['nama']}' berhasil dihapus.", "success")
    else:
        flash("Kriteria tidak ditemukan.", "warning")
    conn.close()
    return redirect(url_for("kriteria_list"))


# ======================================================================== #
#  ALTERNATIF
# ======================================================================== #

@app.route("/alternatif")
def alternatif_list():
    conn = get_connection()
    alts = fetch_alternatifs(conn)
    kriterias = fetch_kriterias(conn)
    nilai_map = fetch_nilai_map(conn)
    # Hitung kelengkapan nilai
    completeness = {}
    for alt in alts:
        filled = sum(1 for krt in kriterias if (alt["id"], krt["id"]) in nilai_map)
        completeness[alt["id"]] = (filled, len(kriterias))
    conn.close()
    return render_template("alternatif.html", alts=alts, kriterias=kriterias,
                           nilai_map=nilai_map, completeness=completeness)


@app.route("/alternatif/tambah", methods=["GET", "POST"])
def alternatif_tambah():
    conn = get_connection()
    kriterias = fetch_kriterias(conn)

    if request.method == "POST":
        nama   = request.form.get("nama_apartemen", "").strip()
        lokasi = request.form.get("lokasi", "").strip()
        deskripsi = request.form.get("deskripsi", "").strip()

        errors = []
        if not nama:
            errors.append("Nama apartemen wajib diisi.")
        if not lokasi:
            errors.append("Lokasi wajib diisi.")

        nilai_input = {}
        for krt in kriterias:
            val_str = request.form.get(f"nilai_{krt['id']}", "").strip()
            if not val_str:
                errors.append(f"Nilai untuk kriteria '{krt['nama']}' wajib diisi.")
            else:
                try:
                    val = float(val_str)
                    if krt["tipe"] == "cost" and val <= 0:
                        errors.append(
                            f"Nilai kriteria COST '{krt['nama']}' harus > 0 (input: {val})."
                        )
                    else:
                        nilai_input[krt["id"]] = val
                except ValueError:
                    errors.append(f"Nilai '{krt['nama']}' harus berupa angka.")

        if not errors:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO alternatif (nama_apartemen, lokasi, deskripsi) VALUES (?,?,?)",
                (nama, lokasi, deskripsi)
            )
            alt_id = cur.lastrowid
            for krt_id, val in nilai_input.items():
                cur.execute(
                    "INSERT INTO nilai_alternatif (alternatif_id, kriteria_id, nilai) VALUES (?,?,?)",
                    (alt_id, krt_id, val)
                )
            conn.commit()
            conn.close()
            flash(f"Apartemen '{nama}' berhasil ditambahkan.", "success")
            return redirect(url_for("alternatif_list"))

        for e in errors:
            flash(e, "danger")

    conn.close()
    return render_template("alternatif_form.html", action="Tambah",
                           kriterias=kriterias, form=request.form if request.method == "POST" else {},
                           alt=None)


@app.route("/alternatif/edit/<int:aid>", methods=["GET", "POST"])
def alternatif_edit(aid):
    conn = get_connection()
    alt = conn.execute("SELECT * FROM alternatif WHERE id=?", (aid,)).fetchone()
    if not alt:
        conn.close()
        flash("Alternatif tidak ditemukan.", "warning")
        return redirect(url_for("alternatif_list"))

    kriterias = fetch_kriterias(conn)
    nilai_map = fetch_nilai_map(conn)

    if request.method == "POST":
        nama   = request.form.get("nama_apartemen", "").strip()
        lokasi = request.form.get("lokasi", "").strip()
        deskripsi = request.form.get("deskripsi", "").strip()

        errors = []
        if not nama:
            errors.append("Nama apartemen wajib diisi.")
        if not lokasi:
            errors.append("Lokasi wajib diisi.")

        nilai_input = {}
        for krt in kriterias:
            val_str = request.form.get(f"nilai_{krt['id']}", "").strip()
            if not val_str:
                errors.append(f"Nilai kriteria '{krt['nama']}' wajib diisi.")
            else:
                try:
                    val = float(val_str)
                    if krt["tipe"] == "cost" and val <= 0:
                        errors.append(
                            f"Nilai kriteria COST '{krt['nama']}' harus > 0 (input: {val})."
                        )
                    else:
                        nilai_input[krt["id"]] = val
                except ValueError:
                    errors.append(f"Nilai '{krt['nama']}' harus berupa angka.")

        if not errors:
            conn.execute(
                "UPDATE alternatif SET nama_apartemen=?, lokasi=?, deskripsi=? WHERE id=?",
                (nama, lokasi, deskripsi, aid)
            )
            for krt_id, val in nilai_input.items():
                conn.execute(
                    """INSERT INTO nilai_alternatif (alternatif_id, kriteria_id, nilai)
                       VALUES (?,?,?)
                       ON CONFLICT(alternatif_id, kriteria_id) DO UPDATE SET nilai=excluded.nilai""",
                    (aid, krt_id, val)
                )
            conn.commit()
            conn.close()
            flash(f"Apartemen '{nama}' berhasil diperbarui.", "success")
            return redirect(url_for("alternatif_list"))

        for e in errors:
            flash(e, "danger")

    conn.close()
    return render_template("alternatif_form.html", action="Edit",
                           kriterias=kriterias, form=request.form if request.method == "POST" else alt,
                           alt=alt, nilai_map=nilai_map)


@app.route("/alternatif/hapus/<int:aid>", methods=["POST"])
def alternatif_hapus(aid):
    conn = get_connection()
    alt = conn.execute("SELECT nama_apartemen FROM alternatif WHERE id=?", (aid,)).fetchone()
    if alt:
        conn.execute("DELETE FROM alternatif WHERE id=?", (aid,))
        conn.commit()
        flash(f"Apartemen '{alt['nama_apartemen']}' berhasil dihapus.", "success")
    else:
        flash("Alternatif tidak ditemukan.", "warning")
    conn.close()
    return redirect(url_for("alternatif_list"))


# ======================================================================== #
#  HASIL SAW
# ======================================================================== #

@app.route("/hasil", methods=["GET", "POST"])
def hasil():
    conn = get_connection()
    kriterias  = fetch_kriterias(conn)
    alternatifs = fetch_alternatifs(conn)
    nilai_map  = fetch_nilai_map(conn)

    # Validasi data
    errors = validate_input(alternatifs, kriterias, nilai_map)
    if errors:
        conn.close()
        return render_template("hasil.html",
                               errors=errors, kriterias=kriterias,
                               alternatifs=alternatifs, results=None)

    # What-If: ambil bobot dari form jika POST
    bobot_override = None
    whatif_active  = False
    if request.method == "POST" and request.form.get("action") == "whatif":
        bobot_override = {}
        whatif_errors  = []
        total_whatif   = 0.0
        for krt in kriterias:
            val_str = request.form.get(f"wb_{krt['id']}", "").strip()
            try:
                wb = float(val_str)
                if wb < 0 or wb > 1:
                    whatif_errors.append(f"Bobot '{krt['nama']}' harus 0–1.")
                else:
                    bobot_override[krt["id"]] = wb
                    total_whatif += wb
            except ValueError:
                whatif_errors.append(f"Bobot '{krt['nama']}' harus angka.")

        if whatif_errors:
            for e in whatif_errors:
                flash(e, "danger")
            bobot_override = None
        elif abs(total_whatif - 1.0) > 0.001:
            flash(f"Total bobot simulasi = {total_whatif:.4f}. Harus tepat 1.00 (100%).", "warning")
            bobot_override = None
        else:
            whatif_active = True

    saw_result = rank_alternatives(alternatifs, kriterias, nilai_map, bobot_override)
    conn.close()

    return render_template("hasil.html",
                           kriterias=kriterias,
                           alternatifs=alternatifs,
                           saw=saw_result,
                           errors=[],
                           whatif_active=whatif_active,
                           bobot_override=bobot_override,
                           form=request.form)


@app.route("/hasil/simpan", methods=["POST"])
def simpan_hasil():
    """Simpan hasil peringkat terkini ke tabel hasil_keputusan."""
    conn = get_connection()
    kriterias  = fetch_kriterias(conn)
    alternatifs = fetch_alternatifs(conn)
    nilai_map  = fetch_nilai_map(conn)

    errors = validate_input(alternatifs, kriterias, nilai_map)
    if errors:
        conn.close()
        flash("Tidak dapat menyimpan: data tidak lengkap.", "danger")
        return redirect(url_for("hasil"))

    saw_result = rank_alternatives(alternatifs, kriterias, nilai_map)
    tanggal    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for r in saw_result["results"]:
        conn.execute(
            """INSERT INTO hasil_keputusan (alternatif_id, nilai_preferensi, peringkat, tanggal)
               VALUES (?,?,?,?)""",
            (r["alternatif"]["id"], r["nilai_preferensi"], r["peringkat"], tanggal)
        )
    conn.commit()
    conn.close()
    flash("Riwayat hasil keputusan berhasil disimpan!", "success")
    return redirect(url_for("riwayat"))


# ======================================================================== #
#  LAPORAN & CETAK PDF
# ======================================================================== #

@app.route("/laporan")
def laporan():
    """Halaman Laporan Keputusan resmi dan siap cetak / simpan PDF."""
    conn = get_connection()
    kriterias   = fetch_kriterias(conn)
    alternatifs = fetch_alternatifs(conn)
    nilai_map   = fetch_nilai_map(conn)
    total       = total_bobot(conn)
    conn.close()

    errors = validate_input(alternatifs, kriterias, nilai_map)
    saw_result = None
    if not errors and alternatifs and kriterias:
        saw_result = rank_alternatives(alternatifs, kriterias, nilai_map)

    wib = timezone(timedelta(hours=7))
    now_wib = datetime.now(wib)
    bulan_id = (
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    )
    waktu_cetak = (
        f"{now_wib.day:02d} {bulan_id[now_wib.month]} {now_wib.year}, "
        f"{now_wib.strftime('%H:%M')} WIB"
    )

    return render_template(
        "laporan.html",
        kriterias=kriterias,
        alternatifs=alternatifs,
        saw=saw_result,
        errors=errors,
        total_bobot=total,
        waktu_cetak=waktu_cetak,
    )


# ======================================================================== #
#  RIWAYAT
# ======================================================================== #

@app.route("/riwayat")
def riwayat():
    conn = get_connection()
    rows = conn.execute("""
        SELECT h.*, a.nama_apartemen, a.lokasi
        FROM hasil_keputusan h
        JOIN alternatif a ON a.id = h.alternatif_id
        ORDER BY h.tanggal DESC, h.peringkat ASC
    """).fetchall()
    # Group by tanggal (sesi)
    sesi = {}
    for r in rows:
        tgl = r["tanggal"]
        if tgl not in sesi:
            sesi[tgl] = []
        sesi[tgl].append(r)
    conn.close()
    return render_template("riwayat.html", sesi=sesi)


@app.route("/riwayat/hapus-sesi", methods=["POST"])
def hapus_sesi():
    tanggal = request.form.get("tanggal", "")
    conn = get_connection()
    conn.execute("DELETE FROM hasil_keputusan WHERE tanggal=?", (tanggal,))
    conn.commit()
    conn.close()
    flash("Sesi riwayat berhasil dihapus.", "success")
    return redirect(url_for("riwayat"))


# ======================================================================== #
#  API - JSON untuk AJAX
# ======================================================================== #

@app.route("/api/whatif", methods=["POST"])
def api_whatif():
    """Endpoint AJAX untuk What-If Analysis real-time."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data"}), 400

    conn = get_connection()
    kriterias  = fetch_kriterias(conn)
    alternatifs = fetch_alternatifs(conn)
    nilai_map  = fetch_nilai_map(conn)
    conn.close()

    bobot_input = data.get("bobot", {})
    bobot_override = {}
    total_wb = 0.0
    for krt in kriterias:
        wb = bobot_input.get(str(krt["id"]), krt["bobot"])
        try:
            wb = float(wb)
        except (ValueError, TypeError):
            wb = float(krt["bobot"])
        bobot_override[krt["id"]] = wb
        total_wb += wb

    if abs(total_wb - 1.0) > 0.001:
        return jsonify({"error": f"Total bobot = {total_wb:.4f}, harus 1.00"}), 400

    saw_result = rank_alternatives(alternatifs, kriterias, nilai_map, bobot_override)
    output = []
    for r in saw_result["results"]:
        output.append({
            "peringkat": r["peringkat"],
            "nama": r["alternatif"]["nama_apartemen"],
            "nilai": round(r["nilai_preferensi"], 6),
        })
    return jsonify({"results": output, "total_bobot": round(total_wb, 6)})


# ======================================================================== #
#  RUN
# ======================================================================== #

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
