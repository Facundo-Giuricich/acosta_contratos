# Control de origen de los datos ("no inventar informacion").
#
# Antes de guardar un dato, se controla que haya salido de lo que ESCRIBIO
# el empleado en la conversacion. Si el modelo "completa" un dato que el
# empleado nunca dio (por ejemplo pone 30 dias de preaviso porque lo vio
# en un ejemplo), el dato se rechaza.
#
# Se compara todo "normalizado": sin mayusculas, sin acentos, sin espacios
# ni signos. Asi "$ 4.800.000" y "4800000" se consideran el mismo dato.

import re
import unicodedata

from num2words import num2words

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def palabras(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"(?<=\d)[.,](?=\d)", "", texto)  # 4.800.000 -> 4800000
    return re.findall(r"[a-z0-9]+", texto)


def numero_aparece(numero, texto):
    # el numero tiene que estar escrito como numero o en letras
    numeros_del_texto = set(re.findall(r"\d+", re.sub(r"(?<=\d)[.,](?=\d)", "", texto)))
    if str(numero) in numeros_del_texto:
        return True
    try:
        en_letras = normalizar(num2words(int(numero), lang="es"))
    except (ValueError, OverflowError):
        return False
    return en_letras in normalizar(texto)


def fecha_aparece(valor, texto):
    partes = re.findall(r"\d+", str(valor))
    if len(partes) != 3:
        return False
    dia, mes, anio = (int(p) for p in partes)
    plano = normalizar(texto)
    if anio < 100:
        anio += 2000
    # 01/04/2026, 1/4/2026, 1-4-26, "1 de abril de 2026"...
    for d in {f"{dia}", f"{dia:02d}"}:
        for m in {f"{mes}", f"{mes:02d}"}:
            for a in {f"{anio}", f"{anio % 100:02d}"}:
                if d + m + a in plano:
                    return True
        if 1 <= mes <= 12 and f"{d}de{MESES[mes - 1]}" in plano:
            return True
    return False


def texto_aparece(valor, texto, largo):
    if normalizar(valor) in normalizar(texto):
        return True
    if not largo:
        return False
    # Para textos largos (objeto, forma de pago) acepto que el modelo
    # lo haya resumido un poco, pero todas las palabras importantes
    # tienen que estar en lo que escribio el empleado.
    importantes = [p for p in palabras(valor) if len(p) >= 4 or p.isdigit()]
    disponibles = set(palabras(texto))
    return len(importantes) >= 2 and all(p in disponibles for p in importantes)


def dato_aparece(tipo_dato, valor, texto_empleado):
    if valor is None or str(valor).strip() == "":
        return False
    if tipo_dato == "fecha":
        return fecha_aparece(valor, texto_empleado)
    if tipo_dato in ("meses", "dias", "monto"):
        solo_numeros = re.sub(r"\D", "", str(valor))
        return bool(solo_numeros) and numero_aparece(int(solo_numeros), texto_empleado)
    if tipo_dato in ("documento", "dni"):
        return normalizar(valor) in normalizar(texto_empleado)
    return texto_aparece(valor, texto_empleado, largo=(tipo_dato == "texto_largo"))


def textos_del_empleado(tool_context):
    # junta todo lo que escribio el empleado en esta conversacion
    textos = []
    sesion = getattr(tool_context, "session", None)
    for evento in getattr(sesion, "events", None) or []:
        if evento.author != "user" or not evento.content:
            continue
        for parte in evento.content.parts or []:
            if parte.text:
                textos.append(parte.text)
    return "\n".join(textos)
