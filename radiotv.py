# -*- coding: utf-8 -*-
# DraveRadio & TV - Copyright (C) 2026 Dravenlock (Roger & Claudio).
"""radiotv.py - DraveRadio & TV: gratis radio en tv van internet, groot en duidelijk.

Radio: Radio Browser. TV: iptv-org (met waarschuwing: niet elke stream is officieel).
Extra: favorieten, laatst gekozen, slaaptimer, wat er nu speelt, en Leon die de zender noemt.
"""
import json
import os
import sys
import threading
import time

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMainWindow, QPushButton, QSlider, QStackedWidget,
                             QVBoxLayout, QWidget)

import bronnen
import leon

VERSIE = "0.3"
NAAM = "DraveRadio & TV"


def app_map():
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


def bron_map():
    return getattr(sys, "_MEIPASS", app_map())


DATA = os.path.join(app_map(), "DraveRadioTV-data")          # naast de app (dus op D:, niet op C:)
os.makedirs(DATA, exist_ok=True)

STIJL = """
* { font-family: 'Segoe UI'; color: #e2e2ec; }
QMainWindow, QWidget#basis, QDialog { background: #0a0810; }
QLabel#titel { font-size: 26pt; font-weight: 700; color: #e2e2ec; }
QLabel#zender { font-size: 22pt; font-weight: 700; }
QLabel#nu { font-size: 20pt; font-weight: 700; color: #ffde3c; background: #2a2208; border: 2px solid #ffde3c; border-radius: 10px; padding: 8px 12px; }
QLabel#klein { font-size: 12pt; color: #9a96aa; }
QWidget#waarschuwing { background: #2a1606; border: 2px solid #ff961e; border-radius: 10px; padding: 10px;
                      font-size: 13pt; color: #ffd9a8; }
QPushButton { background: #18122a; border: 2px solid #9a5ae6; border-radius: 12px; padding: 10px 16px;
              font-size: 15pt; font-weight: 600; }
QPushButton:hover { border-color: #ffde3c; }
QPushButton:checked { background: #9a5ae6; color: #0a0810; border-color: #ffde3c; }
QPushButton#groot { font-size: 20pt; padding: 14px 22px; background: #9a5ae6; color: #0a0810; border-color: #ffde3c; }
QPushButton#rood { background: #c83a3a; color: #ffffff; border-color: #e2e2ec; font-size: 20pt; padding: 14px 22px; }
QLineEdit, QComboBox { background: #fafaff; color: #0a0810; border: 3px solid #ffde3c; border-radius: 10px;
                       padding: 8px 10px; font-size: 16pt; }
QComboBox QAbstractItemView { background: #fafaff; color: #0a0810; font-size: 15pt; }
QListWidget { background: #0f0b1a; border: 2px solid #46307a; border-radius: 12px; font-size: 15pt; }
QListWidget::item { border-bottom: 1px solid #241a3a; }
QListWidget::item:selected { background: #2c1d50; }
QCheckBox { font-size: 14pt; }
QSlider::groove:horizontal { height: 10px; background: #2c2440; border-radius: 5px; }
QSlider::handle:horizontal { width: 26px; margin: -9px 0; background: #ffde3c; border-radius: 13px; }
QSlider::sub-page:horizontal { background: #9a5ae6; border-radius: 5px; }
"""

WAARSCHUWING = ("Let op bij tv: deze lijst komt van iptv-org en bevat streams die openbaar op internet te vinden zijn. "
                "DraveRadio & TV biedt zelf niets aan. Niet elke stream is officieel. "
                "✔ betekent: de stream komt van de website van de zender zelf. "
                "Kijken naar een stream waarvan je weet dat die illegaal is, mag in Nederland niet.")
SLAAP = [0, 15, 30, 60, 90]
LABELS = {"Geo-blocked": "alleen in eigen land", "Not 24/7": "niet altijd aan"}


class Signalen(QObject):
    radio = pyqtSignal(object)
    tv = pyqtSignal(object)
    fout = pyqtSignal(str)
    titel = pyqtSignal(str)
    leon = pyqtSignal(str)


class Rij(QWidget):
    """Een zender in de lijst: logo, naam, wat erbij hoort, en een ster."""

    def __init__(self, z, fav, ster_klik):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        self.logo = QLabel()
        self.logo.setFixedSize(64, 64)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setText("📻" if z["soort"] == "radio" else "📺")
        self.logo.setStyleSheet("font-size: 28pt; background: #1c1530; border-radius: 10px;")
        lay.addWidget(self.logo)
        tekst = QVBoxLayout()
        naam = QLabel(z["naam"])
        naam.setStyleSheet("font-size: 17pt; font-weight: 700;")
        naam.setWordWrap(True)
        naam.setMinimumWidth(10)
        tekst.addWidget(naam)
        sub = QHBoxLayout()
        if z["soort"] == "tv":
            if z.get("officieel"):
                b = QLabel("✔ van de zender zelf")
                b.setStyleSheet("color: #0a0810; background: #46c86e; border-radius: 6px; padding: 2px 8px; font-size: 12pt; font-weight: 700;")
            else:
                b = QLabel("? niet te controleren")
                b.setStyleSheet("color: #e2e2ec; background: #3c3650; border-radius: 6px; padding: 2px 8px; font-size: 12pt;")
            sub.addWidget(b)
            if z.get("nsfw") or "xxx" in z.get("genres", []):
                b18 = QLabel("18+")
                b18.setStyleSheet("color: #fff; background: #c83a3a; border-radius: 6px; padding: 2px 8px; font-size: 12pt; font-weight: 700;")
                sub.addWidget(b18)
            for lb in z.get("labels", []):
                x = QLabel(LABELS.get(lb, lb))
                x.setStyleSheet("color: #ffd9a8; font-size: 12pt;")
                sub.addWidget(x)
        info = QLabel(z.get("sub", ""))
        info.setObjectName("klein")
        info.setMinimumWidth(10)
        sub.addWidget(info)
        sub.addStretch(1)
        tekst.addLayout(sub)
        lay.addLayout(tekst, 1)
        self.ster = QPushButton("★" if fav else "☆")
        self.ster.setFixedSize(64, 56)
        self.ster.setStyleSheet("font-size: 22pt; color: #ffde3c;")
        self.ster.setToolTip("Favoriet")
        self.ster.clicked.connect(lambda: ster_klik(z, self))
        lay.addWidget(self.ster)


class Venster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(NAAM)
        ico = os.path.join(bron_map(), "assets", "icon.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))
        self.inst = {"favorieten": [], "laatst": [], "volume": 70, "leon": True, "verberg18": False,
                     "gezien": False, "land": "NL"}
        try:
            with open(os.path.join(DATA, "instellingen.json"), encoding="utf-8") as f:
                self.inst.update(json.load(f))
        except Exception:
            pass
        self.sig = Signalen()
        self.sig.radio.connect(self.toon_lijst)
        self.sig.tv.connect(self.tv_binnen)
        self.sig.fout.connect(lambda t: self.status.setText(t))
        self.sig.titel.connect(self.zet_titel)
        self.sig.leon.connect(self.speel_leon)
        self.net = QNetworkAccessManager(self)
        self.logo_cache, self.logo_wacht, self.logo_groot = {}, {}, {}
        self.duck, self.duck_doel, self.slaapf, self.leon_nr = 1.0, 1.0, 1.0, 0
        self.tv_alles = None
        self.tab = "radio"
        self.nu = None
        self.url_i = 0
        self.icy_stop = [False]
        self.slaap_i, self.slaap_rest = 0, 0

        basis = QWidget()
        basis.setObjectName("basis")
        self.setCentralWidget(basis)
        hoofd = QVBoxLayout(basis)
        hoofd.setContentsMargins(18, 14, 18, 14)
        # bovenbalk: titel en tabs
        boven = QHBoxLayout()
        logo = QLabel()
        png = os.path.join(bron_map(), "assets", "logo.png")
        if os.path.exists(png):
            logo.setPixmap(QPixmap(png).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))
        boven.addWidget(logo)
        t = QLabel(NAAM)
        t.setObjectName("titel")
        boven.addWidget(t)
        boven.addStretch(1)
        self.tabs = {}
        for sl, label in (("radio", "📻  Radio"), ("tv", "📺  TV"), ("fav", "★  Favorieten"), ("laatst", "🕘  Laatst")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda _, s=sl: self.kies_tab(s))
            boven.addWidget(b)
            self.tabs[sl] = b
        hoofd.addLayout(boven)
        # filters
        self.filters = QWidget()
        fl = QHBoxLayout(self.filters)
        fl.setContentsMargins(0, 4, 0, 4)
        self.zoekvak = QLineEdit()
        self.zoekvak.setPlaceholderText("Zoek een zender...")
        self.zoekvak.returnPressed.connect(self.zoek)
        fl.addWidget(self.zoekvak, 3)
        self.land = QComboBox()
        for code, naam in bronnen.LANDEN:
            self.land.addItem(naam, code)
        i = [c for c, _ in bronnen.LANDEN].index(self.inst.get("land", "NL")) if self.inst.get("land", "NL") in \
            [c for c, _ in bronnen.LANDEN] else 0
        self.land.setCurrentIndex(i)
        self.land.currentIndexChanged.connect(self.zoek)
        fl.addWidget(self.land, 2)
        self.genre = QComboBox()
        self.genre.currentIndexChanged.connect(lambda _: self.zoek() if not self._vullen else None)
        fl.addWidget(self.genre, 2)
        self.v18 = QCheckBox("18+ verbergen")
        self.v18.setChecked(self.inst.get("verberg18", False))
        self.v18.toggled.connect(self.zet_18)
        fl.addWidget(self.v18)
        self.letop = QPushButton("⚠ Let op")
        self.letop.setToolTip("De melding over tv weer laten zien")
        self.letop.clicked.connect(lambda: self.zet_balk(True))
        fl.addWidget(self.letop)
        zb = QPushButton("Zoeken")
        zb.clicked.connect(self.zoek)
        fl.addWidget(zb)
        hoofd.addWidget(self.filters)
        self.waarschuw = QWidget()
        self.waarschuw.setObjectName("waarschuwing")
        self.waarschuw.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wl = QHBoxLayout(self.waarschuw)
        wl.setContentsMargins(12, 8, 12, 8)
        wt = QLabel(WAARSCHUWING)
        wt.setWordWrap(True)
        wt.setStyleSheet("font-size: 13pt; color: #ffd9a8; background: transparent;")
        wl.addWidget(wt, 1)
        wb = QPushButton("Begrepen")
        wb.setToolTip("Deze melding verbergen")
        wb.clicked.connect(lambda: self.zet_balk(False))
        wl.addWidget(wb)
        hoofd.addWidget(self.waarschuw)
        # midden: lijst links, speler rechts
        midden = QHBoxLayout()
        self.lijst = QListWidget()
        self.lijst.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lijst.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.lijst.itemDoubleClicked.connect(lambda it: self.speel(it.data(Qt.ItemDataRole.UserRole)))
        self.lijst.itemActivated.connect(lambda it: self.speel(it.data(Qt.ItemDataRole.UserRole)))
        midden.addWidget(self.lijst, 5)
        rechts = QVBoxLayout()
        self.beeld = QStackedWidget()
        self.beeld.setMinimumSize(560, 320)
        self.radiobeeld = QLabel("📻")
        self.radiobeeld.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.radiobeeld.setStyleSheet("font-size: 96pt; background: #120d20; border-radius: 16px;")
        self.beeld.addWidget(self.radiobeeld)
        self.video = QVideoWidget()
        self.video.setStyleSheet("background: black;")
        self.video.mouseDoubleClickEvent = lambda e: self.volledig()
        self.beeld.addWidget(self.video)
        rechts.addWidget(self.beeld, 3)
        self.zendernaam = QLabel("Kies een zender")
        self.zendernaam.setObjectName("zender")
        self.zendernaam.setWordWrap(True)
        rechts.addWidget(self.zendernaam)
        self.nuspeelt = QLabel("")
        self.nuspeelt.setObjectName("nu")
        self.nuspeelt.setWordWrap(True)
        self.nuspeelt.hide()
        rechts.addWidget(self.nuspeelt)
        knoppen = QHBoxLayout()
        self.speelknop = QPushButton("▶  Afspelen")
        self.speelknop.setObjectName("groot")
        self.speelknop.clicked.connect(self.speel_stop)
        knoppen.addWidget(self.speelknop, 2)
        self.favknop = QPushButton("☆ Favoriet")
        self.favknop.clicked.connect(self.wissel_fav_nu)
        knoppen.addWidget(self.favknop, 1)
        rechts.addLayout(knoppen)
        vol = QHBoxLayout()
        vl = QLabel("🔊")
        vl.setStyleSheet("font-size: 20pt;")
        vol.addWidget(vl)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(self.inst.get("volume", 70)))
        self.volume.valueChanged.connect(self.zet_volume)
        vol.addWidget(self.volume, 1)
        rechts.addLayout(vol)
        extra = QHBoxLayout()
        self.slaapknop = QPushButton("🌙 Slaaptimer: uit")
        self.slaapknop.clicked.connect(self.wissel_slaap)
        extra.addWidget(self.slaapknop, 2)
        self.volknop = QPushButton("⛶ Volledig scherm")
        self.volknop.clicked.connect(self.volledig)
        extra.addWidget(self.volknop, 2)
        rechts.addLayout(extra)
        self.leonvak = QCheckBox("Leon zegt de naam van de zender")
        self.leonvak.setChecked(self.inst.get("leon", True))
        self.leonvak.toggled.connect(lambda v: (self.inst.__setitem__("leon", v), self.bewaar()))
        rechts.addWidget(self.leonvak)
        rechts.addStretch(1)
        midden.addLayout(rechts, 4)
        hoofd.addLayout(midden, 1)
        self.status = QLabel("")
        self.status.setObjectName("klein")
        hoofd.addWidget(self.status)
        voet = QLabel("Radio: Radio Browser  ·  TV: iptv-org  ·  Stem: Leon  ·  %s %s  -  Dravenlock (Roger & Claudio)"
                      % (NAAM, VERSIE))
        voet.setObjectName("klein")
        hoofd.addWidget(voet)

        # spelers
        self.uit = QAudioOutput()
        self.speler = QMediaPlayer()
        self.speler.setAudioOutput(self.uit)
        self.speler.setVideoOutput(self.video)
        self.speler.errorOccurred.connect(self.speelfout)
        self.speler.mediaStatusChanged.connect(self.mediastatus)
        self.leon_uit = QAudioOutput()
        self.leon_speler = QMediaPlayer()
        self.leon_speler.setAudioOutput(self.leon_uit)
        self.leon_speler.mediaStatusChanged.connect(self.leon_klaar)
        self.zet_volume(self.volume.value())
        self.klok = QTimer(self)
        self.klok.timeout.connect(self.tik)
        self.klok.start(1000)
        self.faderklok = QTimer(self)
        self.faderklok.timeout.connect(self.fade)
        self.faderklok.start(40)
        self._vullen = False
        self.resize(1500, 900)
        self.kies_tab("radio")

    # ------------------------------------------------------------ hulp
    def bewaar(self):
        try:
            with open(os.path.join(DATA, "instellingen.json"), "w", encoding="utf-8") as f:
                json.dump(self.inst, f, ensure_ascii=False)
        except Exception:
            pass

    def is_fav(self, z):
        return any(f["id"] == z["id"] for f in self.inst["favorieten"])

    @staticmethod
    def klein(z):
        k = {x: z.get(x) for x in ("soort", "id", "naam", "url", "urls", "logo", "sub", "uuid", "officieel", "nsfw",
                                    "genres", "labels") if z.get(x) is not None}
        return k

    # ------------------------------------------------------------ tabs en zoeken
    def kies_tab(self, s):
        self.tab = s
        for k, b in self.tabs.items():
            b.setChecked(k == s)
        self.filters.setVisible(s in ("radio", "tv"))
        self.zet_balk(self.inst.get("balk", True), bewaren=False)
        self.v18.setVisible(s == "tv")
        self._vullen = True
        self.genre.clear()
        for code, naam in (bronnen.TV_GENRES if s == "tv" else bronnen.RADIO_GENRES):
            self.genre.addItem(naam, code)
        self._vullen = False
        if s == "tv" and not self.inst.get("gezien"):
            self.waarschuw_dialoog()
        if s == "fav":
            self.toon_lijst(list(self.inst["favorieten"]))
        elif s == "laatst":
            self.toon_lijst(list(self.inst["laatst"]))
        else:
            self.zoek()

    def zet_balk(self, aan, bewaren=True):
        self.waarschuw.setVisible(self.tab == "tv" and aan)
        self.letop.setVisible(self.tab == "tv" and not aan)
        if bewaren:
            self.inst["balk"] = aan
            self.bewaar()

    def waarschuw_dialoog(self):
        d = QDialog(self)
        d.setWindowTitle("Let op bij tv")
        lay = QVBoxLayout(d)
        t = QLabel(WAARSCHUWING + "\n\nDe keuze wat je kijkt is aan jou.")
        t.setWordWrap(True)
        t.setStyleSheet("font-size: 15pt;")
        t.setMinimumWidth(620)
        lay.addWidget(t)
        b = QPushButton("Ik begrijp het")
        b.setObjectName("groot")
        b.clicked.connect(d.accept)
        lay.addWidget(b)
        d.exec()
        self.inst["gezien"] = True
        self.bewaar()

    def zoek(self, *_):
        if self.tab not in ("radio", "tv"):
            return
        naam = self.zoekvak.text().strip()
        land = self.land.currentData() or ""
        genre = self.genre.currentData() or ""
        self.inst["land"] = land
        self.bewaar()
        if self.tab == "radio":
            self.status.setText("Radiozenders zoeken...")
            threading.Thread(target=self._zoek_radio, args=(naam, land, genre), daemon=True).start()
        elif self.tv_alles is None:
            self.status.setText("De tv-lijst wordt opgehaald (de eerste keer duurt dit even)...")
            threading.Thread(target=self._laad_tv, daemon=True).start()
        else:
            self.toon_lijst(bronnen.filter_tv(self.tv_alles, naam, land, genre, self.v18.isChecked()))

    def _zoek_radio(self, naam, land, genre):
        try:
            self.sig.radio.emit(bronnen.zoek_radio(naam, land, genre))
        except Exception as e:
            self.sig.fout.emit("Radio zoeken lukte niet (%s). Is er internet?" % e)

    def _laad_tv(self):
        try:
            self.sig.tv.emit(bronnen.laad_tv(os.path.join(DATA, "cache")))
        except Exception as e:
            self.sig.fout.emit("De tv-lijst ophalen lukte niet (%s)." % e)

    def tv_binnen(self, alles):
        self.tv_alles = alles
        if self.tab == "tv":
            self.zoek()

    def zet_18(self, v):
        self.inst["verberg18"] = v
        self.bewaar()
        self.zoek()

    def toon_lijst(self, zenders):
        if self.tab in ("radio", "tv") and zenders and zenders[0]["soort"] != self.tab:
            return
        self.lijst.clear()
        for z in zenders:
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, z)
            rij = Rij(z, self.is_fav(z), self.ster)
            it.setSizeHint(rij.sizeHint())
            self.lijst.addItem(it)
            self.lijst.setItemWidget(it, rij)
            if z.get("logo"):
                self.laad_logo(z["logo"], rij.logo)
        n = len(zenders)
        self.status.setText(("%d zenders. Dubbelklik op een zender om te luisteren of te kijken." % n) if n else
                            ("Nog geen favorieten: klik op de ster ☆ bij een zender." if self.tab == "fav" else
                             "Geen zenders gevonden."))

    def laad_logo(self, url, label):
        if url in self.logo_cache:
            if self.logo_cache[url]:
                label.setPixmap(self.logo_cache[url])
            return
        self.logo_wacht.setdefault(url, []).append(label)
        if len(self.logo_wacht[url]) > 1:
            return
        req = QNetworkRequest(QUrl(url))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, bronnen.AGENT)
        antw = self.net.get(req)
        antw.finished.connect(lambda a=antw, u=url: self.logo_binnen(a, u))

    def logo_binnen(self, antw, url):
        pm = QPixmap()
        ok = pm.loadFromData(bytes(antw.readAll()))
        antw.deleteLater()
        if ok:
            self.logo_groot[url] = pm
        pm = pm.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation) if ok else None
        self.logo_cache[url] = pm
        for lb in self.logo_wacht.pop(url, []):
            try:
                if pm:
                    lb.setPixmap(pm)
                    lb.setStyleSheet("background: #1c1530; border-radius: 10px;")
            except RuntimeError:
                pass

    # ------------------------------------------------------------ favorieten
    def ster(self, z, rij):
        if self.is_fav(z):
            self.inst["favorieten"] = [f for f in self.inst["favorieten"] if f["id"] != z["id"]]
            rij.ster.setText("☆")
        else:
            self.inst["favorieten"].insert(0, self.klein(z))
            rij.ster.setText("★")
        self.bewaar()
        self.zet_favknop()
        if self.tab == "fav":
            self.toon_lijst(list(self.inst["favorieten"]))

    def wissel_fav_nu(self):
        if not self.nu:
            return
        if self.is_fav(self.nu):
            self.inst["favorieten"] = [f for f in self.inst["favorieten"] if f["id"] != self.nu["id"]]
        else:
            self.inst["favorieten"].insert(0, self.klein(self.nu))
        self.bewaar()
        self.zet_favknop()
        if self.tab == "fav":
            self.toon_lijst(list(self.inst["favorieten"]))

    def zet_favknop(self):
        self.favknop.setText("★ Favoriet" if self.nu and self.is_fav(self.nu) else "☆ Favoriet")

    # ------------------------------------------------------------ afspelen
    def speel(self, z):
        if not z:
            return
        self.nu = z
        self.url_i = 0
        self.icy_stop[0] = True
        self.zendernaam.setText(z["naam"])
        self.nuspeelt.setText(""); self.nuspeelt.hide()
        self.beeld.setCurrentWidget(self.video if z["soort"] == "tv" else self.radiobeeld)
        if z["soort"] == "radio":
            pm = self.logo_groot.get(z.get("logo")) or self.logo_cache.get(z.get("logo"))
            if pm:
                maat = min(260, max(pm.width(), pm.height(), 120))      # niet wazig opblazen
                self.radiobeeld.setPixmap(pm.scaled(maat, maat, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))
            else:
                self.radiobeeld.setText("📻")
            threading.Thread(target=bronnen.tel_klik, args=(z.get("uuid"),), daemon=True).start()
            stop = [False]
            self.icy_stop = stop
            threading.Thread(target=bronnen.icy_titel, args=(z["url"], lambda: stop[0], self.sig.titel.emit),
                             daemon=True).start()
        self.leon_nr += 1
        if self.inst.get("leon", True):
            self.duck = self.duck_doel = 0.12                    # zacht beginnen, Leon praat eroverheen
            nr = self.leon_nr
            QTimer.singleShot(12000, lambda: self.duck_omhoog(nr))   # vangnet als Leon niets zegt
        else:
            self.duck = self.duck_doel = 1.0
        self.pas_volume()
        self.start_url()
        self.inst["laatst"] = [self.klein(z)] + [x for x in self.inst["laatst"] if x["id"] != z["id"]][:19]
        self.bewaar()
        self.zet_favknop()
        if self.inst.get("leon", True):
            tekst = ("Je luistert naar %s." if z["soort"] == "radio" else "Je kijkt naar %s.") % z["naam"]
            threading.Thread(target=lambda n=self.leon_nr: self.sig.leon.emit(
                "%d|%s" % (n, leon.maak(tekst, os.path.join(DATA, "leon")) or "")),
                             daemon=True).start()

    def start_url(self):
        urls = self.nu.get("urls") or [self.nu["url"]]
        self.speler.setSource(QUrl(urls[self.url_i]))
        self.speler.play()
        self.speelknop.setText("■  Stop")
        self.speelknop.setObjectName("rood")
        self.speelknop.setStyle(self.speelknop.style())
        self.status.setText("Verbinden met %s..." % self.nu["naam"])

    def speelfout(self, *_):
        if not self.nu:
            return
        urls = self.nu.get("urls") or [self.nu["url"]]
        if self.url_i + 1 < len(urls):
            self.url_i += 1
            self.status.setText("Andere stream proberen...")
            self.start_url()
        else:
            self.status.setText("%s werkt nu niet. Probeer een andere zender." % self.nu["naam"])
            self.stop_spelen()

    def mediastatus(self, st):
        S = QMediaPlayer.MediaStatus
        if st in (S.LoadingMedia, S.StalledMedia):
            self.status.setText("Laden...")
        elif st in (S.BufferedMedia, S.LoadedMedia):
            self.status.setText("Speelt: %s" % (self.nu or {}).get("naam", ""))

    def speel_stop(self):
        if self.speler.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.stop_spelen()
        elif self.nu:
            self.speel(self.nu)
        elif self.lijst.currentItem():
            self.speel(self.lijst.currentItem().data(Qt.ItemDataRole.UserRole))

    def stop_spelen(self):
        self.speler.stop()
        self.icy_stop[0] = True
        self.speelknop.setText("▶  Afspelen")
        self.speelknop.setObjectName("groot")
        self.speelknop.setStyle(self.speelknop.style())
        self.nuspeelt.setText(""); self.nuspeelt.hide()

    def zet_titel(self, t):
        kaal = t.strip().lower().replace("_", "-")
        if kaal.startswith(("commercial", "advert", "adbreak", "ad-break", "reclame")) or kaal in ("ad", "ads", "spot"):
            t = "Reclame"
        self.nuspeelt.setText("♪  Nu: " + t)
        self.nuspeelt.show()

    def zet_volume(self, v):
        self.inst["volume"] = v
        self.pas_volume()
        self.leon_uit.setVolume(min(1.0, 0.4 + v / 100.0))

    def pas_volume(self):
        self.uit.setVolume(self.volume.value() / 100.0 * self.duck * self.slaapf)

    def duck_omhoog(self, nr=None):
        if nr is None or nr == self.leon_nr:
            self.duck_doel = 1.0

    def volledig(self):
        if self.nu and self.nu["soort"] == "tv":
            self.video.setFullScreen(not self.video.isFullScreen())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape and self.video.isFullScreen():
            self.video.setFullScreen(False)
        else:
            super().keyPressEvent(e)

    # ------------------------------------------------------------ Leon
    def speel_leon(self, bericht):
        nr, _, pad = bericht.partition("|")
        if int(nr) != self.leon_nr:
            return                                   # intussen al een andere zender gekozen
        if not pad:
            self.duck_omhoog()
            return
        self.duck_doel = 0.12
        self.leon_speler.setSource(QUrl.fromLocalFile(pad))
        self.leon_speler.play()

    def leon_klaar(self, st):
        if st in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
            nr = self.leon_nr
            QTimer.singleShot(400, lambda: self.duck_omhoog(nr))

    # ------------------------------------------------------------ slaaptimer
    def wissel_slaap(self):
        self.slaap_i = (self.slaap_i + 1) % len(SLAAP)
        self.slaap_rest = SLAAP[self.slaap_i] * 60
        self.slaapf = 1.0
        self.pas_volume()
        self.zet_slaapknop()

    def zet_slaapknop(self):
        if not self.slaap_rest:
            self.slaapknop.setText("🌙 Slaaptimer: uit")
        else:
            self.slaapknop.setText("🌙 Uit over %d:%02d" % (self.slaap_rest // 60, self.slaap_rest % 60))

    def fade(self):
        if abs(self.duck - self.duck_doel) > 0.001:
            stap = 0.04 if self.duck_doel > self.duck else 0.2       # rustig omhoog (ruim een seconde), snel omlaag
            self.duck = min(self.duck_doel, self.duck + stap) if self.duck_doel > self.duck else \
                max(self.duck_doel, self.duck - stap)
            self.pas_volume()

    def tik(self):
        if not self.slaap_rest:
            return
        self.slaap_rest -= 1
        if self.slaap_rest <= 30:                              # de laatste 30 seconden zachtjes uitfaden
            self.slaapf = max(0.0, self.slaap_rest / 30.0)
            self.pas_volume()
        if self.slaap_rest <= 0:
            self.stop_spelen()
            self.slaapf = 1.0
            self.pas_volume()
            self.slaap_i = 0
            self.status.setText("Slaaptimer: welterusten.")
        self.zet_slaapknop()

    def closeEvent(self, e):
        self.icy_stop[0] = True
        self.bewaar()
        super().closeEvent(e)


def stijl():
    vink = os.path.join(bron_map(), "assets", "vink.svg").replace("\\", "/")
    return STIJL + """
QCheckBox { spacing: 12px; }
QCheckBox::indicator { width: 30px; height: 30px; border: 3px solid #ffde3c; border-radius: 7px; background: #18122a; }
QCheckBox::indicator:checked { background: #ffde3c; image: url(%s); }
""" % vink


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(NAAM)
    f = QFont("Segoe UI", 12)
    app.setFont(f)
    app.setStyleSheet(stijl())
    v = Venster()
    v.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
