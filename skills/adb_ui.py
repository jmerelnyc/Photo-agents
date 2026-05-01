# adb_ui.py - one-shot dump + parse of an Android UI tree (uiautomator2 first, native fallback).
# uiautomator2 is not bound by the idle requirement, which makes it usable for animation-heavy apps.
# Popup detection: ui(clickable_only=True, raw=True) finds a fullscreen FrameLayout plus a small
# bottom ImageView (the close X).
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ADB = shutil.which("adb") or "adb"
LOCAL_XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_mt.xml")


def _dump_u2():
    """Dump via uiautomator2; not affected by the idle requirement."""
    try:
        import uiautomator2 as u2
        d = u2.connect()
        xml_str = d.dump_hierarchy()
        if xml_str and len(xml_str) > 100:
            return xml_str
    except Exception as e:
        print(f"[u2 fallback] {e}")
    return None


def _dump_native():
    """Native uiautomator dump (requires the device to be idle)."""
    subprocess.run([ADB, "shell", "rm", "-f", "/sdcard/ui.xml"], capture_output=True)
    r = subprocess.run([ADB, "shell", "uiautomator", "dump", "--compressed", "/sdcard/ui.xml"],
                       capture_output=True, text=True, timeout=15)
    if "dumped" not in r.stdout.lower() and "dumped" not in r.stderr.lower():
        print(f"dump failed: {r.stdout}{r.stderr}")
        return None
    subprocess.run([ADB, "pull", "/sdcard/ui.xml", LOCAL_XML], capture_output=True, timeout=10)
    with open(LOCAL_XML, "r", encoding="utf-8") as f:
        return f.read()


def _parse_xml(xml_str, keyword=None, clickable_only=False, raw=False):
    """Parse an XML string into a list of node dicts."""
    root = ET.fromstring(xml_str)
    nodes = []
    for n in root.iter("node"):
        pkg = n.get("package", "")
        if "termux" in pkg.lower():
            continue
        text = n.get("text", "")
        desc = n.get("content-desc", "")
        bounds = n.get("bounds", "")
        click = n.get("clickable") == "true"
        cls = n.get("class", "").split(".")[-1]
        rid = n.get("resource-id", "")
        label = text or desc
        if not label and not click and not raw:
            continue
        if clickable_only and not click:
            continue
        if keyword and keyword.lower() not in label.lower():
            continue
        cx, cy = 0, 0
        if bounds:
            m = re.findall(r'\[(\d+),(\d+)\]', bounds)
            if len(m) == 2:
                cx = (int(m[0][0]) + int(m[1][0])) // 2
                cy = (int(m[0][1]) + int(m[1][1])) // 2
        edit = cls == "EditText"
        nodes.append({"text": text or desc, "click": click, "edit": edit,
                      "cx": cx, "cy": cy, "cls": cls, "rid": rid})
    return nodes


def ui(keyword=None, clickable_only=False, raw=False):
    """One-shot dump + parse of an Android UI tree (uiautomator2 first).

    keyword: only return nodes containing this keyword.
    clickable_only: only return clickable nodes.
    raw: return the raw node list instead of pretty-printing.
    """
    xml_str = _dump_u2() or _dump_native()
    if not xml_str:
        print("dump failed (both u2 and native)")
        return []
    nodes = _parse_xml(xml_str, keyword, clickable_only, raw)
    if not raw:
        for n in nodes:
            flag = "E" if n.get("edit") else ("Y" if n["click"] else " ")
            coord = f"({n['cx']},{n['cy']})" if n['cx'] else ""
            display_text = n['text']
            if not display_text:
                hint = n.get('rid', '').split('/')[-1] or n.get('cls', 'icon')
                display_text = f"<{hint}>"
            print(f"[{flag}] {display_text}  {coord}")
        print(f"\ntotal: {len(nodes)} nodes")
    return nodes


def tap(x, y):
    subprocess.run([ADB, "shell", "input", "tap", str(x), str(y)], capture_output=True)
    print(f"tap({x},{y}) ok")


if __name__ == "__main__":
    ui()
