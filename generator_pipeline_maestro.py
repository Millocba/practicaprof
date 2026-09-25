#!/usr/bin/env python3
"""
Pipeline Maestro - Ejecuta todos los generadores de datos
Genera: Flota, Telemetría, Consumo, Facturación, Solicitudes

Además registra en `ground_truth.csv` cada anomalía inyectada. Ese archivo es la
verdad de referencia para evaluar la detección y no debe usarse como entrada de
los modelos.

Reproducibilidad: la misma semilla produce exactamente los mismos datos. Todas las
fechas se calculan desde FECHA_REFERENCIA, nunca desde la hora actual.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import random

import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rutas
BASE_DIR = Path(__file__).parent
DATASETS_DIR = BASE_DIR / "datasets" / "synthetics_maestro"
DIRECTORIOS_ESCENARIO = {
    "didactico": DATASETS_DIR,
    "realista": BASE_DIR / "datasets" / "synthetics_realista",
}

# Seed para reproducibilidad
SEED = 42

# Ventana temporal de los datos: consumos y solicitudes entre FECHA_INICIO y
# FECHA_INICIO + DIAS_VENTANA. FECHA_REFERENCIA hace de "ahora" para la telemetría.
FECHA_INICIO = datetime(2024, 1, 1)
DIAS_VENTANA = 270
FECHA_REFERENCIA = FECHA_INICIO + timedelta(days=DIAS_VENTANA + 1)

# Tasas de inyección de anomalías en CONSUMO
TASA_VEHICULOS_EXCESO = 0.07      # vehículos que cargan más que su tanque (H3a)
TASA_ODOMETRO_REGRESIVO = 0.012   # transacciones con retroceso de odómetro (H2)
TASA_ODOMETRO_SALTO = 0.012       # transacciones con salto de odómetro (H2)
TASA_DOMINIO_INVALIDO = 0.01      # dominios mal formados (H1)
TASA_NULOS = 0.02                 # campos vacíos (calidad)
TASA_DUPLICADOS = 0.01            # filas duplicadas (calidad)

# tipo_anomalia -> (hipótesis, severidad)
CATALOGO_ANOMALIAS = {
    "EXCESO_VOLUMETRICO": ("H3a", "ALTA"),
    "ODOMETRO_REGRESIVO": ("H2", "ALTA"),
    "ODOMETRO_SALTO": ("H2", "ALTA"),
    "DOMINIO_INVALIDO": ("H1", "MEDIA"),
    "VALOR_NULO": ("CALIDAD", "BAJA"),
    "DUPLICADO": ("CALIDAD", "MEDIA"),
    # Solo en el escenario realista
    "ODOMETRO_REGRESIVO_LEVE": ("H2", "MEDIA"),
    "FRACCIONAMIENTO": ("H4", "ALTA"),
    "RENDIMIENTO_IMPOSIBLE": ("H5", "ALTA"),
    "CARGA_VEHICULO_INACTIVO": ("H6", "ALTA"),
    "CARGA_FUERA_DE_ZONA": ("H7", "ALTA"),
    # Circuito solicitud -> carga -> factura (escenario realista)
    "CARGA_SIN_SOLICITUD": ("H8", "ALTA"),
    "CARGA_CON_SOLICITUD_RECHAZADA": ("H8", "ALTA"),
    "CARGA_SUPERA_AUTORIZADO": ("H8", "MEDIA"),
    "TOTAL_INFLADO": ("H9", "ALTA"),
    "LINEA_SIN_CONSUMO": ("H9", "ALTA"),
    "LINEA_DUPLICADA": ("H9", "ALTA"),
    "SOBREPRECIO": ("H9", "MEDIA"),
}

ESCENARIOS = ("didactico", "realista")

TIPOS_POR_ESCENARIO = {
    "didactico": ["EXCESO_VOLUMETRICO", "ODOMETRO_REGRESIVO", "ODOMETRO_SALTO",
                  "DOMINIO_INVALIDO", "VALOR_NULO", "DUPLICADO"],
    "realista": list(CATALOGO_ANOMALIAS),
}

# Casos legítimos que se parecen a una anomalía (escenario realista). No van al
# ground truth: se registran en casos_legitimos.csv para medir las falsas alarmas.
CATALOGO_LEGITIMOS = {
    "TANQUE_AUXILIAR": "el vehículo tiene más capacidad que la registrada y carga por encima del tanque",
    "VIAJE_LARGO": "carga en estaciones de ruta durante un viaje real",
    "CAMBIO_ODOMETRO": "el odómetro se reemplazó y vuelve a contar desde un valor bajo",
    "ERROR_TIPEO_ODOMETRO": "la lectura del odómetro se cargó con un error de tipeo",
    "REGULARIZACION_POSTERIOR": "la solicitud se aprobó después de la carga (urgencia regularizada)",
    "TOLERANCIA_MEDICION": "la carga supera lo autorizado dentro de la tolerancia de medición del surtidor",
    "DESFASE_DE_CORTE": "la carga del último día del mes se factura en el período siguiente",
    "AJUSTE_DOCUMENTADO": "la factura incluye un ajuste documentado (bonificación o recargo)",
    "DOMINIO_CON_FORMATO": "el dominio se registró con espacios, guiones o minúsculas; normalizado es el del vehículo",
}

COLUMNAS_CASOS_LEGITIMOS = ["tabla", "id_registro", "vehiculo_id", "tipo_caso", "descripcion"]

# Anomalías que siguen presentes en una fila duplicada (las de odómetro no: la copia
# repite fecha y lectura, así que no hay cambio que detectar)
ANOMALIAS_HEREDABLES = {"EXCESO_VOLUMETRICO", "DOMINIO_INVALIDO", "VALOR_NULO"}

COLUMNAS_GROUND_TRUTH = [
    "tabla", "id_registro", "vehiculo_id", "tipo_anomalia",
    "columna", "hipotesis", "severidad", "descripcion",
]

# Catálogos de la flota (compartidos por ambos escenarios; el orden importa para
# la reproducibilidad)
DIRECCIONES = [
    "DIRECCION GRAL. SEGURIDAD CAPITAL",
    "DIRECCION GRAL. SEGURIDAD PROVINCIA",
    "DIRECCION GRAL. LOGISTICA",
    "DIRECCION GRAL. OBRAS",
    "DIRECCION GRAL. SALUD",
]
DEPENDENCIAS = {
    "DIRECCION GRAL. SEGURIDAD CAPITAL": ["DEP A", "DEP B", "DEP C"],
    "DIRECCION GRAL. SEGURIDAD PROVINCIA": ["DEP D", "DEP E"],
    "DIRECCION GRAL. LOGISTICA": ["DEP F", "DEP G"],
    "DIRECCION GRAL. OBRAS": ["DEP H"],
    "DIRECCION GRAL. SALUD": ["DEP I", "DEP J"],
}
MARCAS = ["FORD", "TOYOTA", "VOLKSWAGEN", "RENAULT", "HONDA", "FIAT", "IVECO", "CHEVROLET"]
TIPOS_VEHICULO = ["SEDAN", "PICK-UP", "MOTOCICLETA", "CAMIONETA", "CAMION", "AMBULANCIA", "UTILITARIO", "BOMBERO"]
COMBUSTIBLES = ["GASOIL", "GASOIL", "GASOIL", "GASOIL", "GASOIL", "NAFTA", "NAFTA", "NAFTA", "GLP"]
MARCAS_ESTACION = ["YPF", "SHELL", "AXION", "PUMA", "ESTACION LOCAL"]

# ============================================================================
# Parámetros del escenario realista
# ============================================================================

# tipo: (capacidad del tanque en L, rendimiento en km/L, km por día hábil)
PERFILES_VEHICULO = {
    "MOTOCICLETA": ((10, 18), (25, 35), (20, 60)),
    "SEDAN": ((45, 60), (10, 14), (30, 70)),
    "PICK-UP": ((70, 80), (7, 10), (40, 90)),
    "CAMIONETA": ((60, 80), (7, 10), (40, 90)),
    "UTILITARIO": ((55, 70), (8, 11), (40, 80)),
    "AMBULANCIA": ((70, 90), (6, 8), (50, 120)),
    "CAMION": ((150, 300), (2.5, 4), (60, 150)),
    "BOMBERO": ((150, 250), (2, 3.5), (10, 40)),
}
# 75% en servicio, 10% en reparación, 5% fuera de servicio, 10% de baja
ESTADOS_REALISTA = ["EN SERVICIO"] * 15 + ["EN REPARACION"] * 2 + ["FUERA DE SERVICIO"] + ["BAJA"] * 2
PRODUCTOS_POR_COMBUSTIBLE = {
    "GASOIL": ["GASOIL", "INFINIA DIESEL"],
    "NAFTA": ["NAFTA", "SUPER", "INFINIA"],
    "GLP": ["GLP"],
}
PRECIO_BASE = {"GASOIL": 2.0, "INFINIA DIESEL": 2.4, "NAFTA": 2.1, "SUPER": 2.3, "INFINIA": 2.6, "GLP": 1.2}
AUMENTO_MENSUAL_PRECIO = 0.02

ZONA_BASE = {"lat": (-34.9, -34.4), "lon": (-58.8, -58.2)}
N_ESTACIONES_LOCALES = 40
N_RUTAS = 5
FRACCIONES_RUTA = [0.25, 0.45, 0.65, 0.85, 1.0]  # una estación en cada tramo de la ruta
COBERTURA_GPS = 0.88            # vehículos con dispositivo
TASA_DIAS_SIN_SENAL = 0.03      # días en que el dispositivo no reporta
PROB_DIA_SIN_USO = 0.25
PROB_CARGA_PARCIAL = 0.25
RESERVA_TANQUE = 0.05           # fracción del tanque en la que el vehículo obliga a cargar

# Cantidad de casos por cada 200 vehículos (escala con n_flota)
EVENTOS_REALISTA = {
    "EXCESO_VOLUMETRICO": 2,        # vehículos que empiezan a cargar más que su tanque
    "RENDIMIENTO_IMPOSIBLE": 2,     # vehículos con cargas que no se corresponden con su uso
    "FRACCIONAMIENTO": 6,           # vehículos con un día de cargas repartidas
    "CARGA_VEHICULO_INACTIVO": 3,   # vehículos fuera de servicio o de baja con cargas
    "CARGA_FUERA_DE_ZONA": 6,       # vehículos con una carga lejos de donde está el vehículo
    "ODOMETRO_REGRESIVO": 3,
    "ODOMETRO_REGRESIVO_LEVE": 4,
    "ODOMETRO_SALTO": 3,
    "TANQUE_AUXILIAR": 3,           # legítimos
    "VIAJE_LARGO": 4,
    "CAMBIO_ODOMETRO": 2,
    "ERROR_TIPEO_ODOMETRO": 5,
    # Circuito solicitud -> carga -> factura
    "CARGA_SIN_SOLICITUD": 6,       # cargas sin ninguna solicitud
    "CARGA_CON_SOLICITUD_RECHAZADA": 4,
    "CARGA_SUPERA_AUTORIZADO": 6,   # 15% a 50% más que lo autorizado
    "REGULARIZACION_POSTERIOR": 8,  # legítimos
    "TOLERANCIA_MEDICION": 10,      # legítimos: 1% a 3% más que lo autorizado
    "TOTAL_INFLADO": 2,             # facturas
    "LINEA_SIN_CONSUMO": 6,
    "LINEA_DUPLICADA": 5,
    "SOBREPRECIO": 6,
    "AJUSTE_DOCUMENTADO": 4,        # legítimos: facturas con un ajuste
}
PROB_DESFASE_DE_CORTE = 0.5         # cargas del último día del mes facturadas al mes siguiente
TASA_SOLICITUDES_SIN_CARGA = 0.08   # solicitudes rechazadas o pendientes que no terminan en carga
TASAS_CALIDAD_REALISTA = {"DOMINIO_INVALIDO": 0.003, "VALOR_NULO": 0.005, "DUPLICADO": 0.003}

# Formatos de origen (realista): cómo llegan los datos de cada fuente, sin ser anomalías.
# Se aplican al final con un generador aleatorio propio, para no alterar el resto del escenario.
TASA_DOMINIO_CON_FORMATO = 0.02     # cargas con el dominio escrito de otra forma (H1)
TASA_FECHA_OTRO_FORMATO = 0.15      # solicitudes con la fecha en DD/MM/AAAA en lugar de AAAA-MM-DD
FORMATOS_DOMINIO = [
    lambda d: d.lower(),                                  # ab0001cd
    lambda d: f"{d[:2]} {d[2:-2]} {d[-2:]}",              # AB 0001 CD
    lambda d: f"{d[:2]}-{d[2:-2]}-{d[-2:]}",              # AB-0001-CD
    lambda d: f"{d} ",                                    # espacio al final
]


# ============================================================================
# Diccionario de datos y relaciones
#
# Fuente única de la descripción de cada archivo: el generador escribe
# `diccionario.json` con las tablas y relaciones del escenario generado, y un test
# verifica que describa todas las columnas que se producen.
# ============================================================================

AMBOS = ("didactico", "realista")
REALISTA = ("realista",)

# tabla: grano, clave, escenarios y columnas {nombre: (tipo, descripción[, escenarios])}
TABLAS = {
    "flota": {
        "grano": "un vehículo", "clave": "Matricula", "escenarios": AMBOS,
        "columnas": {
            "Matricula": ("texto", "Clave del vehículo, VEH-NNNNNN"),
            "Dominio": ("texto", "Dominio sintético ABNNNNCD, único; no proviene de un padrón"),
            "Estado": ("categoría", "EN SERVICIO, EN REPARACION, FUERA DE SERVICIO o BAJA"),
            "DireccionGral": ("categoría", "Dirección ficticia a la que pertenece el vehículo"),
            "Dependencia": ("categoría", "Dependencia ficticia dentro de la dirección"),
            "Identificable": ("SI / NO", "Si el vehículo lleva identificación visible"),
            "TipoVehiculo": ("categoría", "SEDAN, PICK-UP, MOTOCICLETA, CAMIONETA, CAMION, AMBULANCIA, UTILITARIO o BOMBERO"),
            "Marca": ("categoría", "Marca de un catálogo público general"),
            "Modelo": ("texto", "Modelo genérico MODEL-AAAA"),
            "Año": ("entero", "Año del vehículo"),
            "TipoCombustible": ("categoría", "GASOIL, NAFTA o GLP"),
            "CapacidadTanque": ("decimal (L)", "Capacidad registrada del tanque"),
            "NumeroMotor": ("texto", "Número de motor"),
            "NumeroChasis": ("texto", "Número de chasis"),
            "NumeroTarjeta": ("texto", "Tarjeta de combustible asignada"),
            "LimiteSaldo": ("decimal", "Límite de saldo de la tarjeta"),
            "LimiteLitros": ("decimal (L)", "Límite de litros de la tarjeta"),
            "SubEstado": ("categoría", "ACTIVO si está EN SERVICIO; si no, INACTIVO"),
            "FechaEstado": ("fecha", "Último cambio a un estado distinto de EN SERVICIO; vacía si está en servicio",
                            REALISTA),
        },
    },
    "telemetria": {
        "grano": "un dispositivo GPS", "clave": "IMEI", "escenarios": AMBOS,
        "columnas": {
            "IMEI": ("entero", "Identificador del dispositivo"),
            "Alias": ("texto", "Alias del dispositivo, DEV-NNNNNN"),
            "Placa": ("texto", "Dominio del vehículo en el que está instalado"),
            "MSISDN": ("entero", "Línea sintética del dispositivo"),
            "Modelo": ("texto", "Modelo del dispositivo"),
            "Tipo": ("texto", "Siempre GPS"),
            "Estado": ("categoría", "ONLINE u OFFLINE"),
            "Bateria": ("decimal (%)", "Nivel de batería"),
            "UltimaConexion": ("fecha y hora", "Último reporte del dispositivo"),
            "Latitud": ("decimal", "Última posición: latitud"),
            "Longitud": ("decimal", "Última posición: longitud"),
            "Odometro": ("entero (km)", "Odómetro del dispositivo"),
        },
    },
    "telemetria_diaria": {
        "grano": "un dispositivo y un día", "clave": "Placa + fecha", "escenarios": REALISTA,
        "columnas": {
            "Placa": ("texto", "Dominio del vehículo"),
            "fecha": ("fecha", "Día"),
            "km_gps": ("decimal (km)", "km recorridos ese día según el GPS"),
            "lat_inicio": ("decimal", "Latitud al empezar el recorrido del día"),
            "lon_inicio": ("decimal", "Longitud al empezar el recorrido del día"),
            "lat_fin": ("decimal", "Latitud al terminar el recorrido del día"),
            "lon_fin": ("decimal", "Longitud al terminar el recorrido del día"),
        },
    },
    "estaciones": {
        "grano": "una estación de servicio", "clave": "codigo", "escenarios": REALISTA,
        "columnas": {
            "codigo": ("texto", "Código de la estación, EST-NNN"),
            "marca": ("categoría", "Marca de la estación; es el proveedor que factura"),
            "ubicacion": ("categoría", "LOCAL (zona de operación) o RUTA"),
            "latitud": ("decimal", "Latitud"),
            "longitud": ("decimal", "Longitud"),
        },
    },
    "consumo": {
        "grano": "una carga de combustible", "clave": "id", "escenarios": AMBOS,
        "columnas": {
            "id": ("texto", "Clave de la carga, CONS-NNNNNNNN"),
            "vehiculo_id": ("texto", "Vehículo que cargó"),
            "dominio": ("texto", "Dominio informado en la carga; puede no coincidir con la flota"),
            "fecha": ("fecha", "Fecha de la carga"),
            "estacion": ("texto", "Estación (marca en el didáctico, código en el realista); puede estar vacía"),
            "producto": ("categoría", "Combustible cargado"),
            "litros": ("decimal (L)", "Litros cargados"),
            "precio_unitario": ("decimal", "Precio por litro"),
            "importe_total": ("decimal", "litros × precio_unitario"),
            "numero_tarjeta": ("texto", "Tarjeta de combustible usada"),
            "conductor": ("texto", "Conductor, CONDUCTOR-N; puede estar vacío"),
            "odometro": ("entero (km)", "Lectura del odómetro informada en la carga; puede estar vacía"),
        },
    },
    "solicitudes": {
        "grano": "una solicitud de combustible", "clave": "id", "escenarios": AMBOS,
        "columnas": {
            "id": ("texto", "Clave de la solicitud, SOL-NNNNNNNN"),
            "vehiculo_id": ("texto", "Vehículo solicitante"),
            "dominio": ("texto", "Dominio del vehículo solicitante"),
            "fecha_solicitud": ("fecha", "Fecha de la solicitud, AAAA-MM-DD; en el escenario realista, "
                                         "una parte llega como DD/MM/AAAA"),
            "litros_solicitados": ("decimal (L)", "Litros pedidos"),
            "litros_autorizados": ("decimal (L)", "Litros autorizados; 0 si fue rechazada o está pendiente"),
            "estado": ("categoría", "APROBADA, PENDIENTE o RECHAZADA"),
            "centro_costo": ("texto", "Centro de costo, CC-NNN"),
            "responsable": ("texto", "Responsable, RESP-N"),
            "observaciones": ("texto", "Observaciones; puede estar vacía"),
        },
    },
    "facturacion": {
        "grano": "una factura mensual (de toda la flota en el didáctico; de un proveedor en el realista)",
        "clave": "numero_factura", "escenarios": AMBOS,
        "columnas": {
            "numero_factura": ("texto", "Número de factura"),
            "proveedor": ("categoría", "Marca de estación que factura", REALISTA),
            "fecha_factura": ("fecha", "Último día del período"),
            "periodo": ("texto", "Período facturado, AAAA-MM"),
            "total_litros": ("decimal (L)", "Litros facturados"),
            "total_monto": ("decimal", "Importe sin IVA"),
            "iva": ("decimal", "21% de total_monto"),
            "monto_total_con_iva": ("decimal", "total_monto × 1,21"),
            "estado": ("categoría", "PAGADA, PENDIENTE o VENCIDA"),
            "numero_transacciones": ("entero", "Cantidad de cargas facturadas"),
        },
    },
    "facturacion_detalle": {
        "grano": "una línea de factura", "clave": "numero_linea", "escenarios": REALISTA,
        "columnas": {
            "numero_linea": ("texto", "Clave de la línea, LIN-NNNNNNNN"),
            "numero_factura": ("texto", "Factura a la que pertenece"),
            "referencia_consumo": ("texto", "Carga que factura; vacía en los ajustes"),
            "concepto": ("categoría", "COMBUSTIBLE o AJUSTE"),
            "fecha": ("fecha", "Fecha de la carga según el proveedor"),
            "dominio": ("texto", "Dominio según el proveedor"),
            "litros": ("decimal (L)", "Litros facturados"),
            "precio_unitario": ("decimal", "Precio por litro facturado"),
            "importe": ("decimal", "Importe de la línea"),
            "descripcion": ("texto", "Motivo del ajuste; vacía en las líneas de combustible"),
        },
    },
    "ground_truth": {
        "grano": "una anomalía inyectada (verdad de referencia: no es entrada de los modelos)",
        "clave": "tabla + id_registro + tipo_anomalia", "escenarios": AMBOS,
        "columnas": {
            "tabla": ("categoría", "Tabla del registro afectado"),
            "id_registro": ("texto", "Clave del registro afectado en esa tabla"),
            "vehiculo_id": ("texto", "Vehículo involucrado, si corresponde"),
            "tipo_anomalia": ("categoría", "Tipo de anomalía (ver CATALOGO_ANOMALIAS)"),
            "columna": ("texto", "Columna donde se manifiesta"),
            "hipotesis": ("categoría", "Hipótesis que la anomalía permite contrastar"),
            "severidad": ("categoría", "ALTA, MEDIA o BAJA"),
            "descripcion": ("texto", "Detalle legible"),
        },
    },
    "casos_legitimos": {
        "grano": "un caso legítimo que se parece a una anomalía", "clave": "tabla + id_registro",
        "escenarios": REALISTA,
        "columnas": {
            "tabla": ("categoría", "Tabla del registro"),
            "id_registro": ("texto", "Clave del registro en esa tabla"),
            "vehiculo_id": ("texto", "Vehículo involucrado, si corresponde"),
            "tipo_caso": ("categoría", "Tipo de caso (ver CATALOGO_LEGITIMOS)"),
            "descripcion": ("texto", "Detalle legible"),
        },
    },
}

# (origen, columna origen, destino, columna destino, cardinalidad, escenarios, nota)
RELACIONES = [
    ("consumo", "vehiculo_id", "flota", "Matricula", "N:1", AMBOS, ""),
    ("consumo", "dominio", "flota", "Dominio", "N:1", AMBOS, "se rompe en DOMINIO_INVALIDO"),
    ("consumo", "numero_tarjeta", "flota", "NumeroTarjeta", "N:1", AMBOS, ""),
    ("consumo", "estacion", "estaciones", "codigo", "N:1", REALISTA, ""),
    ("solicitudes", "vehiculo_id", "flota", "Matricula", "N:1", AMBOS, ""),
    ("solicitudes", "vehiculo_id + fecha_solicitud + litros_autorizados", "consumo",
     "vehiculo_id + fecha + litros", "1:1", REALISTA,
     "sin clave: se empareja por vehículo, fecha y litros"),
    ("telemetria", "Placa", "flota", "Dominio", "N:1", AMBOS, "uno por vehículo en el realista"),
    ("telemetria_diaria", "Placa", "telemetria", "Placa", "N:1", REALISTA, ""),
    ("facturacion", "periodo", "consumo", "fecha (mes)", "1:N", ("didactico",), "suma de las cargas del mes"),
    ("facturacion", "proveedor", "estaciones", "marca", "N:1", REALISTA, ""),
    ("facturacion_detalle", "numero_factura", "facturacion", "numero_factura", "N:1", REALISTA,
     "la suma de las líneas es el total (salvo TOTAL_INFLADO)"),
    ("facturacion_detalle", "referencia_consumo", "consumo", "id", "N:1", REALISTA,
     "se rompe en LINEA_SIN_CONSUMO; dos líneas en LINEA_DUPLICADA"),
    ("ground_truth", "id_registro", "consumo / facturacion / facturacion_detalle", "id", "N:1", AMBOS,
     "según la columna tabla"),
    ("casos_legitimos", "id_registro", "consumo / facturacion / facturacion_detalle", "id", "N:1", REALISTA,
     "según la columna tabla"),
]


def diccionario_de_datos(escenario, columnas_generadas=None):
    """Tablas y relaciones de un escenario.

    Si se pasa `columnas_generadas` ({tabla: [columnas]}), solo incluye esas tablas y
    columnas, en su orden: el diccionario describe exactamente lo que se escribió.
    """
    tablas = {}
    for nombre, tabla in TABLAS.items():
        if escenario not in tabla["escenarios"]:
            continue
        if columnas_generadas is not None and nombre not in columnas_generadas:
            continue
        definidas = {c: d for c, d in tabla["columnas"].items() if escenario in (d[2] if len(d) > 2 else AMBOS)}
        orden = columnas_generadas[nombre] if columnas_generadas is not None else list(definidas)
        tablas[nombre] = {
            "grano": tabla["grano"], "clave": tabla["clave"],
            "columnas": [{"nombre": c, "tipo": definidas[c][0], "descripcion": definidas[c][1]}
                         for c in orden if c in definidas],
        }
    relaciones = []
    for o, co, d, cd, card, escenarios, nota in RELACIONES:
        # Un destino múltiple ("a / b") conserva solo las tablas del escenario
        destinos = [t.strip() for t in d.split("/") if t.strip() in tablas]
        if escenario in escenarios and o in tablas and destinos:
            relaciones.append({"origen": o, "columna_origen": co, "destino": " / ".join(destinos),
                               "columna_destino": cd, "cardinalidad": card, "nota": nota})
    return {"escenario": escenario, "tablas": tablas, "relaciones": relaciones}


def diagrama_relaciones(diccionario):
    """Diagrama de relaciones en formato DOT (Graphviz) a partir del diccionario."""
    lineas = ['digraph relaciones {', '  rankdir=LR; node [shape=box, style="rounded,filled", '
              'fillcolor="#eef3fb", fontname="Helvetica"]; edge [fontname="Helvetica", fontsize=9];']
    for nombre, tabla in diccionario["tablas"].items():
        color = '#fdf1dc' if nombre in ("ground_truth", "casos_legitimos") else '#eef3fb'
        lineas.append(f'  "{nombre}" [label="{nombre}\\n({tabla["grano"].split(" (")[0]})", fillcolor="{color}"];')
    for r in diccionario["relaciones"]:
        for destino in (d.strip() for d in r["destino"].split("/")):
            estilo = ', style=dashed' if r["nota"].startswith("sin clave") or "suma" in r["nota"] else ''
            lineas.append(f'  "{r["origen"]}" -> "{destino}" [label="{r["columna_origen"]} ({r["cardinalidad"]})"{estilo}];')
    lineas.append("}")
    return "\n".join(lineas)


def distancia_km(lat1, lon1, lat2, lon2):
    """Distancia sobre la superficie terrestre (fórmula del haversine)."""
    from math import asin, cos, radians, sin, sqrt
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def _interpolar(origen, destino, fraccion):
    return (origen[0] + (destino[0] - origen[0]) * fraccion,
            origen[1] + (destino[1] - origen[1]) * fraccion)


def _error_de_tipeo(valor, rng):
    """Lectura con dos dígitos intercambiados (o uno cambiado) que difiere en ≥1000 km."""
    texto = str(int(valor))
    for _ in range(20):
        i = rng.randint(0, len(texto) - 4)
        if texto[i] != texto[i + 1]:
            nuevo = int(texto[:i] + texto[i + 1] + texto[i] + texto[i + 2:])
            if abs(nuevo - valor) >= 1000:
                return nuevo
    i = rng.randint(0, len(texto) - 4)
    digito = str((int(texto[i]) + rng.randint(1, 8)) % 10)
    return int(texto[:i] + digito + texto[i + 1:])


class GeneradorMaestro:
    """Orquesta la generación de todas las entidades"""

    def __init__(self, n_flota=200, seed=SEED, output_dir=None, escenario="didactico"):
        if escenario not in ESCENARIOS:
            raise ValueError(f"escenario debe ser uno de {ESCENARIOS}")
        self.n_flota = n_flota
        self.seed = seed
        self.escenario = escenario
        self.output_dir = Path(output_dir) if output_dir else DIRECTORIOS_ESCENARIO[escenario]
        # Generador propio: no depende del estado global de `random`
        self.rng = random.Random(seed)
        self.datasets = {}
        self.anomalias = []
        self.casos_legitimos = []
        self.metadata = {
            "fecha_generacion": datetime.now().isoformat(),
            "fecha_referencia": FECHA_REFERENCIA.isoformat(),
            "escenario": escenario,
            "seed": seed,
            "n_flota": n_flota,
            "generadores_ejecutados": []
        }

    def _registrar_anomalia(self, tabla, id_registro, vehiculo_id, tipo, columna, descripcion):
        hipotesis, severidad = CATALOGO_ANOMALIAS[tipo]
        self.anomalias.append({
            "tabla": tabla,
            "id_registro": id_registro,
            "vehiculo_id": vehiculo_id,
            "tipo_anomalia": tipo,
            "columna": columna,
            "hipotesis": hipotesis,
            "severidad": severidad,
            "descripcion": descripcion,
        })

    def generar_flota(self):
        """Genera tabla FLOTA (200 vehículos)"""
        logger.info("Generando FLOTA...")
        rng = self.rng

        dg = DIRECCIONES
        dependencias = DEPENDENCIAS
        marcas = MARCAS
        tipos = TIPOS_VEHICULO
        combustible = COMBUSTIBLES
        estados = ["EN SERVICIO", "EN SERVICIO", "EN SERVICIO", "EN REPARACION", "FUERA DE SERVICIO", "BAJA"]

        rows = []
        for i in range(1, self.n_flota + 1):
            dg_sel = rng.choice(dg)
            dep = rng.choice(dependencias[dg_sel])
            estado = rng.choice(estados)
            identificable = "SI" if rng.random() < 0.94 else "NO"
            annio = rng.randint(2005, 2024)

            rows.append({
                "Matricula": f"VEH-{i:06d}",
                "Dominio": f"AB{i:04d}CD",
                "Estado": estado,
                "DireccionGral": dg_sel,
                "Dependencia": dep,
                "Identificable": identificable,
                "TipoVehiculo": rng.choice(tipos),
                "Marca": rng.choice(marcas),
                "Modelo": f"MODEL-{rng.randint(2010, 2024)}",
                "Año": annio,
                "TipoCombustible": rng.choice(combustible),
                "CapacidadTanque": rng.uniform(40, 120),
                "NumeroMotor": f"M{i:08d}",
                "NumeroChasis": f"CH{i:08d}",
                "NumeroTarjeta": f"TARJ{i:08d}",
                "LimiteSaldo": rng.uniform(1000, 10000),
                "LimiteLitros": rng.uniform(100, 500),
                "SubEstado": "ACTIVO" if estado == "EN SERVICIO" else "INACTIVO",
            })

        df = pd.DataFrame(rows)
        self.datasets['flota'] = df
        self.metadata['generadores_ejecutados'].append('flota')
        logger.info(f"✓ FLOTA generada: {len(df)} vehículos")
        return df

    def generar_telemetria(self):
        """Genera tabla TELEMETRIA (dispositivos GPS)"""
        logger.info("Generando TELEMETRIA...")
        rng = self.rng

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        n_dispositivos = int(self.n_flota * 0.88)  # 88% cobertura

        rows = []
        for i in range(1, n_dispositivos + 1):
            online = rng.random() < 0.88
            bateria = round(rng.uniform(20, 100), 1)
            last = FECHA_REFERENCIA - timedelta(minutes=rng.randint(0, 15 if online else 600))

            # Link a un vehículo de la flota
            vehiculo = rng.choice(list(flota_df['Dominio'].values))

            rows.append({
                "IMEI": f"{rng.randint(350000000000000, 359999999999999)}",
                "Alias": f"DEV-{i:06d}",
                "Placa": vehiculo,
                "MSISDN": f"54911{rng.randint(1000000, 9999999)}",
                "Modelo": f"GPS-{rng.choice(['A', 'B', 'C'])}-{rng.randint(1, 5)}",
                "Tipo": "GPS",
                "Estado": "ONLINE" if online else "OFFLINE",
                "Bateria": bateria,
                "UltimaConexion": last.isoformat(),
                "Latitud": round(rng.uniform(-34.9, -34.4), 6),
                "Longitud": round(rng.uniform(-58.8, -58.2), 6),
                "Odometro": rng.randint(10000, 300000),
            })

        df = pd.DataFrame(rows)
        self.datasets['telemetria'] = df
        self.metadata['generadores_ejecutados'].append('telemetria')
        logger.info(f"✓ TELEMETRIA generada: {len(df)} dispositivos")
        return df

    def generar_consumo(self):
        """Genera tabla CONSUMO (transacciones de combustible)

        El odómetro avanza de forma monótona según los días entre cargas. Sobre esa
        base se inyectan anomalías, todas registradas en el ground truth:
        - ~7% de vehículos cargan más litros que su tanque (EXCESO_VOLUMETRICO, H3a)
        - ~1.2% de transacciones con retroceso de odómetro (ODOMETRO_REGRESIVO, H2)
        - ~1.2% de transacciones con salto de odómetro (ODOMETRO_SALTO, H2)
        - ~1% de dominios mal formados (DOMINIO_INVALIDO, H1)
        - ~2% de campos vacíos (VALOR_NULO)
        - ~1% de filas duplicadas (DUPLICADO)
        Las anomalías de odómetro persisten: las cargas siguientes continúan desde el
        valor alterado, por lo que solo la transacción anómala muestra el cambio.
        """
        logger.info("Generando CONSUMO...")
        rng = self.rng

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        productos = ["GASOIL", "NAFTA", "INFINIA", "SUPER", "GLP"]
        estaciones = ["YPF", "SHELL", "AXION", "PUMA", "ESTACION LOCAL"]

        n_anomalos = max(5, int(self.n_flota * TASA_VEHICULOS_EXCESO))
        indices_anomalos = set(rng.sample(range(len(flota_df)), min(n_anomalos, len(flota_df))))

        rows = []
        anomalias_por_id = {}
        contador_total = 0

        def registrar(row, tipo, columna, descripcion):
            self._registrar_anomalia("consumo", row["id"], row["vehiculo_id"], tipo, columna, descripcion)
            anomalias_por_id.setdefault(row["id"], []).append((tipo, columna, descripcion))

        for veh_idx, veh_row in flota_df.iterrows():
            # Cada vehículo genera 5-12 transacciones, en orden cronológico
            n_transacciones = rng.randint(5, 12)
            es_anomalo = veh_idx in indices_anomalos
            capacidad = veh_row['CapacidadTanque']
            fechas = sorted(FECHA_INICIO + timedelta(days=rng.randint(0, DIAS_VENTANA))
                            for _ in range(n_transacciones))

            odometro_real = rng.randint(10000, 250000)
            km_por_dia = rng.uniform(20, 60)
            fecha_previa = None

            for fecha in fechas:
                if fecha_previa is not None:
                    dias = (fecha - fecha_previa).days
                    odometro_real += int(km_por_dia * dias + rng.uniform(0, 30))

                # H3a: los vehículos anómalos cargan más que la capacidad del tanque
                if es_anomalo:
                    litros = round(rng.uniform(capacidad * 1.1, capacidad * 1.8), 2)
                else:
                    litros = round(rng.uniform(5, min(80, capacidad * 0.8)), 2)

                row = {
                    "id": f"CONS-{contador_total+1:08d}",
                    "vehiculo_id": veh_row['Matricula'],
                    "dominio": veh_row['Dominio'],
                    "fecha": fecha,
                    "estacion": rng.choice(estaciones),
                    "producto": rng.choice(productos),
                    "litros": litros,
                    "precio_unitario": round(rng.uniform(1.5, 3.5), 2),
                    "importe_total": 0.0,
                    "numero_tarjeta": veh_row['NumeroTarjeta'],
                    "conductor": f"CONDUCTOR-{rng.randint(1, 500)}",
                    "odometro": odometro_real,
                }
                contador_total += 1

                if es_anomalo:
                    registrar(row, "EXCESO_VOLUMETRICO", "litros",
                              f"{litros:.2f} L con tanque de {capacidad:.2f} L")

                # H2: retroceso o salto de odómetro (nunca en la primera carga)
                odometro_alterado = False
                if fecha_previa is not None:
                    r = rng.random()
                    if r < TASA_ODOMETRO_REGRESIVO:
                        retroceso = min(rng.randint(3000, 40000), odometro_real - 1000)
                        odometro_real -= retroceso
                        row["odometro"] = odometro_real
                        odometro_alterado = True
                        registrar(row, "ODOMETRO_REGRESIVO", "odometro", f"retroceso de {retroceso} km")
                    elif r < TASA_ODOMETRO_REGRESIVO + TASA_ODOMETRO_SALTO:
                        salto = rng.randint(1500, 9000)
                        odometro_real += salto
                        row["odometro"] = odometro_real
                        odometro_alterado = True
                        registrar(row, "ODOMETRO_SALTO", "odometro", f"salto de {salto} km")
                fecha_previa = fecha

                # H1: dominio mal formado
                if rng.random() < TASA_DOMINIO_INVALIDO:
                    original = row["dominio"]
                    row["dominio"] = f"XX{rng.randint(0, 999)}XX"
                    registrar(row, "DOMINIO_INVALIDO", "dominio", f"{original} registrado como {row['dominio']}")

                # Calidad: campo vacío (no se vacía un odómetro alterado, para que
                # la anomalía de H2 siga siendo observable)
                if rng.random() < TASA_NULOS:
                    candidatos = ['estacion', 'conductor'] + ([] if odometro_alterado else ['odometro'])
                    campo_nulo = rng.choice(candidatos)
                    row[campo_nulo] = None
                    registrar(row, "VALOR_NULO", campo_nulo, f"{campo_nulo} vacío")

                rows.append(row)

        # Calidad: filas duplicadas con un id nuevo
        n_duplicados = max(1, int(len(rows) * TASA_DUPLICADOS))
        for _ in range(n_duplicados):
            row_original = rng.choice(rows)
            row_copia = row_original.copy()
            row_copia['id'] = f"CONS-{contador_total+1:08d}"
            contador_total += 1
            rows.append(row_copia)
            registrar(row_copia, "DUPLICADO", "id", f"copia de {row_original['id']}")
            for tipo, columna, descripcion in anomalias_por_id.get(row_original['id'], []):
                if tipo in ANOMALIAS_HEREDABLES:
                    registrar(row_copia, tipo, columna, f"{descripcion} (heredado de {row_original['id']})")

        df = pd.DataFrame(rows)
        df['importe_total'] = (df['litros'] * df['precio_unitario']).round(2)
        df['odometro'] = df['odometro'].astype('Int64')

        self.datasets['consumo'] = df
        self.metadata['generadores_ejecutados'].append('consumo')
        logger.info(f"✓ CONSUMO generado: {len(df)} transacciones, "
                    f"{len(self.anomalias)} anomalías registradas en ground truth")
        return df

    def generar_solicitudes(self):
        """Genera tabla SOLICITUDES (solicitudes de combustible)"""
        logger.info("Generando SOLICITUDES...")
        rng = self.rng

        flota_df = self.datasets.get('flota')
        if flota_df is None:
            logger.error("FLOTA debe generarse primero")
            return None

        estados_solicitud = ["APROBADA", "PENDIENTE", "RECHAZADA", "APROBADA"]

        rows = []
        for veh_idx, veh_row in flota_df.iterrows():
            # Cada vehículo genera 1-4 solicitudes
            n_solicitudes = rng.randint(1, 4)

            for sol_idx in range(n_solicitudes):
                fecha = FECHA_INICIO + timedelta(days=rng.randint(0, DIAS_VENTANA))

                rows.append({
                    "id": f"SOL-{len(rows)+1:08d}",
                    "vehiculo_id": veh_row['Matricula'],
                    "dominio": veh_row['Dominio'],
                    "fecha_solicitud": fecha,
                    "litros_solicitados": round(rng.uniform(20, 100), 2),
                    "litros_autorizados": round(rng.uniform(20, 100), 2),
                    "estado": rng.choice(estados_solicitud),
                    "centro_costo": f"CC-{rng.randint(1, 50):03d}",
                    "responsable": f"RESP-{rng.randint(1, 100)}",
                    "observaciones": rng.choice(["OK", "REVISADO", "PENDIENTE", ""]),
                })

        df = pd.DataFrame(rows)
        self.datasets['solicitudes'] = df
        self.metadata['generadores_ejecutados'].append('solicitudes')
        logger.info(f"✓ SOLICITUDES generada: {len(df)} solicitudes")
        return df

    def generar_facturacion(self):
        """Genera tabla FACTURACION (facturas)"""
        logger.info("Generando FACTURACION...")
        rng = self.rng

        consumo_df = self.datasets.get('consumo')
        if consumo_df is None:
            logger.error("CONSUMO debe generarse primero")
            return None

        # Agrupar consumo por mes y generar facturas
        consumo_df_copy = consumo_df.copy()
        consumo_df_copy['mes'] = consumo_df_copy['fecha'].dt.to_period('M')

        rows = []
        for (mes, grupo) in consumo_df_copy.groupby('mes'):
            factura_num = f"FAC-{mes.year}{mes.month:02d}-{rng.randint(1000, 9999)}"
            total_monto = grupo['importe_total'].sum()

            rows.append({
                "numero_factura": factura_num,
                "fecha_factura": mes.end_time.date(),
                "periodo": str(mes),
                "total_litros": grupo['litros'].sum(),
                "total_monto": total_monto,
                "iva": total_monto * 0.21,
                "monto_total_con_iva": total_monto * 1.21,
                "estado": rng.choice(["PAGADA", "PENDIENTE", "VENCIDA"]),
                "numero_transacciones": len(grupo),
            })

        df = pd.DataFrame(rows)
        self.datasets['facturacion'] = df
        self.metadata['generadores_ejecutados'].append('facturacion')
        logger.info(f"✓ FACTURACION generada: {len(df)} facturas")
        return df

    # ========================================================================
    # ESCENARIO REALISTA
    #
    # Cada vehículo se simula día por día: recorre kilómetros según su perfil,
    # consume según su rendimiento y carga cuando el tanque baja de su umbral.
    # Así litros, odómetro y GPS son coherentes entre sí, y las anomalías (y los
    # casos legítimos que se les parecen) se inyectan sobre ese uso realista.
    # ========================================================================

    def _cantidad(self, clave):
        return max(1, round(EVENTOS_REALISTA[clave] * self.n_flota / 200))

    def _registrar_legitimo(self, id_registro, vehiculo_id, tipo, descripcion):
        self.casos_legitimos.append({"tabla": "consumo", "id_registro": id_registro,
                                     "vehiculo_id": vehiculo_id, "tipo_caso": tipo,
                                     "descripcion": descripcion})

    def generar_flota_realista(self):
        """FLOTA con capacidad acorde al tipo de vehículo y fecha del último cambio de estado."""
        logger.info("Generando FLOTA (escenario realista)...")
        rng = self.rng
        rows, self._perfiles = [], {}
        for i in range(1, self.n_flota + 1):
            dg_sel = rng.choice(DIRECCIONES)
            estado = rng.choice(ESTADOS_REALISTA)
            tipo = rng.choice(TIPOS_VEHICULO)
            (cap_min, cap_max), rendimiento, km_dia = PERFILES_VEHICULO[tipo]
            capacidad = round(rng.uniform(cap_min, cap_max), 1)
            fecha_estado = (None if estado == "EN SERVICIO"
                            else FECHA_INICIO + timedelta(days=rng.randint(60, DIAS_VENTANA - 20)))
            matricula = f"VEH-{i:06d}"
            rows.append({
                "Matricula": matricula,
                "Dominio": f"AB{i:04d}CD",
                "Estado": estado,
                "DireccionGral": dg_sel,
                "Dependencia": rng.choice(DEPENDENCIAS[dg_sel]),
                "Identificable": "SI" if rng.random() < 0.94 else "NO",
                "TipoVehiculo": tipo,
                "Marca": rng.choice(MARCAS),
                "Modelo": f"MODEL-{rng.randint(2010, 2024)}",
                "Año": rng.randint(2005, 2024),
                "TipoCombustible": "NAFTA" if tipo == "MOTOCICLETA" else rng.choice(COMBUSTIBLES),
                "CapacidadTanque": capacidad,
                "NumeroMotor": f"M{i:08d}",
                "NumeroChasis": f"CH{i:08d}",
                "NumeroTarjeta": f"TARJ{i:08d}",
                "LimiteSaldo": round(rng.uniform(1000, 10000), 2),
                "LimiteLitros": round(capacidad * rng.uniform(3, 6), 1),
                "SubEstado": "ACTIVO" if estado == "EN SERVICIO" else "INACTIVO",
                "FechaEstado": fecha_estado.date() if fecha_estado else None,
            })
            # Uso real del vehículo: guía la simulación pero no forma parte de los datos
            self._perfiles[matricula] = {
                "rendimiento": rng.uniform(*rendimiento),
                "km_dia": rng.uniform(*km_dia),
                "base": (rng.uniform(*ZONA_BASE["lat"]), rng.uniform(*ZONA_BASE["lon"])),
                "umbral_carga": rng.uniform(0.15, 0.35),
            }

        df = pd.DataFrame(rows)
        self.datasets['flota'] = df
        self.metadata['generadores_ejecutados'].append('flota')
        logger.info(f"✓ FLOTA generada: {len(df)} vehículos")
        return df

    def generar_estaciones(self):
        """ESTACIONES con coordenadas: locales en la zona de operación y otras sobre rutas."""
        logger.info("Generando ESTACIONES...")
        rng = self.rng
        rows = []
        for _ in range(N_ESTACIONES_LOCALES):
            rows.append({
                "codigo": f"EST-{len(rows) + 1:03d}",
                "marca": rng.choice(MARCAS_ESTACION),
                "ubicacion": "LOCAL",
                "latitud": round(rng.uniform(*ZONA_BASE["lat"]), 5),
                "longitud": round(rng.uniform(*ZONA_BASE["lon"]), 5),
            })

        centro = (sum(ZONA_BASE["lat"]) / 2, sum(ZONA_BASE["lon"]) / 2)
        self._destinos = []
        while len(self._destinos) < N_RUTAS:
            destino = (centro[0] + rng.uniform(-4, 3.5), centro[1] + rng.uniform(-6.5, -1.5))
            if distancia_km(*centro, *destino) >= 250:
                self._destinos.append(destino)
        for destino in self._destinos:
            for fraccion in FRACCIONES_RUTA:
                lat, lon = _interpolar(centro, destino, fraccion)
                rows.append({
                    "codigo": f"EST-{len(rows) + 1:03d}",
                    "marca": rng.choice(MARCAS_ESTACION),
                    "ubicacion": "RUTA",
                    "latitud": round(lat + rng.uniform(-0.05, 0.05), 5),
                    "longitud": round(lon + rng.uniform(-0.05, 0.05), 5),
                })

        self._coords_estaciones = [(r["codigo"], r["latitud"], r["longitud"], r["ubicacion"]) for r in rows]
        self._ubicacion_estacion = {r["codigo"]: r["ubicacion"] for r in rows}
        df = pd.DataFrame(rows)
        self.datasets['estaciones'] = df
        self.metadata['generadores_ejecutados'].append('estaciones')
        logger.info(f"✓ ESTACIONES generadas: {len(df)}")
        return df

    def _estacion_cercana(self, pos, excluir=None, solo=None):
        """Una de las tres estaciones más cercanas a una posición."""
        candidatas = sorted(
            (distancia_km(pos[0], pos[1], lat, lon), codigo)
            for codigo, lat, lon, ubicacion in self._coords_estaciones
            if codigo != excluir and (solo is None or ubicacion == solo)
        )
        return self.rng.choice(candidatas[:3])[1]

    def _asignar_roles(self, vehiculos, con_gps):
        """Elige qué vehículos protagonizan cada anomalía o caso legítimo (a lo sumo uno cada uno)."""
        rng = self.rng
        roles = {}

        def asignar(rol, candidatos):
            libres = [m for m in candidatos if m not in roles]
            for m in rng.sample(libres, min(self._cantidad(rol), len(libres))):
                roles[m] = rol

        en_servicio = [v["Matricula"] for v in vehiculos if v["Estado"] == "EN SERVICIO"]
        tipo = {v["Matricula"]: v["TipoVehiculo"] for v in vehiculos}
        asignar("TANQUE_AUXILIAR", [m for m in en_servicio
                                    if tipo[m] in ("CAMION", "BOMBERO", "PICK-UP", "CAMIONETA")])
        asignar("EXCESO_VOLUMETRICO", en_servicio)
        asignar("RENDIMIENTO_IMPOSIBLE", en_servicio)
        asignar("VIAJE_LARGO", en_servicio)
        asignar("FRACCIONAMIENTO", en_servicio)
        asignar("CARGA_FUERA_DE_ZONA", [m for m in en_servicio if m in con_gps])
        limite = (FECHA_REFERENCIA - timedelta(days=20)).date()
        asignar("CARGA_VEHICULO_INACTIVO", [v["Matricula"] for v in vehiculos
                                            if v["Estado"] != "EN SERVICIO" and v["FechaEstado"] <= limite])
        return roles

    def _simular_vehiculo(self, v, rol, cargas, gps):
        """Simula el uso diario de un vehículo y agrega sus cargas y sus registros de GPS."""
        rng = self.rng
        m = v["Matricula"]
        perfil = self._perfiles[m]
        cap_reg = v["CapacidadTanque"]
        cap_real = cap_reg * rng.uniform(1.3, 1.6) if rol == "TANQUE_AUXILIAR" else cap_reg
        base = perfil["base"]
        fin_activo = datetime.combine(v["FechaEstado"], datetime.min.time()) if v["FechaEstado"] else None
        productos = PRODUCTOS_POR_COMBUSTIBLE[v["TipoCombustible"]]
        odo = float(rng.randint(10000, 250000))
        combustible = cap_real * rng.uniform(0.4, 0.9)
        dia_inicio_fraude = rng.randint(90, 200)

        viaje = (rng.randint(30, DIAS_VENTANA - 10), rng.choice(self._destinos)) if rol == "VIAJE_LARGO" else None
        dias_inactivo = set()
        if rol == "CARGA_VEHICULO_INACTIVO":
            desde = (fin_activo - FECHA_INICIO).days + 5
            dias_inactivo = set(rng.sample(range(desde, DIAS_VENTANA + 1), rng.randint(1, 3)))
        dia_fuera_de_zona = rng.randint(30, DIAS_VENTANA) if rol == "CARGA_FUERA_DE_ZONA" else None
        cargas_sin_uso = rng.randint(3, 6) if rol == "RENDIMIENTO_IMPOSIBLE" else 0
        fraccionado = False

        def registrar(fecha, estacion, litros, odometro, etiqueta=None, legitimo=None):
            cargas.append({
                "vehiculo_id": m, "dominio": v["Dominio"], "fecha": fecha, "estacion": estacion,
                "producto": rng.choice(productos), "litros": round(litros, 2),
                "numero_tarjeta": v["NumeroTarjeta"], "conductor": f"CONDUCTOR-{rng.randint(1, 500)}",
                "_odo_real": odometro, "_etiqueta": etiqueta, "_legitimo": legitimo,
                "_capacidad": cap_reg, "_orden": len(cargas),
            })

        def cargar(fecha, pos, dia):
            nonlocal combustible, fraccionado
            if rng.random() < PROB_CARGA_PARCIAL:
                objetivo = cap_real * rng.uniform(0.6, 0.9)
            else:
                objetivo = cap_real * rng.uniform(0.95, 1.0)
            al_tanque = max(objetivo - combustible, 0.08 * cap_real)
            litros, etiqueta, legitimo = al_tanque, None, None
            estacion = self._estacion_cercana(pos)
            if rol == "TANQUE_AUXILIAR":
                legitimo = "TANQUE_AUXILIAR"
            elif rol == "VIAJE_LARGO" and self._ubicacion_estacion[estacion] == "RUTA":
                legitimo = "VIAJE_LARGO"
            elif rol == "EXCESO_VOLUMETRICO" and dia >= dia_inicio_fraude and rng.random() < 0.3:
                # Se factura más de lo que entra en el tanque; el excedente no llega al vehículo
                litros = max(litros, cap_reg * rng.uniform(1.05, 1.4))
                etiqueta = "EXCESO_VOLUMETRICO"
            fraccionar = rol == "FRACCIONAMIENTO" and not fraccionado and dia >= 30 and rng.random() < 0.3
            if fraccionar:
                etiqueta = "FRACCIONAMIENTO"
            registrar(fecha, estacion, litros, odo, etiqueta, legitimo)
            combustible += al_tanque

            if fraccionar:
                # Cargas adicionales el mismo día en otras estaciones: cada una parece normal,
                # pero entre todas superan el tanque. El combustible extra no llega al vehículo.
                fraccionado = True
                total = litros
                lectura = odo
                extras = rng.randint(1, 2)
                for k in range(extras):
                    extra = cap_reg * rng.uniform(0.4, 0.7)
                    if k == extras - 1 and total + extra <= 1.1 * cap_reg:
                        extra = 1.1 * cap_reg - total + cap_reg * rng.uniform(0.05, 0.2)
                    total += extra
                    lectura += rng.uniform(0.5, 5)  # la estación siguiente queda a pocos km
                    registrar(fecha, self._estacion_cercana(pos, excluir=estacion), extra,
                              lectura, "FRACCIONAMIENTO")

        for dia in range(DIAS_VENTANA + 1):
            fecha = FECHA_INICIO + timedelta(days=dia)
            activo = fin_activo is None or fecha < fin_activo
            origen = destino = base
            km = 0.0
            if viaje and dia == viaje[0]:
                destino = viaje[1]
                km = distancia_km(*base, *destino) * 1.2
            elif viaje and dia == viaje[0] + 1:
                origen = destino = viaje[1]
                km = rng.uniform(20, 80)
            elif viaje and dia == viaje[0] + 2:
                origen, destino = viaje[1], base
                km = distancia_km(*base, *viaje[1]) * 1.2
            elif activo and rng.random() >= PROB_DIA_SIN_USO:
                km = perfil["km_dia"] * rng.uniform(0.5, 1.5)

            cargas_previas = len(cargas)
            rendimiento_dia = perfil["rendimiento"] * rng.uniform(0.9, 1.1)
            recorrido = 0.0
            while km - recorrido > 1e-6:
                tramo = min(km - recorrido, max(combustible - RESERVA_TANQUE * cap_real, 0) * rendimiento_dia)
                combustible -= tramo / rendimiento_dia
                odo += tramo
                recorrido += tramo
                if km - recorrido > 1e-6:  # llegó a la reserva a mitad de camino
                    cargar(fecha, _interpolar(origen, destino, recorrido / km), dia)
            if activo and combustible < perfil["umbral_carga"] * cap_real:
                cargar(fecha, destino, dia)
            hubo_carga = len(cargas) > cargas_previas

            # Cargas que no llegan al tanque del vehículo: el combustible no cambia
            if (cargas_sin_uso and activo and dia >= dia_inicio_fraude and not hubo_carga
                    and combustible > 0.7 * cap_real and rng.random() < 0.15):
                registrar(fecha, self._estacion_cercana(base, solo="LOCAL"),
                          cap_reg * rng.uniform(0.8, 0.95), odo, "RENDIMIENTO_IMPOSIBLE")
                cargas_sin_uso -= 1
            if dia in dias_inactivo:
                registrar(fecha, self._estacion_cercana(base, solo="LOCAL"),
                          cap_reg * rng.uniform(0.5, 0.9), odo, "CARGA_VEHICULO_INACTIVO")
            if dia == dia_fuera_de_zona:
                lejanas = [codigo for codigo, lat, lon, _ in self._coords_estaciones
                           if distancia_km(*base, lat, lon) > 100]
                registrar(fecha, rng.choice(lejanas), cap_reg * rng.uniform(0.5, 0.9), odo, "CARGA_FUERA_DE_ZONA")

            if m in self._con_gps and rng.random() >= TASA_DIAS_SIN_SENAL:
                gps.append({
                    "Placa": v["Dominio"],
                    "fecha": fecha.date(),
                    "km_gps": round(km * rng.uniform(0.97, 1.03), 1),
                    "lat_inicio": round(origen[0] + rng.uniform(-0.01, 0.01), 5),
                    "lon_inicio": round(origen[1] + rng.uniform(-0.01, 0.01), 5),
                    "lat_fin": round(destino[0] + rng.uniform(-0.01, 0.01), 5),
                    "lon_fin": round(destino[1] + rng.uniform(-0.01, 0.01), 5),
                })
        self._odometro_final[m] = odo

    def _alterar_odometros(self, por_vehiculo, roles):
        """Adulteraciones de odómetro (anomalías) y cambios o errores de lectura (legítimos).

        Retrocesos y saltos se miden contra la lectura anterior y persisten: las cargas
        siguientes continúan desde el valor alterado. El error de tipeo afecta una sola
        lectura; el cambio de odómetro reinicia la cuenta desde un valor bajo.
        """
        rng = self.rng
        candidatos = sorted(m for m, lista in por_vehiculo.items() if m not in roles and len(lista) >= 6)
        eventos = {}
        for tipo in ["ODOMETRO_REGRESIVO", "ODOMETRO_REGRESIVO_LEVE", "ODOMETRO_SALTO",
                     "CAMBIO_ODOMETRO", "ERROR_TIPEO_ODOMETRO"]:
            libres = [m for m in candidatos if m not in eventos]
            for m in rng.sample(libres, min(self._cantidad(tipo), len(libres))):
                eventos[m] = (tipo, rng.randint(2, len(por_vehiculo[m]) - 2))

        for m, lista in por_vehiculo.items():
            tipo, posicion = eventos.get(m, (None, None))
            desplazamiento = 0
            anterior = None
            for j, c in enumerate(lista):
                lectura = int(round(c["_odo_real"])) + desplazamiento
                if j == posicion:
                    if tipo == "ODOMETRO_REGRESIVO":
                        nueva = max(anterior - rng.randint(3000, 40000), 500)
                        c.update(_etiqueta=tipo, _detalle=f"retroceso de {anterior - nueva} km")
                    elif tipo == "ODOMETRO_REGRESIVO_LEVE":
                        nueva = anterior - rng.randint(50, 200)
                        c.update(_etiqueta=tipo, _detalle=f"retroceso de {anterior - nueva} km")
                    elif tipo == "ODOMETRO_SALTO":
                        nueva = lectura + rng.randint(1500, 9000)
                        c.update(_etiqueta=tipo, _detalle=f"salto de {nueva - lectura} km")
                    elif tipo == "CAMBIO_ODOMETRO":
                        nueva = rng.randint(0, 3000)
                        c.update(_legitimo=tipo, _detalle=f"odómetro nuevo desde {nueva} km")
                    else:  # ERROR_TIPEO_ODOMETRO: una sola lectura, no cambia las siguientes
                        c["odometro"] = _error_de_tipeo(lectura, rng)
                        c.update(_legitimo=tipo, _detalle=f"{lectura} registrado como {c['odometro']}")
                        anterior = lectura
                        continue
                    desplazamiento += nueva - lectura
                    lectura = nueva
                c["odometro"] = lectura
                anterior = lectura

    def _defectos_de_calidad(self, cargas, siguiente_id):
        """Dominios inválidos, nulos y duplicados, solo sobre cargas sin otra anomalía."""
        rng = self.rng
        n = len(cargas)
        limpias = [c for c in cargas if not c["_etiqueta"] and not c["_legitimo"]]
        rng.shuffle(limpias)
        n_dominio = round(n * TASAS_CALIDAD_REALISTA["DOMINIO_INVALIDO"])
        n_nulos = round(n * TASAS_CALIDAD_REALISTA["VALOR_NULO"])
        n_duplicados = round(n * TASAS_CALIDAD_REALISTA["DUPLICADO"])

        for c in limpias[:n_dominio]:
            original = c["dominio"]
            c["dominio"] = f"XX{rng.randint(0, 999)}XX"
            self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], "DOMINIO_INVALIDO", "dominio",
                                     f"{original} registrado como {c['dominio']}")
        for c in limpias[n_dominio:n_dominio + n_nulos]:
            campo = rng.choice(["estacion", "conductor", "odometro"])
            c[campo] = None
            self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], "VALOR_NULO", campo, f"{campo} vacío")
        copias = []
        for c in limpias[n_dominio + n_nulos:n_dominio + n_nulos + n_duplicados]:
            copia = dict(c, id=f"CONS-{siguiente_id:08d}")
            siguiente_id += 1
            copias.append(copia)
            self._registrar_anomalia("consumo", copia["id"], copia["vehiculo_id"], "DUPLICADO", "id",
                                     f"copia de {c['id']}")
        return copias

    def generar_consumo_realista(self):
        """CONSUMO, TELEMETRIA y TELEMETRIA_DIARIA a partir de la simulación de la flota."""
        logger.info("Simulando el uso diario de la flota (escenario realista)...")
        rng = self.rng
        vehiculos = self.datasets['flota'].to_dict("records")
        matriculas = [v["Matricula"] for v in vehiculos]
        self._con_gps = set(rng.sample(matriculas, int(len(matriculas) * COBERTURA_GPS)))
        self._odometro_final = {}
        roles = self._asignar_roles(vehiculos, self._con_gps)

        cargas, gps = [], []
        for v in vehiculos:
            self._simular_vehiculo(v, roles.get(v["Matricula"]), cargas, gps)

        cargas.sort(key=lambda c: (c["vehiculo_id"], c["fecha"], c["_orden"]))
        por_vehiculo = {}
        for i, c in enumerate(cargas, 1):
            c["id"] = f"CONS-{i:08d}"
            por_vehiculo.setdefault(c["vehiculo_id"], []).append(c)
        self._alterar_odometros(por_vehiculo, roles)

        columnas_etiqueta = {
            "EXCESO_VOLUMETRICO": "litros", "FRACCIONAMIENTO": "litros", "RENDIMIENTO_IMPOSIBLE": "litros",
            "CARGA_VEHICULO_INACTIVO": "fecha", "CARGA_FUERA_DE_ZONA": "estacion",
        }
        for c in cargas:
            meses = (c["fecha"].year - FECHA_INICIO.year) * 12 + c["fecha"].month - FECHA_INICIO.month
            c["precio_unitario"] = round(PRECIO_BASE[c["producto"]] * (1 + AUMENTO_MENSUAL_PRECIO * meses)
                                         * rng.uniform(0.98, 1.02), 2)
            c["importe_total"] = round(c["litros"] * c["precio_unitario"], 2)
            if c["_etiqueta"]:
                tipo = c["_etiqueta"]
                detalle = c.get("_detalle") or {
                    "EXCESO_VOLUMETRICO": f"{c['litros']:.2f} L con tanque de {c['_capacidad']:.1f} L",
                    "FRACCIONAMIENTO": "carga repartida en el mismo día",
                    "RENDIMIENTO_IMPOSIBLE": f"{c['litros']:.2f} L sin recorrido que los justifique",
                    "CARGA_VEHICULO_INACTIVO": "carga posterior a la baja o salida de servicio",
                    "CARGA_FUERA_DE_ZONA": f"carga en {c['estacion']}, lejos de la ubicación del vehículo",
                }[tipo]
                self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], tipo,
                                         columnas_etiqueta.get(tipo, "odometro"), detalle)
            if c["_legitimo"]:
                self._registrar_legitimo(c["id"], c["vehiculo_id"], c["_legitimo"],
                                         c.get("_detalle") or CATALOGO_LEGITIMOS[c["_legitimo"]])

        # Estación de cada carga antes de los defectos de calidad: el proveedor factura
        # con la estación real aunque en nuestro registro quede vacía
        self._estacion_real = {c["id"]: c["estacion"] for c in cargas}
        cargas += self._defectos_de_calidad(cargas, siguiente_id=len(cargas) + 1)

        columnas = ["id", "vehiculo_id", "dominio", "fecha", "estacion", "producto", "litros",
                    "precio_unitario", "importe_total", "numero_tarjeta", "conductor", "odometro"]
        df = pd.DataFrame(cargas)[columnas]
        df['odometro'] = df['odometro'].astype('Int64')
        self.datasets['consumo'] = df
        self.metadata['generadores_ejecutados'].append('consumo')

        self._generar_telemetria_realista(vehiculos, gps)
        logger.info(f"✓ CONSUMO generado: {len(df)} transacciones, {len(self.anomalias)} anomalías y "
                    f"{len(self.casos_legitimos)} casos legítimos registrados")
        return df

    def _generar_telemetria_realista(self, vehiculos, gps):
        """Un dispositivo por vehículo con GPS y su registro diario de recorrido."""
        rng = self.rng
        rows = []
        for i, v in enumerate([v for v in vehiculos if v["Matricula"] in self._con_gps], 1):
            online = v["Estado"] == "EN SERVICIO" and rng.random() < 0.95
            base = self._perfiles[v["Matricula"]]["base"]
            minutos = rng.randint(0, 15) if online else rng.randint(60, 600)
            rows.append({
                "IMEI": f"{rng.randint(350000000000000, 359999999999999)}",
                "Alias": f"DEV-{i:06d}",
                "Placa": v["Dominio"],
                "MSISDN": f"54911{rng.randint(1000000, 9999999)}",
                "Modelo": f"GPS-{rng.choice(['A', 'B', 'C'])}-{rng.randint(1, 5)}",
                "Tipo": "GPS",
                "Estado": "ONLINE" if online else "OFFLINE",
                "Bateria": round(rng.uniform(20, 100), 1),
                "UltimaConexion": (FECHA_REFERENCIA - timedelta(minutes=minutos)).isoformat(),
                "Latitud": round(base[0], 6),
                "Longitud": round(base[1], 6),
                "Odometro": int(round(self._odometro_final[v["Matricula"]])),
            })
        self.datasets['telemetria'] = pd.DataFrame(rows)
        self.datasets['telemetria_diaria'] = pd.DataFrame(gps)
        self.metadata['generadores_ejecutados'] += ['telemetria', 'telemetria_diaria']
        logger.info(f"✓ TELEMETRIA generada: {len(rows)} dispositivos, {len(gps)} registros diarios")

    def _cargas_facturables(self):
        """Cargas reales: sin los duplicados, que son un defecto de nuestro registro."""
        consumo = self.datasets['consumo']
        duplicadas = {a["id_registro"] for a in self.anomalias if a["tipo_anomalia"] == "DUPLICADO"}
        return consumo[~consumo["id"].isin(duplicadas)]

    def _repartir(self, candidatos, roles):
        """Asigna a cada rol una cantidad de candidatos distintos (según EVENTOS_REALISTA)."""
        candidatos = list(candidatos)
        self.rng.shuffle(candidatos)
        asignacion, posicion = {}, 0
        for rol in roles:
            n = self._cantidad(rol)
            for candidato in candidatos[posicion:posicion + n]:
                asignacion[candidato] = rol
            posicion += n
        return asignacion

    def generar_solicitudes_realista(self):
        """SOLICITUDES coherentes con el consumo: cada carga tiene su solicitud aprobada.

        La solicitud se aprueba entre 0 y 2 días antes de la carga por algo más de los
        litros cargados. Se inyectan cargas sin solicitud, con solicitud rechazada o por
        encima de lo autorizado, y casos legítimos: regularizaciones posteriores y
        diferencias dentro de la tolerancia de medición. Además hay solicitudes
        rechazadas o pendientes que no terminan en carga.
        """
        logger.info("Generando SOLICITUDES (escenario realista)...")
        rng = self.rng
        cargas = self._cargas_facturables()
        dominio = self.datasets['flota'].set_index("Matricula")["Dominio"]
        etiquetadas = ({a["id_registro"] for a in self.anomalias}
                       | {c["id_registro"] for c in self.casos_legitimos})
        asignacion = self._repartir(
            [i for i in cargas["id"] if i not in etiquetadas],
            ["CARGA_SIN_SOLICITUD", "CARGA_CON_SOLICITUD_RECHAZADA", "CARGA_SUPERA_AUTORIZADO",
             "REGULARIZACION_POSTERIOR", "TOLERANCIA_MEDICION"])

        rows = []

        def solicitar(vehiculo, fecha, solicitados, autorizados, estado, observaciones=""):
            rows.append({
                "vehiculo_id": vehiculo, "dominio": dominio[vehiculo], "fecha_solicitud": fecha,
                "litros_solicitados": round(solicitados, 2), "litros_autorizados": round(autorizados, 2),
                "estado": estado, "centro_costo": f"CC-{rng.randint(1, 50):03d}",
                "responsable": f"RESP-{rng.randint(1, 100)}", "observaciones": observaciones,
            })

        for c in cargas.itertuples():
            rol = asignacion.get(c.id)
            fecha = pd.Timestamp(c.fecha).to_pydatetime()
            if rol == "CARGA_SIN_SOLICITUD":
                self._registrar_anomalia("consumo", c.id, c.vehiculo_id, rol, "solicitud",
                                         "carga sin ninguna solicitud del vehículo")
                continue
            previa = fecha - timedelta(days=rng.randint(0, 2))
            solicitados = c.litros * rng.uniform(1.0, 1.25)
            if rol == "CARGA_CON_SOLICITUD_RECHAZADA":
                solicitar(c.vehiculo_id, previa, solicitados, 0.0, "RECHAZADA", "RECHAZADA POR SUPERVISOR")
                self._registrar_anomalia("consumo", c.id, c.vehiculo_id, rol, "solicitud",
                                         "la única solicitud cercana fue rechazada")
                continue
            if rol == "REGULARIZACION_POSTERIOR":
                solicitar(c.vehiculo_id, fecha + timedelta(days=rng.randint(1, 3)), solicitados, solicitados,
                          "APROBADA", "REGULARIZACION")
                self._registrar_legitimo(c.id, c.vehiculo_id, rol, CATALOGO_LEGITIMOS[rol])
                continue
            if rng.random() < 0.8:
                autorizados = solicitados
            else:
                autorizados = max(c.litros, solicitados * rng.uniform(0.85, 1.0))
            if rol == "CARGA_SUPERA_AUTORIZADO":
                autorizados = c.litros / rng.uniform(1.15, 1.5)
                self._registrar_anomalia("consumo", c.id, c.vehiculo_id, rol, "litros",
                                         f"{c.litros:.2f} L con {autorizados:.2f} L autorizados")
            elif rol == "TOLERANCIA_MEDICION":
                autorizados = c.litros / rng.uniform(1.01, 1.03)
                self._registrar_legitimo(c.id, c.vehiculo_id, rol,
                                         f"{c.litros:.2f} L con {autorizados:.2f} L autorizados")
            solicitar(c.vehiculo_id, previa, solicitados, autorizados, "APROBADA",
                      rng.choice(["OK", "REVISADO", ""]))

        vehiculos = list(dominio.index)
        for _ in range(round(len(cargas) * TASA_SOLICITUDES_SIN_CARGA)):
            estado = rng.choice(["RECHAZADA", "PENDIENTE"])
            solicitar(rng.choice(vehiculos), FECHA_INICIO + timedelta(days=rng.randint(0, DIAS_VENTANA)),
                      rng.uniform(10, 80), 0.0, estado, "SIN CUPO DISPONIBLE" if estado == "RECHAZADA" else "")

        rows.sort(key=lambda r: (r["vehiculo_id"], r["fecha_solicitud"]))
        for i, r in enumerate(rows, 1):
            r["id"] = f"SOL-{i:08d}"
        columnas = ["id", "vehiculo_id", "dominio", "fecha_solicitud", "litros_solicitados", "litros_autorizados",
                    "estado", "centro_costo", "responsable", "observaciones"]
        df = pd.DataFrame(rows)[columnas]
        self.datasets['solicitudes'] = df
        self.metadata['generadores_ejecutados'].append('solicitudes')
        logger.info(f"✓ SOLICITUDES generada: {len(df)} solicitudes")
        return df

    def generar_facturacion_realista(self):
        """FACTURACION por proveedor y mes, con su detalle línea por línea.

        Cada proveedor (marca de estación) emite una factura mensual; cada línea
        referencia una carga. Se inyectan líneas sin carga real, líneas duplicadas,
        sobreprecios y totales inflados, y casos legítimos: cargas del último día del
        mes facturadas en el período siguiente y facturas con un ajuste documentado.
        """
        logger.info("Generando FACTURACION (escenario realista)...")
        rng = self.rng
        cargas = self._cargas_facturables().copy()
        marca = self.datasets['estaciones'].set_index("codigo")["marca"]
        dominio = self.datasets['flota'].set_index("Matricula")["Dominio"]
        cargas["fecha"] = pd.to_datetime(cargas["fecha"])
        cargas["proveedor"] = cargas["id"].map(self._estacion_real).map(marca)
        cargas = cargas.sort_values(["fecha", "id"])

        lineas = []
        for c in cargas.itertuples():
            periodo = c.fecha.to_period("M")
            desfase = c.fecha.is_month_end and rng.random() < PROB_DESFASE_DE_CORTE
            lineas.append({
                "periodo": periodo + 1 if desfase else periodo, "proveedor": c.proveedor,
                "referencia_consumo": c.id, "concepto": "COMBUSTIBLE", "fecha": c.fecha.date(),
                "dominio": dominio[c.vehiculo_id], "litros": c.litros, "precio_unitario": c.precio_unitario,
                "importe": c.importe_total, "descripcion": "", "_etiqueta": None,
                "_legitimo": "DESFASE_DE_CORTE" if desfase else None, "_vehiculo": c.vehiculo_id,
            })

        # Irregularidades por línea, sobre líneas sin otro caso
        limpias = [i for i, linea in enumerate(lineas) if not linea["_legitimo"]]
        asignacion = self._repartir(limpias, ["SOBREPRECIO", "LINEA_DUPLICADA", "LINEA_SIN_CONSUMO"])
        extras = []
        for i, rol in sorted(asignacion.items()):
            linea = lineas[i]
            if rol == "SOBREPRECIO":
                original = linea["precio_unitario"]
                linea["precio_unitario"] = round(original * rng.uniform(1.08, 1.2), 2)
                linea["importe"] = round(linea["litros"] * linea["precio_unitario"], 2)
                linea["_etiqueta"] = ("SOBREPRECIO",
                                      f"{linea['precio_unitario']} por litro; en la carga, {original}")
            elif rol == "LINEA_DUPLICADA":
                extras.append(dict(linea, _etiqueta=("LINEA_DUPLICADA",
                                                     f"{linea['referencia_consumo']} facturada dos veces")))
            else:  # LINEA_SIN_CONSUMO: una carga que nunca ocurrió, con datos verosímiles
                inexistente = f"CONS-9{rng.randint(0, 9999999):07d}"
                litros = round(linea["litros"] * rng.uniform(0.8, 1.2), 2)
                extras.append(dict(linea, referencia_consumo=inexistente, litros=litros,
                                   importe=round(litros * linea["precio_unitario"], 2),
                                   _etiqueta=("LINEA_SIN_CONSUMO",
                                              f"{inexistente} no existe en el registro de cargas")))
        lineas += extras

        # Ajustes documentados en algunas facturas (legítimos)
        grupos = sorted({(linea["periodo"], linea["proveedor"]) for linea in lineas})
        subtotal = {}
        for linea in lineas:
            clave = (linea["periodo"], linea["proveedor"])
            subtotal[clave] = subtotal.get(clave, 0) + linea["importe"]
        for periodo, proveedor in rng.sample(grupos, min(self._cantidad("AJUSTE_DOCUMENTADO"), len(grupos))):
            signo = rng.choice([-1, 1])
            lineas.append({
                "periodo": periodo, "proveedor": proveedor, "referencia_consumo": None, "concepto": "AJUSTE",
                "fecha": periodo.end_time.date(), "dominio": None, "litros": 0.0, "precio_unitario": 0.0,
                "importe": round(signo * subtotal[(periodo, proveedor)] * rng.uniform(0.02, 0.05), 2),
                "descripcion": "BONIFICACION POR VOLUMEN" if signo < 0 else "RECARGO POR SERVICIO NOCTURNO",
                "_etiqueta": None, "_legitimo": "AJUSTE_DOCUMENTADO", "_vehiculo": None,
            })

        # Numeración y encabezados
        codigo = {g: f"FAC-{g[0].strftime('%Y%m')}-{g[1].replace(' ', '')[:3].upper()}-{rng.randint(1000, 9999)}"
                  for g in grupos}
        lineas.sort(key=lambda linea: (linea["periodo"], linea["proveedor"], linea["concepto"] != "COMBUSTIBLE",
                                       str(linea["fecha"]), str(linea["referencia_consumo"])))
        for i, linea in enumerate(lineas, 1):
            linea["numero_linea"] = f"LIN-{i:08d}"
            linea["numero_factura"] = codigo[(linea["periodo"], linea["proveedor"])]
            if linea["_etiqueta"]:
                tipo, detalle = linea["_etiqueta"]
                columna = {"SOBREPRECIO": "precio_unitario"}.get(tipo, "referencia_consumo")
                self._registrar_anomalia("facturacion_detalle", linea["numero_linea"], linea["_vehiculo"],
                                         tipo, columna, detalle)
            if linea["_legitimo"] == "DESFASE_DE_CORTE":
                self.casos_legitimos.append({
                    "tabla": "facturacion_detalle", "id_registro": linea["numero_linea"],
                    "vehiculo_id": linea["_vehiculo"], "tipo_caso": "DESFASE_DE_CORTE",
                    "descripcion": f"carga del {linea['fecha']} facturada en {linea['periodo']}"})
            elif linea["_legitimo"] == "AJUSTE_DOCUMENTADO":
                self.casos_legitimos.append({
                    "tabla": "facturacion", "id_registro": linea["numero_factura"], "vehiculo_id": None,
                    "tipo_caso": "AJUSTE_DOCUMENTADO", "descripcion": f"{linea['descripcion']}: {linea['importe']}"})

        facturas = []
        for grupo in grupos:
            propias = [linea for linea in lineas if (linea["periodo"], linea["proveedor"]) == grupo]
            combustible = [linea for linea in propias if linea["concepto"] == "COMBUSTIBLE"]
            facturas.append({
                "numero_factura": codigo[grupo], "proveedor": grupo[1],
                "fecha_factura": grupo[0].end_time.date(), "periodo": str(grupo[0]),
                "total_litros": round(sum(x["litros"] for x in combustible), 2),
                "total_monto": round(sum(x["importe"] for x in propias), 2),
                "estado": rng.choice(["PAGADA", "PENDIENTE", "VENCIDA"]),
                "numero_transacciones": len(combustible),
            })
        for factura in rng.sample(facturas, min(self._cantidad("TOTAL_INFLADO"), len(facturas))):
            real = factura["total_monto"]
            factura["total_monto"] = round(real * rng.uniform(1.03, 1.10), 2)
            self._registrar_anomalia("facturacion", factura["numero_factura"], None, "TOTAL_INFLADO",
                                     "total_monto", f"total {factura['total_monto']} con líneas por {real}")
        for factura in facturas:
            factura["iva"] = round(factura["total_monto"] * 0.21, 2)
            factura["monto_total_con_iva"] = round(factura["total_monto"] * 1.21, 2)

        columnas_factura = ["numero_factura", "proveedor", "fecha_factura", "periodo", "total_litros",
                            "total_monto", "iva", "monto_total_con_iva", "estado", "numero_transacciones"]
        columnas_linea = ["numero_linea", "numero_factura", "referencia_consumo", "concepto", "fecha", "dominio",
                          "litros", "precio_unitario", "importe", "descripcion"]
        self.datasets['facturacion'] = pd.DataFrame(facturas)[columnas_factura]
        self.datasets['facturacion_detalle'] = pd.DataFrame(lineas)[columnas_linea]
        self.metadata['generadores_ejecutados'] += ['facturacion', 'facturacion_detalle']
        logger.info(f"✓ FACTURACION generada: {len(facturas)} facturas, {len(lineas)} líneas")
        return self.datasets['facturacion']

    def construir_ground_truth(self):
        """Tabla con una fila por anomalía inyectada (un registro puede tener varias)."""
        return pd.DataFrame(self.anomalias, columns=COLUMNAS_GROUND_TRUTH)

    def construir_casos_legitimos(self):
        """Casos que se parecen a una anomalía pero no lo son (solo escenario realista)."""
        return pd.DataFrame(self.casos_legitimos, columns=COLUMNAS_CASOS_LEGITIMOS)

    def guardar_datasets(self):
        """Guarda todos los datasets en CSV"""
        logger.info("Guardando datasets...")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        archivos = {}
        for nombre, df in self.datasets.items():
            filepath = self.output_dir / f"{nombre}.csv"
            df.to_csv(filepath, index=False)
            archivos[nombre] = str(filepath)
            logger.info(f"  ✓ {nombre}.csv guardado ({len(df)} filas)")

        # La verdad de referencia va aparte: no forma parte de las entidades
        ground_truth = self.construir_ground_truth()
        gt_file = self.output_dir / "ground_truth.csv"
        ground_truth.to_csv(gt_file, index=False)
        logger.info(f"  ✓ ground_truth.csv guardado ({len(ground_truth)} anomalías)")
        if self.escenario == "realista":
            legitimos = self.construir_casos_legitimos()
            legitimos_file = self.output_dir / "casos_legitimos.csv"
            legitimos.to_csv(legitimos_file, index=False)
            self.metadata['casos_legitimos'] = str(legitimos_file)
            self.metadata['casos_legitimos_por_tipo'] = legitimos['tipo_caso'].value_counts().to_dict()
            logger.info(f"  ✓ casos_legitimos.csv guardado ({len(legitimos)} casos)")

        # Diccionario de datos del escenario, con exactamente las columnas escritas
        columnas = {nombre: list(df.columns) for nombre, df in self.datasets.items()}
        columnas["ground_truth"] = list(ground_truth.columns)
        if self.escenario == "realista":
            columnas["casos_legitimos"] = COLUMNAS_CASOS_LEGITIMOS
        diccionario_file = self.output_dir / "diccionario.json"
        with open(diccionario_file, 'w', encoding='utf-8') as f:
            json.dump(diccionario_de_datos(self.escenario, columnas), f, indent=2, ensure_ascii=False)
        self.metadata['diccionario'] = str(diccionario_file)

        # Guardar metadatos
        metadata_file = self.output_dir / "metadata.json"
        self.metadata['archivos'] = archivos
        self.metadata['ground_truth'] = str(gt_file)
        self.metadata['anomalias_por_tipo'] = ground_truth['tipo_anomalia'].value_counts().to_dict()
        self.metadata['directorio_salida'] = str(self.output_dir)

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, default=str, ensure_ascii=False)

        logger.info(f"✓ Metadatos guardados en {metadata_file}")
        return archivos

    def aplicar_formatos_de_origen(self):
        """Realista: dominios escritos de otra forma y fechas en dos formatos.

        No son anomalías sino cómo llegan los datos de cada fuente. Un dominio con espacios,
        guiones o minúsculas corresponde igual al vehículo: es un caso legítimo que la
        vinculación exacta confunde con un dominio inválido (H1). Las fechas de solicitudes
        en DD/MM/AAAA obligan a interpretar cada formato por separado (H8).

        Usa un generador aleatorio propio y se aplica al final, así el resto del escenario
        queda igual que sin estos formatos.
        """
        rng = random.Random(self.seed + 1_000_003)
        consumo = self.datasets['consumo']
        etiquetadas = ({a["id_registro"] for a in self.anomalias}
                       | {c["id_registro"] for c in self.casos_legitimos})
        # Tampoco la carga original de un duplicado: con otro dominio, la copia ya no sería idéntica
        repetidas = consumo.duplicated(subset=[c for c in consumo.columns if c != "id"], keep=False)
        candidatas = [i for i, id_, rep in zip(consumo.index, consumo["id"], repetidas)
                      if id_ not in etiquetadas and not rep]
        elegidas = sorted(rng.sample(candidatas, round(len(consumo) * TASA_DOMINIO_CON_FORMATO)))
        for i in elegidas:
            original = consumo.at[i, "dominio"]
            escrito = rng.choice(FORMATOS_DOMINIO)(original)
            consumo.at[i, "dominio"] = escrito
            self._registrar_legitimo(consumo.at[i, "id"], consumo.at[i, "vehiculo_id"], "DOMINIO_CON_FORMATO",
                                     f"{original} registrado como '{escrito}'")

        solicitudes = self.datasets['solicitudes']
        fechas = pd.to_datetime(solicitudes["fecha_solicitud"])
        otro_formato = [rng.random() < TASA_FECHA_OTRO_FORMATO for _ in range(len(solicitudes))]
        solicitudes["fecha_solicitud"] = [f.strftime("%d/%m/%Y") if otro else f.strftime("%Y-%m-%d")
                                          for f, otro in zip(fechas, otro_formato)]
        logger.info(f"✓ Formatos de origen: {len(elegidas)} dominios con otro formato, "
                    f"{sum(otro_formato)} fechas de solicitud en DD/MM/AAAA")

    def ejecutar(self):
        """Ejecuta todo el pipeline"""
        logger.info("=" * 60)
        logger.info(f"INICIANDO PIPELINE MAESTRO DE GENERACIÓN (escenario {self.escenario})")
        logger.info("=" * 60)

        try:
            if self.escenario == "realista":
                self.generar_flota_realista()
                self.generar_estaciones()
                self.generar_consumo_realista()  # también genera la telemetría
            else:
                self.generar_flota()
                self.generar_telemetria()
                self.generar_consumo()
            if self.escenario == "realista":
                self.generar_solicitudes_realista()
                self.generar_facturacion_realista()
                self.aplicar_formatos_de_origen()
            else:
                self.generar_solicitudes()
                self.generar_facturacion()

            archivos = self.guardar_datasets()

            logger.info("=" * 60)
            logger.info("✅ PIPELINE COMPLETADO EXITOSAMENTE")
            logger.info("=" * 60)

            return {
                "exito": True,
                "directorio": str(self.output_dir),
                "archivos": archivos,
                "ground_truth": self.metadata['ground_truth'],
                "metadata": self.metadata
            }

        except Exception as e:
            logger.error(f"❌ Error en pipeline: {e}", exc_info=True)
            return {
                "exito": False,
                "error": str(e),
                "directorio": str(self.output_dir)
            }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline Maestro - Generador de datos sintéticos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python generator_pipeline_maestro.py                    # Usa valores por defecto (200 vehículos, seed 42)
  python generator_pipeline_maestro.py --n_flota 100      # Genera 100 vehículos
  python generator_pipeline_maestro.py --seed 123         # Usa seed 123 para reproducibilidad
  python generator_pipeline_maestro.py --n_flota 500 --seed 99
  python generator_pipeline_maestro.py --escenario realista
        """
    )

    parser.add_argument(
        '--n_flota',
        type=int,
        default=200,
        help='Número de vehículos a generar (default: 200)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=SEED,
        help=f'Seed para reproducibilidad (default: {SEED})'
    )

    parser.add_argument(
        '--escenario',
        choices=ESCENARIOS,
        default='didactico',
        help='didactico: anomalías inconfundibles; realista: uso simulado día por día, '
             'anomalías sutiles y casos legítimos que se les parecen (default: didactico)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Directorio de salida (default: datasets/synthetics_maestro o datasets/synthetics_realista)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Modo silencioso (menos output)'
    )

    args = parser.parse_args()

    # Validar parámetros
    if args.n_flota < 10:
        print("❌ Error: n_flota debe ser al menos 10")
        sys.exit(1)
    if args.n_flota > 5000:
        print("⚠️  Advertencia: Generar más de 5000 vehículos puede tomar mucho tiempo")

    generador = GeneradorMaestro(n_flota=args.n_flota, seed=args.seed, output_dir=args.output,
                                 escenario=args.escenario)
    resultado = generador.ejecutar()

    # Imprimir resumen
    if not args.quiet:
        print("\n" + "=" * 60)
        print("RESUMEN FINAL")
        print("=" * 60)

    if resultado['exito']:
        if not args.quiet:
            for nombre, ruta in resultado['archivos'].items():
                df = pd.read_csv(ruta)
                print(f"  {nombre:20} | {len(df):6} filas | {ruta}")
            print(f"  {'ground_truth':20} | {len(generador.anomalias):6} filas | {resultado['ground_truth']}")
            print("\n✅ ÉXITO - Todos los datos fueron generados correctamente")
        print(json.dumps(resultado, indent=2, default=str))
    else:
        print(f"❌ ERROR: {resultado['error']}")

    sys.exit(0 if resultado['exito'] else 1)
