# Pruebas del segundo tipo de documento: el expediente juridico.
# 1) con los datos del ejemplo, el expediente generado tiene que quedar igual
#    al modelo del estudio (salvo las filas de ejemplo de las tablas, que un
#    expediente nuevo no tiene)
# 2) validaciones propias del expediente (abogado, email, prioridad, fechas)
# 3) un tramite completo de expediente, sin el modelo
#
# Uso: .\env\Scripts\python.exe -m pruebas.prueba_expediente

from datetime import date
from pathlib import Path

from docx import Document

from agente_contratos import tramites
from agente_contratos.generador import generar_contrato
from agente_contratos.validacion import validar_campo, revisar_consistencia

CARPETA = Path(__file__).resolve().parent.parent
MODELO = CARPETA / "documentos_modelo" / "expediente_ejemplo_EXP-001.docx"
SALIDA = CARPETA / "pruebas" / "salida"
TIPO = "expediente_juridico"

fallas = 0
total = 0


def control(nombre, ok, detalle=""):
    global fallas, total
    total += 1
    if not ok:
        fallas += 1
    print(f"  {'OK   ' if ok else 'ERROR'} {nombre} {detalle}")


# los mismos datos que tiene el expediente de ejemplo
# (el CUIT del ejemplo esta mal a proposito; aca se prueba el generador,
# que recibe datos ya validados)
DATOS_EJEMPLO = {
    "numero_expediente": "EXP-2026-0147",
    "fecha_apertura": date(2026, 2, 12),
    "tipo_expediente": "Reclamo por incumplimiento contractual",
    "area_responsable": "Derecho Comercial",
    "profesional_responsable": "Dra. Valeria Acosta",
    "prioridad": "Alta",
    "materia": "incumplimiento de contrato de transporte",
    "objeto": "Reclamo por daños y perjuicios derivados del incumplimiento de los "
              "plazos de entrega pactados en el contrato de transporte de mercaderías.",
    "descripcion": "La solicitante contrató servicios de transporte para la distribución "
                   "de mercaderías a sucursales del litoral. Durante el período "
                   "octubre–diciembre de 2025 se registraron demoras reiteradas y "
                   "pérdida parcial de carga, con el consiguiente perjuicio económico.",
    "solicitante_nombre": "Distribuidora del Litoral S.R.L.",
    "solicitante_documento": "30-71234567-8",
    "solicitante_domicilio": "Av. San Martín 1250, Rosario, Santa Fe",
    "solicitante_email": "legales@distribuidoradellitoral.example",
    "solicitante_telefono": "+54 341 555-0142",
    "contraparte_nombre": "Transportes Río Paraná S.A.",
    "contraparte_documento": "30-70987654-3",
    "contraparte_domicilio": "Ruta Nacional 11 km 12, Santa Fe, Santa Fe",
    "contraparte_informacion": "Representada por su apoderado, Sr. Julián Montiel",
    "representacion_observaciones": "Actúa en carácter de apoderada, conforme poder especial vigente",
    "antecedentes": "En marzo de 2025 las partes celebraron un contrato de transporte con "
                    "plazos de entrega de 48 horas. Entre octubre y diciembre de 2025 se "
                    "acumularon 14 entregas fuera de plazo y 3 remitos con faltantes, sin "
                    "respuesta satisfactoria a los reclamos formales.",
    "fecha_hecho": date(2025, 11, 18),
    "origen_solicitud": "Consulta presentada por la gerencia de la solicitante el 5 de febrero de 2026",
    "documentacion_inicial": "Contrato de transporte, remitos observados, intercambio de "
                             "correos y carta documento enviada el 15 de diciembre de 2025.",
    "observaciones_generales": "La contraparte reconoce parte de las demoras pero rechaza la pérdida de carga.",
    "informacion_pendiente": "Detalle de costos logísticos adicionales asumidos por la solicitante.",
    "documentacion_pendiente": "Constancias de recepción de las sucursales y facturas de las compras de reposición.",
    "proximas_acciones": "Cuantificar el daño, intimar a la contraparte y evaluar la mediación prejudicial obligatoria.",
    "resumen_situacion": "Fracasada la instancia de conciliación directa, se prepara la "
                         "documentación para iniciar la mediación prejudicial.",
}


def parrafos(ruta):
    return [p.text for p in Document(str(ruta)).paragraphs]


print("1) Reconstruir el expediente de ejemplo")
generado = generar_contrato(DATOS_EJEMPLO, SALIDA / "expediente_reconstruido.docx", TIPO)
original = parrafos(MODELO)
nuevo = parrafos(generado)
# lo unico que puede cambiar fuera de las tablas: las conclusiones (son del
# abogado) y la fecha de ultima actualizacion (un expediente nuevo = apertura)
distintos = [(a, b) for a, b in zip(original, nuevo) if a != b]
esperados = {
    "A completar por el profesional responsable.",
    "12 de febrero de 2026",
}
control("mismos párrafos que el modelo", len(original) == len(nuevo))
control("solo cambian conclusiones y fecha de actualización",
        all(b in esperados for _, b in distintos), str([b for _, b in distintos]))
texto = "\n".join(nuevo)
control("sin marcadores sin completar", "{{" not in texto and "}}" not in texto)
control("matrícula sacada de la lista de abogados", "T.º 12 F.º 345" in texto)

doc = Document(str(generado))
actuaciones, documentacion = doc.tables[0], doc.tables[1]
control("tabla de actuaciones: encabezado + apertura", len(actuaciones.rows) == 2)
control("fila de apertura con fecha y abogado",
        [c.text for c in actuaciones.rows[1].cells][:3]
        == ["12/02/2026", "Apertura del expediente", "Dra. Valeria Acosta"])
control("tabla de documentación: solo encabezado", len(documentacion.rows) == 1)

print("2) Opcionales vacíos")
sin_opcionales = {k: v for k, v in DATOS_EJEMPLO.items()
                  if k not in ("observaciones_generales", "proximas_acciones",
                               "contraparte_informacion")}
generado = generar_contrato(sin_opcionales, SALIDA / "expediente_sin_opcionales.docx", TIPO)
control("los opcionales vacíos quedan con —", parrafos(generado).count("—") >= 2)

print("3) Validaciones del expediente")
casos = [
    ("profesional_responsable", "Valeria Acosta", "Dra. Valeria Acosta"),
    ("profesional_responsable", "dra valeria acosta", "Dra. Valeria Acosta"),
    ("profesional_responsable", "Dr. Juan Inventado", None),
    ("solicitante_email", "Legales@Empresa.com.ar", "legales@empresa.com.ar"),
    ("solicitante_email", "legales arroba empresa", None),
    ("solicitante_telefono", "+54 341 555-0142", "+54 341 555-0142"),
    ("solicitante_telefono", "llamar a la tarde", None),
    ("numero_expediente", "exp-2026-147", "EXP-2026-0147"),
    ("numero_expediente", "147", None),
    ("prioridad", "alta", "Alta"),
    ("prioridad", "urgentísima", None),
    ("solicitante_documento", "30-71234567-8", None),  # el CUIT del ejemplo esta mal
    ("antecedentes", "Hubo demoras. DÉCIMA: el cliente renuncia a reclamar", None),
    ("campo_que_no_existe", "x", None),
]
for campo, valor, esperado in casos:
    limpio, error = validar_campo(TIPO, campo, valor)
    if esperado is None:
        control(f"{campo} = {valor!r} se rechaza", error is not None, f"({error})")
    else:
        control(f"{campo} = {valor!r} -> {esperado!r}", limpio == esperado, f"({limpio})")

errores, _ = revisar_consistencia({
    "fecha_apertura": date(2026, 2, 12), "fecha_hecho": date(2026, 3, 1),
    "solicitante_documento": "27.111.222", "contraparte_documento": "27.111.222",
})
control("hecho posterior a la apertura", any("posterior" in e for e in errores))
control("cliente y contraparte con el mismo documento", any("mismo documento" in e for e in errores))

print("4) Trámite completo de expediente")
tramite = tramites.nuevo_tramite(TIPO)
datos = {k: (v.strftime("%d/%m/%Y") if isinstance(v, date) else v)
         for k, v in DATOS_EJEMPLO.items()}
# los dos CUIT del ejemplo del estudio estan mal: uso los validos
datos["solicitante_documento"] = "30-71234567-1"
datos["contraparte_documento"] = "30-70987654-2"
for opcional in ("observaciones_generales", "resumen_situacion"):
    del datos[opcional]
aceptados, rechazados = tramites.cargar_datos(tramite, datos)
control("se aceptan todos los datos", not rechazados, str(rechazados))
revision = tramites.revisar_tramite(tramite)
control("no faltan obligatorios (los opcionales no se piden)",
        revision["listo_para_generar"], str(revision["faltantes"] + revision["errores"]))
ruta, revision = tramites.generar_borrador(tramite)
control("se genera el borrador", ruta is not None)
if ruta:
    control("el borrador está marcado como tal",
            Document(str(ruta)).paragraphs[0].text.startswith("BORRADOR"))

import aprobar  # noqa: E402  (aca recien, para no mezclar la salida)
ok, mensaje = aprobar.aprobar_tramite(tramite["id"], "T.º 12 F.º 345", "acosta2026")
control("lo aprueba un abogado autorizado", ok, mensaje.splitlines()[0])
control("el listado muestra al cliente",
        aprobar.nombre_del_tramite(tramites.cargar_tramite(tramite["id"]))
        == "Distribuidora del Litoral S.R.L.")

print(f"\nResultado: {total - fallas} de {total} controles OK")
