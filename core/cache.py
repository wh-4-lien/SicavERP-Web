# core/cache.py
# Almacenamiento anticipado de datos de BD para evitar esperas al navegar entre vistas.
import threading


class AppCache:
    def __init__(self):
        # Inventario
        self.inv_bodegas: list | None = None          # [{"id", "nombre"}]
        self.inv_arbol_data: dict | None = None       # {"Familia": ["Sub1", ...]}
        self.inv_productos: list | None = None        # formato procesado (no raw)
        self.inv_sku_bodegas_map: dict | None = None  # sku -> [{bodega, area}]
        self.inv_ready = threading.Event()

        # Movimientos
        self.mov_bodegas: list | None = None       # [{"id", "nombre"}]
        self.mov_historial: list | None = None     # filas raw de Supabase
        self.mov_ready = threading.Event()

        # Finanzas
        self.fin_bodegas: list | None = None
        self.fin_furgones: list | None = None              # [{id, nombre}]
        self.fin_productos_raw: list | None = None         # raw de Supabase con joins
        self.fin_bp_raw: list | None = None                # bodega_productos con bodegas+areas
        self.fin_historial_movs: list | None = None
        self.fin_historial_costo_map: dict | None = None
        self.fin_ready = threading.Event()

        # Dashboard (auditoria; productos reutiliza inv_productos)
        self.dash_auditoria_reciente: list | None = None   # últimas 10 filas
        self.dash_auditoria_top500: list | None = None     # últimas 500 filas para conteo
        self.dash_ready = threading.Event()

        # Categorías
        self.cat_familias: list | None = None      # [nombre]
        self.cat_subfamilias: list | None = None   # [{nombre, familia_nombre}]
        self.cat_tipos: list | None = None         # [{id, nombre}] — tipos_trabajo
        self.cat_areas: list | None = None         # [{id, nombre}] — areas
        self.cat_ready = threading.Event()

        # Auditoría (solo dropdown de usuarios; datos filtrados se cargan al visitar)
        self.aud_usuarios: list | None = None      # [{usuario, nombre}]
        self.aud_ready = threading.Event()

        # Usuarios
        self.usu_roles: list | None = None         # [{id, nombre}]
        self.usu_usuarios: list | None = None      # [{usuario, nombre, roles(nombre)}]
        self.usu_ready = threading.Event()

        # Gestión de Permisos
        self.perm_roles: list | None = None        # [{id, nombre}]
        self.perm_admin_ids: set | None = None     # {rol_id} de roles con permiso "permisos"
        self.perm_ready = threading.Event()

        # Gestión de Furgones (N+1 consolidado)
        self.gfur_usuarios: list | None = None     # [{usuario, nombre, roles(nombre)}]
        self.gfur_furgones: list | None = None     # raw furgones
        self.gfur_fp_counts: dict | None = None   # {furgon_id: n_productos}
        self.gfur_ready = threading.Event()

        # Gráficos
        self.gra_productos: list | None = None
        self.gra_auditoria: list | None = None
        self.gra_movimientos: list | None = None
        self.gra_bodegas: list | None = None
        self.gra_bp: list | None = None
        self.gra_furgones: list | None = None
        self.gra_fp: list | None = None
        self.gra_ready = threading.Event()

    def reset(self):
        self.__init__()


app_cache = AppCache()
