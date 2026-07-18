# core/widgets.py
import flet as ft


class BuscadorProducto(ft.Column):
    """
    Campo de búsqueda de producto por SKU o nombre.
    Muestra lista desplegable con coincidencias al escribir.
    on_seleccionar(prod: dict) — recibe el dict del producto seleccionado.
    """
    def __init__(self, label="SKU o Nombre", on_seleccionar=None,
                 width=None, expand=None, height=55,
                 prefix_icon=None, hint_text=None):
        self._on_seleccionar = on_seleccionar
        self._seleccionando = False
        self._busqueda_id = 0

        campo_kw = {}
        if width is not None:    campo_kw["width"]        = width
        if expand is not None:   campo_kw["expand"]       = expand
        if prefix_icon:          campo_kw["prefix_icon"]  = prefix_icon
        if hint_text:            campo_kw["hint_text"]    = hint_text

        self.campo = ft.TextField(label=label, height=height, **campo_kw)
        self.campo.on_change = self._on_change
        self.campo.on_submit = self._on_change

        self._lista = ft.Container(
            content=ft.ListView([], spacing=0, padding=0),
            visible=False,
            bgcolor="white",
            border=ft.border.all(1, "blue200"),
            border_radius=ft.border_radius.only(
                bottom_left=8, bottom_right=8
            ),
            shadow=ft.BoxShadow(
                blur_radius=10, spread_radius=1,
                color=ft.Colors.with_opacity(0.18, "black"),
                offset=ft.Offset(0, 4),
            ),
            height=260,
        )

        col_kw = {}
        if width is not None:    col_kw["width"]  = width
        if expand is not None:   col_kw["expand"] = expand

        super().__init__(
            controls=[self.campo, self._lista],
            spacing=0,
            **col_kw,
        )

    # ── Acceso al valor ──────────────────────────────────────────────────────
    @property
    def value(self):
        return self.campo.value or ""

    @value.setter
    def value(self, v):
        self.campo.value = v

    def limpiar(self):
        """Limpia el campo y oculta la lista."""
        self._seleccionando = True
        self.campo.value = ""
        self._lista.visible = False
        if self.page:
            self.campo.update()
            self._lista.update()
        self._seleccionando = False

    # ── Lógica interna ───────────────────────────────────────────────────────
    def _ocultar(self):
        self._lista.visible = False
        if self.page:
            self._lista.update()

    def _seleccionar(self, prod):
        self._seleccionando = True
        self.campo.value = prod["sku"]
        self._lista.visible = False
        if self.page:
            self.campo.update()
            self._lista.update()
        self._seleccionando = False
        if self._on_seleccionar:
            self._on_seleccionar(prod)

    def _on_change(self, e=None):
        if self._seleccionando:
            return
        texto = (self.campo.value or "").strip()
        if len(texto) < 2:
            self._ocultar()
            return
        self._busqueda_id += 1
        bid = self._busqueda_id
        from core.utilidades import hilo
        hilo(lambda: self._buscar(texto, bid))

    def _buscar(self, texto, bid):
        try:
            from core.database import get_sb

            # 1. SKU exacto → selección automática
            res = get_sb().table("productos").select(
                "sku, nombre, stock_global"
            ).eq("sku", texto).execute()
            if self._busqueda_id != bid:
                return
            if res.data:
                self._seleccionar(res.data[0])
                return

            # 2. Búsqueda por nombre → siempre muestra dropdown con coincidencias
            res = get_sb().table("productos").select(
                "sku, nombre, stock_global"
            ).ilike("nombre", f"%{texto}%").limit(15).execute()
            if self._busqueda_id != bid:
                return
            prods = res.data or []

            if not prods:
                self._ocultar()
                return

            items = []
            for p in prods:
                stk = p.get("stock_global") or 0
                clr = "red600" if stk == 0 else "orange600" if stk <= 3 else "green700"
                _p = dict(p)
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(p["nombre"], size=13, weight="bold",
                                    color="grey900"),
                            ft.Text(f"SKU: {p['sku']}", size=11, color="grey500"),
                        ], spacing=1, expand=True),
                        ft.Container(
                            content=ft.Text(f"{stk} ud.", size=11, weight="bold", color=clr),
                            bgcolor=ft.Colors.with_opacity(0.12, clr),
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            border_radius=12,
                        ),
                    ], spacing=8),
                    padding=ft.Padding(12, 8, 12, 8),
                    ink=True,
                    on_click=lambda e, pr=_p: self._seleccionar(pr),
                    border=ft.border.only(bottom=ft.BorderSide(1, "grey100")),
                    bgcolor="white",
                ))

            self._lista.content.controls = items
            self._lista.visible = True
            if self.page:
                self._lista.update()
                self.update()

        except Exception as ex:
            print(f"[BuscadorProducto] {ex}")
