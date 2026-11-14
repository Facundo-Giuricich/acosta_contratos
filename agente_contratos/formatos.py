# Funciones para pasar los datos al formato que usa el contrato
# (fechas en palabras, montos con puntos, numeros en letras, etc)
# Esto lo hace el codigo y no la IA, asi el numero y las letras siempre coinciden

import re
from num2words import num2words

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_en_texto(fecha):
    # 2026-04-01 -> "1 de abril de 2026"
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def monto_con_puntos(monto):
    # 4800000 -> "$ 4.800.000"
    return "$ " + f"{monto:,}".replace(",", ".")


def monto_en_letras(monto):
    # 4800000 -> "pesos cuatro millones ochocientos mil"
    letras = num2words(monto, lang="es")
    # num2words pone "veintiuno mil" pero lo correcto es "veintiún mil"
    letras = letras.replace("veintiuno mil", "veintiún mil")
    letras = re.sub(r"\buno mil", "un mil", letras)
    return "pesos " + letras


def numero_con_letras(numero, singular="", plural=""):
    # 6, "mes", "meses" -> "seis (6) meses"
    # 30               -> "treinta (30)"
    letras = num2words(numero, lang="es")

    # delante de una palabra se dice "un mes" y no "uno mes"
    if singular != "":
        if letras.endswith("veintiuno"):
            letras = letras.replace("veintiuno", "veintiún")
        elif letras.endswith("uno"):
            letras = letras[:-1]

    texto = f"{letras} ({numero})"
    if numero == 1:
        texto = texto + " " + singular
    else:
        texto = texto + " " + plural
    return texto.strip()


def tipo_documento(documento):
    # el CUIT tiene 11 numeros y el DNI 7 u 8
    numeros = re.sub(r"\D", "", documento)
    if len(numeros) == 11:
        return "CUIT"
    return "DNI"


def armar_datos_plantilla(datos, tipo="contrato_servicios"):
    # recibe los datos del documento y devuelve todo lo que necesita su plantilla
    # (algunos van tal cual y otros se calculan)
    if tipo == "expediente_juridico":
        return datos_expediente(datos)
    return datos_contrato_servicios(datos)


# lo que va en un campo opcional que no se completo
SIN_DATO = "—"


def datos_expediente(datos):
    # import aca adentro para no crear una importacion circular
    from agente_contratos.campos import ABOGADOS
    from agente_contratos.validacion import buscar_abogado

    def opcional(campo):
        return datos.get(campo) or SIN_DATO

    profesional = datos["profesional_responsable"]
    matricula = ABOGADOS[buscar_abogado(profesional)]["matricula"]
    apertura = datos["fecha_apertura"]

    return {
        # 1. identificacion
        "numero_expediente": datos["numero_expediente"],
        "fecha_apertura_texto": fecha_en_texto(apertura),
        "tipo_expediente": datos["tipo_expediente"],
        "area_responsable": datos["area_responsable"],
        "profesional": profesional,
        "estado": "En trámite",  # un expediente nuevo siempre arranca asi
        "prioridad": datos["prioridad"],
        # 2. caratula: la arma el codigo con el formato de siempre
        #    "Cliente c/ Contraparte s/ materia"
        "caratula": (
            datos["solicitante_nombre"] + " c/ " + datos["contraparte_nombre"]
            + " s/ " + datos["materia"]
        ),
        "objeto": datos["objeto"],
        "descripcion": datos["descripcion"],
        # 3. partes
        "solicitante_nombre": datos["solicitante_nombre"],
        "solicitante_documento": datos["solicitante_documento"],
        "solicitante_domicilio": datos["solicitante_domicilio"],
        "solicitante_email": datos["solicitante_email"],
        "solicitante_telefono": datos["solicitante_telefono"],
        "contraparte_nombre": datos["contraparte_nombre"],
        "contraparte_documento": datos["contraparte_documento"],
        "contraparte_domicilio": datos["contraparte_domicilio"],
        "contraparte_informacion": opcional("contraparte_informacion"),
        # la matricula sale de la lista de abogados, no de lo que se escribio
        "matricula": matricula,
        "representacion_observaciones": opcional("representacion_observaciones"),
        # 4. antecedentes
        "antecedentes": datos["antecedentes"],
        "fecha_hecho_texto": fecha_en_texto(datos["fecha_hecho"]),
        "origen_solicitud": datos["origen_solicitud"],
        "documentacion_inicial": datos["documentacion_inicial"],
        # 5. primera actuacion: la apertura
        "actuacion_fecha": apertura.strftime("%d/%m/%Y"),
        "actuacion_detalle": "Apertura del expediente",
        "actuacion_observaciones": SIN_DATO,
        # 7. observaciones y pendientes
        "observaciones_generales": opcional("observaciones_generales"),
        "informacion_pendiente": opcional("informacion_pendiente"),
        "documentacion_pendiente": opcional("documentacion_pendiente"),
        "proximas_acciones": opcional("proximas_acciones"),
        # 8. estado y conclusiones: las conclusiones son del abogado, no del empleado
        "resumen_situacion": opcional("resumen_situacion"),
        "conclusiones": "A completar por el profesional responsable.",
        "fecha_actualizacion_texto": fecha_en_texto(apertura),
    }


def datos_contrato_servicios(datos):
    fecha = datos["fecha_contrato"]

    valores = {
        # estos van tal cual
        "ciudad": datos["ciudad"],
        "provincia": datos["provincia"],
        "contratante_nombre": datos["contratante_nombre"],
        "contratante_documento": datos["contratante_documento"],
        "contratante_domicilio": datos["contratante_domicilio"],
        "prestador_nombre": datos["prestador_nombre"],
        "prestador_documento": datos["prestador_documento"],
        "prestador_domicilio": datos["prestador_domicilio"],
        "objeto": datos["objeto"],
        "modalidad_pago": datos["modalidad_pago"],
        "medio_pago": datos["medio_pago"],
        "jurisdiccion": datos["jurisdiccion"],

        # estos los calculamos
        "dia": str(fecha.day),
        "mes": MESES[fecha.month - 1],
        "anio": str(fecha.year),
        "contratante_representacion": (
            datos["representante_nombre"] + ", DNI " + datos["representante_dni"]
            + ", en su carácter de " + datos["representante_caracter"]
        ),
        "duracion_texto": numero_con_letras(datos["duracion_meses"], "mes", "meses"),
        "fecha_inicio_texto": fecha_en_texto(datos["fecha_inicio"]),
        "fecha_fin_texto": fecha_en_texto(datos["fecha_fin"]),
        "honorarios_numero": monto_con_puntos(datos["honorarios_total"]),
        "honorarios_letras": monto_en_letras(datos["honorarios_total"]),
        "preaviso_texto": numero_con_letras(datos["dias_preaviso"]),
        "contratante_documento_firma": (
            tipo_documento(datos["contratante_documento"]) + " "
            + datos["contratante_documento"]
        ),
        "prestador_documento_firma": (
            tipo_documento(datos["prestador_documento"]) + " "
            + datos["prestador_documento"]
        ),
    }
    return valores