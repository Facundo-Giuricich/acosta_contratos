# Manejo de los tramites (cada pedido de contrato es un tramite).
# Cada tramite se guarda en un archivo JSON en la carpeta "tramites" con:
#   - los datos que se fueron cargando
#   - el estado (cargando_datos, borrador_generado, aprobado)
#   - un historial de todo lo que paso, cuando y quien (trazabilidad)

import getpass
import hashlib
import json
import re
import secrets
from datetime import date, datetime
from pathlib import Path

from docx import Document
from docx.shared import RGBColor

from agente_contratos.campos import CONTRATOS
from agente_contratos.generador import generar_contrato
from agente_contratos.validacion import validar_campo, campos_faltantes, revisar_consistencia

CARPETA = Path(__file__).resolve().parent.parent
CARPETA_TRAMITES = CARPETA / "tramites"
CARPETA_BORRADORES = CARPETA / "generados" / "borradores"
REGISTRO = CARPETA / "registros" / "registro.log"


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def anotar(tramite, accion, detalle=""):
    # guarda el evento en el historial del tramite
    tramite["historial"].append({
        "fecha": ahora(),
        "usuario": getpass.getuser(),
        "accion": accion,
        "detalle": detalle,
    })
    # y una linea en el registro general (sin datos personales, solo que paso)
    REGISTRO.parent.mkdir(exist_ok=True)
    with open(REGISTRO, "a", encoding="utf-8") as archivo:
        archivo.write(f"{ahora()} | {tramite['id']} | {getpass.getuser()} | {accion}\n")


def ruta_tramite(id_tramite):
    # el id tiene que tener la forma T-20261111-120455-3f2a
    # asi nadie puede pasar algo como "../../otro_archivo" y leer cualquier cosa
    if not isinstance(id_tramite, str):
        return None
    if not re.fullmatch(r"T-\d{8}-\d{6}-[0-9a-f]{4}", id_tramite):
        return None
    return CARPETA_TRAMITES / f"{id_tramite}.json"


def guardar_tramite(tramite):
    CARPETA_TRAMITES.mkdir(exist_ok=True)
    ruta = ruta_tramite(tramite["id"])
    ruta.write_text(json.dumps(tramite, indent=2, ensure_ascii=False), encoding="utf-8")


def cargar_tramite(id_tramite):
    ruta = ruta_tramite(id_tramite)
    if ruta is None or not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def nuevo_tramite(tipo):
    if tipo not in CONTRATOS:
        return None

    tramite = {
        "id": f"T-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}",
        "tipo": tipo,
        "estado": "cargando_datos",
        "creado": ahora(),
        "creado_por": getpass.getuser(),
        "datos": {},
        "borrador": None,
        "historial": [],
    }
    anotar(tramite, "tramite creado", CONTRATOS[tipo]["nombre"])
    guardar_tramite(tramite)
    return tramite


def cargar_datos(tramite, datos_nuevos):
    # datos_nuevos es un diccionario {campo: valor}
    # devuelve la lista de campos aceptados y la lista de rechazados con el motivo
    if tramite["estado"] == "aprobado":
        return [], ["El trámite ya está aprobado, no se puede modificar."]

    aceptados = []
    rechazados = []

    for campo, valor in datos_nuevos.items():
        limpio, error = validar_campo(tramite["tipo"], campo, valor)
        if error:
            rechazados.append(f"{campo}: {error}")
            # anoto el motivo pero no el valor (podria ser cualquier cosa)
            anotar(tramite, "dato rechazado", f"{campo}: {error}")
            continue

        if isinstance(limpio, date):
            limpio = limpio.isoformat()  # en el JSON las fechas van como texto

        anterior = tramite["datos"].get(campo)
        tramite["datos"][campo] = limpio
        aceptados.append(campo)
        if anterior is None:
            anotar(tramite, "dato cargado", f"{campo} = {limpio}")
        elif anterior != limpio:
            anotar(tramite, "dato corregido", f"{campo}: {anterior} -> {limpio}")

    # si ya habia un borrador y cambiaron los datos, ese borrador quedo viejo
    if aceptados and tramite["estado"] == "borrador_generado":
        tramite["estado"] = "cargando_datos"
        tramite["borrador"] = None
        anotar(tramite, "borrador anulado", "se modificaron datos")

    guardar_tramite(tramite)
    return aceptados, rechazados


def datos_validados(tramite):
    # vuelvo a validar todo lo guardado antes de usarlo,
    # por si alguien edito el JSON a mano
    datos = {}
    errores = []
    for campo, valor in tramite["datos"].items():
        limpio, error = validar_campo(tramite["tipo"], campo, valor)
        if error:
            errores.append(f"{campo}: {error}")
        else:
            datos[campo] = limpio
    return datos, errores


def revisar_tramite(tramite):
    # junta todo lo que falta o esta mal para poder generar el contrato
    campos = CONTRATOS[tramite["tipo"]]["campos"]
    datos, errores = datos_validados(tramite)

    faltantes = []
    for campo in campos_faltantes(tramite["tipo"], datos):
        faltantes.append(f"{campo} ({campos[campo][1]})")

    errores_consistencia, advertencias = revisar_consistencia(datos)
    errores = errores + errores_consistencia

    return {
        "faltantes": faltantes,
        "errores": errores,
        "advertencias": advertencias,
        "listo_para_generar": len(faltantes) == 0 and len(errores) == 0,
    }


def marcar_como_borrador(ruta):
    # agrega un aviso en rojo arriba de todo: esto NO es un contrato aprobado
    doc = Document(str(ruta))
    aviso = doc.paragraphs[0].insert_paragraph_before()
    texto = aviso.add_run(
        "BORRADOR - PENDIENTE DE REVISIÓN Y APROBACIÓN PROFESIONAL. "
        "SIN VALIDEZ LEGAL."
    )
    texto.bold = True
    texto.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    doc.save(str(ruta))


def generar_borrador(tramite):
    revision = revisar_tramite(tramite)

    if not revision["listo_para_generar"]:
        anotar(tramite, "generacion rechazada", "faltan datos o hay errores")
        guardar_tramite(tramite)
        return None, revision

    datos, _ = datos_validados(tramite)
    ruta = CARPETA_BORRADORES / f"{tramite['id']}_borrador.docx"

    try:
        generar_contrato(datos, ruta, tramite["tipo"])
    except ValueError as error:
        revision["errores"].append(str(error))
        revision["listo_para_generar"] = False
        anotar(tramite, "generacion fallida", str(error))
        guardar_tramite(tramite)
        return None, revision

    marcar_como_borrador(ruta)

    # guardo la huella del archivo generado: asi queda registrado exactamente
    # que documento salio de este tramite
    huella = hashlib.sha256(ruta.read_bytes()).hexdigest()
    tramite["estado"] = "borrador_generado"
    tramite["borrador"] = {"archivo": ruta.name, "huella": huella, "fecha": ahora()}
    anotar(tramite, "borrador generado", f"{ruta.name} (huella {huella[:12]}...)")
    guardar_tramite(tramite)
    return ruta, revision