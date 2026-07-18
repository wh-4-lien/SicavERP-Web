# core/estado.py
from core.database import get_sb

# Acciones disponibles por vista (usadas en gestion_permisos y en las vistas)
ACCIONES_POR_VISTA = {
    "inventario":       {"exportar": "Exportar Excel"},
    "comercial":        {"crear": "Crear / editar productos", "eliminar": "Eliminar productos", "bodegas": "Bodegas", "ajuste": "Ajuste Rápido de Existencias", "sin_justificacion": "Ajuste sin justificación"},
    "movimientos":      {"ejecutar": "Ejecutar traspaso"},
    "categorias":       {"crear": "Crear", "editar": "Editar", "eliminar": "Eliminar"},
    "usuarios":         {"crear": "Crear usuario", "editar": "Editar usuario", "eliminar": "Eliminar usuario"},
    "finanzas":         {"exportar": "Exportar PDF"},
    "graficos":         {"exportar_pdf": "Exportar PDF"},
    "gestion_furgones": {"crear_furgon": "Crear furgón", "eliminar_furgon": "Eliminar furgón", "importar": "Importar stock", "ajustar_stock": "Ajustar stock", "ver_todos": "Ver todos los furgones"},
    "estadisticas":     {"exportar_pdf": "Exportar PDF"},
    "eliminar":         {"ejecutar": "Ejecutar eliminación"},
}

class AppState:
    def __init__(self):
        self.usuario_actual = {"nombre": "", "rol": "", "rol_id": None, "foto": "", "usuario": ""}
        self.PERMISOS_DINAMICOS = {}
        self.ACCIONES_DINAMICAS = {}  # {rol: {vista: {accion}}}
        self.PERMISOS_USUARIO = set()  # vistas con override individual para el usuario actual

    def cargar_permisos(self):
        try:
            res = get_sb().table("configuracion_permisos").select("*, roles(nombre)").execute()

            if res.data:
                nuevo_dict = {}
                for fila in res.data:
                    rol = fila.get("roles", {}).get("nombre") if fila.get("roles") else None
                    if not rol:
                        continue
                    if rol not in nuevo_dict:
                        nuevo_dict[rol] = set()
                    if fila["permitido"]:
                        nuevo_dict[rol].add(fila["vista"])

                self.PERMISOS_DINAMICOS = nuevo_dict
            else:
                self.PERMISOS_DINAMICOS = {}

            # Cargar acciones granulares
            res_a = get_sb().table("permisos_acciones").select("*, roles(nombre)").execute()
            nuevas_acciones = {}
            for fila in (res_a.data or []):
                rol = fila.get("roles", {}).get("nombre") if fila.get("roles") else None
                if not rol or not fila["permitido"]:
                    continue
                if rol not in nuevas_acciones:
                    nuevas_acciones[rol] = {}
                vista = fila["vista"]
                if vista not in nuevas_acciones[rol]:
                    nuevas_acciones[rol][vista] = set()
                nuevas_acciones[rol][vista].add(fila["accion"])
            self.ACCIONES_DINAMICAS = nuevas_acciones

            # REGLA DE ORO: cualquier rol con acceso a "permisos" recibe TODO automáticamente
            todas_vistas = {
                "dashboard", "inventario", "comercial", "categorias", "usuarios",
                "estadisticas", "finanzas", "graficos", "furgo", "gestion_furgones",
                "permisos", "costo", "eliminar", "importar", "movimientos"
            }
            todas_acciones = {vista: set(acc.keys()) for vista, acc in ACCIONES_POR_VISTA.items()}
            for rol_nombre, vistas_set in self.PERMISOS_DINAMICOS.items():
                if "permisos" in vistas_set:
                    self.PERMISOS_DINAMICOS[rol_nombre] = todas_vistas
                    self.ACCIONES_DINAMICAS[rol_nombre] = todas_acciones

            print("[INFO] Permisos cargados (incluyendo override estricto del Admin).")

            # Cargar overrides individuales del usuario actual
            try:
                login = self.usuario_actual.get("usuario", "")
                if login:
                    res_u = get_sb().table("permisos_usuario").select("vista").eq("usuario_login", login).execute()
                    self.PERMISOS_USUARIO = {f["vista"] for f in (res_u.data or [])}
                else:
                    self.PERMISOS_USUARIO = set()
            except Exception:
                self.PERMISOS_USUARIO = set()

        except Exception as e:
            todas_vistas = {
                "dashboard", "inventario", "comercial", "categorias", "usuarios",
                "estadisticas", "finanzas", "graficos", "furgo", "gestion_furgones",
                "permisos", "costo", "eliminar", "importar", "movimientos"
            }
            rol_actual = self.usuario_actual.get("rol", "Admin")
            self.PERMISOS_DINAMICOS = {rol_actual: todas_vistas}
            self.ACCIONES_DINAMICAS = {rol_actual: {vista: set(acc.keys()) for vista, acc in ACCIONES_POR_VISTA.items()}}
            print(f"[ERROR CRÍTICO] No se pudieron cargar permisos de la BD: {e}")

    def puede_ver(self, seccion):
        if seccion in self.PERMISOS_USUARIO:
            return True
        accesos = self.PERMISOS_DINAMICOS.get(self.usuario_actual["rol"], set())
        return seccion in accesos

    def puede_hacer(self, vista, accion):
        """Verifica si el rol actual puede ejecutar una acción en una vista."""
        if vista in self.PERMISOS_USUARIO:
            return True
        rol = self.usuario_actual["rol"]
        return accion in self.ACCIONES_DINAMICAS.get(rol, {}).get(vista, set())

    @property
    def solo_lectura(self):
        return self.usuario_actual["rol"] == "Gerencia"

    @property
    def es_admin(self):
        return self.puede_ver("permisos")

# Instancia global
estado = AppState()
