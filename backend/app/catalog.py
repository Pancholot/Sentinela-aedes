"""Catálogo base: colonias piloto de Mérida y municipios de Yucatán.

Fuentes:
- Nombres, claves INEGI y coordenadas aproximadas: reales (claves del Marco
  Geoestadístico de INEGI; coordenadas aproximadas del centroide).
- Marginación: grado reportado en el prototipo del equipo (CONAPO).
- Vulnerabilidad (viviendas con tambos), viviendas y parámetros de la
  simulación (huevecillos, IPO, criaderos): datos simulados del prototipo,
  usados para generar la telemetría de la red de ovitrampas IoT que aún no
  existe. El clima se reemplaza con datos reales de Open-Meteo.
"""

# slug, nombre, fila, columna, lat, lon, ipo_actual(%), criaderos/sem,
# tendencia de huevecillos por trampa (4 semanas), vulnerabilidad(%), viviendas
COLONIAS = [
    ("caucel", "Caucel", 1, 1, 21.000, -89.700, 44, 6, (18, 22, 27, 31), 38, 14000),
    ("dzitya", "Dzityá", 1, 2, 21.054, -89.676, 29, 1, (11, 12, 13, 14), 18, 1500),
    ("temozon", "Temozón Norte", 1, 3, 21.060, -89.600, 21, 0, (8, 7, 9, 9), 12, 3500),
    ("cholul", "Cholul", 1, 4, 21.045, -89.555, 33, 2, (10, 12, 14, 15), 16, 4000),
    ("montejo", "Francisco de Montejo", 2, 1, 21.018, -89.655, 46, 4, (17, 21, 24, 28), 22, 9000),
    ("pinos", "Pinos Norte", 2, 2, 21.030, -89.625, 52, 5, (19, 25, 30, 34), 24, 2500),
    ("americas", "Las Américas", 2, 3, 21.045, -89.640, 38, 3, (18, 19, 21, 22), 20, 8000),
    ("chichi", "Chichí Suárez", 2, 4, 21.010, -89.555, 41, 3, (12, 16, 21, 25), 36, 2000),
    ("brisas", "Brisas del Norte", 2, 5, 21.015, -89.578, 58, 7, (20, 27, 35, 41), 26, 3000),
    ("chuburna", "Chuburná", 3, 1, 21.005, -89.645, 30, 1, (11, 12, 12, 13), 18, 6000),
    ("garcia", "García Ginerés", 3, 2, 20.980, -89.640, 19, 0, (7, 8, 8, 8), 8, 4500),
    ("centro", "Centro", 3, 3, 20.967, -89.623, 47, 5, (16, 19, 23, 27), 24, 7000),
    ("itzimna", "Itzimná", 3, 4, 20.995, -89.610, 14, 0, (6, 5, 6, 6), 6, 3000),
    ("poligono", "Polígono 108", 3, 5, 20.990, -89.570, 45, 4, (15, 19, 23, 27), 26, 2500),
    ("bojorquez", "Bojórquez", 4, 1, 20.965, -89.650, 53, 6, (19, 24, 30, 35), 40, 3500),
    ("mulsay", "Mulsay", 4, 2, 20.955, -89.665, 64, 9, (24, 33, 41, 48), 34, 3000),
    ("sansebastian", "San Sebastián", 4, 3, 20.955, -89.627, 50, 5, (18, 23, 28, 32), 28, 4000),
    ("castilla", "Castilla Cámara", 5, 2, 20.940, -89.600, 71, 11, (27, 38, 47, 56), 44, 3500),
    ("tecoh", "San José Tecoh", 5, 3, 20.920, -89.620, 62, 8, (23, 31, 39, 45), 38, 5000),
    ("zapata", "Emiliano Zapata Sur", 5, 4, 20.925, -89.640, 68, 10, (25, 35, 44, 52), 42, 6000),
]

# slug, nombre, clave INEGI, fila, columna, lat, lon, marginación, turístico,
# participación en casos estatales (simulación), nodos IoT, nodos fuera de línea,
# huevecillos por trampa actuales (si tiene nodos), IPO actual, tendencia de casos
MUNICIPIOS = [
    ("celestun", "Celestún", "011", 1, 1, 20.858, -90.400, "Media", True, 0.0020, 0, 0, None, None, -0.25),
    ("progreso", "Progreso", "059", 1, 2, 21.283, -89.663, "Muy baja", True, 0.0245, 0, 0, None, None, -0.05),
    ("motul", "Motul", "052", 1, 3, 21.095, -89.283, "Baja", False, 0.0110, 0, 0, None, None, -0.08),
    ("cansahcab", "Cansahcab", "009", 1, 4, 21.157, -89.102, "Media", False, 0.0150, 10, 1, 33, 49, 0.18),
    ("dzilam", "Dzilam de Bravo", "028", 1, 5, 21.393, -88.892, "Media", False, 0.0095, 10, 0, 31, 46, 0.14),
    ("tizimin", "Tizimín", "096", 1, 6, 21.143, -88.152, "Media", False, 0.0260, 10, 0, 25, 38, 0.0),
    ("hunucma", "Hunucmá", "038", 2, 1, 21.016, -89.877, "Media", False, 0.0090, 0, 0, None, None, -0.10),
    ("merida", "Mérida", "050", 2, 2, 20.967, -89.623, "Muy baja", False, 0.4800, 300, 12, None, None, 0.12),
    ("kanasin", "Kanasín", "041", 2, 3, 20.934, -89.558, "Media", False, 0.0460, 0, 0, None, None, 0.15),
    ("izamal", "Izamal", "040", 2, 4, 20.931, -89.018, "Media", False, 0.0320, 10, 1, 39, 56, 0.25),
    ("buctzotz", "Buctzotz", "006", 2, 5, 21.201, -88.792, "Alta", False, 0.0070, 0, 0, None, None, 0.10),
    ("valladolid", "Valladolid", "102", 2, 6, 20.689, -88.202, "Media", True, 0.0370, 10, 0, 30, 44, 0.05),
    ("maxcanu", "Maxcanú", "048", 3, 1, 20.585, -90.000, "Alta", False, 0.0030, 0, 0, None, None, -0.20),
    ("uman", "Umán", "101", 3, 2, 20.882, -89.747, "Baja", False, 0.0205, 0, 0, None, None, 0.0),
    ("sotuta", "Sotuta", "069", 3, 4, 20.597, -89.008, "Alta", False, 0.0290, 10, 0, 44, 62, 0.35),
    ("tinum", "Tinum", "091", 3, 5, 20.770, -88.393, "Alta", True, 0.0175, 10, 1, 38, 55, 0.25),
    ("ticul", "Ticul", "089", 4, 2, 20.399, -89.535, "Media", False, 0.0135, 10, 0, 24, 36, -0.02),
    ("oxkutzcab", "Oxkutzcab", "056", 4, 3, 20.303, -89.418, "Alta", False, 0.0165, 0, 0, None, None, 0.05),
    ("tekax", "Tekax", "079", 4, 4, 20.204, -89.287, "Alta", False, 0.0190, 10, 1, 29, 43, 0.08),
    ("peto", "Peto", "058", 4, 5, 20.126, -88.922, "Alta", False, 0.0230, 10, 2, 41, 59, 0.30),
    ("tzucacab", "Tzucacab", "098", 4, 6, 20.071, -89.050, "Muy alta", False, 0.0065, 0, 0, None, None, 0.20),
]

# Vulnerabilidad (viviendas con almacenamiento de agua en tambos, % simulado)
VULNERABILIDAD_MUN = {
    "Muy baja": 10, "Baja": 16, "Media": 24, "Alta": 34, "Muy alta": 42,
}
MARG_ORD = {"Muy baja": 0, "Baja": 1, "Media": 2, "Alta": 3, "Muy alta": 4}

ESTADO = ("yucatan", "Yucatán", "31", 20.967, -89.623)

# Textos de las variables explicativas del modelo de riesgo.
DRIVERS_COLONIA = {
    "lluvia": "Lluvia acumulada alta con rezago de 3 a 5 semanas",
    "ipo": "Positividad de ovitrampas en ascenso",
    "huevos": "Huevecillos por trampa por encima de su histórico",
    "vecina": "Colonia vecina en riesgo alto",
    "criaderos": "Criaderos reportados sin atender",
    "calor": "Temperatura mínima elevada",
    "casos": "Casos probables recientes en la colonia",
    "vulner": "Vivienda con almacenamiento de agua en tambos (INEGI)",
}
DRIVERS_MUNICIPIO = {
    "lluvia": "Lluvia acumulada alta con rezago de 3 a 5 semanas",
    "calor": "Temperatura mínima elevada",
    "huevos": "Huevecillos por trampa por encima de su histórico",
    "ipo": "Positividad de ovitrampas en ascenso",
    "casos": "Casos probables en ascenso en el municipio",
    "vecina": "Municipio vecino en riesgo alto",
    "vulner": "Vivienda con almacenamiento de agua en tambos (INEGI)",
    "mov": "Flujo turístico y de trabajadores alto",
}

# Auditoría de sesgos (evaluación del modelo con datos de validación, simulada).
AUDITORIA = [
    ("3er trimestre 2026", "Urbano (Mérida y cabeceras grandes)", 87, 8),
    ("3er trimestre 2026", "Rural", 82, 9),
    ("3er trimestre 2026", "Marginación baja o muy baja", 86, 7),
    ("3er trimestre 2026", "Marginación alta o muy alta", 76, 11),
]
