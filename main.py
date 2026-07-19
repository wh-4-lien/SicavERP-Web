# main.py
import sys, io
if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import warnings
warnings.simplefilter("ignore", category=DeprecationWarning)

import flet as ft
import os
from core.estado import estado
from core.utilidades import obtener_ruta_imagen, init_prev_lists
from core.updater import verificar_actualizacion
from core.cache import app_cache

# --- IMPORTACIÓN DE TODAS LAS VISTAS ---
from vistas.login import VistaLogin
from vistas.inventario import VistaInventario
from vistas.gestion_comercial import VistaComercial
from vistas.categorias import VistaCategorias
from vistas.dashboard import VistaDashboard
from vistas.furgones import VistaFurgones
from vistas.usuarios import VistaUsuarios
from vistas.gestion_furgones import VistaGestionFurgones
from vistas.mi_furgon import VistaMiFurgon
from vistas.auditoria import VistaAuditoria
from vistas.finanzas import VistaFinanzas
from vistas.graficos import VistaGraficos
from vistas.movimientos import VistaMovimientos
from vistas.gestion_permisos import VistaGestionPermisos
from vistas.importar import VistaImportar

def precargar_vistas(on_complete=None):
    """
    Lanza hilos en paralelo inmediatamente tras el login para pre-poblar
    app_cache antes de que el usuario navegue a cada vista.
    """
    import threading
    from core.database import get_sb, fetch_all

    _TOTAL_HILOS = 10
    _completados = [0]
    _lock = threading.Lock()

    def _check_done():
        with _lock:
            _completados[0] += 1
            if _completados[0] >= _TOTAL_HILOS and on_complete:
                on_complete()

    # ── Inventario ──────────────────────────────────────────────────────
    def _pre_inv():
        try:
            sb = get_sb()
            app_cache.inv_bodegas = sb.table("bodegas").select("id, nombre, areas(nombre)").execute().data or []
            fams = sb.table("familias").select("id, nombre").order("nombre").execute().data or []
            subs = sb.table("subfamilias").select("nombre, familia_id").execute().data or []
            arbol: dict = {f["nombre"]: [] for f in fams}
            fam_id_map = {f["id"]: f["nombre"] for f in fams}
            for s in subs:
                fn = fam_id_map.get(s["familia_id"])
                if fn in arbol:
                    arbol[fn].append(s["nombre"])
            app_cache.inv_arbol_data = arbol
            raw = fetch_all(
                "productos",
                "sku, nombre, costo_neto, precio_venta, stock_global, "
                "familia_id, subfamilia_id, familias(nombre), subfamilias(nombre)",
            )
            prods = []
            for p in raw:
                fam_obj = p.get("familias") or {}
                sub_obj = p.get("subfamilias") or {}
                prods.append({
                    "sku":           p.get("sku", ""),
                    "nombre":        p.get("nombre", ""),
                    "familia":       fam_obj.get("nombre") if isinstance(fam_obj, dict) else "",
                    "subfamilia":    sub_obj.get("nombre") if isinstance(sub_obj, dict) else "",
                    "familia_id":    p.get("familia_id"),
                    "subfamilia_id": p.get("subfamilia_id"),
                    "stock_actual":  p.get("stock_global", 0) or 0,
                    "costo_neto":    p.get("costo_neto", 0) or 0,
                    "precio_venta":  p.get("precio_venta", 0) or 0,
                })
            app_cache.inv_productos = prods
            bp_raw = sb.table("bodega_productos") \
                .select("sku, cantidad, bodegas(nombre, areas(nombre))").execute().data or []
            sku_bod_map: dict = {}
            for r in bp_raw:
                if (r.get("cantidad") or 0) <= 0:
                    continue
                sku = r["sku"]
                bod = r.get("bodegas") or {}
                area = (bod.get("areas") or {}).get("nombre") or ""
                sku_bod_map.setdefault(sku, []).append(
                    {"bodega": bod.get("nombre") or "", "area": area}
                )
            app_cache.inv_sku_bodegas_map = sku_bod_map
        except Exception as ex:
            print(f"[CACHE] Inventario ERROR: {ex}")
            app_cache.inv_productos = app_cache.inv_productos or []
            app_cache.inv_sku_bodegas_map = app_cache.inv_sku_bodegas_map or {}
        else:
            n = len(app_cache.inv_productos or [])
            print(f"[CACHE] Inventario listo — {n} productos")
        finally:
            app_cache.inv_ready.set()
            _check_done()

    # ── Movimientos ─────────────────────────────────────────────────────
    def _pre_mov():
        try:
            sb = get_sb()
            app_cache.mov_bodegas = sb.table("bodegas").select("id, nombre, areas(nombre)").order("id").execute().data or []
            app_cache.mov_historial = (
                sb.table("movimientos_inventario").select("*")
                .eq("tipo_movimiento", "TRASPASO_INTERNO")
                .order("fecha", desc=True).limit(30).execute().data or []
            )
        except Exception as ex:
            print(f"[CACHE] Movimientos ERROR: {ex}")
            app_cache.mov_historial = app_cache.mov_historial or []
        else:
            n = len(app_cache.mov_historial or [])
            print(f"[CACHE] Movimientos listo — {n} traspasos")
        finally:
            app_cache.mov_ready.set()
            _check_done()

    # ── Finanzas ────────────────────────────────────────────────────────
    def _pre_fin():
        try:
            from datetime import datetime as _dt
            sb = get_sb()
            app_cache.fin_bodegas  = sb.table("bodegas").select("id, nombre, areas(nombre)").order("id").execute().data or []
            app_cache.fin_furgones = sb.table("furgones").select("id, nombre").order("nombre").execute().data or []
            app_cache.fin_productos_raw = fetch_all(
                "productos",
                "sku, nombre, costo_neto, precio_venta, stock_global, "
                "familia_id, subfamilia_id, familias(nombre), subfamilias(nombre)",
            )
            now = _dt.now()
            mes = str(now.month).zfill(2)
            anio = str(now.year)
            m_next = now.month + 1
            y_next = now.year + (1 if m_next > 12 else 0)
            m_next = m_next if m_next <= 12 else 1
            movs = (
                sb.table("movimientos_inventario").select("*")
                .gte("fecha", f"{anio}-{mes}-01T00:00:00")
                .lt("fecha", f"{y_next}-{str(m_next).zfill(2)}-01T00:00:00")
                .execute().data or []
            )
            skus = {m["sku"] for m in movs if m.get("sku")}
            costo_map: dict = {}
            if skus:
                res_p = sb.table("productos").select("sku, costo_neto").in_("sku", list(skus)).execute().data or []
                costo_map = {r["sku"]: (r.get("costo_neto") or 0) for r in res_p}
            app_cache.fin_historial_movs = movs
            app_cache.fin_historial_costo_map = costo_map
            app_cache.fin_bp_raw = fetch_all(
                "bodega_productos", "sku, cantidad, bodegas(nombre, areas(nombre))"
            )
        except Exception as ex:
            print(f"[CACHE] Finanzas ERROR: {ex}")
            app_cache.fin_historial_movs = app_cache.fin_historial_movs or []
            app_cache.fin_bp_raw = app_cache.fin_bp_raw or []
            app_cache.fin_historial_costo_map = app_cache.fin_historial_costo_map or {}
        else:
            n = len(app_cache.fin_productos_raw or [])
            m = len(app_cache.fin_historial_movs or [])
            bp = len(app_cache.fin_bp_raw or [])
            print(f"[CACHE] Finanzas listo — {n} productos, {m} movimientos del mes, {bp} registros bodega")
        finally:
            app_cache.fin_ready.set()
            _check_done()

    # ── Dashboard ───────────────────────────────────────────────────────
    def _pre_dash():
        try:
            sb = get_sb()
            app_cache.dash_auditoria_reciente = (
                sb.table("auditoria").select("usuario, accion, fecha")
                .order("fecha", desc=True).limit(10).execute().data or []
            )
            app_cache.dash_auditoria_top500 = (
                sb.table("auditoria").select("usuario")
                .order("fecha", desc=True).limit(500).execute().data or []
            )
        except Exception as ex:
            print(f"[CACHE] Dashboard ERROR: {ex}")
            app_cache.dash_auditoria_reciente = app_cache.dash_auditoria_reciente or []
            app_cache.dash_auditoria_top500 = app_cache.dash_auditoria_top500 or []
        else:
            print(f"[CACHE] Dashboard listo — {len(app_cache.dash_auditoria_reciente)} actividad, {len(app_cache.dash_auditoria_top500)} para ranking")
        finally:
            app_cache.dash_ready.set()
            _check_done()

    # ── Categorías ──────────────────────────────────────────────────────
    def _pre_cat():
        try:
            sb = get_sb()
            res_f = sb.table("familias").select("id, nombre").order("nombre").execute()
            fams_raw = res_f.data or []
            app_cache.cat_familias = [f["nombre"] for f in fams_raw]
            fam_id_map = {f["id"]: f["nombre"] for f in fams_raw}
            # subfamilias usa familia_id (FK), construimos familia_nombre por compatibilidad
            res_s = sb.table("subfamilias").select("nombre, familia_id").order("nombre").execute()
            app_cache.cat_subfamilias = [
                {"nombre": s["nombre"], "familia_nombre": fam_id_map.get(s["familia_id"], "")}
                for s in (res_s.data or [])
            ]
            res_t = sb.table("tipos_trabajo").select("id, nombre").order("nombre").execute()
            app_cache.cat_tipos = res_t.data or []
            res_a = sb.table("areas").select("id, nombre").order("nombre").execute()
            app_cache.cat_areas = res_a.data or []
        except Exception as ex:
            print(f"[CACHE] Categorías ERROR: {ex}")
            app_cache.cat_familias = app_cache.cat_familias or []
            app_cache.cat_subfamilias = app_cache.cat_subfamilias or []
            app_cache.cat_tipos = app_cache.cat_tipos or []
            app_cache.cat_areas = app_cache.cat_areas or []
        else:
            print(f"[CACHE] Categorías listo — {len(app_cache.cat_familias)} familias, {len(app_cache.cat_subfamilias)} subfamilias, {len(app_cache.cat_tipos)} tipos")
        finally:
            app_cache.cat_ready.set()
            _check_done()

    # ── Auditoría (dropdown usuarios) ───────────────────────────────────
    def _pre_aud():
        try:
            sb = get_sb()
            app_cache.aud_usuarios = sb.table("usuarios").select("usuario, nombre").execute().data or []
        except Exception as ex:
            print(f"[CACHE] Auditoría ERROR: {ex}")
            app_cache.aud_usuarios = app_cache.aud_usuarios or []
        else:
            print(f"[CACHE] Auditoría listo — {len(app_cache.aud_usuarios)} usuarios")
        finally:
            app_cache.aud_ready.set()
            _check_done()

    # ── Usuarios ────────────────────────────────────────────────────────
    def _pre_usu():
        try:
            sb = get_sb()
            app_cache.usu_roles = sb.table("roles").select("id, nombre").execute().data or []
            app_cache.usu_usuarios = sb.table("usuarios").select("usuario, nombre, rol_id, foto, roles(nombre)").execute().data or []
        except Exception as ex:
            print(f"[CACHE] Usuarios ERROR: {ex}")
            app_cache.usu_roles = app_cache.usu_roles or []
            app_cache.usu_usuarios = app_cache.usu_usuarios or []
        else:
            print(f"[CACHE] Usuarios listo — {len(app_cache.usu_usuarios)} usuarios, {len(app_cache.usu_roles)} roles")
        finally:
            app_cache.usu_ready.set()
            _check_done()

    # ── Gestión de Permisos ─────────────────────────────────────────────
    def _pre_perm():
        try:
            sb = get_sb()
            app_cache.perm_roles = sb.table("roles").select("id, nombre").execute().data or []
            res_p = sb.table("configuracion_permisos").select("rol_id").eq("vista", "permisos").eq("permitido", True).execute()
            app_cache.perm_admin_ids = {f["rol_id"] for f in (res_p.data or [])}
        except Exception as ex:
            print(f"[CACHE] Permisos ERROR: {ex}")
            app_cache.perm_roles = app_cache.perm_roles or []
            app_cache.perm_admin_ids = app_cache.perm_admin_ids or set()
        else:
            print(f"[CACHE] Permisos listo — {len(app_cache.perm_roles)} roles, {len(app_cache.perm_admin_ids)} admins")
        finally:
            app_cache.perm_ready.set()
            _check_done()

    # ── Gestión de Furgones ─────────────────────────────────────────────
    def _pre_gfur():
        try:
            sb = get_sb()
            app_cache.gfur_usuarios = sb.table("usuarios").select("usuario, nombre, roles(nombre)").execute().data or []
            app_cache.gfur_furgones = sb.table("furgones").select("*").order("id").execute().data or []
            # Batch count: una sola query en vez de N queries por furgón
            fp_rows = fetch_all("furgon_productos", "furgon_id")
            counts: dict = {}
            for row in fp_rows:
                fid = row.get("furgon_id")
                if fid is not None:
                    counts[fid] = counts.get(fid, 0) + 1
            app_cache.gfur_fp_counts = counts
        except Exception as ex:
            print(f"[CACHE] GestionFurgones ERROR: {ex}")
            app_cache.gfur_usuarios = app_cache.gfur_usuarios or []
            app_cache.gfur_furgones = app_cache.gfur_furgones or []
            app_cache.gfur_fp_counts = app_cache.gfur_fp_counts or {}
        else:
            print(f"[CACHE] GestionFurgones listo — {len(app_cache.gfur_furgones)} furgones")
        finally:
            app_cache.gfur_ready.set()
            _check_done()

    # ── Gráficos ────────────────────────────────────────────────────────
    def _pre_gra():
        try:
            from core.database import fetch_furgones_con_totales
            sb = get_sb()

            # fetch_all pagina para obtener todos los registros sin límite
            prods_raw = fetch_all(
                "productos",
                "sku, nombre, stock_global, costo_neto, precio_venta, familias(nombre), subfamilias(nombre)",
            )
            for p in prods_raw:
                p["stock_actual"] = p.get("stock_global", 0) or 0
                p["familia"]    = (p.get("familias")    or {}).get("nombre") or "Sin Familia"
                p["subfamilia"] = (p.get("subfamilias") or {}).get("nombre") or "Sin Subfamilia"
            app_cache.gra_productos = prods_raw

            app_cache.gra_auditoria   = fetch_all("auditoria", "usuario, accion, fecha")
            app_cache.gra_movimientos = fetch_all(
                "movimientos_inventario", "sku, tipo_movimiento, cantidad, fecha, usuario"
            )
            app_cache.gra_bodegas = sb.table("bodegas").select("id, nombre").order("id").execute().data or []
            app_cache.gra_bp = fetch_all("bodega_productos", "bodega_id, sku, cantidad")
            app_cache.gra_furgones = fetch_furgones_con_totales()
            app_cache.gra_fp = fetch_all("furgon_productos", "furgon_id, sku, cantidad")
        except Exception as ex:
            print(f"[CACHE] Gráficos ERROR: {ex}")
            for attr in ("gra_productos", "gra_auditoria", "gra_movimientos",
                         "gra_bodegas", "gra_bp", "gra_furgones", "gra_fp"):
                if getattr(app_cache, attr) is None:
                    setattr(app_cache, attr, [])
        else:
            print(f"[CACHE] Gráficos listo — {len(app_cache.gra_productos)} productos, {len(app_cache.gra_movimientos)} movimientos")
        finally:
            app_cache.gra_ready.set()
            _check_done()

    threading.Thread(target=_pre_inv, daemon=True).start()
    threading.Thread(target=_pre_mov, daemon=True).start()
    threading.Thread(target=_pre_fin, daemon=True).start()
    threading.Thread(target=_pre_dash, daemon=True).start()
    threading.Thread(target=_pre_cat, daemon=True).start()
    threading.Thread(target=_pre_aud, daemon=True).start()
    threading.Thread(target=_pre_usu, daemon=True).start()
    threading.Thread(target=_pre_perm, daemon=True).start()
    threading.Thread(target=_pre_gfur, daemon=True).start()
    threading.Thread(target=_pre_gra, daemon=True).start()


def main(page: ft.Page):
    # Configuración de ventana
    page.title = "SICAV ERP - Sistema de Bodega"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width  = 1100
    page.window.height = 800
    page.window.maximized = True
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#f0f2f5"

    area_trabajo = ft.Container(expand=True, padding=25)
    vistas_cacheadas = {}

    # Sidebar estructural
    sidebar = ft.Container(
        width=250, bgcolor="#2b3035", padding=ft.padding.only(top=20), animate=300,
        content=ft.Column([], horizontal_alignment="start", expand=True, scroll=ft.ScrollMode.AUTO)
    )

    def toggle_sidebar(e):
        sidebar.width = 75 if sidebar.width == 250 else 250
        actualizar_sidebar_content()
        sidebar.update()

    def cambiar_vista(accion):
        if accion not in vistas_cacheadas:
            # Enrutador dinámico
            if accion == "dashboard": vistas_cacheadas[accion] = VistaDashboard(page)
            elif accion == "inventario": vistas_cacheadas[accion] = VistaInventario(page)
            elif accion == "comercial": vistas_cacheadas[accion] = VistaComercial(page)
            elif accion == "movimientos": vistas_cacheadas[accion] = VistaMovimientos(page) # <--- ¡ESTA ES LA LÍNEA QUE FALTABA!
            elif accion == "categorias": vistas_cacheadas[accion] = VistaCategorias(page)
            elif accion == "furgo": vistas_cacheadas[accion] = VistaMiFurgon(page)
            elif accion == "gestion_furgones": vistas_cacheadas[accion] = VistaGestionFurgones(page)
            elif accion == "usuarios": vistas_cacheadas[accion] = VistaUsuarios(page)
            elif accion == "estadisticas": vistas_cacheadas[accion] = VistaAuditoria(page) # Recuerda que 'estadisticas' abre Auditoria en tu enrutador
            elif accion == "finanzas": vistas_cacheadas[accion] = VistaFinanzas(page)
            elif accion == "graficos": vistas_cacheadas[accion] = VistaGraficos(page)
            elif accion == "permisos": vistas_cacheadas[accion] = VistaGestionPermisos(page)
            elif accion == "importar": vistas_cacheadas[accion] = VistaImportar(page)
            else: vistas_cacheadas[accion] = ft.Container(content=ft.Text(f"Módulo '{accion}' en refactorización... 🛠️", size=20))
        
        vista = vistas_cacheadas[accion]

        # Path rápido: si el cache ya está listo, poblar controles ANTES de page.update()
        # para que el primer render ya incluya los datos (sin necesidad de hilo ni update() extra)
        if hasattr(vista, 'pre_cargar_si_cache_listo'):
            vista.pre_cargar_si_cache_listo()

        area_trabajo.content = vista
        page.update()

        init_prev_lists(vista)  # seed __prev_lists so background updates produce non-empty patches

        if hasattr(vista, 'inicializar'):
            vista.inicializar()

    def crear_boton_menu(icono, texto, accion, visible=True):
        return ft.ListTile(
            leading=ft.Icon(icono, color="white70", size=22),
            title=ft.Text(texto, color="white", size=13) if sidebar.width == 250 else None,
            on_click=lambda _: cambiar_vista(accion),
            visible=visible,
            hover_color="white10",
            content_padding=ft.padding.symmetric(horizontal=12),
        )

    def seccion_label(texto, visible=True):
        if sidebar.width != 250:
            return ft.Divider(color="white12", height=12, visible=visible)
        return ft.Container(
            content=ft.Text(texto.upper(), size=10, color="white38", weight="bold"),
            padding=ft.padding.only(left=16, top=12, bottom=2),
            visible=visible,
        )

    def actualizar_sidebar_content():
        ruta_avatar = obtener_ruta_imagen(estado.usuario_actual.get("foto", ""))
        if os.path.exists(ruta_avatar):
            avatar_control = ft.CircleAvatar(foreground_image_src=estado.usuario_actual["foto"], radius=20)
        else:
            avatar_control = ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON), radius=20)

        header_content = []
        header_content.append(ft.Row([
            ft.IconButton(ft.Icons.MENU, icon_color="white", on_click=toggle_sidebar)
        ] + ([ft.Text("SICAV", color="white", size=18, weight="bold")] if sidebar.width == 250 else [])))
        header_content.append(ft.Divider(color="white24", height=1))

        if sidebar.width == 250:
            header_content.append(ft.Container(
                content=ft.Row([
                    avatar_control,
                    ft.Column([
                        ft.Text(estado.usuario_actual["nombre"], color="white", weight="bold", size=13),
                        ft.Text(estado.usuario_actual["rol"], color="white54", size=11),
                    ], spacing=1),
                ], spacing=10),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
            ))
        else:
            header_content.append(ft.Container(content=avatar_control, padding=8))

        header_content.append(ft.Divider(color="white24", height=1))

        p = estado.puede_ver  # alias corto

        menu_items = [
            # ── PRINCIPAL ──
            crear_boton_menu(ft.Icons.DASHBOARD, "Dashboard", "dashboard", visible=p("dashboard")),

            # ── STOCK ──
            seccion_label("Stock", visible=p("inventario") or p("movimientos") or p("importar")),
            crear_boton_menu(ft.Icons.INVENTORY_2,       "Inventario General", "inventario",      visible=p("inventario")),
            crear_boton_menu(ft.Icons.SWAP_HORIZ,        "Traspasos",          "movimientos",     visible=p("movimientos")),
            crear_boton_menu(ft.Icons.UPLOAD_FILE,       "Importar",           "importar",        visible=p("importar")),

            # ── VENTAS ──
            seccion_label("Ventas", visible=p("comercial") or p("finanzas")),
            crear_boton_menu(ft.Icons.POINT_OF_SALE,     "Ajuste Exprés",      "comercial",       visible=p("comercial")),
            crear_boton_menu(ft.Icons.ATTACH_MONEY,      "Finanzas",           "finanzas",        visible=p("finanzas")),

            # ── FURGONES ──
            seccion_label("Furgones", visible=p("furgo") or p("gestion_furgones")),
            crear_boton_menu(ft.Icons.LOCAL_SHIPPING,    "Mi Furgón",          "furgo",           visible=p("furgo")),
            crear_boton_menu(ft.Icons.GARAGE,            "Gestión Furgones",   "gestion_furgones",visible=p("gestion_furgones")),

            # ── ANÁLISIS ──
            seccion_label("Análisis", visible=p("graficos") or p("estadisticas") or p("dashboard")),
            crear_boton_menu(ft.Icons.BAR_CHART,         "Gráficos",           "graficos",        visible=p("graficos")),
            crear_boton_menu(ft.Icons.HISTORY,           "Auditoría",          "estadisticas",    visible=p("estadisticas")),

            # ── ADMINISTRACIÓN ──
            seccion_label("Administración", visible=p("categorias") or p("usuarios") or p("permisos") or p("eliminar")),
            crear_boton_menu(ft.Icons.LABEL,             "Categorías",         "categorias",      visible=p("categorias")),
            crear_boton_menu(ft.Icons.MANAGE_ACCOUNTS,   "Usuarios",           "usuarios",        visible=p("usuarios")),
            crear_boton_menu(ft.Icons.ADMIN_PANEL_SETTINGS, "Permisos",        "permisos",        visible=p("permisos")),

            ft.Container(expand=True),
            ft.Divider(color="white24"),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOGOUT, color="#ff6b6b", size=22),
                title=ft.Text("Cerrar Sesión", color="#ff6b6b", size=13) if sidebar.width == 250 else None,
                on_click=lambda e: iniciar_login(),
                hover_color="white10",
                content_padding=ft.padding.symmetric(horizontal=12),
            ),
        ]

        sidebar.content.controls = header_content + menu_items

    # Hook para que vistas internas puedan refrescar el sidebar
    page._actualizar_sidebar = actualizar_sidebar_content

    def iniciar_app_principal():
        page.controls.clear()
        actualizar_sidebar_content()

        barra_carga = ft.ProgressBar(
            color="blue700",
            bgcolor=ft.Colors.with_opacity(0.15, "blue700"),
            height=3,
            visible=True,
        )

        def _ocultar_barra():
            barra_carga.visible = False
            try:
                barra_carga.update()
            except Exception:
                pass

        page.add(ft.Column([
            barra_carga,
            ft.Row([sidebar, area_trabajo], expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
        ], expand=True, spacing=0))
        page.update()

        app_cache.reset()
        precargar_vistas(on_complete=_ocultar_barra)

        primera = next((v for v in ["dashboard", "inventario", "comercial", "finanzas", "estadisticas"] if estado.puede_ver(v)), "inventario")
        cambiar_vista(primera)

    def iniciar_login():
        page.clean()
        vistas_cacheadas.clear()
        app_cache.reset()
        page.add(VistaLogin(page, on_login_success=iniciar_app_principal))
        page.update()
        verificar_actualizacion(page)

    iniciar_login()

if __name__ == "__main__":
    import sys as _sys, os as _os
    _assets = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets")

    # Detectar si el GPU soporta Metal (Sandy Bridge / Intel HD 3000 no tiene Metal)
    _use_web = False
    try:
        import ctypes as _ctypes
        _metal = _ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Metal.framework/Metal")
        _metal.MTLCreateSystemDefaultDevice.restype = _ctypes.c_void_p
        if not _metal.MTLCreateSystemDefaultDevice():
            _use_web = True
    except Exception:
        pass  # No es macOS o no hay Metal framework → modo desktop

    if _use_web:
        import webbrowser as _wb
        _firefox = "/Applications/Firefox.app/Contents/MacOS/firefox"
        if _os.path.exists(_firefox):
            _wb.register("firefox", None, _wb.BackgroundBrowser(_firefox), preferred=True)
        ft.app(target=main, assets_dir=_assets, view=ft.AppView.WEB_BROWSER, port=8080)
    else:
        ft.app(target=main, assets_dir=_assets)