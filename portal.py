# Portal web del estudio: una interfaz simple para empleados y abogados.
#
#   /         -> el empleado chatea con el asistente y descarga el borrador
#                de SU trámite (el de su sesión de chat)
#   /abogado  -> el abogado entra con matrícula y clave, revisa los borradores
#                pendientes, los aprueba u observa, y descarga la version final
#                en Word y PDF
#
# Es lo mismo que adk web + aprobar.py, pero sin pantallas tecnicas.
# El agente sigue sin poder aprobar: la aprobacion es un formulario aparte
# que pide matricula y clave y usa las mismas funciones que aprobar.py.
#
# Uso (con Ollama abierto):
#   .\env\Scripts\python.exe portal.py
# y abrir http://localhost:8080
#
# Solo escucha en 127.0.0.1 (esta computadora): los datos de los clientes no
# quedan expuestos en la red.

import base64
import binascii
import os
import re
import threading
import time
from pathlib import Path

os.environ.setdefault("OLLAMA_API_BASE", "http://localhost:11434")

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

import aprobar
from agente_contratos import tramites
from agente_contratos.agent import root_agent
from agente_contratos.campos import CONTRATOS, verificar_abogado

CARPETA = Path(__file__).resolve().parent
CARPETA_WEB = CARPETA / "web"
CARPETAS_DESCARGA = {
    "borradores": tramites.CARPETA_BORRADORES,
    "aprobados": aprobar.CARPETA_APROBADOS,
}
APP = "acosta"
USUARIO = "empleado"

app = FastAPI(title="Acosta & Asociados", docs_url=None, redoc_url=None)
runner = InMemoryRunner(agent=root_agent, app_name=APP)


# ---------------------------------------------------------------- credenciales
#
# La pagina del abogado manda en cada pedido el encabezado
#   Authorization: Basic base64("matricula:clave")
# (la pagina la guarda solo en memoria, no en localStorage).
# Despues de 5 intentos fallidos seguidos se bloquea todo 1 minuto, aunque
# despues pongan la clave correcta (asi no se puede probar claves sin parar).

INTENTOS_MAXIMOS = 5
SEGUNDOS_BLOQUEO = 60
BLOQUEO = {"fallidos": 0, "hasta": 0.0}
_candado = threading.Lock()


def leer_credenciales(authorization):
    # "Basic xxxx" -> (matricula, clave), o None si no viene bien armado
    if not authorization:
        return None
    esquema, _, valor = authorization.partition(" ")
    if esquema.lower() != "basic":
        return None
    try:
        texto = base64.b64decode(valor.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    matricula, separador, clave = texto.partition(":")
    if not separador:
        return None
    return matricula, clave


def exigir_abogado(authorization):
    # devuelve (matricula, clave) si son correctas; si no, 401 (o 429 si
    # esta bloqueado por demasiados intentos)
    if not authorization:
        raise HTTPException(401, "Faltan la matrícula y la clave.")
    with _candado:
        if time.monotonic() < BLOQUEO["hasta"]:
            raise HTTPException(429, "Demasiados intentos fallidos. Esperá un minuto y probá de nuevo.")

    credenciales = leer_credenciales(authorization)
    correcto = credenciales is not None and verificar_abogado(*credenciales) is not None

    with _candado:
        if correcto:
            BLOQUEO["fallidos"] = 0
        else:
            BLOQUEO["fallidos"] += 1
            if BLOQUEO["fallidos"] >= INTENTOS_MAXIMOS:
                BLOQUEO["fallidos"] = 0
                BLOQUEO["hasta"] = time.monotonic() + SEGUNDOS_BLOQUEO
    if not correcto:
        raise HTTPException(401, aprobar.MENSAJE_CREDENCIALES)
    return credenciales


def exigir_abogado_para(authorization, id_tramite, accion):
    # igual que exigir_abogado, pero si lo rechaza deja anotado el intento
    # en el historial del tramite
    try:
        return exigir_abogado(authorization)
    except HTTPException as error:
        tramite = tramites.cargar_tramite(id_tramite)
        if tramite:
            tramites.anotar(tramite, f"{accion} rechazada", f"desde el portal: {error.detail}")
            tramites.guardar_tramite(tramite)
        raise


async def tramite_de_la_sesion(id_sesion):
    # el tramite en el que esta trabajando esa sesion de chat (o None)
    if not id_sesion:
        return None
    sesion = await runner.session_service.get_session(
        app_name=APP, user_id=USUARIO, session_id=id_sesion)
    return sesion.state.get("id_tramite") if sesion else None


# ---------------------------------------------------------------- paginas

@app.get("/", response_class=HTMLResponse)
def pagina_empleado():
    return (CARPETA_WEB / "empleado.html").read_text(encoding="utf-8")


@app.get("/abogado", response_class=HTMLResponse)
def pagina_abogado():
    return (CARPETA_WEB / "abogado.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------- descargas

def ruta_descarga(carpeta, archivo):
    # solo archivos generados por el sistema, con el nombre que les pone el
    # sistema (asi nadie puede pedir "../../tramites/..." u otro archivo)
    if carpeta not in CARPETAS_DESCARGA:
        raise HTTPException(404)
    if not re.fullmatch(r"T-\d{8}-\d{6}-[0-9a-f]{4}_(borrador|aprobado)\.(docx|pdf)", archivo):
        raise HTTPException(404)
    return CARPETAS_DESCARGA[carpeta] / archivo


def enviar_archivo(ruta):
    if not ruta.exists():
        raise HTTPException(404)
    return FileResponse(ruta, filename=ruta.name)


@app.get("/descargar/borradores/{archivo}")
async def descargar_borrador(archivo: str, authorization: str | None = Header(None),
                             x_sesion: str | None = Header(None)):
    # lo puede bajar un abogado (con matricula y clave) o el empleado cuya
    # sesion de chat es la de ese tramite
    ruta = ruta_descarga("borradores", archivo)
    if authorization:
        await run_in_threadpool(exigir_abogado, authorization)
    elif x_sesion:
        id_tramite = archivo.split("_")[0]
        if await tramite_de_la_sesion(x_sesion) != id_tramite:
            raise HTTPException(403, "Ese borrador no es de tu trámite.")
    else:
        raise HTTPException(401, "Falta identificarse.")
    return enviar_archivo(ruta)


@app.get("/descargar/aprobados/{archivo}")
def descargar_aprobado(archivo: str, authorization: str | None = Header(None)):
    ruta = ruta_descarga("aprobados", archivo)
    exigir_abogado(authorization)
    return enviar_archivo(ruta)


def enlaces(tramite, abogado):
    # links de descarga que corresponden al estado del tramite.
    # Los aprobados solo los baja el abogado
    resultado = {}
    if tramite.get("borrador"):
        resultado["borrador"] = f"/descargar/borradores/{tramite['borrador']['archivo']}"
    aprobacion = tramite.get("aprobacion")
    if abogado and tramite["estado"] == "aprobado" and aprobacion:
        resultado["word"] = f"/descargar/aprobados/{aprobacion['docx']}"
        if aprobacion.get("pdf"):
            resultado["pdf"] = f"/descargar/aprobados/{aprobacion['pdf']}"
    return resultado


ESTADOS = {
    "cargando_datos": "Cargando datos",
    "borrador_generado": "Borrador listo, esperando al abogado",
    "aprobado": "Aprobado",
}


def resumen_tramite(tramite):
    info = CONTRATOS[tramite["tipo"]]
    revision = tramites.revisar_tramite(tramite)
    obligatorios = [c for c in info["campos"] if c not in info.get("opcionales", [])]
    cargados = [c for c in obligatorios if c in tramite["datos"]]
    return {
        "id": tramite["id"],
        "documento": info["nombre"],
        "estado": ESTADOS.get(tramite["estado"], tramite["estado"]),
        "aprobado": tramite["estado"] == "aprobado",
        "cargados": len(cargados),
        "obligatorios": len(obligatorios),
        # los faltantes vienen como "campo (descripcion)": muestro la descripcion
        "faltan": [re.sub(r"^\w+ \((.*)\)$", r"\1", f) for f in revision["faltantes"]],
        "observaciones": tramite.get("observaciones"),
        "enlaces": enlaces(tramite, abogado=False),
    }


# ---------------------------------------------------------------- empleado

class Mensaje(BaseModel):
    sesion: str | None = None
    texto: str


@app.post("/api/mensaje")
async def mensaje(pedido: Mensaje):
    texto = pedido.texto.strip()
    if not texto:
        raise HTTPException(400, "El mensaje está vacío.")
    if len(texto) > 4000:
        raise HTTPException(400, "El mensaje es demasiado largo.")

    servicio = runner.session_service
    sesion = None
    if pedido.sesion:
        sesion = await servicio.get_session(app_name=APP, user_id=USUARIO, session_id=pedido.sesion)
    if sesion is None:
        sesion = await servicio.create_session(app_name=APP, user_id=USUARIO)

    respuestas = []
    contenido = types.Content(role="user", parts=[types.Part(text=texto)])
    try:
        async for evento in runner.run_async(
            user_id=USUARIO, session_id=sesion.id, new_message=contenido
        ):
            # solo muestro lo que el asistente le escribe al empleado
            # (no las llamadas a herramientas ni sus resultados)
            if evento.author == "user" or not evento.content:
                continue
            for parte in evento.content.parts or []:
                if parte.text and parte.text.strip() and not parte.function_call:
                    respuestas.append(parte.text.strip())
    except Exception:
        respuestas.append(
            "Perdón, no pude comunicarme con el asistente. Revisá que el programa "
            "Ollama esté abierto y probá de nuevo."
        )

    if not respuestas:
        respuestas.append("Perdón, no pude procesar eso. ¿Me lo repetís?")

    # solo se devuelve el tramite de esta sesion
    tramite = None
    id_tramite = await tramite_de_la_sesion(sesion.id)
    if id_tramite:
        datos = tramites.cargar_tramite(id_tramite)
        if datos:
            tramite = resumen_tramite(datos)

    return {"sesion": sesion.id, "respuestas": respuestas, "tramite": tramite}


# ---------------------------------------------------------------- abogado

def tramites_con_estado(estado):
    lista = []
    for archivo in sorted(tramites.CARPETA_TRAMITES.glob("T-*.json"), reverse=True):
        tramite = tramites.cargar_tramite(archivo.stem)
        if tramite and tramite["estado"] == estado:
            lista.append(tramite)
    return lista


@app.get("/api/pendientes")
def pendientes(authorization: str | None = Header(None)):
    exigir_abogado(authorization)

    def fila(t):
        return {
            "id": t["id"],
            "documento": CONTRATOS[t["tipo"]]["nombre"],
            "cliente": aprobar.nombre_del_tramite(t),
            "fecha": (t.get("borrador") or {}).get("fecha")
                     or (t.get("aprobacion") or {}).get("fecha"),
            "aprobado_por": (t.get("aprobacion") or {}).get("abogado"),
            "enlaces": enlaces(t, abogado=True),
        }
    return {
        "pendientes": [fila(t) for t in tramites_con_estado("borrador_generado")],
        "aprobados": [fila(t) for t in tramites_con_estado("aprobado")[:20]],
    }


@app.get("/api/tramite/{id_tramite}")
def ver_tramite(id_tramite: str, authorization: str | None = Header(None)):
    exigir_abogado(authorization)
    tramite = tramites.cargar_tramite(id_tramite)
    if tramite is None:
        raise HTTPException(404, "No existe ese trámite.")
    campos = CONTRATOS[tramite["tipo"]]["campos"]
    revision = tramites.revisar_tramite(tramite)
    return {
        "id": tramite["id"],
        "documento": CONTRATOS[tramite["tipo"]]["nombre"],
        "estado": ESTADOS.get(tramite["estado"], tramite["estado"]),
        "pendiente": tramite["estado"] == "borrador_generado",
        "creado_por": tramite["creado_por"],
        "creado": tramite["creado"],
        "datos": [{"dato": campos[c][1], "valor": str(v)} for c, v in tramite["datos"].items()],
        "advertencias": revision["advertencias"],
        "historial": tramite["historial"][-15:],
        "enlaces": enlaces(tramite, abogado=True),
    }


class Aprobacion(BaseModel):
    id: str


class Observacion(BaseModel):
    id: str
    motivo: str


@app.post("/api/aprobar")
def aprobar_desde_web(pedido: Aprobacion, authorization: str | None = Header(None)):
    # las mismas validaciones que aprobar.py (matricula y clave, datos
    # revalidados, version final desde los datos)
    matricula, clave = exigir_abogado_para(authorization, pedido.id, "aprobacion")
    ok, mensaje = aprobar.aprobar_tramite(pedido.id, matricula, clave)
    tramite = tramites.cargar_tramite(pedido.id)
    return {"ok": ok, "mensaje": mensaje.splitlines()[0],
            "enlaces": enlaces(tramite, abogado=True) if tramite else {}}


@app.post("/api/observar")
def observar_desde_web(pedido: Observacion, authorization: str | None = Header(None)):
    matricula, clave = exigir_abogado_para(authorization, pedido.id, "observacion")
    ok, mensaje = aprobar.observar_tramite(pedido.id, matricula, clave, pedido.motivo)
    return {"ok": ok, "mensaje": mensaje}


if __name__ == "__main__":
    print("Portal del estudio en http://localhost:8080  (abogados: http://localhost:8080/abogado)")
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")
