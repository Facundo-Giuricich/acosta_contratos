"""
Convierte los documentos modelo aprobados por el estudio en plantillas:
  - contrato_ejemplo_CONT-001.docx   -> contrato_servicios.docx
  - expediente_ejemplo_EXP-001.docx  -> expediente_juridico.docx

En los modelos, TODO lo variable está en negrita y el resto es texto aprobado.
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
MODELO_EXPEDIENTE = BASE_DIR / "documentos_modelo" / "expediente_ejemplo_EXP-001.docx"
PLANTILLA_EXPEDIENTE = BASE_DIR / "plantillas" / "expediente_juridico.docx"
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


# Expediente. Algunos textos aparecen varias veces (el abogado, la matricula,
# la fecha de apertura): todas las apariciones van al mismo marcador.
REEMPLAZOS_EXPEDIENTE = {
    # 1. identificacion
    "EXP-2026-0147": "{{ numero_expediente }}",
    "12 de febrero de 2026": "{{ fecha_apertura_texto }}",
    "Reclamo por incumplimiento contractual": "{{ tipo_expediente }}",
    "Derecho Comercial": "{{ area_responsable }}",
    "Dra. Valeria Acosta": "{{ profesional }}",
    "En trámite": "{{ estado }}",
    "Alta": "{{ prioridad }}",
    # 2. caratula
    "Distribuidora del Litoral S.R.L. c/ Transportes Río Paraná S.A. s/ "
    "incumplimiento de contrato de transporte": "{{ caratula }}",
    "Reclamo por daños y perjuicios derivados del incumplimiento de los plazos "
    "de entrega pactados en el contrato de transporte de mercaderías.": "{{ objeto }}",
    "La solicitante contrató servicios de transporte para la distribución de "
    "mercaderías a sucursales del litoral. Durante el período octubre–diciembre "
    "de 2025 se registraron demoras reiteradas y pérdida parcial de carga, con el "
    "consiguiente perjuicio económico.": "{{ descripcion }}",
    # 3. partes
    "Distribuidora del Litoral S.R.L.": "{{ solicitante_nombre }}",
    "30-71234567-8": "{{ solicitante_documento }}",
    "Av. San Martín 1250, Rosario, Santa Fe": "{{ solicitante_domicilio }}",
    "legales@distribuidoradellitoral.example": "{{ solicitante_email }}",
    "+54 341 555-0142": "{{ solicitante_telefono }}",
    "Transportes Río Paraná S.A.": "{{ contraparte_nombre }}",
    "30-70987654-3": "{{ contraparte_documento }}",
    "Ruta Nacional 11 km 12, Santa Fe, Santa Fe": "{{ contraparte_domicilio }}",
    "Representada por su apoderado, Sr. Julián Montiel": "{{ contraparte_informacion }}",
    "T.º 12 F.º 345": "{{ matricula }}",
    "Actúa en carácter de apoderada, conforme poder especial vigente":
        "{{ representacion_observaciones }}",
    # 4. antecedentes
    "En marzo de 2025 las partes celebraron un contrato de transporte con plazos "
    "de entrega de 48 horas. Entre octubre y diciembre de 2025 se acumularon 14 "
    "entregas fuera de plazo y 3 remitos con faltantes, sin respuesta "
    "satisfactoria a los reclamos formales.": "{{ antecedentes }}",
    "18 de noviembre de 2025": "{{ fecha_hecho_texto }}",
    "Consulta presentada por la gerencia de la solicitante el 5 de febrero de 2026":
        "{{ origen_solicitud }}",
    "Contrato de transporte, remitos observados, intercambio de correos y carta "
    "documento enviada el 15 de diciembre de 2025.": "{{ documentacion_inicial }}",
    # 5. actuaciones: queda solo la primera fila (la apertura)
    "12/02/2026": "{{ actuacion_fecha }}",
    "Apertura del expediente y análisis preliminar": "{{ actuacion_detalle }}",
    "Se solicitó documentación adicional": "{{ actuacion_observaciones }}",
    # 7. observaciones y pendientes
    "La contraparte reconoce parte de las demoras pero rechaza la pérdida de carga.":
        "{{ observaciones_generales }}",
    "Detalle de costos logísticos adicionales asumidos por la solicitante.":
        "{{ informacion_pendiente }}",
    "Constancias de recepción de las sucursales y facturas de las compras de reposición.":
        "{{ documentacion_pendiente }}",
    "Cuantificar el daño, intimar a la contraparte y evaluar la mediación "
    "prejudicial obligatoria.": "{{ proximas_acciones }}",
    # 8. estado y conclusiones
    "Fracasada la instancia de conciliación directa, se prepara la documentación "
    "para iniciar la mediación prejudicial.": "{{ resumen_situacion }}",
    "Existen elementos probatorios suficientes para sostener el reclamo por las "
    "demoras; la pérdida de carga requiere prueba adicional.": "{{ conclusiones }}",
    "16 de marzo de 2026": "{{ fecha_actualizacion_texto }}",
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


def reemplazar_negritas(documento, reemplazos):
    """Cambia cada texto en negrita por su marcador. Devuelve cuántos cambió."""
    usados = set()
    for parrafo in todos_los_parrafos(documento):
        for fragmento in parrafo.runs:
            texto = fragmento.text

            # El texto aprobado no puede traer marcadores propios
            if "{{" in texto or "{%" in texto:
                raise ValueError(f"El modelo ya contiene marcadores: {texto!r}")

            if not fragmento.bold or not texto.strip():
                continue  # texto fijo aprobado: no se toca

            if texto not in reemplazos:
                raise ValueError(f"Dato en negrita sin campo asignado: {texto!r}")

            fragmento.text = reemplazos[texto]  # conserva la negrita
            usados.add(texto)

    sin_usar = set(reemplazos) - usados
    if sin_usar:
        raise ValueError(f"Reemplazos no encontrados en el modelo: {sin_usar}")
    return len(usados)


def crear_plantilla_contrato():
    documento = Document(str(MODELO))
    cantidad = reemplazar_negritas(documento, REEMPLAZOS)
    PLANTILLA.parent.mkdir(exist_ok=True)
    documento.save(str(PLANTILLA))
    print(f"Plantilla creada: {PLANTILLA.name} ({cantidad} campos)")
    return PLANTILLA


def crear_plantilla_expediente():
    documento = Document(str(MODELO_EXPEDIENTE))

    # Las tablas de actuaciones (5) y de documentacion (6) traen filas de
    # ejemplo. Un expediente nuevo arranca solo con la actuacion de apertura
    # y sin documentos incorporados: se sacan las demas filas.
    actuaciones, documentacion = documento.tables[0], documento.tables[1]
    for fila in list(actuaciones.rows)[2:]:
        actuaciones._tbl.remove(fila._tr)
    for fila in list(documentacion.rows)[1:]:
        documentacion._tbl.remove(fila._tr)

    cantidad = reemplazar_negritas(documento, REEMPLAZOS_EXPEDIENTE)
    PLANTILLA_EXPEDIENTE.parent.mkdir(exist_ok=True)
    documento.save(str(PLANTILLA_EXPEDIENTE))
    print(f"Plantilla creada: {PLANTILLA_EXPEDIENTE.name} ({cantidad} campos)")
    return PLANTILLA_EXPEDIENTE


def crear_plantillas():
    plantillas = [crear_plantilla_contrato(), crear_plantilla_expediente()]

    # Guardamos la huella de cada plantilla para detectar modificaciones
    huellas = {ruta.name: calcular_huella(ruta) for ruta in plantillas}
    HUELLAS.write_text(json.dumps(huellas, indent=2), encoding="utf-8")
    for nombre, valor in huellas.items():
        print(f"Huella SHA-256 de {nombre}: {valor}")


if __name__ == "__main__":
    crear_plantillas()