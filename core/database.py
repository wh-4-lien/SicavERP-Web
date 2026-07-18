# core/database.py
from supabase import create_client, Client
import threading as _threading
import time as _time
import datetime as _dt
from core.config import URL_NUBE, KEY_NUBE

# Cliente global (usado desde el hilo principal)
supabase: Client = create_client(URL_NUBE, KEY_NUBE)

# ── Cliente por hilo (evita WinError 10035 con HTTP/2 concurrente) ────────────
_local = _threading.local()

def get_sb():
    """Devuelve un cliente Supabase exclusivo para el hilo actual."""
    if not hasattr(_local, "client"):
        _local.client = create_client(URL_NUBE, KEY_NUBE)
    return _local.client

# ── Caché en memoria ──────────────────────────────────────────────────────────
_CACHE: dict = {}
_CACHE_TTL = 300  # segundos

def cache_get(key: str):
    entry = _CACHE.get(key)
    if entry and (_time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None

def cache_set(key: str, data):
    _CACHE[key] = {"data": data, "ts": _time.time()}

def cache_invalidate(*keys):
    """
    Invalida caché específica o toda la caché si no se envían parámetros.
    También limpia los campos relevantes de app_cache para que las vistas re-fetchen.
    """
    from core.cache import app_cache
    if not keys:
        _CACHE.clear()
        app_cache.inv_ready.clear()
        app_cache.inv_productos = None
        app_cache.fin_ready.clear()
        app_cache.fin_productos_raw = None
        app_cache.gra_ready.clear()
        app_cache.gra_productos = None
        return
    for k in keys:
        _CACHE.pop(k, None)
    if "furgones_totales" in keys:
        app_cache.gfur_ready.clear()
        app_cache.gfur_furgones = None
        app_cache.gfur_fp_counts = {}

_PAGE_SIZE = 1000  # límite real de Supabase por petición

def fetch_all(tabla: str, cols: str, **filtros) -> list:
    """Pagina automáticamente hasta traer TODOS los registros. Supabase devuelve máximo 1000 por petición."""
    todos = []
    offset = 0
    sb = get_sb()
    while True:
        q = sb.table(tabla).select(cols).range(offset, offset + _PAGE_SIZE - 1)
        for campo, valor in filtros.items():
            q = q.eq(campo, valor)
        pagina = q.execute().data or []
        todos.extend(pagina)
        if len(pagina) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return todos

def fetch_productos(cols="sku, nombre, costo_neto, precio_venta, stock_global, creado_en, familias(nombre), subfamilias(nombre)"):
    cached = cache_get(f"productos:{cols}")
    if cached is not None:
        return cached
    data = fetch_all("productos", cols)
    
    # Aplanar el diccionario para que las vistas viejas sigan funcionando sin romperse tanto
    for d in data:
        if d.get("familias"):
            d["familia"] = d["familias"].get("nombre")
        else:
            d["familia"] = None
            
        if d.get("subfamilias"):
            d["subfamilia"] = d["subfamilias"].get("nombre")
        else:
            d["subfamilia"] = None
            
        # Renombrar stock_global a stock_actual temporalmente para compatibilidad
        if "stock_global" in d:
            d["stock_actual"] = d["stock_global"]
            
    cache_set(f"productos:{cols}", data)
    return data

def fetch_todos_furgones():
    """Devuelve todos los furgones existentes."""
    return get_sb().table("furgones").select("*").order("nombre").execute().data or []

def fetch_herramientas_furgo(furgon_id):
    """Devuelve las herramientas asignadas a un furgón específico."""
    res = get_sb().table("herramientas_furgo").select("*").eq("furgon_id", furgon_id).order("descripcion").execute()
    return res.data or []

def fetch_furgones_con_totales():
    cached = cache_get("furgones_totales")
    if cached is not None:
        return cached
    furgones = get_sb().table("furgones").select("id, nombre, descripcion, tecnico_usuario").execute().data or []
    
    fps = fetch_all("furgon_productos", "furgon_id, cantidad")
    
    totales: dict = {}
    for fp in fps:
        fid = fp["furgon_id"]
        totales[fid] = totales.get(fid, 0) + (fp.get("cantidad") or 0)
    for fg in furgones:
        fg["_total_uds"] = totales.get(fg["id"], 0)
    cache_set("furgones_totales", furgones)
    return furgones

# ── Funciones Multi-Bodega ────────────────────────────────────────────────────
def ejecutar_traspaso(sku: str, origen_id: int, destino_id: int, cantidad: int, usuario_login: str, usuario_nombre: str = ""):
    """
    Mueve stock entre dos bodegas de forma segura y actualiza el consolidado global.
    usuario_login: valor del campo 'usuario' en la tabla usuarios (FK).
    usuario_nombre: nombre legible para auditoría.
    """
    from core.utilidades import registrar_auditoria

    if cantidad <= 0:
        raise ValueError("La cantidad a traspasar debe ser mayor que cero.")
    if origen_id == destino_id:
        raise ValueError("La bodega de origen y destino no pueden ser iguales.")

    # 1. Comprobar disponibilidad en Origen
    res_origen = get_sb().table("bodega_productos").select("cantidad").eq("bodega_id", origen_id).eq("sku", sku).execute()
    if not res_origen.data or (res_origen.data[0]["cantidad"] or 0) < cantidad:
        raise ValueError("Stock insuficiente en la bodega de origen para este SKU.")

    stock_origen_actual = res_origen.data[0]["cantidad"] or 0

    # 2. Descontar de la bodega origen
    get_sb().table("bodega_productos").update({"cantidad": stock_origen_actual - cantidad}).eq("bodega_id", origen_id).eq("sku", sku).execute()

    # 3. Incrementar o insertar en la bodega destino
    res_destino = get_sb().table("bodega_productos").select("cantidad").eq("bodega_id", destino_id).eq("sku", sku).execute()
    if res_destino.data:
        stock_destino_actual = res_destino.data[0]["cantidad"] or 0
        get_sb().table("bodega_productos").update({"cantidad": stock_destino_actual + cantidad}).eq("bodega_id", destino_id).eq("sku", sku).execute()
    else:
        get_sb().table("bodega_productos").insert({"bodega_id": destino_id, "sku": sku, "cantidad": cantidad}).execute()

    # 4. Sincronizar columna consolidada
    res_totales = get_sb().table("bodega_productos").select("cantidad").eq("sku", sku).execute()
    total_consolidado = sum(r.get("cantidad", 0) for r in (res_totales.data or []))
    get_sb().table("productos").update({"stock_global": total_consolidado}).eq("sku", sku).execute()

    # 5. Registrar en nueva tabla de movimientos
    get_sb().table("movimientos_inventario").insert({
        "sku": sku,
        "tipo_movimiento": "TRASPASO_INTERNO",
        "ubicacion_origen": f"BODEGA_{origen_id}",
        "ubicacion_destino": f"BODEGA_{destino_id}",
        "cantidad": cantidad,
        "usuario": usuario_login,
        "comentario": "Traspaso estándar",
        "fecha": _dt.datetime.utcnow().isoformat()
    }).execute()

    registrar_auditoria(usuario_nombre, "TRASPASO DE STOCK", f"SKU: {sku} | -{cantidad} B{origen_id} -> +{cantidad} B{destino_id}")

    cache_invalidate()
    return True

# ── Funciones Perfil Técnico (Despachos y Furgón) ───────────────────────────
def fetch_tipos_trabajo():
    """Descarga el catálogo de tipos de trabajo desde Supabase."""
    res = get_sb().table("tipos_trabajo").select("*").order("nombre").execute()
    return res.data or []

def registrar_despacho_tecnico(sku, bodega_id, cantidad, tipo_trabajo_id, comentario, usuario_login, usuario_nombre=""):
    """Descuenta stock de una bodega para un trabajo y exige un comentario.
    usuario_login: campo 'usuario' en tabla usuarios (FK).
    usuario_nombre: nombre legible para auditoría.
    """
    from core.utilidades import registrar_auditoria

    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    res_origen = get_sb().table("bodega_productos").select("cantidad").eq("bodega_id", bodega_id).eq("sku", sku).execute()
    if not res_origen.data or (res_origen.data[0]["cantidad"] or 0) < cantidad:
        raise ValueError("Stock insuficiente en la bodega seleccionada.")

    stock_actual = res_origen.data[0]["cantidad"] or 0
    get_sb().table("bodega_productos").update({"cantidad": stock_actual - cantidad}).eq("bodega_id", bodega_id).eq("sku", sku).execute()

    res_costo = get_sb().table("productos").select("costo_neto").eq("sku", sku).execute()
    costo_unit = (res_costo.data[0]["costo_neto"] or 0) if res_costo.data else 0

    get_sb().table("movimientos_inventario").insert({
        "sku": sku,
        "tipo_movimiento": "DESPACHO_TECNICO",
        "ubicacion_origen": f"BODEGA_{bodega_id}",
        "ubicacion_destino": "CLIENTE/TERRENO",
        "cantidad": cantidad,
        "costo_unitario_historico": costo_unit,
        "tipo_trabajo_id": tipo_trabajo_id,
        "comentario": comentario,
        "usuario": usuario_login,
        "fecha": _dt.datetime.utcnow().isoformat()
    }).execute()

    res_totales = get_sb().table("bodega_productos").select("cantidad").eq("sku", sku).execute()
    total_consolidado = sum(r.get("cantidad", 0) for r in (res_totales.data or []))
    get_sb().table("productos").update({"stock_global": total_consolidado}).eq("sku", sku).execute()

    registrar_auditoria(usuario_nombre or usuario_login, "DESPACHO TÉCNICO", f"SKU: {sku} | -{cantidad} | Trabajo ID: {tipo_trabajo_id}")
    cache_invalidate()
    return True

def registrar_despacho_desde_furgon(sku, furgon_id, cantidad, tipo_trabajo_id, comentario, usuario_login, usuario_nombre=""):
    """Descuenta stock directamente del furgón (furgon_productos) para un trabajo."""
    from core.utilidades import registrar_auditoria

    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    res = get_sb().table("furgon_productos").select("cantidad").eq("furgon_id", furgon_id).eq("sku", sku).execute()
    if not res.data or (res.data[0]["cantidad"] or 0) < cantidad:
        raise ValueError("Stock insuficiente en el furgón.")

    stock_actual = res.data[0]["cantidad"] or 0
    get_sb().table("furgon_productos").update({"cantidad": stock_actual - cantidad}).eq("furgon_id", furgon_id).eq("sku", sku).execute()

    res_costo = get_sb().table("productos").select("costo_neto").eq("sku", sku).execute()
    costo_unit = (res_costo.data[0]["costo_neto"] or 0) if res_costo.data else 0

    get_sb().table("movimientos_inventario").insert({
        "sku": sku,
        "tipo_movimiento": "DESPACHO_TECNICO",
        "ubicacion_origen": f"FURGON_{furgon_id}",
        "ubicacion_destino": "CLIENTE/TERRENO",
        "cantidad": cantidad,
        "costo_unitario_historico": costo_unit,
        "tipo_trabajo_id": tipo_trabajo_id,
        "comentario": comentario,
        "usuario": usuario_login,
        "fecha": _dt.datetime.utcnow().isoformat()
    }).execute()

    registrar_auditoria(usuario_nombre or usuario_login, "DESPACHO TÉCNICO FURGÓN", f"SKU: {sku} | -{cantidad} | Furgón ID: {furgon_id}")
    cache_invalidate()
    return True

def cargar_stock_furgon(sku, bodega_id, furgon_id, cantidad, usuario_login, usuario_nombre=""):
    """Mueve stock desde una bodega central hacia el furgón del técnico.
    usuario_login: campo 'usuario' en tabla usuarios (FK).
    usuario_nombre: nombre legible para auditoría.
    """
    from core.utilidades import registrar_auditoria

    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    res_origen = get_sb().table("bodega_productos").select("cantidad").eq("bodega_id", bodega_id).eq("sku", sku).execute()
    if not res_origen.data or (res_origen.data[0]["cantidad"] or 0) < cantidad:
        raise ValueError("Stock insuficiente en la bodega seleccionada.")

    stock_actual = res_origen.data[0]["cantidad"] or 0
    get_sb().table("bodega_productos").update({"cantidad": stock_actual - cantidad}).eq("bodega_id", bodega_id).eq("sku", sku).execute()

    res_furgon = get_sb().table("furgon_productos").select("cantidad").eq("furgon_id", furgon_id).eq("sku", sku).execute()
    if res_furgon.data:
        nuevo_stock = (res_furgon.data[0]["cantidad"] or 0) + cantidad
        get_sb().table("furgon_productos").update({"cantidad": nuevo_stock}).eq("furgon_id", furgon_id).eq("sku", sku).execute()
    else:
        get_sb().table("furgon_productos").insert({"furgon_id": furgon_id, "sku": sku, "cantidad": cantidad}).execute()

    res_costo = get_sb().table("productos").select("costo_neto").eq("sku", sku).execute()
    costo_unit = (res_costo.data[0]["costo_neto"] or 0) if res_costo.data else 0

    get_sb().table("movimientos_inventario").insert({
        "sku": sku,
        "tipo_movimiento": "CARGA_FURGON",
        "ubicacion_origen": f"BODEGA_{bodega_id}",
        "ubicacion_destino": f"FURGON_{furgon_id}",
        "cantidad": cantidad,
        "costo_unitario_historico": costo_unit,
        "usuario": usuario_login,
        "comentario": "Carga de stock a furgón",
        "fecha": _dt.datetime.utcnow().isoformat()
    }).execute()

    res_totales = get_sb().table("bodega_productos").select("cantidad").eq("sku", sku).execute()
    total_consolidado = sum(r.get("cantidad", 0) for r in (res_totales.data or []))
    get_sb().table("productos").update({"stock_global": total_consolidado}).eq("sku", sku).execute()

    registrar_auditoria(usuario_nombre or usuario_login, "CARGA FURGÓN", f"SKU: {sku} | +{cantidad} -> Furgón: {furgon_id}")
    cache_invalidate()
    return True

def registrar_herramienta_furgon(furgon_id, descripcion, cantidad, usuario):
    """Añade herramientas nuevas al furgón."""
    from core.utilidades import registrar_auditoria
    for _ in range(cantidad):
        get_sb().table("herramientas_furgo").insert({
            "furgon_id": furgon_id,
            "descripcion": descripcion
        }).execute()
    registrar_auditoria(usuario, "HERRAMIENTA", f"+{cantidad} {descripcion} -> Furgón: {furgon_id}")
    return True
