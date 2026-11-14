# Prueba de leer_respuesta (modelo_ollama.py): como se leen las llamadas a
# herramientas que escribe el modelo.
#
# Caso real visto en adk web: con un mensaje largo de 9 datos, qwen2.5:7b
# cerro mal el JSON (le falto la ultima "}"). Antes, eso se mostraba como
# texto crudo en el chat; ahora se repara y se lee la llamada.
#
# Uso: .\env\Scripts\python.exe -m pruebas.prueba_leer_respuesta

import json

from agente_contratos.modelo_ollama import NO_SE_PUDO_LEER, leer_respuesta

HERRAMIENTAS = {
    "listar_contratos", "iniciar_contrato", "cargar_datos", "ver_resumen",
    "generar_borrador", "consultar_guia", "mensaje_sin_datos",
}

DATOS = {
    "contratante_nombre": "Distribuidora del Litoral S.R.L.",
    "contratante_documento": "30-71234567-1",
    "contratante_domicilio": "Av. San Martín 1250, Rosario, Santa Fe",
    "representante_nombre": "Marcos Ezequiel Ibarra",
    "representante_dni": "28.456.789",
    "representante_caracter": "socio gerente",
    "prestador_nombre": "Lucía Belén Fernández",
    "prestador_documento": "35.678.901",
    "prestador_domicilio": "Calle Mitre 845, 3.º B, Rosario, Santa Fe",
}

resultados = []


def chequear(nombre, ok, detalle=""):
    resultados.append(ok)
    print(f"  {'OK   ' if ok else 'FALLO'} {nombre}  {detalle}")


def llamadas_de(partes):
    return [p.function_call for p in partes if p.function_call]


def textos_de(partes):
    return [p.text for p in partes if p.text]


completo = json.dumps(
    {"name": "iniciar_contrato", "arguments": {"tipo": "contrato_servicios", "datos": DATOS}},
    ensure_ascii=False,
)
assert completo.endswith("}}}")
sin_ultima_llave = completo[:-1]  # termina en "}}" en vez de "}}}"

print("1. JSON sin la última } (el caso de adk web)")
partes = leer_respuesta(f"<tool_call>\n{sin_ultima_llave}\n</tool_call>", HERRAMIENTAS)
llamadas = llamadas_de(partes)
chequear("se lee una llamada", len(llamadas) == 1, [l.name for l in llamadas])
if llamadas:
    llamada = llamadas[0]
    chequear("es iniciar_contrato", llamada.name == "iniciar_contrato")
    chequear("tipo correcto", llamada.args.get("tipo") == "contrato_servicios")
    chequear("trae los 9 datos", llamada.args.get("datos") == DATOS,
             f"{len(llamada.args.get('datos') or {})} datos")
chequear("no se muestra el <tool_call> crudo", not any("<tool_call>" in t for t in textos_de(partes)))

print("2. Mismo caso, sin el </tool_call> de cierre")
partes = leer_respuesta(f"<tool_call>\n{sin_ultima_llave}", HERRAMIENTAS)
llamadas = llamadas_de(partes)
chequear("se lee la llamada con los 9 datos",
         len(llamadas) == 1 and llamadas[0].args.get("datos") == DATOS)

print("3. JSON bien cerrado (no se rompe lo que ya andaba)")
partes = leer_respuesta(f"<tool_call>\n{completo}\n</tool_call>", HERRAMIENTAS)
llamadas = llamadas_de(partes)
chequear("se lee igual", len(llamadas) == 1 and llamadas[0].args.get("datos") == DATOS)

print("4. Llaves dentro de un dato no confunden la reparación")
con_llaves = json.dumps(
    {"name": "cargar_datos", "arguments": {"datos": {"objeto": "texto con { y [ adentro"}}},
    ensure_ascii=False,
)[:-1]
partes = leer_respuesta(f"<tool_call>{con_llaves}</tool_call>", HERRAMIENTAS)
llamadas = llamadas_de(partes)
chequear("se lee la llamada y el texto queda igual",
         len(llamadas) == 1 and llamadas[0].args["datos"]["objeto"] == "texto con { y [ adentro")

print("5. Bloque que no se puede leer")
partes = leer_respuesta('<tool_call>\n{"name": "iniciar_contrato", "arguments": {tipo: ???\n</tool_call>',
                        HERRAMIENTAS)
chequear("no hay llamada", not llamadas_de(partes))
chequear("se muestra el mensaje de error, no el texto crudo",
         textos_de(partes) == [NO_SE_PUDO_LEER], textos_de(partes))

print("6. Texto común sin llamadas")
partes = leer_respuesta("Hola, ¿qué contrato necesitás?", HERRAMIENTAS)
chequear("se deja tal cual", textos_de(partes) == ["Hola, ¿qué contrato necesitás?"])

print()
print(f"Resultado: {sum(resultados)} de {len(resultados)} controles OK")
