# Revision y aprobacion de contratos por un abogado del estudio.
#
# Esto NO lo puede hacer el agente: es un programa aparte que corre el abogado.
# Asi aunque alguien engañe al chat, el chat no tiene forma de aprobar nada.
#
# Uso:
#   .\env\Scripts\python.exe aprobar.py                  -> lista los borradores pendientes
#   .\env\Scripts\python.exe aprobar.py T-2026...        -> revisar y aprobar / rechazar uno

import getpass
import hashlib
import subprocess
import sys
from pathlib import Path

from agente_contratos import tramites
from agente_contratos.campos import ABOGADOS, CONTRATOS, normalizar_matricula, verificar_abogado
from agente_contratos.generador import generar_contrato

CARPETA = Path(__file__).resolve().parent
CARPETA_APROBADOS = CARPETA / "generados" / "aprobados"

# Pueden aprobar u observar los abogados de campos.py, con su matricula y su
# clave (la clave se guarda como hash, ver verificar_abogado en campos.py).
MENSAJE_CREDENCIALES = "Matrícula o clave incorrecta."


def autenticar(tramite, matricula, clave, accion):
    # devuelve la matricula normalizada si las credenciales son correctas.
    # Si no, anota el intento rechazado en el historial del tramite
    # (sin la clave) y devuelve None
    autorizado = verificar_abogado(matricula, clave)
    if autorizado is None:
        escrita = normalizar_matricula(matricula)[:20] or "(vacía)"
        tramites.anotar(tramite, f"{accion} rechazada",
                        f"matrícula o clave incorrecta (matrícula escrita: {escrita})")
        tramites.guardar_tramite(tramite)
    return autorizado


def nombre_del_tramite(tramite):
    # el dato que identifica el tramite en los listados (cliente o contratante)
    campo = CONTRATOS[tramite["tipo"]].get("campo_principal", "")
    return tramite["datos"].get(campo, "?")


def huella(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def pdf_con_word(ruta_docx, ruta_pdf):
    # Abre el Word en SOLO LECTURA y lo exporta a PDF.
    # (docx2pdf lo abre para editar y falla si Office no tiene la licencia
    # activa; en solo lectura Word igual deja exportar)
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        documento = word.Documents.Open(str(ruta_docx), False, True)  # ReadOnly=True
        documento.ExportAsFixedFormat(str(ruta_pdf), 17)  # 17 = PDF
        documento.Close(False)
    finally:
        word.Quit()
        pythoncom.CoUninitialize()


def convertir_a_pdf(ruta_docx):
    # 1ro intento con Word, si no con LibreOffice.
    # Si no hay ninguno, queda solo el .docx
    ruta_pdf = ruta_docx.with_suffix(".pdf")
    try:
        pdf_con_word(ruta_docx, ruta_pdf)
        if ruta_pdf.exists():
            return ruta_pdf
    except Exception as error:
        print("No se pudo exportar con Word:", error)

    for programa in ["soffice", r"C:\Program Files\LibreOffice\program\soffice.exe"]:
        try:
            subprocess.run(
                [programa, "--headless", "--convert-to", "pdf", "--outdir",
                 str(ruta_docx.parent), str(ruta_docx)],
                check=True, capture_output=True, timeout=120,
            )
            if ruta_pdf.exists():
                return ruta_pdf
        except Exception:
            pass
    return None


def listar_pendientes():
    pendientes = []
    for archivo in sorted(tramites.CARPETA_TRAMITES.glob("T-*.json")):
        tramite = tramites.cargar_tramite(archivo.stem)
        if tramite and tramite["estado"] == "borrador_generado":
            pendientes.append(tramite)
    return pendientes


def mostrar_tramite(tramite):
    campos = CONTRATOS[tramite["tipo"]]["campos"]
    print("=" * 70)
    print("Trámite:", tramite["id"], "|", CONTRATOS[tramite["tipo"]]["nombre"])
    print("Creado por:", tramite["creado_por"], "el", tramite["creado"])
    print("Borrador:", tramite["borrador"]["archivo"])
    print("-" * 70)
    for campo, valor in tramite["datos"].items():
        print(f"  {campos[campo][1]}: {valor}")
    revision = tramites.revisar_tramite(tramite)
    for advertencia in revision["advertencias"]:
        print("  ADVERTENCIA:", advertencia)
    print("=" * 70)


def aprobar_tramite(id_tramite, matricula, clave):
    # devuelve (ok, mensaje)
    tramite = tramites.cargar_tramite(id_tramite)
    if tramite is None:
        return False, "No existe ese trámite."

    # primero las credenciales: sin matricula y clave correctas no se hace nada
    matricula = autenticar(tramite, matricula, clave, "aprobacion")
    if matricula is None:
        return False, MENSAJE_CREDENCIALES
    # se guarda siempre el nombre oficial de esa matricula
    nombre = ABOGADOS[matricula]["nombre"]

    if tramite["estado"] != "borrador_generado":
        return False, f"El trámite no tiene un borrador pendiente (estado: {tramite['estado']})."

    # controlo de nuevo todo antes de generar la version final
    revision = tramites.revisar_tramite(tramite)
    if not revision["listo_para_generar"]:
        return False, f"Los datos tienen problemas: {revision['faltantes'] + revision['errores']}"

    # la version final se genera de nuevo desde los datos validados y la
    # plantilla aprobada (no se usa el archivo del borrador, que alguien
    # podria haber editado a mano)
    datos, _ = tramites.datos_validados(tramite)
    ruta_docx = CARPETA_APROBADOS / f"{tramite['id']}_aprobado.docx"
    try:
        generar_contrato(datos, ruta_docx, tramite["tipo"])
    except ValueError as error:
        return False, str(error)

    ruta_pdf = convertir_a_pdf(ruta_docx)

    tramite["estado"] = "aprobado"
    tramite["aprobacion"] = {
        "abogado": nombre,
        "matricula": matricula,
        "fecha": tramites.ahora(),
        "docx": ruta_docx.name,
        "huella_docx": huella(ruta_docx),
        "pdf": ruta_pdf.name if ruta_pdf else None,
    }
    tramites.anotar(tramite, "documento aprobado", f"por {nombre} (mat. {matricula})")
    tramites.guardar_tramite(tramite)

    # solo el nombre del archivo, no la ruta de la computadora
    mensaje = f"Documento aprobado. Word: {ruta_docx.name}"
    if ruta_pdf:
        mensaje += f"\nPDF: {ruta_pdf.name}"
    else:
        mensaje += "\nNo se pudo generar el PDF (hace falta Word o LibreOffice). Quedó el Word."
    return True, mensaje


def observar_tramite(id_tramite, matricula, clave, motivo):
    # el abogado no lo aprueba y lo devuelve con una observacion
    tramite = tramites.cargar_tramite(id_tramite)
    if tramite is None:
        return False, "No hay un borrador pendiente para ese trámite."

    matricula = autenticar(tramite, matricula, clave, "observacion")
    if matricula is None:
        return False, MENSAJE_CREDENCIALES
    nombre = ABOGADOS[matricula]["nombre"]

    if tramite["estado"] != "borrador_generado":
        return False, "No hay un borrador pendiente para ese trámite."
    if not motivo.strip():
        return False, "Tenés que escribir el motivo."

    tramite["estado"] = "cargando_datos"
    tramite["borrador"] = None
    tramite["observaciones"] = motivo.strip()
    tramites.anotar(tramite, "borrador observado", f"{nombre}: {motivo.strip()}")
    tramites.guardar_tramite(tramite)
    return True, "El trámite volvió al empleado con la observación."


def main():
    if len(sys.argv) < 2:
        pendientes = listar_pendientes()
        if not pendientes:
            print("No hay borradores pendientes de aprobación.")
        for tramite in pendientes:
            tipo = CONTRATOS[tramite["tipo"]]["nombre"]
            print(f"{tramite['id']}  |  {tipo}  |  {nombre_del_tramite(tramite)}  |  "
                  f"borrador del {tramite['borrador']['fecha']}")
        print("\nPara revisar uno: aprobar.py NUMERO_DE_TRAMITE")
        return

    tramite = tramites.cargar_tramite(sys.argv[1])
    if tramite is None:
        print("No existe ese trámite.")
        return
    if tramite["estado"] != "borrador_generado":
        print("Ese trámite no tiene un borrador pendiente. Estado:", tramite["estado"])
        return

    mostrar_tramite(tramite)
    print("Revisá también el Word del borrador antes de decidir.")
    opcion = input("¿Qué querés hacer? (a = aprobar, o = observar, cualquier otra = salir): ").strip().lower()

    if opcion in ("a", "o"):
        matricula = input("Matrícula (ej: T.º 12 F.º 345): ")
        clave = getpass.getpass("Clave (no se ve al escribirla): ")
        if opcion == "a":
            ok, mensaje = aprobar_tramite(tramite["id"], matricula, clave)
        else:
            motivo = input("Motivo de la observación: ")
            ok, mensaje = observar_tramite(tramite["id"], matricula, clave, motivo)
        print(mensaje)
    else:
        print("No se hizo ningún cambio.")


if __name__ == "__main__":
    main()
