"""Quick test: render every page and check /api/whatif."""
import json
from app import app

client = app.test_client()

routes = ["/", "/kriteria", "/kriteria/tambah",
          "/alternatif", "/alternatif/tambah",
          "/hasil", "/riwayat"]

all_ok = True
for r in routes:
    resp = client.get(r)
    ok = resp.status_code == 200
    if not ok:
        all_ok = False
    label = "OK" if ok else "FAIL"
    print("  GET %-30s -> %d %s (%d bytes)" % (r, resp.status_code, label, len(resp.data)))

resp = client.post("/api/whatif",
                   data=json.dumps({"bobot": {}}),
                   content_type="application/json")
ok_api = resp.status_code == 200
data = json.loads(resp.data)
print("  POST /api/whatif                -> %d %s" % (resp.status_code, "OK" if ok_api else "FAIL"))
if ok_api and data.get("results"):
    top = data["results"][0]
    print("       Top: %s  V=%.4f" % (top["nama"], top["nilai"]))

if all_ok and ok_api:
    print("\nALL PAGES RENDER OK - No errors!")
else:
    print("\nSOME PAGES FAILED")
