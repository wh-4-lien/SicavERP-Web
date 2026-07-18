# vistas/furgones.py
import flet as ft
from core.database import get_sb, fetch_furgones_con_totales
from core.estado import estado
from core.utilidades import hilo, registrar_auditoria

class VistaFurgones(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page_ref = page
        self.expand = True
        self.construir_ui()

    def mostrar_snack(self, mensaje, tipo_o_color="success"):
        from utils.ui_helpers import mostrar_snack as _snack
        _snack(self.page_ref, mensaje, tipo_o_color)

    def construir_ui(self):
        self.lista_furgones = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True)

        # ── Header ──
        header = ft.Row([
            ft.Text("🚚 Gestión de Furgones (Bodegas Móviles)", size=24, weight="bold", color="blue900", expand=True),
            ft.IconButton(ft.Icons.REFRESH, tooltip="Actualizar lista de furgones",
                          on_click=lambda _: self.inicializar()),
        ])

        # ── Body ──
        body = ft.Container(
            content=self.lista_furgones,
            padding=10, bgcolor="white", border_radius=10,
            expand=True,
        )

        from utils.ui_helpers import sandwich
        self.padding = 0
        self.content = sandwich(header, body)

    def inicializar(self):
        self.cargar_furgones()

    def cargar_furgones(self):
        def _run():
            furgones = fetch_furgones_con_totales()
            self.lista_furgones.controls = [
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.LOCAL_SHIPPING, color="blue700"),
                    title=ft.Text(f"{f['nombre']} — Técnico: {f['tecnico_usuario']}"),
                    subtitle=ft.Text(f"Total productos: {f['_total_uds']}"),
                    tooltip=f"Ver detalle de {f['nombre']}",
                    on_click=lambda e, f=f: self.ver_detalle_furgon(f)
                ) for f in furgones
            ]
            if self.page_ref: self.lista_furgones.update()
        hilo(_run)

    def ver_detalle_furgon(self, furgon):
        # Aquí podrías abrir un diálogo con el detalle de los productos del furgón
        self.mostrar_snack(f"Visualizando: {furgon['nombre']}", "info")
