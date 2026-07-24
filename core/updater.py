import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import urllib.request

import flet as ft

from version import VERSION

_GITHUB_REPO = "wh-4-lien/SicavERP-Web"
_API_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"


def _version_tuple(v):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


def _get_app_path():
    exe = os.path.abspath(sys.executable)
    parts = exe.split(os.sep)
    for i, part in enumerate(parts):
        if part.endswith(".app"):
            return os.sep + os.path.join(*parts[: i + 1])
    return None


def verificar_actualizacion(page):
    def _check():
        try:
            req = urllib.request.Request(_API_URL, headers={"User-Agent": "SicavERP"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())

            latest = data.get("tag_name", "").lstrip("v")
            if not latest or _version_tuple(latest) <= _version_tuple(VERSION):
                return

            asset_url = next(
                (
                    a["browser_download_url"]
                    for a in data.get("assets", [])
                    if a["name"].endswith(".dmg")
                ),
                None,
            )
            if not asset_url:
                return

            _mostrar_dialogo(page, latest, asset_url)
        except Exception as ex:
            print(f"[UPDATER] Error: {ex}")

    threading.Thread(target=_check, daemon=True).start()


def _mostrar_dialogo(page, version, asset_url):
    progress = ft.ProgressBar(visible=False, width=380, color="blue600")
    estado_txt = ft.Text("", size=12, color="grey600")
    btn_update = ft.ElevatedButton(
        "Actualizar ahora", bgcolor="blue600", color="white"
    )
    btn_cancel = ft.TextButton("Más tarde")

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [ft.Icon(ft.Icons.SYSTEM_UPDATE, color="blue600", size=22),
             ft.Text(f"Nueva versión v{version}", weight="bold", size=15)],
            spacing=10,
        ),
        content=ft.Column(
            [
                ft.Text(f"Versión actual: v{VERSION}", size=13),
                ft.Text("Se descargará e instalará automáticamente.", size=13),
                estado_txt,
                progress,
            ],
            tight=True,
            spacing=10,
            width=380,
        ),
        actions=[btn_cancel, btn_update],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def cancelar(_):
        page.pop_dialog()

    def actualizar(_):
        btn_update.disabled = True
        btn_cancel.disabled = True
        progress.visible = True
        estado_txt.value = "Descargando..."
        page.update()
        threading.Thread(
            target=lambda: _instalar(asset_url, estado_txt, progress, page),
            daemon=True,
        ).start()

    btn_update.on_click = actualizar
    btn_cancel.on_click = cancelar
    page.show_dialog(dlg)


def _instalar(asset_url, estado_txt, progress, page):
    def ui(msg):
        estado_txt.value = msg
        page.update()

    mount_point = "/tmp/SicavERP_update"
    tmp_dmg = None

    try:
        # 1. Descargar DMG
        ui("Descargando actualización...")
        tmp_dmg = tempfile.mktemp(suffix=".dmg", prefix="SicavERP-update-")
        urllib.request.urlretrieve(asset_url, tmp_dmg)

        # 2. Montar DMG
        ui("Montando instalador...")
        subprocess.run(["hdiutil", "detach", mount_point, "-quiet", "-force"],
                       capture_output=True)
        r = subprocess.run(
            ["hdiutil", "attach", tmp_dmg, "-nobrowse", "-quiet",
             "-mountpoint", mount_point],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            ui(f"Error montando DMG: {r.stderr.strip()}")
            return

        app_en_dmg = os.path.join(mount_point, "SicavERP.app")
        if not os.path.exists(app_en_dmg):
            ui("No se encontró SicavERP.app en el instalador.")
            subprocess.run(["hdiutil", "detach", mount_point, "-quiet", "-force"],
                           capture_output=True)
            return

        # 3. Detectar dónde está instalada la app actual
        app_actual = _get_app_path()
        if not app_actual:
            ui("Solo funciona cuando la app está instalada como .app")
            subprocess.run(["hdiutil", "detach", mount_point, "-quiet", "-force"],
                           capture_output=True)
            return

        app_dir = os.path.dirname(app_actual)
        app_dest = os.path.join(app_dir, "SicavERP.app")

        # 4. Reemplazar con osascript (pide contraseña admin si hace falta)
        ui("Instalando... (puede pedir contraseña de administrador)")
        src = app_en_dmg.replace("'", "'\\''")
        dst = app_dest.replace("'", "'\\''")
        script = (
            f"do shell script \"rm -rf '{dst}' && cp -R '{src}' '{dst}'\" "
            f"with administrator privileges"
        )
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True)

        subprocess.run(["hdiutil", "detach", mount_point, "-quiet", "-force"],
                       capture_output=True)

        if r.returncode != 0:
            ui("Instalación cancelada o no se autorizó.")
            return

        # 5. Quitar cuarentena
        subprocess.run(["xattr", "-rd", "com.apple.quarantine", app_dest],
                       capture_output=True)

        # 6. Relanzar y salir
        ui("Reiniciando con la nueva versión...")
        import time; time.sleep(1)
        subprocess.Popen(["open", app_dest])
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)

    except Exception as ex:
        ui(f"Error inesperado: {ex}")
    finally:
        if tmp_dmg and os.path.exists(tmp_dmg):
            try:
                os.unlink(tmp_dmg)
            except Exception:
                pass
