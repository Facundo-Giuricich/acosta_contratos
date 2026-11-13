# Indexa la guia para empleados en ChromaDB (la parte de RAG).
# Se corre una vez, y cada vez que se cambia la guia:
#   .\env\Scripts\python.exe indexar_guia.py
#
# No usamos LangChain porque Windows (Control inteligente de aplicaciones)
# bloquea una de sus dependencias. Hacemos lo mismo "a mano":
#   cortar en fragmentos -> embeddings con Ollama -> guardar en ChromaDB

from pathlib import Path

import chromadb
import ollama
from chromadb.config import Settings

CARPETA = Path(__file__).resolve().parent
GUIA = CARPETA / "documentos_guia" / "guia_contratos.md"
RUTA_DB = CARPETA / "base_vectorial"
COLECCION = "guia_contratos"
MODELO_EMBEDDINGS = "nomic-embed-text"
LARGO_MAXIMO = 1000


def cortar_por_titulos(texto):
    # Corto la guia en secciones usando los titulos (lineas que empiezan con #).
    # Cada seccion habla de un solo tema, asi un fragmento no mezcla cosas.
    # A cada fragmento le dejo adelante su titulo (ayuda a la busqueda).
    fragmentos = []
    titulo = ""
    lineas = []

    for linea in texto.splitlines():
        if linea.startswith("#"):
            if lineas:
                fragmentos.append((titulo, "\n".join(lineas).strip()))
            titulo = linea.lstrip("#").strip()
            lineas = [linea]
        else:
            lineas.append(linea)
    if lineas:
        fragmentos.append((titulo, "\n".join(lineas).strip()))

    # si una seccion es muy larga la corto por parrafos
    resultado = []
    for titulo, contenido in fragmentos:
        if len(contenido) <= LARGO_MAXIMO:
            resultado.append((titulo, contenido))
            continue
        actual = ""
        for parrafo in contenido.split("\n\n"):
            if actual and len(actual) + len(parrafo) > LARGO_MAXIMO:
                resultado.append((titulo, actual.strip()))
                actual = f"## {titulo} (continuación)\n"
            actual += parrafo + "\n\n"
        resultado.append((titulo, actual.strip()))

    # saco secciones vacias (solo el titulo)
    return [(t, c) for t, c in resultado if len(c.splitlines()) > 1]


if __name__ == "__main__":
    if not GUIA.exists():
        print("Error: no se encontró la guía en", GUIA)
        raise SystemExit(1)

    # 1. Cortamos la guia en fragmentos
    fragmentos = cortar_por_titulos(GUIA.read_text(encoding="utf-8"))
    print("Fragmentos:", len(fragmentos))

    # 2. Embeddings con Ollama. nomic-embed-text pide poner "search_document:"
    #    adelante de los textos que se guardan (y "search_query:" en las preguntas)
    textos = [contenido for titulo, contenido in fragmentos]
    respuesta = ollama.embed(
        model=MODELO_EMBEDDINGS,
        input=["search_document: " + t for t in textos],
    )
    vectores = respuesta["embeddings"]
    print("Dimensión de cada vector:", len(vectores[0]))

    # 3. Guardamos en ChromaDB (sin telemetria: no se manda nada afuera)
    cliente = chromadb.PersistentClient(
        path=str(RUTA_DB), settings=Settings(anonymized_telemetry=False)
    )

    # borro la coleccion anterior: asi si se indexa dos veces no se duplican
    # los fragmentos (era una limitacion del trabajo anterior)
    try:
        cliente.delete_collection(COLECCION)
    except Exception:
        pass  # no existia todavia

    coleccion = cliente.create_collection(
        name=COLECCION,
        metadata={"hnsw:space": "cosine"},  # distancia coseno para comparar vectores
    )
    coleccion.add(
        ids=[f"fragmento_{i}" for i in range(len(textos))],
        documents=textos,
        embeddings=vectores,
        metadatas=[{"seccion": titulo, "fuente": GUIA.name} for titulo, contenido in fragmentos],
    )

    print("Guía indexada correctamente:", coleccion.count(), "fragmentos.")
