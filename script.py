import os as _os
from qgis.core import QgsApplication
try:
    iface  # QGIS konzolban fut
except NameError:  # önálló futtatás (python-qgis)
    QgsApplication.setPrefixPath('C:/Program Files/QGIS 3.44.15/apps/qgis-ltr', True)
    qgs = QgsApplication([], False); qgs.initQgis()
# -*- coding: utf-8 -*-
"""
Corine CLC50 QGIS projekt - PyQGIS szkript
Futtatás: QGIS -> Plugins -> Python Console -> "Show Editor" -> megnyitás -> Run
(QGIS 3.x). A 4 shp-nek az DATA-ban kell lennie.
Kimenet (ugyanabban a mappában): Corine CLC50.qgz, lomboserdo.shp, allomasok.shp, terkep.jpg
"""
import os
from qgis.core import *
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import Qt, QVariant

# ====================== BEÁLLÍTÁSOK - ITT IGAZÍTSD ======================
DATA = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"C:/Users/bzmot/Desktop/DATA"          # <- ide tedd a 4 shp-t (a kimenetek is ide kerülnek)
FOLYONEV_MEZO = "FOLYO_NEV"          # rivers.dbf mezője (ellenőrizve)
TONEV_MEZO = "TAROZO_N"              # lakes.dbf mezője (ellenőrizve)
CLC_KOD_MEZO = "KOD"                 # numerikus CLC-kód (kódolás-független szűrés)
LOMBOS_KOD = 3115                     # corine_cat = "Lombos erdő ültetvények" (ellenőrizve: 15 805 rekord)
# ========================================================================

def p(name):
    return os.path.join(DATA, name)

def find_field(layer, wanted, candidates):
    names = [f.name() for f in layer.fields()]
    if wanted and wanted in names:
        return wanted
    for c in candidates:
        for n in names:
            if c in n.lower():
                return n
    raise Exception("Nem találom a mezőt a(z) %s rétegben. Mezők: %s" % (layer.name(), names))

# ---------- 1-2. Projekt + EOV ----------
project = QgsProject.instance()
project.clear()
eov = QgsCoordinateReferenceSystem("EPSG:23700")
project.setCrs(eov)
project.setTitle("Corine CLC50")

# ---------- 3. Rétegek betöltése (hierarchia: pont > vonal > poligon) ----------
clc = QgsVectorLayer(p("CLC50_HU.shp"), "clc50", "ogr")
clc.setProviderEncoding("Windows-1250")   # a CLC50_HU.dbf-nek nincs .cpg-je, cp1250 kódolású
county = QgsVectorLayer(p("county.shp"), "county", "ogr")
rivers = QgsVectorLayer(p("rivers.shp"), "rivers", "ogr")
lakes = QgsVectorLayer(p("lakes.shp"), "lakes", "ogr")
for l in (clc, county, rivers, lakes):
    if not l.isValid():
        raise Exception("Nem tölthető be: " + l.source())

# alulról felfelé hozzáadva: clc, county, lakes, rivers
for l in (clc, county, lakes, rivers):
    project.addMapLayer(l)

# ---------- 4. Átnevezés ----------
county.setName("Megyehatár")
rivers.setName("Folyók")
lakes.setName("Tavak")
clc.setName("Felszínborítás")

# ---------- 6a. Tavak: kategorizálás név alapján, kék árnyalatok ----------
tonev = find_field(lakes, TONEV_MEZO, ["víztározó", "viztaroz", "tó", "nev", "name"])
vals = sorted(v for v in lakes.uniqueValues(lakes.fields().lookupField(tonev)) if v not in (None, ""))
ramp_kek = QgsGradientColorRamp(QColor("#c6dbef"), QColor("#08306b"))
cats = []
for i, v in enumerate(vals):
    sym = QgsSymbol.defaultSymbol(lakes.geometryType())
    sym.setColor(ramp_kek.color(i / max(1, len(vals) - 1)))
    cats.append(QgsRendererCategory(v, sym, str(v)))
lakes.setRenderer(QgsCategorizedSymbolRenderer(tonev, cats))

# ---------- 6b. Folyók: folyónév, YlGnBu, 1 mm, csak Duna/Tisza/Rába látszik ----------
folynev = find_field(rivers, FOLYONEV_MEZO, ["folyó", "folyo", "nev", "name"])
vals = sorted(v for v in rivers.uniqueValues(rivers.fields().lookupField(folynev)) if v not in (None, ""))
ylgnbu = QgsStyle.defaultStyle().colorRamp("YlGnBu")
cats = []
for i, v in enumerate(vals):
    sym = QgsSymbol.defaultSymbol(rivers.geometryType())
    lath = ["duna", "tisza", "rába"]
    nv = str(v).strip().lower()
    # a látható 3 folyó az YlGnBu sötétebb szakaszából kap színt (jól olvasható)
    frac = 0.4 + 0.3 * lath.index(nv) if nv in lath else i / max(1, len(vals) - 1)
    sym.setColor(ylgnbu.color(min(frac, 1.0)))
    sym.setWidth(1.0)
    sym.setWidthUnit(QgsUnitTypes.RenderMillimeters)
    cats.append(QgsRendererCategory(v, sym, str(v)))
r = QgsCategorizedSymbolRenderer(folynev, cats)
lathato = ("duna", "tisza", "rába")
for i, c in enumerate(r.categories()):
    r.updateCategoryRenderState(i, str(c.value()).strip().lower() in lathato)
rivers.setRenderer(r)

# ---------- 7. Megyehatár: átlátszó kitöltés, 1 pt fekete szaggatott körvonal ----------
sym = QgsFillSymbol.createSimple({
    "color": "0,0,0,0", "style": "no",
    "outline_color": "0,0,0,255", "outline_style": "dash",
    "outline_width": "1", "outline_width_unit": "Point"})
county.setRenderer(QgsSingleSymbolRenderer(sym))

# ---------- 8. Lombos erdő szűrés + mentés lomboserdo.shp ----------
kodmezo = find_field(clc, CLC_KOD_MEZO, ["corine_cat", "code", "clc", "kod"])
clc.setSubsetString("\"%s\" = %s" % (kodmezo, LOMBOS_KOD))
opt = QgsVectorFileWriter.SaveVectorOptions()
opt.driverName = "ESRI Shapefile"
opt.fileEncoding = "Windows-1250"
res = QgsVectorFileWriter.writeAsVectorFormatV3(
    clc, p("lomboserdo.shp"), project.transformContext(), opt)
if res[0] != QgsVectorFileWriter.NoError:
    raise Exception("lomboserdo.shp mentése sikertelen: %s" % (res,))
clc.setSubsetString("")
lombos = QgsVectorLayer(p("lomboserdo.shp"), "lomboserdo", "ogr")
project.addMapLayer(lombos, False)
project.layerTreeRoot().insertLayer(2, lombos)  # clc és county fölé kerüljön

# ---------- 9. Tematizálás terület szerint, 3 osztály, zöld skála, átlátszó körvonal ----------
base = QgsFillSymbol.createSimple({"outline_style": "no"})
gr = QgsGraduatedSymbolRenderer.createRenderer(
    lombos, "$area", 3, QgsGraduatedSymbolRenderer.Jenks,
    base, QgsStyle.defaultStyle().colorRamp("Greens"))
lf = gr.labelFormat()
lf.setPrecision(0)
lf.setTrimTrailingZeroes(True)
lf.setFormat("%1 – %2 m²")
gr.setLabelFormat(lf, True)
for i, nev in enumerate(("Kis erdők", "Közepes erdők", "Nagy erdők")):
    gr.updateRangeLabel(i, nev)
lombos.setRenderer(gr)

# ---------- 10. Új pont shp: allomasok.shp, all_nev mező ----------
fields = QgsFields()
fields.append(QgsField("all_nev", QVariant.String, "String", 50))
w_opt = QgsVectorFileWriter.SaveVectorOptions()
w_opt.driverName = "ESRI Shapefile"
w_opt.fileEncoding = "UTF-8"
writer = QgsVectorFileWriter.create(
    p("allomasok.shp"), fields, QgsWkbTypes.Point, eov,
    project.transformContext(), w_opt)
del writer
allomas = QgsVectorLayer(p("allomasok.shp"), "Állomások", "ogr")
project.addMapLayer(allomas, False)
project.layerTreeRoot().insertLayer(0, allomas)

# ---------- 11. 5 állomás digitalizálása (EOV koordináták) ----------
punktok = [("Budapest", 650000, 240000), ("Debrecen", 830000, 240000),
           ("Szeged", 740000, 100000), ("Pécs", 580000, 80000),
           ("Győr", 520000, 270000)]
allomas.startEditing()
for nev, x, y in punktok:
    f = QgsFeature(allomas.fields())
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
    f["all_nev"] = nev
    allomas.addFeature(f)
allomas.commitChanges()

# ---------- 12. Címkézés ----------
def cimke(layer, mezo, szin, meret, curved=False):
    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial"))
    fmt.setSize(meret)
    fmt.setColor(QColor(szin))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True); buf.setSize(1); buf.setColor(QColor("white"))
    fmt.setBuffer(buf)
    s = QgsPalLayerSettings()
    s.fieldName = mezo
    if curved:
        s.placement = QgsPalLayerSettings.Curved
        s.lineSettings().setPlacementFlags(QgsLabeling.OnLine)
    s.setFormat(fmt)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(s))
    layer.setLabelsEnabled(True)

cimke(allomas, "all_nev", "#00b000", 10)
cimke(rivers, folynev, "#0000ff", 8, True)
cimke(lakes, tonev, "#0000ff", 8)

root = project.layerTreeRoot()
for lyr in (allomas, county, lakes, lombos, rivers):
    root.removeLayer(lyr)
for i, lyr in enumerate((allomas, county, lakes, lombos, rivers)):
    root.insertLayer(i, lyr)

# ---------- 13. Felszínborítás törlése a rétegkezelőből ----------
project.removeMapLayer(clc.id())

# ---------- 5. Méretarány 1:1 400 000 + rögzítés (ha fut az iface) ----------
try:
    canvas = iface.mapCanvas()
    canvas.setDestinationCrs(eov)
    canvas.setExtent(county.extent())
    canvas.zoomScale(1400000)
    canvas.setScaleLocked(True)   # nagyításra nem változik a méretarány
    canvas.refresh()
except NameError:
    pass

project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(county.extent(), eov))
# ---------- 14. Projekt mentése ----------
qgz = p("Corine CLC50.qgz")
project.write(qgz)

# ---------- 15. Nyomtatási elrendezés ----------
manager = project.layoutManager()
for old in manager.layouts():
    manager.removeLayout(old)
layout = QgsPrintLayout(project)
layout.initializeDefaults()
layout.setName("Magyarország fontos lomhullató erdői")
manager.addLayout(layout)
page = layout.pageCollection().page(0)
page.setPageSize(QgsLayoutSize(297, 175, QgsUnitTypes.LayoutMillimeters))
mm = QgsUnitTypes.LayoutMillimeters

# Térkép - középen, teljes oldal
mp = QgsLayoutItemMap(layout)
mp.attemptResize(QgsLayoutSize(297, 175, mm))
mp.attemptMove(QgsLayoutPoint(0, 0, mm))
mp.setCrs(eov)
ext = county.extent()
ext.scale(1.02)
mp.setExtent(ext)
mp.setScale(2600000)
mp.setFrameEnabled(False)
layout.addLayoutItem(mp)
mp.zoomToExtent(ext) if False else None
cx, cy = county.extent().center().x(), county.extent().center().y()
e2 = QgsRectangle(cx - 297 * 2600 / 2, cy - 8000 - 175 * 2600 / 2, cx + 297 * 2600 / 2, cy - 8000 + 175 * 2600 / 2)
mp.setExtent(e2)

# Cím - alul, középre igazítva, TNR 20, 2 pt szürke keret
cim = QgsLayoutItemLabel(layout)
cim.setText("Magyarország fontos lomhullató erdői")
fmt = QgsTextFormat()
fmt.setFont(QFont("Times New Roman"))
fmt.setSize(20)
cim.setTextFormat(fmt)
cim.setHAlign(Qt.AlignHCenter)
cim.setVAlign(Qt.AlignVCenter)
cim.setFrameEnabled(True)
cim.setFrameStrokeColor(QColor("gray"))
cim.setFrameStrokeWidth(QgsLayoutMeasurement(2, QgsUnitTypes.LayoutPoints))
cim.attemptResize(QgsLayoutSize(130, 13, mm))
cim.attemptMove(QgsLayoutPoint((297 - 130) / 2, 158, mm))
layout.addLayoutItem(cim)

# Méretarány-vonalzó
sb = QgsLayoutItemScaleBar(layout)
sb.setStyle("Single Box")
sb.setLinkedMap(mp)
sb.applyDefaultSize()
sb.setUnits(QgsUnitTypes.DistanceKilometers)
sb.setUnitLabel("km")
sb.setNumberOfSegments(2)
sb.setNumberOfSegmentsLeft(0)
sb.setUnitsPerSegment(50)
sb.attemptMove(QgsLayoutPoint(10, 160, mm))
layout.addLayoutItem(sb)

# Jelmagyarázat - csak látható rétegek (térképhez szűrve), jobbra lent
lg = QgsLayoutItemLegend(layout)
lg.setLinkedMap(mp)
lg.setLegendFilterByMapEnabled(True)
lg.setAutoUpdateModel(True)
lg.setBackgroundEnabled(False)
for stl in (QgsLegendStyle.Title, QgsLegendStyle.Group, QgsLegendStyle.Subgroup, QgsLegendStyle.SymbolLabel):
    tf = QgsTextFormat(); tf.setFont(QFont("Arial")); tf.setSize(8)
    lg.rstyle(stl).setTextFormat(tf)
lg.setSymbolHeight(3); lg.setSymbolWidth(6)
lg.attemptMove(QgsLayoutPoint(232, 92, mm))
layout.addLayoutItem(lg)

# Északi irány (szélrózsa) + N betű, bal felül
na = QgsLayoutItemPicture(layout)
na.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
na.setLinkedMap(mp)
na.attemptResize(QgsLayoutSize(12, 16, mm))
na.attemptMove(QgsLayoutPoint(40, 12, mm))
layout.addLayoutItem(na)
nl = QgsLayoutItemLabel(layout)
nl.setText("N")
nf = QgsTextFormat(); nf.setFont(QFont("Arial")); nf.setSize(12)
nl.setTextFormat(nf)
nl.setHAlign(Qt.AlignHCenter)
nl.attemptResize(QgsLayoutSize(12, 6, mm))
nl.attemptMove(QgsLayoutPoint(40, 6, mm))
layout.addLayoutItem(nl)

# ---------- 16. Export JPEG, 200 dpi ----------
exporter = QgsLayoutExporter(layout)
img = QgsLayoutExporter.ImageExportSettings()
img.dpi = 200
st = exporter.exportToImage(p("terkep.jpg"), img)
print("JPEG export:", "OK" if st == QgsLayoutExporter.Success else "HIBA %s" % st)

# Elrendezéssel együtt újra mentjük a projektet
project.write(qgz)
print("Kész:", qgz)
