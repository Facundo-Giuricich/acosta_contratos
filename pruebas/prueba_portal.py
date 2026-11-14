# Pruebas del portal web (la parte que no necesita el modelo):
# pagina del abogado, aprobar / observar desde la web y descargas.
#
# Uso: .\env\Scripts\python.exe -m pruebas.prueba_portal

from fastapi.testclient import TestClient

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


def borrador_nuevo():
    tramite = tramites.nuevo_tramite("contrato_servicios")
    tramites.cargar_datos(tramite, DATOS_COMPLETOS)
    ruta, _ = tramites.generar_borrador(tramite)
    assert ruta is not None
    return tramite["id"]


print("1) Páginas")
control("página del empleado", cliente.get("/").status_code == 200)
control("página del abogado", cliente.get("/abogado").status_code == 200)
control("sin documentación técnica expuesta", cliente.get("/docs").status_code == 404)

print("2) Revisión del abogado")
id1 = borrador_nuevo()
lista = cliente.get("/api/pendientes").json()
control("el borrador aparece como pendiente", any(t["id"] == id1 for t in lista["pendientes"]))
detalle = cliente.get(f"/api/tramite/{id1}").json()
control("el detalle trae los datos", len(detalle["datos"]) == 21 and detalle["pendiente"])
control("trámite inexistente -> 404", cliente.get("/api/tramite/T-20990101-000000-0000").status_code == 404)

print("3) Descargas")
borrador = detalle["enlaces"]["borrador"]
r = cliente.get(borrador)
control("se descarga el borrador", r.status_code == 200 and r.content[:2] == b"PK")
for intento in ["/descargar/borradores/..%2F..%2Ftramites%2F" + id1 + ".json",
                "/descargar/tramites/" + id1 + ".json",
                "/descargar/borradores/huellas.json",
                "/descargar/borradores/T-20990101-000000-0000_borrador.docx"]:
    control(f"bloqueado: {intento[:60]}", cliente.get(intento).status_code == 404)

print("4) Aprobar desde la web")
r = cliente.post("/api/aprobar", json={"id": id1, "nombre": "Juan Pérez", "matricula": "T.º 12 F.º 345"}).json()
control("nombre que no corresponde a la matrícula", not r["ok"], f"({r['mensaje']})")
r = cliente.post("/api/aprobar", json={"id": id1, "nombre": "Valeria Acosta", "matricula": "T.º 99 F.º 1"}).json()
control("matrícula no autorizada", not r["ok"], f"({r['mensaje']})")
r = cliente.post("/api/aprobar", json={"id": id1, "nombre": "Dra. Valeria Acosta", "matricula": "T.º 12 F.º 345"}).json()
control("abogado autorizado aprueba", r["ok"], f"({r['mensaje']})")
control("queda el Word aprobado para descargar", "word" in r["enlaces"])
if "word" in r["enlaces"]:
    control("se descarga el Word aprobado", cliente.get(r["enlaces"]["word"]).status_code == 200)
r = cliente.post("/api/aprobar", json={"id": id1, "nombre": "Dra. Valeria Acosta", "matricula": "T.º 12 F.º 345"}).json()
control("no se aprueba dos veces", not r["ok"])

print("5) Observar desde la web")
id2 = borrador_nuevo()
r = cliente.post("/api/observar", json={"id": id2, "nombre": "Dr. Tomás Ledesma", "motivo": ""}).json()
control("sin motivo no se puede observar", not r["ok"])
r = cliente.post("/api/observar", json={"id": id2, "nombre": "Dr. Tomás Ledesma",
                                         "motivo": "Revisar el domicilio del prestador"}).json()
control("se devuelve con observación", r["ok"])
control("vuelve a carga de datos", tramites.cargar_tramite(id2)["estado"] == "cargando_datos")

print("6) Mensajes del empleado")
control("mensaje vacío -> 400", cliente.post("/api/mensaje", json={"texto": "  "}).status_code == 400)
control("mensaje gigante -> 400", cliente.post("/api/mensaje", json={"texto": "a" * 5000}).status_code == 400)

print(f"\nResultado: {total - fallas} de {total} controles OK")
