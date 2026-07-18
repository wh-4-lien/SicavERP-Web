# vistas/dashboard.py
import flet as ft
import datetime
from collections import Counter
from core.database import get_sb, fetch_productos
from core.estado import estado
from core.utilidades import hilo

# --- Componentes Visuales ---
def kpi_card(titulo, valor, subtitulo, icono, color):
    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(content=ft.Icon(icono, color="white", size=26), bgcolor=color, border_radius=10, padding=10),
                ft.Container(width=12),
                ft.Column([ft.Text(str(valor), size=28, weight="black", color="grey900"), ft.Text(titulo, size=12, color="grey500")], spacing=0, expand=True),
            ]),
            ft.Divider(height=8, color="transparent"),
            ft.Text(subtitulo, size=11, color="grey400", italic=True),
        ], spacing=2),
        padding=16, bgcolor="white", border_radius=12, expand=True,
        border=ft.border.all(1, "grey200"),
        shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.06, "black")),
    )

def alerta_card(texto, color, icono):
    return ft.Container(
        content=ft.Row([
            ft.Icon(icono, color=color, size=18),
            ft.Container(width=8),
            ft.Text(texto, size=12, color="grey800", expand=True),
        ]),
        padding=ft.Padding(12, 8, 12, 8),
        bgcolor=ft.Colors.with_opacity(0.08, color),
        border_radius=8,
        border=ft.Border(left=ft.BorderSide(3, color)),
    )

def fila_tabla(cols, header=False):
    cells = []
    for i, (txt, w) in enumerate(cols):
        cells.append(ft.Container(
            content=ft.Text(txt, size=11 if not header else 10, weight="bold" if header else "normal", color="grey600" if header else "grey800", no_wrap=True),
            expand=w, padding=ft.Padding(6, 4, 6, 4),
            bgcolor="grey100" if header else None,
        ))
    return ft.Row(cells, spacing=0)

def seccion(titulo, contenido):
    return ft.Container(
        content=ft.Column([ft.Text(titulo, weight="bold", size=14, color="grey700"), ft.Divider(height=6, color="transparent"), contenido]),
        padding=16, bgcolor="white", border_radius=12, border=ft.border.all(1, "grey200"),
        shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.05, "black")),
    )

# --- CLASE PRINCIPAL ---
class VistaDashboard(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.construir_ui()

    def construir_ui(self):
        self.col_kpis = ft.Row([], wrap=False, spacing=12)
        self.col_alertas = ft.Column([], spacing=6)
        self.col_top_stock = ft.Column([], spacing=4)
        self.col_bajo_stock = ft.Column([], spacing=4)
        self.col_sin_precio = ft.Column([], spacing=4)
        self.col_margen = ft.Column([], spacing=4)
        self.col_actividad = ft.Column([], spacing=4)
        self.col_usuarios_act = ft.Column([], spacing=4)

        ver_costo = estado.puede_ver("costo")
        self.fila_costo = ft.Row([
            ft.Column([seccion("🏆 Top 10 Margen de Ganancia", self.col_margen)], expand=1),
            ft.Container(width=12),
            ft.Column([seccion("⚠️ Datos Incompletos", self.col_sin_precio)], expand=1),
        ], visible=ver_costo)

        self.content = ft.Column([
            ft.Row([
                ft.Text("📊 Dashboard", size=24, weight="bold", color="blue900", expand=True),
                ft.ElevatedButton("🔄 Actualizar", on_click=lambda _: self.cargar_dashboard(forzar_fetch=True), height=40),
            ]),
            ft.Divider(height=10, color="transparent"),
            self.col_kpis,
            ft.Divider(height=10, color="transparent"),
            seccion("🚨 Alertas del Sistema", self.col_alertas),
            ft.Divider(height=10, color="transparent"),
            ft.Row([
                ft.Column([seccion("📈 Top 10 Mayor Stock", self.col_top_stock)], expand=1),
                ft.Container(width=12),
                ft.Column([seccion("📉 Stock Crítico (≤3 o Cero)", self.col_bajo_stock)], expand=1),
            ]),
            ft.Divider(height=10, color="transparent"),
            self.fila_costo,
            ft.Divider(height=10, color="transparent"),
            ft.Row([
                ft.Column([seccion("🕐 Actividad Reciente", self.col_actividad)], expand=1),
                ft.Container(width=12),
                ft.Column([seccion("👤 Usuarios Más Activos", self.col_usuarios_act)], expand=1),
            ]),
        ], scroll=ft.ScrollMode.AUTO)

    # ══════════════════════════════ Cache ══════════════════════════════
    def pre_cargar_si_cache_listo(self):
        from core.cache import app_cache
        if getattr(self, '_datos_cargados', False):
            return
        if app_cache.inv_ready.is_set() and app_cache.dash_ready.is_set():
            prods   = app_cache.inv_productos or []
            aud     = app_cache.dash_auditoria_reciente or []
            top500  = app_cache.dash_auditoria_top500 or []
            self._construir_columnas_ui(prods, aud, top500, llamar_update=False)
            self._datos_cargados = True
            print(f"[DASHBOARD] pre-cargado ({len(prods)} productos)")

    def _construir_columnas_ui(self, prods, aud, top500, llamar_update=True):
        """Rellena col_* con los datos proporcionados. Sin update() si llamar_update=False."""
        total_prods  = len(prods)
        sin_stock    = [p for p in prods if (p.get("stock_actual") or 0) == 0]
        bajo_stock   = [p for p in prods if 0 < (p.get("stock_actual") or 0) <= 3]
        sin_precio   = [p for p in prods if not p.get("precio_venta") or p["precio_venta"] == 0]
        val_costo    = sum((p.get("stock_actual") or 0) * (p.get("costo_neto") or 0) for p in prods)
        val_venta    = sum((p.get("stock_actual") or 0) * (p.get("precio_venta") or 0) for p in prods)
        margen_total = val_venta - val_costo
        usr_counter  = Counter(a.get("usuario") for a in top500)
        top_usuarios = usr_counter.most_common(5)

        ver_costo = estado.puede_ver("costo")
        kpis = [kpi_card("Productos", total_prods, f"{len(sin_stock)} sin stock", ft.Icons.INVENTORY_2, "blue700")]
        if ver_costo:
            kpis += [
                kpi_card("Valor Costo", f"${val_costo:,.0f}", f"Venta: ${val_venta:,.0f}", ft.Icons.ACCOUNT_BALANCE_WALLET, "teal700"),
                kpi_card("Margen", f"${margen_total:,.0f}", f"{(margen_total/val_venta*100) if val_venta else 0:.1f}% venta", ft.Icons.TRENDING_UP, "green700"),
            ]
        kpis.append(kpi_card("Alertas", len(sin_stock)+len(bajo_stock)+len(sin_precio), "Ver detalles", ft.Icons.WARNING_AMBER, "orange700"))
        self.col_kpis.controls = kpis

        alertas = []
        if sin_stock:
            alertas.append(alerta_card(f"{len(sin_stock)} producto(s) sin stock — requieren reabastecimiento urgente.", "red700", ft.Icons.ERROR_OUTLINE))
        if bajo_stock:
            alertas.append(alerta_card(f"{len(bajo_stock)} producto(s) con stock crítico (≤ 3 unidades).", "orange700", ft.Icons.WARNING_AMBER))
        if sin_precio:
            alertas.append(alerta_card(f"{len(sin_precio)} producto(s) sin precio de venta registrado.", "amber700", ft.Icons.SELL))
        if ver_costo:
            sin_costo = [p for p in prods if not (p.get("costo_neto") or 0)]
            if sin_costo:
                alertas.append(alerta_card(f"{len(sin_costo)} producto(s) sin costo neto — el margen no se puede calcular.", "amber700", ft.Icons.PRICE_CHANGE))
        if not alertas:
            alertas.append(alerta_card("Todo en orden — sin alertas activas.", "green700", ft.Icons.CHECK_CIRCLE))
        self.col_alertas.controls = alertas

        top10   = sorted(prods, key=lambda p: p.get("stock_actual") or 0, reverse=True)[:10]
        criticos = sorted(sin_stock + bajo_stock, key=lambda p: p.get("stock_actual") or 0)[:10]
        self.col_top_stock.controls = [fila_tabla([("SKU",2),("Nombre",5),("Familia",3),("Stock",1)], header=True)] + \
            [fila_tabla([(p.get("sku",""),2),(p.get("nombre","")[:20],5),(p.get("familia","") or "-",3),(str(p.get("stock_actual",0)),1)]) for p in top10]
        self.col_bajo_stock.controls = [fila_tabla([("SKU",2),("Nombre",5),("Familia",3),("Stock",1)], header=True)] + \
            [fila_tabla([(p.get("sku",""),2),(p.get("nombre","")[:20],5),(p.get("familia","") or "-",3),(str(p.get("stock_actual",0)),1)]) for p in criticos]

        if ver_costo:
            top_margen = sorted([p for p in prods if (p.get("precio_venta") or 0) > 0], key=lambda p: ((p.get("precio_venta") or 0)-(p.get("costo_neto") or 0)), reverse=True)[:10]
            self.col_margen.controls = [fila_tabla([("SKU",2),("Nombre",5),("Margen $",3)], header=True)] + \
                [fila_tabla([(p.get("sku",""),2),(p.get("nombre","")[:20],5),(f"${((p.get('precio_venta') or 0)-(p.get('costo_neto') or 0)):,.0f}",3)]) for p in top_margen]
            sin_datos = [p for p in prods if not (p.get("precio_venta") or 0) or not (p.get("costo_neto") or 0)][:15]
            if sin_datos:
                self.col_sin_precio.controls = [fila_tabla([("SKU",2),("Nombre",5),("Problema",4)], header=True)] + [
                    fila_tabla([(p.get("sku",""),2),(p.get("nombre","")[:22],5),
                                ("Sin precio" if not (p.get("precio_venta") or 0) and not (p.get("costo_neto") or 0)
                                 else "Sin precio" if not (p.get("precio_venta") or 0) else "Sin costo", 4)])
                    for p in sin_datos]
            else:
                self.col_sin_precio.controls = [ft.Container(
                    content=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color="green600", size=18),
                                    ft.Text("Todos los productos tienen precio y costo completos.", size=12, color="green700")], spacing=8), padding=10)]

        filas_aud = []
        for a in aud[:10]:
            fecha_raw = a.get("fecha") or ""
            try:
                _dt = datetime.datetime.fromisoformat(fecha_raw.replace("Z","+00:00"))
                if _dt.tzinfo is None: _dt = _dt.replace(tzinfo=datetime.timezone.utc)
                fecha_fmt = _dt.astimezone().strftime("%d/%m %H:%M")
            except Exception:
                fecha_fmt = "-"
            filas_aud.append(fila_tabla([(fecha_fmt,3),(a.get("usuario",""),3),(a.get("accion",""),4)]))
        self.col_actividad.controls = [fila_tabla([("Fecha",3),("Usuario",3),("Acción",4)], header=True)] + filas_aud
        self.col_usuarios_act.controls = [fila_tabla([("Usuario",6),("Ops",4)], header=True)] + \
            [fila_tabla([(usr or "-",6),(str(cnt),4)]) for usr, cnt in top_usuarios]

        if llamar_update and self.page_ref:
            self.page_ref.update()

    # ══════════════════════════════ Init ══════════════════════════════
    def inicializar(self):
        if getattr(self, '_datos_cargados', False):
            return
        self.cargar_dashboard()

    def cargar_dashboard(self, forzar_fetch=False):
        self._datos_cargados = False
        def _run():
            try:
                from core.cache import app_cache
                # Reusar productos del cache de inventario si disponible (solo en primera carga)
                if not forzar_fetch and app_cache.inv_ready.is_set() and app_cache.inv_productos:
                    prods = list(app_cache.inv_productos)
                else:
                    prods = fetch_productos("sku, nombre, costo_neto, precio_venta, stock_global, familias(nombre), subfamilias(nombre)")

                # Auditoria: reusar cache si disponible; si no, fetch
                if app_cache.dash_ready.is_set() and app_cache.dash_auditoria_reciente is not None:
                    aud    = app_cache.dash_auditoria_reciente
                    top500 = app_cache.dash_auditoria_top500 or []
                else:
                    res_aud = get_sb().table("auditoria").select("usuario, accion, fecha").order("fecha", desc=True).limit(10).execute()
                    aud = res_aud.data or []
                    res_top = get_sb().table("auditoria").select("usuario").order("fecha", desc=True).limit(500).execute()
                    top500 = res_top.data or []

                self._construir_columnas_ui(prods, aud, top500, llamar_update=True)
                self._datos_cargados = True
            except Exception as ex:
                import traceback; traceback.print_exc()
                self.col_alertas.controls = [alerta_card(f"❌ Error al cargar datos: {ex}", "red700", ft.Icons.ERROR)]
                if self.page_ref: self.col_alertas.update()
        hilo(_run)