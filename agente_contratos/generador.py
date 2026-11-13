# Completa la plantilla del contrato con los datos y guarda el Word

import hashlib
import json
from pathlib import Path

from docxtpl import DocxTemplate
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from agente_contratos.formatos import armar_datos_plantilla

CARPETA = Path(__file__).resolve().parent.parent
PLANTILLA = CARPETA / "plantillas" / "contrato_servicios.docx"
HUELLAS = CARPETA / "plantillas" / "huellas.json"


def plantilla_sin_cambios():
    # comparo la huella de ahora con la que se guardo al crear la plantilla
    # si alguien toco aunque sea una coma, no coinciden
    huellas = json.loads(HUELLAS.read_text(encoding="utf-8"))
    huella_actual = hashlib.sha256(PLANTILLA.read_bytes()).hexdigest()
    return huellas.get(PLANTILLA.name) == huella_actual


def generar_contrato(datos, ruta_salida):
    if not PLANTILLA.exists() or not HUELLAS.exists():
        raise ValueError("Falta la plantilla, hay que ejecutar crear_plantillas.py")

    if not plantilla_sin_cambios():
        raise ValueError("La plantilla fue modificada, no se genera el contrato")

    valores = armar_datos_plantilla(datos)

    # sandbox: no deja ejecutar codigo raro desde la plantilla
    # autoescape: los datos se pegan como texto (un & o un < no rompen el Word)
    # StrictUndefined: si falta un dato tira error en vez de dejar el hueco vacio
    entorno = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)

    doc = DocxTemplate(str(PLANTILLA))
    doc.render(valores, jinja_env=entorno, autoescape=True)

    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta_salida))
    return ruta_salida