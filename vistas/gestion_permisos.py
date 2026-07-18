# vistas/gestion_permisos.py
import flet as ft
from core.database import get_sb
from core.estado import estado, ACCIONES_POR_VISTA
from core.utilidades import hilo, registrar_auditoria

VISTAS_DISPONIBLES = [
    "dashboard", "inventario", "comercial", "movimientos", "categorias",
    "usuarios", "estadisticas", "finanzas", "graficos",
    "furgo", "gestion_furgones", "permisos", "costo", "eliminar", "importar"
]

LABELS = {
    "dashboard":        "Dashboard",
    "inventario":       "Inventario",
    "movimientos":      "Traspasos",
    "importar":         "Importar",
    "comercial":        "Ajuste Exprés",
    "finanzas":         "Finanzas",
    "furgo":            "Mi Furgón",
    "gestion_furgones": "Gestión Furgones",
    "graficos":         "Gráficos",
    "estadisticas":     "Auditoría",
    "categorias":       "Categorías",
    "usuarios":         "Usuarios",
    "permisos":         "Permisos de Acceso",
    "costo":            "Ver Costos",
    "eliminar":         "Eliminar Registros",
}

GRUPOS = {
    "📦  Stock e Inventario":       ["inventario", "movimientos", "categorias", "furgo", "gestion_furgones", "importar"],
    "💰  Ventas y Finanzas":        ["comercial", "finanzas", "costo"],
    "📊  Análisis y Reportes":      ["dashboard", "estadisticas", "graficos"],
    "⚙️  Administración":           ["usuarios", "permisos", "eliminar"],
}

ICONOS_GRUPO = {
    "📦  Stock e Inventario":   ft.Icons.INVENTORY_2,
    "💰  Ventas y Finanzas":    ft.Icons.ATTACH_MONEY,
    "📊  Análisis y Reportes":  ft.Icons.BAR_CHART,
    "⚙️  Administración":       ft.Icons.ADMIN_PANEL_SETTINGS,
}


def _avatar(texto, color_bg="blue100", color_txt="blue800"):
    return ft.Container(
        content=ft.Text(texto[:2].upper(), size=13, weight="bold", color=color_txt),
        width=34, height=34, border_radius=17,
        bgcolor=color_bg,
        alignment=ft.Alignment(0, 0),
    )


class VistaGestionPermisos(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.switches_permisos = {}
        self.switches_acciones = {}
        self._roles_map = {}
        self._rol_seleccionado = None
        self._controles_roles = {}   # nombre_rol -> Container card
        self.construir_ui()

    def mostrar_snack(self, mensaje, tipo_o_color="success"):
        from utils.ui_helpers import mostrar_snack as _snack
        _snack(self.page_ref, mensaje, tipo_o_color)

    def pre_cargar_si_cache_listo(self):
        from core.cache import app_cache
        if getattr(self, '_datos_cargados', False) or not app_cache.perm_ready.is_set():
            return
        roles = app_cache.perm_roles or []
        ids_admin = app_cache.perm_admin_ids or set()
        self._roles_map = {r["nombre"]: r["id"] for r in roles}
        self._ids_admin = ids_admin
        # Solo guardar datos — NO modificar controles antes de estar en la página
        # (evita que col_roles quede dirty y falle page.update() desde otros hilos)
        self._roles_editables_cache = [r for r in roles if r["id"] not in ids_admin]
        self._datos_cargados = True
        print(f"[PERMISOS] pre-cargados ({len(self._roles_editables_cache)} roles editables)")

    def inicializar(self):
        if getattr(self, '_datos_cargados', False):
            roles_cache = getattr(self, '_roles_editables_cache', None)
            if roles_cache is not None:
                self._construir_lista_roles(roles_cache)
                self._roles_editables_cache = None
                if self.page_ref:
                    self.page_ref.update()
            return
        self.cargar_lista_roles()

    # ── Roles ──────────────────────────────────────────────────────────────
    def cargar_lista_roles(self):
        def _run():
            try:
                res = get_sb().table("roles").select("id, nombre").execute()
                self._roles_map = {r["nombre"]: r["id"] for r in res.data}

                # Detectar roles admin (los que tienen permiso "permisos"=true)
                res_p = get_sb().table("configuracion_permisos").select("rol_id, permitido").eq("vista", "permisos").eq("permitido", True).execute()
                ids_admin = {f["rol_id"] for f in (res_p.data or [])}
                self._ids_admin = ids_admin

                roles_editables = [r for r in res.data if r["id"] not in ids_admin]
                self._construir_lista_roles(roles_editables)
                self.page_ref.update()
            except Exception as e:
                self.mostrar_snack(f"❌ Error al cargar roles: {e}", "red700")
        hilo(_run)

    def _construir_lista_roles(self, roles):
        self._controles_roles = {}
        items = []
        for r in roles:
            nombre = r["nombre"]
            card = self._card_rol(nombre)
            self._controles_roles[nombre] = card
            items.append(card)
        items.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD, size=14, color="grey500"),
                    ft.Text("Nuevo rol", size=12, color="grey500"),
                ], spacing=6),
                padding=ft.Padding(10, 8, 10, 8),
                border_radius=8,
                border=ft.border.all(1, "grey300"),
                ink=True,
                on_click=self._mostrar_crear_rol,
                margin=ft.Margin(0, 4, 0, 0),
            )
        )
        self.col_roles.controls = items

    def _card_rol(self, nombre):
        es_admin_rol = nombre in self._roles_map and self._es_rol_admin(nombre)
        activo = self._rol_seleccionado == nombre

        cont = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text(nombre[:1].upper(), size=11, weight="bold",
                                    color="blue700" if activo else "grey600"),
                    width=26, height=26, border_radius=13,
                    bgcolor="blue100" if activo else "grey100",
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Text(nombre, size=13, weight="bold" if activo else "normal",
                        color="blue900" if activo else "grey800", expand=True),
                ft.Icon(ft.Icons.LOCK, size=13, color="grey400") if es_admin_rol else ft.Container(width=0),
            ], spacing=8),
            padding=ft.Padding(10, 9, 10, 9),
            border_radius=8,
            bgcolor="blue50" if activo else None,
            border=ft.border.all(1, "blue200") if activo else ft.border.all(1, "transparent"),
            ink=True,
            on_click=lambda e, n=nombre: self._seleccionar_rol(n),
        )
        return cont

    def _es_rol_admin(self, nombre):
        rol_id = self._roles_map.get(nombre)
        if not rol_id:
            return False
        return nombre == self._rol_seleccionado and self.switches_permisos.get("permisos") and self.switches_permisos["permisos"].value

    def _seleccionar_rol(self, nombre):
        self._rol_seleccionado = nombre
        # Actualizar apariencia de cards
        for n, card in self._controles_roles.items():
            activo = n == nombre
            card.bgcolor = "blue50" if activo else None
            card.border = ft.border.all(1, "blue200") if activo else ft.border.all(1, "transparent")
            row = card.content
            row.controls[0].bgcolor = "blue100" if activo else "grey100"
            row.controls[0].content.color = "blue700" if activo else "grey600"
            row.controls[1].weight = "bold" if activo else "normal"
            row.controls[1].color = "blue900" if activo else "grey800"
        self.col_roles.update()
        # Actualizar encabezado del panel derecho
        self.txt_rol_header.value = nombre
        self.txt_rol_header.update()
        self.cont_panel_vacio.visible = False
        self.cont_panel_permisos.visible = True
        self.cont_panel_permisos.update()
        self.cont_panel_vacio.update()
        self.cargar_permisos_rol(nombre)

    def _mostrar_crear_rol(self, e):
        self.cont_crear_rol.visible = True
        self.cont_crear_rol.update()
        self.in_nuevo_rol.focus()

    def crear_nuevo_rol(self, e):
        nuevo = self.in_nuevo_rol.value.strip()
        if not nuevo:
            return
        def _run():
            try:
                get_sb().table("roles").insert({"nombre": nuevo}).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "CREAR ROL", f"Rol: {nuevo}")
                self.in_nuevo_rol.value = ""
                self.cont_crear_rol.visible = False
                self.mostrar_snack(f"Rol '{nuevo}' creado.", "green700")
                self.cargar_lista_roles()
            except Exception as ex:
                self.mostrar_snack(f"Error al crear: {ex}", "red")
        hilo(_run)

    def confirmar_eliminacion(self, e):
        rol = self._rol_seleccionado
        if not rol:
            self.mostrar_snack("Selecciona un rol primero.", "warning"); return
        if self.switches_permisos.get("permisos") and self.switches_permisos["permisos"].value:
            self.mostrar_snack("No puedes eliminar el rol administrador.", "error"); return
        from utils.ui_helpers import mostrar_alerta
        mostrar_alerta(
            self.page_ref,
            "Eliminar rol",
            f"¿Eliminar el rol '{rol}'? Esta acción no se puede deshacer.",
            self._ejecutar_eliminar_sin_args,
            texto_confirmar="Sí, eliminar",
        )

    def _cerrar_confirmar(self, e=None):
        self.cont_confirmar.visible = False
        self.cont_confirmar.update()

    def _ejecutar_eliminar_sin_args(self):
        """Wrapper sin argumento de evento para usar con mostrar_alerta."""
        self._ejecutar_eliminar(None)

    def _ejecutar_eliminar(self, e):
        rol = self._rol_seleccionado
        self._cerrar_confirmar()
        if not rol:
            return
        def _run():
            try:
                rol_id = self._roles_map.get(rol)
                if rol_id:
                    get_sb().table("configuracion_permisos").delete().eq("rol_id", rol_id).execute()
                    get_sb().table("permisos_acciones").delete().eq("rol_id", rol_id).execute()
                get_sb().table("roles").delete().eq("nombre", rol).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "ELIMINAR ROL", f"Rol: {rol}")
                self._rol_seleccionado = None
                self.cont_panel_vacio.visible = True
                self.cont_panel_permisos.visible = False
                self.mostrar_snack(f"Rol '{rol}' eliminado.", "red700")
                self.cargar_lista_roles()
            except Exception as ex:
                self.mostrar_snack(f"Error al eliminar: {ex}", "red")
        hilo(_run)

    # ── Cargar permisos ────────────────────────────────────────────────────
    def cargar_permisos_rol(self, rol=None):
        rol = rol or self._rol_seleccionado
        if not rol:
            return
        def _run():
            try:
                for v in VISTAS_DISPONIBLES:
                    if v in self.switches_permisos:
                        self.switches_permisos[v].value = False
                        self.switches_permisos[v].disabled = False
                for v, acc in self.switches_acciones.items():
                    for sw in acc.values():
                        sw.value = False
                        sw.disabled = False

                rol_id = self._roles_map.get(rol)
                if rol_id:
                    res_v = get_sb().table("configuracion_permisos").select("vista, permitido").eq("rol_id", rol_id).execute()
                    for f in (res_v.data or []):
                        if f["vista"] in self.switches_permisos:
                            self.switches_permisos[f["vista"]].value = f["permitido"]
                    res_a = get_sb().table("permisos_acciones").select("vista, accion, permitido").eq("rol_id", rol_id).execute()
                    for f in (res_a.data or []):
                        sw = self.switches_acciones.get(f["vista"], {}).get(f["accion"])
                        if sw:
                            sw.value = f["permitido"]

                # Si tiene "permisos" → es admin → bloquear todo ON
                if self.switches_permisos.get("permisos") and self.switches_permisos["permisos"].value:
                    for v in VISTAS_DISPONIBLES:
                        self.switches_permisos[v].value = True
                        self.switches_permisos[v].disabled = True
                    for v, acc in self.switches_acciones.items():
                        for sw in acc.values():
                            sw.value = True
                            sw.disabled = True
                    self.btn_eliminar_rol.disabled = True
                else:
                    self.btn_eliminar_rol.disabled = False

                self.page_ref.update()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al cargar permisos: {ex}", "red700")
        hilo(_run)

    # ── Guardar ────────────────────────────────────────────────────────────
    def guardar_permisos(self, e):
        rol = self._rol_seleccionado
        if not rol:
            return
        snap_v = {v: self.switches_permisos[v].value for v in VISTAS_DISPONIBLES}
        snap_a = {v: {a: sw.value for a, sw in acc.items()} for v, acc in self.switches_acciones.items()}

        def _run():
            try:
                rol_id = self._roles_map.get(rol)
                if not rol_id:
                    self.mostrar_snack("Rol no encontrado.", "red"); return

                if snap_v.get("permisos"):
                    for v in VISTAS_DISPONIBLES:
                        snap_v[v] = True
                    for v, acc in snap_a.items():
                        for a in acc:
                            snap_a[v][a] = True

                get_sb().table("configuracion_permisos").delete().eq("rol_id", rol_id).execute()
                get_sb().table("configuracion_permisos").insert(
                    [{"rol_id": rol_id, "vista": v, "permitido": snap_v[v]} for v in VISTAS_DISPONIBLES]
                ).execute()

                get_sb().table("permisos_acciones").delete().eq("rol_id", rol_id).execute()
                rows_a = [
                    {"rol_id": rol_id, "vista": v, "accion": a, "permitido": p}
                    for v, acc in snap_a.items() for a, p in acc.items()
                ]
                if rows_a:
                    get_sb().table("permisos_acciones").insert(rows_a).execute()

                registrar_auditoria(estado.usuario_actual["nombre"], "GUARDAR PERMISOS", f"Rol: {rol}")
                estado.cargar_permisos()
                fn = getattr(self.page_ref, "_actualizar_sidebar", None)
                if fn:
                    fn(); self.page_ref.update()
                self.mostrar_snack(f"Permisos de '{rol}' guardados.", "green700")
            except Exception as ex:
                self.mostrar_snack(f"Error: {ex}", "red")
        hilo(_run)

    # ── UI ─────────────────────────────────────────────────────────────────
    def construir_ui(self):
        self.switches_permisos = {v: ft.Switch(value=False, active_color="green600") for v in VISTAS_DISPONIBLES}
        self.switches_acciones = {
            v: {a: ft.Switch(value=False, active_color="blue600") for a in acc}
            for v, acc in ACCIONES_POR_VISTA.items()
        }

        # ── Panel izquierdo: lista de roles ──
        self.col_roles = ft.Column([], spacing=3, scroll=ft.ScrollMode.AUTO)

        self.in_nuevo_rol = ft.TextField(label="Nombre del rol", height=42, expand=True)
        self.cont_crear_rol = ft.Container(
            visible=False,
            content=ft.Row([
                self.in_nuevo_rol,
                ft.IconButton(ft.Icons.CHECK, icon_color="green600", on_click=self.crear_nuevo_rol),
                ft.IconButton(ft.Icons.CLOSE, icon_color="grey400", on_click=lambda _: setattr(self.cont_crear_rol, 'visible', False) or self.cont_crear_rol.update()),
            ], spacing=4),
            padding=ft.Padding(8, 6, 8, 6),
        )

        panel_izq = ft.Container(
            width=220,
            bgcolor="grey50",
            border=ft.Border(right=ft.BorderSide(1, "grey200")),
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Roles", size=14, weight="bold", color="grey900"),
                        ft.Text("Selecciona para editar", size=11, color="grey500"),
                    ], spacing=2),
                    padding=ft.Padding(16, 14, 16, 14),
                    border=ft.Border(bottom=ft.BorderSide(1, "grey200")),
                ),
                ft.Container(
                    content=ft.Column([self.col_roles, self.cont_crear_rol], spacing=0),
                    padding=ft.Padding(8, 8, 8, 8),
                    expand=True,
                ),
            ], spacing=0, expand=True),
        )

        # ── Panel derecho: vacío inicial ──
        self.cont_panel_vacio = ft.Container(
            expand=True,
            content=ft.Column([
                ft.Icon(ft.Icons.TUNE, size=40, color="grey300"),
                ft.Text("Selecciona un rol para ver sus permisos", size=14, color="grey400"),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            visible=True,
        )

        # ── Encabezado del panel derecho ──
        self.txt_rol_header = ft.Text("", size=16, weight="bold", color="blue900")
        self.btn_eliminar_rol = ft.IconButton(
            ft.Icons.DELETE_OUTLINE, icon_color="red400",
            tooltip="Eliminar este rol permanentemente",
            on_click=self.confirmar_eliminacion,
        )

        self.txt_confirmar = ft.Text("", size=12, color="red800", weight="bold")
        self.cont_confirmar = ft.Container(
            visible=False,
            content=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER, color="red700", size=18),
                self.txt_confirmar,
                ft.Container(expand=True),
                ft.TextButton("Sí, eliminar", on_click=self._ejecutar_eliminar, style=ft.ButtonStyle(color="red700")),
                ft.TextButton("Cancelar", on_click=self._cerrar_confirmar),
            ], spacing=8),
            padding=ft.Padding(12, 8, 12, 8),
            bgcolor=ft.Colors.with_opacity(0.06, "red"),
            border_radius=8,
            border=ft.Border(left=ft.BorderSide(3, "red400")),
            margin=ft.Margin(0, 0, 0, 4),
        )

        # ── Leyenda ──
        def _leyenda_item(color, texto):
            return ft.Row([
                ft.Container(width=10, height=10, bgcolor=color, border_radius=2),
                ft.Text(texto, size=11, color="grey500"),
            ], spacing=6)

        leyenda = ft.Container(
            content=ft.Row([
                _leyenda_item("green600", "Vista habilitada"),
                _leyenda_item("blue500", "Acción permitida"),
                _leyenda_item("grey300", "Sin acceso"),
            ], spacing=20),
            padding=ft.Padding(16, 8, 16, 8),
            bgcolor="grey50",
            border=ft.Border(bottom=ft.BorderSide(1, "grey200")),
        )

        # ── Grupos de permisos ──
        grupos_ui = []
        for titulo_grupo, vistas in GRUPOS.items():
            filas = []
            for v in vistas:
                if v not in self.switches_permisos:
                    continue
                sw_vista = self.switches_permisos[v]
                acc_vista = ACCIONES_POR_VISTA.get(v, {})

                chips = []
                for accion_key, accion_label in acc_vista.items():
                    sw_a = self.switches_acciones[v][accion_key]
                    chips.append(
                        ft.Row([
                            sw_a,
                            ft.Text(accion_label, size=11, color="grey700", width=170),
                        ], spacing=0, tight=True)
                    )

                def _filas_chips(lst, n=3):
                    return [ft.Row(lst[i:i+n], spacing=8) for i in range(0, len(lst), n)]

                acciones_ctrl = ft.Column(_filas_chips(chips), spacing=2) if chips else \
                                ft.Text("Sin acciones específicas", size=11, color="grey400", italic=True)

                fila = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            sw_vista,
                            ft.Text(LABELS.get(v, v), size=13, weight="bold", color="grey800"),
                        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        acciones_ctrl,
                    ], spacing=4),
                    padding=ft.Padding(12, 6, 12, 6),
                    border=ft.Border(top=ft.BorderSide(1, "grey100")),
                )
                filas.append(fila)

            icono = ICONOS_GRUPO.get(titulo_grupo, ft.Icons.CIRCLE)
            grupo_card = ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(icono, size=15, color="grey500"),
                            ft.Text(titulo_grupo.split("  ", 1)[-1], size=12, weight="bold", color="grey600"),
                        ], spacing=8),
                        padding=ft.Padding(12, 9, 12, 9),
                        bgcolor="grey50",
                    ),
                    ft.Column(filas, spacing=0),
                ], spacing=0),
                border=ft.border.all(1, "grey200"),
                border_radius=10,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
            grupos_ui.append(grupo_card)

        self.cont_panel_permisos = ft.Container(
            expand=True,
            visible=False,
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text("R", size=13, weight="bold", color="blue700"),
                            width=34, height=34, border_radius=17,
                            bgcolor="blue100", alignment=ft.Alignment(0, 0),
                        ),
                        self.txt_rol_header,
                        ft.Container(expand=True),
                        self.btn_eliminar_rol,
                        ft.ElevatedButton(
                            "Guardar cambios",
                            icon=ft.Icons.SAVE,
                            on_click=self.guardar_permisos,
                            bgcolor="green600", color="white", height=40,
                            tooltip="Guardar los permisos del rol seleccionado",
                        ),
                    ], spacing=10),
                    padding=ft.Padding(16, 12, 16, 12),
                    border=ft.Border(bottom=ft.BorderSide(1, "grey200")),
                ),
                self.cont_confirmar,
                leyenda,
                ft.Column(grupos_ui, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
            ], spacing=0, expand=True),
        )

        # ── Layout principal ──
        from utils.ui_helpers import sandwich

        self._btn_modo_rol = ft.Container(
            content=ft.Text("Por Rol", weight="bold", color="blue900"),
            border=ft.Border(bottom=ft.BorderSide(2, "blue700")),
            padding=ft.Padding(10, 6, 10, 6), ink=True,
            on_click=lambda _: self._cambiar_modo("rol"),
        )
        self._btn_modo_usr = ft.Container(
            content=ft.Text("Por Usuario", color="grey500"),
            border=ft.Border(bottom=ft.BorderSide(2, "transparent")),
            padding=ft.Padding(10, 6, 10, 6), ink=True,
            on_click=lambda _: self._cambiar_modo("usuario"),
        )

        _header = ft.Column([
            ft.Row([
                ft.Text("Gestión de Roles y Permisos", size=22, weight="bold", color="blue900"),
                ft.Container(expand=True),
                ft.Row([self._btn_modo_rol, self._btn_modo_usr], spacing=0),
                ft.IconButton(ft.Icons.REFRESH, tooltip="Recargar lista de roles",
                              on_click=lambda _: self.cargar_lista_roles()),
            ]),
            ft.Divider(height=1),
        ], spacing=4)

        self.cont_modo_rol = ft.Row([
            panel_izq,
            ft.Container(
                expand=True,
                content=ft.Stack([self.cont_panel_vacio, self.cont_panel_permisos]),
            ),
        ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=0,
           vertical_alignment=ft.CrossAxisAlignment.STRETCH)

        # ── Panel modo usuario ──
        self._usuario_seleccionado = None
        self._usuarios_map = {}
        self.col_usuarios = ft.Column([], spacing=3, scroll=ft.ScrollMode.AUTO)
        self.txt_usuario_header = ft.Text("", size=16, weight="bold", color="purple900")
        self.switches_usuario = {v: ft.Switch(value=False, active_color="purple600") for v in VISTAS_DISPONIBLES}

        filas_usuario_grupos = []
        for titulo_g, vistas_g in GRUPOS.items():
            filas_g = []
            for v in vistas_g:
                if v not in self.switches_usuario:
                    continue
                filas_g.append(ft.Container(
                    content=ft.Row([self.switches_usuario[v], ft.Text(LABELS.get(v, v), size=13, color="grey800")], spacing=4),
                    padding=ft.Padding(12, 6, 12, 6),
                    border=ft.Border(top=ft.BorderSide(1, "grey100")),
                ))
            if not filas_g:
                continue
            icono_g = ICONOS_GRUPO.get(titulo_g, ft.Icons.CIRCLE)
            filas_usuario_grupos.append(ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(icono_g, size=15, color="grey500"),
                            ft.Text(titulo_g.split("  ", 1)[-1], size=12, weight="bold", color="grey600"),
                        ], spacing=8),
                        padding=ft.Padding(12, 9, 12, 9), bgcolor="grey50",
                    ),
                    ft.Column(filas_g, spacing=0),
                ], spacing=0),
                border=ft.border.all(1, "grey200"), border_radius=10,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ))

        self.cont_panel_usr_vacio = ft.Container(
            expand=True,
            content=ft.Column([
                ft.Icon(ft.Icons.PERSON, size=40, color="grey300"),
                ft.Text("Selecciona un usuario para gestionar sus permisos especiales", size=14, color="grey400"),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            visible=True,
        )
        self.cont_panel_usr = ft.Container(
            expand=True, visible=False,
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text("U", size=13, weight="bold", color="purple700"),
                            width=34, height=34, border_radius=17,
                            bgcolor="purple100", alignment=ft.Alignment(0, 0),
                        ),
                        self.txt_usuario_header,
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Guardar permisos", icon=ft.Icons.SAVE,
                            on_click=self.guardar_permisos_usuario,
                            bgcolor="purple600", color="white", height=40,
                        ),
                    ], spacing=10),
                    padding=ft.Padding(16, 12, 16, 12),
                    border=ft.Border(bottom=ft.BorderSide(1, "grey200")),
                ),
                ft.Container(
                    content=ft.Text(
                        "Los switches activados otorgan acceso extra a esa vista, independiente del rol del usuario.",
                        size=12, color="grey500", italic=True,
                    ),
                    padding=ft.Padding(16, 8, 16, 8), bgcolor="purple50",
                    border=ft.Border(bottom=ft.BorderSide(1, "grey200")),
                ),
                ft.Column(filas_usuario_grupos, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
            ], spacing=0, expand=True),
        )

        panel_izq_usr = ft.Container(
            width=220, bgcolor="grey50",
            border=ft.Border(right=ft.BorderSide(1, "grey200")),
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Usuarios", size=14, weight="bold", color="grey900"),
                        ft.Text("Permisos especiales", size=11, color="grey500"),
                    ], spacing=2),
                    padding=ft.Padding(16, 14, 16, 14),
                    border=ft.Border(bottom=ft.BorderSide(1, "grey200")),
                ),
                ft.Container(content=self.col_usuarios, padding=ft.Padding(8, 8, 8, 8), expand=True),
            ], spacing=0, expand=True),
        )

        self.cont_modo_usuario = ft.Row([
            panel_izq_usr,
            ft.Container(expand=True, content=ft.Stack([self.cont_panel_usr_vacio, self.cont_panel_usr])),
        ], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH, visible=False)

        _body = ft.Column([self.cont_modo_rol, self.cont_modo_usuario], expand=True, spacing=0)

        self.content = sandwich(_header, _body)

    # ── Modo usuario ───────────────────────────────────────────────────────
    def _cambiar_modo(self, modo):
        self.cont_modo_rol.visible = (modo == "rol")
        self.cont_modo_usuario.visible = (modo == "usuario")
        self._btn_modo_rol.border = ft.Border(bottom=ft.BorderSide(2, "blue700" if modo == "rol" else "transparent"))
        self._btn_modo_rol.content.color = "blue900" if modo == "rol" else "grey500"
        self._btn_modo_rol.content.weight = "bold" if modo == "rol" else "normal"
        self._btn_modo_usr.border = ft.Border(bottom=ft.BorderSide(2, "blue700" if modo == "usuario" else "transparent"))
        self._btn_modo_usr.content.color = "blue900" if modo == "usuario" else "grey500"
        self._btn_modo_usr.content.weight = "bold" if modo == "usuario" else "normal"
        if modo == "usuario":
            self.cargar_lista_usuarios()
        if self.page_ref:
            self.cont_modo_rol.update()
            self.cont_modo_usuario.update()
            self._btn_modo_rol.update()
            self._btn_modo_usr.update()

    def cargar_lista_usuarios(self):
        def _run():
            try:
                res = get_sb().table("usuarios").select("usuario, nombre, rol_id, roles(nombre)").execute()
                ids_admin = getattr(self, "_ids_admin", set())
                usuarios = [u for u in (res.data or []) if u.get("rol_id") not in ids_admin]
                self._usuarios_map = {u["usuario"]: u for u in usuarios}
                self._construir_lista_usuarios(usuarios)
                if self.page_ref:
                    self.col_usuarios.update()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al cargar usuarios: {ex}", "red700")
        hilo(_run)

    def _construir_lista_usuarios(self, usuarios):
        items = []
        for u in usuarios:
            nombre = u.get("nombre") or u["usuario"]
            login = u["usuario"]
            rol_nombre = (u.get("roles") or {}).get("nombre", "")
            activo = self._usuario_seleccionado == login
            card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(nombre[:1].upper(), size=11, weight="bold",
                                        color="purple700" if activo else "grey600"),
                        width=26, height=26, border_radius=13,
                        bgcolor="purple100" if activo else "grey100",
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column([
                        ft.Text(nombre, size=13, weight="bold" if activo else "normal",
                                color="purple900" if activo else "grey800"),
                        ft.Text(rol_nombre, size=10, color="grey500"),
                    ], spacing=0, tight=True, expand=True),
                ], spacing=8),
                padding=ft.Padding(10, 9, 10, 9), border_radius=8,
                bgcolor="purple50" if activo else None,
                border=ft.border.all(1, "purple200") if activo else ft.border.all(1, "transparent"),
                ink=True,
                on_click=lambda e, l=login, n=nombre: self._seleccionar_usuario(l, n),
            )
            items.append(card)
        self.col_usuarios.controls = items

    def _seleccionar_usuario(self, login, nombre):
        self._usuario_seleccionado = login
        self._construir_lista_usuarios(list(self._usuarios_map.values()))
        self.txt_usuario_header.value = nombre
        self.cont_panel_usr_vacio.visible = False
        self.cont_panel_usr.visible = True
        if self.page_ref:
            self.col_usuarios.update()
            self.cont_panel_usr.update()
            self.cont_panel_usr_vacio.update()
        self.cargar_permisos_usuario(login)

    def cargar_permisos_usuario(self, login):
        def _run():
            try:
                for sw in self.switches_usuario.values():
                    sw.value = False
                res = get_sb().table("permisos_usuario").select("vista").eq("usuario_login", login).execute()
                for f in (res.data or []):
                    if f["vista"] in self.switches_usuario:
                        self.switches_usuario[f["vista"]].value = True
                if self.page_ref:
                    self.page_ref.update()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error al cargar permisos de usuario: {ex}", "red700")
        hilo(_run)

    def guardar_permisos_usuario(self, e):
        login = self._usuario_seleccionado
        if not login:
            return
        vistas_activas = [v for v in VISTAS_DISPONIBLES if self.switches_usuario[v].value]
        def _run():
            try:
                get_sb().table("permisos_usuario").delete().eq("usuario_login", login).execute()
                if vistas_activas:
                    get_sb().table("permisos_usuario").insert(
                        [{"usuario_login": login, "vista": v} for v in vistas_activas]
                    ).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "PERMISOS_USUARIO",
                                    f"Usuario: {login}, Vistas: {vistas_activas}")
                estado.cargar_permisos()
                fn = getattr(self.page_ref, "_actualizar_sidebar", None)
                if fn:
                    fn(); self.page_ref.update()
                self.mostrar_snack(f"✅ Permisos de '{login}' guardados.", "green700")
            except Exception as ex:
                self.mostrar_snack(f"❌ Error: {ex}", "red700")
        hilo(_run)
