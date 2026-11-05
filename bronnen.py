# -*- coding: utf-8 -*-
# DraveRadio & TV - Copyright (C) 2026 Dravenlock (Roger & Claudio).
"""bronnen.py - waar de zenders vandaan komen.

Radio: Radio Browser (radio-browser.info), een gratis, open lijst die door gebruikers wordt bijgehouden.
TV:    de iptv-org-lijst (iptv-org.github.io). Daarin staan streams die openbaar op internet te vinden zijn;
       DraveRadio & TV biedt zelf niets aan en controleert of een stream van de website van de zender zelf komt.
"""
import json
import os
import random
import re
import ssl
import time
import urllib.parse
import urllib.request

AGENT = "DraveRadioTV/0.1 (Dravenlock; persoonlijk gebruik)"
IPTV = "https://iptv-org.github.io/api/%s.json"
RB_SERVERS = ["de1.api.radio-browser.info", "de2.api.radio-browser.info", "fi1.api.radio-browser.info",
              "nl1.api.radio-browser.info"]

LANDEN = [("NL", "Nederland"), ("BE", "België"), ("DE", "Duitsland"), ("GB", "Verenigd Koninkrijk"),
          ("US", "Verenigde Staten"), ("FR", "Frankrijk"), ("ES", "Spanje"), ("IT", "Italië"), ("TR", "Turkije"),
          ("MA", "Marokko"), ("SR", "Suriname"), ("CW", "Curaçao"), ("", "Alle landen")]
RADIO_GENRES = [("", "Alle genres"), ("pop", "Pop"), ("rock", "Rock"), ("news", "Nieuws"), ("talk", "Praten"),
                ("dance", "Dance"), ("jazz", "Jazz"), ("classical", "Klassiek"), ("80s", "Jaren 80"),
                ("90s", "Jaren 90"), ("oldies", "Oldies"), ("schlager", "Schlager"), ("country", "Country"),
                ("hip hop", "Hiphop"), ("ambient", "Rustig / ambient"), ("christmas", "Kerst")]
TV_GENRES = [("", "Alle soorten"), ("news", "Nieuws"), ("general", "Algemeen"), ("music", "Muziek"),
             ("entertainment", "Amusement"), ("movies", "Films"), ("series", "Series"), ("kids", "Kinderen"),
             ("documentary", "Documentaires"), ("sports", "Sport"), ("culture", "Cultuur"), ("religious", "Geloof"),
             ("weather", "Weer"), ("cooking", "Koken"), ("travel", "Reizen"), ("xxx", "18+")]


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


SSL = _ctx()


def haal(url, tijd=20, kop=None):
    k = {"User-Agent": AGENT}
    k.update(kop or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=k), timeout=tijd, context=SSL) as r:
        return r.read()


# ------------------------------------------------------------------ radio
def _rb(pad, params=None):
    servers = RB_SERVERS[:]
    random.shuffle(servers)
    fout = None
    for s in servers:
        try:
            q = "https://%s/json/%s" % (s, pad) + ("?" + urllib.parse.urlencode(params) if params else "")
            return json.loads(haal(q, tijd=12))
        except Exception as e:
            fout = e
    raise fout or RuntimeError("geen radio-server bereikbaar")


def zoek_radio(naam="", land="NL", genre="", aantal=250):
    p = {"hidebroken": "true", "order": "clickcount", "reverse": "true", "limit": str(aantal)}
    if naam:
        p["name"] = naam
    if land:
        p["countrycode"] = land
    if genre:
        p["tag"] = genre
    uit = []
    for s in _rb("stations/search", p):
        url = s.get("url_resolved") or s.get("url")
        if not url:
            continue
        tags = [t for t in (s.get("tags") or "").split(",") if t][:3]
        sub = " · ".join(x for x in (dict(LANDEN).get(s.get("countrycode") or "-", s.get("country") or ""), ", ".join(tags),
                                     ("%d kbps" % s["bitrate"]) if s.get("bitrate") else "") if x)
        uit.append(dict(soort="radio", id="r:" + s.get("stationuuid", url), naam=(s.get("name") or "?").strip(),
                        url=url, logo=s.get("favicon") or "", sub=sub, uuid=s.get("stationuuid", "")))
    return uit


def tel_klik(uuid):
    """Radio Browser vraagt om te laten weten welke zender je kiest (zo blijven de lijsten goed)."""
    if uuid:
        try:
            _rb("url/" + uuid)
        except Exception:
            pass


# ------------------------------------------------------------------ tv
def _domein(url):
    h = urllib.parse.urlparse(url or "").hostname or ""
    h = h.lower()
    if h.startswith("www."):
        h = h[4:]
    delen = h.split(".")
    if len(delen) >= 3 and delen[-2] in ("co", "com", "org", "net", "gov", "ac") and len(delen[-1]) == 2:
        return ".".join(delen[-3:])
    return ".".join(delen[-2:])


def laad_tv(cache_map, max_oud=24 * 3600):
    """iptv-org ophalen (eens per dag, daarna uit de cache) -> lijst zenders."""
    os.makedirs(cache_map, exist_ok=True)
    data = {}
    for naam in ("channels", "streams", "logos"):
        pad = os.path.join(cache_map, naam + ".json")
        if not os.path.exists(pad) or time.time() - os.path.getmtime(pad) > max_oud:
            try:
                ruw = haal(IPTV % naam, tijd=60)
                with open(pad, "wb") as f:
                    f.write(ruw)
            except Exception:
                if not os.path.exists(pad):
                    raise
        with open(pad, encoding="utf-8") as f:
            data[naam] = json.load(f)
    kanalen = {c["id"]: c for c in data["channels"]}
    logos = {}
    for lg in data["logos"]:
        if lg.get("channel") and lg.get("channel") not in logos and lg.get("in_use", True):
            logos[lg["channel"]] = lg.get("url", "")
    per_kanaal = {}
    for s in data["streams"]:
        if s.get("referrer") or s.get("user_agent"):
            continue                                   # heeft speciale instellingen nodig: werkt niet in een gewone speler
        cid = s.get("channel")
        k = kanalen.get(cid, {})
        if k.get("closed"):
            continue
        sleutel = cid or s.get("title") or s["url"]
        z = per_kanaal.get(sleutel)
        if z is None:
            site = k.get("website") or ""
            z = dict(soort="tv", id="t:" + sleutel, naam=k.get("name") or s.get("title") or "?", urls=[],
                     land=k.get("country") or "", genres=k.get("categories") or [], logo=logos.get(cid, ""),
                     nsfw=bool(k.get("is_nsfw")), site=site, officieel=False, labels=set())
            per_kanaal[sleutel] = z
        z["urls"].append(s["url"])
        z["labels"].update(s.get("labels") or [])
        if z["site"] and _domein(s["url"]) == _domein(z["site"]):
            z["officieel"] = True
            z["urls"].insert(0, z["urls"].pop())           # de eigen stream van de zender eerst proberen
    uit = []
    for z in per_kanaal.values():
        z["url"] = z["urls"][0]
        z["labels"] = sorted(z["labels"])
        z["sub"] = " · ".join(x for x in (z["land"], ", ".join(z["genres"][:2])) if x)
        uit.append(z)
    uit.sort(key=lambda z: (not z["officieel"], z["naam"].lower()))
    return uit


def filter_tv(alle, naam="", land="NL", genre="", verberg_18=False):
    naam = naam.lower().strip()
    uit = []
    for z in alle:
        if land and z["land"] != land:
            continue
        if genre and genre not in z["genres"]:
            continue
        if verberg_18 and (z["nsfw"] or "xxx" in z["genres"]):
            continue
        if naam and naam not in z["naam"].lower():
            continue
        uit.append(z)
    return uit[:400]


# ------------------------------------------------------------------ wat speelt er nu (radio, ICY)
def icy_titel(url, stop, melden):
    """Leest bij een radiostream de titel van het nummer mee (als de zender die stuurt)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Icy-MetaData": "1"})
        with urllib.request.urlopen(req, timeout=12, context=SSL) as r:
            interval = int(r.headers.get("icy-metaint") or 0)
            if not interval:
                return
            while not stop():
                r.read(interval)
                lengte = r.read(1)
                if not lengte:
                    return
                n = lengte[0] * 16
                if n:
                    meta = r.read(n).decode("utf-8", "replace")
                    m = re.search(r"StreamTitle='(.*?)';", meta)
                    if m and m.group(1).strip():
                        melden(m.group(1).strip())
    except Exception:
        return
