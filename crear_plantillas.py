"""
Convierte el contrato de ejemplo aprobado por el estudio en una plantilla.

En el modelo, TODO lo variable está en negrita y el resto es texto aprobado.
Reemplazamos cada fragmento en negrita por un marcador {{ campo }} sin tocar
nada más, así se conservan el formato y las cláusulas.
"""

import hashlib
import json
from pathlib import Path

from docx import Document

BASE_DIR = Path(__file__).resolve().parent
MODELO = BASE_DIR / "documentos_modelo" / "contrato_ejemplo_CONT-001.docx"
PLANTILLA = BASE_DIR / "plantillas" / "contrato_servicios.docx"
HUELLAS = BASE_DIR / "plantillas" / "huellas.json"

#Texto en negrita del modelo -> marcador de la plantilla
REEMPLAZOS = {
    "Rosario": "{{ ciudad }}",
    "Santa Fe": "{{ provincia }}",
    "15": "{{ dia }}",
    "marzo": "{{ mes }}",
    "2026": "{{ anio }}",
    "Distribuidora del Litoral S.R.L.": "{{ contratante_nombre }}",
    "30-71234567-8": "{{ contratante_documento }}",
    "Av. San Martín 1250, Rosario, Santa Fe": "{{ contratante_domicilio }}",
    "Marcos Ezequiel Ibarra, DNI 28.456.789, en su carácter de socio gerente":
        "{{ contratante_representacion }}",
    "Lucía Belén Fernández": "{{ prestador_nombre }}",
    "35.678.901": "{{ prestador_documento }}",
    "Calle Mitre 845, 3.º B, Rosario, Santa Fe": "{{ prestador_domicilio }}",
    "Desarrollo e implementación de una API REST en Python (FastAPI) para la "
    "gestión de pedidos y stock, incluyendo documentación técnica, pruebas "
    "automatizadas y despliegue en el entorno productivo de LA CONTRATANTE.":
        "{{ objeto }}",
    "seis (6) meses": "{{ duracion_texto }}",
    "1 de abril de 2026": "{{ fecha_inicio_texto }}",
    "30 de septiembre de 2026": "{{ fecha_fin_texto }}",
    "$ 4.800.000": "{{ honorarios_numero }}",
    "pesos cuatro millones ochocientos mil": "{{ honorarios_letras }}",
    "seis (6) cuotas mensuales, iguales y consecutivas, de $ 800.000 cada "
    "una, con vencimiento entre el 1 y el 5 de cada mes": "{{ modalidad_pago }}",
    "transferencia bancaria a la cuenta indicada por EL PRESTADOR":
        "{{ medio_pago }}",
    "treinta (30)": "{{ preaviso_texto }}",
    "la ciudad de Rosario, Provincia de Santa Fe": "{{ jurisdiccion }}",
    "CUIT 30-71234567-8": "{{ contratante_documento_firma }}",
    "DNI 35.678.901": "{{ prestador_documento_firma }}",
}


def todos_los_parrafos(documento):
    """Párrafos del cuerpo y de las tablas (el bloque de firmas es una tabla)."""
    yield from documento.paragraphs
    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                yield from celda.paragraphs


def calcular_huella(ruta: Path) -> str:
    """SHA-256 del archivo: si cambia un solo byte, cambia la huella."""
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def crear_plantilla_contrato():
    documento = Document(str(MODELO))
    usados = set()

    for parrafo in todos_los_parrafos(documento):
        for fragmento in parrafo.runs:
            texto = fragmento.text

            # El texto aprobado no puede traer marcadores propios
            if "{{" in texto or "{%" in texto:
                raise ValueError(f"El modelo ya contiene marcadores: {texto!r}")

            if not fragmento.bold or not texto.strip():
                continue  # texto fijo aprobado: no se toca

            if texto not in REEMPLAZOS:
                raise ValueError(f"Dato en negrita sin campo asignado: {texto!r}")

            fragmento.text = REEMPLAZOS[texto]  # conserva la negrita
            usados.add(texto)

    sin_usar = set(REEMPLAZOS) - usados
    if sin_usar:
        raise ValueError(f"Reemplazos no encontrados en el modelo: {sin_usar}")

    PLANTILLA.parent.mkdir(exist_ok=True)
    documento.save(str(PLANTILLA))

    # Guardamos la huella para detectar modificaciones posteriores
    huellas = {PLANTILLA.name: calcular_huella(PLANTILLA)}
    HUELLAS.write_text(json.dumps(huellas, indent=2), encoding="utf-8")

    print(f"Plantilla creada: {PLANTILLA.name}")
    print(f"Campos reemplazados: {len(usados)}")
    print(f"Huella SHA-256: {huellas[PLANTILLA.name]}")


if __name__ == "__main__":
    crear_plantilla_contrato()