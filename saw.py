"""
saw.py - Modul perhitungan SAW (Simple Additive Weighting)
SPK Pemilihan Apartemen di Semarang

Langkah SAW:
  1. Bangun matriks keputusan X[i][j]  (alternatif × kriteria)
  2. Normalisasi linier R[i][j]
       benefit : R[i][j] = X[i][j] / max(X[*][j])
       cost    : R[i][j] = min(X[*][j]) / X[i][j]
  3. Hitung nilai preferensi  V[i] = Σ w[j] * R[i][j]
  4. Rank berdasar V[i] descending
"""

from __future__ import annotations
from typing import Any


# --------------------------------------------------------------------------- #
#  Helper type alias
# --------------------------------------------------------------------------- #
Row = dict[str, Any]


def build_matrix(alternatifs: list[Row], kriterias: list[Row],
                 nilai_map: dict[tuple[int, int], float]) -> list[list[float]]:
    """
    Bangun matriks keputusan X (m × n).
    Returns list 2D: X[i][j] untuk alternatif ke-i, kriteria ke-j.
    """
    matrix: list[list[float]] = []
    for alt in alternatifs:
        row: list[float] = []
        for krt in kriterias:
            val = nilai_map.get((alt["id"], krt["id"]), 0.0)
            row.append(float(val))
        matrix.append(row)
    return matrix


def normalize(matrix: list[list[float]], kriterias: list[Row]) -> list[list[float]]:
    """
    Normalisasi matriks keputusan menjadi matriks R.
    - benefit : R[i][j] = X[i][j] / max_col
    - cost    : R[i][j] = min_col  / X[i][j]   (jika X[i][j] == 0 → R = 0)
    """
    if not matrix:
        return []

    n_alt = len(matrix)
    n_krt = len(kriterias)

    # Hitung nilai max/min per kolom
    col_max: list[float] = [max(matrix[i][j] for i in range(n_alt)) for j in range(n_krt)]
    col_min: list[float] = [min(matrix[i][j] for i in range(n_alt)) for j in range(n_krt)]

    r: list[list[float]] = []
    for i in range(n_alt):
        row_r: list[float] = []
        for j, krt in enumerate(kriterias):
            x_ij = matrix[i][j]
            if krt["tipe"] == "benefit":
                denom = col_max[j]
                row_r.append(round(x_ij / denom, 6) if denom != 0 else 0.0)
            else:  # cost
                numer = col_min[j]
                row_r.append(round(numer / x_ij, 6) if x_ij != 0 else 0.0)
        r.append(row_r)
    return r


def rank_alternatives(alternatifs: list[Row], kriterias: list[Row],
                       nilai_map: dict[tuple[int, int], float],
                       bobot_override: dict[int, float] | None = None
                       ) -> dict[str, Any]:
    """
    Jalankan seluruh pipeline SAW.

    Parameters
    ----------
    alternatifs     : list row alternatif (id, nama_apartemen, …)
    kriterias       : list row kriteria   (id, kode, nama, tipe, bobot)
    nilai_map       : dict {(alt_id, krt_id): nilai}
    bobot_override  : dict {krt_id: bobot_baru}  untuk What-If Analysis

    Returns
    -------
    dict berisi:
        matrix_x    : matriks keputusan awal
        matrix_r    : matriks normalisasi
        bobot       : bobot yang dipakai (bisa override)
        col_max     : nilai max per kolom
        col_min     : nilai min per kolom
        results     : list dict {alternatif, nilai_preferensi, peringkat}
    """
    if not alternatifs or not kriterias:
        return {
            "matrix_x": [], "matrix_r": [], "bobot": [],
            "col_max": [], "col_min": [], "results": []
        }

    # Siapkan bobot (bisa dioverride untuk simulasi)
    bobot: list[float] = []
    for krt in kriterias:
        if bobot_override and krt["id"] in bobot_override:
            bobot.append(float(bobot_override[krt["id"]]))
        else:
            bobot.append(float(krt["bobot"]))

    # Bangun matriks X
    matrix_x = build_matrix(alternatifs, kriterias, nilai_map)

    # Hitung col_max & col_min (untuk transparansi tampilan)
    n_alt = len(matrix_x)
    n_krt = len(kriterias)
    col_max = [max(matrix_x[i][j] for i in range(n_alt)) for j in range(n_krt)] if n_alt else []
    col_min = [min(matrix_x[i][j] for i in range(n_alt)) for j in range(n_krt)] if n_alt else []

    # Normalisasi
    matrix_r = normalize(matrix_x, kriterias)

    # Hitung nilai preferensi V[i]
    preferensi: list[float] = []
    for i in range(n_alt):
        v = sum(bobot[j] * matrix_r[i][j] for j in range(n_krt))
        preferensi.append(round(v, 6))

    # Peringkat (descending)
    indexed = sorted(enumerate(preferensi), key=lambda t: t[1], reverse=True)
    results: list[dict[str, Any]] = []
    for rank, (i, v) in enumerate(indexed, start=1):
        results.append({
            "alternatif": alternatifs[i],
            "nilai_preferensi": v,
            "peringkat": rank,
            "matrix_r_row": matrix_r[i],
            "matrix_x_row": matrix_x[i],
        })

    return {
        "matrix_x": matrix_x,
        "matrix_r": matrix_r,
        "bobot": bobot,
        "col_max": col_max,
        "col_min": col_min,
        "results": results,
    }


def validate_input(alternatifs: list[Row], kriterias: list[Row],
                   nilai_map: dict[tuple[int, int], float]) -> list[str]:
    """
    Validasi data sebelum perhitungan.
    Returns list pesan error (kosong = valid).
    """
    errors: list[str] = []
    for alt in alternatifs:
        for krt in kriterias:
            val = nilai_map.get((alt["id"], krt["id"]))
            if val is None:
                errors.append(
                    f"Nilai kosong: {alt['nama_apartemen']} – {krt['nama']}"
                )
            elif krt["tipe"] == "cost" and val <= 0:
                errors.append(
                    f"Nilai kriteria COST harus > 0: "
                    f"{alt['nama_apartemen']} – {krt['nama']} = {val}"
                )
    return errors


# Alias untuk fleksibilitas pemanggilan modul SAW
hitung_saw = rank_alternatives

