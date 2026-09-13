# Analytics Cup 2.0: control del espacio ponderado por valor de tiro (scbasket)

## Decisión
Ampliar `scbasket` con su parte analítica: un modelo de CONTROL DEL ESPACIO PONDERADO
POR VALOR DE TIRO ("puntos esperados controlados", EPC) que adapta el pitch control
del fútbol (linaje Spearman / Fernández-Bornn) al baloncesto sobre el open data de
SkillCorner de la Liga ACB 2025-2026.

Sustituye a la decisión anterior del council (54/100: paquete de ingesta y calidad
sin métrica táctica). Lo que ya existe (loader, perfil de calidad, medida del ruido)
no se rehace: es la base. La incertidumbre baja a sección de apoyo (barras de error
del campo de control donde las posiciones son extrapoladas).

La contribución intelectual está en la adaptación, que no es mecánica: en fútbol el
control pregunta quién llegaría antes al balón; en baloncesto el balón casi siempre
está controlado y lo que importa es quién posee las localizaciones que VALEN PUNTOS.
Controlar la esquina de tres no es lo mismo que controlar el medio campo.

Tres diferencias del baloncesto que el modelo trata de forma explícita:
- Pista de 28x15 m con los 10 jugadores siempre a distancia de ayuda: radios de
  influencia pequeños (pies, no metros) y foco en la media pista de ataque.
- Reloj de posesión: presupuesto temporal del control. Entra como tope del horizonte
  de proyección de las velocidades y como dimensión de análisis.
- El aro como foco en vez de una línea de gol: la superficie de valor es radial y
  discontinua (línea de tres), no un gradiente hacia la portería.

### Restricción de diseño que manda sobre todo el plan
10 partidos son unas 2.000 posesiones pero casi un MILLÓN de frames vivos. El proyecto
se apoya en FRAMES, no en posesiones. Prohibido cualquier entregable que sea un ranking
de jugadores: no hay muestra. Las conclusiones son sobre MECANISMOS (zona, rol,
cobertura, reloj, nivel de contestación). Los ids de jugador solo viven en tablas
intermedias, nunca en el README ni en las figuras.

## Bases oficiales (verificadas en el bundle de pysport.org)
- Entrega: 18 dic 2026. Finalistas: 8 ene 2027. Final Europa: 17 feb 2027, París.
- NO hay tracks en la 2.0. Tema sugerido de baloncesto, no obligatorio: **Shot Quality**.
- Criterios, 20% cada uno: Relevance, Methodology, Originality, Communication,
  Open-source potential.
- Individual o pareja (máximo 2). Licencia abierta obligatoria, repo público.
- Entregable: vídeo de 1 minuto con voz propia + repo que funcione out of the box +
  README de máximo 1000 palabras y máximo 2 figuras.
- Premios: 500 euros por finalista, 1.500 al ganador regional como grant para paquete
  Python o PR.
- Solo herramientas open source. Quedan 14 semanas, en solitario y a tiempo parcial
  (unas 110 horas en total).

## Datos verificados

### Las tres capas y el papel de cada una
1. AGREGADOS, 293 partidos, `data/aggregates/acb_shotsaggregates_20252026.csv`, 326
   filas jugador-equipo-temporada (316 jugadores; los traspasados tienen fila por
   equipo más una fila `total`). Papel: estimar la SUPERFICIE DE VALOR (puntos por
   tiro por zona) sobre una temporada entera en vez de sobre 10 partidos. Zonas con
   `_attempts`, `_mades`, `_misses`, `_total_points`: `restricted_area`,
   `paint_non_ra`, `mid_range`, `corner_3` (y `corner_3_left/right`),
   `wing_3_left/right`, `top_3`, `above_break_3`, `backcourt`, `far`, `other`.
   Ojo: `attempts` excluye los fallos con falta (convención FIBA) y `total_points`
   incluye el tiro adicional de los and-one.
2. TRACKING, 10 partidos a 25 fps. Papel: el campo de control frame a frame. En los
   frames vivos están SIEMPRE los 10 jugadores y el balón, al 100% (92.188 frames
   vivos de 124.796 en el partido 114086; el resto son balón muerto, entre el 26% y
   el 55% según partido). Coordenadas en pies, origen en el centro de la pista, x a
   lo largo (media pista = 45,93 ft), y a lo ancho (media anchura = 24,61 ft). Cada
   posición trae `speed` (ft/s, sin dirección), `isDetected` (0/1) y `predError`
   (ft, cuantil 90% del error). El balón trae z real (mediana 3,5 ft, máx 17 ft).
   Detección 76,2%-82,8% por partido; predError medio 0,9 ft en detectadas y
   4,4-5,1 ft en extrapoladas (17-24% de las posiciones).
3. EVENTOS, esos 10 partidos, 20 familias. Papel: VALIDACIÓN EXTERNA, la verdad de
   campo. `shots` trae `contestLevel` (open/light/average/plus/blocked), `shotQuality`
   (0-100, modelo de SkillCorner), `closestDefDist`, `closestDefId`, `location`,
   `region`, `startFrame` (release), `outcome`, `three`, `shotClock`. `picks` trae
   `frame`, `bhrDefType` (none/ice/switch/over/blitz/under) y `scrDefType`
   (none/ice/soft/switch/blitz/show), los ids de ambos defensores y `locationType`.
   `matchups` trae asignaciones defensor-atacante por intervalos
   (`startFrame`/`endFrame`) dentro de cada chance. `possessions` (con `leftHoop`,
   `offTeamId`, `defTeamId`) y `chances` (con `usable`, `transition`,
   `frontcourtFrame`) delimitan las unidades de juego. `touches` da quién tiene el
   balón en cada intervalo.

### Orientación de coordenadas (a verificar en P0.3, no asumido)
La documentación dice que en los eventos el aro atacado está en x negativo, y que
el tracking va en el eje de la cámara. `possessions.leftHoop` indica si el ataque va
al aro izquierdo del broadcast. Hipótesis: el frame de ataque se obtiene con
`(x, y)` si `leftHoop` y `(-x, -y)` si no. Se comprueba contra `shots.location`.

### Correcciones sobre el council, verificadas contra los datos reales
1. La opción "clasificador de cobertura del pick and roll" está MUERTA: los eventos
   `picks` ya traen `bhrDefType` y `scrDefType` con las etiquetas. Aquí esas etiquetas
   se usan al revés: como verdad de campo para validar que el campo de control tiene
   una firma distinta por cobertura.
2. La incertidumbre NO hay que modelarla: cada posición trae `isDetected` y
   `predError` en pies. El trabajo es propagarla, que es ingeniería.
3. El dato defensivo NO falta en los eventos: `matchups`, `closeouts` y los ids de
   ambos defensores en `picks`. Lo que falta son los AGREGADOS de temporada de defensa
   (los CSV de 293 partidos son solo de ataque). La salida "negación de espacio" cubre
   ese hueco declarado del dataset.

### Trabajo previo sobre la contestación (verificado con datos, 1.414 tiros)
"Shot Quality" se apoya en `closestDefDist`, distancia tirador-defensor en el release,
calculada sobre dos posiciones que traen su propio error. Medido:
- Mediana de `closestDefDist`: 3,59 ft. Error combinado medio: 1,85 ft.
- 17,3% de los tiros tienen una distancia menor que su propio error de medición.
- 21,6% tienen defensor más cercano ambiguo (el segundo entra dentro del margen).
- El ruido se concentra donde más pesa: `plus` 26,3%, `blocked` 43,1%, `open` 4,1%.
Validación del cálculo: la distancia recalculada desde el tracking difiere del campo
publicado con mediana 0,000 ft, el 96,5% cae dentro de 0,5 ft y se identifica al mismo
defensor en el 95,1% de los tiros. Esto pasa a ser la sección de apoyo: barras de
error del campo de control (P1.2).

## SPEC

### Arquitectura
Paquete `src/scbasket/`, todo numpy + pandas, sin scipy ni scikit-learn. Cada módulo
nuevo tiene una única responsabilidad y consume los anteriores.

| Módulo | Estado | Responsabilidad | Depende de |
|---|---|---|---|
| `io.py` | existe | Streaming del tracking, eventos con trampas corregidas, `Dataset` | - |
| `quality.py` | existe (+1 función) | Perfil de detección y predError; gana `sigma_from_pred_error` | `io` |
| `court.py` | nuevo | Geometría FIBA en pies, orientación del frame, zonas, rejilla | `quality` (constantes) |
| `value.py` | nuevo | Superficie de valor (puntos por tiro por celda) desde los agregados | `court` |
| `frames.py` | nuevo | Del stream JSON a arrays orientados por partido, con velocidades, poseedor del balón y emparejamientos; caché `.npz` | `io`, `court` |
| `control.py` | nuevo | Campo de control (Fernández-Bornn adaptado), Voronoi de referencia, contrafactuales, Monte Carlo del error | `frames`, `court`, `quality` |
| `epc.py` | nuevo | Puntos esperados controlados: cuota total, por zona, contribución por jugador, serie por chance | `control`, `value` |
| `validation.py` | nuevo | Rasgos en el release, ventanas de pick, métricas de rango (AUC, Spearman, parcial, permutación), calibración | `epc`, `frames` |
| `plotting.py` | nuevo (extra `viz`) | Pista, campo como mapa de calor, series | `court` |

Scripts en `scripts/` (uno por salida, todos con `--root` y `--out`, todos escriben
en `reports/`): `build_value_surface.py`, `build_frame_cache.py`,
`calibrate_control.py`, `validate_release.py`, `space_creation.py`,
`chance_series.py`, `pick_signatures.py`, `make_figures.py`, `run_all.py [--quick]`.

Tests en `tests/`: `conftest.py` con un dataset SINTÉTICO (2 posesiones, 10 jugadores,
unos 300 frames vivos y 100 muertos, y eventos de las familias que se usan) para que
la suite corra sin los 730 MB. Los tests que necesitan datos reales llevan el marcador
`data` y se saltan si no existe `data/raw/opendata-basketball/data/matches.json`.

### Interfaces públicas
```python
# court.py
HOOP_X = -40.76          # aro atacado, ft (FIBA: 1,575 m desde la línea de fondo; ataque hacia -x)
THREE_RADIUS_FT = 22.15  # 6,75 m
CORNER_LINE_Y_FT = 21.65 # banda a 0,90 m
ZONES = ("restricted_area", "paint_non_ra", "mid_range", "corner_3", "wing_3", "top_3",
         "backcourt", "far", "other")
def orient(xy: np.ndarray, left_hoop: bool) -> np.ndarray       # broadcast -> frame de ataque
def zone_of(x: np.ndarray, y: np.ndarray, geom: CourtGeometry = FIBA) -> np.ndarray
def region_to_zone(region: str) -> str                          # 14 regiones de eventos -> 9 zonas
@dataclass(frozen=True)
class Grid: cell_ft: float; centers: np.ndarray  # (G, 2), solo media pista de ataque
             zone: np.ndarray                     # (G,) etiqueta de zona por celda
def make_grid(cell_ft: float = 1.0) -> Grid

# value.py
def league_zone_values(shots_agg: pd.DataFrame) -> dict[str, float]   # PPS por zona, 293 partidos
def player_zone_values(shots_agg, canonical_ids, k: float = 50.0) -> pd.DataFrame  # opcional, P2.4
@dataclass(frozen=True)
class ValueSurface: grid: Grid; values: np.ndarray; zone_values: dict[str, float]
def surface_from_zones(grid: Grid, zone_values: dict, smooth_ft: float = 1.5) -> ValueSurface

# frames.py
@dataclass
class GameFrames:            # un elemento por frame vivo dentro de una chance usable
    game_id: int
    frame_idx, wall_clock, shot_clock, period: np.ndarray        # (N,)
    possession_idx, chance_idx: np.ndarray                       # (N,) índice en las tablas
    off_ids, def_ids: np.ndarray                                 # (N, 5)
    xy: np.ndarray             # (N, 10, 2) orientado al ataque; filas 0-4 ataque, 5-9 defensa
    v: np.ndarray              # (N, 10, 2) velocidad estimada, ft/s
    pred_error: np.ndarray     # (N, 10)
    detected: np.ndarray       # (N, 10) bool
    ball: np.ndarray           # (N, 3)
    ball_holder: np.ndarray    # (N,) índice 0-4 del poseedor (touches) o -1
    matchup: np.ndarray        # (N, 5) índice 0-4 del defensor asignado a cada atacante o -1
def build_game_frames(dataset: Dataset, game_id: int) -> GameFrames
def save_npz(frames, path) -> None;  def load_npz(path) -> GameFrames
def get_or_build(dataset, game_id, cache_dir) -> GameFrames
def subsample(frames, every: int) -> GameFrames
def at_frames(frames, frame_idx: np.ndarray) -> GameFrames

# control.py
@dataclass(frozen=True)
class ControlParams:
    r_near: float = 4.0; r_far: float = 10.0; d_far: float = 30.0  # radio según distancia al balón
    v_max: float = 25.0                                            # ft/s, elongación por velocidad
    t_h: float = 0.3                                               # horizonte de proyección, s
    slope: float = 1.0                                             # pendiente de la sigmoide
def influence(xy, v, ball, shot_clock, points, params) -> np.ndarray  # (B, 10, G)
def control_field(frames, grid, params, batch: int = 64) -> np.ndarray  # (N, G) P_off en [0, 1]
def control_at_points(frames, points, params) -> np.ndarray             # (N,)
def voronoi_field(frames, grid) -> np.ndarray                           # (N, G) referencia
def remove_players(frames, mask) -> GameFrames                          # (N, 10) bool, contrafactuales
def control_with_uncertainty(frames, grid, params, samples=20, rng=None) -> tuple[np.ndarray, np.ndarray]

# quality.py (añadido)
def sigma_from_pred_error(pred_error) -> np.ndarray   # predError / 2.146 (cuantil 90% de una Rayleigh 2D)

# epc.py
def epc_share(p_off, surface) -> np.ndarray                 # (N,) cuota del valor de la pista controlada
def epc_by_zone(p_off, surface) -> pd.DataFrame             # (N x zonas)
def player_contributions(frames, grid, params, surface) -> pd.DataFrame  # frame x jugador: own, created, denied
def chance_series(frames, grid, params, surface, every=5) -> pd.DataFrame

# validation.py
def release_features(frames, shots, grid, params, surface) -> pd.DataFrame
def rank_auc(score, label) -> float
def spearman(a, b) -> float;  def partial_spearman(y, x, z) -> float
def permutation_pvalue(stat, groups, n=2000, rng=None) -> float
def calibrate(frames_by_game, shots_by_game, grid, surface, param_grid) -> pd.DataFrame
def pick_windows(frames, picks, grid, params, surface, before_s=1.0, after_s=2.0) -> pd.DataFrame
def break_points(series, shots, actions) -> pd.DataFrame
```

### Decisiones de modelado
- D1. Forma del control: Fernández-Bornn (2018). Cada jugador i ejerce una influencia
  gaussiana bivariante centrada en su posición proyectada, alargada en la dirección de
  su velocidad, con radio según su distancia al balón; el control de ataque en una
  celda es `sigmoide(slope * (sum_off I_i - sum_def I_i))`. Elegido porque pregunta
  quién posee el espacio, no quién llega al balón (que en baloncesto está poseído), y
  porque sus ingredientes vienen en el tracking. Descartados: Voronoi (queda como
  referencia a batir), Spearman completo con tiempo de intercepción (requiere
  aceleraciones, y derivar dos veces posiciones con 4,5 ft de error es ruido), modelos
  aprendidos (sin verdad de campo de "control" y con 10 partidos no hay muestra).
- D2. Radios en pies, no en metros: `r_near` = 4 ft junto al balón, `r_far` = 10 ft a
  30 ft o más del balón, interpolación lineal. Justificación: fútbol usa 4-10 m; la
  pista es 3,6 veces más corta y todo el mundo está a distancia de ayuda. Los valores
  son iniciales: se calibran en P1.4 contra `contestLevel`, nunca a ojo.
- D3. Tiempo y reloj de posesión: la posición se proyecta `t_h` segundos (0,3 s de
  partida, calibrado) a lo largo de la velocidad; el horizonte se recorta a
  `min(t_h, shotClock)`, de modo que con el reloj agotado el control es puramente
  posicional. El reloj es además dimensión de análisis (tramos 24-16, 16-8, 8-0 s).
  Descartado: horizonte por celda igual al tiempo de vuelo del pase (añade `v_pass`,
  que no se puede calibrar por separado de `t_h` con 10 partidos).
- D4. Rejilla: 1 ft, solo media pista de ataque (46 x 49, unas 2.250 celdas). Una
  celda de 1 ft está al nivel del error de las posiciones detectadas (0,9 ft); más
  fino es fingir precisión. 2 ft es demasiado grueso para la franja de la esquina de
  tres (3 ft entre la línea y la banda). `--quick` usa 2 ft.
- D5. Superficie de valor: constante por zona con los agregados de 293 partidos,
  `PPS_zona = sum(zone_total_points) / sum(zone_attempts)` sobre filas con
  `team_name != 'total'`; izquierda y derecha se funden (la liga es simétrica);
  `backcourt`, `far` y `other` valen 0; suavizado gaussiano de 1,5 ft en las fronteras
  para no crear escalones artificiales en el campo. Descartados: ajustar una
  superficie continua con los 1.414 tiros de los 10 partidos (poca muestra), ponderar
  por frecuencia de tiro (confunde uso con valor), un modelo xP propio (no hace falta,
  el valor de zona ya viene de la temporada entera).
- D6. Métrica cabecera: `epc_share = sum_c P_off(c) V(c) / sum_c V(c)`, cuota del valor
  de la pista bajo control del ataque, en [0, 1], y su descomposición por zona.
  Comunicable ("el ataque controla el 38% del valor; tras el bloqueo sube al 52%,
  casi todo en el lado débil") y sin unidades raras (puntos por pie cuadrado).
- D7. Contrafactuales por jugador (cada uno un frame sin ese jugador):
  - `own_j`: valor de las celdas donde j es el atacante con mayor influencia.
  - `created_j` (creación sin balón): cambio del valor controlado por los COMPAÑEROS
    (celdas donde j no domina) al quitar a j y a su defensor asignado (`matchups`;
    si no hay asignación, el defensor más cercano). Puede ser negativo: un no tirador
    cuyo defensor ayuda dentro cuesta espacio a sus compañeros. Se calcula solo en
    frames donde j no es el poseedor del balón.
  - `denied_k` (negación): subida del valor controlado por el ataque al quitar al
    defensor k. Es monótono no negativo por construcción.
  Limitación declarada en el README: el contrafactual es estático (no sabe dónde
  estaría el defensor si j no fuese amenaza); por eso el análisis mira también la
  DINÁMICA (cómo cambia `created_j` durante cortes y bloqueos indirectos).
- D8. Incertidumbre: perturbación Monte Carlo de las posiciones con
  `sigma = predError / 2.146` (para un error 2D isótropo, el cuantil 90% del radio
  es 2,146 sigma), K = 20 muestras, solo en los frames de evento (release, picks),
  no en el millón de frames. Sustituye la cota heurística de ambigüedad del trabajo
  previo. Reutiliza `quality.py`, no lo duplica.
- D9. Muestreo temporal: 5 Hz (uno de cada cinco frames) para series y agregados; los
  frames consecutivos a 25 Hz están autocorrelados y no añaden información. 25 Hz
  solo en los frames de evento.
- D10. Velocidad: diferencia centrada sobre ±2 frames de posiciones suavizadas con
  media móvil de 5 frames, calculada sobre los arrays cacheados (respetando cortes
  de posesión y saltos de `frameIdx`), acotada a 30 ft/s. El `speed` del proveedor
  sirve de comprobación (correlación esperada ≥ 0,9), no de entrada: no trae
  dirección. Descartado: Kalman (sobreingeniería).
- D11. Calibración y validación separadas por PARTIDO. Calibran los 5 más antiguos
  por fecha (114243, 114234, 114169, 114099, 114086); validan los 5 restantes
  (178442, 179612, 184439, 188630, 191313). Los parámetros se congelan en
  `reports/control_params.json` con el hash del commit ANTES de tocar los partidos de
  validación. Todos los números del README salen de los partidos reservados.
- D12. Frames que entran: vivos, dentro de una `chance` con `usable == True`, con
  `shotClock` no nulo y con 5 + 5 jugadores. Se imprime cuántos se descartan y por qué.
- D13. Umbrales de validación PRE-REGISTRADOS (P1.5). Si no se alcanzan, se reporta
  como hallazgo y se PARA a replanificar; no se ajustan los umbrales al resultado.

### Convenciones
- Unidades: pies y segundos en todo el paquete. Frame de ataque: el aro atacado en
  `(HOOP_X, 0)`, ataque hacia x negativo, lado izquierdo del ataque en y positivo.
- Todo cálculo sobre frames es vectorizado por lotes (`batch` frames a la vez) sobre
  arrays `(N, 10, 2)`; nunca un bucle en Python por frame dentro del modelo.
- Nada del paquete lee el tracking dos veces: `frames.py` lo convierte una vez a
  `.npz` por partido en `data/interim/` (ignorado por git).
- Estilo: el de `io.py` y `quality.py` (docstrings en castellano sin tildes en el
  código, `from __future__ import annotations`, líneas ≤ 100). Ruff con `E, F, I, B, UP`.
- Tests: por módulo, camino feliz más dos casos límite. No hay UI, así que no aplica
  Playwright.

## Fases y tareas

Modo de ejecución elegido por el usuario el 2026-09-13: **mixto según plan**. Cada
tarea se ejecuta con el modelo de su etiqueta, `sonnet` o `PLANNER` (Fable 5.1).

Calendario comprimido a 12 semanas por decisión del usuario, dejando las semanas 13 y
14 como reserva ante el escenario de que un umbral pre-registrado falle en F1 y obligue
a replanificar. Coste de la compresión: la carga semanal sube de unas 7,5 h a unas
8,4 h. Reparto de horas (unas 101): F0 12 h, F1 30 h, F2 18 h, F3 18 h, F4 15 h, V 8 h.
Las tareas `[opcional]` quedan fuera salvo que una fase cierre antes de plazo.

### F0. Cimientos verificables (semanas 1-2)
Objetivo cerrado: suite de tests y lint en verde, geometría validada contra las
etiquetas del proveedor, y la superficie de valor de liga escrita en `reports/`.

- [ ] P0.1 Infraestructura de tests y lint `[sonnet]`
  - Hace: `ruff` en el extra `dev` con la config de arriba; `tests/conftest.py` con el
    dataset sintético (fixture `synthetic_root` que crea `matches.json`,
    `player_id_aliases.csv` y un partido con los tres ficheros; incluye 2 posesiones
    con `leftHoop` distinto, 2 `shots`, 1 `pick`, 1 `off_ball_screen`, `matchups`,
    `touches`, `chances` con `usable`); marcador `data` con `skipif` si no está el
    dataset real; tres tests de humo sobre `io.py`.
  - Acepta: `uv run pytest -q` en verde con ≥ 3 tests sin datos reales;
    `uv run ruff check .` con 0 errores (corrige lo trivial que salga en el código
    existente, sin refactorizar).
- [ ] P0.2 Geometría de pista y clasificador de zonas `[sonnet]`
  - Hace: `court.py` con la geometría FIBA en pies, `zone_of`, `region_to_zone`,
    `make_grid`. El radio de la `restricted_area` y las fronteras angulares
    esquina/ala/frontal no están documentadas: se ajustan por búsqueda en rejilla
    (radio 3-6 ft, ángulos) maximizando el acuerdo con `shots.region` de los 10
    partidos, y los valores ajustados quedan como constantes con el acuerdo anotado.
  - Acepta: acuerdo `zone_of(location)` contra `region_to_zone(region)` ≥ 95% sobre
    los 1.414 tiros (test con marcador `data` que imprime el número); acuerdo con
    `three` ≥ 99%; 6 puntos conocidos en un test unitario (aro, esquina de tres,
    frontal de tres, codo, backcourt, fuera de pista).
- [ ] P0.3 Orientación del tracking `[sonnet]`
  - Hace: `orient` en `court.py`; script corto que, para cada tiro, compara la posición
    del tirador en el tracking en `startFrame` (orientada con el `leftHoop` de su
    posesión) contra `shots.location` bajo las dos hipótesis de giro.
  - Acepta: exactamente una hipótesis tiene ≥ 99% de tiros con diferencia < 0,5 ft;
    esa hipótesis y su número quedan en el docstring de `orient` y en un test `data`.
- [ ] P0.4 Superficie de valor de liga `[sonnet]`
  - Hace: `value.py` (`league_zone_values`, `surface_from_zones`) y
    `scripts/build_value_surface.py`, que escribe `reports/value_surface_zones.csv`
    (zona, intentos, puntos, PPS) y `reports/value_surface_grid.csv`.
  - Acepta: 6 zonas con valor; `restricted_area` es la máxima y `mid_range` la mínima;
    todas en [0,5, 1,6] puntos por tiro; la suma de intentos por zona cuadra con
    `attempts` de las mismas filas con desviación < 1%; test unitario con agregados
    sintéticos (incluida una fila `total` que NO debe contarse) y test de que la
    superficie suavizada integra igual que la escalonada (< 1e-6 relativo).
- [ ] P0.5 Arrays por partido con caché `[PLANNER]`
  - Hace: `frames.py` completo (`build_game_frames`, velocidades D10, poseedor desde
    `touches` con respaldo al atacante más cercano al balón a < 3 ft, `matchup` desde
    `matchups` por intervalos, filtros D12) y `scripts/build_frame_cache.py` que deja
    `data/interim/{gid}_frames.npz` para los 10 partidos.
  - Acepta: para 114086 se leen 92.188 frames vivos y se imprime cuántos quedan tras
    D12 y por qué motivo se descarta el resto; cada fila tiene 5 + 5 jugadores; el
    módulo de la velocidad estimada contra `speed` del proveedor tiene Pearson ≥ 0,9
    en posiciones detectadas; cobertura de `matchup` impresa (si < 80%, se documenta
    y se usa el respaldo); construcción ≤ 3 min por partido; `.npz` ≤ 50 MB por
    partido y carga ≤ 2 s; tests unitarios sobre el sintético: orientación por
    posesión, velocidad de un jugador en línea recta (error < 1%), poseedor,
    `subsample` y `at_frames`.

### F1. Campo de control y validación en el release (semanas 3-6)
Objetivo cerrado: el modelo calibrado en 5 partidos y VALIDADO en los otros 5 contra
`contestLevel` y `shotQuality`, con barras de error. Primera demo del proyecto.

- [ ] P1.1 Modelo de control `[PLANNER]`
  - Hace: `control.py` con `influence` (forma cuadrática 2x2 analítica, sin
    `np.linalg`), `control_field` por lotes, `control_at_points`, `voronoi_field`,
    `remove_players`.
  - Acepta: tests: `P_off` en [0, 1]; simetría al intercambiar equipos
    (`|P + P' - 1| < 1e-9`); un atacante solo contra nadie da `P > 0,99` en su
    posición; con radios → 0 coincide con Voronoi en ≥ 99% de celdas; lote de 1 y de
    64 dan arrays idénticos; con `shotClock = 0` el resultado no depende de `v`.
    Rendimiento: un partido a 5 Hz con rejilla de 1 ft ≤ 2 min sobre el `.npz`
    (tiempo impreso por un test `data`).
- [ ] P1.2 Incertidumbre por Monte Carlo `[sonnet]`
  - Hace: `sigma_from_pred_error` en `quality.py`; `control_with_uncertainty`;
    columna `p_off_std` en los rasgos de release. Sustituye la cota heurística de
    `scripts/shot_contest_uncertainty.py` por la perturbación (el script pasa a
    escribir además `p_off_mean`, `p_off_std` y si la diferencia entre niveles de
    contestación consecutivos cae dentro de la desviación).
  - Acepta: tests: con `predError = 0` la desviación es 0; con 200 muestras la media
    dista < 0,02 del campo determinista en el sintético; misma semilla, mismo
    resultado. El informe imprime qué fracción de tiros `plus` y `blocked` tiene
    `p_off_std` mayor que la distancia a la mediana del nivel vecino.
- [ ] P1.3 Rasgos en el release y métricas de rango `[sonnet]`
  - Hace: `release_features` (P_off en la posición del tirador, media en disco de
    3 ft, `epc_share`, Voronoi en el tirador, `closestDefDist` recalculada, más las
    columnas de `shots` necesarias), `rank_auc`, `spearman`, `partial_spearman`
    (residuos de rangos), `permutation_pvalue`.
  - Acepta: 1.414 tiros emparejados (mismo número que el script previo); tests:
    `rank_auc` da 1,0 con separación perfecta y 0,5 ± 0,05 con etiquetas aleatorias
    (n = 2.000, semilla fija); `spearman` coincide con pandas (< 1e-12);
    `partial_spearman(y, x, z)` es 0 (± 0,05) cuando `y` depende solo de `z`.
- [ ] P1.4 Calibración en los 5 partidos antiguos `[PLANNER]`
  - Hace: `calibrate` y `scripts/calibrate_control.py`: rejilla `r_near` ∈ {3,4,5,6},
    `r_far` ∈ {8,10,12,14}, `slope` ∈ {0,5, 1, 2}, `t_h` ∈ {0, 0,3, 0,6} (144
    combinaciones) sobre los frames de release de los partidos de calibración;
    objetivo = AUC(open contra contested) + Spearman(shotQuality) de `P_off` en el
    tirador. Los parámetros elegidos se congelan en `reports/control_params.json`
    con el hash del commit.
  - Acepta: `reports/calibration_grid.csv` con 144 filas; el óptimo no está en el
    borde de la rejilla en ninguna dimensión (si lo está, se amplía y se repite);
    commit del json ANTES de ejecutar nada sobre los partidos de validación.
- [ ] P1.5 Validación en los 5 partidos reservados `[PLANNER]`
  - Hace: `scripts/validate_release.py` con los parámetros congelados. Escribe
    `reports/validation_release.csv` (una fila por métrica y modelo: control,
    Voronoi, `closestDefDist`) e imprime la tabla de medianas por `contestLevel`.
  - Acepta (umbrales pre-registrados, D13): AUC(open contra contested) de `P_off` en
    el tirador ≥ 0,80 y ≥ AUC de Voronoi + 0,03; medianas monótonas en los 5 niveles
    open > light > average > plus > blocked; Spearman con `shotQuality` ≥ 0,30;
    Spearman parcial con `shotQuality` controlando `closestDefDist` > 0 con p < 0,01
    por permutación (2.000 barajados). Este último es el argumento de Methodology:
    el campo aporta información que la distancia al defensor más cercano no tiene
    (velocidades y segundo defensor). Si falla un umbral: se escribe tal cual en el
    informe y se PARA a replanificar antes de F2.

### F2. Puntos esperados controlados y contrafactuales (semanas 7-8)
Objetivo cerrado: las salidas 1 (creación) y 2 (negación) como tablas por mecanismo.

- [ ] P2.1 EPC y descomposición por zona `[sonnet]`
  - Hace: `epc.py` con `epc_share` y `epc_by_zone`.
  - Acepta: tests: `P_off = 1` da cuota 1 y `P_off = 0` da 0; las zonas suman el
    total (< 1e-9); en un partido real la cuota media de los frames vivos cae en
    [0,3, 0,7] (impresa, sanidad).
- [ ] P2.2 Contrafactuales por jugador `[PLANNER]`
  - Hace: `player_contributions` según D7 (own, created, denied) usando
    `remove_players`, `matchup` y `ball_holder`.
  - Acepta: tests: `sum_j own_j == epc_share` (< 1e-9, dominancia particiona las
    celdas); `denied_k ≥ 0` en todos los frames del sintético (monotonía exacta);
    `created_j` es NaN cuando j tiene el balón; el coste total ≤ 6 veces el del
    campo base (11 campos por frame, medido e impreso).
- [ ] P2.3 Mecanismos de creación y negación `[sonnet]`
  - Hace: `scripts/space_creation.py`. Agrega `created` y `denied` (5 Hz, 10
    partidos) por rol del jugador en el frame (poseedor, bloqueador o cortador según
    las ventanas de `picks` y `off_ball_screens`, y si no, espaciador), por zona del
    jugador, por tramo de reloj de posesión y por distancia a su defensor (tramos de
    3 ft). Salidas: `reports/space_creation_by_role.csv`,
    `reports/space_denial_by_zone.csv`. Sin columnas de id de jugador.
  - Acepta: comprobación de sanidad con verdad de campo: alrededor de los bloqueos
    indirectos (`off_ball_screens`), el `created` del que bloquea sube entre la
    ventana [-2 s, 0] y la ventana [0, +2 s] con p < 0,05 por permutación; el
    defensor del poseedor niega más valor que los defensores del lado débil (media
    impresa). Si una sanidad falla, se reporta como hallazgo con su número.
- [ ] P2.4 `[opcional]` Superficie de valor por jugador `[PLANNER]`
  - Hace: `player_zone_values` con shrinkage hacia la liga (`k = 50` intentos,
    ids canonizados con `Dataset.canonical_ids`, sumando filas por equipo); el valor
    de una celda pasa a ser la mezcla de los valores de los atacantes ponderada por
    su influencia. Repite las métricas de P1.5 con esta superficie.
  - Acepta: fila `surface = player` en `reports/validation_release.csv`; se conserva
    en el paquete solo si la Spearman con `shotQuality` mejora ≥ 0,02 en los
    partidos reservados; si no, queda como función documentada y no como default.

### F3. La posesión como serie temporal (semanas 9-10)
Objetivo cerrado: salida 3 (dónde y cuándo se rompe una defensa) y la segunda
validación externa (firmas del pick and roll por cobertura).

- [ ] P3.1 Series por chance `[sonnet]`
  - Hace: `chance_series` a 5 Hz y `scripts/chance_series.py`, que cachea
    `data/interim/{gid}_series.csv` (chance, frame, segundos hasta el final,
    `shot_clock`, `epc_share`, cuota en pintura, en media distancia, en triples, y
    `P_off` en el balón).
  - Acepta: una fila por (chance, frame muestreado), recuento igual al de
    `subsample(frames, 5)`; los 10 partidos en ≤ 15 min; test en el sintético de
    que la serie respeta los límites de chance.
- [ ] P3.2 Trayectorias alineadas al release `[sonnet]`
  - Hace: media de `epc_share` en [-4 s, 0] por `contestLevel` con bandas bootstrap
    del 95% remuestreando por chance. Escribe `reports/release_trajectories.csv`.
  - Acepta: en t = 0 la diferencia open menos blocked es positiva con intervalo que
    excluye 0 (esperado; si no, se reporta). Tabla impresa con los 5 niveles.
- [ ] P3.3 Punto de ruptura y atribución a acciones `[PLANNER]`
  - Hace: `break_points`: en cada chance que acaba en tiro, el mayor incremento de
    `epc_share` en 1 s dentro de los últimos 4 s; se atribuye a la acción cuya
    ventana lo contiene (`picks`, `drives`, `handoffs`, `off_ball_screens`,
    `isolations`, `posts`, con orden de prioridad documentado) o a "ninguna".
    Escribe `reports/break_points.csv` y la tabla acción x segundos antes del tiro
    x zona donde sube el control.
  - Acepta: ≥ 60% de las chances con tiro tienen ruptura atribuida a una acción (si
    no, se reporta el número tal cual); test en el sintético con una subida
    construida a mano que se atribuye al pick.
- [ ] P3.4 Firmas de control del pick and roll `[PLANNER]`
  - Hace: `pick_windows` en [-1 s, +2 s] a 5 Hz alrededor de `picks.frame`, en
    coordenadas locales (espejo en y para que el lado del bloqueo sea positivo);
    rasgos por instante: `epc_share`, cuota en pintura, cuota en triples del lado
    del balón y del lado débil, `P_off` en el poseedor, en el bloqueador y en el
    carril de continuación (segmento bloqueador-aro). Firma = trayectoria media por
    `bhrDefType` (over, under, switch, ice, blitz) y por `scrDefType` (soft, show,
    switch, blitz, ice) con bandas bootstrap. Prueba: clasificador de centroide más
    cercano con validación dejando un partido fuera contra la clase mayoritaria, y
    permutación de la distancia entre centroides. Escribe `reports/pick_signatures.csv`.
  - Acepta: acierto ≥ mayoritaria + 10 puntos; p < 0,01 en al menos 3 de las 5
    coberturas del poseedor contra el resto; ≥ 1.000 picks con cobertura etiquetada
    y frame en caché (impreso).

### F4. Comunicación y paquete (semanas 11-12)
Objetivo cerrado: repo público reproducible, README dentro de límites, guion del vídeo.

- [ ] P4.1 Figuras `[sonnet]`
  - Hace: `plotting.py` (extra `viz` con matplotlib) y `scripts/make_figures.py`.
    Figura 1: campo ponderado por valor en un frame de pick and roll con la serie
    `epc_share` de esa chance debajo y la banda de incertidumbre. Figura 2: firmas
    por cobertura (P3.4) o trayectorias por contestación (P3.2), la que tenga el
    resultado más claro. Ambas generadas desde ficheros de `reports/`.
  - Acepta: exactamente 2 PNG en `reports/figures/`, ≤ 300 KB cada uno, con la
    fuente de datos en el pie; `uv run python scripts/make_figures.py` las regenera.
- [ ] P4.2 `run_all` y reproducibilidad `[sonnet]`
  - Hace: `scripts/run_all.py` encadena caché, valor, calibración (solo si no existe
    el json congelado), validación, creación, series, picks y figuras; `--quick`
    usa 2 partidos y rejilla de 2 ft; escribe `reports/summary.json` con cada
    número que cita el README.
  - Acepta: en un clon limpio, `uv sync --all-extras`, `uv run python
    scripts/fetch_data.py`, `uv run python scripts/run_all.py --quick` termina en
    ≤ 10 min; la ejecución completa reproduce `reports/summary.json` con
    diferencias < 1e-6 respecto al committeado.
- [ ] P4.3 README de máximo 1000 palabras `[PLANNER]`
  - Hace: estructura por los 5 criterios (qué pregunta, por qué frames y no
    posesiones, el modelo en 5 líneas, la validación externa con sus números, las
    tres salidas por mecanismo, la incertidumbre como apoyo, limitaciones: contrafactual
    estático, valor de liga y no de jugador, 10 partidos; cómo reproducir; cómo
    contribuir). Pasada de `/humanizer`.
  - Acepta: `wc -w README.md` ≤ 1000; ≤ 2 imágenes referenciadas; cada número del
    README existe en `reports/summary.json`; ningún nombre ni id de jugador.
- [ ] P4.4 Guion del vídeo de 1 minuto `[sonnet]`
  - Hace: `docs/video_script.md` con 6 planos de 10 s (pregunta, dato, modelo,
    validación, hallazgo, repo) y el texto a locutar.
  - Acepta: ≤ 160 palabras locutadas; cada plano señala qué figura o pantalla se ve.
- [ ] P4.5 Publicación `[sonnet]`
  - Hace: nombre público del paquete decidido, metadatos de `pyproject.toml`,
    `CITATION.cff`, LICENSE MIT ya existe, etiqueta `v0.2.0`, repo público.
  - Acepta: `uv build` produce wheel y sdist; el clon limpio de P4.2 se repite desde
    la URL pública.

### V. Verificación (semana 12; semanas 13-14 de reserva)
- [ ] V. Verificación
  - Comandos exactos del gate, en este orden y todos en verde:
    ```
    uv sync --all-extras
    uv run ruff check .
    uv run pytest -q                      # sin datos: los `data` se saltan
    uv run pytest -q -m data              # con el dataset en data/raw
    uv run python scripts/run_all.py --quick
    uv run python scripts/run_all.py      # completa; compara reports/summary.json con el committeado
    wc -w README.md                       # ≤ 1000
    grep -c '!\[' README.md               # ≤ 2
    grep -ci 'player' reports/summary.json   # 0: nada citado en el README va por jugador
    git clone <url pública> /tmp/scb && cd /tmp/scb && uv sync --all-extras && uv run pytest -q
    ```
  - Criterio de aceptación agregado: todos los "Acepta" de P0.1 a P4.5 cumplidos o,
    en los casos de umbral (P1.5, P2.3, P3.2, P3.3, P3.4), reportados como hallazgo
    con su número y sin haber tocado el umbral; los parámetros del modelo son los
    congelados en `reports/control_params.json` y su hash es anterior a cualquier
    ejecución sobre los partidos de validación (`git log` del fichero); ningún
    entregable es un ranking de jugadores; el trabajo previo de incertidumbre queda
    integrado (P1.2) y no duplicado.
  - Revisión adversarial: lanzar el subagente `revisor-adversarial` con
    `git diff bf47b73..HEAD` completo y la lista de "Acepta" de este fichero. Debe
    devolver la sección "Rompe" vacía; cada punto que devuelva se corrige y se
    vuelve a lanzar hasta que esté vacía. Después, `/simplify` sobre el diff y
    `/verification-before-completion`.

## Fuera de alcance (no cabe en 14 semanas a tiempo parcial, dicho aquí y no con calzador)
- Modelo de Spearman completo con tiempo de intercepción y aceleraciones.
- Modelos de control aprendidos (redes, gradient boosting) o un EPV de posesión
  completa: sin verdad de campo y sin muestra.
- Cualquier ranking o ficha de jugador, incluida la "gravedad" individual como
  número de temporada: el dato son 10 partidos.
- Agregados defensivos de temporada: no hay tracking de los otros 283 partidos.
- Superficie de valor continua o dependiente del tipo de tiro; solo constante por
  zona (y por jugador con shrinkage si entra P2.4).
- Uso del z del balón, vuelo de pases, modelado de rebotes.
- Análisis específico de transición: los frames de transición entran con su etiqueta
  `transition` pero no tienen fase propia.
- Integración en kloppy, DataballPy o similares: se menciona en el README como
  siguiente paso y posible destino del grant, no se hace.
- Dashboard, app web o vídeo animado del campo: el vídeo lo graba el autor con las
  figuras estáticas.

## Decisiones abiertas
- Nombre público del paquete. Nombre de trabajo `scbasket`. Se decide en P4.5.
- Solo o en pareja: el plan asume solitario; si entra pareja, F2 y F3 se paralelizan.
- Figura 2 (P4.1): se elige con los números en la mano, no antes.

## Avisos
- El repo padre `data_engineer` tiene 119 borrados sin commitear: el proyecto anterior
  se movió a `feb_platform/`. No tocar ni commitear eso sin preguntar.
- El proyecto vive en `C:\Users\javie\Desktop\proyectos\skillcorner_basket_data`, no
  bajo `data_engineer/` (ahí solo queda una carpeta vacía con el mismo nombre).
- `data/interim/` y `reports/figures/` ya están en `.gitignore`; `reports/*.csv` y
  `reports/summary.json` sí se versionan porque el README los cita.
- No existe `tasks/lessons.md`; se crea con la primera corrección del usuario.
