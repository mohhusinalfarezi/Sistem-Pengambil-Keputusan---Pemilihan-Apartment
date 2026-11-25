from database import get_connection
from saw import rank_alternatives, validate_input

conn = get_connection()
kriterias = conn.execute("SELECT * FROM kriteria ORDER BY id").fetchall()
alts      = conn.execute("SELECT * FROM alternatif ORDER BY id").fetchall()
rows      = conn.execute("SELECT alternatif_id, kriteria_id, nilai FROM nilai_alternatif").fetchall()
nilai_map = {(r["alternatif_id"], r["kriteria_id"]): r["nilai"] for r in rows}
conn.close()

errors = validate_input(alts, kriterias, nilai_map)
print("Validasi errors:", errors)

result = rank_alternatives(alts, kriterias, nilai_map)
print("--- PERINGKAT SAW ---")
for r in result["results"]:
    nama = r["alternatif"]["nama_apartemen"]
    rank = r["peringkat"]
    v    = r["nilai_preferensi"]
    print(f"  #{rank} {nama:<25s}  V={v:.6f}")

print("Total bobot:", round(sum(result["bobot"]), 4))
print("TEST PASSED")
