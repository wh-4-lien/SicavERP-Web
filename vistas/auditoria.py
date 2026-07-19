# vistas/auditoria.py
import flet as ft
import datetime
from core.database import get_sb
from core.estado import estado
from core.utilidades import hilo

class VistaAuditoria(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.datos_actuales = []
        self.datos_terreno  = []
        self._pagina_general = 0
        self._pagina_terreno = 0
        self._por_pagina = 50
        self.construir_ui()

    def mostrar_snack(self, mensaje, tipo_o_color="success"):
        from utils.ui_helpers import mostrar_snack as _snack
        _snack(self.page_ref, mensaje, tipo_o_color)

    def abrir_calendario(self, e):
        try:
            if hasattr(self.page_ref, "open"):
                self.page_ref.open(self.date_picker)
            else:
                self.date_picker.open = True
                self.page_ref.update()
        except: pass

    def al_seleccionar_fecha(self, e):
        if self.date_picker.value:
            self.in_fecha.value = self.date_picker.value.strftime('%Y-%m-%d')
            if self.page_ref: self.in_fecha.update()
            self.cargar_datos()

    def cambiar_tab(self, indice):
        self.btn_tab_1.border = ft.Border(bottom=ft.BorderSide(3, "transparent"))
        self.btn_tab_2.border = ft.Border(bottom=ft.BorderSide(3, "transparent"))
        self.btn_tab_1.content.color = "grey600"
        self.btn_tab_2.content.color = "grey600"
        self.cont_general.visible = False
        self.cont_terreno.visible = False

        if indice == 0:
            self.btn_tab_1.border = ft.Border(bottom=ft.BorderSide(3, "blue900"))
            self.btn_tab_1.content.color = "blue900"
            self.cont_general.visible = True
        else:
            self.btn_tab_2.border = ft.Border(bottom=ft.BorderSide(3, "blue900"))
            self.btn_tab_2.content.color = "blue900"
            self.cont_terreno.visible = True
            self.cargar_terreno()

        if self.page_ref:
            self.btn_tab_1.update()
            self.btn_tab_1.content.update()
            self.btn_tab_2.update()
            self.btn_tab_2.content.update()
            self.cont_general.update()
            self.cont_terreno.update()

    def _make_paginacion(self, ir_prev, ir_next, lbl, in_pag, btn_ir):
        return ft.Row(
            [ir_prev, lbl, ir_next,
             ft.Container(width=16),
             in_pag, btn_ir],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def construir_ui(self):
        self.date_picker = ft.DatePicker(
            on_change=self.al_seleccionar_fecha,
            first_date=datetime.datetime(2023, 1, 1),
            last_date=datetime.datetime(2030, 12, 31)
        )
        if self.date_picker not in self.page_ref.overlay:
            self.page_ref.overlay.append(self.date_picker)

        self.sel_usuario = ft.Dropdown(label="Usuario", width=180, options=[ft.dropdown.Option("", "Todos")])
        self.sel_usuario.on_change = lambda e: self.cargar_datos()

        meses = [("01","Enero"),("02","Febrero"),("03","Marzo"),("04","Abril"),
                 ("05","Mayo"),("06","Junio"),("07","Julio"),("08","Agosto"),
                 ("09","Septiembre"),("10","Octubre"),("11","Noviembre"),("12","Diciembre")]
        self.sel_mes  = ft.Dropdown(label="Mes",  width=130,
            options=[ft.dropdown.Option("","Todos")] + [ft.dropdown.Option(m[0], m[1]) for m in meses])
        anio_actual = datetime.date.today().year
        self.sel_anio = ft.Dropdown(label="Año", width=110,
            options=[ft.dropdown.Option("","Todos")] + [ft.dropdown.Option(str(y),str(y)) for y in range(anio_actual-2, anio_actual+3)])
        self.in_fecha = ft.TextField(
            label="Día exacto (YYYY-MM-DD)", width=220,
            suffix_icon=ft.Icons.CALENDAR_MONTH, on_click=self.abrir_calendario)

        # ── tabla general ──
        self.tabla_auditoria = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Fecha/Hora", weight="bold")),
                ft.DataColumn(ft.Text("Usuario",    weight="bold")),
                ft.DataColumn(ft.Text("Acción",     weight="bold")),
                ft.DataColumn(ft.Text("Detalle del Movimiento", weight="bold")),
            ],
            rows=[], border=ft.border.all(1,"grey200"), border_radius=8,
            heading_row_color=ft.Colors.with_opacity(0.04,"blue")
        )

        # paginación general
        self.lbl_pag_g  = ft.Text("", size=12, color="grey700")
        self.btn_prev_g = ft.IconButton(ft.Icons.CHEVRON_LEFT,  tooltip="Anterior",
                                        on_click=lambda _: self._ir_pag_g(self._pagina_general - 1))
        self.btn_next_g = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Siguiente",
                                        on_click=lambda _: self._ir_pag_g(self._pagina_general + 1))
        self.in_pag_g   = ft.TextField(label="Ir a pág.", width=90, height=40,
                                        text_align="center", keyboard_type=ft.KeyboardType.NUMBER)
        self.in_pag_g.on_submit = self._saltar_pag_g
        self.row_pag_g  = self._make_paginacion(
            self.btn_prev_g, self.btn_next_g, self.lbl_pag_g,
            self.in_pag_g,
            ft.IconButton(ft.Icons.ARROW_FORWARD, tooltip="Ir", on_click=self._saltar_pag_g)
        )

        # ── tabla terreno ──
        self.tabla_terreno = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Fecha",      weight="bold")),
                ft.DataColumn(ft.Text("Técnico",    weight="bold")),
                ft.DataColumn(ft.Text("Tipo de Trabajo", weight="bold")),
                ft.DataColumn(ft.Text("Producto Descontado", weight="bold")),
                ft.DataColumn(ft.Text("Comentario Obligatorio", weight="bold")),
            ],
            rows=[], border=ft.border.all(1,"grey200"), border_radius=8,
            heading_row_color=ft.Colors.with_opacity(0.04,"orange")
        )

        # paginación terreno
        self.lbl_pag_t  = ft.Text("", size=12, color="grey700")
        self.btn_prev_t = ft.IconButton(ft.Icons.CHEVRON_LEFT,  tooltip="Anterior",
                                        on_click=lambda _: self._ir_pag_t(self._pagina_terreno - 1))
        self.btn_next_t = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Siguiente",
                                        on_click=lambda _: self._ir_pag_t(self._pagina_terreno + 1))
        self.in_pag_t   = ft.TextField(label="Ir a pág.", width=90, height=40,
                                        text_align="center", keyboard_type=ft.KeyboardType.NUMBER)
        self.in_pag_t.on_submit = self._saltar_pag_t
        self.row_pag_t  = self._make_paginacion(
            self.btn_prev_t, self.btn_next_t, self.lbl_pag_t,
            self.in_pag_t,
            ft.IconButton(ft.Icons.ARROW_FORWARD, tooltip="Ir", on_click=self._saltar_pag_t)
        )

        self.txt_estado = ft.Text("Cargando...", color="grey600", italic=True)

        self.btn_tab_1 = ft.Container(
            content=ft.Text("Movimientos de Sistema", weight="bold", color="blue900"),
            padding=15, border=ft.Border(bottom=ft.BorderSide(3,"blue900")),
            ink=True, on_click=lambda e: self.cambiar_tab(0))
        self.btn_tab_2 = ft.Container(
            content=ft.Text("Control de Trabajos a Terreno", weight="bold", color="grey600"),
            padding=15, border=ft.Border(bottom=ft.BorderSide(3,"transparent")),
            ink=True, on_click=lambda e: self.cambiar_tab(1))

        self.cont_general = ft.Container(
            content=ft.Column([
                ft.Row([self.tabla_auditoria], scroll=ft.ScrollMode.ALWAYS),
                self.row_pag_g,
            ], scroll=ft.ScrollMode.ALWAYS, expand=True),
            expand=True, visible=True)

        self.cont_terreno = ft.Container(
            content=ft.Column([
                ft.Row([self.tabla_terreno], scroll=ft.ScrollMode.ALWAYS),
                self.row_pag_t,
            ], scroll=ft.ScrollMode.ALWAYS, expand=True),
            expand=True, visible=False)

        from utils.ui_helpers import sandwich

        _header = ft.Column([
            ft.Row([
                ft.Text("Auditoría y Control de Terreno", size=24, weight="bold", color="blue900", expand=True),
                ft.IconButton(ft.Icons.REFRESH, tooltip="Actualizar auditoría", on_click=lambda _: self.inicializar()),
                ft.ElevatedButton("DESCARGAR REPORTES", icon=ft.Icons.PICTURE_AS_PDF,
                                  on_click=self.exportar_pdf, bgcolor="red700", color="white", height=45,
                                  tooltip="Descargar reporte PDF de auditoría",
                                  visible=estado.puede_hacer("estadisticas","exportar_pdf")),
            ]),
            ft.Divider(height=6, color="transparent"),
            ft.Container(
                content=ft.Column([
                    ft.Text("Filtros de búsqueda", weight="bold", size=14, color="grey800"),
                    ft.Row([
                        self.sel_usuario, self.sel_mes, self.sel_anio,
                        ft.Text(" ó ", weight="bold", color="grey400"),
                        self.in_fecha,
                        ft.Container(expand=True),
                        ft.OutlinedButton("Limpiar", icon=ft.Icons.CLEAR, on_click=self.limpiar_filtros,
                                          height=45, tooltip="Limpiar todos los filtros"),
                        ft.ElevatedButton("Buscar", icon=ft.Icons.SEARCH, on_click=lambda _: self.cargar_datos(),
                                          bgcolor="blue800", color="white", height=45,
                                          tooltip="Buscar con los filtros seleccionados"),
                    ])
                ]), padding=15, bgcolor="white", border_radius=10, border=ft.border.all(1,"grey200")
            ),
            ft.Row([self.btn_tab_1, self.btn_tab_2], spacing=0),
            ft.Divider(height=1, color="grey300"),
            self.txt_estado,
        ], spacing=6)

        _body = ft.Container(
            content=ft.Column([self.cont_general, self.cont_terreno], expand=True, scroll=ft.ScrollMode.AUTO),
            expand=True,
            bgcolor="white", border_radius=10,
            border=ft.border.all(1,"grey200"), padding=10,
        )

        self.content = sandwich(_header, _body)

    # ══════════════════════════════ Cache ══════════════════════════════
    def pre_cargar_si_cache_listo(self):
        from core.cache import app_cache
        if getattr(self, '_usuarios_listos', False) or not app_cache.aud_ready.is_set():
            return
        usuarios = app_cache.aud_usuarios or []
        opc = [ft.dropdown.Option("", "Todos")]
        for u in usuarios:
            opc.append(ft.dropdown.Option(u["nombre"], u["nombre"]))
        self.sel_usuario.options = opc
        self._usuarios_listos = True
        print(f"[AUDITORIA] usuarios pre-cargados ({len(usuarios)})")

    # ══════════════════════════════ Init ══════════════════════════════
    def inicializar(self):
        def _run():
            try:
                if not getattr(self, '_usuarios_listos', False):
                    res_usuarios = get_sb().table("usuarios").select("usuario, nombre").execute()
                    opc = [ft.dropdown.Option("","Todos")]
                    for u in (res_usuarios.data or []):
                        opc.append(ft.dropdown.Option(u["nombre"], u["nombre"]))
                    self.sel_usuario.options = opc
                    if self.page_ref: self.sel_usuario.update()
                self.cargar_datos()
            except Exception as e:
                self.txt_estado.value = f"❌ Error al inicializar: {e}"
                if self.page_ref: self.txt_estado.update()
        hilo(_run)

    def limpiar_filtros(self, e):
        self.sel_usuario.value = ""
        self.sel_mes.value     = ""
        self.sel_anio.value    = ""
        self.in_fecha.value    = ""
        self.cargar_datos()

    # ══════════════════════════════ Carga ══════════════════════════════
    def cargar_datos(self):
        self.txt_estado.value = "Cargando datos..."
        if self.page_ref: self.txt_estado.update()

        def _run():
            try:
                q = get_sb().table("auditoria").select("*")
                if self.sel_usuario.value: q = q.eq("usuario", self.sel_usuario.value)
                if self.in_fecha.value:
                    q = q.gte("fecha", f"{self.in_fecha.value}T00:00:00") \
                         .lte("fecha", f"{self.in_fecha.value}T23:59:59")
                else:
                    if self.sel_anio.value:
                        y = self.sel_anio.value
                        m = self.sel_mes.value if self.sel_mes.value else "01"
                        q = q.gte("fecha", f"{y}-{m}-01T00:00:00")
                        if self.sel_mes.value:
                            import calendar
                            last_day = calendar.monthrange(int(y), int(m))[1]
                            q = q.lte("fecha", f"{y}-{m}-{last_day}T23:59:59")
                        else:
                            q = q.lte("fecha", f"{y}-12-31T23:59:59")

                self.datos_actuales = q.order("fecha", desc=True).execute().data or []
                self._pagina_general = 0
                self._renderizar_pagina_general()

                if self.cont_terreno.visible:
                    self.cargar_terreno()

                if self.page_ref:
                    self.page_ref.update()
            except Exception as e:
                self.txt_estado.value = f"Error: {e}"
                if self.page_ref: self.txt_estado.update()
        hilo(_run)

    def cargar_terreno(self):
        def _run():
            try:
                q = (get_sb().table("movimientos_inventario")
                     .select("*, tipos_trabajo(nombre), usuarios(nombre)")
                     .eq("tipo_movimiento", "DESPACHO_TECNICO"))
                if self.sel_usuario.value:
                    res_u = get_sb().table("usuarios").select("usuario").eq("nombre", self.sel_usuario.value).execute()
                    if res_u.data:
                        q = q.eq("usuario", res_u.data[0]["usuario"])
                self.datos_terreno = q.order("fecha", desc=True).execute().data or []
                self._pagina_terreno = 0
                self._renderizar_pagina_terreno()
                if self.page_ref:
                    self.page_ref.update()
            except Exception as e:
                self.txt_estado.value = f"❌ Error al cargar terreno: {e}"
                if self.page_ref: self.txt_estado.update()
        hilo(_run)

    # ══════════════════════════════ Paginación general ══════════════════════════════
    def _renderizar_pagina_general(self):
        datos = self.datos_actuales
        total = len(datos)
        inicio = self._pagina_general * self._por_pagina
        fin    = min(inicio + self._por_pagina, total)
        pagina_datos = datos[inicio:fin]

        filas = []
        for d in pagina_datos:
            f_str = d.get("fecha", "")
            try: f_str = datetime.datetime.fromisoformat(f_str.replace("Z","+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
            except: f_str = f_str[:16]
            filas.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(f_str, size=12)),
                ft.DataCell(ft.Text(d.get("usuario",""), weight="bold", color="blue900", size=12)),
                ft.DataCell(ft.Text(d.get("accion",""), size=12,
                                    color="orange900" if "ELIMIN" in d.get("accion","") else "black")),
                ft.DataCell(ft.Text(d.get("detalle",""), size=12, color="grey700")),
            ]))

        self.tabla_auditoria.rows = filas
        total_pags = max(1, -(-total // self._por_pagina))
        self.lbl_pag_g.value = f"Página {self._pagina_general + 1} de {total_pags}  ({total} registros)"
        self.btn_prev_g.disabled = self._pagina_general == 0
        self.btn_next_g.disabled = self._pagina_general >= total_pags - 1
        self.txt_estado.value = f"Mostrando {inicio + 1}–{fin} de {total} registros."

    def _ir_pag_g(self, nueva):
        total = len(self.datos_actuales)
        max_p = max(0, -(-total // self._por_pagina) - 1)
        self._pagina_general = max(0, min(nueva, max_p))
        self._renderizar_pagina_general()
        if self.page_ref:
            self.tabla_auditoria.update()
            self.lbl_pag_g.update()
            self.btn_prev_g.update()
            self.btn_next_g.update()
            self.txt_estado.update()

    def _saltar_pag_g(self, e=None):
        try: destino = int(self.in_pag_g.value or "1") - 1
        except: return
        self.in_pag_g.value = ""
        if self.page_ref: self.in_pag_g.update()
        self._ir_pag_g(destino)

    # ══════════════════════════════ Paginación terreno ══════════════════════════════
    def _renderizar_pagina_terreno(self):
        datos = self.datos_terreno
        total = len(datos)
        inicio = self._pagina_terreno * self._por_pagina
        fin    = min(inicio + self._por_pagina, total)
        pagina_datos = datos[inicio:fin]

        filas = []
        for d in pagina_datos:
            f_str = d.get("fecha","")
            try: f_str = datetime.datetime.fromisoformat(f_str.replace("Z","+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
            except: f_str = f_str[:16]
            tipo_nombre    = (d.get("tipos_trabajo") or {}).get("nombre","Sin tipo")
            tecnico_nombre = (d.get("usuarios") or {}).get("nombre", d.get("usuario",""))
            lbl_tipo = ft.Container(
                content=ft.Text(tipo_nombre, size=11, color="white", weight="bold"),
                bgcolor="blue700", padding=ft.Padding(8,2,8,2), border_radius=10)
            prod_str = f"{d.get('cantidad')}x {d.get('sku')} (Desde {d.get('ubicacion_origen','')})"
            filas.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(f_str, size=12)),
                ft.DataCell(ft.Text(tecnico_nombre, weight="bold", color="blue900", size=12)),
                ft.DataCell(lbl_tipo),
                ft.DataCell(ft.Text(prod_str, size=12, color="grey800")),
                ft.DataCell(ft.Text(d.get("comentario",""), size=12, italic=True)),
            ]))

        self.tabla_terreno.rows = filas
        total_pags = max(1, -(-total // self._por_pagina))
        self.lbl_pag_t.value = f"Página {self._pagina_terreno + 1} de {total_pags}  ({total} registros)"
        self.btn_prev_t.disabled = self._pagina_terreno == 0
        self.btn_next_t.disabled = self._pagina_terreno >= total_pags - 1

    def _ir_pag_t(self, nueva):
        total = len(self.datos_terreno)
        max_p = max(0, -(-total // self._por_pagina) - 1)
        self._pagina_terreno = max(0, min(nueva, max_p))
        self._renderizar_pagina_terreno()
        if self.page_ref:
            self.tabla_terreno.update()
            self.lbl_pag_t.update()
            self.btn_prev_t.update()
            self.btn_next_t.update()

    def _saltar_pag_t(self, e=None):
        try: destino = int(self.in_pag_t.value or "1") - 1
        except: return
        self.in_pag_t.value = ""
        if self.page_ref: self.in_pag_t.update()
        self._ir_pag_t(destino)

    # ══════════════════════════════ PDF ══════════════════════════════
    def exportar_pdf(self, e):
        try:
            from fpdf import FPDF
        except ImportError:
            self.mostrar_snack("❌ Instala fpdf2: pip install fpdf2", "red")
            return

        def _safe(text, maxlen=60):
            return str(text or "")[:maxlen].encode("latin-1", errors="replace").decode("latin-1")

        def _run():
            try:
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)

                # ── Movimientos de Sistema ──
                datos  = self.datos_actuales
                cols   = ["Fecha/Hora","Usuario","Accion","Detalle"]
                anchos = [38, 30, 38, 84]

                pdf.add_page()
                pdf.set_font("Helvetica","B",14)
                pdf.cell(0,10,"Auditoria - Movimientos de Sistema", ln=True, align="C")
                pdf.set_font("Helvetica","",9)
                pdf.cell(0,6,f"Generado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} - {len(datos)} registros", ln=True, align="C")
                pdf.ln(3)
                pdf.set_fill_color(30,60,120); pdf.set_text_color(255,255,255)
                pdf.set_font("Helvetica","B",9)
                for col, w in zip(cols, anchos):
                    pdf.cell(w, 8, col, border=1, fill=True)
                pdf.ln()
                pdf.set_text_color(0,0,0); pdf.set_font("Helvetica","",8)
                fill = False
                for d in datos:
                    f_str = d.get("fecha","")
                    try: f_str = datetime.datetime.fromisoformat(f_str.replace("Z","+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
                    except: f_str = f_str[:16]
                    fila = [f_str, d.get("usuario",""), d.get("accion",""), d.get("detalle","") or ""]
                    pdf.set_fill_color(240,245,255) if fill else pdf.set_fill_color(255,255,255)
                    for val, w in zip(fila, anchos):
                        pdf.cell(w, 6, _safe(val), border=1, fill=True)
                    pdf.ln(); fill = not fill

                # ── Control de Terreno ──
                if self.datos_terreno:
                    pdf.add_page()
                    pdf.set_font("Helvetica","B",14); pdf.set_text_color(0,0,0)
                    pdf.cell(0,10,"Auditoria - Control de Trabajos a Terreno", ln=True, align="C")
                    pdf.set_font("Helvetica","",9)
                    pdf.cell(0,6,f"Generado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} - {len(self.datos_terreno)} registros", ln=True, align="C")
                    pdf.ln(3)
                    cols2   = ["Fecha","Tecnico","Tipo Trabajo","Producto","Comentario"]
                    anchos2 = [32, 30, 32, 50, 56]
                    pdf.set_fill_color(180,100,20); pdf.set_text_color(255,255,255)
                    pdf.set_font("Helvetica","B",9)
                    for col, w in zip(cols2, anchos2):
                        pdf.cell(w, 8, col, border=1, fill=True)
                    pdf.ln()
                    pdf.set_text_color(0,0,0); pdf.set_font("Helvetica","",8)
                    fill = False
                    for d in self.datos_terreno:
                        f_str = d.get("fecha","")
                        try: f_str = datetime.datetime.fromisoformat(f_str.replace("Z","+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
                        except: f_str = f_str[:16]
                        tipo    = (d.get("tipos_trabajo") or {}).get("nombre","")
                        tecnico = (d.get("usuarios") or {}).get("nombre", d.get("usuario",""))
                        prod    = f"{d.get('cantidad')}x {d.get('sku')} (Desde {d.get('ubicacion_origen','')})"
                        fila2   = [f_str, tecnico, tipo, prod, d.get("comentario","") or ""]
                        pdf.set_fill_color(255,245,230) if fill else pdf.set_fill_color(255,255,255)
                        for val, w in zip(fila2, anchos2):
                            pdf.cell(w, 6, _safe(val,55), border=1, fill=True)
                        pdf.ln(); fill = not fill

                import base64 as _b64
                _b64str = _b64.b64encode(pdf.output()).decode()
                self.page_ref.launch_url(f"data:application/pdf;base64,{_b64str}")
                self.mostrar_snack("PDF generado correctamente.", "green700")
            except Exception as ex:
                import traceback; traceback.print_exc()
                self.mostrar_snack(f"❌ Error al generar PDF: {ex}", "red")
        hilo(_run)
