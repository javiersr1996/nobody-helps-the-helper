# Analytics Cup 2.0 - proyecto de baloncesto SkillCorner

## Decisión (council, 54/100)
Paquete open source de ingesta y estandarización del tracking de baloncesto de SkillCorner,
con módulo de calidad e incertidumbre, en lugar de una métrica táctica nueva.

Motivo: el precedente de la edición 1 (el ganador acabó integrado en DataballPy), kloppy es de
PySport y no soporta baloncesto, y el perfil es de ingeniería de datos, no de investigación.

## Correcciones sobre el council, verificadas contra los datos reales
1. La opción "clasificador de cobertura del pick and roll" está MUERTA: los eventos `picks` ya
   traen `bhrDefType` y `scrDefType` con las etiquetas (ice, switch, over, blitz, under, soft,
   show). No hay nada que clasificar, el dataset ya lo da.
2. La incertidumbre NO hay que modelarla: cada posición de cada frame trae `isDetected` y
   `predError` en pies. El trabajo es propagarla, que es ingeniería, no estadística avanzada.
   Esto desactiva el rojo que tres advisors pusieron sobre el perfil.
3. El dato defensivo NO falta en los eventos: `matchups` (asignaciones defensor-atacante por
   intervalos), `closeouts`, y los ids de ambos defensores en `picks`. Lo que falta son los
   AGREGADOS de temporada de defensa (los CSV de 293 partidos son solo de ataque).

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

## Tesis del proyecto (verificada con datos, 1.414 tiros)
"Shot Quality" se apoya en `closestDefDist`, la distancia tirador-defensor en el release.
Esa distancia se calcula sobre dos posiciones que traen su propio error. Medido:
- Mediana de `closestDefDist`: 3,59 ft. Error combinado medio: 1,85 ft.
- **17,3% de los tiros tienen una distancia menor que su propio error de medición.**
- **21,6% tienen defensor más cercano ambiguo** (el segundo entra dentro del margen).
- Y el ruido se concentra donde más pesa: en los tiros `plus` es el 26,3% y en los
  `blocked` el 43,1%, frente al 4,1% de los `open`.

Validación de que el cálculo es correcto: al recalcular la distancia desde el tracking,
la diferencia con el campo publicado tiene mediana 0,000 ft, el 96,5% cae dentro de
0,5 ft y se identifica al mismo defensor en el 95,1% de los tiros.

## Producto
- A. Loader con las trampas de KNOWN_ISSUES.md codificadas. HECHO (v0).
- B. Módulo de calidad: perfil de detección y `predError`. HECHO (v0).
- C. Capa de incertidumbre sobre shot quality: qué diferencias de calidad de tiro son
     reales y cuáles caben dentro del error de medición.
- D. Agregados defensivos desde eventos, si sobra tiempo. Secundario.

## Estado
- [x] Clonar el dataset (728 MB, Git LFS) en data/raw, ignorado por git
- [x] Verificar esquemas reales contra la documentación
- [x] Esqueleto con uv, pyproject, paquete instalable
- [x] A. Loader de tracking (streaming) y de eventos con las trampas corregidas
- [x] B. Perfil de calidad sobre los 10 partidos: 76,2%-82,8% detectadas,
      predError 1,52-1,86 ft, frames muertos 26%-55% (la doc dice "la mitad", falso)
- [x] Experimento de contestación: la tesis aguanta
- [ ] Sustituir la cota heurística de ambigüedad por perturbación Monte Carlo
- [ ] C. Propagar la incertidumbre a shotQuality
- [ ] Tests
- [ ] README (máximo 1000 palabras) y vídeo de 1 minuto
- [ ] Publicación del repo

## Decisiones abiertas
- Nombre público del paquete. Nombre de trabajo `scbasket`.
- Solo o en pareja: las bases permiten 2 y el punto débil declarado es el modelado.

## Avisos
- El repo padre `data_engineer` tiene 119 borrados sin commitear: el proyecto anterior se movió
  a `feb_platform/`. No tocar ni commitear eso sin preguntar.
