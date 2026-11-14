# Completa la plantilla del documento con los datos y guarda el Word

import hashlib
import json
from pathlib import Path

from docxtpl import DocxTemplate
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from agente_contratos.campos import CONTRATOS
from agente_contratos.formatos import armar_datos_plantilla

CARPETA = Path(__file__).resolve().parent.parent
CARPETA_PLANTILLAS = CARPETA / "plantillas"
HUELLAS = CARPETA_PLANTILLAS / "huellas.json"
# la del contrato de servicios (la usan las pruebas)
PLANTILLA = CARPETA_PLANTILLAS / CONTRATOS["contrato_servicios"]["plantilla"]


def ruta_plantilla(tipo):
    return CARPETA_PLANTILLAS / CONTRATOS[tipo]["plantilla"]


def plantilla_sin_cambios(plantilla):
    # comparo la huella de ahora con la que se guardo al crear la plantilla
    # si alguien toco aunque sea una coma, no coinciden
    huellas = json.loads(HUELLAS.read_text(encoding="utf-8"))
    huella_actual = hashlib.sha256(plantilla.read_bytes()).hexdigest()
    return huellas.get(plantilla.name) == huella_actual


def generar_contrato(datos, ruta_salida, tipo="contrato_servicios"):
    plantilla = ruta_plantilla(tipo)
    if not plantilla.exists() or not HUELLAS.exists():
        raise ValueError("Falta la plantilla, hay que ejecutar crear_plantillas.py")

    if not plantilla_sin_cambios(plantilla):
        raise ValueError("La plantilla fue modificada, no se genera el documento")

    valores = armar_datos_plantilla(datos, tipo)

    # sandbox: no deja ejecutar codigo raro desde la plantilla
    # autoescape: los datos se pegan como texto (un & o un < no rompen el Word)
    # StrictUndefined: si falta un dato tira error en vez de dejar el hueco vacio
    entorno = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)

    doc = DocxTemplate(str(plantilla))
    doc.render(valores, jinja_env=entorno, autoescape=True)

    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta_salida))
    return ruta_salida
