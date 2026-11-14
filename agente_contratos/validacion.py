# Validacion de los datos del contrato.
# Todo lo que escribe el empleado (y todo lo que el agente le pasa a las
# herramientas) pasa por aca antes de llegar al contrato.
# Cada funcion devuelve (valor_limpio, error). Si error no es None, el dato se rechaza.

import re
import unicodedata
from datetime import date, datetime, timedelta

from agente_contratos.campos import ABOGADOS, CONTRATOS

# caracteres que no tienen nada que hacer en un dato de un contrato
# ({ } son los de las plantillas, < > los de codigo / html)
CARACTERES_PROHIBIDOS = ["{", "}", "<", ">", "`", "\\"]

# palabras tipicas de cuando alguien intenta darle ordenes al sistema
# o meter algo que no es un dato
PALABRAS_SOSPECHOSAS = [
    "ignora", "ignorá", "instruccion", "instrucción", "prompt",
    "olvida", "olvidá", "cláusula", "clausula",
]

# algo como "DÉCIMA:" o "novena :" es el titulo de una clausula nueva
TITULO_CLAUSULA = r"\b(primera|segunda|tercera|cuarta|quinta|sexta|s[eé]ptima|octava|novena|d[eé]cima)\s*:"

LARGO_MAXIMO = {"texto": 150, "texto_largo": 600}


def validar_texto(valor, maximo):
    if not isinstance(valor, str):
        return None, "tiene que ser texto"

    valor = " ".join(valor.split())  # saco espacios y saltos de linea de mas
    if valor == "":
        return None, "está vacío"
    if len(valor) > maximo:
        return None, f"es demasiado largo (máximo {maximo} caracteres)"

    for caracter in CARACTERES_PROHIBIDOS:
        if caracter in valor:
            return None, f"tiene un caracter no permitido: {caracter}"

    minusculas = valor.lower()
    for palabra in PALABRAS_SOSPECHOSAS:
        if palabra in minusculas:
            return None, "parece una instrucción o una cláusula, no un dato"
    if re.search(TITULO_CLAUSULA, minusculas):
        return None, "parece el título de una cláusula nueva, no un dato"

    return valor, None


def cuit_valido(numeros):
    # el ultimo numero del CUIT es un digito verificador que se calcula
    # con los otros 10. Si no coincide, el CUIT esta mal copiado.
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = 0
    for i in range(10):
        suma = suma + int(numeros[i]) * pesos[i]
    verificador = 11 - (suma % 11)
    if verificador == 11:
        verificador = 0
    return verificador == int(numeros[10])


def validar_dni(valor):
    valor = str(valor).strip()
    # solo acepto numeros, puntos, espacios y la palabra DNI adelante
    if not re.fullmatch(r"(?i)(dni)?[\d.\s]+", valor):
        return None, "tiene que tener solo números (ej: 35.678.901)"
    numeros = re.sub(r"\D", "", valor)
    if len(numeros) not in (7, 8):
        return None, "un DNI tiene 7 u 8 números"
    return f"{int(numeros):,}".replace(",", "."), None  # 35678901 -> 35.678.901


def validar_documento(valor):
    valor = str(valor).strip()
    if not re.fullmatch(r"(?i)(dni|cuit|cuil)?[\d.\-\s]+", valor):
        return None, "tiene que tener solo números (DNI o CUIT)"
    numeros = re.sub(r"\D", "", valor)

    if len(numeros) == 11:
        if not cuit_valido(numeros):
            return None, "el CUIT no es válido (no coincide el dígito verificador), revisá que esté bien copiado"
        return f"{numeros[:2]}-{numeros[2:10]}-{numeros[10]}", None  # 30-12345678-9

    if len(numeros) in (7, 8):
        return validar_dni(numeros)

    return None, "tiene que ser un DNI (7 u 8 números) o un CUIT (11 números)"


def validar_fecha(valor):
    if isinstance(valor, date):
        fecha = valor
    else:
        fecha = None
        for formato in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
            try:
                fecha = datetime.strptime(str(valor).strip(), formato).date()
                break
            except ValueError:
                pass
        if fecha is None:
            return None, "no es una fecha válida (usá DD/MM/AAAA)"

    if fecha.year < 2000 or fecha.year > 2100:
        return None, "el año no tiene sentido"
    return fecha, None


def validar_numero(valor, minimo, maximo):
    texto = str(valor).strip()
    if not texto.isdigit():
        return None, "tiene que ser un número entero"
    numero = int(texto)
    if numero < minimo or numero > maximo:
        return None, f"tiene que estar entre {minimo} y {maximo}"
    return numero, None


def validar_monto(valor):
    texto = str(valor).replace("$", "").replace(" ", "").replace(".", "")
    if "," in texto:
        return None, "va sin centavos (ej: 4800000)"
    if not texto.isdigit():
        return None, "tiene que ser un número (ej: 4800000)"
    monto = int(texto)
    if monto <= 0:
        return None, "tiene que ser mayor a cero"
    if monto > 100_000_000_000:
        return None, "es demasiado grande, revisalo"
    return monto, None


def validar_email(valor):
    valor = str(valor).strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", valor) or len(valor) > 100:
        return None, "no es un correo válido (ej: nombre@empresa.com)"
    return valor, None


def validar_telefono(valor):
    valor = " ".join(str(valor).split())
    # solo numeros, espacios, guiones, parentesis y el + del codigo de pais
    if not re.fullmatch(r"\+?[\d\s\-()]+", valor):
        return None, "tiene que tener solo números (ej: +54 341 555-0142)"
    numeros = re.sub(r"\D", "", valor)
    if len(numeros) < 8 or len(numeros) > 15:
        return None, "un teléfono tiene entre 8 y 15 números"
    return valor, None


def validar_expediente(valor):
    # EXP-2026-0147 (se acepta en minusculas o con espacios)
    texto = re.sub(r"\s", "", str(valor)).upper()
    encontrado = re.fullmatch(r"EXP-?(\d{4})-?(\d{1,4})", texto)
    if not encontrado:
        return None, "tiene que tener la forma EXP-AAAA-NNNN (ej: EXP-2026-0147)"
    anio, numero = encontrado.groups()
    return f"EXP-{anio}-{int(numero):04d}", None


def validar_prioridad(valor):
    texto = str(valor).strip().lower()
    for opcion in ["Alta", "Media", "Baja"]:
        if texto == opcion.lower():
            return opcion, None
    return None, "tiene que ser Alta, Media o Baja"


def normalizar_nombre(nombre):
    # "Dra. Valeria Acosta" -> "valeria acosta"
    # (sin mayusculas, sin acentos y sin "Dr." / "Dra.")
    nombre = unicodedata.normalize("NFKD", str(nombre))
    nombre = "".join(c for c in nombre if not unicodedata.combining(c)).lower()
    nombre = re.sub(r"\bdra?\b\.?", " ", nombre)
    nombre = re.sub(r"[^a-z\s]", " ", nombre)
    return " ".join(nombre.split())


def buscar_abogado(nombre):
    # devuelve la matricula del abogado con ese nombre, o None
    for matricula, abogado in ABOGADOS.items():
        if normalizar_nombre(nombre) == normalizar_nombre(abogado["nombre"]):
            return matricula
    return None


def validar_abogado(valor):
    # el responsable tiene que ser un abogado del estudio. Se guarda el
    # nombre oficial (asi la matricula del expediente sale de la lista y
    # no de lo que escribio alguien)
    matricula = buscar_abogado(valor)
    if matricula is None:
        nombres = ", ".join(a["nombre"] for a in ABOGADOS.values())
        return None, f"no es un abogado del estudio (los abogados son: {nombres})"
    return ABOGADOS[matricula]["nombre"], None


def validar_campo(tipo_contrato, campo, valor):
    campos = CONTRATOS[tipo_contrato]["campos"]
    if campo not in campos:
        return None, f"'{campo}' no es un dato de este contrato"

    tipo = campos[campo][0]
    if tipo in ("texto", "texto_largo"):
        return validar_texto(valor, LARGO_MAXIMO[tipo])
    if tipo == "documento":
        return validar_documento(valor)
    if tipo == "dni":
        return validar_dni(valor)
    if tipo == "fecha":
        return validar_fecha(valor)
    if tipo == "meses":
        return validar_numero(valor, 1, 60)
    if tipo == "dias":
        return validar_numero(valor, 1, 180)
    if tipo == "monto":
        return validar_monto(valor)
    if tipo == "email":
        return validar_email(valor)
    if tipo == "telefono":
        return validar_telefono(valor)
    if tipo == "expediente":
        return validar_expediente(valor)
    if tipo == "prioridad":
        return validar_prioridad(valor)
    if tipo == "abogado":
        return validar_abogado(valor)
    return None, "tipo de dato desconocido"


def campos_faltantes(tipo_contrato, datos):
    # devuelve los campos obligatorios que todavia no se cargaron
    # (los opcionales se pueden dejar vacios)
    opcionales = CONTRATOS[tipo_contrato].get("opcionales", [])
    faltan = []
    for campo in CONTRATOS[tipo_contrato]["campos"]:
        if campo not in datos and campo not in opcionales:
            faltan.append(campo)
    return faltan


def revisar_consistencia(datos):
    # controla que los datos tengan sentido entre ellos.
    # errores: no se puede generar el contrato
    # advertencias: se puede generar, pero el abogado lo tiene que mirar
    errores = []
    advertencias = []

    # las fechas
    if "fecha_inicio" in datos and "fecha_fin" in datos:
        inicio = datos["fecha_inicio"]
        fin = datos["fecha_fin"]
        if fin <= inicio:
            errores.append("La fecha de fin tiene que ser posterior a la de inicio.")
        elif "duracion_meses" in datos:
            # ej: del 1/4 al 30/9 son 6 meses (el 1/10 empezaria el mes 7)
            dia_siguiente = fin + timedelta(days=1)
            meses = (dia_siguiente.year - inicio.year) * 12 + dia_siguiente.month - inicio.month
            if dia_siguiente.day != inicio.day or meses != datos["duracion_meses"]:
                errores.append(
                    f"La duración ({datos['duracion_meses']} meses) no coincide "
                    f"con las fechas de inicio y fin."
                )

    if "fecha_contrato" in datos and "fecha_inicio" in datos:
        if datos["fecha_inicio"] < datos["fecha_contrato"]:
            advertencias.append("El contrato empieza antes de la fecha de firma.")

    # las cuotas: si dice "6 cuotas de $ 800.000" tiene que dar el total
    if "modalidad_pago" in datos and "honorarios_total" in datos:
        texto = datos["modalidad_pago"]
        cuotas = re.search(r"(\d+)\)?\s*cuotas", texto)
        monto_cuota = re.search(r"\$\s*([\d.]+)", texto)
        if cuotas and monto_cuota:
            cantidad = int(cuotas.group(1))
            valor_cuota = int(monto_cuota.group(1).replace(".", ""))
            if cantidad * valor_cuota != datos["honorarios_total"]:
                errores.append(
                    f"{cantidad} cuotas de $ {valor_cuota:,} no dan el total de "
                    f"honorarios ($ {datos['honorarios_total']:,}).".replace(",", ".")
                )

    # las dos partes no pueden ser la misma persona
    if "contratante_documento" in datos and "prestador_documento" in datos:
        if datos["contratante_documento"] == datos["prestador_documento"]:
            errores.append("La contratante y el prestador tienen el mismo documento.")

    # expediente: el hecho no puede ser posterior a la apertura
    if "fecha_hecho" in datos and "fecha_apertura" in datos:
        if datos["fecha_hecho"] > datos["fecha_apertura"]:
            errores.append("La fecha del hecho no puede ser posterior a la apertura del expediente.")

    if "solicitante_documento" in datos and "contraparte_documento" in datos:
        if datos["solicitante_documento"] == datos["contraparte_documento"]:
            errores.append("El cliente y la contraparte tienen el mismo documento.")

    if "solicitante_nombre" in datos and "contraparte_nombre" in datos:
        if normalizar_nombre(datos["solicitante_nombre"]) == normalizar_nombre(datos["contraparte_nombre"]):
            errores.append("El cliente y la contraparte tienen el mismo nombre.")

    return errores, advertencias