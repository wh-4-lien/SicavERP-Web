# utils/ui_helpers.py
# Feedback visual centralizado para toda la app SICAV ERP.
# Importar: from utils.ui_helpers import mostrar_snack, mostrar_alerta, sandwich

import flet as ft

# ── Mapeo de colores legacy → tipo semántico ───────────────────────────
_COLOR_A_TIPO: dict[str, str] = {
    "green700": "success",
    "teal700":  "success",
    "red700":   "error",
    "red":      "error",
    "blue700":  "info",
    "blue":     "info",
    "orange":   "warning",
    "orange700":"warning",
    "amber":    "warning",
}

# ── Configuración visual por tipo ──────────────────────────────────────
_TIPO_CFG: dict[str, dict] = {
    "success": {"color": "teal700",   "icono": ft.Icons.CHECK_CIRCLE_OUTLINE,    "icono_alerta": ft.Icons.CHECK_CIRCLE_OUTLINE},
    "error":   {"color": "red700",    "icono": ft.Icons.ERROR_OUTLINE,           "icono_alerta": ft.Icons.CANCEL_OUTLINED},
    "info":    {"color": "blue700",   "icono": ft.Icons.INFO_OUTLINE,            "icono_alerta": ft.Icons.INFO_OUTLINE},
    "warning": {"color": "orange700", "icono": ft.Icons.WARNING_AMBER_ROUNDED,   "icono_alerta": ft.Icons.WARNING_AMBER_ROUNDED},
}
_DEFAULT_CFG = _TIPO_CFG["info"]


# ══════════════════════════════════════════════════════════════════════
#  mostrar_snack
# ══════════════════════════════════════════════════════════════════════
def mostrar_snack(page: ft.Page, mensaje: str, tipo: str = "success") -> None:
    """
    Muestra un SnackBar no intrusivo en la parte inferior de la pantalla.

    tipo puede ser:
      'success'  → teal   (operación exitosa)
      'error'    → rojo   (fallo o dato inválido)
      'info'     → azul   (estado informativo)
      'warning'  → naranja (advertencia, campo vacío, etc.)

    También acepta los colores legacy ('green700', 'red700', 'orange', 'blue700', …)
    para compatibilidad con llamadas anteriores.
    """
    tipo_real = _COLOR_A_TIPO.get(tipo, tipo)
    cfg       = _TIPO_CFG.get(tipo_real, _DEFAULT_CFG)

    # Limpiar prefijos emoji para no duplicarlos con el icono
    texto = mensaje
    for em in ("✅ ", "❌ ", "🗑️ ", "✏️ ", "⚠️ ", "⏳ ", "📄 ", "🔍 "):
        texto = texto.replace(em, "")

    sb = ft.SnackBar(
        content=ft.Row(
            [
                ft.Icon(cfg["icono"], color="white", size=22),
                ft.Text(texto, color="white", expand=True, size=15),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
        bgcolor=cfg["color"],
        duration=5000,
        behavior=ft.SnackBarBehavior.FLOATING,
        show_close_icon=True,
        close_icon_color="white70",
    )
    page.show_dialog(sb)


# ══════════════════════════════════════════════════════════════════════
#  mostrar_alerta
# ══════════════════════════════════════════════════════════════════════
def mostrar_alerta(
    page:              ft.Page,
    titulo:            str,
    contenido:         str,
    accion_confirmar:  callable,
    texto_confirmar:   str  = "Confirmar",
    texto_cancelar:    str  = "Cancelar",
    tipo:              str  = "warning",
    color_btn:         str  = "red700",
) -> None:
    """
    Muestra un AlertDialog modal con botones Cancelar / Confirmar.
    Llama a accion_confirmar() solo si el usuario confirma.

    tipo controla el icono/color del encabezado ('warning', 'error', 'info', 'success').
    """
    cfg = _TIPO_CFG.get(tipo, _TIPO_CFG["warning"])

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(cfg["icono_alerta"], color=cfg["color"], size=22),
                ft.Text(titulo, weight="bold", size=15),
            ],
            spacing=10,
        ),
        content=ft.Text(contenido, size=13),
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _cerrar(e=None):
        page.pop_dialog()

    def _confirmar(e):
        page.pop_dialog()
        accion_confirmar()

    dlg.actions = [
        ft.TextButton(texto_cancelar, on_click=_cerrar),
        ft.ElevatedButton(
            texto_confirmar,
            bgcolor=color_btn,
            color="white",
            on_click=_confirmar,
        ),
    ]

    page.show_dialog(dlg)


# ══════════════════════════════════════════════════════════════════════
#  sandwich  — layout Header / Body / Footer
# ══════════════════════════════════════════════════════════════════════
def sandwich(
    header: ft.Control,
    body:   ft.Control,
    footer: ft.Control | None = None,
    padding_h: int = 20,
    padding_v: int = 16,
) -> ft.Column:
    """
    Devuelve un ft.Column con estructura Sándwich:
      • Header — fijo, no expande
      • Body   — expande para llenar el espacio restante
      • Footer — fijo, no expande (opcional)

    Uso:
        self.content = sandwich(header, body, footer)
    """
    filas: list[ft.Control] = [
        ft.Container(
            content=header,
            padding=ft.padding.only(
                left=padding_h, right=padding_h,
                top=padding_v, bottom=8,
            ),
        ),
        ft.Container(
            content=body,
            expand=True,
            padding=ft.padding.symmetric(horizontal=padding_h),
        ),
    ]
    if footer is not None:
        filas.append(
            ft.Container(
                content=footer,
                padding=ft.padding.only(
                    left=padding_h, right=padding_h,
                    top=8, bottom=padding_v,
                ),
            )
        )
    return ft.Column(filas, expand=True, spacing=0)


# ══════════════════════════════════════════════════════════════════════
#  btn — constructor de botones con tooltip estandarizado
# ══════════════════════════════════════════════════════════════════════
def btn(
    texto:   str,
    icono:   str | None = None,
    tooltip: str = "",
    color:   str = "blue700",
    on_click = None,
    disabled: bool = False,
    **kwargs,
) -> ft.ElevatedButton:
    """Botón elevado con icono, tooltip y estilo SICAV."""
    return ft.ElevatedButton(
        text=texto,
        icon=icono,
        bgcolor=color,
        color="white",
        tooltip=tooltip or texto,
        on_click=on_click,
        disabled=disabled,
        **kwargs,
    )


def btn_icon(
    icono:   str,
    tooltip: str,
    on_click = None,
    color:   str = "blue700",
    size:    int = 20,
    disabled: bool = False,
) -> ft.IconButton:
    """Botón de icono con tooltip obligatorio."""
    return ft.IconButton(
        icon=icono,
        icon_color=color,
        tooltip=tooltip,
        on_click=on_click,
        icon_size=size,
        disabled=disabled,
    )


def spinner_view(mensaje: str = "Cargando datos...") -> ft.Column:
    """Spinner de carga centrado — úsalo como valor inicial de self.content."""
    return ft.Column(
        [
            ft.ProgressRing(width=48, height=48, stroke_width=3, color="blue700"),
            ft.Text(mensaje, color="grey500", italic=True, size=13),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        expand=True,
        spacing=14,
    )
