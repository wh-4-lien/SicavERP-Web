# vistas/categorias.py
import flet as ft
from core.database import get_sb
from core.estado import estado
from core.utilidades import hilo, registrar_auditoria

class VistaCategorias(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self._datos_jerarquia = []
        self._datos_tipos     = []
        self._pagina_jer  = 0
        self._pagina_tip  = 0
        self._por_pagina  = 25
        self.construir_ui()

    def mostrar_snack(self, mensaje, tipo_o_color="success"):
        from utils.ui_helpers import mostrar_snack as _snack
        _snack(self.page_ref, mensaje, tipo_o_color)

    def _paginacion_row(self, btn_prev, lbl, btn_next, in_pag, btn_ir):
        return ft.Row(
            [btn_prev, lbl, btn_next, ft.Container(width=16), in_pag, btn_ir],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def construir_ui(self):
        puede_crear    = estado.puede_hacer("categorias", "crear")
        puede_eliminar = estado.puede_hacer("categorias", "eliminar")

        # ── Áreas ──
        self.in_nueva_area   = ft.TextField(label="Nueva Área", width=200)
        self.sel_elim_area   = ft.Dropdown(label="Área a Eliminar", width=200, options=[])
        self.tabla_areas     = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID",     weight="bold")),
                ft.DataColumn(ft.Text("Área",   weight="bold")),
            ],
            rows=[], border=ft.border.all(1, "grey200"), border_radius=5,
        )

        # ── Familias ──
        self.in_nueva_fam          = ft.TextField(label="Nueva Familia", width=200)
        self.selector_eliminar_fam = ft.Dropdown(label="Familia a Eliminar", width=200, options=[])
        self.sel_fam_para_sub      = ft.Dropdown(label="Familia Padre", width=180, options=[])
        self.in_nueva_subfam       = ft.TextField(label="Nueva Subfamilia", width=180)
        self.sel_elim_subfam       = ft.Dropdown(label="Subfamilia a Eliminar", width=230, options=[])

        # tabla jerarquía
        self.tabla_jerarquia = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Familia Principal",     weight="bold")),
                ft.DataColumn(ft.Text("Subfamilias Asociadas", weight="bold")),
            ],
            rows=[], border=ft.border.all(1, "grey200"), border_radius=5,
        )
        self.lbl_pag_jer  = ft.Text("", size=12, color="grey700")
        self.btn_prev_jer = ft.IconButton(ft.Icons.CHEVRON_LEFT,  tooltip="Página anterior",
                                          on_click=lambda _: self._ir_pag_jer(self._pagina_jer - 1))
        self.btn_next_jer = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Página siguiente",
                                          on_click=lambda _: self._ir_pag_jer(self._pagina_jer + 1))
        self.in_pag_jer   = ft.TextField(label="Ir a pág.", width=90, height=40,
                                          text_align="center", keyboard_type=ft.KeyboardType.NUMBER)
        self.in_pag_jer.on_submit = self._saltar_pag_jer
        self.row_pag_jer  = self._paginacion_row(
            self.btn_prev_jer, self.lbl_pag_jer, self.btn_next_jer,
            self.in_pag_jer,
            ft.IconButton(ft.Icons.ARROW_FORWARD, tooltip="Ir a la página indicada", on_click=self._saltar_pag_jer),
        )

        # ── Tipos de trabajo ──
        self.in_nuevo_tipo = ft.TextField(label="Nombre del tipo de trabajo", width=220)
        self.sel_elim_tipo = ft.Dropdown(label="Tipo a eliminar", width=220, options=[])
        self.tabla_tipos   = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID",              weight="bold")),
                ft.DataColumn(ft.Text("Tipo de Trabajo", weight="bold")),
            ],
            rows=[], border=ft.border.all(1, "grey200"), border_radius=5,
        )
        self.lbl_pag_tip  = ft.Text("", size=12, color="grey700")
        self.btn_prev_tip = ft.IconButton(ft.Icons.CHEVRON_LEFT,  tooltip="Página anterior",
                                          on_click=lambda _: self._ir_pag_tip(self._pagina_tip - 1))
        self.btn_next_tip = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Página siguiente",
                                          on_click=lambda _: self._ir_pag_tip(self._pagina_tip + 1))
        self.in_pag_tip   = ft.TextField(label="Ir a pág.", width=90, height=40,
                                          text_align="center", keyboard_type=ft.KeyboardType.NUMBER)
        self.in_pag_tip.on_submit = self._saltar_pag_tip
        self.row_pag_tip  = self._paginacion_row(
            self.btn_prev_tip, self.lbl_pag_tip, self.btn_next_tip,
            self.in_pag_tip,
            ft.IconButton(ft.Icons.ARROW_FORWARD, tooltip="Ir a la página indicada", on_click=self._saltar_pag_tip),
        )

        # ── Header ──
        header = ft.Row([
            ft.Text("📑 Gestión de Categorías y Configuración", size=24, weight="bold", color="blue900", expand=True),
            ft.IconButton(ft.Icons.REFRESH, tooltip="Actualizar categorías", on_click=lambda _: self.cargar_datos()),
        ])

        # ── Body: cuadrícula 2x2 + fila áreas ──
        body = ft.Column([
            ft.Divider(height=10, color="transparent"),

            # Fila áreas: gestión de áreas de bodega
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.LOCATION_CITY, color="indigo700", size=20),
                        ft.Text("Áreas de Bodega", weight="bold", size=16, color="indigo900"),
                    ], spacing=8),
                    ft.Text("Las áreas agrupan las bodegas por sección (Ej: Ingeniería, Comercial).",
                            size=12, color="grey600"),
                    ft.Divider(height=8, color="transparent"),
                    ft.Row([
                        self.in_nueva_area,
                        ft.ElevatedButton("CREAR", icon=ft.Icons.ADD,
                                          tooltip="Crear nueva área",
                                          on_click=self.crear_area, bgcolor="indigo700", color="white",
                                          visible=puede_crear),
                        ft.Container(width=20),
                        self.sel_elim_area,
                        ft.ElevatedButton("ELIMINAR", icon=ft.Icons.DELETE,
                                          tooltip="Eliminar el área seleccionada",
                                          on_click=self.eliminar_area, bgcolor="red", color="white",
                                          visible=puede_eliminar),
                    ], spacing=12, wrap=True),
                    ft.Divider(height=8, color="grey200"),
                    ft.Row([self.tabla_areas], scroll=ft.ScrollMode.ALWAYS),
                ]),
                padding=16, bgcolor="white",
                border_radius=10, border=ft.border.all(1, "indigo200"),
            ),

            ft.Divider(height=10, color="transparent"),

            # Fila superior: formularios lado a lado
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("📂 Familias Principales", weight="bold", size=16),
                        ft.Divider(height=6, color="transparent"),
                        ft.Row([self.in_nueva_fam,
                                ft.ElevatedButton("CREAR", icon=ft.Icons.ADD,
                                                  tooltip="Crear nueva familia principal",
                                                  on_click=self.crear_familia, bgcolor="green", color="white",
                                                  visible=puede_crear)]),
                        ft.Row([self.selector_eliminar_fam,
                                ft.ElevatedButton("ELIMINAR", icon=ft.Icons.DELETE,
                                                  tooltip="Eliminar la familia seleccionada",
                                                  on_click=self.eliminar_familia, bgcolor="red", color="white",
                                                  visible=puede_eliminar)]),
                    ]),
                    expand=True, padding=16, bgcolor="white",
                    border_radius=10, border=ft.border.all(1, "grey300"),
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("📁 Subfamilias", weight="bold", size=16),
                        ft.Divider(height=6, color="transparent"),
                        ft.Row([self.sel_fam_para_sub, self.in_nueva_subfam,
                                ft.ElevatedButton("CREAR", icon=ft.Icons.ADD,
                                                  tooltip="Crear nueva subfamilia bajo la familia seleccionada",
                                                  on_click=self.crear_subfamilia, bgcolor="green", color="white",
                                                  visible=puede_crear)]),
                        ft.Row([self.sel_elim_subfam,
                                ft.ElevatedButton("ELIMINAR", icon=ft.Icons.DELETE,
                                                  tooltip="Eliminar la subfamilia seleccionada",
                                                  on_click=self.eliminar_subfamilia, bgcolor="red", color="white",
                                                  visible=puede_eliminar)]),
                    ]),
                    expand=True, padding=16, bgcolor="white",
                    border_radius=10, border=ft.border.all(1, "grey300"),
                ),
            ], spacing=10),

            ft.Divider(height=10, color="transparent"),

            # Fila inferior: tablas lado a lado
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("📊 Estructura Actual de Categorías", weight="bold", size=16, color="blue900"),
                        ft.Divider(height=6, color="transparent"),
                        ft.Row([self.tabla_jerarquia], scroll=ft.ScrollMode.ALWAYS),
                        self.row_pag_jer,
                    ]),
                    expand=True, padding=16, bgcolor="white",
                    border_radius=10, border=ft.border.all(1, "grey300"),
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("🔧 Tipos de Trabajo a Terreno", weight="bold", size=16, color="orange900"),
                        ft.Text("Aparecen en el formulario de descuento de stock del técnico.",
                                size=12, color="grey600"),
                        ft.Divider(height=8, color="transparent"),
                        ft.Row([self.in_nuevo_tipo,
                                ft.ElevatedButton("CREAR", icon=ft.Icons.ADD,
                                                  tooltip="Crear nuevo tipo de trabajo a terreno",
                                                  on_click=self.crear_tipo_trabajo, bgcolor="orange700", color="white",
                                                  visible=puede_crear)]),
                        ft.Row([self.sel_elim_tipo,
                                ft.ElevatedButton("ELIMINAR", icon=ft.Icons.DELETE,
                                                  tooltip="Eliminar el tipo de trabajo seleccionado",
                                                  on_click=self.eliminar_tipo_trabajo, bgcolor="red", color="white",
                                                  visible=puede_eliminar)]),
                        ft.Divider(height=8, color="transparent"),
                        ft.Row([self.tabla_tipos], scroll=ft.ScrollMode.ALWAYS),
                        self.row_pag_tip,
                    ]),
                    expand=True, padding=16, bgcolor="white",
                    border_radius=10, border=ft.border.all(1, "orange200"),
                ),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),

        ], scroll=ft.ScrollMode.AUTO, expand=True)

        from utils.ui_helpers import sandwich
        self.padding = 0
        self.content = sandwich(header, body)

    # ══════════════════════════════ Cache ══════════════════════════════
    def pre_cargar_si_cache_listo(self):
        from core.cache import app_cache
        if getattr(self, '_datos_cargados', False) or not app_cache.cat_ready.is_set():
            return
        self._poblar_desde_cache(app_cache)

    def _poblar_desde_cache(self, cache):
        import flet as ft
        fams    = cache.cat_familias or []
        subs    = cache.cat_subfamilias or []
        tipos   = cache.cat_tipos or []
        areas   = cache.cat_areas or []

        self.selector_eliminar_fam.options = [ft.dropdown.Option(f) for f in fams]
        self.sel_fam_para_sub.options      = [ft.dropdown.Option(f) for f in fams]
        self.sel_elim_subfam.options = [
            ft.dropdown.Option(f"{s['nombre']} ({s['familia_nombre']})") for s in subs
        ]
        self._datos_jerarquia = [
            (f_name, [s["nombre"] for s in subs if s["familia_nombre"] == f_name])
            for f_name in fams
        ]
        self._pagina_jer = 0
        self._renderizar_pagina_jerarquia()

        self._datos_tipos = tipos
        self.sel_elim_tipo.options = [
            ft.dropdown.Option(key=str(t["id"]), text=t["nombre"]) for t in tipos
        ]
        self._pagina_tip = 0
        self._renderizar_pagina_tipos()

        self._renderizar_areas(areas)

        self._datos_cargados = True
        print(f"[CATEGORIAS] pre-cargadas ({len(fams)} familias, {len(subs)} subfamilias, {len(tipos)} tipos, {len(areas)} áreas)")

    # ══════════════════════════════ Init ══════════════════════════════
    def inicializar(self):
        if getattr(self, '_datos_cargados', False):
            return
        self.cargar_datos()

    def cargar_datos(self):
        def _run():
            try:
                sb = get_sb()
                res_f = sb.table("familias").select("nombre").order("nombre").execute()
                fams  = [f["nombre"] for f in (res_f.data or [])]

                self.selector_eliminar_fam.options = [ft.dropdown.Option(f) for f in fams]
                self.sel_fam_para_sub.options      = [ft.dropdown.Option(f) for f in fams]

                res_f2 = sb.table("familias").select("id, nombre").execute()
                fam_id_map = {f["id"]: f["nombre"] for f in (res_f2.data or [])}
                res_s = sb.table("subfamilias").select("nombre, familia_id").order("nombre").execute()
                subs  = [{"nombre": s["nombre"], "familia_nombre": fam_id_map.get(s["familia_id"], "")}
                         for s in (res_s.data or [])]
                self.sel_elim_subfam.options = [
                    ft.dropdown.Option(f"{s['nombre']} ({s['familia_nombre']})") for s in subs
                ]

                # guardar datos para paginación
                self._datos_jerarquia = [
                    (f_name, [s["nombre"] for s in subs if s["familia_nombre"] == f_name])
                    for f_name in fams
                ]
                self._pagina_jer = 0
                self._renderizar_pagina_jerarquia()

                res_t = sb.table("tipos_trabajo").select("*").order("nombre").execute()
                self._datos_tipos = res_t.data or []
                self.sel_elim_tipo.options = [
                    ft.dropdown.Option(key=str(t["id"]), text=t["nombre"]) for t in self._datos_tipos
                ]
                self._pagina_tip = 0
                self._renderizar_pagina_tipos()

                res_a = sb.table("areas").select("id, nombre").order("nombre").execute()
                areas = res_a.data or []
                self._renderizar_areas(areas)

                if self.page_ref:
                    self.tabla_jerarquia.update()
                    self.lbl_pag_jer.update()
                    self.btn_prev_jer.update()
                    self.btn_next_jer.update()
                    self.tabla_tipos.update()
                    self.lbl_pag_tip.update()
                    self.btn_prev_tip.update()
                    self.btn_next_tip.update()
                    self.sel_elim_subfam.update()
                    self.sel_elim_tipo.update()
                    self.tabla_areas.update()
                    self.sel_elim_area.update()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al cargar categorías: {ex}", "error")
        hilo(_run)

    def _renderizar_areas(self, areas):
        self.sel_elim_area.options = [
            ft.dropdown.Option(key=str(a["id"]), text=a["nombre"]) for a in areas
        ]
        self.tabla_areas.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(a["id"]), color="grey600", size=12)),
                ft.DataCell(ft.Text(a["nombre"], weight="bold", color="indigo900")),
            ])
            for a in areas
        ]

    # ══════════════════════════════ Paginación jerarquía ══════════════════════════════
    def _renderizar_pagina_jerarquia(self):
        datos  = self._datos_jerarquia
        total  = len(datos)
        inicio = self._pagina_jer * self._por_pagina
        fin    = min(inicio + self._por_pagina, total)

        filas = []
        for f_name, s_list in datos[inicio:fin]:
            s_text = ", ".join(s_list) if s_list else "--- Sin subfamilias ---"
            filas.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(f_name, weight="bold", color="blue900")),
                ft.DataCell(ft.Text(s_text, color="blue700" if s_list else "grey400")),
            ]))
        self.tabla_jerarquia.rows = filas

        total_pags = max(1, -(-total // self._por_pagina))
        self.lbl_pag_jer.value   = f"Página {self._pagina_jer + 1} de {total_pags}  ({total} familias)"
        self.btn_prev_jer.disabled = self._pagina_jer == 0
        self.btn_next_jer.disabled = self._pagina_jer >= total_pags - 1

    def _ir_pag_jer(self, nueva):
        total = len(self._datos_jerarquia)
        max_p = max(0, -(-total // self._por_pagina) - 1)
        self._pagina_jer = max(0, min(nueva, max_p))
        self._renderizar_pagina_jerarquia()
        if self.page_ref:
            self.tabla_jerarquia.update()
            self.lbl_pag_jer.update()
            self.btn_prev_jer.update()
            self.btn_next_jer.update()

    def _saltar_pag_jer(self, e=None):
        try: destino = int(self.in_pag_jer.value or "1") - 1
        except: return
        self.in_pag_jer.value = ""
        if self.page_ref: self.in_pag_jer.update()
        self._ir_pag_jer(destino)

    # ══════════════════════════════ Paginación tipos ══════════════════════════════
    def _renderizar_pagina_tipos(self):
        datos  = self._datos_tipos
        total  = len(datos)
        inicio = self._pagina_tip * self._por_pagina
        fin    = min(inicio + self._por_pagina, total)

        self.tabla_tipos.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(t["id"]), color="grey600", size=12)),
                ft.DataCell(ft.Text(t["nombre"], weight="bold", color="orange900")),
            ])
            for t in datos[inicio:fin]
        ]

        total_pags = max(1, -(-total // self._por_pagina))
        self.lbl_pag_tip.value   = f"Página {self._pagina_tip + 1} de {total_pags}  ({total} tipos)"
        self.btn_prev_tip.disabled = self._pagina_tip == 0
        self.btn_next_tip.disabled = self._pagina_tip >= total_pags - 1

    def _ir_pag_tip(self, nueva):
        total = len(self._datos_tipos)
        max_p = max(0, -(-total // self._por_pagina) - 1)
        self._pagina_tip = max(0, min(nueva, max_p))
        self._renderizar_pagina_tipos()
        if self.page_ref:
            self.tabla_tipos.update()
            self.lbl_pag_tip.update()
            self.btn_prev_tip.update()
            self.btn_next_tip.update()

    def _saltar_pag_tip(self, e=None):
        try: destino = int(self.in_pag_tip.value or "1") - 1
        except: return
        self.in_pag_tip.value = ""
        if self.page_ref: self.in_pag_tip.update()
        self._ir_pag_tip(destino)

    # ══════════════════════════════ CRUD ══════════════════════════════
    def crear_familia(self, e):
        nombre = self.in_nueva_fam.value.strip()
        if not nombre: return
        def _run():
            try:
                get_sb().table("familias").insert({"nombre": nombre}).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "CREAR FAMILIA", f"Familia: {nombre}")
                self.mostrar_snack("✅ Familia creada", "success")
                self.in_nueva_fam.value = ""
                self.cargar_datos()
            except Exception:
                self.mostrar_snack("❌ La familia ya existe", "error")
        hilo(_run)

    def eliminar_familia(self, e):
        valor = self.selector_eliminar_fam.value
        if not valor: return
        def _ejecutar():
            def _run():
                try:
                    get_sb().table("familias").delete().eq("nombre", valor).execute()
                    registrar_auditoria(estado.usuario_actual["nombre"], "ELIMINAR FAMILIA", f"Familia: {valor}")
                    self.mostrar_snack("🗑️ Familia eliminada", "success")
                    self.selector_eliminar_fam.value = None
                    self.cargar_datos()
                except Exception as ex:
                    self.mostrar_snack(f"❌ Error: {ex}", "error")
            hilo(_run)
        from utils.ui_helpers import mostrar_alerta
        mostrar_alerta(
            self.page_ref,
            "Eliminar familia",
            f"¿Eliminar la familia '{valor}'?\nSe eliminarán también sus subfamilias asociadas.",
            _ejecutar,
            texto_confirmar="Sí, eliminar",
        )

    def crear_subfamilia(self, e):
        fam    = self.sel_fam_para_sub.value
        nombre = self.in_nueva_subfam.value.strip()
        if not fam or not nombre: return
        def _run():
            try:
                sb = get_sb()
                res_fam = sb.table("familias").select("id").eq("nombre", fam).execute()
                if not res_fam.data:
                    self.mostrar_snack("❌ Familia no encontrada", "error")
                    return
                fam_id = res_fam.data[0]["id"]
                sb.table("subfamilias").insert({"nombre": nombre, "familia_id": fam_id}).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "CREAR SUBFAMILIA", f"{nombre} en {fam}")
                self.mostrar_snack("✅ Subfamilia creada", "success")
                self.in_nueva_subfam.value = ""
                self.cargar_datos()
            except Exception:
                self.mostrar_snack("❌ Error o subfamilia existente", "error")
        hilo(_run)

    def eliminar_subfamilia(self, e):
        valor = self.sel_elim_subfam.value
        if not valor: return
        _partes = valor.rsplit(" (", 1)
        nombre_s = _partes[0]
        def _ejecutar():
            def _run():
                try:
                    fam_s = _partes[1].replace(")", "") if len(_partes) > 1 else ""
                    sb2 = get_sb()
                    res_fam2 = sb2.table("familias").select("id").eq("nombre", fam_s).execute()
                    fam_id2 = res_fam2.data[0]["id"] if res_fam2.data else None
                    if not fam_id2:
                        self.mostrar_snack("❌ Familia no encontrada, recarga y reintenta", "error")
                        return
                    sb2.table("subfamilias").delete().eq("nombre", nombre_s).eq("familia_id", fam_id2).execute()
                    registrar_auditoria(estado.usuario_actual["nombre"], "ELIMINAR SUBFAMILIA", f"Subfamilia: {nombre_s}")
                    self.mostrar_snack("🗑️ Subfamilia eliminada", "success")
                    self.sel_elim_subfam.value = None
                    self.cargar_datos()
                except Exception as ex:
                    self.mostrar_snack(f"❌ Error: {ex}", "error")
            hilo(_run)
        from utils.ui_helpers import mostrar_alerta
        mostrar_alerta(
            self.page_ref,
            "Eliminar subfamilia",
            f"¿Eliminar la subfamilia '{nombre_s}'?\nEsta acción no se puede deshacer.",
            _ejecutar,
            texto_confirmar="Sí, eliminar",
        )

    def crear_tipo_trabajo(self, e):
        nombre = self.in_nuevo_tipo.value.strip()
        if not nombre:
            self.mostrar_snack("⚠️ Escribe el nombre del tipo de trabajo", "warning")
            return
        def _run():
            try:
                get_sb().table("tipos_trabajo").insert({"nombre": nombre}).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "CREAR TIPO TRABAJO", f"Tipo: {nombre}")
                self.mostrar_snack(f"✅ Tipo '{nombre}' creado", "success")
                self.in_nuevo_tipo.value = ""
                self.cargar_datos()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error: {ex}", "error")
        hilo(_run)

    def eliminar_tipo_trabajo(self, e):
        tipo_id = self.sel_elim_tipo.value
        if not tipo_id:
            self.mostrar_snack("⚠️ Selecciona un tipo de trabajo", "warning")
            return
        nombre_tipo = next((o.text for o in self.sel_elim_tipo.options if o.key == tipo_id), tipo_id)
        def _ejecutar():
            def _run():
                try:
                    get_sb().table("tipos_trabajo").delete().eq("id", int(tipo_id)).execute()
                    registrar_auditoria(estado.usuario_actual["nombre"], "ELIMINAR TIPO TRABAJO", f"Tipo: {nombre_tipo}")
                    self.mostrar_snack(f"🗑️ Tipo '{nombre_tipo}' eliminado", "success")
                    self.sel_elim_tipo.value = None
                    self.cargar_datos()
                except Exception as ex:
                    self.mostrar_snack(f"❌ Error: {ex}", "error")
            hilo(_run)
        from utils.ui_helpers import mostrar_alerta
        mostrar_alerta(
            self.page_ref,
            "Eliminar tipo de trabajo",
            f"¿Eliminar el tipo de trabajo '{nombre_tipo}'?\nEsta acción no se puede deshacer.",
            _ejecutar,
            texto_confirmar="Sí, eliminar",
        )

    def crear_area(self, e):
        nombre = self.in_nueva_area.value.strip()
        if not nombre:
            self.mostrar_snack("⚠️ Escribe el nombre del área", "warning")
            return
        def _run():
            try:
                get_sb().table("areas").insert({"nombre": nombre}).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "CREAR ÁREA", f"Área: {nombre}")
                self.mostrar_snack(f"✅ Área '{nombre}' creada", "success")
                self.in_nueva_area.value = ""
                if self.page_ref:
                    self.in_nueva_area.update()
                self.cargar_datos()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error: {ex}", "error")
        hilo(_run)

    def eliminar_area(self, e):
        area_id = self.sel_elim_area.value
        if not area_id:
            self.mostrar_snack("⚠️ Selecciona un área", "warning")
            return
        nombre_area = next((o.text for o in self.sel_elim_area.options if o.key == area_id), area_id)
        def _ejecutar():
            def _run():
                try:
                    get_sb().table("areas").delete().eq("id", int(area_id)).execute()
                    registrar_auditoria(estado.usuario_actual["nombre"], "ELIMINAR ÁREA", f"Área: {nombre_area}")
                    self.mostrar_snack(f"🗑️ Área '{nombre_area}' eliminada", "success")
                    self.sel_elim_area.value = None
                    self.cargar_datos()
                except Exception as ex:
                    self.mostrar_snack(f"❌ Error: {ex}", "error")
            hilo(_run)
        from utils.ui_helpers import mostrar_alerta
        mostrar_alerta(
            self.page_ref,
            "Eliminar área",
            f"¿Eliminar el área '{nombre_area}'?\nLas bodegas asociadas quedarán sin área asignada.",
            _ejecutar,
            texto_confirmar="Sí, eliminar",
        )
