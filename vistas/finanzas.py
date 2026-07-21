# vistas/finanzas.py
import flet as ft
from core.database import get_sb, fetch_productos
from core.estado import estado
from core.utilidades import hilo, registrar_auditoria, clp
from datetime import datetime

# ── helpers de schema nuevo ──────────────────────────────────────────
def _fam(p):  return (p.get("familias")   or {}).get("nombre") or "Sin Familia"
def _sub(p):  return (p.get("subfamilias") or {}).get("nombre") or ""
def _label_bodega(b: dict) -> str:
    area = (b.get("areas") or {}).get("nombre") or ""
    return f"[{area}] {b['nombre']}" if area else b["nombre"]
def _stk(p):  return p.get("stock_global") or 0

# ── tarjetas ─────────────────────────────────────────────────────────
def tarjeta_resumen(titulo, val_costo, val_venta, icono, color):
    return ft.Container(
        width=340,
        content=ft.Column([
            ft.Row([ft.Icon(icono, color=color, size=22),
                    ft.Text(titulo, weight="bold", size=13, color="grey800", expand=True)]),
            ft.Divider(height=6, color="transparent"),
            ft.Row([
                ft.Column([ft.Text("Costo", size=10, color="grey500"),
                           ft.Text(clp(val_costo), size=15, weight="bold", color="blue900")]),
                ft.Column([ft.Text("Venta", size=10, color="grey500"),
                           ft.Text(clp(val_venta), size=15, weight="bold", color="green800")]),
                ft.Column([ft.Text("Margen", size=10, color="grey500"),
                           ft.Text(clp(val_venta - val_costo), size=15, weight="bold",
                                   color="green700" if val_venta >= val_costo else "red700")]),
            ], spacing=20),
        ], spacing=3),
        padding=16, bgcolor="white", border_radius=12,
        border=ft.border.all(1, "grey200"),
        shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.06, "black")),
    )

def tarjeta_movimiento(titulo, valor, subtitulo, icono, color):
    return ft.Container(
        width=220,
        content=ft.Column([
            ft.Row([ft.Icon(icono, color=color, size=20),
                    ft.Text(titulo, weight="bold", size=12, color="grey800", expand=True)]),
            ft.Text(clp(valor), size=18, weight="black", color="grey900"),
            ft.Text(subtitulo, size=10, color="grey500", italic=True),
        ], spacing=3),
        padding=14, bgcolor="white", border_radius=12,
        border=ft.border.all(1, "grey200"),
    )

def tarjeta_conteo(titulo, valor, subtitulo, icono, color):
    return ft.Container(
        width=220,
        content=ft.Column([
            ft.Row([ft.Icon(icono, color=color, size=20),
                    ft.Text(titulo, weight="bold", size=12, color="grey800", expand=True)]),
            ft.Text(f"{valor:,}", size=18, weight="black", color="grey900"),
            ft.Text(subtitulo, size=10, color="grey500", italic=True),
        ], spacing=3),
        padding=14, bgcolor="white", border_radius=12,
        border=ft.border.all(1, "grey200"),
    )

def fila_sub(sub, costo, venta):
    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT, color="grey400", size=14),
            ft.Text(sub, size=11, color="grey700", expand=True),
            ft.Text(clp(costo),  size=11, color="blue800", weight="bold"),
            ft.Container(width=16),
            ft.Text(clp(venta),  size=11, color="green700", weight="bold"),
            ft.Container(width=16),
            ft.Text(clp(venta-costo), size=11,
                    color="green700" if venta >= costo else "red700", weight="bold"),
        ]),
        padding=ft.Padding(12, 5, 12, 5),
        bgcolor="grey50", border_radius=6,
        border=ft.border.all(1, "grey100"),
    )


class VistaFinanzas(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.datos_cargados = False
        self._cargando = False
        self._datos_familias = {}
        self._resumen_global = {}
        self._historial_kpis = {}
        self.construir_ui()
        self.content = self._main_content

    def mostrar_snack(self, mensaje, tipo_o_color="success"):
        from utils.ui_helpers import mostrar_snack as _snack
        _snack(self.page_ref, mensaje, tipo_o_color)

    def construir_ui(self):
        self.dd_bodega = ft.Dropdown(
            label="Ver por", width=220, height=48,
            options=[ft.dropdown.Option("0", "Todas las bodegas")],
            value="0",
        )
        self.dd_bodega.on_change = lambda e: self.cargar_todo()

        self.dd_mes = ft.Dropdown(
            label="Mes", width=160,
            options=[ft.dropdown.Option(str(i), datetime(2000, i, 1).strftime('%B').capitalize())
                     for i in range(1, 13)],
            value=str(datetime.now().month),
        )
        self.dd_anio = ft.Dropdown(
            label="Año", width=110,
            options=[ft.dropdown.Option(str(y))
                     for y in range(datetime.now().year - 3, datetime.now().year + 1)],
            value=str(datetime.now().year),
        )

        self.col_global    = ft.Row([], wrap=True, spacing=12)
        self.col_bodegas   = ft.Column([], spacing=8)
        self.col_historial = ft.Row([], wrap=True, spacing=12)
        self.col_familias  = ft.Column([], spacing=10)
        self._datos_bodegas_areas = {}

        from utils.ui_helpers import sandwich

        _header = ft.Row([
            ft.Text("Finanzas y Valorización", size=24, weight="bold", color="blue900", expand=True),
            self.dd_bodega,
            ft.ElevatedButton("Refrescar", icon=ft.Icons.REFRESH,
                              on_click=self._recargar, height=42,
                              tooltip="Actualizar valorización e historial"),
            ft.ElevatedButton("Exportar PDF", icon=ft.Icons.PICTURE_AS_PDF,
                              on_click=self.exportar_pdf,
                              bgcolor="red700", color="white", height=42,
                              tooltip="Exportar reporte financiero en PDF",
                              visible=estado.puede_hacer("finanzas", "exportar")),
        ])

        _body = ft.Column([
            # ── Valorización Global ──
            ft.Text("Valorización del Inventario", size=16, weight="bold", color="grey800"),
            self.col_global,
            ft.Divider(height=16, color="grey200"),

            # ── Por Área y Bodega ──
            ft.Text("Valorización por Área y Bodega", size=16, weight="bold", color="indigo900"),
            self.col_bodegas,
            ft.Divider(height=16, color="grey200"),

            # ── Análisis de Movimientos ──
            ft.Text("Análisis de Movimientos por Período", size=16, weight="bold", color="blue900"),
            ft.Row([self.dd_mes, self.dd_anio,
                    ft.ElevatedButton("Consultar", icon=ft.Icons.SEARCH,
                                      on_click=lambda _: self.cargar_historial(), height=44,
                                      tooltip="Consultar movimientos del período seleccionado")],
                   spacing=10),
            self.col_historial,
            ft.Divider(height=16, color="grey200"),

            # ── Por Familias ──
            ft.Text("Valorización por Familia y Subfamilia", size=16, weight="bold", color="blue900"),
            self.col_familias,
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=14)

        self._main_content = sandwich(_header, _body)

    def _parse_filtro(self):
        """Devuelve (tipo, valor) desde dd_bodega.value.
        tipos: 'global' | 'area' | 'bodega' | 'furgon'
        """
        sel = self.dd_bodega.value or "0"
        if sel == "0" or sel.startswith("__sep"):
            return "global", None
        if sel.startswith("f:"):
            return "furgon", int(sel[2:])
        if sel.startswith("a:"):
            return "area", sel[2:]
        try:
            return "bodega", int(sel)
        except ValueError:
            return "global", None

    def pre_cargar_si_cache_listo(self):
        from core.cache import app_cache
        if self.datos_cargados or not app_cache.fin_ready.is_set():
            return
        self._poblar_desde_cache(app_cache)

    def _poblar_desde_cache(self, app_cache):
        """Aplica datos del cache a los controles. Sin update() — el llamador debe actualizar."""
        bodegas  = app_cache.fin_bodegas  or []
        furgones = app_cache.fin_furgones or []
        areas = sorted({(b.get("areas") or {}).get("nombre") for b in bodegas} - {None, ""})

        options = [ft.dropdown.Option("0", "Todas las bodegas")]
        if areas:
            options.append(ft.dropdown.Option("__sep_a", "── Áreas ──"))
            for area in areas:
                options.append(ft.dropdown.Option(f"a:{area}", f"📍 {area}"))
        if bodegas:
            options.append(ft.dropdown.Option("__sep_b", "── Bodegas ──"))
            for b in bodegas:
                options.append(ft.dropdown.Option(str(b["id"]), f"🏭 {_label_bodega(b)}"))
        if furgones:
            options.append(ft.dropdown.Option("__sep_f", "── Furgones ──"))
            for f in furgones:
                options.append(ft.dropdown.Option(f"f:{f['id']}", f"🚐 {f['nombre']}"))
        self.dd_bodega.options = options
        prods = list(app_cache.fin_productos_raw or [])
        for p in prods:
            p["_stock_filtrado"] = _stk(p)
        self._render_valorizacion(prods, "Todas las bodegas")
        bp_cache = getattr(app_cache, "fin_bp_raw", None) or []
        if bp_cache:
            prods_dict = {p["sku"]: p for p in prods}
            self._render_por_area_bodega(bp_cache, prods_dict)
        self._render_historial(
            app_cache.fin_historial_movs or [],
            app_cache.fin_historial_costo_map or {},
        )
        self.datos_cargados = True
        self._cargando = False

    def inicializar(self):
        from core.cache import app_cache
        if self._cargando:
            return
        if self.datos_cargados and app_cache.fin_ready.is_set():
            return
        self.datos_cargados = False
        self._cargando = True
        hilo(self._cargar_desde_cache)

    def _cargar_desde_cache(self):
        """Espera el evento de cache y renderiza — solo si el cache no estaba listo al navegar."""
        from core.cache import app_cache
        app_cache.fin_ready.wait(timeout=60)
        print(f"[FIN] cache tardó — renderizando desde hilo de espera")
        try:
            self._poblar_desde_cache(app_cache)
        except Exception:
            import traceback; traceback.print_exc()
            self._cargando = False
        if self.page_ref:
            try: self.dd_bodega.update()
            except Exception: pass
            try: self.page_ref.update()
            except Exception: pass

    def _recargar(self, e=None):
        self.cargar_todo()

    def _carga_inicial(self):
        """Re-obtiene datos desde la BD, actualiza cache y hace content-swap."""
        def _run():
            try:
                from core.cache import app_cache
                sb = get_sb()

                # 1. Bodegas
                bodegas = sb.table("bodegas").select("id, nombre, areas(nombre)").order("id").execute().data or []
                self.dd_bodega.options = [ft.dropdown.Option("0", "Todas las bodegas")] + \
                    [ft.dropdown.Option(str(b["id"]), _label_bodega(b)) for b in bodegas]

                # 2. Finanzas y historial (sincrónico, sin update() intermedios)
                self._calcular_finanzas(sb)
                self._calcular_historial(sb)

                # 3. Actualizar cache con datos frescos
                app_cache.fin_bodegas = bodegas
                app_cache.fin_ready.set()

                # 4. Content-swap
                self.content = self._main_content
                self.datos_cargados = True
                self._cargando = False
                if self.page_ref:
                    self.page_ref.update()

            except Exception as ex:
                self._cargando = False
                import traceback; traceback.print_exc()
                self.mostrar_snack(f"❌ Error al cargar finanzas: {ex}", "red700")
        hilo(_run)

    def cargar_todo(self):
        if (self.dd_bodega.value or "").startswith("__sep"):
            return
        self.cargar_finanzas()
        self.cargar_historial()

    # ═══════════════ helpers de renderizado (sin acceso a BD) ══════════════════
    def _render_valorizacion(self, productos, bodega_label):
        """Popula col_global y col_familias a partir de una lista de productos
        que ya tienen '_stock_filtrado' asignado."""
        def stk(p): return p.get("_stock_filtrado", 0)
        total_costo = sum(stk(p) * (p.get("costo_neto") or 0) for p in productos)
        total_venta = sum(stk(p) * (p.get("precio_venta") or 0) for p in productos)
        self._resumen_global = {"costo": total_costo, "venta": total_venta}
        self.col_global.controls = [
            tarjeta_resumen(bodega_label, total_costo, total_venta,
                            ft.Icons.ACCOUNT_BALANCE_WALLET, "blue700"),
        ]
        familias: dict = {}
        for p in productos:
            fam = _fam(p)
            sub = _sub(p) or "Sin Subfamilia"
            costo = stk(p) * (p.get("costo_neto") or 0)
            venta = stk(p) * (p.get("precio_venta") or 0)
            if fam not in familias:
                familias[fam] = {"costo": 0, "venta": 0, "subs": {}}
            familias[fam]["costo"] += costo
            familias[fam]["venta"] += venta
            if sub not in familias[fam]["subs"]:
                familias[fam]["subs"][sub] = {"costo": 0, "venta": 0}
            familias[fam]["subs"][sub]["costo"] += costo
            familias[fam]["subs"][sub]["venta"] += venta
        self._datos_familias = familias
        colores = ["teal700", "purple700", "orange700", "red700", "indigo700", "cyan700", "blue700", "green700"]
        controles = []
        for i, (fam, d) in enumerate(sorted(familias.items())):
            color = colores[i % len(colores)]
            cab = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.FOLDER, color=color, size=18),
                    ft.Text(fam, weight="bold", size=13, color="grey900", expand=True),
                    ft.Text(f"Costo: {clp(d['costo'])}", size=11, color="blue800", weight="bold"),
                    ft.Container(width=12),
                    ft.Text(f"Venta: {clp(d['venta'])}", size=11, color="green700", weight="bold"),
                    ft.Container(width=12),
                    ft.Text(f"Margen: {clp(d['venta']-d['costo'])}", size=11,
                            color="green700" if d['venta'] >= d['costo'] else "red700", weight="bold"),
                ]),
                padding=ft.Padding(14, 10, 14, 10),
                bgcolor=ft.Colors.with_opacity(0.06, color),
                border_radius=10,
                border=ft.Border(left=ft.BorderSide(4, color)),
            )
            subs_ctrl = [fila_sub(sub, sd["costo"], sd["venta"])
                         for sub, sd in sorted(d["subs"].items())
                         if sub != "Sin Subfamilia" or len(d["subs"]) > 1]
            controles.append(ft.Column([cab] + subs_ctrl, spacing=4))
        self.col_familias.controls = controles

    def _render_por_area_bodega(self, bp_raw, prods_dict):
        """bp_raw: [{sku, cantidad, bodegas:{nombre, areas:{nombre}}}]
        prods_dict: {sku: {costo_neto, precio_venta}}"""
        # Acumular por area -> bodega
        datos: dict = {}  # area -> bodega -> {costo, venta}
        for r in bp_raw:
            cant = r.get("cantidad") or 0
            if cant <= 0:
                continue
            sku = r.get("sku", "")
            prod = prods_dict.get(sku, {})
            costo = cant * (prod.get("costo_neto") or 0)
            venta = cant * (prod.get("precio_venta") or 0)
            bod   = r.get("bodegas") or {}
            area  = (bod.get("areas") or {}).get("nombre") or "Sin Área"
            bod_n = bod.get("nombre") or "?"
            datos.setdefault(area, {}).setdefault(bod_n, {"costo": 0, "venta": 0})
            datos[area][bod_n]["costo"] += costo
            datos[area][bod_n]["venta"] += venta

        self._datos_bodegas_areas = datos

        if not datos:
            self.col_bodegas.controls = [
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE, color="grey400", size=18),
                        ft.Text("Sin registros de stock por bodega. Asegúrese de usar el módulo de Inventario para asignar cantidades por bodega.", color="grey500", size=12, italic=True),
                    ], spacing=8),
                    padding=12,
                )
            ]
            return

        colores_area = ["indigo700", "teal700", "purple700", "blue700", "orange700"]
        controles = []
        for idx, (area, bodegas) in enumerate(sorted(datos.items())):
            color = colores_area[idx % len(colores_area)]
            total_c = sum(b["costo"] for b in bodegas.values())
            total_v = sum(b["venta"] for b in bodegas.values())

            cab = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.LOCATION_ON, color=color, size=16),
                    ft.Text(area, weight="bold", size=13, color="grey900", expand=True),
                    ft.Text(f"Costo: {clp(total_c)}", size=11, color="blue800", weight="bold"),
                    ft.Container(width=12),
                    ft.Text(f"Venta: {clp(total_v)}", size=11, color="green700", weight="bold"),
                    ft.Container(width=12),
                    ft.Text(f"Margen: {clp(total_v - total_c)}", size=11,
                            color="green700" if total_v >= total_c else "red700", weight="bold"),
                ]),
                padding=ft.Padding(14, 10, 14, 10),
                bgcolor=ft.Colors.with_opacity(0.06, color),
                border_radius=10,
                border=ft.Border(left=ft.BorderSide(4, color)),
            )
            filas_bod = []
            for bod_n, d in sorted(bodegas.items()):
                filas_bod.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.WAREHOUSE, color="grey400", size=14),
                        ft.Text(bod_n, size=11, color="grey700", expand=True),
                        ft.Text(clp(d['costo']), size=11, color="blue800", weight="bold"),
                        ft.Container(width=16),
                        ft.Text(clp(d['venta']), size=11, color="green700", weight="bold"),
                        ft.Container(width=16),
                        ft.Text(clp(d['venta'] - d['costo']), size=11,
                                color="green700" if d["venta"] >= d["costo"] else "red700", weight="bold"),
                    ]),
                    padding=ft.Padding(12, 5, 12, 5),
                    bgcolor="grey50", border_radius=6,
                    border=ft.border.all(1, "grey100"),
                ))
            controles.append(ft.Column([cab] + filas_bod, spacing=4))

        self.col_bodegas.controls = controles

    def _render_historial(self, movs, costo_map):
        """Popula col_historial a partir de movimientos y mapa de costos."""
        totales = {"DESPACHO_TECNICO": 0, "CARGA_FURGON": 0, "TRASPASO_INTERNO": 0}
        total_unidades = 0
        for m in movs:
            sku  = m.get("sku", "")
            cu   = m.get("costo_unitario_historico") or costo_map.get(sku, 0)
            cant = m.get("cantidad") or 0
            tipo = m.get("tipo_movimiento", "")
            if tipo in totales:
                totales[tipo] += cu * cant
            total_unidades += cant
        mes  = str(self.dd_mes.value or datetime.now().month).zfill(2)
        anio = str(self.dd_anio.value or datetime.now().year)
        self._historial_kpis = {**totales, "total_unidades": total_unidades, "mes": mes, "anio": anio}
        self.col_historial.controls = [
            tarjeta_movimiento("Despachos a Terreno",  totales["DESPACHO_TECNICO"], "Costo material utilizado",           ft.Icons.HANDYMAN,       "orange600"),
            tarjeta_movimiento("Carga a Furgones",     totales["CARGA_FURGON"],     "Costo transferido a móviles",        ft.Icons.LOCAL_SHIPPING, "purple600"),
            tarjeta_movimiento("Traspasos Internos",   totales["TRASPASO_INTERNO"], "Costo re-distribuido entre bodegas", ft.Icons.SWAP_HORIZ,     "blue600"),
            tarjeta_conteo("Movimientos del Período",  len(movs),                   "Total de operaciones registradas",   ft.Icons.RECEIPT_LONG,   "grey600"),
        ]

    # ════════════════ versiones síncronas (para _carga_inicial) ════════════════
    def _calcular_finanzas(self, sb):
        """Obtiene productos desde la BD y delega el renderizado en _render_valorizacion."""
        from core.database import fetch_all as _fa
        from core.cache import app_cache as _ac
        tipo, valor = self._parse_filtro()
        sel = self.dd_bodega.value or "0"
        productos = list(_ac.fin_productos_raw or _fa(
            "productos",
            "sku, nombre, costo_neto, precio_venta, stock_global, "
            "familia_id, subfamilia_id, familias(nombre), subfamilias(nombre)"
        ))
        bp_raw = _ac.fin_bp_raw or []

        if tipo == "furgon":
            filas = sb.table("furgon_productos").select("sku, cantidad") \
                       .eq("furgon_id", valor).execute().data or []
            stock_map = {r["sku"]: (r.get("cantidad") or 0) for r in filas}
            productos = [p for p in productos if stock_map.get(p["sku"], 0) > 0]
            for p in productos: p["_stock_filtrado"] = stock_map.get(p["sku"], 0)
        elif tipo == "area":
            bodegas_area = [b for b in (_ac.fin_bodegas or [])
                            if (b.get("areas") or {}).get("nombre") == valor]
            stock_map = {}
            for b in bodegas_area:
                for r in _fa("bodega_productos", "sku, cantidad", bodega_id=b["id"]):
                    stock_map[r["sku"]] = stock_map.get(r["sku"], 0) + (r.get("cantidad") or 0)
            productos = [p for p in productos if stock_map.get(p["sku"], 0) > 0]
            for p in productos: p["_stock_filtrado"] = stock_map.get(p["sku"], 0)
        elif tipo == "bodega":
            filas = _fa("bodega_productos", "sku, cantidad", bodega_id=valor)
            stock_map = {r["sku"]: (r.get("cantidad") or 0) for r in filas}
            productos = [p for p in productos if p["sku"] in stock_map]
            for p in productos: p["_stock_filtrado"] = stock_map.get(p["sku"], 0)
        else:
            for p in productos: p["_stock_filtrado"] = _stk(p)

        label = next((o.text for o in self.dd_bodega.options if o.key == sel), "Todas las bodegas")
        self._render_valorizacion(productos, label)
        prods_dict = {p["sku"]: p for p in productos}
        self._render_por_area_bodega(bp_raw, prods_dict)

    def _calcular_historial(self, sb):
        """Obtiene movimientos desde la BD y delega el renderizado en _render_historial."""
        mes  = str(self.dd_mes.value).zfill(2)
        anio = self.dd_anio.value
        fecha_inicio = f"{anio}-{mes}-01T00:00:00"
        m_next = int(mes) + 1
        y_next = int(anio) + (1 if m_next > 12 else 0)
        m_next = m_next if m_next <= 12 else 1
        fecha_fin = f"{y_next}-{str(m_next).zfill(2)}-01T00:00:00"
        tipo, valor = self._parse_filtro()
        q = sb.table("movimientos_inventario").select("*") \
              .gte("fecha", fecha_inicio).lt("fecha", fecha_fin)
        if tipo == "furgon":
            q = q.eq("ubicacion_origen", f"FURGON_{valor}")
        elif tipo == "area":
            from core.cache import app_cache as _ac
            bodegas_area = [b for b in (_ac.fin_bodegas or [])
                            if (b.get("areas") or {}).get("nombre") == valor]
            if bodegas_area:
                q = q.in_("ubicacion_origen", [str(b["id"]) for b in bodegas_area])
        elif tipo == "bodega":
            q = q.eq("ubicacion_origen", valor)
        movs = q.execute().data or []
        skus_usados = {m["sku"] for m in movs if m.get("sku")}
        costo_map: dict = {}
        if skus_usados:
            res_p = sb.table("productos").select("sku, costo_neto") \
                      .in_("sku", list(skus_usados)).execute().data or []
            costo_map = {r["sku"]: (r.get("costo_neto") or 0) for r in res_p}
        self._render_historial(movs, costo_map)

    # ════════════════════════ VALORIZACIÓN ════════════════════════
    def cargar_finanzas(self):
        tipo, valor = self._parse_filtro()
        sel = self.dd_bodega.value or "0"
        def _run():
            try:
                from core.cache import app_cache as _ac
                from core.database import fetch_all
                sb = get_sb()
                productos = list(_ac.fin_productos_raw or fetch_all(
                    "productos",
                    "sku, nombre, costo_neto, precio_venta, stock_global, "
                    "familia_id, subfamilia_id, familias(nombre), subfamilias(nombre)"
                ))

                if tipo == "furgon":
                    filas = sb.table("furgon_productos").select("sku, cantidad") \
                               .eq("furgon_id", valor).execute().data or []
                    stock_map = {r["sku"]: (r.get("cantidad") or 0) for r in filas}
                    productos = [p for p in productos if stock_map.get(p["sku"], 0) > 0]
                    for p in productos: p["_stock_filtrado"] = stock_map.get(p["sku"], 0)
                elif tipo == "area":
                    bodegas_area = [b for b in (_ac.fin_bodegas or [])
                                    if (b.get("areas") or {}).get("nombre") == valor]
                    stock_map: dict = {}
                    for b in bodegas_area:
                        for r in fetch_all("bodega_productos", "sku, cantidad", bodega_id=b["id"]):
                            stock_map[r["sku"]] = stock_map.get(r["sku"], 0) + (r.get("cantidad") or 0)
                    productos = [p for p in productos if stock_map.get(p["sku"], 0) > 0]
                    for p in productos: p["_stock_filtrado"] = stock_map.get(p["sku"], 0)
                elif tipo == "bodega":
                    filas = fetch_all("bodega_productos", "sku, cantidad", bodega_id=valor)
                    stock_map = {r["sku"]: (r.get("cantidad") or 0) for r in filas}
                    productos = [p for p in productos if p["sku"] in stock_map]
                    for p in productos: p["_stock_filtrado"] = stock_map.get(p["sku"], 0)
                else:
                    for p in productos: p["_stock_filtrado"] = _stk(p)

                def stk(p): return p.get("_stock_filtrado", 0)
                total_costo = sum(stk(p) * (p.get("costo_neto") or 0) for p in productos)
                total_venta = sum(stk(p) * (p.get("precio_venta") or 0) for p in productos)
                self._resumen_global = {"costo": total_costo, "venta": total_venta}

                label = next((o.text for o in self.dd_bodega.options if o.key == sel), "Todas las bodegas")
                self.col_global.controls = [
                    tarjeta_resumen(label, total_costo, total_venta,
                                    ft.Icons.ACCOUNT_BALANCE_WALLET, "blue700"),
                ]

                familias: dict = {}
                for p in productos:
                    fam = _fam(p); sub = _sub(p) or "Sin Subfamilia"
                    costo = stk(p) * (p.get("costo_neto") or 0)
                    venta = stk(p) * (p.get("precio_venta") or 0)
                    if fam not in familias:
                        familias[fam] = {"costo": 0, "venta": 0, "subs": {}}
                    familias[fam]["costo"] += costo; familias[fam]["venta"] += venta
                    if sub not in familias[fam]["subs"]:
                        familias[fam]["subs"][sub] = {"costo": 0, "venta": 0}
                    familias[fam]["subs"][sub]["costo"] += costo
                    familias[fam]["subs"][sub]["venta"] += venta
                self._datos_familias = familias

                colores = ["teal700","purple700","orange700","red700","indigo700","cyan700","blue700","green700"]
                controles = []
                for i, (fam, d) in enumerate(sorted(familias.items())):
                    color = colores[i % len(colores)]
                    cab = ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.FOLDER, color=color, size=18),
                            ft.Text(fam, weight="bold", size=13, color="grey900", expand=True),
                            ft.Text(f"Costo: ${d['costo']:,.0f}", size=11, color="blue800", weight="bold"),
                            ft.Container(width=12),
                            ft.Text(f"Venta: ${d['venta']:,.0f}", size=11, color="green700", weight="bold"),
                            ft.Container(width=12),
                            ft.Text(f"Margen: ${d['venta']-d['costo']:,.0f}", size=11,
                                    color="green700" if d['venta'] >= d['costo'] else "red700", weight="bold"),
                        ]),
                        padding=ft.Padding(14, 10, 14, 10),
                        bgcolor=ft.Colors.with_opacity(0.06, color),
                        border_radius=10,
                        border=ft.Border(left=ft.BorderSide(4, color)),
                    )
                    subs_ctrl = [fila_sub(sub, sd["costo"], sd["venta"])
                                 for sub, sd in sorted(d["subs"].items())
                                 if sub != "Sin Subfamilia" or len(d["subs"]) > 1]
                    controles.append(ft.Column([cab] + subs_ctrl, spacing=4))
                self.col_familias.controls = controles

                prods_dict = {p["sku"]: p for p in productos}
                bp_raw = _ac.fin_bp_raw or []
                self._render_por_area_bodega(bp_raw, prods_dict)

                if self.page_ref:
                    self.col_global.update()
                    self.col_familias.update()
                    self.col_bodegas.update()

            except Exception as ex:
                import traceback; traceback.print_exc()
                self.col_global.controls = [
                    ft.Container(
                        content=ft.Text(f"❌ Error al cargar: {ex}", color="red700", size=12),
                        padding=12, bgcolor="red50", border_radius=8,
                    )
                ]
                if self.page_ref: self.col_global.update()
        hilo(_run)

    # ════════════════════════ HISTORIAL ════════════════════════
    def cargar_historial(self):
        ftipo, fvalor = self._parse_filtro()  # renombrado para evitar colision con 'tipo' del loop
        def _run():
            try:
                mes  = str(self.dd_mes.value).zfill(2)
                anio = self.dd_anio.value
                fecha_inicio = f"{anio}-{mes}-01T00:00:00"
                m_next = int(mes) + 1
                y_next = int(anio) + (1 if m_next > 12 else 0)
                m_next = m_next if m_next <= 12 else 1
                fecha_fin = f"{y_next}-{str(m_next).zfill(2)}-01T00:00:00"

                sb = get_sb()
                q = sb.table("movimientos_inventario").select("*") \
                      .gte("fecha", fecha_inicio).lt("fecha", fecha_fin)
                if ftipo == "furgon":
                    q = q.eq("ubicacion_origen", f"FURGON_{fvalor}")
                elif ftipo == "area":
                    from core.cache import app_cache as _ac
                    bodegas_area = [b for b in (_ac.fin_bodegas or [])
                                    if (b.get("areas") or {}).get("nombre") == fvalor]
                    if bodegas_area:
                        q = q.in_("ubicacion_origen", [str(b["id"]) for b in bodegas_area])
                elif ftipo == "bodega":
                    q = q.eq("ubicacion_origen", fvalor)
                movs = q.execute().data or []

                skus_usados = {m["sku"] for m in movs if m.get("sku")}
                costo_map = {}
                if skus_usados:
                    res_p = sb.table("productos").select("sku, costo_neto") \
                              .in_("sku", list(skus_usados)).execute().data or []
                    costo_map = {r["sku"]: (r.get("costo_neto") or 0) for r in res_p}

                totales = {
                    "DESPACHO_TECNICO": 0,
                    "CARGA_FURGON":     0,
                    "TRASPASO_INTERNO": 0,
                }
                total_unidades = 0
                for m in movs:
                    sku      = m.get("sku", "")
                    cu       = m.get("costo_unitario_historico") or costo_map.get(sku, 0)
                    cant     = m.get("cantidad") or 0
                    val      = cu * cant
                    tipo_mov = m.get("tipo_movimiento", "")
                    if tipo_mov in totales:
                        totales[tipo_mov] += val
                    total_unidades += cant

                self._historial_kpis = {**totales, "total_unidades": total_unidades, "mes": mes, "anio": anio}

                self.col_historial.controls = [
                    tarjeta_movimiento("Despachos a Terreno",  totales["DESPACHO_TECNICO"], "Costo material utilizado",          ft.Icons.HANDYMAN,     "orange600"),
                    tarjeta_movimiento("Carga a Furgones",     totales["CARGA_FURGON"],     "Costo transferido a móviles",       ft.Icons.LOCAL_SHIPPING, "purple600"),
                    tarjeta_movimiento("Traspasos Internos",   totales["TRASPASO_INTERNO"], "Costo re-distribuido entre bodegas", ft.Icons.SWAP_HORIZ,  "blue600"),
                    tarjeta_conteo("Movimientos del Período",  len(movs),                   "Total de operaciones registradas",  ft.Icons.RECEIPT_LONG, "grey600"),
                ]
                if self.page_ref: self.col_historial.update()

            except Exception as ex:
                self.col_historial.controls = [ft.Text(f"❌ Error historial: {ex}", color="red")]
                if self.page_ref: self.col_historial.update()
        hilo(_run)

    # ════════════════════════ EXPORTAR PDF ════════════════════════
    def exportar_pdf(self, e=None):
        if not self._datos_familias:
            self.mostrar_snack("⚠️ Genera el reporte primero", "orange")
            return

        def _run():
            try:
                from fpdf import FPDF

                def txt(t): return str(t).encode("latin-1", "replace").decode("latin-1")

                pdf = FPDF(orientation="P", unit="mm", format="A4")
                pdf.add_page()

                # ── Portada ──
                pdf.set_font("Arial", "B", 18)
                pdf.cell(0, 12, txt("SICAV ERP — Reporte Financiero"), ln=True, align="C")
                pdf.set_font("Arial", "", 10)
                pdf.cell(0, 7, txt(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Usuario: {estado.usuario_actual.get('nombre','')}"), ln=True, align="C")
                pdf.ln(4)
                pdf.set_draw_color(180, 180, 180)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(6)

                # ── Resumen global ──
                r = self._resumen_global
                pdf.set_font("Arial", "B", 13)
                pdf.cell(0, 8, txt("Valorización Total del Inventario"), ln=True)
                pdf.set_font("Arial", "", 11)
                pdf.cell(60, 7, txt(f"Costo total:  ${r.get('costo',0):>18,.0f}"), ln=True)
                pdf.cell(60, 7, txt(f"Venta total:  ${r.get('venta',0):>18,.0f}"), ln=True)
                pdf.cell(60, 7, txt(f"Margen total: ${r.get('venta',0)-r.get('costo',0):>18,.0f}"), ln=True)
                pdf.ln(6)

                # ── Historial si existe ──
                if self._historial_kpis:
                    k = self._historial_kpis
                    pdf.set_font("Arial", "B", 13)
                    pdf.cell(0, 8, txt(f"Movimientos {k.get('mes','')}/{k.get('anio','')}"), ln=True)
                    pdf.set_font("Arial", "", 10)
                    for label, key in [("Despachos", "DESPACHO_TECNICO"),
                                       ("Carga Furgones", "CARGA_FURGON"), ("Traspasos Internos", "TRASPASO_INTERNO")]:
                        pdf.cell(0, 6, txt(f"  {label}: {clp(k.get(key,0))}"), ln=True)
                    pdf.cell(0, 6, txt(f"  Total operaciones: {k.get('total_unidades',0):,} uds"), ln=True)
                    pdf.ln(4)

                # ── Por familia ──
                pdf.set_font("Arial", "B", 13)
                pdf.cell(0, 8, txt("Valorización por Familia y Subfamilia"), ln=True)
                pdf.ln(2)

                # Encabezado tabla
                def encabezado():
                    pdf.set_fill_color(21, 101, 192)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("Arial", "B", 9)
                    pdf.cell(80, 7, "Familia / Subfamilia", border=1, fill=True)
                    pdf.cell(35, 7, "Costo ($)",    border=1, fill=True, align="R")
                    pdf.cell(35, 7, "Venta ($)",    border=1, fill=True, align="R")
                    pdf.cell(35, 7, "Margen ($)",   border=1, fill=True, align="R")
                    pdf.ln()
                    pdf.set_text_color(0, 0, 0)

                encabezado()

                for fam, d in sorted(self._datos_familias.items()):
                    # Nueva página si queda poco espacio
                    if pdf.get_y() > 260:
                        pdf.add_page()
                        encabezado()

                    margen = d["venta"] - d["costo"]
                    pdf.set_fill_color(230, 240, 255)
                    pdf.set_font("Arial", "B", 9)
                    pdf.cell(80, 7, txt(fam[:40]), border=1, fill=True)
                    pdf.cell(35, 7, clp(d['costo']), border=1, fill=True, align="R")
                    pdf.cell(35, 7, clp(d['venta']), border=1, fill=True, align="R")
                    pdf.cell(35, 7, clp(margen),     border=1, fill=True, align="R")
                    pdf.ln()

                    pdf.set_font("Arial", "", 8)
                    for sub, sd in sorted(d["subs"].items()):
                        if sub != "Sin Subfamilia" or len(d["subs"]) > 1:
                            if pdf.get_y() > 260:
                                pdf.add_page(); encabezado()
                            sm = sd["venta"] - sd["costo"]
                            pdf.cell(80, 6, txt(f"   ↳ {sub[:37]}"), border=1)
                            pdf.cell(35, 6, clp(sd['costo']), border=1, align="R")
                            pdf.cell(35, 6, clp(sd['venta']), border=1, align="R")
                            pdf.cell(35, 6, clp(sm),          border=1, align="R")
                            pdf.ln()

                import subprocess as _sp, datetime as _dt
                _fname = f"/tmp/Finanzas_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                open(_fname, 'wb').write(pdf.output())
                _sp.Popen(['open', _fname])
                registrar_auditoria(estado.usuario_actual.get("nombre", ""), "EXPORTAR FINANZAS PDF", _fname)
                self.mostrar_snack("✅ PDF exportado correctamente.", "green700")
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al exportar: {ex}", "red")
        hilo(_run)