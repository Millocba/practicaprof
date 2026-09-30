#!/usr/bin/env python3
"""
Pipeline Maestro - Ejecuta todos los generadores de datos
Genera, en los dos escenarios: flota, telemetría, consumo, solicitudes y facturación. El
escenario realista suma estaciones, telemetría diaria, detalle de facturación, contratos,
transferencias, excepciones de odómetro y casos legítimos (ver TABLAS).

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
import re

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
# Versión de los datos que produce el generador: cambiarla cuando cambie lo que genera, así la
# aplicación regenera los datos que tenga en disco de una versión anterior
VERSION_GENERADOR = "2.6"   # 2.0: escenario realista v2 (docs/DISENO_ESCENARIO_V2.md); 2.1: horas del día en el orden del odómetro; 2.2: forma de cargar calibrada; 2.3: excepciones de odómetro; 2.4: textos del diccionario; 2.5: origen de la transacción (H13); 2.6: errores de carga en el registro interno

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
    "CARGA_SIN_REGISTRO": ("H8", "ALTA"),
    "ANULADA_CON_CARGA": ("H8", "ALTA"),
    "RENDIDA_SIN_CARGA": ("H8", "ALTA"),
    "DESACUERDO_DE_LITROS": ("H8", "MEDIA"),
    "CARGA_SUPERA_AUTORIZADO": ("H8", "MEDIA"),
    "TOTAL_INFLADO": ("H9", "ALTA"),
    "LINEA_SIN_CONSUMO": ("H9", "ALTA"),
    "LINEA_DUPLICADA": ("H9", "ALTA"),
    "SOBREPRECIO": ("H9", "MEDIA"),
    "FACTURADA_A_PRECIO_DE_SURTIDOR": ("H9", "MEDIA"),
    "DIFERENCIA_DEUDA_PDF": ("H9", "ALTA"),
    "PRODUCTO_NO_COMBUSTIBLE": ("H9", "MEDIA"),
    "CARGA_CON_CUPO_AGOTADO": ("H10", "ALTA"),
    "DISPOSITIVO_ACTIVO_EN_BAJA": ("H11", "ALTA"),
    "TRANSFERENCIA_SIN_NECESIDAD": ("H10", "MEDIA"),
    "ODOMETRO_SIN_AVANCE": ("H12", "MEDIA"),
    "DOBLE_COBRO": ("H13", "ALTA"),
    # Errores de carga en el registro interno (realista): disparan alertas correctas, que se citan y
    # se corrigen; no son irregularidades (#24)
    "ERROR_PROVEEDOR": ("CALIDAD", "BAJA"),
    "ERROR_DOMINIO": ("CALIDAD", "BAJA"),
    "ERROR_TARJETA": ("CALIDAD", "BAJA"),
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
    "PENDIENTE_DE_RENDICION": "la solicitud del registro interno todavía no se rindió: la carga existe",
    "ESTACION_AJENA": "carga en una estación de otro proveedor: está en el registro interno y no en el reporte",
    "TARJETA_PERSONAL": "carga con una tarjeta personal: el reporte trae la persona y no el dominio",
    "REGISTRO_REHECHO": "el pedido se anuló y se volvió a hacer antes de cargar: el anulado no tiene carga",
    "TOLERANCIA_MEDICION": "la carga supera lo autorizado dentro de la tolerancia de medición del surtidor",
    "DESFASE_DE_CORTE": "la carga del último día del mes se factura en el período siguiente",
    "AJUSTE_DOCUMENTADO": "la factura incluye un ajuste documentado (bonificación o recargo)",
    "DOMINIO_CON_FORMATO": "el dominio se registró con espacios, guiones o minúsculas; normalizado es el del vehículo",
    "TRANSFERENCIA_DE_SALDO": "el contrato recibió saldo de otro porque la proyección del mes no alcanzaba",
    "DISPOSITIVO_EN_DEPOSITO": "el móvil está de baja y su dispositivo quedó en el grupo de depósito, sin transmitir",
    "ODOMETRO_EXCEPTUADO": "el vehículo tiene una excepción de odómetro vigente ese día: la lectura se repite",
    "CONTINGENCIA": "la carga se registró por contingencia (vía alternativa) y no se duplicó",
}

COLUMNAS_CASOS_LEGITIMOS = ["tabla", "id_registro", "vehiculo_id", "tipo_caso", "descripcion"]

# Contratos del escenario realista: seis, con topes mensuales en pesos. Los vehículos se reparten
# como el consumo de la fuente y cada tope es el consumo del mes de mayor uso del contrato por un
# factor: los dos grandes quedan cortos y reciben transferencias preventivas de los que sobran; en
# total el cupo alcanza cualquier mes (ejecución media cercana al 90%)
REPARTO_CONTRATOS = [0.492, 0.237, 0.091, 0.082, 0.075, 0.023]
FACTOR_PRECIO_EMPRESA = 0.98        # el proveedor factura al precio de empresa, un 2% menor que el del surtidor
PROB_PDF_CARGADO = 0.85             # el 15% de las facturas no tiene su PDF cargado (fuente)
PROVEEDOR_CONTRATO = "PROVEEDOR 1"
FACTOR_TOPE_CONTRATO = [0.9, 0.92, 1.2, 1.25, 1.2, 1.3]
MARGEN_PROYECCION = 1.05            # se transfiere si la proyección a fin de mes supera el saldo en este margen
DIA_INICIO_SEGUIMIENTO = 5          # antes, el promedio del mes no es confiable (salvo que no alcance el día)
DIAS_PESO_HISTORICO = 7             # la proyección combina el mes con 7 días del promedio histórico
DIAS_DE_SEGUIMIENTO = (0, 3)        # el saldo se revisa a mano los lunes y los jueves
RESERVA_DONANTE = 1.2               # el contrato que cede conserva un 20% más que su propia proyección

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
# Composición de la flota del escenario realista, calibrada con el perfil agregado de la fuente
# (perfiles/): estados, tipos, combustible y telemetría por estado
ESTADOS_REALISTA = {"EN SERVICIO": 0.515, "FUERA DE SERVICIO": 0.127, "TRAMITE EN BAJA": 0.358}
SUBESTADOS_REALISTA = {
    "EN SERVICIO": {None: 1.0},
    "FUERA DE SERVICIO": {"PROBLEMA DE MOTOR": 0.35, "OTROS PROBLEMAS MECANICOS": 0.28, "PROBLEMA DE BATERIA": 0.2,
                          "SINIESTRO": 0.1, "PROBLEMAS ELECTRICOS": 0.07},
    "TRAMITE EN BAJA": {"TRAMITE NO INICIADO EN EL DPTO. TRANSPORTE": 0.5,
                        "TRAMITE INICIADO EN EL DPTO. TRANSPORTE": 0.5},
}
# Parte de los vehículos fuera de servicio o en baja cambió de estado durante la ventana (cargan
# hasta esa fecha); el resto ya estaba así antes y no carga
PROB_CAMBIO_EN_VENTANA = {"FUERA DE SERVICIO": 0.4, "TRAMITE EN BAJA": 0.15}
TIPOS_REALISTA = {"SEDAN": 0.37, "PICK-UP": 0.36, "MOTOCICLETA": 0.25, "UTILITARIO": 0.01, "CAMION": 0.01}
PROB_NAFTA_POR_TIPO = {"SEDAN": 0.8, "PICK-UP": 0.2, "MOTOCICLETA": 1.0, "UTILITARIO": 0.0, "CAMION": 0.0}
PRODUCTOS_REALISTA = {"GASOIL": {"INFINIA DIESEL": 0.99, "GASOIL": 0.01}, "NAFTA": {"INFINIA": 0.99, "SUPER": 0.01}}
MARCAS_REALISTA = {
    "MOTOCICLETA": {"KAWASAKI": 0.45, "HONDA": 0.4, "YAMAHA": 0.15},
    "SEDAN": {"FIAT": 0.4, "CHEVROLET": 0.25, "RENAULT": 0.15, "VOLKSWAGEN": 0.1, "TOYOTA": 0.1},
    "PICK-UP": {"NISSAN": 0.55, "TOYOTA": 0.2, "FORD": 0.15, "CHEVROLET": 0.1},
    "UTILITARIO": {"RENAULT": 0.5, "FIAT": 0.5},
    "CAMION": {"IVECO": 0.6, "FORD": 0.4},
}
TELEMETRIA_POR_ESTADO = {"EN SERVICIO": 0.80, "FUERA DE SERVICIO": 0.47, "TRAMITE EN BAJA": 0.043}
GRUPO_DEPOSITO = "BAJA / REEMPLAZOS"   # grupo de los dispositivos retirados de los móviles de baja
PROB_IDENTIFICABLE_REALISTA = 0.8
PRECIO_BASE = {"GASOIL": 2.0, "INFINIA DIESEL": 2.4, "NAFTA": 2.1, "SUPER": 2.3, "INFINIA": 2.6, "GLP": 1.2}
AUMENTO_MENSUAL_PRECIO = 0.02

ZONA_BASE = {"lat": (-34.9, -34.4), "lon": (-58.8, -58.2)}
N_ESTACIONES_LOCALES = 40
N_RUTAS = 5
FRACCIONES_RUTA = [0.25, 0.45, 0.65, 0.85, 1.0]  # una estación en cada tramo de la ruta
TASA_DIAS_SIN_SENAL = 0.03      # días en que el dispositivo no reporta
PROB_DIA_SIN_USO = 0.25
# Forma de cargar, calibrada con la auditoría agregada de las fuentes (docs/BITACORA.md, 2026-09-29):
# la flota carga seguido y completa el tanque (unas 7 cargas por mes por vehículo en servicio,
# 59% del tanque y 35 L por carga en la mediana y un rendimiento estable entre cargas)
PROB_CARGA_PARCIAL = 0.0        # la fuente casi no muestra cargas parciales: la siguiente parecería un rendimiento imposible
CARGA_PARCIAL = (0.6, 0.9)      # nivel del tanque, en fracción, al que llega una carga parcial
RESERVA_TANQUE = 0.05           # fracción del tanque en la que el vehículo obliga a cargar
UMBRAL_CARGA = (0.25, 0.7)      # nivel por debajo del cual cada vehículo carga al final del día
UMBRAL_CARGA_POR_TIPO = {"MOTOCICLETA": (0.1, 0.3)}  # con un tanque chico se carga casi vacío
VARIACION_KM_DIA = (0.3, 2.2)   # km del día respecto de los habituales del vehículo
PROB_SEGUNDO_TURNO = 0.04       # días con carga en que el vehículo sigue en otro turno y vuelve a cargar
KM_SEGUNDO_TURNO = (0.4, 1.0)   # km del segundo turno respecto de los habituales del día
FACTOR_KM_DIA = 1.6             # escala de los km habituales por día de cada tipo de vehículo
FACTOR_KM_POR_TIPO = {"MOTOCICLETA": 1.0, "PICK-UP": 2.2}  # la fuente: 35 L por carga en la mediana, 17% de menos de 10 L

# Excepciones de odómetro (H12). En la fuente, el 1,5% de la flota tiene la excepción vigente; mientras
# dura, la carga repite la última lectura. Una excepción puede durar un solo día.
EXCEPCIONES_ODOMETRO = {
    "vigente": 3,          # vehículos cada 200 con la excepción vigente hasta después de la ventana
    "cumplida": 3,         # excepciones que ya vencieron (una de un solo día)
    "sin_excepcion": 3,    # anomalías: la lectura se repite sin excepción (una, después de que venció)
}
MOTIVOS_EXCEPCION = ["ODOMETRO SIN FUNCIONAR", "TABLERO EN REPARACION", "CAMBIO DE INSTRUMENTAL"]

# Origen de la transacción en el reporte del proveedor (H13): el medio de pago electrónico habitual o una
# contingencia, la carga registrada por una vía alternativa cuando el habitual no funciona. En la fuente,
# el 1,2% de las transacciones es de contingencia; cuántas son doble cobro no se conoce: la proporción
# (una de cada diez contingencias) es un supuesto del diseño.
ORIGEN_HABITUAL = "POSNET"
ORIGEN_CONTINGENCIA = "CONTINGENCIA"
PROPORCION_CONTINGENCIA = 0.011      # cargas registradas por contingencia sin duplicarse (legítimas)
CONTINGENCIAS_CERCANAS = 0.3         # de ellas, las que tienen otra carga del vehículo a menos de 12 horas
DOBLE_COBRO_MAX_MINUTOS = 45         # la carga duplicada se registra hasta 45 minutos después de la original
DOBLE_COBRO_VARIACION_LITROS = 0.015  # y con hasta 1,5% de diferencia de litros (el criterio es ±2%)

# Casos legítimos que en la fuente son una proporción de las cargas, no una cantidad por vehículo
PROPORCION_DE_CARGAS = {
    "TARJETA_PERSONAL": 0.011,      # cargas con tarjeta personal (fuente: 1,1%)
    "ESTACION_AJENA": 0.075,        # cargas en otra red, solo en el registro (fuente: 7,2% de los pedidos)
}

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
    "CARGA_SIN_REGISTRO": 6,        # cargas sin ningún registro interno
    "ANULADA_CON_CARGA": 4,         # registro anulado cuya carga igual existe
    "RENDIDA_SIN_CARGA": 5,         # registros rendidos sin carga en el reporte
    "DESACUERDO_DE_LITROS": 6,      # el registro declara de 2 a 18 L distintos que la carga
    "CARGA_SUPERA_AUTORIZADO": 6,   # 15% a 50% más que lo autorizado
    "PENDIENTE_DE_RENDICION": 37,   # legítimos: ~1,1% de las cargas (fuente)
    "REGISTRO_REHECHO": 27,         # legítimos: con los anulados con carga, ~0,9% de registros anulados (fuente)
    "TOLERANCIA_MEDICION": 10,      # legítimos: 1% a 3% más que lo autorizado
    "TOTAL_INFLADO": 2,             # facturas
    "LINEA_SIN_CONSUMO": 6,
    "LINEA_DUPLICADA": 5,
    "SOBREPRECIO": 6,
    "FACTURADA_A_PRECIO_DE_SURTIDOR": 6,  # líneas al precio del surtidor en lugar del de empresa
    "DIFERENCIA_DEUDA_PDF": 2,      # facturas cuyo PDF no coincide con la deuda
    "PRODUCTO_NO_COMBUSTIBLE": 2,   # facturas con renglones de lubricante
    "CARGA_CON_CUPO_AGOTADO": 1,    # contratos-mes en los que una transferencia llega tarde y se carga sin saldo
    "DISPOSITIVO_ACTIVO_EN_BAJA": 2,  # móviles de baja con el dispositivo fuera del depósito y transmitiendo
    "DISPOSITIVO_EN_DEPOSITO": 3,   # legítimos, como mínimo: ~4% de las bajas tiene dispositivo (fuente)
    "TRANSFERENCIA_SIN_NECESIDAD": 2,  # transferencias que la proyección no justifica
    "AJUSTE_DOCUMENTADO": 4,        # legítimos: facturas con un ajuste
    "DOBLE_COBRO": 8,               # cargas duplicadas por contingencia (~0,1% de las cargas)
}
# Errores de carga cada 200 vehículos (#24). Provisorio: la proporción real hay que definirla con el
# referente del dominio; según él, son la mayoría de las alertas del registro interno.
ERRORES_DE_CARGA = {
    "ERROR_PROVEEDOR": 6,   # el pedido se registra como de otra red
    "ERROR_DOMINIO": 6,     # el pedido se registra con el dominio de otro vehículo
    "ERROR_TARJETA": 4,     # se carga con la tarjeta de otro vehículo: el reporte atribuye la carga a ese
}
PROB_DESFASE_DE_CORTE = 0.5         # cargas del último día del mes facturadas al mes siguiente
TASAS_CALIDAD_REALISTA = {"DOMINIO_INVALIDO": 0.003, "VALOR_NULO": 0.005, "DUPLICADO": 0.003}

# Formatos de origen (realista): cómo llegan los datos de cada fuente, sin ser anomalías.
# Se aplican al final con un generador aleatorio propio, para no alterar el resto del escenario.
TASA_DOMINIO_CON_FORMATO = 0.005    # cargas con el dominio escrito de otra forma (H1): la fuente gana
                                    # alrededor de medio punto de vinculación al normalizar
# Registro interno (escenario realista), calibrado con el perfil de la fuente
NIVELES_TANQUE = {"TANQUE LLENO": 0.74, "1/2 TANQUE": 0.09, "3/4 TANQUE": 0.085, "1/4 TANQUE": 0.075, "RESERVA": 0.01}
BANDERAS_RENDICION = {"Amarillo": 0.64, "Verde": 0.359, "Rojo": 0.001}
RELACIONES_CONSUMO = {"J": 0.62, "I": 0.13, "D": 0.08, "Q": 0.06, "E": 0.06, "K": 0.05}
ESTACION_AJENA = "ESTACION AJENA"
_CORTES_DOMINIO = r"(?<=[A-Z])(?=\d)|(?<=\d)(?=[A-Z])"   # entre letras y números
FORMATOS_DOMINIO = [
    lambda d: d.lower(),                                  # za123bc
    lambda d: re.sub(_CORTES_DOMINIO, " ", d),            # ZA 123 BC
    lambda d: re.sub(_CORTES_DOMINIO, "-", d),            # ZA-123-BC
    lambda d: f"{d} ",                                    # espacio al final
]


def dominio_sintetico(i, tipo, anio):
    """Dominio con un formato público pero marcado como sintético: siempre empieza con Z, una serie
    no asignada. Autos desde 2016 AA999AA, anteriores AAA999; motos A999AAA."""
    letras = "ABCDEFGHJKLMNPRSTUVWXY"

    def letra(k):
        return letras[k % len(letras)]

    numero = f"{i % 1000:03d}"
    if tipo == "MOTOCICLETA":
        return f"Z{numero}{letra(i // 1000)}{letra(i // 7)}{letra(i // 3)}"
    if anio >= 2016:
        return f"Z{letra(i // 1000)}{numero}{letra(i // 7)}{letra(i // 3)}"
    return f"ZZ{letra(i // 1000)}{numero}"


# ============================================================================
# Diccionario de datos y relaciones
#
# Fuente única de la descripción de cada archivo: el generador escribe
# `diccionario.json` con las tablas y relaciones del escenario generado, y un test
# verifica que describa todas las columnas que se producen.
# ============================================================================

AMBOS = ("didactico", "realista")
REALISTA = ("realista",)
DIDACTICO = ("didactico",)

# tabla: grano, clave, escenarios y columnas {nombre: (tipo, descripción[, escenarios])}
TABLAS = {
    "flota": {
        "grano": "un vehículo", "clave": "Matricula", "escenarios": AMBOS,
        "columnas": {
            "Matricula": ("texto", "Clave del vehículo, VEH-NNNNNN"),
            "Dominio": ("texto", "Dominio sintético, único; no proviene de un padrón. Didáctico: ABNNNNCD. "
                                 "Realista: formatos públicos que empiezan con Z (Z999AAA motos, ZA999AA autos "
                                 "desde 2016, ZZA999 anteriores)"),
            "Estado": ("categoría", "EN SERVICIO, FUERA DE SERVICIO o de baja: BAJA y EN REPARACION en el "
                                    "escenario didáctico, TRAMITE EN BAJA en el realista"),
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
            "LimiteSaldo": ("decimal", "Límite de saldo de la tarjeta (realista: mensual, fijado al registrarla)"),
            "LimiteLitros": ("decimal (L)", "Límite de litros de la tarjeta (realista: mensual, fijado al registrarla)"),
            "NumeroContrato": ("entero", "Contrato al que pertenece la tarjeta, 1 a 6", REALISTA),
            "Cupo": ("decimal (L)", "Litros por carga de la tarjeta: la capacidad del tanque", REALISTA),
            "SubEstado": ("categoría", "Didáctico: ACTIVO o INACTIVO. Realista: motivo de fuera de servicio o "
                                       "etapa del trámite de baja; vacío si está en servicio"),
            "FechaEstado": ("fecha", "Último cambio a un estado distinto de EN SERVICIO; vacía si está en servicio",
                            REALISTA),
            "ExcepcionOdometro": ("SI / NO", "Si el vehículo tiene hoy una excepción de odómetro vigente", REALISTA),
            "FechaHastaExcepcionOdometro": ("fecha DD/MM/AAAA", "Hasta cuándo rige la excepción; vacía si no tiene",
                                            REALISTA),
        },
    },
    "excepciones_odometro": {
        "grano": "una excepción de odómetro (vigente o cumplida)", "clave": "id", "escenarios": ("realista",),
        "columnas": {
            "id": ("texto", "Clave de la excepción, EXC-NNNN"),
            "patente": ("texto", "Dominio sintético del vehículo exceptuado"),
            "motivo": ("categoría", "Motivo sintético: ODOMETRO SIN FUNCIONAR, TABLERO EN REPARACION o CAMBIO DE INSTRUMENTAL"),
            "activo": ("SI / NO", "Si la excepción sigue vigente"),
            "fecha_creacion": ("fecha", "Desde cuándo rige la excepción"),
            "fecha_hasta": ("fecha", "Último día en que rige; puede ser el mismo día de la creación"),
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
            "Grupo": ("categoría", "Grupo del dispositivo: el de la dependencia del móvil, o BAJA / REEMPLAZOS "
                                   "si está en depósito", REALISTA),
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
            "contrato": ("entero", "Contrato de la tarjeta, 1 a 6: descuenta del saldo del mes", REALISTA),
            "hora": ("texto", "Hora de la carga, HH:MM:SS", REALISTA),
            "tipo_identificacion": ("categoría", "PATENTE, o DNI si la tarjeta es personal: entonces el dominio "
                                                 "viene vacío y el conductor es la persona", REALISTA),
            "origen_transaccion": ("categoría", "POSNET (medio de pago electrónico habitual) o CONTINGENCIA (carga "
                                                "registrada por una vía alternativa); una contingencia con una carga "
                                                "por POSNET del mismo vehículo cercana es el doble cobro", REALISTA),
        },
    },
    "solicitudes": {
        "grano": "una solicitud de combustible (en el realista, del registro interno: pedido y rendición)",
        "clave": "id", "escenarios": AMBOS,
        "columnas": {
            "id": ("texto", "Clave de la solicitud, SOL-NNNNNNNN"),
            "vehiculo_id": ("texto", "Vehículo solicitante"),
            "dominio": ("texto", "Dominio del vehículo solicitante"),
            "fecha_solicitud": ("fecha", "Fecha de la solicitud, AAAA-MM-DD", DIDACTICO),
            "litros_solicitados": ("decimal (L)", "Litros pedidos", DIDACTICO),
            "estado": ("categoría", "APROBADA, PENDIENTE o RECHAZADA", DIDACTICO),
            "centro_costo": ("texto", "Centro de costo, CC-NNN", DIDACTICO),
            "responsable": ("texto", "Responsable, RESP-N", DIDACTICO),
            "observaciones": ("texto", "Observaciones; puede estar vacía", DIDACTICO),
            "fecha": ("fecha", "Fecha del pedido, DD/MM/AAAA como en la fuente", REALISTA),
            "hora": ("texto", "Hora del pedido, HH:MM:SS: de 5 a 90 minutos antes de la carga", REALISTA),
            "odometro": ("entero (km)", "Odómetro declarado", REALISTA),
            "solicitante": ("texto", "Quien pide: el conductor, o la persona de la tarjeta personal", REALISTA),
            "tarjeta_personal": ("booleano", "La carga se hace con una tarjeta personal y no con la del vehículo",
                                 REALISTA),
            "litros_autorizados": ("decimal (L)", "Litros autorizados. Didáctico: de 20 a 100, generados por "
                                                  "separado. Realista: los del pedido, antes de cargar"),
            "litros_cargados": ("decimal (L)", "Litros que el registro declara cargados", REALISTA),
            "nivel_tanque": ("categoría", "Nivel del tanque antes de cargar: TANQUE LLENO, 3/4, 1/2, 1/4, RESERVA",
                             REALISTA),
            "rendido": ("categoría", "SI si se rindió el ticket; NO si está pendiente", REALISTA),
            "fecha_rendicion": ("fecha", "Fecha de la rendición, DD/MM/AAAA; vacía si está pendiente", REALISTA),
            "hora_rendicion": ("texto", "Hora de la rendición; vacía si está pendiente", REALISTA),
            "numero_ticket": ("texto", "Ticket de la carga, 6 dígitos; vacío si está pendiente", REALISTA),
            "anulado": ("categoría", "SI si el registro se anuló", REALISTA),
            "fecha_anulado": ("fecha", "Fecha de la anulación, DD/MM/AAAA", REALISTA),
            "estacion_servicio": ("texto", "Estación (código del reporte) o ESTACION AJENA si es de otro proveedor",
                                  REALISTA),
            "bandera_rendicion": ("categoría", "Amarillo, Verde o Rojo", REALISTA),
            "relacion_consumo": ("categoría", "Código de relación de consumo del vehículo", REALISTA),
        },
    },
    "contratos": {
        "grano": "un contrato de abastecimiento", "clave": "indice", "escenarios": REALISTA,
        "columnas": {
            "indice": ("entero", "Número de contrato en la flota, 1 a 6"),
            "numero": ("texto", "Número del contrato, CTO-NNNNNN"),
            "etiqueta": ("texto", "Nombre del contrato"),
            "limite_mensual": ("decimal", "Tope mensual en pesos; se renueva cada mes"),
        },
    },
    "transferencias": {
        "grano": "una transferencia de saldo entre contratos", "clave": "id", "escenarios": REALISTA,
        "columnas": {
            "id": ("texto", "Clave de la transferencia, TRF-NNNNNN"),
            "fecha": ("fecha", "Día en que se acredita, antes de las cargas del día"),
            "contrato_origen": ("entero", "Contrato que cede saldo"),
            "contrato_destino": ("entero", "Contrato que recibe saldo"),
            "monto": ("decimal", "Pesos transferidos"),
        },
    },
    "facturacion": {
        "grano": "una factura mensual (de toda la flota en el didáctico; de un proveedor en el realista)",
        "clave": "numero_factura", "escenarios": AMBOS,
        "columnas": {
            "numero_factura": ("texto", "Número de factura"),
            "contrato": ("entero", "Contrato facturado, 1 a 6", REALISTA),
            "proveedor": ("categoría", "Proveedor del contrato", REALISTA),
            "producto": ("categoría", "DIESEL o NAFTA: una factura por contrato, mes y familia", REALISTA),
            "fecha_factura": ("fecha", "Último día del período"),
            "periodo": ("texto", "Período facturado, AAAA-MM"),
            "total_litros": ("decimal (L)", "Litros facturados"),
            "total_monto": ("decimal", "Importe sin IVA (realista: monto de la deuda, a precio de empresa)"),
            "total_pdf": ("decimal", "Total del PDF de la factura; vacío si el PDF no se cargó", REALISTA),
            "vencimiento": ("fecha", "Vencimiento: 15 días después de la factura", REALISTA),
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
            "concepto": ("categoría", "COMBUSTIBLE, AJUSTE o (realista) LUBRICANTE"),
            "fecha": ("fecha", "Fecha de la carga según el proveedor"),
            "dominio": ("texto", "Dominio según el proveedor"),
            "litros": ("decimal (L)", "Litros facturados"),
            "precio_unitario": ("decimal", "Precio por litro facturado (realista: de empresa, un 2% menor que el del surtidor)"),
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
    ("consumo", "contrato", "contratos", "indice", "N:1", REALISTA, "cada carga descuenta del saldo del mes"),
    ("flota", "NumeroContrato", "contratos", "indice", "N:1", REALISTA, ""),
    ("transferencias", "contrato_origen", "contratos", "indice", "N:1", REALISTA, ""),
    ("transferencias", "contrato_destino", "contratos", "indice", "N:1", REALISTA, ""),
    ("solicitudes", "vehiculo_id", "flota", "Matricula", "N:1", AMBOS, ""),
    ("solicitudes", "dominio + fecha + hora", "consumo", "dominio + fecha + hora", "1:1", REALISTA,
     "sin clave común: se cruza por dominio y horario; en las tarjetas personales, por solicitante y conductor"),
    ("telemetria", "Placa", "flota", "Dominio", "N:1", AMBOS, "uno por vehículo en el realista"),
    ("excepciones_odometro", "patente", "flota", "Dominio", "N:1", REALISTA,
     "mientras rige, la carga repite la lectura del odómetro"),
    ("telemetria_diaria", "Placa", "telemetria", "Placa", "N:1", REALISTA, ""),
    ("facturacion", "periodo", "consumo", "fecha (mes)", "1:N", ("didactico",), "suma de las cargas del mes"),
    ("facturacion", "proveedor", "estaciones", "marca", "N:1", REALISTA, ""),
    ("facturacion_detalle", "numero_factura", "facturacion", "numero_factura", "N:1", REALISTA,
     "la suma de las líneas es el total (salvo TOTAL_INFLADO)"),
    ("facturacion_detalle", "referencia_consumo", "consumo", "id", "N:1", REALISTA,
     "se rompe en LINEA_SIN_CONSUMO; dos líneas en LINEA_DUPLICADA"),
    ("ground_truth", "id_registro", "consumo / facturacion / facturacion_detalle / solicitudes / telemetria", "id",
     "N:1", AMBOS, "según la columna tabla (en telemetria, el Alias); en tabla contrato_mes, el id es CTO-N|AAAA-MM"),
    ("casos_legitimos", "id_registro", "consumo / facturacion / facturacion_detalle / solicitudes / telemetria", "id",
     "N:1", REALISTA, "según la columna tabla (en telemetria, el Alias); en tabla contrato_mes, el id es CTO-N|AAAA-MM"),
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
            "version_generador": VERSION_GENERADOR,
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
        """Genera la tabla FLOTA con `n_flota` vehículos (escenario didáctico)."""
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

    def _registrar_legitimo(self, id_registro, vehiculo_id, tipo, descripcion, tabla="consumo"):
        self.casos_legitimos.append({"tabla": tabla, "id_registro": id_registro,
                                     "vehiculo_id": vehiculo_id, "tipo_caso": tipo,
                                     "descripcion": descripcion})

    def generar_flota_realista(self):
        """FLOTA con capacidad acorde al tipo de vehículo y fecha del último cambio de estado."""
        logger.info("Generando FLOTA (escenario realista)...")
        rng = self.rng
        rows, self._perfiles = [], {}

        def elegir(pesos):
            return rng.choices(list(pesos), weights=list(pesos.values()))[0]

        for i in range(1, self.n_flota + 1):
            dg_sel = rng.choice(DIRECCIONES)
            estado = elegir(ESTADOS_REALISTA)
            tipo = elegir(TIPOS_REALISTA)
            (cap_min, cap_max), rendimiento, km_dia = PERFILES_VEHICULO[tipo]
            capacidad = round(rng.uniform(cap_min, cap_max), 1)
            if estado == "EN SERVICIO":
                fecha_estado = None
            elif rng.random() < PROB_CAMBIO_EN_VENTANA[estado]:
                fecha_estado = FECHA_INICIO + timedelta(days=rng.randint(60, DIAS_VENTANA - 20))
            else:
                fecha_estado = FECHA_INICIO - timedelta(days=rng.randint(30, 720))
            anio = min(2025, max(2005, round(rng.triangular(2008, 2025, 2020))))
            matricula = f"VEH-{i:06d}"
            rows.append({
                "Matricula": matricula,
                "Dominio": dominio_sintetico(i, tipo, anio),
                "Estado": estado,
                "DireccionGral": dg_sel,
                "Dependencia": rng.choice(DEPENDENCIAS[dg_sel]),
                "Identificable": "SI" if rng.random() < PROB_IDENTIFICABLE_REALISTA else "NO",
                "TipoVehiculo": tipo,
                "Marca": elegir(MARCAS_REALISTA[tipo]),
                "Modelo": f"MODEL-{rng.randint(2010, 2024)}",
                "Año": anio,
                "TipoCombustible": "NAFTA" if rng.random() < PROB_NAFTA_POR_TIPO[tipo] else "GASOIL",
                "CapacidadTanque": capacidad,
                "NumeroMotor": f"M{i:08d}",
                "NumeroChasis": f"CH{i:08d}",
                "NumeroTarjeta": f"TARJ{i:08d}",
                "LimiteSaldo": round(rng.uniform(1000, 10000), 2),
                "LimiteLitros": round(capacidad * rng.uniform(3, 6), 1),
                "SubEstado": elegir(SUBESTADOS_REALISTA[estado]),
                "FechaEstado": fecha_estado.date() if fecha_estado else None,
            })
            # Uso real del vehículo: guía la simulación pero no forma parte de los datos
            self._perfiles[matricula] = {
                "rendimiento": rng.uniform(*rendimiento),
                "km_dia": rng.uniform(*km_dia) * FACTOR_KM_POR_TIPO.get(tipo, FACTOR_KM_DIA),
                "base": (rng.uniform(*ZONA_BASE["lat"]), rng.uniform(*ZONA_BASE["lon"])),
                "umbral_carga": rng.uniform(*UMBRAL_CARGA_POR_TIPO.get(tipo, UMBRAL_CARGA)),
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
        productos = PRODUCTOS_REALISTA[v["TipoCombustible"]]
        odo = float(rng.randint(10000, 250000))
        combustible = cap_real * rng.uniform(0.4, 0.9)
        dia_inicio_fraude = rng.randint(90, 200)

        viaje = (rng.randint(30, DIAS_VENTANA - 10), rng.choice(self._destinos)) if rol == "VIAJE_LARGO" else None
        dias_inactivo = set()
        if rol == "CARGA_VEHICULO_INACTIVO":
            desde = max(5, (fin_activo - FECHA_INICIO).days + 5)
            dias_inactivo = set(rng.sample(range(desde, DIAS_VENTANA + 1), rng.randint(1, 3)))
        dia_fuera_de_zona = rng.randint(30, DIAS_VENTANA) if rol == "CARGA_FUERA_DE_ZONA" else None
        cargas_sin_uso = rng.randint(3, 6) if rol == "RENDIMIENTO_IMPOSIBLE" else 0
        fraccionado = False

        def registrar(fecha, estacion, litros, odometro, etiqueta=None, legitimo=None):
            cargas.append({
                "vehiculo_id": m, "dominio": v["Dominio"], "fecha": fecha, "estacion": estacion,
                "producto": rng.choices(list(productos), weights=list(productos.values()))[0],
                "litros": round(litros, 2),
                "numero_tarjeta": v["NumeroTarjeta"], "conductor": f"CONDUCTOR-{rng.randint(1, 500)}",
                "_odo_real": odometro, "_etiqueta": etiqueta, "_legitimo": legitimo,
                "_capacidad": cap_reg, "_orden": len(cargas),
            })

        def cargar(fecha, pos, dia, completa=False):
            nonlocal combustible, fraccionado
            if not completa and PROB_CARGA_PARCIAL and rng.random() < PROB_CARGA_PARCIAL:
                objetivo = cap_real * rng.uniform(*CARGA_PARCIAL)
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
                km = perfil["km_dia"] * rng.uniform(*VARIACION_KM_DIA)

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
            if (PROB_SEGUNDO_TURNO and activo and km > 0 and len(cargas) > cargas_previas
                    and rng.random() < PROB_SEGUNDO_TURNO):
                # Otro turno con el mismo vehículo: recorre más y completa el tanque al terminar
                extra = perfil["km_dia"] * rng.uniform(*KM_SEGUNDO_TURNO)
                combustible -= min(extra / rendimiento_dia, max(combustible - RESERVA_TANQUE * cap_real, 0))
                odo += extra
                km += extra
                cargar(fecha, destino, dia, completa=True)
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
        self._con_gps = {v["Matricula"] for v in vehiculos if rng.random() < TELEMETRIA_POR_ESTADO[v["Estado"]]}
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
        """Asigna a cada rol una cantidad de candidatos distintos: una proporción de los candidatos
        (PROPORCION_DE_CARGAS) o una cantidad cada 200 vehículos (EVENTOS_REALISTA)."""
        candidatos = list(candidatos)
        self.rng.shuffle(candidatos)
        asignacion, posicion = {}, 0
        for rol in roles:
            n = (round(PROPORCION_DE_CARGAS[rol] * len(candidatos)) if rol in PROPORCION_DE_CARGAS
                 else self._cantidad(rol))
            for candidato in candidatos[posicion:posicion + n]:
                asignacion[candidato] = rol
            posicion += n
        return asignacion

    def generar_solicitudes_realista(self):
        """REGISTRO INTERNO (solicitudes.csv): pedido y rendición de cada carga.

        Como en la fuente, cada carga del reporte del proveedor tiene su pedido en el registro
        interno, de 5 a 90 minutos antes, con los litros autorizados y el ticket de la rendición.
        No comparten ningún identificador: se cruzan por dominio y horario (o por persona, en las
        tarjetas personales). También agrega al reporte la hora de cada carga y el tipo de tarjeta.

        Anomalías: carga sin registro, registro anulado con carga, registro rendido sin carga,
        desacuerdo de litros y carga que supera lo autorizado. Casos legítimos: rendición
        pendiente, estación de otro proveedor (solo en el registro), tarjeta personal (el
        reporte trae la persona y no el dominio), exceso dentro de la tolerancia del surtidor y
        pedido rehecho (se anula y se vuelve a hacer antes de cargar).
        """
        rng = self.rng
        consumo = self.datasets["consumo"]

        def elegir(pesos):
            return rng.choices(list(pesos), weights=list(pesos.values()))[0]

        consumo["hora"] = [f"{min(23, int(rng.triangular(6, 24, 12))):02d}:{rng.randint(0, 59):02d}:"
                           f"{rng.randint(0, 59):02d}" for _ in range(len(consumo))]
        # Las cargas del mismo vehículo en el día siguen, en horario, el orden del odómetro
        orden = consumo.sort_values(["vehiculo_id", "fecha", "id"]).index
        horas = consumo.loc[orden, "hora"].groupby([consumo.loc[orden, "vehiculo_id"], consumo.loc[orden, "fecha"]])
        consumo.loc[orden, "hora"] = horas.transform(lambda h: pd.Series(sorted(h), index=h.index)).values
        # Un duplicado repite también la hora de su original
        original_de = {a["id_registro"]: a["descripcion"].removeprefix("copia de ")
                       for a in self.anomalias if a["tipo_anomalia"] == "DUPLICADO"}
        hora_de = consumo.set_index("id")["hora"]
        consumo["hora"] = [hora_de[original_de[i]] if i in original_de else h for i, h in zip(consumo["id"], consumo["hora"])]
        consumo["tipo_identificacion"] = "PATENTE"
        cargas = self._cargas_facturables()
        etiquetadas = ({a["id_registro"] for a in self.anomalias}
                       | {c["id_registro"] for c in self.casos_legitimos} | set(original_de.values()))
        asignacion = self._repartir(
            [i for i in cargas["id"] if i not in etiquetadas],
            ["CARGA_SIN_REGISTRO", "ANULADA_CON_CARGA", "CARGA_SUPERA_AUTORIZADO", "DESACUERDO_DE_LITROS",
             "TOLERANCIA_MEDICION", "PENDIENTE_DE_RENDICION", "TARJETA_PERSONAL", "ESTACION_AJENA",
             "REGISTRO_REHECHO"])

        # Tarjetas personales: el reporte trae la persona en lugar del dominio
        personales = [i for i, rol in asignacion.items() if rol == "TARJETA_PERSONAL"]
        es_personal = consumo["id"].isin(personales)
        consumo.loc[es_personal, "tipo_identificacion"] = "DNI"
        consumo.loc[es_personal, "dominio"] = None
        consumo.loc[es_personal, "numero_tarjeta"] = [f"TARJ-DNI-{k:05d}" for k in range(1, es_personal.sum() + 1)]

        rows, pendientes_de_id = [], []

        def registrar(c, fecha_carga, litros_reg, autorizados, rendido="SI", anulado="NO", estacion=None,
                      personal=False, etiqueta=None):
            pedido = fecha_carga - timedelta(minutes=rng.randint(5, 90))
            rendicion = fecha_carga + timedelta(minutes=rng.randint(0, 20))
            fila = {
                "vehiculo_id": c["vehiculo_id"], "dominio": self._dominio_de[c["vehiculo_id"]],
                "_orden": pedido, "fecha": pedido.strftime("%d/%m/%Y"), "hora": pedido.strftime("%H:%M:%S"),
                "odometro": c["odometro"], "solicitante": c["conductor"], "tarjeta_personal": personal,
                "litros_autorizados": autorizados, "litros_cargados": round(litros_reg, 2),
                "nivel_tanque": elegir(NIVELES_TANQUE), "rendido": rendido,
                "fecha_rendicion": rendicion.strftime("%d/%m/%Y") if rendido == "SI" else None,
                "hora_rendicion": rendicion.strftime("%H:%M:%S") if rendido == "SI" else None,
                "numero_ticket": f"{rng.randint(100000, 999999)}" if rendido == "SI" else None,
                "anulado": anulado,
                "fecha_anulado": (pedido + timedelta(hours=rng.randint(1, 48))).strftime("%d/%m/%Y")
                if anulado == "SI" else None,
                "estacion_servicio": estacion or c["estacion"],
                "bandera_rendicion": elegir(BANDERAS_RENDICION), "relacion_consumo": elegir(RELACIONES_CONSUMO),
            }
            rows.append(fila)
            if etiqueta:
                pendientes_de_id.append((fila, etiqueta))

        self._dominio_de = self.datasets["flota"].set_index("Matricula")["Dominio"].to_dict()
        ajenas = []
        for c in consumo[~consumo["id"].isin(set(consumo["id"]) - set(cargas["id"]))].to_dict("records"):
            rol = asignacion.get(c["id"])
            fecha_carga = datetime.combine(pd.Timestamp(c["fecha"]).date(),
                                           datetime.strptime(c["hora"], "%H:%M:%S").time())
            litros = c["litros"]
            autorizados = float(round(litros + rng.uniform(0, 10)))
            if rol == "CARGA_SIN_REGISTRO":
                self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], rol, "registro",
                                         "carga sin registro interno")
                continue
            if rol == "ESTACION_AJENA":
                # La carga se hizo en otra red: no está en el reporte del proveedor, solo en el registro
                ajenas.append(c["id"])
                registrar(c, fecha_carga, litros, autorizados, estacion=ESTACION_AJENA,
                          etiqueta=("legitimo", rol, CATALOGO_LEGITIMOS[rol]))
                continue
            if rol == "ANULADA_CON_CARGA":
                registrar(c, fecha_carga, litros, autorizados, rendido="NO", anulado="SI")
                self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], rol, "anulado",
                                         "el registro se anuló pero la carga existe")
            elif rol == "PENDIENTE_DE_RENDICION":
                registrar(c, fecha_carga, litros, autorizados, rendido="NO")
                self._registrar_legitimo(c["id"], c["vehiculo_id"], rol, CATALOGO_LEGITIMOS[rol])
            elif rol == "DESACUERDO_DE_LITROS":
                declarados = max(1.0, litros + rng.choice([-1, 1]) * rng.uniform(2, 18))
                registrar(c, fecha_carga, declarados, max(autorizados, float(round(declarados))))
                self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], rol, "litros",
                                         f"el registro declara {declarados:.2f} L y se cargaron {litros:.2f} L")
            elif rol == "CARGA_SUPERA_AUTORIZADO":
                autorizados = round(litros / rng.uniform(1.15, 1.5), 1)
                registrar(c, fecha_carga, litros, autorizados)
                self._registrar_anomalia("consumo", c["id"], c["vehiculo_id"], rol, "litros",
                                         f"{litros:.2f} L con {autorizados:.1f} L autorizados")
            elif rol == "TOLERANCIA_MEDICION":
                autorizados = round(litros / rng.uniform(1.01, 1.03), 2)
                registrar(c, fecha_carga, litros, autorizados)
                self._registrar_legitimo(c["id"], c["vehiculo_id"], rol,
                                         f"{litros:.2f} L con {autorizados:.2f} L autorizados")
            elif rol == "REGISTRO_REHECHO":
                # Primero un pedido que se anula, después el válido: los dos antes de la carga
                anulado = fecha_carga - timedelta(minutes=rng.randint(95, 180))
                registrar(c, anulado, litros, autorizados, rendido="NO", anulado="SI",
                          etiqueta=("legitimo", rol, CATALOGO_LEGITIMOS[rol]))
                registrar(c, fecha_carga, litros, autorizados)
            elif rol == "TARJETA_PERSONAL":
                registrar(c, fecha_carga, litros, autorizados, personal=True)
                self._registrar_legitimo(c["id"], c["vehiculo_id"], rol, CATALOGO_LEGITIMOS[rol])
            else:
                registrar(c, fecha_carga, litros, autorizados)

        # Registros rendidos sin carga: pedidos de un vehículo en días en que no cargó
        dias_con_carga = set(zip(consumo["vehiculo_id"], pd.to_datetime(consumo["fecha"]).dt.date))
        activos = [c for c in cargas.to_dict("records") if c["id"] not in personales]
        for _ in range(self._cantidad("RENDIDA_SIN_CARGA")):
            base = rng.choice(activos)
            for _intento in range(30):
                dia = pd.Timestamp(base["fecha"]).date() + timedelta(days=rng.randint(1, 6))
                if (base["vehiculo_id"], dia) not in dias_con_carga:
                    break
            fecha_carga = datetime.combine(dia, datetime.min.time()) + timedelta(hours=rng.randint(8, 20))
            registrar(dict(base, odometro=None), fecha_carga, base["litros"], float(round(base["litros"] + 5)),
                      etiqueta=("anomalia", "RENDIDA_SIN_CARGA", "registro rendido sin carga en el reporte"))

        self.datasets["consumo"] = consumo[~consumo["id"].isin(ajenas)].reset_index(drop=True)
        rows.sort(key=lambda r: (r["vehiculo_id"], r["_orden"]))
        for i, r in enumerate(rows, 1):
            r["id"] = f"SOL-{i:08d}"
        for fila, (clase, tipo, detalle) in pendientes_de_id:
            if clase == "legitimo":
                self._registrar_legitimo(fila["id"], fila["vehiculo_id"], tipo, detalle, tabla="solicitudes")
            else:
                self._registrar_anomalia("solicitudes", fila["id"], fila["vehiculo_id"], tipo, "registro", detalle)
        columnas = ["id", "vehiculo_id", "dominio", "fecha", "hora", "odometro", "solicitante", "tarjeta_personal",
                    "litros_autorizados", "litros_cargados", "nivel_tanque", "rendido", "fecha_rendicion",
                    "hora_rendicion", "numero_ticket", "anulado", "fecha_anulado", "estacion_servicio",
                    "bandera_rendicion", "relacion_consumo"]
        df = pd.DataFrame(rows)[columnas]
        df["odometro"] = df["odometro"].astype("Int64")
        self.datasets["solicitudes"] = df
        self.metadata['generadores_ejecutados'].append('solicitudes')
        logger.info(f"✓ REGISTRO INTERNO generado: {len(df)} registros ({len(ajenas)} en estaciones de otra red)")
        return df

    def aplicar_errores_de_carga(self):
        """Realista: errores de carga en el registro interno (#24), con un generador aleatorio propio.

        Son errores humanos que disparan alertas correctas (H8 y, según el caso, H2, H5 o H12) y se
        resuelven citando a quien hizo el pedido:
        - ERROR_PROVEEDOR: el pedido de una carga del reporte se registra como de otra red.
        - ERROR_DOMINIO: el pedido se registra con el dominio de otro vehículo.
        - ERROR_TARJETA: se carga con la tarjeta de otro vehículo; el reporte atribuye la carga, con el
          odómetro del vehículo que cargó, al dueño de la tarjeta. El pedido queda del que cargó.
        Se registran en el ground truth como calidad de datos, sobre la carga y sobre su pedido.
        """
        # Desplazamiento propio: 5_000_003 es el de las contingencias de H13 (PR #25)
        rng = random.Random(self.seed + 6_000_003)
        consumo, solicitudes, flota = self.datasets["consumo"], self.datasets["solicitudes"], self.datasets["flota"]
        etiquetados = {a["id_registro"] for a in self.anomalias} | {c["id_registro"] for c in self.casos_legitimos}
        en_servicio = flota[flota["Estado"] == "EN SERVICIO"].set_index("Matricula")
        # Cada carga con su pedido: mismo vehículo, odómetro y litros, ni anulado ni de otra red
        pedidos = solicitudes[(solicitudes["anulado"] == "NO") & (solicitudes["estacion_servicio"] != ESTACION_AJENA)
                              & ~solicitudes["id"].isin(etiquetados)]
        claves = ["vehiculo_id", "odometro", "litros"]
        unicos = pedidos.assign(litros=pedidos["litros_cargados"]).drop_duplicates(claves, keep=False)
        cargas = consumo[(consumo["tipo_identificacion"] == "PATENTE") & ~consumo["id"].isin(etiquetados)
                         & consumo["vehiculo_id"].isin(en_servicio.index) & consumo["odometro"].notna()]
        pares = (cargas.assign(litros=cargas["litros"].round(2), odometro=cargas["odometro"].astype("Int64"))
                 .drop_duplicates(claves, keep=False)
                 .merge(unicos[claves + ["id"]].rename(columns={"id": "pedido"}), on=claves)[["id", "vehiculo_id", "pedido"]])
        elegidos = rng.sample(list(pares.itertuples(index=False)),
                              k=min(len(pares), sum(max(1, round(n * self.n_flota / 200)) for n in ERRORES_DE_CARGA.values())))
        otros = sorted(en_servicio.index)
        fila_carga = pd.Series(consumo.index, index=consumo["id"])
        fila_pedido = pd.Series(solicitudes.index, index=solicitudes["id"])
        for tipo, n in ERRORES_DE_CARGA.items():
            for _ in range(max(1, round(n * self.n_flota / 200))):
                if not elegidos:
                    break
                carga, vehiculo, pedido = elegidos.pop()
                otro = rng.choice([v for v in otros if v != vehiculo])
                i, j = fila_carga[carga], fila_pedido[pedido]
                if tipo == "ERROR_PROVEEDOR":
                    solicitudes.at[j, "estacion_servicio"] = ESTACION_AJENA
                    detalle = "el pedido se registró como de otra red"
                elif tipo == "ERROR_DOMINIO":
                    solicitudes.at[j, "vehiculo_id"] = otro
                    solicitudes.at[j, "dominio"] = en_servicio.at[otro, "Dominio"]
                    detalle = "el pedido se registró con el dominio de otro vehículo"
                else:
                    consumo.at[i, "vehiculo_id"] = otro
                    consumo.at[i, "dominio"] = en_servicio.at[otro, "Dominio"]
                    consumo.at[i, "numero_tarjeta"] = en_servicio.at[otro, "NumeroTarjeta"]
                    detalle = "se cargó con la tarjeta de otro vehículo"
                self._registrar_anomalia("consumo", carga, consumo.at[i, "vehiculo_id"], tipo, "registro", detalle)
                self._registrar_anomalia("solicitudes", pedido, solicitudes.at[j, "vehiculo_id"], tipo, "registro", detalle)
        self.metadata['generadores_ejecutados'].append('errores_de_carga')

    def _asignar_contratos(self):
        """Cada vehículo (y su tarjeta) pertenece a un contrato. Generador aleatorio propio."""
        self._rng_contratos = random.Random(self.seed + 2_000_003)
        indices = list(range(1, len(REPARTO_CONTRATOS) + 1))
        flota = self.datasets["flota"]
        self._contrato_de = {m: self._rng_contratos.choices(indices, weights=REPARTO_CONTRATOS)[0]
                             for m in flota["Matricula"]}
        flota["NumeroContrato"] = flota["Matricula"].map(self._contrato_de)

    def generar_facturacion_realista(self):
        """FACTURACION por contrato, mes y familia de combustible, con su detalle línea por línea.

        Como en la fuente, el proveedor factura cada contrato a precio de empresa (un 2% menor que
        el del surtidor). Cada factura tiene el monto de la deuda y el total de su PDF (el 15% no
        tiene el PDF cargado); cada línea referencia una carga. Se inyectan líneas sin carga real,
        duplicadas, con sobreprecio o al precio del surtidor, renglones que no son combustible,
        deudas infladas y PDF que no coinciden con la deuda, y casos legítimos: cargas del último
        día del mes facturadas en el período siguiente y facturas con un ajuste documentado.
        """
        logger.info("Generando FACTURACION (escenario realista)...")
        rng = self.rng
        self._asignar_contratos()
        cargas = self._cargas_facturables().copy()
        dominio = self.datasets['flota'].set_index("Matricula")["Dominio"]
        cargas["fecha"] = pd.to_datetime(cargas["fecha"])
        cargas["proveedor"] = cargas["vehiculo_id"].map(self._contrato_de)
        cargas["familia"] = cargas["producto"].str.contains("DIESEL|GASOIL").map({True: "DIESEL", False: "NAFTA"})
        cargas = cargas.sort_values(["fecha", "id"])

        lineas = []
        for c in cargas.itertuples():
            periodo = c.fecha.to_period("M")
            desfase = c.fecha.is_month_end and rng.random() < PROB_DESFASE_DE_CORTE
            precio = round(c.precio_unitario * FACTOR_PRECIO_EMPRESA, 2)
            lineas.append({
                "periodo": periodo + 1 if desfase else periodo, "proveedor": (c.proveedor, c.familia),
                "referencia_consumo": c.id, "concepto": "COMBUSTIBLE", "fecha": c.fecha.date(),
                "dominio": dominio[c.vehiculo_id], "litros": c.litros, "precio_unitario": precio,
                "importe": round(c.litros * precio, 2), "descripcion": "", "_etiqueta": None,
                "_legitimo": "DESFASE_DE_CORTE" if desfase else None, "_vehiculo": c.vehiculo_id,
                "_precio_surtidor": c.precio_unitario,
            })

        # Irregularidades por línea, sobre líneas sin otro caso
        limpias = [i for i, linea in enumerate(lineas) if not linea["_legitimo"]]
        asignacion = self._repartir(limpias, ["SOBREPRECIO", "LINEA_DUPLICADA", "LINEA_SIN_CONSUMO",
                                              "FACTURADA_A_PRECIO_DE_SURTIDOR"])
        extras = []
        for i, rol in sorted(asignacion.items()):
            linea = lineas[i]
            if rol == "FACTURADA_A_PRECIO_DE_SURTIDOR":
                linea["precio_unitario"] = linea["_precio_surtidor"]
                linea["importe"] = round(linea["litros"] * linea["precio_unitario"], 2)
                linea["_etiqueta"] = ("FACTURADA_A_PRECIO_DE_SURTIDOR",
                                      f"{linea['precio_unitario']} por litro: el precio del surtidor, sin el "
                                      f"descuento de empresa")
            elif rol == "SOBREPRECIO":
                original = linea["_precio_surtidor"]
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

        # Renglones que no son combustible (lubricante) en algunas facturas
        grupos = sorted({(linea["periodo"], linea["proveedor"]) for linea in lineas})
        for periodo, proveedor in rng.sample(grupos, min(self._cantidad("PRODUCTO_NO_COMBUSTIBLE"), len(grupos))):
            for _ in range(rng.randint(1, 3)):
                litros = float(rng.choice([4, 8]))
                precio = round(PRECIO_BASE["INFINIA"] * rng.uniform(4, 6), 2)
                lineas.append({
                    "periodo": periodo, "proveedor": proveedor, "referencia_consumo": None, "concepto": "LUBRICANTE",
                    "fecha": periodo.end_time.date(), "dominio": None, "litros": litros, "precio_unitario": precio,
                    "importe": round(litros * precio, 2), "descripcion": "LUBRICANTE 15W40",
                    "_etiqueta": ("PRODUCTO_NO_COMBUSTIBLE", "renglón de lubricante en una factura de combustible"),
                    "_legitimo": None, "_vehiculo": None,
                })

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
        codigo = {g: f"FAC-{g[0].strftime('%Y%m')}-C{g[1][0]}{g[1][1][0]}-{rng.randint(1000, 9999)}" for g in grupos}
        lineas.sort(key=lambda linea: (linea["periodo"], linea["proveedor"], linea["concepto"] != "COMBUSTIBLE",
                                       str(linea["fecha"]), str(linea["referencia_consumo"])))
        for i, linea in enumerate(lineas, 1):
            linea["numero_linea"] = f"LIN-{i:08d}"
            linea["numero_factura"] = codigo[(linea["periodo"], linea["proveedor"])]
            if linea["_etiqueta"]:
                tipo, detalle = linea["_etiqueta"]
                columna = {"SOBREPRECIO": "precio_unitario", "FACTURADA_A_PRECIO_DE_SURTIDOR": "precio_unitario",
                           "PRODUCTO_NO_COMBUSTIBLE": "concepto"}.get(tipo, "referencia_consumo")
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
                "numero_factura": codigo[grupo], "contrato": grupo[1][0], "proveedor": PROVEEDOR_CONTRATO,
                "producto": grupo[1][1], "fecha_factura": grupo[0].end_time.date(),
                "vencimiento": (grupo[0].end_time + timedelta(days=15)).date(), "periodo": str(grupo[0]),
                "total_litros": round(sum(x["litros"] for x in combustible), 2),
                "total_monto": round(sum(x["importe"] for x in propias), 2),
                "estado": rng.choice(["PAGADA", "PENDIENTE", "VENCIDA"]),
                "numero_transacciones": len(combustible),
            })
        # Una factura con un ajuste documentado es un caso legítimo: no puede ser también la inflada
        con_ajuste = {c["id_registro"] for c in self.casos_legitimos if c["tipo_caso"] == "AJUSTE_DOCUMENTADO"}
        sin_ajuste = [f for f in facturas if f["numero_factura"] not in con_ajuste]
        for factura in rng.sample(sin_ajuste, min(self._cantidad("TOTAL_INFLADO"), len(sin_ajuste))):
            real = factura["total_monto"]
            factura["total_monto"] = round(real * rng.uniform(1.03, 1.10), 2)
            self._registrar_anomalia("facturacion", factura["numero_factura"], None, "TOTAL_INFLADO",
                                     "total_monto", f"total {factura['total_monto']} con líneas por {real}")
        # El PDF repite la deuda (también la inflada); el 15% no se cargó y en algunas no coincide
        for factura in facturas:
            factura["total_pdf"] = factura["total_monto"] if rng.random() < PROB_PDF_CARGADO else None
        con_pdf = [f for f in facturas if f["total_pdf"] is not None and
                   not any(a["id_registro"] == f["numero_factura"] for a in self.anomalias)]
        for factura in rng.sample(con_pdf, min(self._cantidad("DIFERENCIA_DEUDA_PDF"), len(con_pdf))):
            factura["total_pdf"] = round(factura["total_monto"] * rng.choice([-1, 1]) * rng.uniform(0.02, 0.08)
                                         + factura["total_monto"], 2)
            self._registrar_anomalia("facturacion", factura["numero_factura"], None, "DIFERENCIA_DEUDA_PDF",
                                     "total_pdf", f"PDF por {factura['total_pdf']} y deuda por {factura['total_monto']}")
        for factura in facturas:
            factura["iva"] = round(factura["total_monto"] * 0.21, 2)
            factura["monto_total_con_iva"] = round(factura["total_monto"] * 1.21, 2)

        columnas_factura = ["numero_factura", "contrato", "proveedor", "producto", "fecha_factura", "vencimiento",
                            "periodo", "total_litros", "total_monto", "total_pdf", "iva", "monto_total_con_iva",
                            "estado", "numero_transacciones"]
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
        """Realista: dominios escritos de otra forma en el reporte del proveedor.

        No son anomalías sino cómo llegan los datos de la fuente. Un dominio con espacios,
        guiones o minúsculas corresponde igual al vehículo: es un caso legítimo que la
        vinculación exacta confunde con un dominio inválido (H1). (Las fechas del registro
        interno llegan en DD/MM/AAAA y las del reporte en AAAA-MM-DD, como en la fuente.)

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

        logger.info(f"✓ Formatos de origen: {len(elegidas)} dominios con otro formato")

    def generar_contratos_realista(self):
        """CONTRATOS y TRANSFERENCIAS: cupo mensual por contrato y transferencias preventivas.

        Cada tarjeta pertenece a un contrato con un tope mensual en pesos; cada carga descuenta del
        saldo del mes. Los lunes y jueves, desde el quinto día del mes, se proyecta el consumo promedio
        diario a fin de mes: si supera el saldo (con margen), se transfiere la diferencia desde el
        contrato con más saldo sobrante (caso legítimo TRANSFERENCIA_DE_SALDO). Si un día no
        alcanzara, se transfiere en el momento. Así el saldo no se agota, salvo en las anomalías:

        - TRANSFERENCIA_SIN_NECESIDAD: transferencia a un contrato cuya proyección alcanzaba.
        - CARGA_CON_CUPO_AGOTADO: una transferencia legítima llega tarde y se carga sin saldo.

        Usa un generador aleatorio propio y se aplica al final: el resto del escenario no cambia.
        """
        rng = self._rng_contratos
        flota, consumo = self.datasets["flota"], self.datasets["consumo"]
        indices = list(range(1, len(REPARTO_CONTRATOS) + 1))
        flota["Cupo"] = flota["CapacidadTanque"]
        flota["LimiteLitros"] = [round(c * rng.uniform(15, 35)) for c in flota["CapacidadTanque"]]
        precio_medio = consumo["precio_unitario"].mean()
        flota["LimiteSaldo"] = [round(ll * precio_medio * rng.uniform(1.0, 1.3), -1) for ll in flota["LimiteLitros"]]
        consumo["contrato"] = consumo["vehiculo_id"].map(self._contrato_de).astype("Int64")

        fechas = pd.to_datetime(consumo["fecha"])
        meses = sorted(fechas.dt.to_period("M").unique())
        por_dia = consumo.assign(dia=fechas.dt.normalize()).groupby(["contrato", "dia"])["importe_total"].sum()
        por_mes = consumo.assign(mes=fechas.dt.to_period("M")).groupby(["contrato", "mes"])["importe_total"].sum()
        completos = [m for m in meses if m != meses[-1]] or meses

        def del_mes(c, m):
            return float(por_mes.get((c, m), 0.0))

        medio = {c: sum(del_mes(c, m) for m in completos) / len(completos) for c in indices}
        maximo = {c: max(del_mes(c, m) for m in completos) for c in indices}
        limites = {c: max(10.0, round(maximo[c] * FACTOR_TOPE_CONTRATO[c - 1], -1)) for c in indices}
        self.datasets["contratos"] = pd.DataFrame({
            "indice": indices, "numero": [f"CTO-{100000 + c:06d}" for c in indices],
            "etiqueta": [f"CONTRATO {c}" for c in indices], "limite_mensual": [limites[c] for c in indices]})

        def del_dia(c, dia):
            return float(por_dia.get((c, dia), 0.0))

        def clave(c, mes):
            return f"CTO-{c}|{mes}"

        # Transferencias innecesarias, decididas antes: a principio de mes, a los contratos-mes con
        # más holgura (los de menor ejecución entre los contratos que sobran)
        holgados = sorted(((c, m) for m in completos for c in indices
                           if FACTOR_TOPE_CONTRATO[c - 1] > 1 and del_mes(c, m) > 0),
                          key=lambda cm: del_mes(*cm) / limites[cm[0]])
        innecesarias = []
        for c, m in holgados[:self._cantidad("TRANSFERENCIA_SIN_NECESIDAD")]:
            donante = max((d for d in indices if d != c), key=lambda d: limites[d] - del_mes(d, m))
            dia = m.start_time + timedelta(days=rng.randint(6, 9))
            innecesarias.append({"fecha": dia, "contrato_origen": donante, "contrato_destino": c,
                                 "monto": round(limites[c] * rng.uniform(0.15, 0.3), -1)})

        transferencias = list(innecesarias)
        for m in meses:
            dias = pd.date_range(m.start_time, m.end_time.normalize(), freq="D")
            saldo = dict(limites)
            consumido = {c: 0.0 for c in indices}
            for n_dia, dia in enumerate(dias, 1):
                for tr in [tr for tr in transferencias if tr["fecha"] == dia]:
                    saldo[tr["contrato_origen"]] -= tr["monto"]
                    saldo[tr["contrato_destino"]] += tr["monto"]
                restantes = len(dias) - n_dia + 1

                def proyeccion(c, conservadora=False):
                    """Consumo que falta hasta fin de mes: promedio del mes combinado con el histórico
                    del contrato (a principio de mes hay pocas cargas). Para ceder saldo se toma el
                    mayor de los dos, así el donante no queda corto."""
                    historico = medio[c] / len(dias)
                    diario = (consumido[c] + historico * DIAS_PESO_HISTORICO) / (n_dia - 1 + DIAS_PESO_HISTORICO)
                    return max(diario, historico) * restantes if conservadora else diario * restantes

                for c in indices:
                    hoy = del_dia(c, dia)
                    en_seguimiento = dia.weekday() in DIAS_DE_SEGUIMIENTO and n_dia > DIA_INICIO_SEGUIMIENTO
                    if (en_seguimiento and proyeccion(c) * MARGEN_PROYECCION > saldo[c]) or hoy > saldo[c]:
                        # Se cubre el resto del mes con holgura, desde el contrato al que más le sobra
                        # según su propia proyección; nunca se lo deja por debajo de ella
                        necesidad = max(proyeccion(c) * MARGEN_PROYECCION, hoy) - saldo[c]
                        sobrante = {d: saldo[d] - proyeccion(d, conservadora=True) * RESERVA_DONANTE
                                    for d in indices if d != c}
                        donante = max(sobrante, key=sobrante.get)
                        monto = round(min(necesidad * 1.3, sobrante[donante]), -1)
                        if monto <= 0:
                            if hoy <= saldo[c]:
                                continue
                            # Hoy no alcanza y a nadie le sobra: cede el que más saldo conserva después de
                            # sus propias cargas del día
                            donante = max((d for d in indices if d != c), key=lambda d: saldo[d] - del_dia(d, dia))
                            monto = round(hoy - saldo[c], -1) + 10
                        transferencias.append({"fecha": dia, "contrato_origen": donante, "contrato_destino": c,
                                               "monto": monto})
                        saldo[donante] -= monto
                        saldo[c] += monto
                for c in indices:
                    hoy = del_dia(c, dia)
                    saldo[c] -= hoy
                    consumido[c] += hoy

        transferencias.sort(key=lambda tr: (tr["fecha"], tr["contrato_destino"]))
        for i, tr in enumerate(transferencias, 1):
            tr["id"] = f"TRF-{i:06d}"
        es_innecesaria = {tr["id"] for tr in innecesarias}
        legitimas = [tr for tr in transferencias if tr["id"] not in es_innecesaria]

        # Una transferencia legítima llega tarde: el contrato carga sin saldo hasta que se acredita
        agotados = set()
        # Nadie revisa el saldo de un contrato ajustado durante un mes: todas sus transferencias
        # llegan de uno a tres días después de que el saldo se agota, y en esos días se carga igual
        candidatas = sorted({(tr["contrato_destino"], tr["fecha"].to_period("M")) for tr in legitimas
                             if FACTOR_TOPE_CONTRATO[tr["contrato_destino"] - 1] < 1})
        rng.shuffle(candidatas)
        for c, mes in candidatas:
            if len(agotados) >= self._cantidad("CARGA_CON_CUPO_AGOTADO"):
                break
            del_contrato = [tr for tr in legitimas if tr["contrato_destino"] == c and tr["fecha"].to_period("M") == mes]
            originales = [tr["fecha"] for tr in del_contrato]
            otras = [tr for tr in transferencias if tr not in del_contrato]
            agotado = self._dia_de_saldo_agotado(c, mes, limites, otras, por_dia)
            if agotado is None:
                continue
            llegada = min(agotado + timedelta(days=rng.randint(1, 3)), mes.end_time.normalize())
            for tr in del_contrato:
                tr["fecha"] = llegada
            if self._cargas_sin_saldo(c, mes, limites, transferencias, por_dia):
                agotados.add(clave(c, mes))
            else:
                for tr, fecha in zip(del_contrato, originales):
                    tr["fecha"] = fecha
        for c_m in sorted(agotados):
            self._registrar_anomalia("contrato_mes", c_m, None, "CARGA_CON_CUPO_AGOTADO", "saldo",
                                     "una transferencia llegó tarde y se cargó con el saldo agotado")
        for tr in innecesarias:
            self._registrar_anomalia("contrato_mes", clave(tr["contrato_destino"], tr["fecha"].to_period("M")), None,
                                     "TRANSFERENCIA_SIN_NECESIDAD", "transferencias",
                                     f"{tr['id']}: la proyección del mes alcanzaba")
        # Un contrato-mes con una anomalía no es además un caso legítimo, aunque reciba transferencias
        anomalos = agotados | {clave(tr["contrato_destino"], tr["fecha"].to_period("M")) for tr in innecesarias}
        for c_m in sorted({clave(tr["contrato_destino"], tr["fecha"].to_period("M")) for tr in legitimas} - anomalos):
            self._registrar_legitimo(c_m, None, "TRANSFERENCIA_DE_SALDO", CATALOGO_LEGITIMOS["TRANSFERENCIA_DE_SALDO"],
                                     tabla="contrato_mes")

        df = pd.DataFrame(sorted(transferencias, key=lambda tr: tr["id"]))[
            ["id", "fecha", "contrato_origen", "contrato_destino", "monto"]]
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
        self.datasets["transferencias"] = df
        self.metadata['generadores_ejecutados'] += ['contratos', 'transferencias']
        logger.info(f"✓ CONTRATOS: {len(indices)} contratos y {len(df)} transferencias "
                    f"({len(innecesarias)} innecesarias, {len(agotados)} contratos-mes con el saldo agotado)")

    @staticmethod
    def _dia_de_saldo_agotado(contrato, mes, limites, transferencias, por_dia):
        """Primer día del mes que el contrato empieza sin saldo y carga, o None."""
        saldo = limites[contrato]
        for dia in pd.date_range(mes.start_time, mes.end_time.normalize(), freq="D"):
            for tr in transferencias:
                if tr["fecha"] == dia:
                    if tr["contrato_destino"] == contrato:
                        saldo += tr["monto"]
                    if tr["contrato_origen"] == contrato:
                        saldo -= tr["monto"]
            hoy = float(por_dia.get((contrato, dia), 0.0))
            if saldo <= 0 and hoy > 0:
                return dia
            saldo -= hoy
        return None

    @classmethod
    def _cargas_sin_saldo(cls, contrato, mes, limites, transferencias, por_dia):
        """Si algún día del mes el contrato empieza con el saldo en cero o menos y carga igual."""
        return cls._dia_de_saldo_agotado(contrato, mes, limites, transferencias, por_dia) is not None

    def aplicar_excepciones_de_odometro(self):
        """Realista: excepciones de odómetro (H12).

        Mientras rige una excepción, la carga repite la última lectura del odómetro (caso legítimo
        ODOMETRO_EXCEPTUADO); al terminar, la lectura vuelve al valor real. Si la lectura se repite
        sin una excepción vigente ese día, es la anomalía ODOMETRO_SIN_AVANCE (en uno de los
        vehículos, porque la excepción ya venció). El padrón muestra el estado de hoy
        (ExcepcionOdometro y FechaHastaExcepcionOdometro) y excepciones_odometro.csv, el historial.
        Solo toma vehículos en servicio sin otras etiquetas y usa un generador aleatorio propio.
        """
        rng = random.Random(self.seed + 4_000_003)
        consumo, flota = self.datasets["consumo"], self.datasets["flota"]
        etiquetados = {a["vehiculo_id"] for a in self.anomalias} | {c["vehiculo_id"] for c in self.casos_legitimos}
        en_servicio = set(flota.loc[flota["Estado"] == "EN SERVICIO", "Matricula"])
        orden = consumo.assign(_fecha=pd.to_datetime(consumo["fecha"])).sort_values(["vehiculo_id", "_fecha", "id"])
        por_vehiculo = {m: list(g.index) for m, g in orden.groupby("vehiculo_id")
                        if m in en_servicio and m not in etiquetados and g["odometro"].notna().all() and len(g) >= 12}
        candidatos = sorted(por_vehiculo)
        rng.shuffle(candidatos)
        cantidad = {k: max(1, round(v * self.n_flota / 200)) for k, v in EXCEPCIONES_ODOMETRO.items()}
        dominio = flota.set_index("Matricula")["Dominio"]
        fecha_de = orden["_fecha"]
        excepciones, vigentes = [], {}

        def congelar(m, desde, hasta):
            """Repite en las cargas desde..hasta (posiciones) la lectura de la carga anterior."""
            indices = por_vehiculo[m]
            lectura = consumo.at[indices[desde - 1], "odometro"]
            for i in indices[desde:hasta + 1]:
                consumo.at[i, "odometro"] = lectura
            return indices[desde:hasta + 1]

        def excepcion(m, inicio, fin, activa):
            excepciones.append({"id": f"EXC-{len(excepciones) + 1:04d}", "patente": dominio[m],
                                "motivo": rng.choice(MOTIVOS_EXCEPCION), "activo": "SI" if activa else "NO",
                                "fecha_creacion": inicio.date().isoformat(), "fecha_hasta": fin.date().isoformat()})

        def etiquetar(m, indices, cubiertas, detalle):
            for i in indices:
                if fecha_de[i] in cubiertas:
                    self._registrar_legitimo(consumo.at[i, "id"], m, "ODOMETRO_EXCEPTUADO",
                                             CATALOGO_LEGITIMOS["ODOMETRO_EXCEPTUADO"])
                else:
                    self._registrar_anomalia("consumo", consumo.at[i, "id"], m, "ODOMETRO_SIN_AVANCE", "odometro",
                                             detalle)

        for m in candidatos[:cantidad["vigente"]]:
            n = len(por_vehiculo[m])
            desde = rng.randint(n // 3, 2 * n // 3)
            indices = congelar(m, desde, n - 1)
            inicio = fecha_de[indices[0]] - timedelta(days=rng.randint(0, 3))
            fin = FECHA_REFERENCIA + timedelta(days=rng.randint(30, 180))
            excepcion(m, inicio, fin, activa=True)
            vigentes[m] = fin
            etiquetar(m, indices, set(fecha_de[indices]), "")

        for k, m in enumerate(candidatos[cantidad["vigente"]:cantidad["vigente"] + cantidad["cumplida"]]):
            n = len(por_vehiculo[m])
            desde = rng.randint(2, n - 4)
            largo = 0 if k == 0 else rng.randint(1, 3)          # la primera, de un solo día y una sola carga
            indices = congelar(m, desde, desde + largo)
            inicio = fecha_de[indices[0]] - (timedelta(0) if largo == 0 else timedelta(days=rng.randint(0, 2)))
            excepcion(m, inicio, fecha_de[indices[-1]], activa=False)
            etiquetar(m, indices, set(fecha_de[indices]), "")

        inicio_sin = cantidad["vigente"] + cantidad["cumplida"]
        for k, m in enumerate(candidatos[inicio_sin:inicio_sin + cantidad["sin_excepcion"]]):
            n = len(por_vehiculo[m])
            desde = rng.randint(2, n - 7)
            indices = congelar(m, desde, desde + rng.randint(2, 5))
            cubiertas = set()
            if k == 0:
                # Tuvo una excepción por la primera carga, pero la lectura se siguió repitiendo después
                excepcion(m, fecha_de[indices[0]], fecha_de[indices[0]], activa=False)
                cubiertas = {fecha_de[indices[0]]}
                detalle = "la lectura se repite después de que venció la excepción"
            else:
                detalle = "la lectura se repite sin excepción de odómetro"
            etiquetar(m, indices, cubiertas, detalle)

        flota["ExcepcionOdometro"] = flota["Matricula"].map(lambda m: "SI" if m in vigentes else "NO")
        flota["FechaHastaExcepcionOdometro"] = flota["Matricula"].map(
            lambda m: vigentes[m].strftime("%d/%m/%Y") if m in vigentes else None)
        self.datasets["excepciones_odometro"] = pd.DataFrame(
            excepciones, columns=["id", "patente", "motivo", "activo", "fecha_creacion", "fecha_hasta"])
        logger.info(f"✓ Excepciones de odómetro: {len(vigentes)} vigentes, {len(excepciones) - len(vigentes)} cumplidas")

    def aplicar_contingencias(self):
        """Realista: origen de cada transacción del reporte y dobles cobros (H13).

        Cada carga llega por el medio de pago habitual (POSNET) o, si este no funciona, por
        contingencia. Casi todas las contingencias son legítimas (caso CONTINGENCIA): la carga se
        registró por la vía alternativa y no se repitió; algunas tienen otra carga del mismo
        vehículo cercana, pero con otros litros. La anomalía DOBLE_COBRO es la misma carga cobrada
        por las dos vías: una segunda transacción de contingencia con los mismos litros (hasta
        1,5% de diferencia) y la misma hora aproximada de una carga por POSNET, sin pedido propio
        en el registro interno. Se factura, así que la conciliación de facturas la ve como una
        línea más con su carga. Usa un generador aleatorio propio y se aplica antes de facturar.
        """
        rng = random.Random(self.seed + 5_000_003)
        consumo = self.datasets["consumo"]
        consumo["origen_transaccion"] = ORIGEN_HABITUAL
        # Tampoco la carga original de un duplicado de nuestro registro
        etiquetadas = ({a["id_registro"] for a in self.anomalias}
                       | {c["id_registro"] for c in self.casos_legitimos}
                       | {a["descripcion"].removeprefix("copia de ") for a in self.anomalias
                          if a["tipo_anomalia"] == "DUPLICADO"})
        instante = pd.to_datetime(consumo["fecha"]) + pd.to_timedelta(consumo["hora"])
        limpias = consumo[~consumo["id"].isin(etiquetadas) & consumo["vehiculo_id"].notna()
                          & consumo["odometro"].notna() & (consumo["tipo_identificacion"] == "PATENTE")]

        # Dobles cobros: copia de una carga limpia, unos minutos después y con litros casi iguales
        originales = sorted(rng.sample(list(limpias.index), self._cantidad("DOBLE_COBRO")))
        siguiente = int(consumo["id"].str.extract(r"(\d+)$", expand=False).astype(int).max()) + 1
        copias = []
        for k, i in enumerate(originales):
            original = consumo.loc[i]
            registro = instante[i] + timedelta(minutes=rng.randint(1, DOBLE_COBRO_MAX_MINUTOS))
            if registro.date() != instante[i].date():          # no cruza la medianoche
                registro = instante[i]
            litros = round(original["litros"] * (1 + rng.uniform(-DOBLE_COBRO_VARIACION_LITROS,
                                                                  DOBLE_COBRO_VARIACION_LITROS)), 2)
            copia = original.copy()
            copia["id"] = f"CONS-{siguiente + k:08d}"
            copia["hora"] = registro.strftime("%H:%M:%S")
            copia["litros"] = litros
            copia["importe_total"] = round(litros * original["precio_unitario"], 2)
            copia["origen_transaccion"] = ORIGEN_CONTINGENCIA
            copias.append(copia)
            self._registrar_anomalia(
                "consumo", copia["id"], original["vehiculo_id"], "DOBLE_COBRO", "origen_transaccion",
                f"la carga {original['id']} se cobró también por contingencia")

        # Contingencias legítimas: una proporción de las cargas; una parte con otra carga del vehículo
        # a menos de 12 horas (pero con otros litros), que la regla ingenua confunde con un doble cobro
        candidatas = limpias[~limpias.index.isin(originales)]
        instantes_de = {v: g for v, g in instante.groupby(consumo["vehiculo_id"])}
        doce_horas = pd.Timedelta(hours=12)
        cercanas = [i for i in candidatas.index
                    if ((instantes_de[consumo.at[i, "vehiculo_id"]] - instante[i]).abs()
                        .between(pd.Timedelta(0), doce_horas, inclusive="neither")).any()]
        n_legitimas = round(PROPORCION_CONTINGENCIA * len(consumo))
        n_cercanas = min(round(CONTINGENCIAS_CERCANAS * n_legitimas), len(cercanas))
        elegidas = rng.sample(cercanas, n_cercanas)
        resto = [i for i in candidatas.index if i not in set(elegidas)]
        elegidas += rng.sample(resto, min(n_legitimas - n_cercanas, len(resto)))
        for i in sorted(elegidas):
            consumo.at[i, "origen_transaccion"] = ORIGEN_CONTINGENCIA
            self._registrar_legitimo(consumo.at[i, "id"], consumo.at[i, "vehiculo_id"], "CONTINGENCIA",
                                     CATALOGO_LEGITIMOS["CONTINGENCIA"])

        consumo = pd.concat([consumo, pd.DataFrame(copias)], ignore_index=True)
        consumo["odometro"] = consumo["odometro"].astype("Int64")
        self.datasets["consumo"] = consumo
        logger.info(f"✓ Contingencias: {len(elegidas)} legítimas, {len(copias)} dobles cobros")

    def aplicar_telemetria_de_bajas(self):
        """Realista: grupo de cada dispositivo y dispositivos de los móviles de baja.

        A un móvil de baja no se le pone telemetría; si la tenía, el dispositivo pasa al grupo de
        depósito (BAJA / REEMPLAZOS) y deja de transmitir (caso legítimo DISPOSITIVO_EN_DEPOSITO).
        Ningún móvil debe ir a desguace con el aparato funcionando: un móvil de baja con el
        dispositivo en un grupo operativo y transmitiendo es la anomalía DISPOSITIVO_ACTIVO_EN_BAJA.
        Usa un generador aleatorio propio y se aplica al final: el resto del escenario no cambia.
        """
        rng = random.Random(self.seed + 3_000_003)
        flota, telemetria = self.datasets["flota"], self.datasets["telemetria"]
        por_dominio = flota.set_index("Dominio")
        estado = telemetria["Placa"].map(por_dominio["Estado"])
        telemetria["Grupo"] = "GRUPO " + telemetria["Placa"].map(por_dominio["Dependencia"]).fillna("SIN DEPENDENCIA")
        de_baja = estado.str.contains("BAJA", na=False)
        telemetria.loc[de_baja, "Grupo"] = GRUPO_DEPOSITO
        telemetria.loc[de_baja, "Estado"] = "OFFLINE"
        telemetria.loc[de_baja, "UltimaConexion"] = [
            (FECHA_REFERENCIA - timedelta(days=rng.randint(30, 300))).isoformat() for _ in range(de_baja.sum())]

        # Móviles de baja con el dispositivo activo: el propio, que nunca se movió al depósito, o uno
        # nuevo instalado en un móvil que ya estaba de baja
        bajas = sorted(flota.loc[flota["Estado"].str.contains("BAJA"), "Dominio"])
        activos = rng.sample(bajas, min(self._cantidad("DISPOSITIVO_ACTIVO_EN_BAJA"), len(bajas)))
        nuevas = []
        for dominio in activos:
            fila = telemetria.index[telemetria["Placa"] == dominio]
            reciente = (FECHA_REFERENCIA - timedelta(minutes=rng.randint(10, 3 * 24 * 60))).isoformat()
            grupo = "GRUPO " + por_dominio.at[dominio, "Dependencia"]
            if len(fila):
                telemetria.loc[fila, ["Grupo", "Estado", "UltimaConexion"]] = [grupo, "ONLINE", reciente]
                alias = telemetria.at[fila[0], "Alias"]
            else:
                alias = f"DEV-{len(telemetria) + len(nuevas) + 1:06d}"
                base = self._perfiles[por_dominio.at[dominio, "Matricula"]]["base"]
                nuevas.append({
                    "IMEI": f"{rng.randint(350000000000000, 359999999999999)}", "Alias": alias, "Placa": dominio,
                    "MSISDN": f"54911{rng.randint(1000000, 9999999)}", "Modelo": f"GPS-A-{rng.randint(1, 5)}",
                    "Tipo": "GPS", "Estado": "ONLINE", "Bateria": round(rng.uniform(60, 100), 1),
                    "UltimaConexion": reciente, "Latitud": round(base[0], 6), "Longitud": round(base[1], 6),
                    "Odometro": int(rng.randint(20000, 250000)), "Grupo": grupo})
            self._registrar_anomalia("telemetria", alias, por_dominio.at[dominio, "Matricula"],
                                     "DISPOSITIVO_ACTIVO_EN_BAJA", "Grupo",
                                     f"móvil de baja con el dispositivo en {grupo}, transmitiendo")
        # Al menos unos pocos dispositivos retirados en depósito, como en la fuente
        con_dispositivo = set(telemetria["Placa"]) | set(activos)
        faltan = max(0, self._cantidad("DISPOSITIVO_EN_DEPOSITO") - int((telemetria["Grupo"] == GRUPO_DEPOSITO).sum()))
        for dominio in rng.sample([b for b in bajas if b not in con_dispositivo], faltan):
            base = self._perfiles[por_dominio.at[dominio, "Matricula"]]["base"]
            nuevas.append({
                "IMEI": f"{rng.randint(350000000000000, 359999999999999)}",
                "Alias": f"DEV-{len(telemetria) + len(nuevas) + 1:06d}", "Placa": dominio,
                "MSISDN": f"54911{rng.randint(1000000, 9999999)}", "Modelo": f"GPS-A-{rng.randint(1, 5)}",
                "Tipo": "GPS", "Estado": "OFFLINE", "Bateria": round(rng.uniform(0, 30), 1),
                "UltimaConexion": (FECHA_REFERENCIA - timedelta(days=rng.randint(30, 300))).isoformat(),
                "Latitud": round(base[0], 6), "Longitud": round(base[1], 6),
                "Odometro": int(rng.randint(20000, 250000)), "Grupo": GRUPO_DEPOSITO})
        if nuevas:
            telemetria = pd.concat([telemetria, pd.DataFrame(nuevas)], ignore_index=True)
        en_deposito = telemetria[telemetria["Grupo"] == GRUPO_DEPOSITO]
        for fila in en_deposito.itertuples():
            self._registrar_legitimo(fila.Alias, por_dominio.at[fila.Placa, "Matricula"], "DISPOSITIVO_EN_DEPOSITO",
                                     CATALOGO_LEGITIMOS["DISPOSITIVO_EN_DEPOSITO"], tabla="telemetria")
        self.datasets["telemetria"] = telemetria
        logger.info(f"✓ Telemetría de bajas: {len(en_deposito)} dispositivos en depósito, "
                    f"{len(activos)} móviles de baja con el dispositivo activo")

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
                self.aplicar_excepciones_de_odometro()
            else:
                self.generar_flota()
                self.generar_telemetria()
                self.generar_consumo()
            if self.escenario == "realista":
                self.generar_solicitudes_realista()
                self.aplicar_contingencias()
                self.aplicar_errores_de_carga()
                self.generar_facturacion_realista()
                self.aplicar_formatos_de_origen()
                self.generar_contratos_realista()
                self.aplicar_telemetria_de_bajas()
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

    # La consola de Windows no siempre usa UTF-8: sin esto, los mensajes con acentos o emojis fallan
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
