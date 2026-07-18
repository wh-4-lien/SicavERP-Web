# vistas/gestion_comercial.py
import flet as ft
import os
from core.database import get_sb, cache_invalidate
from core.estado import estado
from core.utilidades import hilo, registrar_auditoria
from core.widgets import BuscadorProducto


def _label_bodega(b: dict) -> str:
    area = (b.get("areas") or {}).get("nombre") or ""
    return f"[{area}] {b['nombre']}" if area else b["nombre"]

class VistaComercial(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.construir_ui()

    def mostrar_snack(self, mensaje, tipo_o_color="success"):
        from utils.ui_helpers import mostrar_snack as _snack
        _snack(self.page_ref, mensaje, tipo_o_color)

    def mostrar_dialogo(self, titulo, mensaje, icono=ft.Icons.INFO, color_icono="blue700", detalle=""):
        """Informacional: muestra como snack de tipo info."""
        texto_completo = f"{titulo}: {mensaje}"
        if detalle:
            texto_completo += f" — {detalle}"
        self.mostrar_snack(texto_completo, "info")

    def construir_ui(self):
        solo_lectura      = not estado.puede_hacer("comercial", "crear")
        puede_ajuste      = estado.puede_hacer("comercial", "ajuste")
        puede_eliminar    = estado.puede_hacer("comercial", "eliminar")
        puede_bodegas     = estado.puede_hacer("comercial", "bodegas")
        puede_sin_just    = estado.puede_hacer("comercial", "sin_justificacion")

        # ── Bloque 1: Formulario de Creación / Edición ──
        self.buscador_producto = BuscadorProducto(
            label="SKU o Nombre", width=180,
            on_seleccionar=self._on_producto_seleccionado,
        )

        self.in_nom    = ft.TextField(label="Nombre del Producto", expand=True)
        self.in_fam    = ft.Dropdown(label="Familia", width=180, options=[])
        self.in_fam.on_change = self.al_cambiar_familia
        self.in_subfam = ft.Dropdown(
            label="Subfamilia", width=180,
            options=[ft.dropdown.Option("", "— Sin Subfamilia —")],
            hint_text="Seleccione Familia", value="", disabled=True,
        )
        self.in_cos = ft.TextField(label="Costo Neto ($)",    value="0", width=150,
                                   visible=estado.puede_ver("costo"))
        self.in_ven = ft.TextField(label="Precio Venta ($)",  value="0", width=150)

        # ── Bloque 2: Ajuste Rápido ──
        self.buscador_ajuste = BuscadorProducto(
            label="SKU o Nombre", hint_text="Ingresa SKU o nombre",
            width=200, height=55, prefix_icon=ft.Icons.QR_CODE_SCANNER,
            on_seleccionar=self._on_ajuste_seleccionado,
        )

        self.sel_bodega_ajuste      = ft.Dropdown(label="Bodega Asignada", width=180, height=55, options=[])
        self.in_cant_ajuste         = ft.TextField(label="Cantidad", value="1", width=100, height=55, text_align="center")
        self.dd_tipo_ajuste         = ft.Dropdown(label="Tipo de Trabajo", width=220, height=55, options=[])
        self.in_comentario_ajuste   = ft.TextField(
            label="Comentario (ej: Cliente o N° Orden)", expand=True, height=55,
            hint_text="Obligatorio al restar",
        )
        self.chk_sin_justificacion  = ft.Checkbox(
            label="Sin justificación (Ajuste de stock)",
            value=False,
            on_change=self._toggle_justificacion,
        )
        self.txt_info_ajuste   = ft.Text("", size=12, color="grey600", weight="bold")
        self.cont_info_ajuste  = ft.Container(
            content=self.txt_info_ajuste, visible=False,
            padding=ft.Padding(12, 8, 12, 8), bgcolor="blue50", border_radius=8,
            border=ft.Border(left=ft.BorderSide(3, "blue400")),
        )

        # ── Bloque 3: Configuración de Bodegas Físicas ──
        self.in_bodega_area   = ft.Dropdown(label="Área", width=180, height=50, options=[])
        self.in_bodega_nombre = ft.TextField(label="Nombre de la Bodega", width=260, height=50)
        self.in_bodega_desc   = ft.TextField(label="Descripción / Ubicación", width=300, height=50)
        self.col_lista_bodegas = ft.Column([], spacing=2, scroll=ft.ScrollMode.AUTO)

        from utils.ui_helpers import sandwich

        _header = ft.Row([
            ft.Text("Ajuste Exprés", size=24, weight="bold", color="blue900", expand=True),
            ft.IconButton(ft.Icons.REFRESH, tooltip="Actualizar vista comercial", on_click=lambda _: self.inicializar()),
        ])

        _body = ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.VISIBILITY, color="amber700", size=16),
                    ft.Container(width=6),
                    ft.Text("Sin permiso de escritura — solo lectura", size=12, color="amber800"),
                ]),
                bgcolor="amber50", border_radius=8, padding=ft.Padding(12, 6, 12, 6),
                border=ft.Border(left=ft.BorderSide(3, "amber500")), visible=solo_lectura,
            ),
            ft.Divider(height=20, color="transparent"),

            # 1. Ajuste Rápido de Existencias
            ft.Container(
                content=ft.Column([
                    ft.Text("Ajuste Rápido de Existencias", weight="bold", size=16),
                    ft.Divider(height=8, color="transparent"),
                    ft.Row([
                        self.buscador_ajuste,
                        self.sel_bodega_ajuste,
                        self.in_cant_ajuste,
                        ft.ElevatedButton("SUMAR",  icon=ft.Icons.ADD,    on_click=lambda _: self.ajuste_stock(1),
                                          bgcolor="green700",  color="white", height=55,
                                          disabled=not puede_ajuste, tooltip="Sumar unidades al stock de la bodega"),
                        ft.ElevatedButton("RESTAR", icon=ft.Icons.REMOVE, on_click=lambda _: self.ajuste_stock(-1),
                                          bgcolor="orange700", color="white", height=55,
                                          disabled=not puede_ajuste, tooltip="Restar unidades del stock de la bodega"),
                        ft.Container(expand=True),
                        ft.ElevatedButton("ELIMINAR SKU", icon=ft.Icons.DELETE_FOREVER,
                                          on_click=self.eliminar_item,
                                          bgcolor="red800", color="white", height=55,
                                          visible=puede_eliminar, tooltip="Eliminar producto del sistema"),
                    ], spacing=8),
                    ft.Container(self.chk_sin_justificacion, visible=puede_sin_just),
                    ft.Row([
                        self.dd_tipo_ajuste,
                        self.in_comentario_ajuste,
                    ], spacing=8),
                    self.cont_info_ajuste,
                ]),
                padding=20, bgcolor="white", border_radius=10, border=ft.border.all(1, "grey300"),
            ),
            ft.Divider(height=10, color="transparent"),

            # 2. Maestro Productos
            ft.Container(
                content=ft.Column([
                    ft.Text("Ficha Técnica Nuevo Producto", weight="bold", size=16),
                    ft.Row([self.buscador_producto, self.in_nom, self.in_fam, self.in_subfam]),
                    ft.Row([ft.TextButton("Cargar subfamilias",
                                          on_click=lambda _: self.cargar_subfamilias(self.in_fam.value),
                                          tooltip="Recargar subfamilias de la familia seleccionada",
                                          style=ft.ButtonStyle(color="blue700"))]),
                    ft.Row([
                        self.in_cos, self.in_ven,
                        ft.Container(expand=True),
                        ft.ElevatedButton("GUARDAR MAESTRO", icon=ft.Icons.SAVE,
                                          on_click=self.guardar_item, height=50,
                                          disabled=solo_lectura, tooltip="Guardar ficha del producto"),
                    ]),
                ]),
                padding=20, bgcolor="white", border_radius=10, border=ft.border.all(1, "grey300"),
            ),
            ft.Divider(height=10, color="transparent"),

            # 3. Gestión de Bodegas
            ft.Container(
                content=ft.Column([
                    ft.Text("Configuración de Bodegas Físicas", weight="bold", size=16),
                    ft.Divider(height=8, color="transparent"),
                    ft.Row([
                        self.in_bodega_area,
                        self.in_bodega_nombre,
                        self.in_bodega_desc,
                        ft.ElevatedButton("CREAR BODEGA", icon=ft.Icons.ADD_BUSINESS,
                                          on_click=self.crear_bodega,
                                          bgcolor="blue900", color="white", height=50,
                                          disabled=not puede_bodegas, tooltip="Crear nueva bodega física"),
                    ], spacing=12, scroll=ft.ScrollMode.AUTO),
                    ft.Divider(height=8, color="grey200"),
                    ft.Text("Bodegas actuales:", size=12, weight="bold", color="grey700"),
                    ft.Container(content=self.col_lista_bodegas, height=180,
                                 border=ft.border.all(1, "grey200"), border_radius=8, bgcolor="grey50"),
                ]),
                padding=20, bgcolor="white", border_radius=10, border=ft.border.all(1, "grey300"),
            ),
        ], scroll=ft.ScrollMode.AUTO, expand=True)

        self.content = sandwich(_header, _body)

    def pre_cargar_si_cache_listo(self):
        from core.cache import app_cache
        if getattr(self, '_familias_listas', False) or not app_cache.cat_ready.is_set():
            return
        fams = app_cache.cat_familias or []
        if fams:
            self.in_fam.options = [ft.dropdown.Option(f) for f in fams]
            self.in_fam.value = None
            self._familias_listas = True
        areas = app_cache.cat_areas or []
        self.in_bodega_area.options = (
            [ft.dropdown.Option("", "— Sin Área —")] +
            [ft.dropdown.Option(key=str(a["id"]), text=a["nombre"]) for a in areas]
        )
        self.in_bodega_area.value = ""
        tipos = app_cache.cat_tipos or []
        if tipos:
            self.dd_tipo_ajuste.options = [
                ft.dropdown.Option(key=str(t["id"]), text=t["nombre"]) for t in tipos
            ]
        print(f"[COMERCIAL] familias y áreas pre-cargadas ({len(fams)}, {len(areas)})")

    def inicializar(self):
        def _run():
            try:
                sb = get_sb()
                if not getattr(self, '_familias_listas', False):
                    res_f = sb.table("familias").select("nombre").order("nombre").execute()
                    fams = [f["nombre"] for f in (res_f.data or [])]
                    self.in_fam.options = [ft.dropdown.Option(f) for f in fams]
                    self.in_fam.value = None
                    if self.page_ref: self.in_fam.update()
                res_a = sb.table("areas").select("id, nombre").order("nombre").execute()
                areas = res_a.data or []
                self.in_bodega_area.options = (
                    [ft.dropdown.Option("", "— Sin Área —")] +
                    [ft.dropdown.Option(key=str(a["id"]), text=a["nombre"]) for a in areas]
                )
                self.in_bodega_area.value = ""
                if self.page_ref: self.in_bodega_area.update()
                if not self.dd_tipo_ajuste.options:
                    from core.database import fetch_tipos_trabajo
                    tipos = fetch_tipos_trabajo()
                    self.dd_tipo_ajuste.options = [
                        ft.dropdown.Option(key=str(t["id"]), text=t["nombre"]) for t in tipos
                    ]
                    if self.page_ref: self.dd_tipo_ajuste.update()
                self.cargar_bodegas()
            except Exception as ex:
                print(f"[ERROR INICIALIZAR COMERCIAL] {ex}")
        hilo(_run)

    # ── MÉTODOS DE BODEGAS ──
    def cargar_bodegas(self):
        cache_invalidate()
        def _run():
            try:
                res_b  = get_sb().table("bodegas").select("id, nombre, descripcion, area_id, areas(nombre)").order("id").execute()
                bodegas = res_b.data or []

                ops = [ft.dropdown.Option(key=str(b["id"]), text=_label_bodega(b)) for b in bodegas]
                self.sel_bodega_ajuste.options = ops
                if bodegas and not self.sel_bodega_ajuste.value:
                    self.sel_bodega_ajuste.value = str(bodegas[0]["id"])

                filas = []
                for b in bodegas:
                    area_nombre = (b.get("areas") or {}).get("nombre") or ""
                    subtitle_txt = b.get("descripcion") or "Sin descripción"
                    area_chip = ft.Container(
                        content=ft.Text(area_nombre or "Sin área", size=11, color="white"),
                        bgcolor="indigo700" if area_nombre else "grey500",
                        border_radius=10,
                        padding=ft.Padding(8, 2, 8, 2),
                    )
                    filas.append(ft.ListTile(
                        leading=ft.Icon(ft.Icons.WAREHOUSE, color="blue800"),
                        title=ft.Row([
                            ft.Text(b['nombre'], weight="bold", size=14),
                            area_chip,
                        ], spacing=8),
                        subtitle=ft.Text(subtitle_txt, size=12, color="grey600"),
                        trailing=ft.Row([
                            ft.IconButton(
                                ft.Icons.EDIT_LOCATION_ALT, icon_color="indigo500",
                                tooltip="Cambiar área de esta bodega",
                                on_click=self.hacer_cambiar_area(b["id"], b["nombre"], b.get("area_id"), b.get("descripcion") or ""),
                                disabled=not estado.puede_hacer("comercial", "bodegas"),
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE, icon_color="red500", tooltip="Eliminar bodega",
                                on_click=self.hacer_eliminar_bodega(b["id"], b["nombre"]),
                                disabled=not estado.puede_hacer("comercial", "bodegas"),
                            ),
                        ], spacing=0, tight=True),
                    ))
                if not filas:
                    filas.append(ft.Container(
                        content=ft.Text("No hay bodegas registradas.", italic=True, color="grey500"), padding=20))

                self.col_lista_bodegas.controls = filas
                if self.page_ref:
                    self.sel_bodega_ajuste.update()
                    self.page_ref.update()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al cargar bodegas: {ex}", "red700")
        hilo(_run)

    def crear_bodega(self, e):
        nombre   = self.in_bodega_nombre.value.strip()
        desc     = self.in_bodega_desc.value.strip()
        area_val = self.in_bodega_area.value
        if not nombre:
            self.mostrar_snack("⚠️ El nombre de la bodega es obligatorio", "orange")
            return
        area_id = int(area_val) if area_val else None
        def _run():
            try:
                get_sb().table("bodegas").insert({"nombre": nombre, "descripcion": desc, "area_id": area_id}).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "CREAR BODEGA", f"Nombre: {nombre}")
                cache_invalidate()
                self.mostrar_snack(f"✅ Bodega '{nombre}' creada exitosamente", "green700")
                self.in_bodega_nombre.value = ""
                self.in_bodega_desc.value   = ""
                self.in_bodega_area.value   = ""
                if self.page_ref:
                    self.in_bodega_nombre.update()
                    self.in_bodega_desc.update()
                    self.in_bodega_area.update()
                self.cargar_bodegas()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al crear bodega: {ex}", "red700")
        hilo(_run)

    def hacer_eliminar_bodega(self, bid, bnombre):
        def _abrir_alerta(e):
            def _ejecutar():
                def _run():
                    try:
                        get_sb().table("bodega_productos").delete().eq("bodega_id", bid).execute()
                        get_sb().table("bodegas").delete().eq("id", bid).execute()
                        registrar_auditoria(estado.usuario_actual["nombre"], "ELIMINAR BODEGA",
                                            f"ID: {bid} | Nombre: {bnombre}")
                        cache_invalidate()
                        self.mostrar_snack(f"Bodega '{bnombre}' eliminada", "error")
                        self.cargar_bodegas()
                    except Exception as ex:
                        self.mostrar_snack(f"Error: {ex}", "error")
                hilo(_run)
            from utils.ui_helpers import mostrar_alerta
            mostrar_alerta(
                self.page_ref,
                "Eliminar Bodega",
                f"¿Estás seguro de eliminar '{bnombre}'?\n\n"
                "Todo el stock almacenado en esta bodega se perderá definitivamente.",
                _ejecutar,
                texto_confirmar="Sí, eliminar",
                tipo="warning",
            )
        return _abrir_alerta

    def hacer_cambiar_area(self, bid, bnombre, area_id_actual, desc_actual=""):
        def _abrir_dialogo(e):
            from core.cache import app_cache
            areas = app_cache.cat_areas or []
            dd = ft.Dropdown(
                label="Área",
                width=220,
                value=str(area_id_actual) if area_id_actual else "",
                options=(
                    [ft.dropdown.Option("", "— Sin Área —")] +
                    [ft.dropdown.Option(key=str(a["id"]), text=a["nombre"]) for a in areas]
                ),
            )
            tf_desc = ft.TextField(label="Descripción / Ubicación", value=desc_actual, width=340)
            dlg = [None]

            def _guardar(ev):
                nuevo_area_id = int(dd.value) if dd.value else None
                nueva_desc = tf_desc.value.strip()
                self.page_ref.pop_dialog()
                def _run():
                    try:
                        get_sb().table("bodegas").update({"area_id": nuevo_area_id, "descripcion": nueva_desc}).eq("id", bid).execute()
                        nombre_area = next((a["nombre"] for a in areas if a["id"] == nuevo_area_id), "Sin área")
                        registrar_auditoria(estado.usuario_actual["nombre"], "EDITAR BODEGA",
                                            f"Bodega: {bnombre} → Área: {nombre_area} | Desc: {nueva_desc}")
                        cache_invalidate()
                        self.mostrar_snack(f"✅ Bodega '{bnombre}' actualizada", "success")
                        self.cargar_bodegas()
                    except Exception as ex:
                        self.mostrar_snack(f"❌ Error: {ex}", "error")
                hilo(_run)

            def _cancelar(ev):
                self.page_ref.pop_dialog()

            dlg[0] = ft.AlertDialog(
                modal=True,
                title=ft.Row([
                    ft.Icon(ft.Icons.EDIT_LOCATION_ALT, color="indigo700", size=22),
                    ft.Text(f"Editar bodega — {bnombre}", weight="bold", size=14),
                ], spacing=10),
                content=ft.Column([dd, tf_desc], tight=True, spacing=12),
                actions=[
                    ft.TextButton("Cancelar", on_click=_cancelar),
                    ft.ElevatedButton("Guardar", bgcolor="indigo700", color="white", on_click=_guardar),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.page_ref.show_dialog(dlg[0])
        return _abrir_dialogo

    # ── MÉTODOS CREAR/EDITAR PRODUCTO ──
    def _on_producto_seleccionado(self, prod):
        sku = prod["sku"]
        def _run():
            try:
                res = get_sb().table("productos").select("*").eq("sku", sku).execute()
                if res.data:
                    p = res.data[0]
                    self.in_nom.value = p.get("nombre", "")
                    self.in_cos.value = str(p.get("costo_neto", 0))
                    self.in_ven.value = str(p.get("precio_venta", 0))
                    self.in_fam.value = p.get("familia") or None
                    if self.in_fam.value:
                        self.cargar_subfamilias(self.in_fam.value)
                        self.in_subfam.value = p.get("subfamilia") or ""
                    if self.page_ref:
                        self.in_nom.update()
                        self.in_cos.update()
                        self.in_ven.update()
                        self.in_fam.update()
                        self.in_subfam.update()
                        self.mostrar_snack(f"✏️ Modificando: {p.get('nombre','')}", "blue700")
            except Exception as ex:
                print(f"[CALLBACK PRODUCTO] {ex}")
        hilo(_run)

    def al_cambiar_familia(self, e):
        self.cargar_subfamilias(self.in_fam.value)

    def cargar_subfamilias(self, familia):
        self.in_subfam.options = [ft.dropdown.Option("", "— Sin Subfamilia —")]
        self.in_subfam.value   = ""
        self.in_subfam.disabled = True
        if self.page_ref: self.in_subfam.update()
        if not familia:
            return
        def _run():
            try:
                sb = get_sb()
                res_fam = sb.table("familias").select("id").eq("nombre", familia).execute()
                if not res_fam.data:
                    return
                fam_id = res_fam.data[0]["id"]
                res = sb.table("subfamilias").select("nombre").eq("familia_id", fam_id).execute()
                self.in_subfam.options += [ft.dropdown.Option(s["nombre"]) for s in (res.data or [])]
                self.in_subfam.disabled = False
                if self.page_ref: self.in_subfam.update()
            except Exception as ex:
                print(f"[SUBFAM LOAD] {ex}")
        hilo(_run)

    def guardar_item(self, e):
        val_subfam = self.in_subfam.value if self.in_subfam.value else ""
        sku    = self.buscador_producto.value.strip()
        nombre = self.in_nom.value.strip()
        if not sku or not nombre:
            self.mostrar_snack("⚠️ SKU y nombre son obligatorios", "orange")
            return
        def _run():
            try:
                sb = get_sb()
                existe = sb.table("productos").select("sku").eq("sku", sku).execute().data
                # Resolver familia_id y subfamilia_id por nombre
                fam_id = None
                sub_id = None
                if self.in_fam.value:
                    res_f = sb.table("familias").select("id").eq("nombre", self.in_fam.value).execute()
                    if res_f.data:
                        fam_id = res_f.data[0]["id"]
                if val_subfam and fam_id:
                    res_s = sb.table("subfamilias").select("id").eq("nombre", val_subfam).eq("familia_id", fam_id).execute()
                    if res_s.data:
                        sub_id = res_s.data[0]["id"]
                datos = {
                    "sku": sku, "nombre": nombre,
                    "familia_id": fam_id, "subfamilia_id": sub_id,
                    "precio_venta": float(self.in_ven.value or 0),
                }
                if estado.puede_ver("costo"):
                    datos["costo_neto"] = float(self.in_cos.value or 0)
                sb.table("productos").upsert(datos).execute()
                cache_invalidate()
                accion = "EDITAR PRODUCTO" if existe else "CREAR PRODUCTO"
                registrar_auditoria(estado.usuario_actual["nombre"], accion, f"SKU: {sku} | Nombre: {nombre}")
                self.mostrar_snack("✅ Producto guardado en maestro", "green700")
                self.buscador_producto.limpiar()
                self.in_nom.value = ""
                if self.page_ref: self.in_nom.update()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error: {ex}", "red700")
        hilo(_run)

    # ── MÉTODOS AJUSTE RÁPIDO ──
    def _toggle_justificacion(self, e):
        if not estado.puede_hacer("comercial", "sin_justificacion"):
            self.chk_sin_justificacion.value = False
            if self.page_ref: self.chk_sin_justificacion.update()
            return
        sin_just = self.chk_sin_justificacion.value
        self.dd_tipo_ajuste.disabled       = sin_just
        self.in_comentario_ajuste.disabled = sin_just
        if self.page_ref:
            self.dd_tipo_ajuste.update()
            self.in_comentario_ajuste.update()

    def _on_ajuste_seleccionado(self, prod):
        sku = prod["sku"]
        def _run():
            try:
                res_b = get_sb().table("bodega_productos").select("bodegas(nombre), cantidad").eq("sku", sku).execute()
                partes = []
                for b_rec in (res_b.data or []):
                    nom_b  = (b_rec.get("bodegas") or {}).get("nombre", "Bodega")
                    cant_b = b_rec.get("cantidad") or 0
                    partes.append(f"{nom_b}: {cant_b}")
                info = " | ".join(partes) if partes else "Sin stock en bodegas"
                self.txt_info_ajuste.value  = f"📦 {prod['nombre']}  |  {info}"
                self.txt_info_ajuste.color  = "blue900"
                self.cont_info_ajuste.bgcolor = "blue50"
                self.cont_info_ajuste.border  = ft.Border(left=ft.BorderSide(3, "blue400"))
                self.cont_info_ajuste.visible = True
                if self.page_ref:
                    self.txt_info_ajuste.update()
                    self.cont_info_ajuste.update()
            except Exception as ex:
                print(f"[CALLBACK AJUSTE] {ex}")
        hilo(_run)

    def ajuste_stock(self, delta):
        if not estado.puede_hacer("comercial", "ajuste"):
            self.mostrar_snack("⚠️ Sin permiso para ajustar existencias", "orange")
            return
        sku = self.buscador_ajuste.value.strip()
        if not self.sel_bodega_ajuste.value:
            self.mostrar_snack("⚠️ Debes seleccionar o crear una bodega primero", "orange")
            return
        if not sku:
            return
        b_id = int(self.sel_bodega_ajuste.value)
        try: cant = int(self.in_cant_ajuste.value or "1")
        except: cant = 1

        sin_just   = self.chk_sin_justificacion.value
        tipo       = self.dd_tipo_ajuste.value
        comentario = self.in_comentario_ajuste.value.strip()

        if delta < 0 and not sin_just and (not tipo or not comentario):
            self.mostrar_snack("⚠️ Tipo de trabajo y comentario son obligatorios para descontar", "orange")
            return

        def _run():
            try:
                if delta < 0 and not sin_just:
                    from core.database import registrar_despacho_tecnico
                    usuario_login  = estado.usuario_actual.get("usuario", "")
                    usuario_nombre = estado.usuario_actual.get("nombre", "")
                    registrar_despacho_tecnico(sku, b_id, cant, int(tipo), comentario, usuario_login, usuario_nombre)
                    self.mostrar_snack(f"✅ Stock descontado y movimiento registrado.", "green700")
                else:
                    res_p = get_sb().table("productos").select("nombre").eq("sku", sku).execute()
                    if not res_p.data:
                        self.mostrar_snack(f"❌ SKU '{sku}' no existe en el maestro de productos", "red700")
                        return
                    res_existente = get_sb().table("bodega_productos").select("cantidad") \
                                            .eq("bodega_id", b_id).eq("sku", sku).execute()
                    actual = (res_existente.data[0]["cantidad"] or 0) if res_existente.data else 0
                    nuevo  = max(0, actual + (cant if delta > 0 else -cant))
                    if res_existente.data:
                        get_sb().table("bodega_productos").update({"cantidad": nuevo}) \
                                .eq("bodega_id", b_id).eq("sku", sku).execute()
                    else:
                        get_sb().table("bodega_productos").insert(
                            {"bodega_id": b_id, "sku": sku, "cantidad": nuevo}).execute()
                    res_totales = get_sb().table("bodega_productos").select("cantidad").eq("sku", sku).execute()
                    total = sum(r.get("cantidad", 0) for r in (res_totales.data or []))
                    get_sb().table("productos").update({"stock_global": total}).eq("sku", sku).execute()
                    cache_invalidate()
                    signo = f"+{cant}" if delta > 0 else f"-{cant}"
                    accion = "AJUSTE STOCK BODEGA"
                    registrar_auditoria(estado.usuario_actual["nombre"], accion,
                                        f"SKU: {sku} | B{b_id}: {signo}")
                    msg = f"✅ Stock sumado: +{cant} uds en bodega" if delta > 0 else f"✅ Stock restado: -{cant} uds en bodega"
                    self.mostrar_snack(msg, "green700")

                self.in_cant_ajuste.value = "1"
                self.in_comentario_ajuste.value = ""
                self.chk_sin_justificacion.value = False
                self.dd_tipo_ajuste.disabled = False
                self.in_comentario_ajuste.disabled = False
                self.buscador_ajuste.limpiar()
                self.cont_info_ajuste.visible = False
                if self.page_ref:
                    self.in_cant_ajuste.update()
                    self.in_comentario_ajuste.update()
                    self.chk_sin_justificacion.update()
                    self.dd_tipo_ajuste.update()
                    self.cont_info_ajuste.update()
            except ValueError as ex:
                self.mostrar_snack(f"⚠️ {ex}", "orange")
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al ajustar stock: {ex}", "red700")
        hilo(_run)

    def eliminar_item(self, e):
        sku = self.buscador_ajuste.value.strip() or self.buscador_producto.value.strip()
        if not sku:
            self.mostrar_snack("⚠️ Selecciona un producto para eliminar", "warning")
            return
        def _ejecutar():
            def _run():
                try:
                    get_sb().table("bodega_productos").delete().eq("sku", sku).execute()
                    get_sb().table("furgon_productos").delete().eq("sku", sku).execute()
                    get_sb().table("productos").delete().eq("sku", sku).execute()
                    cache_invalidate()
                    registrar_auditoria(estado.usuario_actual["nombre"], "ELIMINAR PRODUCTO", f"SKU: {sku}")
                    self.mostrar_snack("🗑️ Producto eliminado del sistema", "red700")
                    self.buscador_ajuste.limpiar()
                    self.buscador_producto.limpiar()
                    self.in_nom.value = ""
                    self.in_cos.value = ""
                    self.in_ven.value = ""
                    self.in_fam.value = None
                    self.in_subfam.value = None
                    self.cont_info_ajuste.visible = False
                    if self.page_ref:
                        self.in_nom.update()
                        self.in_cos.update()
                        self.in_ven.update()
                        self.in_fam.update()
                        self.in_subfam.update()
                        self.cont_info_ajuste.update()
                except Exception as ex:
                    self.mostrar_snack(f"❌ Error: {ex}", "red700")
            hilo(_run)
        from utils.ui_helpers import mostrar_alerta
        mostrar_alerta(
            self.page_ref,
            "Eliminar Producto",
            f"¿Eliminar el producto con SKU '{sku}'?\n"
            "Se borrará completamente del sistema incluyendo su stock en bodegas y furgones.",
            _ejecutar,
            texto_confirmar="Sí, eliminar",
            tipo="error",
        )
