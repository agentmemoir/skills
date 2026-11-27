#!/usr/bin/env python3
"""design-lock: compare an approved design frame with what the app actually renders. Python 3 stdlib only (Playwright only for extract-web).

  gate         run the project's capture command, then compare every screen of .design-lock.json   (the command hooks and CI run)
  compare      frame.spec.json app.measured.json [--tolerance ...]                                  -> per-element table
  extract-web  render an HTML page with Playwright -> spec/measured JSON
  init         scaffold .design-lock.json, tools, a capture recipe and the CI workflow in a new project

Exit codes: 0 pass, 1 design violation, 2 usage or input error.
"""
import argparse
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dlcore  # noqa: E402

SCHEMA = "design-lock/1"
# Defaults are tight enough to catch 1 dp offsets and 0.5 sp fonts. Loosen only in .design-lock.json, which is locked.
DEFAULT_TOL = {"box": 0.5, "fontSize": 0.1, "lineHeight": 0.1, "letterSpacing": 0.1, "radius": 0.25, "borderWidth": 0.1, "color": 2.0, "alpha": 0.02,
               "pixelRatio": 0.001, "pixelBlock": 4}
ROLES = ("container", "text", "image")
BOX_KEYS = ("x", "y", "w", "h")
SIDES = ("top", "right", "bottom", "left")
FONT_CORE = ("family", "size", "weight", "letterSpacing", "lineHeight")
FONT_KEYS = FONT_CORE + ("style", "align", "transform", "decoration", "variantNumeric", "indent", "whiteSpace", "overflow", "stroke")
FONT_TOL = {"size": "fontSize", "letterSpacing": "letterSpacing", "lineHeight": "lineHeight"}
BOX_STYLE = ("fill", "border", "radius", "shadow", "opacity", "backgroundImage", "filter", "clipPath", "outline", "textShadow", "blendMode", "backdropFilter", "objectFit")
STYLE_DEFAULT = {"opacity": 1, "backgroundImage": None, "filter": None, "clipPath": None, "outline": None, "textShadow": None, "blendMode": "normal",
                 "backdropFilter": None, "objectFit": None}  # absent means "none", so no adapter can skip them
SHAPE = ("radius", "border", "shadow", "clipPath", "objectFit")  # what a variable image slot still pins: its shape, never its content
MAX_GATE_SEC = 840


# ---------------------------------------------------------------- tolerance

def parse_tolerance(arg):
    """None, a dict, a number (box px), or 'k=v,k=v'. Unknown keys and non-numbers are errors, never ignored."""
    tol = dict(DEFAULT_TOL)
    if not arg:
        return tol
    if isinstance(arg, dict):
        over = arg
    elif isinstance(arg, str) and os.path.isfile(arg):
        over = json.load(open(arg))
    elif isinstance(arg, str) and "=" in arg:
        over = dict(kv.split("=", 1) for kv in arg.split(","))
    else:
        over = {"box": arg}
    bad = set(over) - set(DEFAULT_TOL)
    if bad:
        raise ValueError(f"unknown tolerance keys {sorted(bad)}; known: {sorted(DEFAULT_TOL)}")
    for k, v in over.items():
        try:
            tol[k] = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"tolerance {k} must be a number, got {v!r}")
        if tol[k] < 0:
            raise ValueError(f"tolerance {k} must not be negative")
    return tol


# ---------------------------------------------------------------- spec validation

def validate_spec(doc, pixel=False):
    """Problems that make a frame spec unable to pin the design: every constant a role needs must be stated, so absence is never "no constraint"."""
    errs = []
    if doc.get("schema") != SCHEMA:
        return [f"not a {SCHEMA} file"]
    els = doc.get("elements")
    if not isinstance(els, list) or not els:
        return ["the spec lists no elements"]
    seen = set()
    for e in els:
        eid = e.get("id")
        if not eid or not isinstance(eid, str):
            errs.append("an element has no id")
            continue
        if eid in seen:
            errs.append(f"{eid}: duplicate id")
        seen.add(eid)
        role = e.get("role")
        if role not in ROLES:
            errs.append(f"{eid}: role must be one of {ROLES}")
            continue
        box = e.get("box") or {}
        if any(not isinstance(box.get(k), (int, float)) for k in BOX_KEYS):
            errs.append(f"{eid}: box needs numeric x, y, w, h")
        if e.get("variable") and role == "container":
            errs.append(f"{eid}: a container is a constant and cannot be variable; mark only the content slot inside it as variable "
                        "(an image or text slot with no role is read as a container: set role image or text, e.g. data-dl-role or the map's role)")
        if set(e.get("flex", [])) - {"x", "y", "w", "h", "color", "fill"}:
            errs.append(f"{eid}: flex may list only x, y, w, h, color, fill")
        if pixel:
            if not e.get("variable"):
                errs.append(f"{eid}: a pixel-mode spec lists only variable regions (the masked slots)")
            continue
        style = e.get("style")
        if not isinstance(style, dict):
            errs.append(f"{eid}: no style")
            continue
        need = {"container": ("fill", "border", "radius", "shadow"), "text": ("fill", "border", "radius", "shadow", "color", "font"),
                "image": ("radius", "border")}[role]
        miss = [k for k in need if k not in style]
        if role == "text":
            miss += [f"font.{k}" for k in FONT_CORE if k not in (style.get("font") or {})]
            if not e.get("variable") and "text" not in style:
                miss.append("text")
        if miss:
            errs.append(f"{eid}: the spec does not state {', '.join(miss)} (state it, or null for none)")
    for ig in doc.get("ignored", []):
        if not (isinstance(ig, dict) and ig.get("selector") and str(ig.get("reason", "")).strip()):
            errs.append("an ignored region needs a selector and a reason")
    return errs


# ---------------------------------------------------------------- compare

def _num_ok(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol + 1e-9


def _color_ok(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return all(abs(x - y) <= tol["color"] + 1e-9 for x, y in zip(a[:3], b[:3])) and abs(a[3] - b[3]) <= tol["alpha"] + 1e-9


def _sides(b):
    """A border is one {width,color,style?} for all sides or {top,right,bottom,left}; None when no side paints."""
    if b is None:
        return None
    s = {k: b for k in SIDES} if "width" in b or "color" in b else {k: b.get(k) for k in SIDES}
    return None if all(v is None for v in s.values()) else s


def _side_ok(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return (_num_ok(a["width"], b["width"], tol["borderWidth"]) and _color_ok(a["color"], b["color"], tol)
            and a.get("style", "solid") == b.get("style", "solid"))


def _same(prop, a, b, tol):
    """Whether frame value `a` and app value `b` agree for property `prop`."""
    if prop.startswith("box."):
        return _num_ok(a, b, tol["box"])
    if prop.startswith("font."):
        k = prop[5:]
        if k in FONT_TOL:
            return _num_ok(a, b, tol[FONT_TOL[k]])
        return str(a).lower() == str(b).lower() if k == "family" else a == b
    if prop in ("fill", "color"):
        return _color_ok(a, b, tol)
    if prop == "opacity":
        return _num_ok(a, b, tol["alpha"])
    if prop == "border":
        sa, sb = _sides(a), _sides(b)
        return (sa is None and sb is None) or (sa is not None and sb is not None and all(_side_ok(sa[k], sb[k], tol) for k in SIDES))
    if prop == "radius":
        return a is not None and b is not None and len(a) == len(b) and all(_num_ok(x, y, tol["radius"]) for x, y in zip(a, b))
    return a == b  # text, shadow, backgroundImage, filter, clipPath, outline, role, theme, presence


def _show(v):
    if v is None:
        return "none"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, list):
        return "[" + ",".join(f"{x:g}" if isinstance(x, (int, float)) else str(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(f"{k}:{_show(x)}" for k, x in v.items()) + "}"
    return str(v)


def element_props(el):
    """(property, value) pairs a frame element pins down. A variable pins only its slot (box minus flex axes, font, and for an image its
    shape), never its content. A container around a variable is its own constant element."""
    variable = el.get("variable", False)
    flex = set(el.get("flex", [])) if variable else set()
    style = el.get("style", {})
    props = [(f"box.{k}", el["box"][k]) for k in BOX_KEYS if k in el.get("box", {})]
    if variable and el["role"] == "image":
        props += [(k, style[k]) for k in SHAPE if k in style]
    else:
        props += [(k, style.get(k, STYLE_DEFAULT.get(k))) for k in BOX_STYLE if k in style or k in STYLE_DEFAULT]
        if el["role"] == "text":
            props += [(f"font.{k}", style["font"][k]) for k in FONT_KEYS if k in style.get("font", {})]
            if "color" in style:
                props.append(("color", style["color"]))
            if not variable and "text" in style:
                props.append(("text", style["text"]))
    return [(k, v) for k, v in props if k not in flex and k.removeprefix("box.") not in flex]


def _get(el, prop):
    style = el.get("style", {})
    if prop.startswith("box."):
        return el.get("box", {}).get(prop[4:])
    if prop.startswith("font."):
        return (style.get("font") or {}).get(prop[5:])
    return style.get(prop, STYLE_DEFAULT.get(prop))


def _row(el_id, prop, frame, app, status, note=""):
    return {"element": el_id, "property": prop, "frame": frame, "app": app, "status": status, "note": note}


def _dups(doc):
    ids = [e.get("id") for e in doc.get("elements", [])]
    return sorted({i for i in ids if ids.count(i) > 1})


def compare_specs(frame, app, tol, exceptions=(), known=(), allow_extra=False):
    """Rows of the per-element table. status: pass | variable | exception | known | fail | warn. Any `fail` fails the design."""
    rows = []
    for doc, name in ((frame, "frame"), (app, "app")):
        if doc.get("schema") != SCHEMA:
            raise ValueError(f"{name} file is not {SCHEMA}")
    for p in validate_spec(frame):
        rows.append(_row("(frame spec)", "invalid", p, "-", "fail", "the approved frame does not pin this down; ask me to complete the spec"))
    for who, doc in (("app", app), ("frame", frame)):
        for i in _dups(doc):
            rows.append(_row(i, "duplicate id", "unique", "twice", "fail", f"two elements of the {who} share an id, so one would go unchecked"))
    if frame.get("theme") != app.get("theme"):
        rows.append(_row("(screen)", "theme", frame.get("theme"), app.get("theme"), "fail"))
    fv, av = frame.get("viewport", {}), app.get("viewport", {})
    for k in ("width", "height"):
        if k in fv and not _num_ok(fv[k], av.get(k), tol["box"]):
            rows.append(_row("(screen)", f"viewport.{k}", fv[k], av.get(k), "fail"))
    fr, ar = frame.get("renderer"), app.get("renderer")
    if fr and ar and fr != ar:
        rows.append(_row("(screen)", "renderer", _show(fr), _show(ar), "warn",
                         "frame and app were rendered by different engines; text widths may differ. Pin the browser and fonts in CI"))
    allowed = {g.get("selector") for g in frame.get("ignored", [])}
    for g in app.get("ignored", []):
        if g.get("selector") not in allowed:
            rows.append(_row(str(g.get("selector")), "ignored region", "-", "ignored by the app's capture", "fail",
                             "only regions the approved frame ignores may be ignored; the frame spec lists them, the capture map may not add more"))
    for doc, who in ((frame, "frame"), (app, "app")):
        for u in doc.get("unmapped", []):
            rows.append(_row(u.get("path", "?"), "unmapped", "-" if who == "frame" else "not in frame", u.get("why", "paints"), "fail",
                             f"{who} paints an element with no id in the table: map it, mark it variable, or ignore it with a reason"))
    app_by_id = {e["id"]: e for e in app.get("elements", [])}
    frame_ids = {e["id"] for e in frame.get("elements", [])}
    for el in frame.get("elements", []):
        if "role" not in el or "box" not in el:
            continue
        m = app_by_id.get(el["id"])
        if m is None:
            rows.append(_row(el["id"], "presence", "present", "missing", "fail"))
            continue
        if m.get("role") != el["role"]:
            rows.append(_row(el["id"], "role", el["role"], m.get("role"), "fail", "tag the app element with the frame's role (data-dl-role, or `role` in the capture map)"))
        for prop, fv_ in element_props(el):
            av_ = _get(m, prop)
            rows.append(_row(el["id"], prop, fv_, av_, "pass" if _same(prop, fv_, av_, tol) else "fail"))
        if el.get("variable"):
            rows.append(_row(el["id"], "content", "(variable)", "(not checked)", "variable"))
    if not allow_extra:
        for i in sorted(set(app_by_id) - frame_ids):
            rows.append(_row(i, "presence", "absent", "present", "fail", "element is not in the frame"))
    return _apply_rules(rows, frame_ids, exceptions, known, tol)


def _apply_rules(rows, frame_ids, exceptions, known, tol):
    """Turn named exceptions and known violations into statuses. A rule names one property and PINS the accepted app value: any other value
    (a worse one included) still fails. Invalid or stale rules fail (known) or warn (exception)."""
    extra = []
    for kind, rules in (("exception", exceptions), ("known violation", known)):
        for r in rules:
            who = r.get("element", "?")
            need = ("element", "property", "value", "reason") if kind == "exception" else ("element", "property", "value", "issue")
            missing = [k for k in need if k not in r or (k != "value" and not str(r.get(k, "")).strip())]
            if missing or r.get("element") not in frame_ids:
                extra.append(_row(who, r.get("property", "?"), "-", "-", "fail",
                                  f"{kind} is not valid: " + (f"missing {', '.join(missing)}" if missing else "element is not in the frame")))
                continue
            hit = [x for x in rows if x["element"] == who and x["property"] == r["property"] and x["status"] == "fail"]
            for x in hit:
                if _same(x["property"], r["value"], x["app"], tol):
                    x["status"] = "exception" if kind == "exception" else "known"
                    x["note"] = r.get("reason") or r.get("issue")
                else:
                    x["note"] = f"{kind} accepts {_show(r['value'])} but the app has {_show(x['app'])}: it changed, so it is not covered"
            if not hit:
                st = "warn" if kind == "exception" else "fail"
                extra.append(_row(who, r["property"], "-", "-", st,
                                  f"{kind} matches nothing" + (": remove it from the baseline (it now matches the frame)" if kind != "exception" else "")))
    return rows + extra


# ---------------------------------------------------------------- pixel mode (any platform that can write a PNG)

def read_png(path):
    """(width, height, bytes per pixel, rows) of an 8-bit, non-interlaced RGB or RGBA PNG."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    pos, idat, hdr = 8, b"", None
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if typ == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
    w, h, depth, ct, _, _, il = hdr
    if depth != 8 or ct not in (2, 6) or il:
        raise ValueError(f"{path}: only 8-bit RGB or RGBA non-interlaced PNGs are supported; re-export it")
    bpp, raw = (3 if ct == 2 else 4), zlib.decompress(idat)
    stride, rows, prev = w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride if f else 0):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return w, h, bpp, rows


def compare_pixels(frame_png, app_png, spec, tol):
    """Rows for a pixel-mode screen: same size, and at most pixelRatio of the pixels differ, outside the spec's variable slots."""
    fw, fh, fb, frows = read_png(frame_png)
    aw, ah, ab, arows = read_png(app_png)
    if (fw, fh) != (aw, ah):
        return [_row("(screen)", "image size", f"{fw}x{fh}", f"{aw}x{ah}", "fail", "capture at the frame's size and density")]
    vw = (spec.get("viewport") or {}).get("width") or fw
    scale = fw / vw
    masks = [(e["box"]["x"] * scale, e["box"]["y"] * scale, (e["box"]["x"] + e["box"]["w"]) * scale, (e["box"]["y"] + e["box"]["h"]) * scale)
             for e in spec.get("elements", []) if e.get("variable") and "box" in e]
    bad, x0, y0, x1, y1, blocks = 0, fw, fh, -1, -1, {}
    for y in range(fh):
        fa, aa = frows[y], arows[y]
        if fa == aa and fb == ab:
            continue
        m = [(a, c) for a, b_, c, d in masks if b_ <= y < d]
        for x in range(fw):
            if any(a <= x < c for a, c in m):
                continue
            if any(abs(fa[x * fb + k] - aa[x * ab + k]) > tol["color"] for k in range(3)):
                bad += 1
                x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
                blocks[x // 16, y // 16] = blocks.get((x // 16, y // 16), 0) + 1
    ratio = bad / (fw * fh)
    (bx, by), worst = max(blocks.items(), key=lambda kv: kv[1], default=((0, 0), 0))
    # A global budget alone would let a whole small element (an icon, a badge, a word) go wrong, so no 16x16 block may exceed `pixelBlock` either.
    ok = ratio <= tol["pixelRatio"] and worst <= tol["pixelBlock"]
    return [_row("(screen)", "pixels", f"<= {tol['pixelRatio']:.3%} differ, <= {tol['pixelBlock']:g} per 16x16 block",
                 f"{ratio:.3%} differ, worst block {worst} at x {bx * 16}, y {by * 16}" + (f"; changes within x {x0}-{x1}, y {y0}-{y1}" if bad else ""),
                 "pass" if ok else "fail", "" if ok else "variable slots are masked; every other pixel is a constant")]


# ---------------------------------------------------------------- report

def summarize(rows):
    s = {k: sum(1 for r in rows if r["status"] == k) for k in ("pass", "variable", "exception", "known", "warn", "fail")}
    s["elements"] = len({r["element"] for r in rows})
    return s


def markdown(title, rows, only_fail=False, note=""):
    s = summarize(rows)
    head = f"### {title}: {'FAIL' if s['fail'] else 'PASS'} ({s['fail']} failing, {s['pass']} passing, {s['exception']} exceptions, {s['known']} known violations)\n\n{note}"
    shown = [r for r in rows if r["status"] in ("fail", "warn")] if only_fail else sorted(rows, key=lambda r: r["status"] not in ("fail", "warn"))
    lines = ["| element | property | frame | app | result |", "| :- | :- | :- | :- | :- |"]
    for r in shown:
        res = {"pass": "ok", "fail": "**FAIL**", "variable": "variable", "exception": "exception", "known": "known", "warn": "warn"}[r["status"]]
        lines.append(f"| {r['element']} | {r['property']} | {_show(r['frame'])} | {_show(r['app'])} | {res} {r['note']} |".replace("  |", " |"))
    return head + "\n".join(lines) + "\n"


def cmd_compare(a):
    try:
        frame, app = json.load(open(a.frame)), json.load(open(a.app))
        tol = parse_tolerance(a.tolerance)
        rows = compare_specs(frame, app, tol, allow_extra=a.allow_extra)
    except (OSError, ValueError, KeyError) as e:
        print(f"design-lock compare: {e}", file=sys.stderr)
        return 2
    md = markdown(f"{a.frame} vs {a.app}", rows, a.only_fail)
    print(md)
    if a.md:
        open(a.md, "w").write(md)
    if a.json:
        json.dump({"pass": not summarize(rows)["fail"], "summary": summarize(rows), "tolerance": tol, "rows": rows}, open(a.json, "w"), indent=1)
    return 1 if summarize(rows)["fail"] else 0


# ---------------------------------------------------------------- gate

def gate_timeout(cfg):
    return min(int(cfg.get("gateTimeoutSec", 600)), MAX_GATE_SEC)


def run_capture(cfg, root):
    """Run the project's capture command in its own process group (killed whole on timeout). Returns (ok, output tail)."""
    p = subprocess.Popen(cfg["capture"], shell=True, cwd=root, start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def stop_group(signum, frame):  # the hook stops the gate with SIGTERM: take the capture's own process group down with it
        os.killpg(p.pid, signal.SIGKILL)
        sys.exit(2)

    signal.signal(signal.SIGTERM, stop_group)
    try:
        out, _ = p.communicate(timeout=gate_timeout(cfg))
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        return False, f"the capture command did not finish in {gate_timeout(cfg)} s\n" + out[-2000:]
    return p.returncode == 0, "\n".join(out.splitlines()[-40:])


def screen_rows(name, row, cfg, root, tol, known):
    pixel = row.get("mode", "structure") == "pixel"
    for k in ("frame", "image"):
        if not row.get(k) or not os.path.isfile(os.path.join(root, row[k])):
            return [_row("(screen)", k, f"approved {k}", f"missing {row.get(k)}", "fail", "ask me for the approved frame spec and image of every screen")]
    mp = os.path.join(root, row["measured"])
    if not os.path.isfile(mp):
        return [_row("(screen)", "measured", "approved frame", f"missing {row['measured']}", "fail", "the screen did not run: capture produced nothing for it")]
    try:
        frame = json.load(open(os.path.join(root, row["frame"])))
        if pixel:
            errs = validate_spec(frame, pixel=True)
            return ([_row("(frame spec)", "invalid", p, "-", "fail") for p in errs]
                    or compare_pixels(os.path.join(root, row["image"]), mp, frame, tol))
        return compare_specs(frame, json.load(open(mp)), tol, row.get("exceptions", []), known, row.get("allowExtra", False))
    except (OSError, ValueError, KeyError, struct.error, zlib.error) as e:
        return [_row("(screen)", "measured", "approved frame", f"cannot read: {e}", "fail")]


def coverage_rows(cfg, root):
    """Every UI file that `screenFiles` names must belong to a screen's `sources`, so a new screen cannot ship without a frame."""
    pats = cfg.get("screenFiles")
    if not pats:
        return []
    owned = [s for row in cfg["screens"].values() for s in row.get("sources", [])]
    return [_row(f, "frame coverage", "a registered screen", "none", "fail", "this UI file is in no screen's sources: it has no approved frame")
            for f in sorted(dlcore.project_files(root) or []) if dlcore.matches(f, pats) and not dlcore.matches(f, owned)]


def cmd_gate(a):
    root = os.path.abspath(a.root)
    try:
        cfg = dlcore.load_config(root)
        tol = parse_tolerance(cfg.get("tolerance"))
        bp = os.path.join(root, dlcore.baseline_path(cfg))
        baseline = json.load(open(bp)) if os.path.isfile(bp) else {}
    except (OSError, ValueError) as e:
        print(f"design-lock gate: {e}", file=sys.stderr)
        return 2
    screens = cfg["screens"]
    capture_note = ""
    if cfg.get("capture") and not a.no_capture:
        for row in screens.values():  # a stale measured file from an earlier run must never pass for a fresh one
            try:
                os.remove(os.path.join(root, row["measured"]))
            except OSError:
                pass
        guarded = dlcore.protected(cfg) + [dlcore.baseline_path(cfg)]
        before = dlcore.tree_digest(root, guarded)
        ok, tail = run_capture(cfg, root)
        if dlcore.tree_digest(root, guarded) != before:
            ok, tail = False, "the capture command modified the approved frames, the config, the baseline or a locked path; the approved design is read-only\n" + tail
        if not ok:
            capture_note = f"capture command failed ({cfg['capture']}):\n{tail}"
            print(capture_note, file=sys.stderr)
    report, md_all, failed = {}, [], []
    for name, row in sorted(screens.items()):
        rows = screen_rows(name, row, cfg, root, tol, baseline.get(name, []))
        if capture_note:
            rows.append(_row("(capture)", "command", "exit 0", "failed", "fail", capture_note.splitlines()[0]))
        report[name] = {"summary": summarize(rows), "rows": rows}
        md_all.append(markdown(name, rows, note=f"Frame image: {row.get('image')}. Measured: {row['measured']}.\n\n"))
        if summarize(rows)["fail"]:
            failed.append(name)
    cov = coverage_rows(cfg, root)
    if cov:
        report["(coverage)"] = {"summary": summarize(cov), "rows": cov}
        md_all.append(markdown("(coverage)", cov))
        failed.append("(coverage)")
    for n in sorted(set(baseline) - set(screens)):
        failed.append(n)
        print(f"design-lock gate: the baseline lists {n!r}, which is not a registered screen", file=sys.stderr)
    out = a.out if os.path.isabs(a.out) else os.path.join(root, a.out)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "report.md"), "w").write("\n".join(md_all))
    json.dump({"pass": not failed, "failed": failed, "screens": report}, open(os.path.join(out, "report.json"), "w"), indent=1)
    for name in failed:
        if name in report:
            print(markdown(name, report[name]["rows"], only_fail=True))
    print(f"design gate: {'FAIL' if failed else 'PASS'}: {len(screens) - len([f for f in failed if f in screens])}/{len(screens)} screens match their frames. "
          f"Failing: {', '.join(failed) or 'none'}. Full per-element table: {os.path.join(out, 'report.md')}")
    return 1 if failed else 0


# ---------------------------------------------------------------- extract-web

EXTRACT_JS = r"""
(cfg) => {
  const num = (v) => Math.round(v * 100) / 100;
  const errors = [];
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  // rgb()/rgba() parse directly; anything else (oklch, color(), color-mix, named) goes through the canvas so it lands in sRGB 0-255.
  const rgba = (c) => {
    const m = c.match(/^rgba?\(([^)]*)\)$/);
    if (m) { const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number); if (p.length >= 3 && p.every(isFinite)) return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
    if (c === 'transparent') return [0, 0, 0, 0];
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#010203'; cx.fillStyle = c;
    if (cx.fillStyle === '#010203' && c !== '#010203') { errors.push('unsupported colour syntax: ' + c); return [0, 0, 0, 0]; }
    cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], num(d[3] / 255)];
  };
  const rootEl = cfg.root ? document.querySelector(cfg.root) : null;
  const o = rootEl ? rootEl.getBoundingClientRect() : {left: 0, top: 0, width: innerWidth, height: innerHeight};
  const shown = (el) => { for (let p = el; p && p.nodeType === 1; p = p.parentElement) { const s = getComputedStyle(p);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) < 0.02) return false; } const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const own = (el) => [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim()).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
  const isImg = (el, s) => ['IMG', 'SVG', 'CANVAS', 'VIDEO', 'PICTURE'].includes(el.tagName.toUpperCase()) || s.backgroundImage.includes('url(');
  const flexOf = (v) => (v || '').split(',').map((x) => x.trim()).filter((x) => ['x', 'y', 'w', 'h', 'color', 'fill'].includes(x));
  const SIDES = ['Top', 'Right', 'Bottom', 'Left'];
  const side = (s, d) => (s['border' + d + 'Style'] === 'none' || parseFloat(s['border' + d + 'Width']) === 0) ? null
    : {width: num(parseFloat(s['border' + d + 'Width'])), color: rgba(s['border' + d + 'Color']), style: s['border' + d + 'Style']};
  const describe = (el, id, role, variable, flex) => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    const sd = SIDES.map((d) => side(s, d)), uniform = sd.every((x) => JSON.stringify(x) === JSON.stringify(sd[0]));
    const fill = rgba(s.backgroundColor);
    const style = {
      fill: fill[3] > 0.02 ? fill : null,
      border: sd.every((x) => x === null) ? null : uniform ? sd[0] : {top: sd[0], right: sd[1], bottom: sd[2], left: sd[3]},
      radius: ['TopLeft', 'TopRight', 'BottomRight', 'BottomLeft'].map((c) => num(parseFloat(s['border' + c + 'Radius']) || 0)),
      shadow: s.boxShadow === 'none' ? null : s.boxShadow.replace(/\s+/g, ' '),
      opacity: num(parseFloat(s.opacity)),
      backgroundImage: (s.backgroundImage === 'none' || s.backgroundImage.includes('url(')) ? null : s.backgroundImage,
      filter: s.filter === 'none' ? null : s.filter,
      clipPath: s.clipPath === 'none' ? null : s.clipPath,
      outline: (s.outlineStyle === 'none' || parseFloat(s.outlineWidth) === 0) ? null : s.outlineWidth + ' ' + s.outlineStyle + ' ' + s.outlineColor + ' +' + s.outlineOffset,
      textShadow: s.textShadow === 'none' ? null : s.textShadow.replace(/\s+/g, ' '),
      blendMode: s.mixBlendMode,
      backdropFilter: (s.backdropFilter || 'none') === 'none' ? null : s.backdropFilter,
      objectFit: role === 'image' && s.objectFit !== 'fill' ? s.objectFit + ' ' + s.objectPosition : null,
    };
    if (role === 'text') {
      style.font = {family: s.fontFamily.split(',')[0].replace(/["']/g, '').trim(), size: num(parseFloat(s.fontSize)), weight: parseInt(s.fontWeight),
        letterSpacing: s.letterSpacing === 'normal' ? 0 : num(parseFloat(s.letterSpacing)), lineHeight: s.lineHeight === 'normal' ? null : num(parseFloat(s.lineHeight)),
        style: s.fontStyle, align: s.textAlign, transform: s.textTransform, decoration: s.textDecorationLine,
        variantNumeric: s.fontVariantNumeric, indent: num(parseFloat(s.textIndent) || 0), whiteSpace: s.whiteSpace, overflow: s.textOverflow,
        stroke: parseFloat(s.webkitTextStrokeWidth) > 0 ? s.webkitTextStrokeWidth + ' ' + s.webkitTextStrokeColor : null};
      style.color = rgba(s.color);
      if (!variable) style.text = el.innerText.replace(/\s+/g, ' ').trim();
    }
    const e = {id, role, variable, box: {x: num(r.left - o.left), y: num(r.top - o.top), w: num(r.width), h: num(r.height)}, style};
    if (variable && flex.length) e.flex = flex;
    return e;
  };
  const picked = [];
  const add = (el, id, role, variable, flex) => {
    if (!shown(el)) { errors.push('element ' + id + ' is not visible'); return; }
    const s = getComputedStyle(el);
    role = role || (isImg(el, s) ? 'image' : own(el) ? 'text' : 'container');
    picked.push({el, id, role, rec: describe(el, id, role, variable, flex)});
  };
  for (const m of cfg.elements) {
    const el = document.querySelector(m.selector);
    if (!el) { errors.push('selector of ' + m.id + ' matches nothing: ' + m.selector); continue; }
    add(el, m.id, m.role, !!m.variable, m.flex || []);
  }
  for (const el of document.querySelectorAll('[data-dl-id]')) {
    if (picked.some((p) => p.el === el)) continue;
    const v = el.getAttribute('data-dl-variable');
    add(el, el.getAttribute('data-dl-id'), el.getAttribute('data-dl-role'), v !== null, flexOf(v));
  }
  const ids = picked.map((p) => p.id);
  for (const i of ids) if (ids.indexOf(i) !== ids.lastIndexOf(i)) errors.push('duplicate id ' + i);
  const ignored = (el) => cfg.ignore.some((g) => el.closest(g.selector));
  const covered = (el) => picked.some((p) => p.el === el || (p.rec.role !== 'container' && p.el.contains(el))) || ignored(el);
  const skip = (el) => ['SCRIPT', 'STYLE', 'HEAD', 'META', 'LINK', 'TITLE', 'NOSCRIPT'].includes(el.tagName.toUpperCase()) || (el.closest('svg') && el.tagName.toLowerCase() !== 'svg');
  const paints = (s) => rgba(s.backgroundColor)[3] > 0.02 || s.boxShadow !== 'none' || ['Top', 'Right', 'Bottom', 'Left'].some((d) => s['border' + d + 'Style'] !== 'none' && parseFloat(s['border' + d + 'Width']) > 0);
  const unmapped = [], pathOf = (el) => { const parts = []; for (let p = el; p && p !== document.body; p = p.parentElement) parts.unshift(p.tagName.toLowerCase() + (p.classList.length ? '.' + p.classList[0] : '')); return parts.join('>'); };
  for (const el of (rootEl || document.body).querySelectorAll('*')) {
    if (skip(el) || !shown(el) || ignored(el)) continue;
    const s = getComputedStyle(el);
    for (const pe of ['::before', '::after']) {
      const ps = getComputedStyle(el, pe), c = ps.content;
      if (c !== 'none' && c !== 'normal' && (c !== '""' || paints(ps) || ps.backgroundImage !== 'none')) unmapped.push({path: pathOf(el) + pe, why: 'pseudo-element', text: c.slice(0, 40)});
    }
    // text inside a tagged text element is covered by it, unless it paints or is styled on its own (a bold or tinted <span> would otherwise hide)
    const host = picked.find((p) => p.rec.role === 'text' && p.el !== el && p.el.contains(el));
    if (host && !ignored(el)) {
      const hs = getComputedStyle(host.el);
      const own_ = ['fontSize', 'fontWeight', 'fontFamily', 'color', 'fontStyle', 'letterSpacing', 'textTransform', 'fontVariantNumeric', 'textShadow'].some((k) => s[k] !== hs[k]);
      if (own_ || paints(s) || s.backgroundImage !== 'none') unmapped.push({path: pathOf(el), why: 'styled or painted inside text', text: own(el).slice(0, 40)});
      continue;
    }
    if (covered(el)) continue;
    const why = own(el) ? 'text' : isImg(el, s) ? 'image' : (s.backgroundImage !== 'none') ? 'gradient' : paints(s) ? 'paint' : null;
    if (why) unmapped.push({path: pathOf(el), why, text: own(el).slice(0, 40)});
  }
  return {errors, elements: picked.map((p) => p.rec), unmapped: unmapped.slice(0, 50), width: o.width, height: o.height};
}
"""


def cmd_extract_web(a):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("design-lock extract-web needs Playwright: pip install playwright && playwright install chromium", file=sys.stderr)
        return 2
    cfg = {"elements": [], "ignore": [], "root": a.root}
    if a.map:
        m = json.load(open(a.map))
        cfg.update({k: m[k] for k in ("elements", "ignore", "root") if k in m})
        cfg["root"] = a.root or cfg.get("root")
    if any(not (isinstance(g, dict) and g.get("selector") and str(g.get("reason", "")).strip()) for g in cfg["ignore"]):
        print("design-lock extract-web: every `ignore` entry must be {\"selector\": ..., \"reason\": ...}; ignoring a region needs a stated reason", file=sys.stderr)
        return 2
    w, h = (int(x) for x in a.viewport.lower().split("x"))
    url = a.url or "file://" + os.path.abspath(a.file)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": w, "height": h}, color_scheme=a.theme, device_scale_factor=1).new_page()
        pg.goto(url)
        pg.evaluate("document.fonts.ready.then(() => 0)")
        data = pg.evaluate(EXTRACT_JS, cfg)
        if a.screenshot:
            pg.screenshot(path=a.screenshot)
        version = b.version
        b.close()
    if data["errors"]:
        print("design-lock extract-web: " + "; ".join(data["errors"]), file=sys.stderr)
        return 2
    out = {"schema": SCHEMA, "kind": a.kind, "frame": a.name or os.path.basename(url), "theme": a.theme, "renderer": {"browser": version.split(".")[0], "platform": sys.platform},
           "viewport": {"width": data["width"], "height": data["height"]}, "unmapped": data["unmapped"], "ignored": cfg["ignore"], "elements": data["elements"]}
    if a.kind == "spec" and validate_spec(out):
        print("design-lock extract-web: this frame spec cannot pin the design:\n  " + "\n  ".join(validate_spec(out)), file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"design-lock extract-web: {len(out['elements'])} elements, {len(out['unmapped'])} unmapped -> {a.out}")
    return 0


# ---------------------------------------------------------------- init

PLATFORMS = {  # platform: (screen mode, capture recipe, ui globs, commands that re-record goldens). `ui` is also the trigger and cache key of the Stop hook:
    # it must cover EVERYTHING that changes rendering (styles, theme files, tailwind/gradle config, assets), or a change there never runs the gate.
    "web": ("structure", "capture-web.sh", ["src/**", "app/**", "public/**", "*.config.js", "*.config.ts", "package.json"], ["--update-snapshots", "updateSnapshots", r"jest .*-u\b", "vitest .*-u\b"]),
    "android": ("pixel", "capture-android.sh", ["**/src/main/**", "**/*.gradle", "**/*.gradle.kts"], ["recordRoborazzi", "recordPaparazzi", "updateDebugAndroidTestScreenshot", "recordScreenshotTest"]),
    "ios": ("pixel", "capture-ios.sh", ["**/*.swift", "**/*.storyboard", "**/*.xib", "**/*.xcassets/**"], ["record\\s*=\\s*true", "RECORD_SNAPSHOTS", "isRecording"]),
    "flutter": ("pixel", "capture-flutter.sh", ["lib/**", "assets/**", "pubspec.yaml"], ["--update-goldens"]),
    "desktop": ("pixel", "capture-command.sh", ["src/**"], ["record_golden", "update_golden"]),
    "command": ("pixel", "capture-command.sh", ["src/**"], ["record_golden", "update_golden"]),
}


def cmd_init(a):
    mode, recipe, ui, forbid = PLATFORMS[a.platform]
    d, tpl = os.path.abspath(a.dir), os.path.join(os.path.dirname(HERE), "templates")
    files = {".design-lock.json": None, "design/baseline.json": "{}\n", "design/changes.json": "[]\n", "tools/design-lock/capture.sh": ("copy", recipe),
             ".github/workflows/design-lock.yml": ("copy", "design-lock.yml")}
    files.update({f"tools/design-lock/{f}": ("copy-script", f) for f in ("designlock.py", "dlcore.py", "guard.py")})
    taken = [f for f in files if os.path.exists(os.path.join(d, f))]
    if taken:
        print(f"design-lock init: refusing to overwrite {', '.join(taken)}", file=sys.stderr)
        return 2
    s = a.screen
    ext = "json" if mode == "structure" else "png"
    cfg = {"version": 1, "platform": a.platform, "ui": ui, "capture": "sh tools/design-lock/capture.sh", "gateTimeoutSec": 600,
           "locked": ["tools/design-lock/**", ".github/workflows/design-lock.yml"], "goldens": ["**/__snapshots__/**", "**/screenshots/**", "**/*.golden.png"], "forbidCommands": forbid,
           "screens": {s: {"frame": f"design/frames/{s}.spec.json", "image": f"design/frames/{s}.png", "measured": f"build/design-lock/measured/{s}.{ext}",
                           "mode": mode, "exceptions": [], "sources": []}}}
    for f, v in files.items():
        p = os.path.join(d, f)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if f == ".design-lock.json":
            json.dump(cfg, open(p, "w"), indent=2)
            open(p, "a").write("\n")
        elif isinstance(v, str):
            open(p, "w").write(v)
        elif v[0] == "copy-script":
            shutil.copy(os.path.join(HERE, v[1]), p)
        else:
            shutil.copy(os.path.join(tpl, v[1]), p)
    os.makedirs(os.path.join(d, "design/frames"), exist_ok=True)
    if subprocess.run(["git", "-C", d, "check-ignore", "-q", ".design-lock.json"], capture_output=True).returncode == 0:
        print("design-lock init: WARNING a gitignore (maybe a global `.*` rule) hides .design-lock.json; commit it with `git add -f .design-lock.json`")
    print(f"design-lock init ({a.platform}): wrote {len(files)} files, among them .design-lock.json (dotfile: `ls -a`, `git add -f`). The local hooks are advisory; "
          f"the protection is the required CI check `design-ok` (branch protection or a ruleset), so the repo is not protected until that is set. Next, put the approved frame image and spec for screen {s!r} in design/frames/, "
          f"edit tools/design-lock/capture.sh, run `python3 tools/design-lock/designlock.py gate`, then commit and make `design-ok` a required check.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="designlock", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare", help="compare a frame spec with a measured app file")
    c.add_argument("frame")
    c.add_argument("app")
    c.add_argument("--tolerance", help="box px as a number, 'box=1,fontSize=0.1,...', or a JSON file; keys: " + ", ".join(DEFAULT_TOL))
    c.add_argument("--allow-extra", action="store_true", help="do not fail on app elements the frame does not list")
    c.add_argument("--only-fail", action="store_true")
    c.add_argument("--md", help="write the Markdown table here")
    c.add_argument("--json", help="write the JSON result here")
    c.set_defaults(fn=cmd_compare)
    g = sub.add_parser("gate", help="run the capture command, then compare every screen of .design-lock.json")
    g.add_argument("--root", default=".", help="the project root holding .design-lock.json")
    g.add_argument("--out", default="build/design-lock", help="report directory (relative to --root)")
    g.add_argument("--no-capture", action="store_true", help="compare the measured files already on disk")
    g.set_defaults(fn=cmd_gate)
    e = sub.add_parser("extract-web", help="render an HTML page or URL with Playwright into a spec or measured file")
    src = e.add_mutually_exclusive_group(required=True)
    src.add_argument("--file")
    src.add_argument("--url")
    e.add_argument("--out", required=True)
    e.add_argument("--kind", choices=["spec", "measured"], default="measured")
    e.add_argument("--map", help="JSON {elements:[{id,selector,role?,variable?,flex?}], ignore:[{selector,reason}], root?}; pages tagged with data-dl-id need none")
    e.add_argument("--root", help="selector of the frame; box coordinates are relative to it (default: the page)")
    e.add_argument("--viewport", default="390x844")
    e.add_argument("--theme", choices=["light", "dark"], default="light")
    e.add_argument("--name", help="frame id recorded in the file")
    e.add_argument("--screenshot")
    e.set_defaults(fn=cmd_extract_web)
    i = sub.add_parser("init", help="scaffold design-lock in a new project")
    i.add_argument("--platform", choices=sorted(PLATFORMS), required=True)
    i.add_argument("--dir", default=".")
    i.add_argument("--screen", default="home", help="name of the first screen")
    i.set_defaults(fn=cmd_init)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
