"""FCFF-basert DCF med scenarier, sensitivitet og omvendt DCF (Damodaran).

Bruk: python3 aksjeagent/modeller/dcf.py aksjeagent/modeller/BOUV.json
Skriver resultat til <ticker>_resultat.json ved siden av input-filen.

Modell per år t:
  omsetning_t = omsetning_{t-1} * (1 + vekst_t)
  EBIT_t      = omsetning_t * margin_t
  NOPAT_t     = EBIT_t * (1 - skatt)
  reinvest_t  = (omsetning_t - omsetning_{t-1}) / sales_to_capital
  FCFF_t      = NOPAT_t - reinvest_t
Terminalverdi = FCFF_{N+1} / (WACC - g), der reinvestering i evig tid = g / ROIC_terminal (Damodaran).
Egenkapitalverdi = EV + netto kontanter. Verdi per aksje = egenkapital / antall aksjer.
"""
import json
import sys
from pathlib import Path


def wacc(p):
    ke = p["rente"] + p["beta"] * p["markedspremie"]
    kd = p.get("gjeldsrente", 0) * (1 - p["skatt"])
    v = p.get("gjeldsandel", 0)
    return ke * (1 - v) + kd * v, ke


def baner(p, s):
    """Lager vekst- og marginbane over N år. Første år følger listene, deretter lineær overgang til terminal."""
    n = p["aar"]
    vekst = list(s["vekst"]) + [None] * (n - len(s["vekst"]))
    siste = s["vekst"][-1]
    rest = n - len(s["vekst"])
    for i in range(rest):
        vekst[len(s["vekst"]) + i] = siste + (s["terminal_vekst"] - siste) * (i + 1) / rest
    margin = [p["margin_naa"] + (s["margin_maal"] - p["margin_naa"]) * min(1, (t + 1) / s["margin_aar"]) for t in range(n)]
    return vekst, margin


def verdi(p, s, w=None, g=None):
    w_, _ = wacc(p)
    w = w if w is not None else w_
    g = g if g is not None else s["terminal_vekst"]
    vekst, margin = baner(p, s)
    oms, pv, rader = p["omsetning"], 0.0, []
    for t in range(p["aar"]):
        ny = oms * (1 + vekst[t])
        nopat = ny * margin[t] * (1 - p["skatt"])
        fcff = nopat - (ny - oms) / p["sales_to_capital"]
        pv += fcff / (1 + w) ** (t + 1)
        rader.append({"aar": t + 1, "omsetning": round(ny), "vekst": round(vekst[t] * 100, 1), "margin": round(margin[t] * 100, 1), "fcff": round(fcff)})
        oms = ny
    nopat_t = oms * (1 + g) * margin[-1] * (1 - p["skatt"])
    fcff_t = nopat_t * (1 - g / s.get("roic_terminal", p.get("roic_terminal", 0.15)))
    tv = fcff_t / (w - g)
    pv_tv = tv / (1 + w) ** p["aar"]
    ek = pv + pv_tv + p["netto_kontanter"]
    return {"per_aksje": ek / p["aksjer"], "ev": pv + pv_tv, "andel_terminal": pv_tv / (pv + pv_tv), "rader": rader}


def omvendt(p, s):
    """Finner hvilken årlig vekst de første årene dagens kurs priser inn (alt annet likt)."""
    lo, hi = -0.15, 0.40
    for _ in range(60):
        mid = (lo + hi) / 2
        s2 = dict(s, vekst=[mid] * len(s["vekst"]))
        if verdi(p, s2)["per_aksje"] < p["kurs"]:
            lo = mid
        else:
            hi = mid
    return mid


def main(sti):
    p = json.loads(Path(sti).read_text(encoding="utf-8"))
    w, ke = wacc(p)
    ut = {"ticker": p["ticker"], "kurs": p["kurs"], "wacc": round(w * 100, 2), "ke": round(ke * 100, 2), "scenarier": {}}
    for navn, s in p["scenarier"].items():
        r = verdi(p, s)
        ut["scenarier"][navn] = {
            "per_aksje": round(r["per_aksje"], 1),
            "oppside_pct": round((r["per_aksje"] / p["kurs"] - 1) * 100, 1),
            "sannsynlighet": s.get("sannsynlighet"),
            "andel_terminal_pct": round(r["andel_terminal"] * 100),
            "beskrivelse": s.get("beskrivelse", ""),
            "rader": r["rader"],
        }
    sann = [(v["per_aksje"], v["sannsynlighet"]) for v in ut["scenarier"].values() if v["sannsynlighet"]]
    if sann:
        vektet = sum(a * b for a, b in sann) / sum(b for _, b in sann)
        ut["vektet_verdi"] = round(vektet, 1)
        ut["vektet_oppside_pct"] = round((vektet / p["kurs"] - 1) * 100, 1)
        ut["kjop_under_mos"] = round(vektet * (1 - p["sikkerhetsmargin"]), 1)
        ut["sikkerhetsmargin_pct"] = round(p["sikkerhetsmargin"] * 100)
    basis = p["scenarier"]["Basis"]
    ut["sensitivitet"] = {
        "wacc": [round((w + d) * 100, 1) for d in (-0.01, -0.005, 0, 0.005, 0.01)],
        "g": [round((basis["terminal_vekst"] + d) * 100, 1) for d in (-0.01, 0, 0.01)],
        "verdi": [[round(verdi(p, basis, w + dw, basis["terminal_vekst"] + dg)["per_aksje"], 1) for dw in (-0.01, -0.005, 0, 0.005, 0.01)] for dg in (-0.01, 0, 0.01)],
    }
    ut["omvendt_dcf_vekst_pct"] = round(omvendt(p, basis) * 100, 1)
    utfil = Path(sti).with_name(p["ticker"] + "_resultat.json")
    utfil.write_text(json.dumps(ut, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in ut.items() if k != "scenarier"}, ensure_ascii=False))
    for k, v in ut["scenarier"].items():
        print(k, v["per_aksje"], str(v["oppside_pct"]) + " %", "terminal", str(v["andel_terminal_pct"]) + " %")


if __name__ == "__main__":
    main(sys.argv[1])
