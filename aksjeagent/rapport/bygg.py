"""Bygger rapport/index.html fra mal.html, data.json og DCF-resultater i modeller/.

Kjør: python3 aksjeagent/rapport/bygg.py
Hvis modeller/<id>_resultat.json finnes, legges DCF-resultatet inn på aksjen automatisk.
"""
import json
from pathlib import Path

mappe = Path(__file__).parent
data = json.loads((mappe / "data.json").read_text(encoding="utf-8"))
for a in data["aksjer"]:
    res = mappe.parent / "modeller" / f"{a.get('modell', a['id'])}_resultat.json"
    if res.exists():
        r = json.loads(res.read_text(encoding="utf-8"))
        a["dcf"] = {
            "wacc": r["wacc"], "vektet": r.get("vektet_verdi"), "oppside": r.get("vektet_oppside_pct"),
            "mos_kjop": r.get("kjop_under_mos"), "mos": r.get("sikkerhetsmargin_pct"),
            "omvendt": r["omvendt_dcf_vekst_pct"], "sens": r["sensitivitet"], "kurs": r["kurs"],
            "scenarier": [[k, v["per_aksje"], v["oppside_pct"], v["sannsynlighet"], v["beskrivelse"]] for k, v in r["scenarier"].items()],
        }
innhold = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
mal = (mappe / "mal.html").read_text(encoding="utf-8")
(mappe / "index.html").write_text(mal.replace("/*DATA*/", innhold), encoding="utf-8")
print("Skrev", mappe / "index.html")
