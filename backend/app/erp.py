"""Conector SIMULADO hacia el ERP de la Secretaría de Salud.

No existe un ERP real: la función `enviar_a_erp` arma el documento con la
estructura que recibiría un ERP (folio, tipo de documento, centro de costos,
partidas de materiales, importes), lo imprime en la consola del servidor
(visible en los logs de Render) y guarda la transacción en la tabla
`erp_transactions` con un acuse de recibo simulado. El tablero muestra una
alerta con el folio para que el usuario vea que la información "viajó" al ERP.

Tipos de documento:
- ORDEN_SERVICIO: brigada de control vectorial asignada (con requisición de materiales).
- AVISO_CIUDADANO: aviso de servicio generado por un reporte de criadero.
- ORDEN_MANTENIMIENTO: nodos IoT sin datos por más de 48 h (falla técnica).
- REPORTE_KPI: indicadores semanales para tableros de dirección.
"""
import json
import logging
import random
import time
from datetime import datetime

from sqlalchemy.orm import Session

from .config import settings
from .models import ErpTransaction
from .timeutil import iso_utc, utcnow

log = logging.getLogger("sentinela.erp")

PREFIJOS = {
    "ORDEN_SERVICIO": "OS",
    "AVISO_CIUDADANO": "AV",
    "ORDEN_MANTENIMIENTO": "OM",
    "REPORTE_KPI": "RK",
}
CENTRO_COSTOS = "SSY-VECTORES-JS1"
SOCIEDAD = "SSY-YUC"

# Catálogo de materiales con precios de referencia (simulados, MXN).
MATERIALES = {
    "LARV-TEMEFOS": ("Larvicida temefós 1% granulado", "KG", 185.0),
    "ADUL-ULV": ("Insecticida adulticida para nebulización ULV", "L", 420.0),
    "HH-BRIGADA": ("Horas-hombre brigada de control vectorial", "H", 120.0),
    "REF-NODO": ("Kit de reposición de nodo (batería, paleta, sello)", "PZA", 650.0),
    "HH-TECNICO": ("Horas-hombre técnico de campo IoT", "H", 160.0),
}


def partida(clave: str, cantidad: float) -> dict:
    desc, unidad, precio = MATERIALES[clave]
    cantidad = round(cantidad, 1)
    return {"material": clave, "descripcion": desc, "cantidad": cantidad, "unidad": unidad,
            "precio_unitario": precio, "importe": round(cantidad * precio, 2)}


def requisicion_brigada(viviendas: int | None, nivel: int) -> list[dict]:
    """Calcula la requisición de materiales según el nivel de riesgo (lógica tipo MRP)."""
    viviendas = viviendas or 3000
    cobertura = {0: 0.05, 1: 0.10, 2: 0.25, 3: 0.40}[nivel]
    casas = max(60, int(viviendas * cobertura))
    lineas = [partida("LARV-TEMEFOS", casas * 0.02), partida("HH-BRIGADA", casas / 12)]
    if nivel >= 3:
        lineas.append(partida("ADUL-ULV", casas * 0.01))
    return lineas


def enviar_a_erp(db: Session, doc_type: str, datos: dict, resumen: str, area_id: str | None = None) -> ErpTransaction:
    """Simula el envío de un documento al ERP y regresa la transacción registrada."""
    tx = ErpTransaction(doc_type=doc_type, created_at=utcnow(), status="ENVIANDO",
                        summary=resumen[:240], area_id=area_id, payload="{}")
    db.add(tx)
    db.flush()  # obtiene el id para el folio
    year = datetime.now().year
    tx.folio = f"{PREFIJOS.get(doc_type, 'DOC')}-{year}-{tx.id:06d}"
    documento = {
        "sistema_origen": "SENTINELA-AEDES",
        "sistema_destino": settings.erp_name,
        "interfaz": "REST/JSON (simulada)",
        "tipo_documento": doc_type,
        "folio_origen": tx.folio,
        "sociedad": SOCIEDAD,
        "centro_costos": CENTRO_COSTOS,
        "fecha_documento": iso_utc(tx.created_at),
        "datos": datos,
    }
    print(f"\n[ERP-SIM] >>> Enviando {doc_type} {tx.folio} a {settings.erp_name} ...", flush=True)
    print("[ERP-SIM]     " + json.dumps(documento, ensure_ascii=False, default=str), flush=True)
    time.sleep(random.uniform(0.08, 0.25))  # latencia de red simulada
    acuse = {
        "estado": "RECIBIDO",
        "id_documento_erp": str(4500000000 + tx.id),
        "mensaje": "Documento registrado en el ERP (simulado). Listo para su uso por las áreas de la SSY.",
        "recibido_en": iso_utc(utcnow()),
    }
    print(f"[ERP-SIM] <<< Acuse {acuse['estado']} · documento ERP {acuse['id_documento_erp']} para {tx.folio}\n", flush=True)
    log.info("ERP: %s %s confirmado (%s)", doc_type, tx.folio, resumen)
    tx.payload = json.dumps(documento, ensure_ascii=False, default=str)
    tx.ack = json.dumps(acuse, ensure_ascii=False)
    tx.status = "CONFIRMADO"
    return tx


def tx_payload(tx: ErpTransaction, include_document: bool = False) -> dict:
    out = {
        "folio": tx.folio, "doc_type": tx.doc_type, "status": tx.status, "summary": tx.summary,
        "area_id": tx.area_id, "created_at": iso_utc(tx.created_at),
        "ack": json.loads(tx.ack) if tx.ack else None,
    }
    if include_document:
        out["document"] = json.loads(tx.payload)
    return out
