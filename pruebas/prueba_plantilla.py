# Pruebas de la plantilla:
# 1) si la completo con los datos del ejemplo tiene que quedar igual al original
# 2) si meto codigo en un dato se tiene que escribir como texto y no ejecutarse
# 3) si alguien modifica la plantilla no tiene que generar nada

from datetime import date
from pathlib import Path

from docx import Document

from agente_contratos.generador import generar_contrato, PLANTILLA

CARPETA = Path(__file__).resolve().parent.parent
MODELO = CARPETA / "documentos_modelo" / "contrato_ejemplo_CONT-001.docx"
SALIDA = CARPETA / "pruebas" / "salida"

# los mismos datos que tiene el contrato de ejemplo
datos_ejemplo = {
    "ciudad": "Rosario",
    "provincia": "Santa Fe",
    "fecha_contrato": date(2026, 3, 15),
    "contratante_nombre": "Distribuidora del Litoral S.R.L.",
    "contratante_documento": "30-71234567-8",
    "contratante_domicilio": "Av. San Martín 1250, Rosario, Santa Fe",
    "representante_nombre": "Marcos Ezequiel Ibarra",
    "representante_dni": "28.456.789",
    "representante_caracter": "socio gerente",
    "prestador_nombre": "Lucía Belén Fernández",
    "prestador_documento": "35.678.901",
    "prestador_domicilio": "Calle Mitre 845, 3.º B, Rosario, Santa Fe",
    "objeto": "Desarrollo e implementación de una API REST en Python (FastAPI) "
              "para la gestión de pedidos y stock, incluyendo documentación "
              "técnica, pruebas automatizadas y despliegue en el entorno "
              "productivo de LA CONTRATANTE.",
    "duracion_meses": 6,
    "fecha_inicio": date(2026, 4, 1),
    "fecha_fin": date(2026, 9, 30),
    "honorarios_total": 4800000,
    "modalidad_pago": "seis (6) cuotas mensuales, iguales y consecutivas, de "
                      "$ 800.000 cada una, con vencimiento entre el 1 y el 5 "
                      "de cada mes",
    "medio_pago": "transferencia bancaria a la cuenta indicada por EL PRESTADOR",
    "dias_preaviso": 30,
    "jurisdiccion": "la ciudad de Rosario, Provincia de Santa Fe",
}


def leer_texto(ruta):
    # devuelve una lista con el texto de cada parrafo (incluye la tabla de firmas)
    doc = Document(str(ruta))
    lineas = []
    for p in doc.paragraphs:
        lineas.append(p.text)
    for tabla in doc.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                lineas.append(celda.text)
    return lineas


print("Prueba 1: reconstruir el contrato de ejemplo")
generado = generar_contrato(datos_ejemplo, SALIDA / "contrato_reconstruido.docx")
original = leer_texto(MODELO)
nuevo = leer_texto(generado)
if original == nuevo:
    print("  OK, el contrato generado es igual al original")
else:
    print("  ERROR, hay diferencias:")
    for a, b in zip(original, nuevo):
        if a != b:
            print("    original:", a)
            print("    generado:", b)


print("Prueba 2: meter codigo en los datos")
datos = datos_ejemplo.copy()
datos["contratante_nombre"] = "Perez & Hijos <S.A.>"
datos["objeto"] = "{{ 7*7 }}"
generado = generar_contrato(datos, SALIDA / "contrato_con_codigo.docx")
texto = "\n".join(leer_texto(generado))
if "{{ 7*7 }}" in texto and "Perez & Hijos <S.A.>" in texto:
    print("  OK, se escribio como texto y no se ejecuto")
else:
    print("  ERROR, el dato no quedo como texto")


print("Prueba 3: plantilla modificada")
contenido_original = PLANTILLA.read_bytes()
PLANTILLA.write_bytes(contenido_original + b"cambio")  # la "rompo" a proposito
try:
    generar_contrato(datos_ejemplo, SALIDA / "no_deberia_existir.docx")
    print("  ERROR, genero el contrato igual")
except ValueError as error:
    print("  OK, no lo genero:", error)
finally:
    PLANTILLA.write_bytes(contenido_original)  # la dejo como estaba