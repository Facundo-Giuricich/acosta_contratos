# Conector propio entre ADK y Ollama.
#
# POR QUE EXISTE:
# Con las 7 herramientas, el modelo (qwen2.5:7b) genera bien la llamada
# a la herramienta, pero el "parser" de herramientas de Ollama 0.40 la
# descarta y devuelve una respuesta vacia. Lo comprobamos asi:
#   - pidiendole a Ollama el texto crudo (/api/generate con raw=True),
#     el modelo devuelve un <tool_call>{...}</tool_call> perfecto;
#   - el mismo pedido por /api/chat, en streaming o por /v1 sale vacio.
# Entonces armamos nosotros el prompt (con el mismo formato que usa Qwen)
# y leemos las llamadas a herramientas con codigo. Asi no dependemos de
# ese parser y de paso nos sacamos de encima litellm.
#
# SEGURIDAD: el conector solo acepta llamadas a herramientas que existen.
# Si el modelo inventa una herramienta (por ejemplo "aprobar_contrato"),
# no se ejecuta nada: se trata como texto comun.

import asyncio
import json
import os
import re
import urllib.request
from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

OLLAMA = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")

INICIO = "<|im_start|>"
FIN = "<|im_end|>"

# Texto que agrega la plantilla oficial de Qwen cuando hay herramientas
BLOQUE_HERRAMIENTAS = """

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{herramientas}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>"""

PATRON_LLAMADA = re.compile(r"<tool_call>\s*(.*?)\s*(?:</tool_call>|$)", re.DOTALL)


def esquema_a_json(esquema):
    # El esquema de ADK usa tipos en mayuscula ("OBJECT", "STRING").
    # Los paso a minuscula como en JSON Schema y saco lo vacio.
    if isinstance(esquema, dict):
        limpio = {}
        for clave, valor in esquema.items():
            if valor is None:
                continue
            if clave == "type" and isinstance(valor, str):
                valor = valor.lower()
            limpio[clave] = esquema_a_json(valor)
        return limpio
    if isinstance(esquema, list):
        return [esquema_a_json(v) for v in esquema]
    return esquema


def describir_herramientas(config):
    herramientas = []
    nombres = set()
    for tool in config.tools or []:
        for funcion in getattr(tool, "function_declarations", None) or []:
            if funcion.parameters_json_schema:
                parametros = funcion.parameters_json_schema
            elif funcion.parameters:
                parametros = funcion.parameters.model_dump(mode="json", exclude_none=True)
            else:
                parametros = {"type": "object", "properties": {}}
            herramientas.append({
                "type": "function",
                "function": {
                    "name": funcion.name,
                    "description": funcion.description or "",
                    "parameters": esquema_a_json(parametros),
                },
            })
            nombres.add(funcion.name)
    return herramientas, nombres


def texto_del_sistema(config):
    instruccion = config.system_instruction
    if instruccion is None:
        return ""
    if isinstance(instruccion, str):
        return instruccion
    if isinstance(instruccion, types.Content):
        return "".join(p.text or "" for p in instruccion.parts or [])
    return str(instruccion)


def armar_prompt(llm_request):
    # Arma el texto completo en el formato de chat de Qwen
    config = llm_request.config
    herramientas, nombres = describir_herramientas(config)

    sistema = texto_del_sistema(config)
    if herramientas:
        sistema += BLOQUE_HERRAMIENTAS.format(
            herramientas="\n".join(json.dumps(h, ensure_ascii=False) for h in herramientas)
        )
    prompt = f"{INICIO}system\n{sistema}{FIN}\n"

    for contenido in llm_request.contents:
        textos, llamadas, respuestas = [], [], []
        for parte in contenido.parts or []:
            if parte.function_call:
                llamadas.append(json.dumps(
                    {"name": parte.function_call.name, "arguments": parte.function_call.args or {}},
                    ensure_ascii=False,
                ))
            elif parte.function_response:
                respuestas.append(json.dumps(parte.function_response.response, ensure_ascii=False, default=str))
            elif parte.text and not parte.thought:
                textos.append(parte.text)

        if contenido.role == "model":
            cuerpo = "\n".join(textos)
            if llamadas:
                cuerpo += ("\n" if cuerpo else "") + "<tool_call>\n" + "\n".join(llamadas) + "\n</tool_call>"
            prompt += f"{INICIO}assistant\n{cuerpo}{FIN}\n"
        else:
            # Las respuestas de las herramientas van como mensaje "user"
            # dentro de <tool_response>, igual que en la plantilla de Qwen
            for respuesta in respuestas:
                prompt += f"{INICIO}user\n<tool_response>\n{respuesta}\n</tool_response>{FIN}\n"
            if textos:
                prompt += f"{INICIO}user\n" + "\n".join(textos) + f"{FIN}\n"

    prompt += f"{INICIO}assistant\n"
    return prompt, nombres


def es_mensaje_del_empleado(llm_request):
    # True si lo ultimo de la conversacion es un mensaje escrito por el
    # empleado (y no el resultado de una herramienta)
    if not llm_request.contents:
        return False
    ultimo = llm_request.contents[-1]
    if ultimo.role != "user":
        return False
    partes = ultimo.parts or []
    return any(p.text for p in partes) and not any(p.function_response for p in partes)


NO_SE_PUDO_LEER = "Perdón, no pude procesar eso. ¿Me lo repetís?"


def reparar_json(bloque):
    # POR QUE: con mensajes largos (por ejemplo 9 datos juntos), qwen2.5:7b a
    # veces cierra mal la llamada y le falta la ultima "}":
    #   {"name": "iniciar_contrato", "arguments": {"tipo": ..., "datos": {...}}
    # (dos llaves al final en vez de tres). json.loads falla y la llamada se
    # pierde (antes, el empleado veia el <tool_call> crudo en el chat).
    # Nota: esto NO alcanza para explicar el problema original con el parser
    # de Ollama. En esa prueba, con las 7 herramientas, el modelo devolvio el
    # JSON bien cerrado (pedido "crudo" a /api/generate) y aun asi /api/chat
    # lo descartaba. Son dos problemas distintos y el conector cubre los dos.
    # SOLUCION: cuento las { y [ que se abrieron y no se cerraron, y agrego al
    # final las } y ] que falten (en el orden correcto). Lo que esta entre
    # comillas no se cuenta, porque es texto de un dato y no estructura.
    abiertos = []
    en_texto = False
    escapado = False
    for caracter in bloque:
        if en_texto:
            if escapado:
                escapado = False
            elif caracter == "\\":
                escapado = True
            elif caracter == '"':
                en_texto = False
        elif caracter == '"':
            en_texto = True
        elif caracter in "{[":
            abiertos.append(caracter)
        elif caracter in "}]" and abiertos:
            abiertos.pop()
    cierres = "".join("}" if a == "{" else "]" for a in reversed(abiertos))
    return bloque + cierres


def leer_respuesta(texto, nombres_validos):
    # Separa el texto comun de las llamadas a herramientas
    partes = []
    llamadas = []
    bloques = PATRON_LLAMADA.findall(texto)
    for bloque in bloques:
        # normalmente cada bloque es un JSON; a veces el modelo pone
        # varias llamadas en el mismo bloque, una por linea
        try:
            candidatas = [json.loads(reparar_json(bloque))]
        except json.JSONDecodeError:
            candidatas = []
            for linea in bloque.splitlines():
                try:
                    candidatas.append(json.loads(reparar_json(linea)))
                except json.JSONDecodeError:
                    pass

        for llamada in candidatas:
            # solo herramientas que existen: si inventa una, no se ejecuta
            if not isinstance(llamada, dict) or llamada.get("name") not in nombres_validos:
                continue
            argumentos = llamada.get("arguments") or {}
            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos)
                except json.JSONDecodeError:
                    argumentos = {}
            if not isinstance(argumentos, dict):
                argumentos = {}
            llamadas.append(types.Part.from_function_call(name=llamada["name"], args=argumentos))

    if llamadas:
        texto_libre = PATRON_LLAMADA.sub("", texto).strip()
    elif bloques:
        # Hubo <tool_call> pero ninguno se pudo leer (o pedia una herramienta
        # que no existe): no le mostramos al empleado el texto crudo
        texto_libre = NO_SE_PUDO_LEER
    else:
        texto_libre = texto.strip()

    if texto_libre:
        partes.append(types.Part(text=texto_libre))
    partes.extend(llamadas)
    return partes


def pedir_a_ollama(cuerpo):
    pedido = urllib.request.Request(
        OLLAMA.rstrip("/") + "/api/generate",
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(pedido, timeout=600) as respuesta:
        return json.loads(respuesta.read())


class OllamaLocal(BaseLlm):
    """Modelo local de Ollama, con las llamadas a herramientas leidas por codigo."""

    model: str = "qwen2.5:7b"
    num_ctx: int = 8192
    # Ante cada mensaje del empleado, el modelo TIENE que usar una herramienta
    # antes de contestar (equivale a tool_choice="required" en otras APIs).
    # Asi no puede decir "ya cargue los datos" sin haberlos guardado.
    forzar_herramienta: bool = True

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        prompt, nombres = armar_prompt(llm_request)

        # Le dejamos empezada la respuesta con "<tool_call>": el modelo solo
        # puede seguir escribiendo una llamada a herramienta
        forzada = self.forzar_herramienta and nombres and es_mensaje_del_empleado(llm_request)
        if forzada:
            prompt += "<tool_call>\n"

        opciones = {"num_ctx": self.num_ctx}
        if llm_request.config.temperature is not None:
            opciones["temperature"] = llm_request.config.temperature

        cuerpo = {
            "model": self.model,
            "prompt": prompt,
            "raw": True,  # sin plantilla ni parser de Ollama: lo hacemos nosotros
            "stream": False,
            "options": opciones,
        }
        try:
            respuesta = await asyncio.to_thread(pedir_a_ollama, cuerpo)
        except Exception as error:
            yield LlmResponse(
                error_code="OLLAMA_ERROR",
                error_message=f"No se pudo conectar con Ollama: {error}",
            )
            return

        texto = respuesta.get("response", "")
        if forzada:
            texto = "<tool_call>\n" + texto
        partes = leer_respuesta(texto, nombres)
        if not partes:
            partes = [types.Part(text="Perdón, no entendí bien. ¿Me lo podés repetir?")]

        yield LlmResponse(
            content=types.Content(role="model", parts=partes),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=respuesta.get("prompt_eval_count"),
                candidates_token_count=respuesta.get("eval_count"),
            ),
        )
