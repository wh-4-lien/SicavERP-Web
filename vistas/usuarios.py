# vistas/usuarios.py
import flet as ft
import os
import shutil
import hashlib
from core.database import get_sb
from core.estado import estado
from core.utilidades import hilo, registrar_auditoria, obtener_ruta_imagen

_IMG_TYPES = [
    ("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tiff *.tif *.ico *.heic *.avif"),
    ("Todos", "*.*"),
]

class VistaUsuarios(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.foto_seleccionada = {"valor": "person.png"}
        self.foto_editando     = {"valor": "person.png"}
        self._picker_foto = ft.FilePicker(on_result=self._on_foto_result)
        self._picker_foto_edit = ft.FilePicker(on_result=self._on_foto_edit_result)
        page.overlay.extend([self._picker_foto, self._picker_foto_edit])
        self.construir_ui()

    def mostrar_snack(self, mensaje, tipo_o_color="success"):
        from utils.ui_helpers import mostrar_snack as _snack
        _snack(self.page_ref, mensaje, tipo_o_color)

    def construir_ui(self):
        puede_crear    = estado.puede_hacer("usuarios", "crear")
        puede_editar   = estado.puede_hacer("usuarios", "editar")
        puede_eliminar = estado.puede_hacer("usuarios", "eliminar")

        # ── Crear ──────────────────────────────────────────────────────────
        self.in_nombre = ft.TextField(label="Nombre Completo", expand=True)
        self.in_user   = ft.TextField(label="Usuario", width=200)
        self.in_pass   = ft.TextField(label="Contraseña", width=200, password=True)
        self.in_rol    = ft.Dropdown(label="Rol", width=180, options=[])

        self.preview_foto    = ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON, size=36), radius=36)
        self.txt_foto_nombre = ft.Text("Sin imagen", size=12, color="grey500", italic=True)

        # ── Editar usuario ─────────────────────────────────────────────────
        self.sel_editar_usuario = ft.Dropdown(label="Usuario a editar", width=220, options=[])

        self.in_edit_nombre_edit = ft.TextField(label="Nombre Completo", expand=True, disabled=True)
        self.in_edit_rol_edit    = ft.Dropdown(label="Rol", width=180, options=[], disabled=True)

        self.preview_foto_edit    = ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON, size=36), radius=36)
        self.txt_foto_edit_nombre = ft.Text("Sin cambios", size=12, color="grey500", italic=True)

        self.btn_subir_foto_edit = ft.ElevatedButton(
            "CAMBIAR FOTO", icon=ft.Icons.UPLOAD, disabled=True,
            tooltip="Seleccionar nueva foto de perfil",
            on_click=self.abrir_selector_foto_edicion,
        )
        self.btn_guardar_edicion = ft.ElevatedButton(
            "GUARDAR CAMBIOS", icon=ft.Icons.SAVE,
            bgcolor="blue800", color="white", disabled=True,
            tooltip="Guardar nombre, rol y foto del usuario seleccionado",
            on_click=self.guardar_edicion_usuario,
        )

        # ── Cambio de contraseña y eliminación ────────────────────────────
        self.in_edit_user  = ft.TextField(label="Usuario", width=200)
        self.in_edit_pass  = ft.TextField(label="Nueva Contraseña", width=200, password=True)
        self.sel_eliminar_usuario = ft.Dropdown(label="Usuario a Eliminar", width=200, options=[])

        # ── Tabla ──────────────────────────────────────────────────────────
        self.lista_usuarios = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Usuario")),
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(ft.Text("Rol")),
            ],
            rows=[],
        )

        # ── Header ─────────────────────────────────────────────────────────
        header = ft.Row([
            ft.Text("👤 Gestión de Usuarios", size=24, weight="bold", color="blue900", expand=True),
            ft.IconButton(ft.Icons.REFRESH, tooltip="Actualizar",
                          on_click=lambda _: (self.cargar_usuarios(), self.cargar_roles())),
        ])

        # ── Body ───────────────────────────────────────────────────────────
        body = ft.Column([

            # 1. Crear
            ft.Container(
                visible=puede_crear,
                content=ft.Column([
                    ft.Text("➕ Crear nuevo usuario", weight="bold"),
                    ft.Row([self.in_nombre, self.in_user, self.in_pass, self.in_rol]),
                    ft.Row([
                        self.preview_foto, self.txt_foto_nombre,
                        ft.ElevatedButton("SUBIR FOTO", icon=ft.Icons.UPLOAD,
                                          tooltip="Seleccionar foto de perfil",
                                          on_click=self.abrir_selector_foto),
                    ]),
                    ft.ElevatedButton("CREAR USUARIO", icon=ft.Icons.PERSON_ADD,
                                      tooltip="Crear nuevo usuario con los datos ingresados",
                                      on_click=self.crear_usuario, bgcolor="green", color="white"),
                ]),
                padding=20, bgcolor="white", border_radius=10, border=ft.border.all(1, "grey300"),
            ),

            ft.Divider(),

            # 2. Editar usuario
            ft.Container(
                visible=puede_editar,
                content=ft.Column([
                    ft.Text("✏️ Editar usuario", weight="bold"),
                    ft.Row([
                        self.sel_editar_usuario,
                        ft.IconButton(
                            ft.Icons.SEARCH, tooltip="Cargar datos del usuario seleccionado",
                            on_click=self.cargar_datos_editar,
                        ),
                    ]),
                    ft.Row([self.in_edit_nombre_edit, self.in_edit_rol_edit]),
                    ft.Row([
                        self.preview_foto_edit, self.txt_foto_edit_nombre,
                        self.btn_subir_foto_edit,
                    ]),
                    self.btn_guardar_edicion,
                ]),
                padding=20, bgcolor="white", border_radius=10, border=ft.border.all(1, "blue100"),
            ),

            ft.Divider(),

            # 3. Contraseña + Eliminar
            ft.Container(
                visible=puede_editar or puede_eliminar,
                content=ft.Column([
                    ft.Container(
                        visible=puede_editar,
                        content=ft.Column([
                            ft.Text("⚙️ Cambiar contraseña", weight="bold"),
                            ft.Row([
                                self.in_edit_user, self.in_edit_pass,
                                ft.ElevatedButton("ACTUALIZAR PASS",
                                                  tooltip="Guardar nueva contraseña",
                                                  on_click=self.actualizar_password),
                            ]),
                        ]),
                    ),
                    ft.Divider(visible=puede_editar and puede_eliminar),
                    ft.Container(
                        visible=puede_eliminar,
                        content=ft.Column([
                            ft.Text("🗑️ Eliminar usuario", weight="bold"),
                            ft.Row([
                                self.sel_eliminar_usuario,
                                ft.ElevatedButton("ELIMINAR", icon=ft.Icons.DELETE,
                                                  tooltip="Eliminar el usuario seleccionado permanentemente",
                                                  on_click=self.eliminar_usuario,
                                                  bgcolor="red", color="white"),
                            ]),
                        ]),
                    ),
                ]),
                padding=20, bgcolor="white", border_radius=10, border=ft.border.all(1, "grey300"),
            ),

            ft.Divider(),

            # 4. Lista
            ft.Container(
                content=ft.Column([
                    ft.Text("👥 Usuarios registrados", weight="bold"),
                    self.lista_usuarios,
                ]),
                padding=20, bgcolor="white", border_radius=10, border=ft.border.all(1, "grey300"),
            ),

        ], scroll=ft.ScrollMode.AUTO, expand=True)

        from utils.ui_helpers import sandwich
        self.padding = 0
        self.content = sandwich(header, body)

    # ── Cache ──────────────────────────────────────────────────────────────
    def pre_cargar_si_cache_listo(self):
        from core.cache import app_cache
        if getattr(self, '_datos_cargados', False) or not app_cache.usu_ready.is_set():
            return
        self._poblar_desde_cache(app_cache)

    def _poblar_desde_cache(self, cache):
        roles    = cache.usu_roles or []
        usuarios = cache.usu_usuarios or []

        opts_roles = [ft.dropdown.Option(key=str(r["id"]), text=r["nombre"]) for r in roles]
        self.in_rol.options           = opts_roles
        self.in_edit_rol_edit.options = opts_roles

        self._actualizar_ui_usuarios(usuarios, do_update=False)
        self._datos_cargados = True
        print(f"[USUARIOS] pre-cargados ({len(usuarios)} usuarios, {len(roles)} roles)")

    # ── Init ───────────────────────────────────────────────────────────────
    def inicializar(self):
        if getattr(self, '_datos_cargados', False):
            return
        self.cargar_usuarios()
        self.cargar_roles()

    def cargar_roles(self):
        def _run():
            try:
                res = get_sb().table("roles").select("id, nombre").execute()
                opts = [ft.dropdown.Option(key=str(r["id"]), text=r["nombre"]) for r in (res.data or [])]
                self.in_rol.options           = opts
                self.in_edit_rol_edit.options = opts
                if self.page_ref:
                    self.in_rol.update()
                    self.in_edit_rol_edit.update()
            except Exception as e:
                print(f"Error cargando roles: {e}")
        hilo(_run)

    def cargar_usuarios(self):
        def _run():
            try:
                res = get_sb().table("usuarios").select("usuario, nombre, rol_id, foto, roles(nombre)").execute()
                datos = res.data or []
                from core.cache import app_cache
                app_cache.usu_usuarios = datos
                self._actualizar_ui_usuarios(datos)
            except Exception as ex:
                print(f"[ERROR USUARIOS] {ex}")
        hilo(_run)

    def _actualizar_ui_usuarios(self, datos, do_update=True):
        self.lista_usuarios.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(u["usuario"])),
                ft.DataCell(ft.Text(u["nombre"])),
                ft.DataCell(ft.Text((u.get("roles") or {}).get("nombre", "—"))),
            ])
            for u in datos
        ]
        opts = [ft.dropdown.Option(u["usuario"]) for u in datos]
        self.sel_eliminar_usuario.options = opts
        self.sel_editar_usuario.options   = opts
        if do_update and self.page_ref:
            try:
                self.lista_usuarios.update()
                self.sel_eliminar_usuario.update()
                self.sel_editar_usuario.update()
            except RuntimeError:
                pass

    def _on_foto_result(self, e: ft.FilePickerResultEvent):
        if e.files and e.files[0].path:
            self.procesar_foto(e.files[0].path)

    # ── Foto creación ───────────────────────────────────────────────────────
    def abrir_selector_foto(self, e):
        self._picker_foto.pick_files(
            dialog_title="Seleccionar foto de perfil",
            allowed_extensions=["png", "jpg", "jpeg", "webp", "bmp", "gif"],
            allow_multiple=False,
        )

    def procesar_foto(self, ruta):
        try:
            ext = os.path.splitext(ruta)[1]
            nombre_destino = f"usr_{self.in_user.value or 'nuevo'}{ext}"
            destino = obtener_ruta_imagen(nombre_destino)
            shutil.copy2(ruta, destino)
            self.foto_seleccionada["valor"] = nombre_destino
            self.preview_foto.foreground_image_src = nombre_destino
            self.txt_foto_nombre.value = f"✅ {nombre_destino}"
            if self.page_ref:
                self.preview_foto.update()
                self.txt_foto_nombre.update()
        except Exception as ex:
            self.mostrar_snack(f"❌ Error al subir foto: {ex}", "error")

    def _on_foto_edit_result(self, e: ft.FilePickerResultEvent):
        if e.files and e.files[0].path:
            self.procesar_foto_edicion(e.files[0].path)

    # ── Foto edición ────────────────────────────────────────────────────────
    def abrir_selector_foto_edicion(self, e):
        self._picker_foto_edit.pick_files(
            dialog_title="Seleccionar nueva foto",
            allowed_extensions=["png", "jpg", "jpeg", "webp", "bmp", "gif"],
            allow_multiple=False,
        )

    def procesar_foto_edicion(self, ruta):
        try:
            usr = self.sel_editar_usuario.value or "edit"
            ext = os.path.splitext(ruta)[1]
            nombre_destino = f"usr_{usr}{ext}"
            destino = obtener_ruta_imagen(nombre_destino)
            shutil.copy2(ruta, destino)
            self.foto_editando["valor"] = nombre_destino
            self.preview_foto_edit.foreground_image_src = nombre_destino
            self.txt_foto_edit_nombre.value = f"✅ {nombre_destino}"
            if self.page_ref:
                self.preview_foto_edit.update()
                self.txt_foto_edit_nombre.update()
        except Exception as ex:
            self.mostrar_snack(f"❌ Error al subir foto: {ex}", "error")

    # ── Editar usuario ──────────────────────────────────────────────────────
    def cargar_datos_editar(self, e):
        usr = self.sel_editar_usuario.value
        if not usr:
            self.mostrar_snack("⚠️ Selecciona un usuario primero", "warning")
            return
        from core.cache import app_cache
        datos = app_cache.usu_usuarios or []
        u = next((x for x in datos if x["usuario"] == usr), None)
        if not u:
            return
        self.in_edit_nombre_edit.value    = u.get("nombre") or ""
        self.in_edit_nombre_edit.disabled = False
        self.in_edit_rol_edit.value       = str(u["rol_id"]) if u.get("rol_id") else None
        self.in_edit_rol_edit.disabled    = False
        self.btn_subir_foto_edit.disabled  = False
        self.btn_guardar_edicion.disabled  = False
        foto_actual = u.get("foto") or "person.png"
        self.foto_editando["valor"] = foto_actual
        self.preview_foto_edit.foreground_image_src = foto_actual
        self.txt_foto_edit_nombre.value = foto_actual
        if self.page_ref:
            self.page_ref.update()

    def guardar_edicion_usuario(self, e):
        usr = self.sel_editar_usuario.value
        if not usr:
            self.mostrar_snack("⚠️ Selecciona un usuario", "warning")
            return
        nombre = (self.in_edit_nombre_edit.value or "").strip()
        if not nombre:
            self.mostrar_snack("⚠️ El nombre no puede estar vacío", "warning")
            return
        datos = {
            "nombre":  nombre,
            "rol_id":  int(self.in_edit_rol_edit.value) if self.in_edit_rol_edit.value else None,
            "foto":    self.foto_editando["valor"],
        }
        def _run():
            try:
                get_sb().table("usuarios").update(datos).eq("usuario", usr).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "EDITAR USUARIO", f"Usuario: {usr}")
                self.mostrar_snack(f"✅ Usuario '{usr}' actualizado", "success")
                self.cargar_usuarios()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error: {ex}", "error")
        hilo(_run)

    # ── Crear usuario ───────────────────────────────────────────────────────
    def crear_usuario(self, e):
        usr = (self.in_user.value or "").strip()
        pwd = (self.in_pass.value or "").strip()
        if not usr or not pwd:
            self.mostrar_snack("⚠️ Completa usuario y contraseña", "warning")
            return
        pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
        datos = {
            "usuario":  usr,
            "password": pwd_hash,
            "nombre":   (self.in_nombre.value or "").strip(),
            "rol_id":   int(self.in_rol.value) if self.in_rol.value else None,
            "foto":     self.foto_seleccionada["valor"],
        }
        def _run():
            try:
                get_sb().table("usuarios").insert(datos).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "CREAR USUARIO", f"Usuario: {usr}")
                self.mostrar_snack(f"✅ Usuario {usr} creado", "success")
                self.in_nombre.value = ""; self.in_user.value = ""; self.in_pass.value = ""
                self.in_rol.value = None; self.foto_seleccionada["valor"] = "person.png"
                if self.page_ref:
                    self.in_nombre.update(); self.in_user.update()
                    self.in_pass.update(); self.in_rol.update()
                self.cargar_usuarios()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error: {ex}", "error")
        hilo(_run)

    # ── Cambiar contraseña ──────────────────────────────────────────────────
    def actualizar_password(self, e):
        usr = self.in_edit_user.value
        pwd = self.in_edit_pass.value
        if not usr or not pwd:
            self.mostrar_snack("⚠️ Completa usuario y contraseña nueva", "warning")
            return
        pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
        def _run():
            try:
                get_sb().table("usuarios").update({"password": pwd_hash}).eq("usuario", usr).execute()
                registrar_auditoria(estado.usuario_actual["nombre"], "CAMBIO CONTRASEÑA", f"Usuario: {usr}")
                self.mostrar_snack("✅ Contraseña actualizada", "success")
                self.in_edit_user.value = ""; self.in_edit_pass.value = ""
                if self.page_ref:
                    self.in_edit_user.update()
                    self.in_edit_pass.update()
            except Exception as ex:
                self.mostrar_snack(f"❌ Error: {ex}", "error")
        hilo(_run)

    # ── Eliminar usuario ────────────────────────────────────────────────────
    def eliminar_usuario(self, e):
        usr = self.sel_eliminar_usuario.value
        if not usr:
            return
        def _ejecutar():
            def _run():
                try:
                    get_sb().table("furgones").update({"tecnico_usuario": None}).eq("tecnico_usuario", usr).execute()
                    get_sb().table("usuarios").delete().eq("usuario", usr).execute()
                    registrar_auditoria(estado.usuario_actual["nombre"], "ELIMINAR USUARIO", f"Usuario: {usr}")
                    self.mostrar_snack(f"🗑️ Usuario '{usr}' eliminado", "success")
                    self.cargar_usuarios()
                except Exception as ex:
                    self.mostrar_snack(f"❌ Error: {ex}", "error")
            hilo(_run)
        from utils.ui_helpers import mostrar_alerta
        mostrar_alerta(
            self.page_ref,
            "Eliminar usuario",
            f"¿Estás seguro de que deseas eliminar el usuario '{usr}'?\nEsta acción no se puede deshacer.",
            _ejecutar,
            texto_confirmar="Sí, eliminar",
        )
