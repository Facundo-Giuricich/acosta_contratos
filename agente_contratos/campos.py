# Lista de contratos que el sistema sabe generar y los datos que pide cada uno.
# El agente solo puede usar lo que esta aca, no puede inventar contratos ni campos.

# tipos de dato:
#   texto       -> texto corto (nombres, domicilios, ciudades)
#   texto_largo -> texto mas largo (objeto del contrato, forma de pago)
#   documento   -> DNI o CUIT
#   dni         -> solo DNI
#   fecha       -> una fecha
#   meses       -> cantidad de meses (1 a 60)
#   dias        -> cantidad de dias (1 a 180)
#   monto       -> plata en pesos, sin centavos

CONTRATOS = {
    "contrato_servicios": {
        "nombre": "Contrato de Prestación de Servicios Profesionales",
        "plantilla": "contrato_servicios.docx",
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
}