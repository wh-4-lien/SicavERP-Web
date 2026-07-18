# vistas/mi_furgon.py
import flet as ft
import datetime
from core.database import (
    get_sb, fetch_todos_furgones, fetch_tipos_trabajo,
    registrar_despacho_tecnico, registrar_despacho_desde_furgon,
)
from core.estado import estado
from core.utilidades import hilo, registrar_auditoria
from core.widgets import BuscadorProducto


def _label_bodega(b: dict) -> str:
    area = (b.get("areas") or {}).get("nombre") or ""
    return f"[{area}] {b['nombre']}" if area else b["nombre"]

class VistaMiFurgon(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.furgon_actual = None
        
        # Almacenamiento de datos en memoria para búsquedas reactivas
        self.datos_repuestos = []
        self.datos_herramientas = []
        
        self.construir_ui()

    def mostrar_snack(self, mensaje, tipo_o_color="success"):
        from utils.ui_helpers import mostrar_snack as _snack
        _snack(self.page_ref, mensaje, tipo_o_color)

    def construir_ui(self):
        # ── Cabecera ──
        self.txt_titulo = ft.Text(" Furgones & Equipos", size=24, weight="bold", color="blue900")
        self.txt_info_furgon = ft.Text("Buscando asignación...", size=14, color="grey600")

        # ── Selector de furgón (Vista Administrador) ──
        self.sel_furgon_admin = ft.Dropdown(
            label="Ver furgón", width=260, height=50, options=[],
            visible=False,
        )
        self.sel_furgon_admin.on_change = lambda e: self.cargar_furgon_por_id(e.control.value)
        
        # ── Buscadores e Indicadores Financieros Nativos ──
        self.in_buscar_rep = ft.TextField(
            label="Buscar por SKU o nombre...", width=300, height=50, prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self.filtrar_tablas()
        )
        self.dd_orden_rep = ft.Dropdown(
            label="Ordenar", width=180, height=50,
            value="alfa_az",
            options=[
                ft.dropdown.Option("alfa_az",    "A → Z"),
                ft.dropdown.Option("alfa_za",    "Z → A"),
                ft.dropdown.Option("stock_desc", "Mayor stock"),
                ft.dropdown.Option("stock_asc",  "Menor stock"),
            ],
        )
        self.dd_orden_rep.on_change = lambda e: self.filtrar_tablas()
        self.in_buscar_her = ft.TextField(
            label="Buscar por SKU o nombre...", width=300, height=50, prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self.filtrar_tablas()
        )
        
        self.txt_total_valor_repuestos   = ft.Text("Suma Total: $0", size=15, weight="bold", color="blue900")
        self.txt_total_valor_herramientas = ft.Text("Suma Total: $0", size=15, weight="bold", color="orange900")
        
        # ── Tablas Estructurales ──
        self.tabla_repuestos = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("SKU", weight="bold")),
                ft.DataColumn(ft.Text("Repuesto", weight="bold")),
                ft.DataColumn(ft.Text("Cantidad", weight="bold"), numeric=True),
                ft.DataColumn(ft.Text("Valor Unit.", weight="bold"), numeric=True),
                ft.DataColumn(ft.Text("Fecha Entrega", weight="bold")),
                ft.DataColumn(ft.Text("Valor Total", weight="bold"), numeric=True),
            ], rows=[], border=ft.border.all(1, "grey200"), border_radius=8, heading_row_color=ft.Colors.with_opacity(0.04, "blue")
        )
        
        self.tabla_herramientas = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("SKU", weight="bold")),
                ft.DataColumn(ft.Text("Herramienta", weight="bold")),
                ft.DataColumn(ft.Text("Cantidad", weight="bold"), numeric=True),
                ft.DataColumn(ft.Text("Valor Unit.", weight="bold"), numeric=True),
                ft.DataColumn(ft.Text("Fecha Entrega", weight="bold")),
                ft.DataColumn(ft.Text("Valor Total", weight="bold"), numeric=True),
            ], rows=[], border=ft.border.all(1, "grey200"), border_radius=8, heading_row_color=ft.Colors.with_opacity(0.04, "orange")
        )

        # ── NUEVOS PANELES DE ACCIÓN (Despacho e Importación) ──
        
        # TAB 3: Trabajo Terreno (Descontar)
        self.dd_bodega_despacho = ft.Dropdown(label="Seleccionar Bodega Origen", expand=1)
        self.buscador_despacho = BuscadorProducto(
            label="SKU o Nombre", expand=1,
            on_seleccionar=self._on_despacho_seleccionado,
        )
        self._txt_preview_desp = ft.Text("", size=12, weight="bold")
        self._cont_preview_desp = ft.Container(
            content=self._txt_preview_desp, visible=False,
            padding=ft.Padding(12, 6, 12, 6), border_radius=8,
            bgcolor="blue50", border=ft.Border(left=ft.BorderSide(3, "blue400")),
        )
        self.in_cant_despacho = ft.TextField(label="Cantidad", width=120, value="1")
        self.dd_tipo_trabajo = ft.Dropdown(label="Tipo de Trabajo", expand=1)
        self.in_comentario = ft.TextField(label="Comentario Obligatorio (Ej. Cliente o N° Orden)", expand=True)
        self.btn_despachar = ft.ElevatedButton("REGISTRAR DESCUENTO", bgcolor="blue800", color="white", on_click=self.accion_despachar)

        self.cont_despacho = ft.Container(
            content=ft.Column([
                ft.Text("👷 Consumo de Stock a Terreno", size=18, weight="bold", color="blue900"),
                ft.Row([self.dd_bodega_despacho, self.buscador_despacho, self.in_cant_despacho]),
                self._cont_preview_desp,
                ft.Row([self.dd_tipo_trabajo, self.in_comentario]),
                ft.Row([self.btn_despachar], alignment="end")
            ], spacing=15), expand=True, visible=False, padding=20
        )

        # ── Selectores de Pestaña Customizados ──
        self.btn_tab_rep = ft.Container(content=ft.Row([ft.Icon(ft.Icons.INVENTORY_2, size=18), ft.Text("Repuestos", weight="bold")], spacing=6), padding=15, border=ft.Border(bottom=ft.BorderSide(3, "blue900")), ink=True, on_click=lambda e: self.cambiar_tab("repuestos", e))
        self.btn_tab_her = ft.Container(content=ft.Row([ft.Icon(ft.Icons.HANDYMAN, size=18), ft.Text("Herramientas", weight="bold")], spacing=6), padding=15, border=ft.Border(bottom=ft.BorderSide(3, "transparent")), ink=True, on_click=lambda e: self.cambiar_tab("herramientas", e))
        self.btn_tab_desp = ft.Container(content=ft.Row([ft.Icon(ft.Icons.WORK, size=18), ft.Text("Descontar Terreno", weight="bold")], spacing=6), padding=15, border=ft.Border(bottom=ft.BorderSide(3, "transparent")), ink=True, on_click=lambda e: self.cambiar_tab("despacho", e))

        self.row_tabs = ft.Row([self.btn_tab_rep, self.btn_tab_her, self.btn_tab_desp], spacing=0, scroll=ft.ScrollMode.AUTO)
        
        self.cont_repuestos = ft.Container(
            content=ft.Column([
                ft.Divider(height=10, color="transparent"),
                ft.Row([self.in_buscar_rep, self.dd_orden_rep, self.txt_total_valor_repuestos], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Column([ft.Row([self.tabla_repuestos], scroll=ft.ScrollMode.ALWAYS)], scroll=ft.ScrollMode.ALWAYS, expand=True)
            ]), expand=True, visible=True
        )
        
        self.cont_herramientas = ft.Container(
            content=ft.Column([
                ft.Divider(height=10, color="transparent"),
                ft.Row([self.in_buscar_her, self.txt_total_valor_herramientas], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Column([ft.Row([self.tabla_herramientas], scroll=ft.ScrollMode.ALWAYS)], scroll=ft.ScrollMode.ALWAYS, expand=True)
            ]), expand=True, visible=False
        )
        
        self.cont_tabs = ft.Container(
            content=ft.Column([
                self.row_tabs,
                ft.Divider(height=1, color="grey300"),
                self.cont_repuestos,
                self.cont_herramientas,
                self.cont_despacho,
            ], expand=True), expand=True, visible=False
        )
        
        self.cont_mensaje = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.DIRECTIONS_CAR_FILLED, size=80, color="grey300"),
                ft.Text("No registras furgón asignado", size=20, weight="bold", color="grey600"),
                ft.Text("Solicita al administrador la asignación de una bodega móvil en el panel general.", size=14, color="grey500")
            ], horizontal_alignment="center", alignment=ft.MainAxisAlignment.CENTER, spacing=10), expand=True, visible=False
        )

        from utils.ui_helpers import sandwich

        _header = ft.Row([
            ft.Column([self.txt_titulo, self.txt_info_furgon], expand=True, spacing=2),
            self.sel_furgon_admin,
            ft.ElevatedButton(
                "Refrescar", icon=ft.Icons.REFRESH,
                on_click=lambda _: self.inicializar(),
                height=40, tooltip="Recargar datos del furgón",
            ),
        ])

        _body = ft.Container(
            content=ft.Column([self.cont_tabs, self.cont_mensaje], expand=True, scroll=ft.ScrollMode.AUTO),
            padding=20, bgcolor="white", border_radius=12, border=ft.border.all(1, "grey200"), expand=True,
        )

        self.content = sandwich(_header, _body)

    def _on_despacho_seleccionado(self, prod):
        bodega_sel = self.dd_bodega_despacho.value or ""
        if bodega_sel.startswith("furgon_"):
            entrada = next((r for r in self.datos_repuestos if r["sku"] == prod["sku"]), None)
            stk = (entrada["cantidad"] or 0) if entrada else 0
        else:
            stk = prod.get("stock_global") or 0
        color_stk = "red600" if stk == 0 else "orange600" if stk <= 3 else "green700"
        self._txt_preview_desp.value = f"📦  {prod['nombre']}   ·   SKU: {prod['sku']}   ·   Stock: {stk} uds"
        self._txt_preview_desp.color = "blue900"
        self._cont_preview_desp.bgcolor = "blue50"
        self._cont_preview_desp.border = ft.Border(left=ft.BorderSide(3, color_stk))
        self._cont_preview_desp.visible = True
        if self.page_ref: self._cont_preview_desp.update()

    def cambiar_tab(self, tab, e):
        # Resetear bordes
        for btn in [self.btn_tab_rep, self.btn_tab_her, self.btn_tab_desp]:
            btn.border = ft.Border(bottom=ft.BorderSide(3, "transparent"))

        e.control.border = ft.Border(bottom=ft.BorderSide(3, "blue900"))

        # Ocultar todos
        self.cont_repuestos.visible = False
        self.cont_herramientas.visible = False
        self.cont_despacho.visible = False

        if tab == "repuestos": self.cont_repuestos.visible = True
        elif tab == "herramientas": self.cont_herramientas.visible = True
        elif tab == "despacho": self.cont_despacho.visible = True

        if self.page_ref:
            self.cont_repuestos.update()
            self.cont_herramientas.update()
            self.cont_despacho.update()

    def pre_cargar_si_cache_listo(self):
        from core.cache import app_cache
        if app_cache.inv_ready.is_set() and not getattr(self, '_bodegas_listas', False):
            bodegas = app_cache.inv_bodegas or []
            if bodegas:
                self.dd_bodega_despacho.options = [
                    ft.dropdown.Option(key=str(b["id"]), text=_label_bodega(b)) for b in bodegas
                ]
                self._bodegas_listas = True
        if app_cache.cat_ready.is_set() and not getattr(self, '_tipos_listos', False):
            tipos = app_cache.cat_tipos or []
            if tipos:
                self.dd_tipo_trabajo.options = [
                    ft.dropdown.Option(key=str(t["id"]), text=t["nombre"]) for t in tipos
                ]
                self._tipos_listos = True
        if getattr(self, '_bodegas_listas', False) and getattr(self, '_tipos_listos', False) and not getattr(self, '_combos_logueados', False):
            self._combos_logueados = True
            print("[MI_FURGON] combos pre-cargados")

    def inicializar(self):
        def _run():
            try:
                if not getattr(self, '_bodegas_listas', False):
                    res_bodegas = get_sb().table("bodegas").select("id, nombre, areas(nombre)").execute()
                    opc_bod = [ft.dropdown.Option(key=str(b["id"]), text=_label_bodega(b)) for b in (res_bodegas.data or [])]
                    self.dd_bodega_despacho.options = opc_bod

                if not getattr(self, '_tipos_listos', False):
                    tipos = fetch_tipos_trabajo()
                    self.dd_tipo_trabajo.options = [
                        ft.dropdown.Option(key=str(t["id"]), text=t["nombre"]) for t in tipos
                    ]

                if estado.es_admin: self.cargar_lista_furgones_admin()
                else:
                    self.sel_furgon_admin.visible = False
                    self.cargar_datos_furgon()
            except Exception as e:
                self.mostrar_snack(f"❌ Error al inicializar: {e}", "red700")
        hilo(_run)

    def cargar_lista_furgones_admin(self):
        try:
            furgones = fetch_todos_furgones()
            self.sel_furgon_admin.visible = True
            self.sel_furgon_admin.options = [
                ft.dropdown.Option(str(f["id"]), f"{f['nombre']} ({f.get('tecnico_usuario') or 'Sin asignar'})") for f in furgones
            ]
            if furgones:
                ids_disponibles = [str(f["id"]) for f in furgones]
                seleccionado = self.sel_furgon_admin.value if self.sel_furgon_admin.value in ids_disponibles else ids_disponibles[0]
                self.sel_furgon_admin.value = seleccionado
                if self.page_ref:
                    self.page_ref.update()
                self.cargar_furgon_por_id(seleccionado)
            else:
                self.furgon_actual = None
                self.txt_titulo.value = " Furgones vacíos"
                self.txt_info_furgon.value = "No se registran bodegas móviles registradas."
                self.cont_mensaje.visible = True; self.cont_tabs.visible = False
                if self.page_ref:
                    self.page_ref.update()
        except Exception as ex: self.mostrar_snack(f"❌ Error al cargar furgones: {ex}", "red700")

    def _agregar_furgon_a_dd_bodega(self):
        """Prepend the current furgon as first option in the bodega dropdown."""
        f = self.furgon_actual
        if not f:
            return
        fid = f["id"]
        fname = f["nombre"]
        opcion_furgon = ft.dropdown.Option(key=f"furgon_{fid}", text=f"🚐 {fname} (este furgón)")
        opciones_actuales = [o for o in self.dd_bodega_despacho.options if not o.key.startswith("furgon_")]
        self.dd_bodega_despacho.options = [opcion_furgon] + opciones_actuales
        if self.page_ref:
            try:
                self.dd_bodega_despacho.update()
            except Exception:
                pass

    def cargar_furgon_por_id(self, furgon_id):
        if not furgon_id: return
        def _run():
            try:
                res_f = get_sb().table("furgones").select("*").eq("id", furgon_id).execute()
                if res_f.data:
                    self.furgon_actual = res_f.data[0]
                    self.txt_titulo.value = f" Furgón: {self.furgon_actual['nombre']}"
                    self.txt_info_furgon.value = f"{self.furgon_actual.get('descripcion') or ''} | Técnico: {self.furgon_actual.get('tecnico_usuario') or 'Sin asignar'}"
                    self.cont_mensaje.visible = False; self.cont_tabs.visible = True
                    self._agregar_furgon_a_dd_bodega()
                    if self.page_ref:
                        self.page_ref.update()
                    self.cargar_inventario_furgon()
            except Exception as ex: self.mostrar_snack(f"❌ Error al cargar furgón: {ex}", "red700")
        hilo(_run)

    def cargar_datos_furgon(self):
        def _run():
            try:
                usuario_login = str(estado.usuario_actual.get("usuario", "")).strip()
                res_f = get_sb().table("furgones").select("*").ilike("tecnico_usuario", usuario_login).execute()
                self.furgon_actual = res_f.data[0] if res_f.data else None
                if self.furgon_actual:
                    self.txt_titulo.value = f" Mi Furgón: {self.furgon_actual['nombre']}"
                    self.txt_info_furgon.value = f"{self.furgon_actual.get('descripcion') or ''} | Técnico: {estado.usuario_actual.get('nombre', usuario_login)}"
                    self.cont_mensaje.visible = False; self.cont_tabs.visible = True
                    self._agregar_furgon_a_dd_bodega()
                    if self.page_ref:
                        self.page_ref.update()
                    self.cargar_inventario_furgon()
                else:
                    self.furgon_actual = None
                    self.txt_titulo.value = " Mi Furgón"; self.txt_info_furgon.value = "Sin asignación"
                    self.cont_mensaje.visible = True; self.cont_tabs.visible = False
                    if self.page_ref:
                        self.page_ref.update()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al cargar datos del furgón: {ex}", "red700")
        hilo(_run)

    def cargar_inventario_furgon(self):
        if not self.furgon_actual: return
        def _run():
            try:
                fid = self.furgon_actual["id"]
                res_p = get_sb().table("furgon_productos").select("cantidad, sku, productos(nombre, precio_venta, familias(nombre))").eq("furgon_id", fid).execute()
                res_h = get_sb().table("herramientas_furgo").select("id, descripcion, modelo, stock, valor_unitario, fecha_entrega").eq("furgon_id", fid).execute()
                
                self.datos_repuestos.clear()
                self.datos_herramientas.clear()

                for p in (res_p.data or []):
                    sku = p.get("sku", "")
                    cant = p.get("cantidad", 0) or 0
                    prod = p.get("productos") or {}
                    nom = prod.get("nombre", sku)
                    fam_obj = prod.get("familias") or {}
                    fam = (fam_obj.get("nombre") if isinstance(fam_obj, dict) else "").strip().upper()
                    precio = prod.get("precio_venta", 0) or 0

                    item = {
                        "sku": sku, "nombre": nom, "cantidad": cant,
                        "valor_unitario": precio, "fecha_entrega": "—", "valor_total": cant * precio,
                    }
                    if "HERRAMIENTA" in fam: self.datos_herramientas.append(item)
                    else: self.datos_repuestos.append(item)

                for h in (res_h.data or []):
                    modelo_str = f" ({h.get('modelo')})" if h.get("modelo") else ""
                    cant = h.get("stock", 0) or 0
                    v_unit = h.get("valor_unitario", 0) or 0
                    fecha = h.get("fecha_entrega") or "—"
                    
                    if fecha != "—":
                        try: fecha = datetime.date.fromisoformat(fecha).strftime("%d/%m/%Y")
                        except: pass

                    self.datos_herramientas.append({
                        "sku": f"HERR-{h['id']}",
                        "nombre": f"{h.get('descripcion', 'Sin descripción')}{modelo_str}",
                        "text_nombre": h.get('descripcion', 'Sin descripción'),
                        "cantidad": cant, "valor_unitario": v_unit,
                        "fecha_entrega": fecha, "valor_total": cant * v_unit
                    })
                
                self.datos_repuestos.sort(key=lambda x: x["nombre"])  # orden inicial; filtrar_tablas aplica el orden seleccionado
                self.datos_herramientas.sort(key=lambda x: x["nombre"])
                self.filtrar_tablas()
            except Exception as ex: self.mostrar_snack(f"❌ Error al cargar inventario: {ex}", "red700")
        hilo(_run)

    def filtrar_tablas(self):
        busq_rep = self.in_buscar_rep.value.strip().lower()
        busq_her = self.in_buscar_her.value.strip().lower()

        orden = getattr(self, "dd_orden_rep", None)
        orden_val = orden.value if orden else "alfa_az"
        if orden_val == "alfa_az":
            datos_rep = sorted(self.datos_repuestos, key=lambda x: x["nombre"].lower())
        elif orden_val == "alfa_za":
            datos_rep = sorted(self.datos_repuestos, key=lambda x: x["nombre"].lower(), reverse=True)
        elif orden_val == "stock_desc":
            datos_rep = sorted(self.datos_repuestos, key=lambda x: x["cantidad"], reverse=True)
        elif orden_val == "stock_asc":
            datos_rep = sorted(self.datos_repuestos, key=lambda x: x["cantidad"])
        else:
            datos_rep = self.datos_repuestos

        def _crear_filas(datos, filtro, es_herramienta=False):
            filas = []
            total_valor_visible = 0
            for d in datos:
                nombre_busqueda = d.get("text_nombre", d["nombre"]).lower()
                if filtro and filtro not in d["sku"].lower() and filtro not in nombre_busqueda: continue
                
                color_cant = "red700" if d["cantidad"] == 0 else "orange700" if d["cantidad"] <= 2 else "green700"
                lbl_cant = ft.Container(
                    content=ft.Text(str(d["cantidad"]), weight="bold", color="white", size=12),
                    bgcolor=color_cant, border_radius=12, padding=ft.Padding(10, 4, 10, 4)
                )
                
                total_valor_visible += d["valor_total"]
                
                celdas = [
                    ft.DataCell(ft.Text(d["sku"], weight="bold", color="blue900" if not es_herramienta else "orange900", size=13)),
                    ft.DataCell(ft.Text(d["nombre"], size=13, color="grey800")),
                    ft.DataCell(lbl_cant),
                    ft.DataCell(ft.Text(f"${d.get('valor_unitario', 0):,.0f}", size=13, color="grey800")),
                ]

                if es_herramienta:
                    pass  # valor_unitario ya incluido arriba
                    
                celdas.extend([
                    ft.DataCell(ft.Text(d["fecha_entrega"], size=13, color="grey700")),
                    ft.DataCell(ft.Text(f"${d['valor_total']:,.0f}", size=13, color="grey800", weight="bold")),
                ])
                filas.append(ft.DataRow(cells=celdas))
            return filas, total_valor_visible

        filas_rep, total_rep = _crear_filas(datos_rep, busq_rep, es_herramienta=False)
        self.tabla_repuestos.rows = filas_rep
        self.txt_total_valor_repuestos.value = f"Suma Total: ${total_rep:,.0f}"

        filas_her, total_her = _crear_filas(self.datos_herramientas, busq_her, es_herramienta=True)
        self.tabla_herramientas.rows = filas_her
        self.txt_total_valor_herramientas.value = f"Suma Total: ${total_her:,.0f}"

        if self.page_ref:
            try:
                self.tabla_repuestos.update()
                self.txt_total_valor_repuestos.update()
                self.tabla_herramientas.update()
                self.txt_total_valor_herramientas.update()
            except Exception:
                self.page_ref.update()

    # --- ACCIONES DE TERRENO Y FURGON ---
    def accion_despachar(self, e):
        bodega_id = self.dd_bodega_despacho.value
        texto_sku = self.buscador_despacho.value.strip()
        tipo = self.dd_tipo_trabajo.value
        comentario = self.in_comentario.value.strip()

        try: cant = int(self.in_cant_despacho.value.strip())
        except: cant = 0

        if not all([bodega_id, texto_sku, tipo, comentario]) or cant <= 0:
            self.mostrar_snack("⚠️ Todos los campos son obligatorios.", "orange")
            return

        def _run():
            try:
                sku = texto_sku
                res_check = get_sb().table("productos").select("sku").eq("sku", texto_sku).execute()
                if not res_check.data:
                    self.mostrar_snack(f"❌ '{texto_sku}' no encontrado. Escribe el nombre y selecciona de la lista.", "red700")
                    return
                usuario_login = estado.usuario_actual.get("usuario", "")
                usuario_nombre = estado.usuario_actual.get("nombre", "Tecnico")
                if bodega_id.startswith("furgon_"):
                    fid = int(bodega_id.split("_")[1])
                    registrar_despacho_desde_furgon(sku, fid, cant, int(tipo), comentario, usuario_login, usuario_nombre)
                else:
                    registrar_despacho_tecnico(sku, int(bodega_id), cant, int(tipo), comentario, usuario_login, usuario_nombre)
                self.mostrar_snack(f"✅ Trabajo guardado y stock descontado.", "blue700")
                self.buscador_despacho.limpiar()
                self.in_cant_despacho.value = "1"; self.in_comentario.value = ""
                self._cont_preview_desp.visible = False
                if self.page_ref:
                    self.in_cant_despacho.update()
                    self.in_comentario.update()
                    self._cont_preview_desp.update()
                self.cargar_inventario_furgon()
            except Exception as ex: self.mostrar_snack(f"❌ Error: {ex}", "red700")
        hilo(_run)

