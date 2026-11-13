# Revision y aprobacion de contratos por un abogado del estudio.
#
# Esto NO lo puede hacer el agente: es un programa aparte que corre el abogado.
# Asi aunque alguien engañe al chat, el chat no tiene forma de aprobar nada.
#
# Uso:
#   .\env\Scripts\python.exe aprobar.py                  -> lista los borradores pendientes
#   .\env\Scripts\python.exe aprobar.py T-2026...        -> revisar y aprobar / rechazar uno

import hashlib
import re
import subprocess
import unicodedata
import sys
from pathlib import Path

from agente_contratos import tramites
from agente_contratos.campos import CONTRATOS
from agente_contratos.generador import generar_contrato

CARPETA = Path(__file__).resolve().parent
CARPETA_APROBADOS = CARPETA / "generados" / "aprobados"

# Abogados que pueden aprobar (matricula -> nombre).
# En un sistema real esto saldria de un login con usuario y contraseña.
ABOGADOS_AUTORIZADOS = {
    "T12F345": "Dra. Valeria Acosta",
    "T15F210": "Dr. Tomás Ledesma",
}


def normalizar_matricula(matricula):
    # "T.º 12 F.º 345" -> "T12F345"
    return re.sub(r"[^A-Za-z0-9]", "", matricula).upper()


def normalizar_nombre(nombre):
    # "Dra. Valeria Acosta" -> "valeria acosta"
    # (sin mayusculas, sin acentos y sin "Dr." / "Dra.")
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(c for c in nombre if not unicodedata.combining(c)).lower()
    nombre = re.sub(r"\bdra?\b\.?", " ", nombre)
    nombre = re.sub(r"[^a-z\s]", " ", nombre)
    return " ".join(nombre.split())


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


def aprobar_tramite(id_tramite, nombre, matricula):
    # devuelve (ok, mensaje)
    tramite = tramites.cargar_tramite(id_tramite)
    if tramite is None:
        return False, "No existe ese trámite."
    if tramite["estado"] != "borrador_generado":
        return False, f"El trámite no tiene un borrador pendiente (estado: {tramite['estado']})."

    matricula = normalizar_matricula(matricula)
    if matricula not in ABOGADOS_AUTORIZADOS:
        tramites.anotar(tramite, "aprobacion rechazada", "matrícula no autorizada")
        tramites.guardar_tramite(tramite)
        return False, "Esa matrícula no está autorizada para aprobar contratos."
    if not nombre.strip():
        return False, "Falta el nombre del abogado."

    # No se guarda el nombre tal como lo escribieron: se usa el que figura
    # para esa matricula. Si el nombre escrito no es ese, se rechaza
    # (alguien podria estar usando la matricula de otro abogado).
    nombre_autorizado = ABOGADOS_AUTORIZADOS[matricula]
    if normalizar_nombre(nombre) != normalizar_nombre(nombre_autorizado):
        tramites.anotar(tramite, "aprobacion rechazada",
                        f"el nombre escrito no corresponde a la matrícula {matricula}")
        tramites.guardar_tramite(tramite)
        return False, "El nombre no corresponde a esa matrícula."
    nombre = nombre_autorizado

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
        generar_contrato(datos, ruta_docx)
    except ValueError as error:
        return False, str(error)

    ruta_pdf = convertir_a_pdf(ruta_docx)

    tramite["estado"] = "aprobado"
    tramite["aprobacion"] = {
        "abogado": nombre.strip(),
        "matricula": matricula,
        "fecha": tramites.ahora(),
        "docx": ruta_docx.name,
        "huella_docx": huella(ruta_docx),
        "pdf": ruta_pdf.name if ruta_pdf else None,
    }
    tramites.anotar(tramite, "contrato aprobado", f"por {nombre.strip()} (mat. {matricula})")
    tramites.guardar_tramite(tramite)

    mensaje = f"Contrato aprobado. Word: {ruta_docx}"
    if ruta_pdf:
        mensaje += f"\nPDF: {ruta_pdf}"
    else:
        mensaje += "\nNo se pudo generar el PDF (hace falta Word o LibreOffice). Quedó el Word."
    return True, mensaje


def observar_tramite(id_tramite, nombre, motivo):
    # el abogado no lo aprueba y lo devuelve con una observacion
    tramite = tramites.cargar_tramite(id_tramite)
    if tramite is None or tramite["estado"] != "borrador_generado":
        return False, "No hay un borrador pendiente para ese trámite."
    if not motivo.strip():
        return False, "Tenés que escribir el motivo."

    tramite["estado"] = "cargando_datos"
    tramite["borrador"] = None
    tramite["observaciones"] = motivo.strip()
    tramites.anotar(tramite, "borrador observado", f"{nombre.strip()}: {motivo.strip()}")
    tramites.guardar_tramite(tramite)
    return True, "El trámite volvió al empleado con la observación."


def main():
    if len(sys.argv) < 2:
        pendientes = listar_pendientes()
        if not pendientes:
            print("No hay borradores pendientes de aprobación.")
        for tramite in pendientes:
            nombre = tramite["datos"].get("contratante_nombre", "?")
            print(f"{tramite['id']}  |  {nombre}  |  borrador del {tramite['borrador']['fecha']}")
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

    if opcion == "a":
        nombre = input("Nombre del abogado: ")
        matricula = input("Matrícula (ej: T.º 12 F.º 345): ")
        ok, mensaje = aprobar_tramite(tramite["id"], nombre, matricula)
        print(mensaje)
    elif opcion == "o":
        nombre = input("Nombre del abogado: ")
        motivo = input("Motivo de la observación: ")
        ok, mensaje = observar_tramite(tramite["id"], nombre, motivo)
        print(mensaje)
    else:
        print("No se hizo ningún cambio.")


if __name__ == "__main__":
    main()
