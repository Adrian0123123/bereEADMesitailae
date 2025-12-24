#!/usr/bin/env python3
import json
import math
import re
from pathlib import Path
from urllib.parse import quote

# Categorías "fila" (pocas y usables)
CANON = [
  ("general", "En directo · Generalistas"),
  ("news", "En directo · Noticias"),
  ("sports", "En directo · Deportes"),
  ("events", "En directo · Eventos / Passes"),
  ("movies", "En directo · Cine / Series"),
  ("ent", "En directo · Entretenimiento"),
  ("docs", "En directo · Documentales"),
  ("kids", "En directo · Infantil"),
  ("other", "En directo · Otros"),
]

def canon_category(raw: str) -> str:
  s = (raw or "").strip().lower()
  if any(k in s for k in ["event", "pass", "ppv", "multipantalla"]): return "events"
  if any(k in s for k in ["deport", "sport"]): return "sports"
  if any(k in s for k in ["noticia", "news", "econom"]): return "news"
  if any(k in s for k in ["cine", "movie", "series", "hbo", "showtime", "cinemax", "max"]): return "movies"
  if any(k in s for k in ["entreten", "entertainment", "cable"]): return "ent"
  if any(k in s for k in ["document", "history", "discovery", "nat geo", "travel", "tlc"]): return "docs"
  if any(k in s for k in ["infantil", "kids", "disney", "nick"]): return "kids"
  if any(k in s for k in ["general", "abierta", "generalista"]): return "general"
  return "other"

def slugify(s: str) -> str:
  s = (s or "").strip().lower()
  s = re.sub(r"[^\w\s-]", "", s)
  s = re.sub(r"[\s_-]+", "-", s).strip("-")
  return s or "item"

def write_json(p: Path, obj):
  p.parent.mkdir(parents=True, exist_ok=True)
  p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def paginate(base_file: Path, base_dir: Path, metas):
  page = 100
  write_json(base_file, {"metas": metas[:page]})
  total = len(metas)
  for skip in range(page, total, page):
    write_json(base_dir / f"skip={skip}.json", {"metas": metas[skip:skip+page]})
  terminal_skip = int(math.ceil(max(total, 1) / page) * page)
  write_json(base_dir / f"skip={terminal_skip}.json", {"metas": []})

def main():
  channels = json.loads(Path("channels.json").read_text(encoding="utf-8"))
  if isinstance(channels, dict): channels = channels.get("channels", [])
  if not isinstance(channels, list): raise SystemExit("channels.json debe ser array o {channels:[...]}")

  out = Path("docs")
  prefix = "live_"

  # Normaliza
  norm = []
  countries = set()
  for ch in channels:
    name = (ch.get("name") or "").strip()
    url = (ch.get("url") or "").strip()
    if not name or not url: 
      continue
    country = (ch.get("country") or "xx").strip().lower()
    country = country[:2] if len(country) >= 2 else "xx"
    countries.add(country.upper())

    raw_cat = ch.get("category") or ch.get("group") or "other"
    cat = canon_category(str(raw_cat))

    cid = ch.get("id") or f"{country}_{slugify(name)}"
    cid = prefix + slugify(str(cid)).replace(prefix, "", 1)

    norm.append({
      "id": cid,
      "name": name,
      "country": country.upper(),
      "cat": cat,
      "logo": (ch.get("logo") or ch.get("poster") or "").strip(),
      "desc": (ch.get("description") or "").strip(),
      "url": url
    })

  used = sorted(set(x["cat"] for x in norm))
  catalogs = [c for c in CANON if c[0] in used]

  manifest = {
    "id": "com.tuusuario.live",
    "version": "1.0.0",
    "name": "Mis Canales en Directo",
    "description": "Canales en directo (estático en GitHub Pages)",
    "resources": [
      "catalog",
      {"name": "meta", "types": ["tv"], "idPrefixes": [prefix]},
      "stream"
    ],
    "types": ["tv"],
    "catalogs": []
  }

  for cat_id, cat_name in catalogs:
    manifest["catalogs"].append({
      "type": "tv",
      "id": f"live_{cat_id}",
      "name": cat_name,
      "extra": [{"name": "genre"}, {"name": "skip"}],
      "genres": sorted(countries)
    })

  write_json(out / "manifest.json", manifest)
  (out / ".nojekyll").write_text("", encoding="utf-8")

  # Genera catálogos
  for cat_id, _ in catalogs:
    catalog_id = f"live_{cat_id}"
    cat_channels = [x for x in norm if x["cat"] == cat_id]
    cat_channels.sort(key=lambda x: (x["country"], x["name"].lower()))

    metas = []
    for x in cat_channels:
      m = {"type": "tv", "id": x["id"], "name": x["name"], "genres": [x["country"]], "posterShape": "square"}
      if x["logo"]: m["poster"] = x["logo"]
      metas.append(m)

    base_file = out / "catalog" / "tv" / f"{catalog_id}.json"
    base_dir = out / "catalog" / "tv" / catalog_id
    paginate(base_file, base_dir, metas)

    # Filtrado por país (genre=XX)
    for ctry in sorted(countries):
      filtered = [m for m in metas if ctry in (m.get("genres") or [])]
      genre_file = base_dir / f"genre={quote(ctry)}.json"
      genre_dir  = base_dir / f"genre={quote(ctry)}"
      paginate(genre_file, genre_dir, filtered)

  # Meta + Stream por canal
  for x in norm:
    meta = {
      "meta": {
        "id": x["id"], "type": "tv", "name": x["name"],
        "genres": [x["country"]], "posterShape": "square",
        "description": x["desc"] or f'{x["country"]}'
      }
    }
    if x["logo"]:
      meta["meta"]["poster"] = x["logo"]
      meta["meta"]["logo"] = x["logo"]
    write_json(out / "meta" / "tv" / f'{x["id"]}.json', meta)

    write_json(out / "stream" / "tv" / f'{x["id"]}.json', {
      "streams": [{"title": "Directo (HLS)", "url": x["url"]}]
    })

if __name__ == "__main__":
  main()
