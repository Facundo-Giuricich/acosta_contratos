# Lista de documentos que el sistema sabe generar y los datos que pide cada uno.
# El agente solo puede usar lo que esta aca, no puede inventar documentos ni campos.
# (el diccionario se llama CONTRATOS por historia, pero tambien tiene el expediente)

# tipos de dato:
#   texto       -> texto corto (nombres, domicilios, ciudades)
#   texto_largo -> texto mas largo (objeto del contrato, forma de pago)
#   documento   -> DNI o CUIT
#   dni         -> solo DNI
#   fecha       -> una fecha
#   meses       -> cantidad de meses (1 a 60)
#   dias        -> cantidad de dias (1 a 180)
#   monto       -> plata en pesos, sin centavos
#   email       -> correo electronico
#   telefono    -> numero de telefono
#   expediente  -> numero de expediente (EXP-2026-0147)
#   prioridad   -> Alta, Media o Baja
#   abogado     -> un abogado del estudio (tiene que estar en ABOGADOS)
#
# "opcionales": campos que se pueden dejar sin completar. Si no se dan,
# la plantilla pone "—". El resto son obligatorios.
# "campo_principal": el dato que identifica el tramite en los listados.

# Abogados del estudio (matricula normalizada -> nombre y matricula como se escribe).
# Los usa aprobar.py (quien puede aprobar) y el expediente (profesional responsable).
# En un sistema real esto saldria de una base de datos con login.
ABOGADOS = {
    "T12F345": {"nombre": "Dra. Valeria Acosta", "matricula": "T.º 12 F.º 345"},
    "T15F210": {"nombre": "Dr. Tomás Ledesma", "matricula": "T.º 15 F.º 210"},
}

CONTRATOS = {
    "contrato_servicios": {
        "nombre": "Contrato de Prestación de Servicios Profesionales",
        "plantilla": "contrato_servicios.docx",
        "campo_principal": "contratante_nombre",
        "opcionales": [],
        "campos": {
            "ciudad": ("texto", "Ciudad donde se firma"),
            "provincia": ("texto", "Provincia donde se firma"),
            "fecha_contrato": ("fecha", "Fecha de firma del contrato"),
            "contratante_nombre": ("texto", "Nombre o razón social de la contratante"),
            "contratante_documento": ("documento", "DNI o CUIT de la contratante"),
            "contratante_domicilio": ("texto", "Domicilio de la contratante"),
            "representante_nombre": ("texto", "Nombre de quien firma por la contratante"),
            "representante_dni": ("dni", "DNI de quien firma por la contratante"),
            "representante_caracter": ("texto", "Cargo de quien firma (ej: socio gerente)"),
            "prestador_nombre": ("texto", "Nombre del prestador"),
            "prestador_documento": ("documento", "DNI o CUIT del prestador"),
            "prestador_domicilio": ("texto", "Domicilio del prestador"),
            "objeto": ("texto_largo", "Qué servicios va a hacer el prestador"),
            "duracion_meses": ("meses", "Duración del contrato en meses"),
            "fecha_inicio": ("fecha", "Fecha de inicio"),
            "fecha_fin": ("fecha", "Fecha de finalización"),
            "honorarios_total": ("monto", "Honorarios totales en pesos"),
            "modalidad_pago": ("texto_largo", "Cómo se paga (ej: 6 cuotas de $ 800.000)"),
            "medio_pago": ("texto_largo", "Medio de pago (ej: transferencia bancaria)"),
            "dias_preaviso": ("dias", "Días de aviso previo para rescindir"),
            "jurisdiccion": ("texto", "Tribunales competentes (ej: la ciudad de Rosario, Provincia de Santa Fe)"),
        },
    },
    "expediente_juridico": {
        "nombre": "Expediente Jurídico (apertura)",
        "plantilla": "expediente_juridico.docx",
        "campo_principal": "solicitante_nombre",
        "opcionales": [
            "contraparte_informacion", "representacion_observaciones",
            "observaciones_generales", "informacion_pendiente",
            "documentacion_pendiente", "proximas_acciones", "resumen_situacion",
        ],
        "campos": {
            "numero_expediente": ("expediente", "Número de expediente (ej: EXP-2026-0147)"),
            "fecha_apertura": ("fecha", "Fecha de apertura del expediente"),
            "tipo_expediente": ("texto", "Tipo de expediente (ej: Reclamo por incumplimiento contractual)"),
            "area_responsable": ("texto", "Área del estudio (ej: Derecho Comercial)"),
            "profesional_responsable": ("abogado", "Abogado responsable del estudio"),
            "prioridad": ("prioridad", "Prioridad: Alta, Media o Baja"),
            "materia": ("texto", "De qué se trata, para la carátula (ej: incumplimiento de contrato de transporte)"),
            "objeto": ("texto_largo", "Objeto del expediente (qué se reclama o se pide)"),
            "descripcion": ("texto_largo", "Descripción general del caso"),
            "solicitante_nombre": ("texto", "Nombre o razón social del cliente que consulta"),
            "solicitante_documento": ("documento", "DNI o CUIT del cliente"),
            "solicitante_domicilio": ("texto", "Domicilio del cliente"),
            "solicitante_email": ("email", "Correo electrónico del cliente"),
            "solicitante_telefono": ("telefono", "Teléfono del cliente"),
            "contraparte_nombre": ("texto", "Nombre o razón social de la contraparte"),
            "contraparte_documento": ("documento", "DNI o CUIT de la contraparte"),
            "contraparte_domicilio": ("texto", "Domicilio de la contraparte"),
            "contraparte_informacion": ("texto", "Información adicional de la contraparte (opcional)"),
            "representacion_observaciones": ("texto", "Observaciones sobre la representación legal (opcional)"),
            "antecedentes": ("texto_largo", "Antecedentes: qué pasó"),
            "fecha_hecho": ("fecha", "Fecha del hecho principal"),
            "origen_solicitud": ("texto_largo", "Cómo llegó la consulta (quién y cuándo)"),
            "documentacion_inicial": ("texto_largo", "Documentación que trajo el cliente"),
            "observaciones_generales": ("texto_largo", "Observaciones generales (opcional)"),
            "informacion_pendiente": ("texto_largo", "Información que falta conseguir (opcional)"),
            "documentacion_pendiente": ("texto_largo", "Documentación que falta (opcional)"),
            "proximas_acciones": ("texto_largo", "Próximas acciones previstas (opcional)"),
            "resumen_situacion": ("texto_largo", "Resumen de la situación (opcional)"),
        },
    },
}
