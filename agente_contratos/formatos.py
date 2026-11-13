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


def armar_datos_plantilla(datos):
    # recibe los datos del contrato y devuelve todo lo que necesita la plantilla
    # (algunos van tal cual y otros se calculan)
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