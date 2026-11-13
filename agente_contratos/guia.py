# Busqueda en la guia para empleados (la parte de RAG).
# Convierte la pregunta en un vector y busca los fragmentos mas parecidos.

from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent
RUTA_DB = CARPETA / "base_vectorial"
COLECCION = "guia_contratos"
MODELO_EMBEDDINGS = "nomic-embed-text"  # el mismo que en indexar_guia.py


def buscar_en_guia(pregunta, k=3):
    if not isinstance(pregunta, str) or not pregunta.strip():
        return {"estado": "error", "mensaje": "La pregunta está vacía.", "fragmentos": []}
    if len(pregunta) > 300:
        return {"estado": "error", "mensaje": "La pregunta es demasiado larga.", "fragmentos": []}
    if not RUTA_DB.exists():
        return {"estado": "error", "mensaje": "No está indexada la guía. Ejecutá indexar_guia.py.", "fragmentos": []}

    try:
        # importo aca adentro y no arriba: si estas librerias fallan,
        # solo deja de andar la guia y el resto del sistema sigue funcionando
        import chromadb
        import ollama
        from chromadb.config import Settings

        cliente = chromadb.PersistentClient(
            path=str(RUTA_DB), settings=Settings(anonymized_telemetry=False)
        )
        coleccion = cliente.get_collection(COLECCION)
        if coleccion.count() == 0:
            return {"estado": "sin_resultados", "mensaje": "La guía no tiene contenido indexado.", "fragmentos": []}

        # la pregunta se pasa a vector con el MISMO modelo que los fragmentos,
        # si no los vectores no se pueden comparar
        vector = ollama.embed(
            model=MODELO_EMBEDDINGS, input=["search_query: " + pregunta.strip()]
        )["embeddings"][0]

        resultado = coleccion.query(query_embeddings=[vector], n_results=k)

    except Exception as error:
        return {"estado": "error", "mensaje": f"Error al buscar en la guía: {error}", "fragmentos": []}

    fragmentos = []
    for texto, datos, distancia in zip(
        resultado["documents"][0], resultado["metadatas"][0], resultado["distances"][0]
    ):
        fragmentos.append({
            "seccion": datos.get("seccion", ""),
            "texto": texto,
            # distancia coseno: cuanto mas chica, mas parecido a la pregunta
            "distancia": round(distancia, 3),
        })

    return {"estado": "ok", "fragmentos": fragmentos}
