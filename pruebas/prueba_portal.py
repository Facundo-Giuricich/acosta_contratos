# Pruebas del portal web (la parte que no necesita el modelo):
# ingreso del abogado, aprobar / observar desde la web, descargas y que el
# empleado solo vea su propio tramite.
#
# Uso: .\env\Scripts\python.exe -m pruebas.prueba_portal

import asyncio
import base64

from fastapi.testclient import TestClient

import portal
from agente_contratos import tramites
from portal import app

DATOS_COMPLETOS = {
    "ciudad": "Rosario", "provincia": "Santa Fe", "fecha_contrato": "15/03/2026",
    "contratante_nombre": "Distribuidora del Litoral S.R.L.",
    "contratante_documento": "30-71234567-1",
    "contratante_domicilio": "Av. San Martín 1250, Rosario, Santa Fe",
    "representante_nombre": "Marcos Ezequiel Ibarra", "representante_dni": "28456789",
    "representante_caracter": "socio gerente",
    "prestador_nombre": "Lucía Belén Fernández", "prestador_documento": "35678901",
    "prestador_domicilio": "Calle Mitre 845, 3.º B, Rosario, Santa Fe",
    "objeto": "Desarrollo de una API REST para gestión de pedidos y stock.",
    "duracion_meses": "6", "fecha_inicio": "01/04/2026", "fecha_fin": "30/09/2026",
    "honorarios_total": "4800000",
    "modalidad_pago": "seis (6) cuotas mensuales de $ 800.000 cada una",
    "medio_pago": "transferencia bancaria", "dias_preaviso": "30",
    "jurisdiccion": "la ciudad de Rosario, Provincia de Santa Fe",
}

cliente = TestClient(app)
fallas = 0
total = 0


def control(nombre, ok, detalle=""):
    global fallas, total
    total += 1
    if not ok:
        fallas += 1
    print(f"  {'OK   ' if ok else 'ERROR'} {nombre} {detalle}")


def credencial(matricula, clave):
    texto = base64.b64encode(f"{matricula}:{clave}".encode("utf-8")).decode()
    return {"Authorization": f"Basic {texto}"}


ACOSTA = credencial("T.º 12 F.º 345", "acosta2026")
LEDESMA = credencial("T.º 15 F.º 210", "ledesma2026")
CLAVE_MAL = credencial("T.º 12 F.º 345", "otra-clave")
SIN_CLAVE = credencial("T.º 12 F.º 345", "")


def desbloquear():
    portal.BLOQUEO.clear()


def borrador_nuevo():
    tramite = tramites.nuevo_tramite("contrato_servicios")
    tramites.cargar_datos(tramite, DATOS_COMPLETOS)
    ruta, _ = tramites.generar_borrador(tramite)
    assert ruta is not None
    return tramite["id"]


def sesion_de_chat(id_tramite):
    # una sesion de chat del empleado que esta trabajando en ese tramite
    # (lo mismo que deja iniciar_contrato en el state, sin usar el modelo)
    sesion = asyncio.run(portal.runner.session_service.create_session(
        app_name=portal.APP, user_id=portal.USUARIO, state={"id_tramite": id_tramite}))
    return sesion.id


print("1) Páginas")
control("página del empleado", cliente.get("/").status_code == 200)
control("página del abogado", cliente.get("/abogado").status_code == 200)
control("sin documentación técnica expuesta", cliente.get("/docs").status_code == 404)

id1 = borrador_nuevo()

print("2) Sin credenciales no se ve nada")
control("pendientes sin credenciales -> 401", cliente.get("/api/pendientes").status_code == 401)
control("ver un trámite sin credenciales -> 401", cliente.get(f"/api/tramite/{id1}").status_code == 401)
r = cliente.get(f"/api/tramite/{id1}", headers=CLAVE_MAL)
control("ver un trámite con clave incorrecta -> 401",
        r.status_code == 401 and "Distribuidora" not in r.text)
control("ver un trámite sin clave -> 401", cliente.get(f"/api/tramite/{id1}", headers=SIN_CLAVE).status_code == 401)
control("credencial mal armada -> 401",
        cliente.get("/api/pendientes", headers={"Authorization": "Basic ###"}).status_code == 401)
desbloquear()  # (cada prueba con clave mala suma un intento fallido)
r = cliente.post("/api/aprobar", json={"id": id1})
control("aprobar sin credenciales -> 401", r.status_code == 401)
r = cliente.post("/api/aprobar", json={"id": id1}, headers=SIN_CLAVE)
control("aprobar sin clave -> 401", r.status_code == 401)
r = cliente.post("/api/aprobar", json={"id": id1}, headers=CLAVE_MAL)
control("aprobar con clave incorrecta -> 401", r.status_code == 401)
r = cliente.post("/api/aprobar", json={"id": id1}, headers=credencial("T.º 12 F.º 345", "ledesma2026"))
control("aprobar con la clave de otro abogado -> 401", r.status_code == 401)
desbloquear()
r = cliente.post("/api/observar", json={"id": id1, "motivo": "x"})
control("observar sin credenciales -> 401", r.status_code == 401)
r = cliente.post("/api/observar", json={"id": id1, "motivo": "x"}, headers=CLAVE_MAL)
control("observar con clave incorrecta -> 401", r.status_code == 401)
tramite = tramites.cargar_tramite(id1)
control("sigue pendiente", tramite["estado"] == "borrador_generado")
control("los intentos rechazados quedan en el historial",
        sum("rechazada" in p["accion"] for p in tramite["historial"]) == 6)
desbloquear()

print("3) Bloqueo después de 5 intentos fallidos")
for _ in range(5):
    cliente.get("/api/pendientes", headers=CLAVE_MAL)
r = cliente.get("/api/pendientes", headers=ACOSTA)
control("con la clave correcta igual queda bloqueada -> 429", r.status_code == 429, f"({r.status_code})")
r = cliente.get("/api/pendientes", headers=credencial("T12F345", "acosta2026"))
control("escribiendo la matrícula de otra forma sigue bloqueada -> 429", r.status_code == 429)
r = cliente.get("/api/pendientes", headers=LEDESMA)
control("bloquear a la Dra. Acosta no impide que entre el Dr. Ledesma", r.status_code == 200,
        f"({r.status_code})")
desbloquear()
for i in range(5):
    cliente.get("/api/pendientes", headers=credencial(f"T.º 9{i} F.º 1", "x"))
r = cliente.get("/api/pendientes", headers=credencial("T.º 99 F.º 7", "x"))
control("5 matrículas al azar distintas bloquean el contador general -> 429",
        r.status_code == 429, f"({r.status_code})")
r = cliente.get("/api/pendientes", headers={"Authorization": "Basic ###"})
control("credenciales mal armadas cuentan en el general -> 429", r.status_code == 429)
control("las matrículas al azar no bloquean a la Dra. Acosta",
        cliente.get("/api/pendientes", headers=ACOSTA).status_code == 200)
desbloquear()
control("pasado el bloqueo, entra", cliente.get("/api/pendientes", headers=ACOSTA).status_code == 200)
for _ in range(4):
    cliente.get("/api/pendientes", headers=CLAVE_MAL)
cliente.get("/api/pendientes", headers=ACOSTA)
cliente.get("/api/pendientes", headers=CLAVE_MAL)
control("un ingreso correcto reinicia la cuenta (4 + 1 no bloquea)",
        cliente.get("/api/pendientes", headers=ACOSTA).status_code == 200)
desbloquear()

print("4) Revisión del abogado")
lista = cliente.get("/api/pendientes", headers=ACOSTA).json()
control("el borrador aparece como pendiente", any(t["id"] == id1 for t in lista["pendientes"]))
detalle = cliente.get(f"/api/tramite/{id1}", headers=ACOSTA).json()
control("el detalle trae los datos", len(detalle["datos"]) == 21 and detalle["pendiente"])
control("trámite inexistente -> 404",
        cliente.get("/api/tramite/T-20990101-000000-0000", headers=ACOSTA).status_code == 404)

print("5) Descargas")
borrador = detalle["enlaces"]["borrador"]
control("borrador sin credenciales ni sesión -> 401", cliente.get(borrador).status_code == 401)
control("borrador con clave incorrecta -> 401", cliente.get(borrador, headers=CLAVE_MAL).status_code == 401)
r = cliente.get(borrador, headers=ACOSTA)
control("el abogado descarga el borrador", r.status_code == 200 and r.content[:2] == b"PK")
sesion_propia = sesion_de_chat(id1)
r = cliente.get(borrador, headers={"X-Sesion": sesion_propia})
control("el empleado descarga el borrador de su sesión", r.status_code == 200 and r.content[:2] == b"PK")
id_otro = borrador_nuevo()
sesion_otra = sesion_de_chat(id_otro)
r = cliente.get(borrador, headers={"X-Sesion": sesion_otra})
control("un empleado descarga el borrador de otra sesión -> 403", r.status_code == 403, f"({r.status_code})")
r = cliente.get(borrador, headers={"X-Sesion": "sesion-inventada"})
control("con una sesión inventada -> 403", r.status_code == 403, f"({r.status_code})")
for intento in ["/descargar/borradores/..%2F..%2Ftramites%2F" + id1 + ".json",
                "/descargar/tramites/" + id1 + ".json",
                "/descargar/borradores/huellas.json",
                "/descargar/borradores/T-20990101-000000-0000_borrador.docx"]:
    control(f"bloqueado: {intento[:60]}", cliente.get(intento, headers=ACOSTA).status_code == 404)
desbloquear()

print("6) Aprobar desde la web")
r = cliente.post("/api/aprobar", json={"id": id1}, headers=ACOSTA).json()
control("abogada con matrícula y clave aprueba", r["ok"], f"({r['mensaje']})")
control("el mensaje no muestra la ruta de la computadora",
        "\\" not in r["mensaje"] and "/" not in r["mensaje"], f"({r['mensaje']})")
control("queda aprobado con su nombre",
        tramites.cargar_tramite(id1)["aprobacion"]["abogado"] == "Dra. Valeria Acosta")
control("queda el Word aprobado para descargar", "word" in r["enlaces"])
for formato in ["word", "pdf"]:
    if formato not in r["enlaces"]:
        if formato == "pdf":
            print("  (no se generó el PDF en esta computadora: se prueba solo el Word)")
        continue
    url = r["enlaces"][formato]
    control(f"aprobado ({formato}) sin credenciales ni sesión -> 401", cliente.get(url).status_code == 401)
    control(f"aprobado ({formato}) con clave incorrecta -> 401",
            cliente.get(url, headers=CLAVE_MAL).status_code == 401)
    control(f"el abogado descarga el {formato} aprobado", cliente.get(url, headers=ACOSTA).status_code == 200)
    control(f"el empleado descarga el {formato} aprobado de su sesión",
            cliente.get(url, headers={"X-Sesion": sesion_propia}).status_code == 200)
    r_otra = cliente.get(url, headers={"X-Sesion": sesion_otra})
    control(f"un empleado descarga el {formato} aprobado de otra sesión -> 403",
            r_otra.status_code == 403, f"({r_otra.status_code})")
    desbloquear()
r = cliente.post("/api/aprobar", json={"id": id1}, headers=ACOSTA).json()
control("no se aprueba dos veces", not r["ok"])

print("7) Observar desde la web")
r = cliente.post("/api/observar", json={"id": id_otro, "motivo": ""}, headers=LEDESMA).json()
control("sin motivo no se puede observar", not r["ok"])
r = cliente.post("/api/observar", json={"id": id_otro, "motivo": "Revisar el domicilio del prestador"},
                 headers=LEDESMA).json()
control("se devuelve con observación", r["ok"])
control("vuelve a carga de datos", tramites.cargar_tramite(id_otro)["estado"] == "cargando_datos")

print("8) Mensajes del empleado")
control("mensaje vacío -> 400", cliente.post("/api/mensaje", json={"texto": "  "}).status_code == 400)
control("mensaje gigante -> 400", cliente.post("/api/mensaje", json={"texto": "a" * 5000}).status_code == 400)

print(f"\nResultado: {total - fallas} de {total} controles OK")
