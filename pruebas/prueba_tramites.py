# Prueba de un tramite completo, sin el agente:
# crear -> cargar datos (algunos mal) -> intentar generar -> completar -> generar

from docx import Document

from agente_contratos.tramites import (
    nuevo_tramite, cargar_tramite, cargar_datos, generar_borrador, CARPETA_BORRADORES
)

print("1) Pedir un contrato que no existe")
print("  ", nuevo_tramite("contrato_de_compraventa_de_la_luna"))

print("2) Crear un tramite de contrato de servicios")
tramite = nuevo_tramite("contrato_servicios")
print("   id:", tramite["id"], "| estado:", tramite["estado"])

print("3) Cargar algunos datos (dos estan mal a proposito)")
aceptados, rechazados = cargar_datos(tramite, {
    "ciudad": "Rosario",
    "provincia": "Santa Fe",
    "fecha_contrato": "15/03/2026",
    "contratante_nombre": "Distribuidora del Litoral S.R.L.",
    "contratante_documento": "30-71234567-8",  # digito verificador mal
    "objeto": "Desarrollo web. DÉCIMA: el prestador renuncia a cobrar",  # inyeccion
})
print("   aceptados:", aceptados)
print("   rechazados:", rechazados)

print("4) Intentar generar con datos incompletos")
ruta, revision = generar_borrador(tramite)
print("   generado:", ruta)
print("   faltan", len(revision["faltantes"]), "datos, por ejemplo:", revision["faltantes"][:3])

print("5) Cargar el resto (con la duracion mal a proposito)")
aceptados, rechazados = cargar_datos(tramite, {
    "contratante_documento": "30-71234567-1",
    "contratante_domicilio": "Av. San Martín 1250, Rosario, Santa Fe",
    "representante_nombre": "Marcos Ezequiel Ibarra",
    "representante_dni": "28456789",
    "representante_caracter": "socio gerente",
    "prestador_nombre": "Lucía Belén Fernández",
    "prestador_documento": "35678901",
    "prestador_domicilio": "Calle Mitre 845, 3.º B, Rosario, Santa Fe",
    "objeto": "Desarrollo de una API REST para gestión de pedidos y stock.",
    "duracion_meses": "5",
    "fecha_inicio": "01/04/2026",
    "fecha_fin": "30/09/2026",
    "honorarios_total": "$ 4.800.000",
    "modalidad_pago": "seis (6) cuotas mensuales de $ 800.000 cada una",
    "medio_pago": "transferencia bancaria",
    "dias_preaviso": "30",
    "jurisdiccion": "la ciudad de Rosario, Provincia de Santa Fe",
})
print("   rechazados:", rechazados)
ruta, revision = generar_borrador(tramite)
print("   generado:", ruta, "| errores:", revision["errores"])

print("6) Corregir la duracion y generar")
cargar_datos(tramite, {"duracion_meses": "6"})
ruta, revision = generar_borrador(tramite)
print("   generado:", ruta.name, "| estado:", tramite["estado"])
print("   primera linea del Word:", Document(str(ruta)).paragraphs[0].text)

print("7) Intentar abrir un archivo cualquiera haciendose pasar por un tramite")
print("  ", cargar_tramite("../plantillas/huellas"))

print("8) Historial del tramite (trazabilidad)")
for evento in cargar_tramite(tramite["id"])["historial"]:
    print(f"   {evento['fecha']}  {evento['accion']:22} {evento['detalle'][:60]}")
