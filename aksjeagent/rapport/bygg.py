"""Bygger rapport/index.html fra mal.html og data.json. Kjør: python3 aksjeagent/rapport/bygg.py"""
import json
from pathlib import Path

mappe = Path(__file__).parent
data = json.loads((mappe / "data.json").read_text(encoding="utf-8"))
innhold = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
mal = (mappe / "mal.html").read_text(encoding="utf-8")
(mappe / "index.html").write_text(mal.replace("/*DATA*/", innhold), encoding="utf-8")
print("Skrev", mappe / "index.html")
