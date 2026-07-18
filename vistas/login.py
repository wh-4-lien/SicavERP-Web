# vistas/login.py
import flet as ft
import os
import asyncio
import hashlib
from core.database import supabase
from core.estado import estado
from core.utilidades import obtener_ruta_imagen, registrar_auditoria, hilo
from version import VERSION

class VistaLogin(ft.Container):
    def __init__(self, page: ft.Page, on_login_success):
        super().__init__()
        self.main_page = page  
        self.on_login_success = on_login_success
        self.expand = True
        self.construir_ui()

    def construir_ui(self):
        self.in_user = ft.TextField(label="Usuario", width=300, prefix_icon=ft.Icons.PERSON)
        self.in_pass = ft.TextField(label="Contraseña", width=300, password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK)
        self.txt_error = ft.Text("", color="red", weight="bold")
        
        ruta_logo = obtener_ruta_imagen("sicav.png")
        control_logo = ft.Image(src="sicav.png", width=150, height=150) if os.path.exists(ruta_logo) else ft.Icon(ft.Icons.SECURITY, size=80, color="blue900")

        self.content = ft.Column([
            ft.Column([
                control_logo,
                ft.Text("BODEGA SICAV", size=40, weight="black", color="blue900"),
                ft.Text("Acceso Restringido al Personal", size=16, color="grey700"),
                ft.Divider(height=20, color="transparent"),
                self.in_user,
                self.in_pass,
                self.txt_error,
                ft.Divider(height=10, color="transparent"),
                ft.ElevatedButton("INGRESAR AL SISTEMA", icon=ft.Icons.LOGIN, on_click=self.intentar_login, width=300, height=50),
            ], horizontal_alignment="center", alignment="center", expand=True),
            ft.Row([
                ft.Text(f"v{VERSION}", size=11, color="grey400"),
            ], alignment=ft.MainAxisAlignment.END),
        ], expand=True)
        self.padding = 50

    def intentar_login(self, e):
        self.txt_error.value = ""
        self.update()
        usuario  = self.in_user.value
        pwd_raw  = self.in_pass.value
        pwd_hash = hashlib.sha256(pwd_raw.encode()).hexdigest()
        def _run():
            try:
                # Intenta con contraseña hasheada primero
                res = supabase.table("usuarios").select("*, roles(nombre)").eq("usuario", usuario).eq("password", pwd_hash).execute()
                if not res.data:
                    # Fallback: texto plano (período de migración automática)
                    res = supabase.table("usuarios").select("*, roles(nombre)").eq("usuario", usuario).eq("password", pwd_raw).execute()
                    if res.data:
                        supabase.table("usuarios").update({"password": pwd_hash}).eq("usuario", usuario).execute()
                if res.data:
                    user_db = res.data[0]
                    nombre_rol = user_db.get("roles", {}).get("nombre", "Sin Rol") if user_db.get("roles") else "Sin Rol"
                    estado.usuario_actual["rol"]    = nombre_rol
                    estado.usuario_actual["rol_id"] = user_db.get("rol_id")
                    estado.usuario_actual["nombre"] = user_db["nombre"]
                    estado.usuario_actual["usuario"] = user_db["usuario"]
                    estado.usuario_actual["foto"]   = (user_db.get("foto") or "tech.png").replace("assets/", "")
                    registrar_auditoria(user_db["nombre"], "LOGIN", f"Rol: {nombre_rol}")
                    estado.cargar_permisos()
                    self.mostrar_splash()
                else:
                    self.txt_error.value = "❌ Usuario o contraseña incorrectos."
                    self.txt_error.update()
            except Exception as ex:
                self.txt_error.value = f"❌ Error de conexión: {ex}"
                self.txt_error.update()
        hilo(_run)

    def mostrar_splash(self):
        self.content = ft.Column([
            ft.ProgressRing(color="blue900", width=50, height=50, stroke_width=4),
            ft.Container(height=20),
            ft.Text(f"Bienvenido, {estado.usuario_actual['nombre']}", size=24, weight="bold", color="blue900"),
            ft.Text("Iniciando módulos...", color="grey700")
        ], horizontal_alignment="center", alignment="center")
        self.update()
        self.main_page.run_task(self.ir_a_principal)  

    async def ir_a_principal(self):
        await asyncio.sleep(2.0)
        self.on_login_success()
