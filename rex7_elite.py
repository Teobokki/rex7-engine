"""REX 7 ELITE - image board (place, move, scale, rotate, layer, draw) with OPTIONAL frame animation.
(c)2026 EX Inc./HYPERION DIGITAL (c)2026"""
import io, json, math, os, subprocess, time, zipfile
import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, QBuffer, QByteArray, QIODevice, QSize
from PySide6.QtGui import (QImage, QPainter, QPen, QColor, QTransform, QPolygonF, QPixmap, QIcon, QKeySequence,
                           QShortcut, QBrush, QFont, QGuiApplication)
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSlider, QComboBox, QSpinBox,
                               QCheckBox, QListWidget, QListWidgetItem, QFileDialog, QColorDialog, QMenu, QMessageBox,
                               QButtonGroup, QSizePolicy, QListView, QAbstractItemView)
from rex7_style import (BG, PANEL, CARD, CARD2, BORDER, TXT, MUT, DIM, ACC, SILVER, BOARD_RGB, downloads_dir)

PRESETS = [(1920, 1080), (1280, 720), (1080, 1080), (1080, 1920), (800, 600), (512, 512)]
BGS = [("Dark board", QColor(*BOARD_RGB)), ("White", QColor(255, 255, 255)), ("Transparent", None)]
SWATCHES = ["#000000", "#ffffff", "#7f7f7f", "#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa", "#6d4c41"]
IMG_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
FMT = QImage.Format_ARGB32_Premultiplied
UNDO_MAX = 60


def trash_icon():
    pm = QPixmap(32, 32); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#e3e5e9"), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(7, 9), QPointF(25, 9)); p.drawLine(QPointF(13, 9), QPointF(13, 6)); p.drawLine(QPointF(13, 6), QPointF(19, 6))
    p.drawLine(QPointF(19, 6), QPointF(19, 9))
    p.drawPolygon(QPolygonF([QPointF(9, 11), QPointF(23, 11), QPointF(21.5, 27), QPointF(10.5, 27)]))
    p.drawLine(QPointF(14, 14), QPointF(14, 24)); p.drawLine(QPointF(18, 14), QPointF(18, 24)); p.end()
    return QIcon(pm)


class Layer:
    def __init__(self, kind, img, name, x=0.0, y=0.0, scale=1.0, rot=0.0, visible=True, opacity=1.0):
        self.kind, self.img, self.name = kind, img, name
        self.x, self.y, self.scale, self.rot = x, y, scale, rot
        self.visible, self.opacity = visible, opacity

    def clone(self, blank=False):
        img = self.img
        if blank and self.kind == "draw":
            img = QImage(img.size(), FMT); img.fill(0)
        return Layer(self.kind, QImage(img), self.name, self.x, self.y, self.scale, self.rot, self.visible, self.opacity)

    def xform(self):
        t = QTransform(); t.translate(self.x, self.y); t.rotate(self.rot); t.scale(self.scale, self.scale)
        t.translate(-self.img.width() / 2, -self.img.height() / 2)
        return t


def blank_draw(w, h, name="Drawing"):
    im = QImage(w, h, FMT); im.fill(0)
    return Layer("draw", im, name)


def qimg_to_np(img):
    img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    a = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine())[:, :w * 4]
    return a.reshape(h, w, 4).copy()


def np_to_qimg(a):
    a = np.ascontiguousarray(a)
    h, w = a.shape[:2]
    return QImage(a.data, w, h, w * 4, QImage.Format_RGBA8888).copy()


def img_bytes(img):
    ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); img.save(buf, "PNG"); buf.close()
    return bytes(ba)


def flood_mask(arr, sx, sy, tol=40):
    """Connected region similar to the seed pixel, by scanline runs (fast enough for full-HD)."""
    h, w = arr.shape[:2]
    seed = arr[sy, sx].astype(np.int16)
    sim = (np.abs(arr.astype(np.int16) - seed).max(axis=2) <= tol)
    runs = {}
    def row_runs(y):
        r = runs.get(y)
        if r is None:
            d = np.diff(np.concatenate(([0], sim[y].astype(np.int8), [0])))
            r = (np.flatnonzero(d == 1), np.flatnonzero(d == -1)); runs[y] = r
        return r
    mask = np.zeros((h, w), bool)
    st, en = row_runs(sy)
    i = int(np.searchsorted(en, sx, side="right"))
    if i >= len(st) or st[i] > sx:
        return mask
    seen = {(sy, i)}; todo = [(sy, i)]
    while todo:
        y, i = todo.pop()
        s, e = row_runs(y)[0][i], row_runs(y)[1][i]
        mask[y, s:e] = True
        for ny in (y - 1, y + 1):
            if 0 <= ny < h:
                ns, ne = row_runs(ny)
                a = int(np.searchsorted(ne, s, side="right")); b = int(np.searchsorted(ns, e, side="left"))
                for j in range(a, b):
                    if (ny, j) not in seen:
                        seen.add((ny, j)); todo.append((ny, j))
    return mask


class Project:
    def __init__(self, w=1920, h=1080):
        self.w, self.h = w, h
        self.bg = 0
        self.frames = [[blank_draw(w, h)]]
        self.fps, self.loop, self.anim = 8, True, False

    def snapshot(self):
        return (self.w, self.h, self.bg, [[l.clone() for l in f] for f in self.frames])

    def restore(self, s):
        self.w, self.h, self.bg, fr = s
        self.frames = [[l.clone() for l in f] for f in fr]

    def is_empty(self):
        for f in self.frames:
            for l in f:
                if l.kind == "image":
                    return False
                if l.kind == "draw" and not l.img.isNull():
                    a = qimg_to_np(l.img.scaled(64, 64)) if (l.img.width() > 64) else qimg_to_np(l.img)
                    if a[..., 3].any():
                        return False
        return True


def paint_frame(p, proj, frame, bg=True):
    if bg:
        c = BGS[proj.bg][1]
        if c is not None:
            p.fillRect(QRectF(0, 0, proj.w, proj.h), c)
    for l in frame:
        if not l.visible:
            continue
        p.save(); p.setOpacity(p.opacity() * l.opacity)
        if l.kind == "image":
            p.setTransform(l.xform(), True)
        p.drawImage(0, 0, l.img)
        p.restore()


def render_frame(proj, frame, force_bg=None):
    im = QImage(proj.w, proj.h, FMT); im.fill(force_bg if force_bg is not None else 0)
    p = QPainter(im); p.setRenderHint(QPainter.SmoothPixmapTransform); p.setRenderHint(QPainter.Antialiasing)
    paint_frame(p, proj, frame); p.end()
    return im


class Canvas(QWidget):
    def __init__(self, board):
        super().__init__()
        self.b = board
        self.setFocusPolicy(Qt.StrongFocus); self.setMouseTracking(True); self.setAcceptDrops(True)
        self.setMinimumSize(320, 240)
        self.drag = None; self.last = None

    # view mapping
    def view(self):
        pr = self.b.proj
        s = max(0.02, min((self.width() - 24) / pr.w, (self.height() - 24) / pr.h))
        return s, (self.width() - pr.w * s) / 2, (self.height() - pr.h * s) / 2

    def to_canvas(self, pos):
        s, ox, oy = self.view()
        return QPointF((pos.x() - ox) / s, (pos.y() - oy) / s)

    def handles(self, l):
        s, ox, oy = self.view()
        t = l.xform(); w, h = l.img.width(), l.img.height()
        corners = [t.map(QPointF(x, y)) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]
        topmid = t.map(QPointF(w / 2, 0)); c = QPointF(l.x, l.y)
        d = topmid - c; n = math.hypot(d.x(), d.y()) or 1
        rot = topmid + QPointF(d.x() / n, d.y() / n) * (34 / s)
        return corners, rot

    def paintEvent(self, e):
        b = self.b; pr = b.proj
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(BG))
        s, ox, oy = self.view()
        rect = QRectF(ox, oy, pr.w * s, pr.h * s)
        if BGS[pr.bg][1] is None:  # checkerboard
            p.save(); p.setClipRect(rect); k = 12
            for yy in range(int(rect.height() / k) + 1):
                for xx in range(int(rect.width() / k) + 1):
                    p.fillRect(QRectF(ox + xx * k, oy + yy * k, k, k), QColor("#3a3c42" if (xx + yy) % 2 else "#2c2e33"))
            p.restore()
        p.save(); p.setClipRect(rect); p.translate(ox, oy); p.scale(s, s)
        fr = pr.frames[b.cur]
        paint_frame(p, pr, [], bg=True)
        if pr.anim and b.onion.isChecked() and not b.playing:
            for k, op in ((b.cur - 1, 0.28), (b.cur + 1, 0.18)):
                if 0 <= k < len(pr.frames):
                    p.save(); p.setOpacity(op); paint_frame(p, pr, pr.frames[k], bg=False); p.restore()
        paint_frame(p, pr, fr, bg=False)
        p.restore()
        p.setPen(QPen(QColor(BORDER), 1)); p.drawRect(rect)
        l = b.layer()
        if l is not None and l.kind == "image" and b.tool == "move" and not b.playing:
            corners, rot = self.handles(l)
            vc = [QPointF(ox + c.x() * s, oy + c.y() * s) for c in corners]
            vr = QPointF(ox + rot.x() * s, oy + rot.y() * s)
            p.setPen(QPen(QColor(ACC), 1)); p.setBrush(Qt.NoBrush); p.drawPolygon(QPolygonF(vc))
            tm = (vc[0] + vc[1]) / 2; p.drawLine(tm, vr)
            p.setBrush(QColor(SILVER)); p.setPen(QPen(QColor("#141518"), 1))
            for c in vc:
                p.drawRect(QRectF(c.x() - 5, c.y() - 5, 10, 10))
            p.drawEllipse(vr, 6, 6)
        if b.empty:
            cx, cy = self.width() / 2, self.height() / 2 - 30
            p.setPen(QPen(QColor(DIM), 3)); p.setBrush(Qt.NoBrush); p.drawRect(QRectF(cx - 36, cy - 26, 72, 52))
            p.setPen(Qt.NoPen); p.setBrush(QColor(DIM))
            p.drawPolygon(QPolygonF([QPointF(cx - 30, cy + 20), QPointF(cx - 8, cy - 6), QPointF(cx + 6, cy + 8),
                                     QPointF(cx + 14, cy), QPointF(cx + 30, cy + 20)]))
            p.setBrush(QColor(ACC)); p.drawEllipse(QPointF(cx + 14, cy - 14), 6, 6)
            p.setPen(QColor(TXT)); f = QFont("Segoe UI", 15, QFont.Bold); p.setFont(f)
            p.drawText(QRectF(0, cy + 34, self.width(), 30), Qt.AlignCenter, "Your board is empty")
            p.setPen(QColor(MUT)); p.setFont(QFont("Segoe UI", 10))
            p.drawText(QRectF(0, cy + 64, self.width(), 24), Qt.AlignCenter,
                       "Click here or press  \u2b06 Upload  to add images from Downloads  \u2022  or use  Import to board  in WEB")
        p.end()

    # ---- mouse
    def mousePressEvent(self, e):
        b = self.b; self.setFocus()
        if b.playing:
            b.toggle_play()
        if e.button() != Qt.LeftButton:
            return
        if b.empty and b.tool == "move":
            b.upload(); return
        pt = self.to_canvas(e.position())
        if b.tool == "move":
            l = b.layer()
            if l is not None and l.kind == "image":
                corners, rot = self.handles(l)
                s = self.view()[0]; tol = 10 / s
                if math.hypot(pt.x() - rot.x(), pt.y() - rot.y()) < tol:
                    b.push_undo(); self.drag = ("rot", l); return
                c = corners[2]
                if math.hypot(pt.x() - c.x(), pt.y() - c.y()) < tol or any(math.hypot(pt.x() - q.x(), pt.y() - q.y()) < tol for q in corners):
                    b.push_undo(); self.drag = ("scale", l); return
            hit = b.hit(pt)
            if hit is not None:
                b.select_layer(hit); l = b.layer()
                b.push_undo(); self.drag = ("move", l, pt.x() - l.x, pt.y() - l.y)
            self.update(); return
        if b.tool == "picker":
            im = render_frame(b.proj, b.proj.frames[b.cur])
            x, y = int(pt.x()), int(pt.y())
            if 0 <= x < im.width() and 0 <= y < im.height():
                b.set_color(QColor(im.pixelColor(x, y).rgb()))
            return
        l = b.draw_target()
        if b.tool == "fill":
            b.push_undo(); b.fill_at(l, pt); return
        b.push_undo(); self.drag = ("paint", l); self.last = pt
        self.stroke(l, pt, pt)

    def stroke(self, l, a, c):
        b = self.b
        p = QPainter(l.img); p.setRenderHint(QPainter.Antialiasing)
        if b.tool == "eraser":
            p.setCompositionMode(QPainter.CompositionMode_Clear)
        pen = QPen(b.color, b.size.value(), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        if a == c:
            p.drawPoint(a)
        else:
            p.drawLine(a, c)
        p.end()
        b.empty = False
        self.update()

    def mouseMoveEvent(self, e):
        if not self.drag:
            return
        b = self.b; pt = self.to_canvas(e.position()); k = self.drag[0]; l = self.drag[1]
        if k == "paint":
            self.stroke(l, self.last, pt); self.last = pt; return
        if k == "move":
            l.x, l.y = pt.x() - self.drag[2], pt.y() - self.drag[3]
        elif k == "scale":
            r = math.hypot(l.img.width(), l.img.height()) / 2 or 1
            l.scale = max(0.02, math.hypot(pt.x() - l.x, pt.y() - l.y) / r)
        elif k == "rot":
            l.rot = math.degrees(math.atan2(pt.y() - l.y, pt.x() - l.x)) + 90
            if e.modifiers() & Qt.ShiftModifier:
                l.rot = round(l.rot / 15) * 15
        self.update()

    def mouseReleaseEvent(self, e):
        if self.drag:
            self.drag = None; self.b.changed()

    def wheelEvent(self, e):
        b = self.b; l = b.layer()
        if b.tool == "move" and l is not None and l.kind == "image":
            if not getattr(self, "_wheel_undo", False):
                b.push_undo(); self._wheel_undo = True
                QTimer.singleShot(600, lambda: setattr(self, "_wheel_undo", False))
            l.scale = max(0.02, l.scale * (1.1 ** (e.angleDelta().y() / 120)))
            self.update(); b.changed(light=True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        if md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    self.b.add_file(u.toLocalFile())
        elif md.hasImage():
            self.b.import_image(QImage(md.imageData()), "Dropped image")


class EliteBoard(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.proj = Project()
        self.cur = 0; self.cur_layer = 0
        self.tool = "move"; self.color = QColor("#000000")
        self.undo_stack, self.redo_stack = [], []
        self.playing = False; self.empty = True
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick)
        self.thumb_timer = QTimer(self); self.thumb_timer.setSingleShot(True); self.thumb_timer.timeout.connect(self._thumbs)
        self._build()
        self._refresh_layers(); self._thumbs()

    # ---------------- UI
    def _build(self):
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        bar = QWidget(); bar.setObjectName("tools"); h = QHBoxLayout(bar); h.setContentsMargins(12, 8, 12, 8); h.setSpacing(6)
        up = QPushButton("\u2b06  Upload"); up.setObjectName("accent"); up.setToolTip("Add images from your Downloads"); up.clicked.connect(self.upload); h.addWidget(up)
        h.addSpacing(8)
        self.tool_btns = {}; grp = QButtonGroup(self); grp.setExclusive(True)
        for key, txt, tip in (("move", "\u2725", "Move / scale / rotate (V)"), ("brush", "\u270e", "Brush (B)"),
                              ("eraser", "\u232b", "Eraser (E)"), ("fill", "\u25a7", "Fill (G)"), ("picker", "\u2316", "Colour picker (I)")):
            b = QPushButton(txt); b.setObjectName("tool"); b.setCheckable(True); b.setToolTip(tip)
            b.clicked.connect(lambda _=False, k=key: self.set_tool(k)); grp.addButton(b); h.addWidget(b); self.tool_btns[key] = b
        self.tool_btns["move"].setChecked(True)
        self.col_btn = QPushButton(); self.col_btn.setFixedSize(30, 28); self.col_btn.setToolTip("Colour"); self.col_btn.clicked.connect(self.pick_color)
        h.addWidget(self.col_btn)
        for c in SWATCHES:
            s = QPushButton(); s.setFixedSize(16, 16); s.setToolTip(c)
            s.setStyleSheet("QPushButton{background:%s;border:1px solid %s;border-radius:2px;padding:0}" % (c, BORDER))
            s.clicked.connect(lambda _=False, cc=c: self.set_color(QColor(cc))); h.addWidget(s)
        h.addSpacing(6); sl = QLabel("Size"); sl.setObjectName("muted"); h.addWidget(sl)
        self.size = QSlider(Qt.Horizontal); self.size.setRange(1, 200); self.size.setValue(12); self.size.setFixedWidth(110); h.addWidget(self.size)
        self.size_lbl = QLabel("12"); self.size_lbl.setObjectName("muted"); self.size_lbl.setFixedWidth(26); h.addWidget(self.size_lbl)
        self.size.valueChanged.connect(lambda x: self.size_lbl.setText(str(x)))
        bu = QPushButton("\u21b6"); bu.setObjectName("tool"); bu.setToolTip("Undo (Ctrl+Z)"); bu.clicked.connect(self.undo); h.addWidget(bu)
        br = QPushButton("\u21b7"); br.setObjectName("tool"); br.setToolTip("Redo (Ctrl+Y)"); br.clicked.connect(self.redo); h.addWidget(br)
        h.addSpacing(6)
        self.preset = QComboBox(); self.preset.addItems(["%d \u00d7 %d" % p for p in PRESETS]); self.preset.setToolTip("Canvas size")
        self.preset.currentIndexChanged.connect(self.set_preset); h.addWidget(self.preset)
        self.bgc = QComboBox(); self.bgc.addItems([n for n, _ in BGS]); self.bgc.setToolTip("Board background")
        self.bgc.currentIndexChanged.connect(self.set_bg); h.addWidget(self.bgc)
        h.addStretch(1)
        self.anim_chk = QCheckBox("Animation"); self.anim_chk.setToolTip("Show the frame timeline, onion skin, play and GIF/MP4 export")
        self.anim_chk.toggled.connect(self.set_anim); h.addWidget(self.anim_chk)
        h.addSpacing(8)
        bo = QPushButton("Open"); bo.setObjectName("tool"); bo.setToolTip("Open project .rex7 (Ctrl+O)"); bo.clicked.connect(self.open_project); h.addWidget(bo)
        bs = QPushButton("Save"); bs.setObjectName("tool"); bs.setToolTip("Save project .rex7 (Ctrl+S)"); bs.clicked.connect(self.save_project); h.addWidget(bs)
        bb = QPushButton(" Bin"); bb.setIcon(trash_icon()); bb.setObjectName("danger"); bb.setToolTip("Clear the board (Ctrl+Z brings it back)"); bb.clicked.connect(self.bin); h.addWidget(bb)
        self.dl = QPushButton("\u2b07  Download"); self.dl.setToolTip("Save the result to Downloads"); self.dl.clicked.connect(self.download); h.addWidget(self.dl)
        v.addWidget(bar)

        mid = QHBoxLayout(); mid.setContentsMargins(12, 10, 12, 8); mid.setSpacing(10)
        self.canvas = Canvas(self); mid.addWidget(self.canvas, 1)
        side = QVBoxLayout(); side.setSpacing(6)
        lt = QLabel("LAYERS"); lt.setObjectName("dim"); side.addWidget(lt)
        self.layers = QListWidget(); self.layers.setFixedWidth(220)
        self.layers.currentRowChanged.connect(self._layer_row); self.layers.itemChanged.connect(self._layer_vis)
        side.addWidget(self.layers, 1)
        lr = QHBoxLayout(); lr.setSpacing(4)
        for txt, tip, fn in (("+", "New drawing layer", self.add_draw_layer), ("\u25b2", "Move layer up", lambda: self.move_layer(1)),
                             ("\u25bc", "Move layer down", lambda: self.move_layer(-1)), ("\u29c9", "Duplicate layer", self.dup_layer),
                             ("\u2715", "Delete layer (Del)", self.del_layer)):
            b = QPushButton(txt); b.setObjectName("tool"); b.setToolTip(tip); b.clicked.connect(fn); lr.addWidget(b)
        side.addLayout(lr)
        ol = QLabel("Layer opacity"); ol.setObjectName("muted"); side.addWidget(ol)
        self.opacity = QSlider(Qt.Horizontal); self.opacity.setRange(5, 100); self.opacity.setValue(100)
        self.opacity.sliderPressed.connect(self.push_undo); self.opacity.valueChanged.connect(self._opacity); side.addWidget(self.opacity)
        mid.addLayout(side)
        v.addLayout(mid, 1)

        # ---- optional animation timeline
        self.tl = QWidget(); self.tl.setObjectName("timeline"); tv = QVBoxLayout(self.tl); tv.setContentsMargins(12, 6, 12, 8); tv.setSpacing(6)
        row = QHBoxLayout(); row.setSpacing(6)
        self.b_play = QPushButton("\u25b6  Play"); self.b_play.setToolTip("Play / pause (Space)"); self.b_play.clicked.connect(self.toggle_play); row.addWidget(self.b_play)
        self.loop = QCheckBox("Loop"); self.loop.setChecked(True); self.loop.toggled.connect(lambda x: setattr(self.proj, "loop", x)); row.addWidget(self.loop)
        fl = QLabel("FPS"); fl.setObjectName("muted"); row.addWidget(fl)
        self.fps = QSpinBox(); self.fps.setRange(1, 30); self.fps.setValue(8); self.fps.valueChanged.connect(self._fps); row.addWidget(self.fps)
        self.onion = QCheckBox("Onion skin"); self.onion.setChecked(True); self.onion.toggled.connect(lambda _: self.canvas.update()); row.addWidget(self.onion)
        row.addSpacing(12)
        for txt, tip, fn in (("+ Frame", "New frame (N)", self.new_frame), ("\u29c9 Duplicate", "Duplicate frame (Ctrl+D)", self.dup_frame),
                             ("\u2715 Delete", "Delete frame", self.del_frame), ("\u25c0 Move", "Move frame left", lambda: self.move_frame(-1)),
                             ("Move \u25b6", "Move frame right", lambda: self.move_frame(1))):
            b = QPushButton(txt); b.setToolTip(tip); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch(1)
        self.frame_lbl = QLabel(""); self.frame_lbl.setObjectName("muted"); row.addWidget(self.frame_lbl)
        hint = QLabel("\u2190/\u2192 frames \u2022 Space play \u2022 N new frame"); hint.setObjectName("dim"); row.addWidget(hint)
        tv.addLayout(row)
        self.strip = QListWidget(); self.strip.setViewMode(QListView.IconMode); self.strip.setFlow(QListView.LeftToRight)
        self.strip.setWrapping(False); self.strip.setMovement(QListView.Static); self.strip.setFixedHeight(104)
        self.strip.setIconSize(QSize(128, 72)); self.strip.setSpacing(4)
        self.strip.currentRowChanged.connect(self._strip_row)
        tv.addWidget(self.strip)
        self.tl.setVisible(False)
        v.addWidget(self.tl)

        st = QHBoxLayout(); st.setContentsMargins(14, 0, 14, 6)
        self.status = QLabel("Upload images from your Downloads to start."); self.status.setObjectName("muted"); st.addWidget(self.status)
        v.addLayout(st)
        self.set_color(self.color)

        def sc(keys, fn, anim_only=False):
            for k in keys if isinstance(keys, (list, tuple)) else [keys]:
                s = QShortcut(QKeySequence(k), self, (lambda f=fn: self.proj.anim and f()) if anim_only else fn)
                s.setContext(Qt.WidgetWithChildrenShortcut)
        sc("Ctrl+Z", self.undo); sc(["Ctrl+Y", "Ctrl+Shift+Z"], self.redo)
        sc(["Right", "."], lambda: self.goto(self.cur + 1), True); sc(["Left", ","], lambda: self.goto(self.cur - 1), True)
        sc("Space", self.toggle_play, True); sc("N", self.new_frame, True); sc("Ctrl+D", self.dup_frame, True)
        sc("V", lambda: self.set_tool("move")); sc("B", lambda: self.set_tool("brush")); sc("E", lambda: self.set_tool("eraser"))
        sc("G", lambda: self.set_tool("fill")); sc("I", lambda: self.set_tool("picker"))
        sc("Delete", self.del_layer); sc("Ctrl+S", self.save_project); sc("Ctrl+O", self.open_project); sc("Ctrl+V", self.paste)
        sc("[", lambda: self.size.setValue(max(1, self.size.value() - 2))); sc("]", lambda: self.size.setValue(self.size.value() + 2))

    def say(self, t):
        self.status.setText(t)

    def enter(self):
        self.canvas.setFocus()

    def leave(self):
        if self.playing:
            self.toggle_play()

    # ---------------- model helpers
    def frame(self):
        return self.proj.frames[self.cur]

    def layer(self):
        f = self.frame()
        return f[self.cur_layer] if 0 <= self.cur_layer < len(f) else None

    def push_undo(self):
        self.undo_stack.append((self.proj.snapshot(), self.cur, self.cur_layer, self.empty))
        del self.undo_stack[:-UNDO_MAX]; self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append((self.proj.snapshot(), self.cur, self.cur_layer, self.empty))
        s, self.cur, self.cur_layer, self.empty = self.undo_stack.pop(); self.proj.restore(s); self._after_restore()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append((self.proj.snapshot(), self.cur, self.cur_layer, self.empty))
        s, self.cur, self.cur_layer, self.empty = self.redo_stack.pop(); self.proj.restore(s); self._after_restore()

    def _after_restore(self):
        self.cur = min(self.cur, len(self.proj.frames) - 1)
        self._sync_controls(); self._refresh_layers(); self._thumbs(); self.canvas.update()

    def _sync_controls(self):
        for i, p in enumerate(PRESETS):
            if p == (self.proj.w, self.proj.h):
                self.preset.blockSignals(True); self.preset.setCurrentIndex(i); self.preset.blockSignals(False)
        self.bgc.blockSignals(True); self.bgc.setCurrentIndex(self.proj.bg); self.bgc.blockSignals(False)

    def changed(self, light=False):
        self.canvas.update()
        if not light:
            self._refresh_layers()
        self.thumb_timer.start(250)

    def hit(self, pt):
        f = self.frame()
        for i in range(len(f) - 1, -1, -1):
            l = f[i]
            if l.kind == "image" and l.visible:
                q, ok = l.xform().inverted()
                m = q.map(pt)
                if 0 <= m.x() <= l.img.width() and 0 <= m.y() <= l.img.height():
                    return i
        return None

    def draw_target(self):
        f = self.frame(); l = self.layer()
        if l is not None and l.kind == "draw":
            return l
        i = self.cur_layer + 1
        if i < len(f) and f[i].kind == "draw":
            self.cur_layer = i
        else:
            f.insert(i, blank_draw(self.proj.w, self.proj.h, "Drawing %d" % (sum(1 for x in f if x.kind == "draw") + 1)))
            self.cur_layer = i
        self._refresh_layers()
        return f[self.cur_layer]

    def fill_at(self, l, pt):
        x, y = int(pt.x()), int(pt.y())
        if not (0 <= x < self.proj.w and 0 <= y < self.proj.h):
            return
        comp = qimg_to_np(render_frame(self.proj, self.frame()))
        m = flood_mask(comp, x, y)
        a = np.zeros((self.proj.h, self.proj.w, 4), np.uint8)
        c = self.color; a[m] = (c.red(), c.green(), c.blue(), 255)
        p = QPainter(l.img); p.drawImage(0, 0, np_to_qimg(a)); p.end()
        self.empty = False; self.changed()

    # ---------------- tools
    def set_tool(self, k):
        self.tool = k; self.tool_btns[k].setChecked(True)
        self.canvas.setCursor(Qt.ArrowCursor if k == "move" else Qt.CrossCursor); self.canvas.update()

    def set_color(self, c):
        self.color = c
        self.col_btn.setStyleSheet("QPushButton{background:%s;border:2px solid %s;border-radius:4px;padding:0}" % (c.name(), SILVER))

    def pick_color(self):
        c = QColorDialog.getColor(self.color, self, "Colour")
        if c.isValid():
            self.set_color(c)

    def set_preset(self, i):
        w, h = PRESETS[i]
        if (w, h) == (self.proj.w, self.proj.h):
            return
        self.push_undo()
        dx, dy = (w - self.proj.w) / 2, (h - self.proj.h) / 2
        for f in self.proj.frames:
            for l in f:
                if l.kind == "image":
                    l.x += dx; l.y += dy
                else:
                    im = QImage(w, h, FMT); im.fill(0); p = QPainter(im); p.drawImage(int(dx), int(dy), l.img); p.end(); l.img = im
        self.proj.w, self.proj.h = w, h
        self.changed(); self._thumbs(); self.say("Canvas %d \u00d7 %d" % (w, h))

    def set_bg(self, i):
        self.push_undo(); self.proj.bg = i; self.changed(); self._thumbs()

    # ---------------- images
    def import_image(self, img, name):
        if img is None or img.isNull():
            self.say("Nothing to import."); return
        img = img.convertToFormat(FMT)
        if max(img.width(), img.height()) > 4096:
            img = img.scaled(4096, 4096, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.push_undo()
        pr = self.proj
        sc = min(1.0, 0.9 * pr.w / img.width(), 0.9 * pr.h / img.height())
        l = Layer("image", img, name[:40], pr.w / 2, pr.h / 2, sc)
        f = self.frame(); i = min(self.cur_layer + 1, len(f)); f.insert(i, l); self.cur_layer = i
        self.empty = False
        self.set_tool("move"); self.changed(); self.say("%s added \u2014 drag to move, corner to scale, round handle to rotate." % name[:40])

    def add_file(self, path):
        img = QImage(path)
        if img.isNull():
            self.say("Couldn't open " + os.path.basename(path)); return
        self.import_image(img, os.path.splitext(os.path.basename(path))[0])

    def upload(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Upload images", downloads_dir(), IMG_FILTER)
        for f in files:
            self.add_file(f)

    def paste(self):
        md = QGuiApplication.clipboard().mimeData()
        if md.hasImage():
            self.import_image(QImage(md.imageData()), "Pasted image")
        elif md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    self.add_file(u.toLocalFile())

    def bin(self):
        self.push_undo()
        if self.playing:
            self.toggle_play()
        self.proj.frames = [[blank_draw(self.proj.w, self.proj.h)]]
        self.cur = 0; self.cur_layer = 0; self.empty = True
        self.changed(); self._thumbs(); self.say("Board cleared. Ctrl+Z brings it back.")

    # ---------------- layers
    def _refresh_layers(self):
        f = self.frame()
        self.cur_layer = max(0, min(self.cur_layer, len(f) - 1))
        self.layers.blockSignals(True); self.layers.clear()
        for i in range(len(f) - 1, -1, -1):
            l = f[i]
            it = QListWidgetItem(("\u25a3  " if l.kind == "image" else "\u270e  ") + l.name)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked if l.visible else Qt.Unchecked)
            self.layers.addItem(it)
        self.layers.setCurrentRow(len(f) - 1 - self.cur_layer)
        self.layers.blockSignals(False)
        l = self.layer()
        if l is not None:
            self.opacity.blockSignals(True); self.opacity.setValue(int(l.opacity * 100)); self.opacity.blockSignals(False)

    def _layer_row(self, r):
        if r >= 0:
            self.cur_layer = len(self.frame()) - 1 - r
            l = self.layer()
            if l is not None:
                self.opacity.blockSignals(True); self.opacity.setValue(int(l.opacity * 100)); self.opacity.blockSignals(False)
            self.canvas.update()

    def _layer_vis(self, it):
        r = self.layers.row(it); i = len(self.frame()) - 1 - r
        self.frame()[i].visible = it.checkState() == Qt.Checked
        self.canvas.update(); self.thumb_timer.start(250)

    def _opacity(self, v):
        l = self.layer()
        if l is not None:
            l.opacity = v / 100.0; self.canvas.update(); self.thumb_timer.start(250)

    def select_layer(self, i):
        self.cur_layer = i; self._refresh_layers()

    def add_draw_layer(self):
        self.push_undo(); f = self.frame(); i = self.cur_layer + 1
        f.insert(i, blank_draw(self.proj.w, self.proj.h, "Drawing %d" % (sum(1 for x in f if x.kind == "draw") + 1)))
        self.cur_layer = i; self.changed()

    def move_layer(self, d):
        f = self.frame(); i = self.cur_layer; j = i + d
        if 0 <= j < len(f):
            self.push_undo(); f[i], f[j] = f[j], f[i]; self.cur_layer = j; self.changed()

    def dup_layer(self):
        l = self.layer()
        if l is None:
            return
        self.push_undo(); n = l.clone(); n.name = (l.name + " copy")[:40]
        if n.kind == "image":
            n.x += 24; n.y += 24
        self.frame().insert(self.cur_layer + 1, n); self.cur_layer += 1; self.changed()

    def del_layer(self):
        f = self.frame()
        if not f:
            return
        self.push_undo(); del f[self.cur_layer]
        if not f:
            f.append(blank_draw(self.proj.w, self.proj.h))
        self.cur_layer = max(0, self.cur_layer - 1)
        self.empty = self.proj.is_empty(); self.changed()

    # ---------------- animation (optional)
    def set_anim(self, on):
        self.proj.anim = on; self.tl.setVisible(on)
        if not on and self.playing:
            self.toggle_play()
        self.dl.setText("\u2b07  Download  \u25be" if on else "\u2b07  Download")
        self._thumbs(); self.canvas.update()
        self.say("Animation on \u2014 add frames, onion skin shows the frames around this one." if on else "Image board mode.")

    def _fps(self, v):
        self.proj.fps = v
        if self.playing:
            self.timer.start(int(1000 / v))

    def goto(self, i):
        n = len(self.proj.frames)
        if n == 0:
            return
        self.cur = max(0, min(n - 1, i))
        self._refresh_layers()
        self.strip.blockSignals(True); self.strip.setCurrentRow(self.cur); self.strip.blockSignals(False)
        self.frame_lbl.setText("Frame %d / %d" % (self.cur + 1, n))
        self.canvas.update()

    def _strip_row(self, r):
        if r >= 0 and r != self.cur:
            self.goto(r)

    def new_frame(self):
        self.push_undo()
        nf = [l.clone(blank=True) for l in self.frame()]  # images carry over, drawings start blank
        self.proj.frames.insert(self.cur + 1, nf); self._thumbs(); self.goto(self.cur + 1)

    def dup_frame(self):
        self.push_undo()
        self.proj.frames.insert(self.cur + 1, [l.clone() for l in self.frame()]); self._thumbs(); self.goto(self.cur + 1)

    def del_frame(self):
        if len(self.proj.frames) <= 1:
            self.say("The last frame can't be deleted \u2014 use Bin to clear."); return
        self.push_undo(); del self.proj.frames[self.cur]; self._thumbs(); self.goto(min(self.cur, len(self.proj.frames) - 1))

    def move_frame(self, d):
        j = self.cur + d
        if 0 <= j < len(self.proj.frames):
            self.push_undo(); fr = self.proj.frames; fr[self.cur], fr[j] = fr[j], fr[self.cur]; self._thumbs(); self.goto(j)

    def toggle_play(self):
        if self.playing:
            self.playing = False; self.timer.stop(); self.b_play.setText("\u25b6  Play"); self.canvas.update(); return
        if len(self.proj.frames) < 2:
            self.say("Add at least 2 frames to play."); return
        self.playing = True; self.b_play.setText("\u275a\u275a  Pause"); self.timer.start(int(1000 / self.proj.fps))

    def _tick(self):
        n = len(self.proj.frames)
        if self.cur + 1 >= n:
            if not self.proj.loop:
                self.toggle_play(); return
            self.goto(0)
        else:
            self.goto(self.cur + 1)

    def _thumbs(self):
        if not self.proj.anim:
            self.frame_lbl.setText(""); return
        pr = self.proj
        self.strip.blockSignals(True)
        while self.strip.count() > len(pr.frames):
            self.strip.takeItem(self.strip.count() - 1)
        for i, f in enumerate(pr.frames):
            im = render_frame(pr, f, QColor(*BOARD_RGB) if BGS[pr.bg][1] is None else None).scaled(128, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if i >= self.strip.count():
                self.strip.addItem(QListWidgetItem())
            it = self.strip.item(i); it.setIcon(QIcon(QPixmap.fromImage(im))); it.setText(str(i + 1))
        self.strip.setCurrentRow(self.cur); self.strip.blockSignals(False)
        self.frame_lbl.setText("Frame %d / %d" % (self.cur + 1, len(pr.frames)))

    # ---------------- files
    def save_project(self, path=None):
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save REX 7 ELITE project", os.path.join(downloads_dir(), "board.rex7"), "REX 7 project (*.rex7)")
        if not path:
            return
        if not path.lower().endswith(".rex7"):
            path += ".rex7"
        pr = self.proj; blobs = {}; frames = []
        for f in pr.frames:
            fl = []
            for l in f:
                key = "img_%x.png" % l.img.cacheKey()
                if key not in blobs:
                    blobs[key] = img_bytes(l.img)
                fl.append(dict(kind=l.kind, name=l.name, img=key, x=l.x, y=l.y, scale=l.scale, rot=l.rot, visible=l.visible, opacity=l.opacity))
            frames.append(fl)
        meta = dict(format="rex7", version=1, w=pr.w, h=pr.h, bg=pr.bg, fps=pr.fps, loop=pr.loop, anim=pr.anim, frames=frames)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json", json.dumps(meta, indent=1))
            for k, b in blobs.items():
                z.writestr(k, b)
        self.say("Saved " + path)

    def open_project(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open REX 7 ELITE project", downloads_dir(), "REX 7 project (*.rex7)")
        if not path:
            return
        try:
            with zipfile.ZipFile(path) as z:
                meta = json.loads(z.read("project.json")); cache = {}
                def im(k):
                    if k not in cache:
                        q = QImage(); q.loadFromData(z.read(k)); cache[k] = q.convertToFormat(FMT)
                    return cache[k]
                frames = [[Layer(d["kind"], QImage(im(d["img"])), d["name"], d["x"], d["y"], d["scale"], d["rot"], d["visible"], d["opacity"])
                           for d in f] for f in meta["frames"]]
        except Exception as ex:
            QMessageBox.warning(self, "REX 7 ELITE", "Couldn't open this project:\n%s" % ex); return
        self.push_undo()
        pr = self.proj; pr.w, pr.h, pr.bg = meta["w"], meta["h"], meta.get("bg", 0); pr.frames = frames or [[blank_draw(pr.w, pr.h)]]
        pr.fps, pr.loop = meta.get("fps", 8), meta.get("loop", True)
        self.fps.setValue(pr.fps); self.loop.setChecked(pr.loop); self.anim_chk.setChecked(bool(meta.get("anim")))
        self.cur = 0; self.cur_layer = len(pr.frames[0]) - 1; self.empty = pr.is_empty()
        self._sync_controls(); self.changed(); self._thumbs(); self.goto(0); self.say("Opened " + os.path.basename(path))

    def download(self):
        if not self.proj.anim:
            self.export_png(); return
        m = QMenu(self)
        m.addAction("PNG image (this frame)", self.export_png)
        m.addAction("GIF animation", self.export_gif)
        m.addAction("MP4 video", self.export_mp4)
        m.addAction("PNG sequence (folder)", self.export_seq)
        m.exec(self.dl.mapToGlobal(self.dl.rect().bottomLeft()))

    def _stamp(self):
        return time.strftime("%Y%m%d_%H%M%S")

    def export_png(self, path=None):
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save PNG", os.path.join(downloads_dir(), "REX7_ELITE_%s.png" % self._stamp()), "PNG (*.png)")
        if path:
            render_frame(self.proj, self.frame()).save(path, "PNG"); self.say("Saved " + path)
        return path

    def _pil_frames(self):
        from PIL import Image
        bgc = QColor(255, 255, 255) if BGS[self.proj.bg][1] is None else None
        out = []
        for f in self.proj.frames:
            a = qimg_to_np(render_frame(self.proj, f, bgc).convertToFormat(QImage.Format_RGB888).convertToFormat(QImage.Format_ARGB32))
            out.append(Image.fromarray(a[..., :3].copy()))
        return out

    def export_gif(self, path=None):
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save GIF", os.path.join(downloads_dir(), "REX7_ELITE_%s.gif" % self._stamp()), "GIF (*.gif)")
        if not path:
            return
        fr = self._pil_frames()
        fr[0].save(path, save_all=True, append_images=fr[1:], duration=int(1000 / self.proj.fps), loop=0 if self.proj.loop else 1, optimize=False)
        self.say("Saved " + path); return path

    def export_mp4(self, path=None):
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save MP4", os.path.join(downloads_dir(), "REX7_ELITE_%s.mp4" % self._stamp()), "MP4 (*.mp4)")
        if not path:
            return
        import imageio_ffmpeg
        fr = self._pil_frames(); fps = self.proj.fps
        seq = list(fr)
        if self.proj.loop:  # loops play for at least 3 seconds
            while len(seq) < fps * 3:
                seq += fr
        w, h = fr[0].size
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
               "-r", str(fps), "-i", "-", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", path]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000 if os.name == "nt" else 0)
        for im in seq:
            pr.stdin.write(im.tobytes())
        pr.stdin.close(); err = pr.stderr.read(); pr.wait()
        if pr.returncode != 0:
            QMessageBox.warning(self, "REX 7 ELITE", "MP4 export failed:\n" + err.decode("utf-8", "ignore")[-400:]); return
        self.say("Saved " + path); return path

    def export_seq(self, folder=None):
        if not folder:
            base = QFileDialog.getExistingDirectory(self, "Choose a folder for the PNG sequence", downloads_dir())
            if not base:
                return
            folder = os.path.join(base, "REX7_ELITE_%s" % self._stamp())
        os.makedirs(folder, exist_ok=True)
        for i, f in enumerate(self.proj.frames):
            render_frame(self.proj, f).save(os.path.join(folder, "frame_%04d.png" % (i + 1)), "PNG")
        self.say("Saved %d frames to %s" % (len(self.proj.frames), folder)); return folder

    # ---------------- QA helpers (used by --selftest)
    def selftest_fill(self):
        pr = self.proj
        im = QImage(640, 400, FMT); im.fill(QColor("#c9ccd2"))
        p = QPainter(im); p.setRenderHint(QPainter.Antialiasing); p.setBrush(QColor("#3a3c42")); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(170, 50, 300, 300)); p.end()
        self.import_image(im, "Uploaded art")
        l = self.layer(); l.x, l.y, l.rot, l.scale = pr.w * 0.72, pr.h * 0.62, -12, 0.9
        self.set_tool("brush"); self.set_color(QColor("#e53935")); self.size.setValue(18)
        t = self.draw_target()
        p = QPainter(t.img); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#e53935"), 18, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for k in range(40):
            a = k / 39 * math.pi * 2
            p.drawPoint(QPointF(380 + 200 * math.cos(a) * (k / 39), 820 + 120 * math.sin(a)))
        p.drawLine(QPointF(220, 900), QPointF(620, 700)); p.end()
        self.fill_at(t, QPointF(pr.w * 0.72, pr.h * 0.62))
        from rex7_style import res_path
        self.add_file(res_path("assets", "splash.png"))
        l = self.layer(); l.x, l.y, l.scale = pr.w * 0.2, pr.h * 0.3, 0.75
        self.set_tool("move"); self.changed()

    def selftest_anim(self, out):
        self.anim_chk.setChecked(True)
        for k in range(5):
            self.dup_frame()
            l = [x for x in self.frame() if x.kind == "image"][-1]
            l.x -= 60; l.rot += 10
        self.goto(3); self._thumbs()
        try:
            self.export_gif(os.path.join(out, "test.gif")); self.export_mp4(os.path.join(out, "test.mp4"))
            self.export_seq(os.path.join(out, "seq")); self.save_project(os.path.join(out, "test.rex7"))
            self.open_project(os.path.join(out, "test.rex7")); self.goto(3)
            self.say("Self-test exports OK")
        except Exception as ex:
            self.say("Self-test export error: %s" % ex)
