# core/utilidades.py
import flet as ft
import os
import threading
import datetime as _dt
import dataclasses
from core.database import get_sb

DIRECTORIO_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_ASSETS = os.path.join(DIRECTORIO_BASE, "assets")

def obtener_ruta_imagen(nombre_archivo):
    if not nombre_archivo: return ""
    nombre_limpio = nombre_archivo.replace("assets/", "").replace("assets\\", "")
    return os.path.join(CARPETA_ASSETS, nombre_limpio)

def snack(page, mensaje: str, color: str = "green700"):
    """Legacy wrapper — delega a utils.ui_helpers.mostrar_snack."""
    from utils.ui_helpers import mostrar_snack as _snack
    _snack(page, mensaje, color)

def hilo(fn):
    threading.Thread(target=fn, daemon=True).start()

def init_prev_lists(control, _visited=None):
    """
    Seeds Flet's __prev_lists snapshots for structural list fields so that subsequent
    background-thread update() calls produce non-empty patches. Call this after
    page.update() registers new controls and before starting background data loads.
    """
    if _visited is None:
        _visited = set()
    cid = id(control)
    if cid in _visited or not dataclasses.is_dataclass(control):
        return
    _visited.add(cid)

    prev = getattr(control, "__prev_lists", None)
    if prev is None:
        object.__setattr__(control, "__prev_lists", {})
        prev = getattr(control, "__prev_lists")

    for f in dataclasses.fields(control):
        if f.metadata.get("skip", False):
            continue
        try:
            val = getattr(control, f.name, None)
        except Exception:
            continue
        if isinstance(val, list):
            if f.name not in prev:
                prev[f.name] = val[:]
            for item in val:
                init_prev_lists(item, _visited)
        elif dataclasses.is_dataclass(val):
            init_prev_lists(val, _visited)

def abrir_dialogo(page_ref, dlg):
    page_ref.show_dialog(dlg)

def cerrar_dialogo(page_ref, dlg):
    page_ref.pop_dialog()

def mostrar_dialogo_resultado(page_ref, mensaje: str, color: str = "green700"):
    """Legacy wrapper — ahora usa mostrar_snack centralizado (SnackBar flotante)."""
    from utils.ui_helpers import mostrar_snack as _snack
    _snack(page_ref, mensaje, color)

def registrar_auditoria(usuario, accion, detalle=""):
    print(f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {accion} | usuario={usuario} | {detalle}")
    def _run():
        try:
            get_sb().table("auditoria").insert({
                "usuario": usuario,
                "accion": accion,
                "detalle": detalle,
                "fecha": _dt.datetime.utcnow().isoformat()
            }).execute()
        except Exception as ex:
            print(f"[AUDITORIA ERROR] {ex}")
    threading.Thread(target=_run, daemon=True).start()