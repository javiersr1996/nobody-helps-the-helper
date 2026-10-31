// La memoria del proyecto "Nobody helps the helper", como .docx, generada desde el repo.
//
// Uso (desde la raíz del repositorio, con docx-js instalado en global):
//   NODE_PATH="$(npm root -g)" node docs/memoria/build_memoria.js
//
// Todo número que aparece en la memoria sale de reports/*.csv (los mismos ficheros que leen
// las figuras), del git log, o del registro tasks/todo.md cuando procede de una sonda que no
// dejó código en el paquete; en ese caso la prosa lo dice. Ampliar la memoria en un hito es
// añadir una sección aquí y una fila al registro de versiones del final.

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, Header, Footer,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber,
  PageBreak,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const REPORTS = path.join(ROOT, "reports");
const FIGURES = path.join(REPORTS, "figures");
const OUT = path.join(__dirname, "memoria_nobody_helps_the_helper.docx");

const VERSION = "0.15";
const DATE = "31 de octubre de 2026";
const HOOP_X = -40.76; // scbasket.court.HOOP_X
const HELP_FT = 4.0;
const OPEN_FT = 6.0;
// Las de scbasket.help_kinds (secciones 13 y 17); PASS_MIN_N, la de scripts/near_robustness.py (13 a2).
const PATH_FT = 6, LAST_MOVE_FT = 4, STAY_FT = 2, NEAR_STEP_FT = 2, NEAR_STAY_FT = 1, RECOVER_FT = 1;
const PASS_MIN_N = 30;
const THREE_ZONES = new Set(["corner_3", "wing_3", "top_3", "far"]);
const CONTENT_WIDTH = 9026; // A4 con márgenes de una pulgada, en DXA

// ----------------------------------------------------------------------------- datos

function readCsv(file) {
  const text = fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n").trim();
  const [head, ...lines] = text.split("\n");
  const cols = head.split(",");
  return lines.map((line) => {
    const values = line.split(",");
    const row = {};
    cols.forEach((c, i) => { row[c] = values[i] === undefined ? "" : values[i]; });
    return row;
  });
}
const num = (v) => (v === "" || v === undefined ? NaN : Number(v));
const bool = (v) => v === "True" || v === "true" || v === "1";
const median = (xs) => {
  const s = xs.filter((x) => !Number.isNaN(x)).sort((a, b) => a - b);
  if (!s.length) return NaN;
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const share = (xs) => xs.filter(Boolean).length / xs.length;

const table = readCsv(path.join(REPORTS, "help_table.csv"));
const byGame = readCsv(path.join(REPORTS, "help_by_game.csv"));
const sensitivity = readCsv(path.join(REPORTS, "help_sensitivity.csv"));
const flow = readCsv(path.join(REPORTS, "help_flow.csv"));
const vectors = readCsv(path.join(REPORTS, "help_vectors.csv"));
const baseRate = readCsv(path.join(REPORTS, "help_base_rate.csv"));
const scenes = JSON.parse(fs.readFileSync(path.join(REPORTS, "wind_scenes.json"), "utf8"));
const sh = readCsv(path.join(REPORTS, "second_help_summary.csv"));
const shGame = readCsv(path.join(REPORTS, "second_help_by_game.csv"));
const shContrast = readCsv(path.join(REPORTS, "second_help_contrast.csv"));
const shSens = readCsv(path.join(REPORTS, "second_help_sensitivity.csv"));
const shContrastSens = readCsv(path.join(REPORTS, "second_help_contrast_sensitivity.csv"));
const shPass = readCsv(path.join(REPORTS, "second_help_pass.csv"));
const shClose = readCsv(path.join(REPORTS, "second_help_closeouts.csv"));
const hk = readCsv(path.join(REPORTS, "help_kinds_summary.csv"));
// La revisión del 31 de octubre (sección 17): los near_*.csv que escribe scripts/near_robustness.py.
const nSens = readCsv(path.join(REPORTS, "near_sensitivity.csv"));
const nRob = readCsv(path.join(REPORTS, "near_robustness.csv"));
const nCoh = readCsv(path.join(REPORTS, "near_matchup_coherence.csv"));
const nRot = readCsv(path.join(REPORTS, "near_rotator.csv"));
const nPass = readCsv(path.join(REPORTS, "near_pass.csv"));

const ok = table.filter((r) => r.status === "ok");
const helped = ok.filter((r) => bool(r.has_helper));
const left = helped.filter((r) => r.left_nearest1 !== "");
const N = {
  drives: table.length,
  resolved: ok.length,
  noFrame: table.filter((r) => r.status === "no_frame").length,
  noHorizon: table.filter((r) => r.status === "no_horizon").length,
  noHandler: table.filter((r) => r.status === "no_handler").length,
  helped: helped.length,
  shareHelped: helped.length / ok.length,
  fromMiddle: share(helped.map((r) => Math.abs(num(r.helper_origin_y)) < 8)),
  fromCorner: share(helped.map((r) => Math.abs(num(r.helper_origin_y)) > 18)),
  helperStartDist: median(helped.map((r) => num(r.helper_start_dist))),
  helperHoopDist: median(helped.map((r) => num(r.helper_hoop_dist0))),
  nLeft: left.length,
  leftSep0: median(left.map((r) => num(r.left_sep0))),
  leftSep1: median(left.map((r) => num(r.left_sep1))),
  leftNearest: median(left.map((r) => num(r.left_nearest1))),
  leftOpen: share(left.map((r) => num(r.left_nearest1) >= OPEN_FT)),
  leftHoop: median(left.map((r) => num(r.left_hoop1))),
  leftBeyondArc: share(left.map((r) => THREE_ZONES.has(r.left_zone1))),
  leftFarSide: share(left.map((r) => num(r.left_y1) < 0)),
  // flip = +1 cuando el jugador con balón se movió hacia +y (la izquierda del equipo atacante)
  // en el marco de ataque; las columnas handler_y* ya están reflejadas y no sirven para esto.
  directionAgree: share(ok.map((r) => (r.provider_direction === "left") === (num(r.flip) === 1))),
  flowCells: flow.length,
  flowConsistencyMedian: median(flow.map((r) => num(r.consistency))),
  flowConsistencyMax: Math.max(...flow.map((r) => num(r.consistency))),
};
const originBands = [[0, 8], [8, 16], [16, 24], [24, 100]].map(([lo, hi]) => {
  const rows = helped.filter((r) => {
    const x = num(r.helper_origin_x) - HOOP_X;
    return x >= lo && x < hi;
  });
  return {
    band: hi === 100 ? `${lo}+ ft` : `${lo} a ${hi} ft`,
    n: rows.length,
    share: rows.length / helped.length,
    middle: share(rows.map((r) => Math.abs(num(r.helper_origin_y)) < 8)),
    corner: share(rows.map((r) => Math.abs(num(r.helper_origin_y)) > 18)),
  };
});
const endTypes = [...new Set(ok.map((r) => r.end_type))].sort().map((et) => {
  const rows = ok.filter((r) => r.end_type === et);
  return { et, n: rows.length, share: share(rows.map((r) => bool(r.has_helper))) };
});
const commits = execSync('git log --format="%h|%ad|%s" --date=short -n 8', { cwd: ROOT })
  .toString().trim().split("\n").map((l) => l.split("|"));

// ------------------------------------------------------------------------- formato

const es = (x, d = 1) => x.toFixed(d).replace(".", ",");
const pct = (x, d = 0) => `${es(100 * x, d)} %`;
const ft = (x, d = 1) => `${es(x, d)} ft`;
const thousands = (n) => String(n).replace(/\B(?=(\d{3})+$)/g, ".");
const sg = (x, d = 2) => es(x, d).replace("-", "−"); // con el signo menos tipográfico
const sft = (x, d = 2) => `${sg(x, d)} ft`;

// Segunda ayuda: filas de second_help_summary.csv por horizonte (fotogramas) y ayuda.
const HORIZONS = [25, 38, 50];
const SH = (h, helped) => sh.find((r) => num(r.horizon) === h && bool(r.helped) === helped);
const HEADLINE = 38; // 1,5 s, el horizonte que fija la decisión D4 de tasks/todo.md
const hsec = (h) => es(num(SH(h, true).horizon_s), 1);
const meanCi = (r) => `${sg(num(r.mean_diff))} (${sg(num(r.ci_low))} a ${sg(num(r.ci_high))})`;
// Contraste con ayudante menos sin él (reports/second_help_contrast.csv): la referencia es la serie sin ayudante, no el cero.
const CT = (h) => shContrast.find((r) => num(r.horizon) === h);
const CONTRAST_TEXT = HORIZONS.map((h) => `${sg(num(CT(h).contrast_mean))} (${sg(num(CT(h).contrast_ci_low))} a ${sg(num(CT(h).contrast_ci_high))})`).join(" / ");
// Signos por partido a 1,5 s con ayudante: mediana por pareja (median_diff_pairs) y por
// penetración (median_diff). Se cuentan aquí, no se teclean.
const gameRows = shGame.filter((r) => num(r.horizon) === HEADLINE && bool(r.helped));
const gameSigns = {
  games: gameRows.length,
  pairNeg: gameRows.filter((r) => num(r.median_diff_pairs) < 0).length,
  driveNeg: gameRows.filter((r) => num(r.median_diff) < 0).length,
  pairClosest: Math.max(...gameRows.map((r) => num(r.median_diff_pairs)).filter((x) => x < 0)),
  driveClosest: Math.max(...gameRows.map((r) => num(r.median_diff)).filter((x) => x < 0)),
};
// Tasa base de "hombre libre" en la rejilla de sensibilidad de la ayuda (4 ft, 1,0 s).
const base = sensitivity.find((s) => num(s.horizon_s) === 1 && num(s.help_ft) === 4);
const cornerSide = sensitivity.map((s) => num(s.helper_from_corner_side));
const sharesHelper = byGame.map((g) => num(g.share_with_helper));
const halfSecThree = sensitivity.find((s) => num(s.horizon_s) === 0.5 && num(s.help_ft) === 3);

// La esquina con su tasa base (sección 12), leída de reports/help_base_rate.csv.
const RATE_MIN_WEIGHT = 80; // src/scbasket/wind.py: masa kernel mínima para pintar la tasa
const BR = (grouping, by, group) => baseRate.find((r) => r.grouping === grouping && r.standardised_by === by && r.group === group);
const yBands = baseRate.filter((r) => r.grouping === "y_band" && r.standardised_by === "none");
const cornerBand = yBands[yBands.length - 1];
const middleBand = yBands[0];
const bearingRows = baseRate.filter((r) => r.grouping === "bearing_band");
const ZONES = ["top_3", "wing_3", "mid_range", "paint_non_ra", "restricted_area", "far"];
const ZONE_NAME = {
  top_3: "Triple frontal", wing_3: "Triple de ala", mid_range: "Media distancia",
  paint_non_ra: "Pintura (fuera del área restringida)", restricted_area: "Área restringida",
  far: "Lejos (más de 32 ft del aro)",
};
const bandName = (g) => {
  const [lo, hi] = g.split("-");
  return hi === "inf" ? `más de ${lo} ft (lado de la esquina)` : `${lo} a ${hi} ft${lo === "0" ? " (centro)" : ""}`;
};
const ratio = (r) => es(num(r.ratio), 2);
const ratioCi = (r) => `${ratio(r)} (${es(num(r.ratio_low), 2)} a ${es(num(r.ratio_high), 2)})`;
const rateCi = (r) => `${pct(num(r.rate), 1)} (${pct(num(r.rate_low), 1)} a ${pct(num(r.rate_high), 1)})`;
const helperKey = new Set(helped.map((r) => `${r.drive_id}|${num(r.helper_def_slot)}`));
const helperVectors = vectors.filter((r) => helperKey.has(`${r.drive_id}|${num(r.def_slot)}`));
if (helperVectors.length !== helped.length) throw new Error("help_vectors y help_table no coinciden en los ayudantes");
const farDx = median(helperVectors.filter((r) => r.zone0 === "far").map((r) => num(r.dx)));
const nCorner3 = vectors.filter((r) => r.zone0 === "corner_3").length;
const sens = (col) => sensitivity.map((s) => num(s[col]));
const cornerMinusMiddle = sensitivity.filter((s) => num(s.horizon_s) >= 1)
  .map((s) => num(s.helper_rate_corner_side) - num(s.helper_rate_middle));
const halfSecCorner = Math.max(...sensitivity.filter((s) => num(s.horizon_s) === 0.5)
  .map((s) => Math.round(num(s.helper_rate_corner_side) * num(s.n_defenders_corner_side))));
const targetDist = (z) => median(vectors.filter((r) => r.zone0 === z).map((r) => num(r.target_dist)));
const rateSe = Math.sqrt(num(base.helper_rate) * (1 - num(base.helper_rate)) / RATE_MIN_WEIGHT);
// Lo que la sección 12 afirma se comprueba al generar, no se supone.
if (!(num(cornerBand.rate_low) <= num(middleBand.rate) && num(middleBand.rate) <= num(cornerBand.rate_high))) throw new Error("el IC de la esquina ya no contiene la tasa del centro: revisar la sección 12.1");
if (!(Math.min(targetDist("paint_non_ra"), targetDist("restricted_area")) > targetDist("top_3"))) throw new Error("los interiores ya están más cerca del punto adonde va el balón: revisar la sección 12.2");
if (!(num(BR("zone0", "target_dist", "top_3").ratio_low) > 1)) throw new Error("la distancia ya explica el exceso del triple frontal: revisar la sección 12.2");
for (const z of ["top_3", "paint_non_ra"]) {
  const r = BR("zone0", "bearing", z);
  if (!(num(r.ratio_low) <= 1 && 1 <= num(r.ratio_high))) throw new Error(`por orientación, ${z} ya no contiene el 1: revisar la sección 12.2`);
}

// La penetración de la figura 1 (sección 9.1): la primera escena de reports/wind_scenes.json.
const SC = scenes.scenes[0];
const SCT = scenes.headline_frame;
const scToLeft = SC.to_left.map((r) => r[SCT]);
const scPlacebo = SC.placebo.map((r) => r[SCT]);
const scAmong = SC.paired_mean_1_5s_among_helped;
const scDiffs = scToLeft.map((v, i) => v - scPlacebo[i]); // lo que aporta cada uno de los tres
const sg1 = (x) => sg(Math.abs(x) < 0.05 ? 0 : x, 1); // sin "−0,0"
const scSel = scenes.selection; // una entrada por partido probado, con su penetración elegida
if (scSel[0].chosen !== SC.drive_id) throw new Error("la primera escena no es la elegida en el primer partido");
// Lo que 9.1 dice de los tres y del percentil, comprobado aquí para que no quede escrito en falso.
const [scHi, scMid, scLo] = [...scDiffs].sort((a, b) => b - a);
if (!(scHi > 0.5 && Math.abs(scMid) < 0.05 && scLo < -0.5)) throw new Error("9.1: «uno más hacia él, otro igual y el tercero menos» ya no es cierto");
if (!(scAmong.percentile >= 40 && scAmong.percentile <= 60)) throw new Error("9.1: «del centro de la distribución» ya no es cierto");
// Quién es el más cercano al hombre que deja a 1,5 s, y la reclasificación de esta escena (secciones 9.1 y 17.8).
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const scR = SC.roles;
const scNearest = [scR.handler_def, scR.helper, ...scR.others].map((i) => [i, dist(SC.xy[SCT][i], SC.xy[SCT][scR.left])]).sort((a, b) => a[1] - b[1])[0];
if (scNearest[0] !== scR.helper || Math.abs(scNearest[1] - SC.clearance_ft["1.5s"]) > 0.01) throw new Error("9.1: el más cercano al hombre que deja a 1,5 s ya no es el ayudante");
const scEnd = SC.xy.length - 1; // 2,0 s
const scStart = dist(SC.xy[0][scR.helper], SC.xy[0][scR.left]);
const scToManNow = dist(SC.xy[scEnd][scR.helper], SC.xy[scEnd][scR.left]);
const scToManStart = dist(SC.xy[scEnd][scR.helper], SC.xy[0][scR.left]);
const scManMoved = dist(SC.xy[0][scR.left], SC.xy[scEnd][scR.left]);
if (!(scToManNow <= scStart + RECOVER_FT && scToManStart > scStart + RECOVER_FT)) throw new Error("17.8: la escena 0 ya no es finta con la regla anterior y comprometida con la nueva");
// La escena 0 anterior, del commit que eligió las cuatro el 30 de octubre.
const gitSha = (subject) => execSync(`git log --format=%h --grep="${subject}" -n 1`, { cwd: ROOT }).toString().trim();
const REPICK_SHA = gitSha("Re-pick the page's drives among committed near helps");
const OSC = JSON.parse(execSync(`git show ${REPICK_SHA}:reports/wind_scenes.json`, { cwd: ROOT, maxBuffer: 64 * 1024 * 1024 }).toString()).scenes[0];
if (OSC.drive_id === SC.drive_id) throw new Error("17.8: la escena 0 ya no ha cambiado respecto a la del 30 de octubre");

const BODY = 22; // 11 pt
const p = (text, opts = {}) => new Paragraph({
  spacing: { after: 120, line: 276 },
  ...opts,
  children: Array.isArray(text) ? text : [new TextRun({ text, size: BODY })],
});
const run = (text, extra = {}) => new TextRun({ text, size: BODY, ...extra });
const bold = (text) => run(text, { bold: true });
const mono = (text) => new TextRun({ text, size: 20, font: "Consolas" });
const h1 = (text, opts = {}) => new Paragraph({
  heading: HeadingLevel.HEADING_1, ...opts, children: [new TextRun(text)],
});
const h2 = (text, opts = {}) => new Paragraph({
  heading: HeadingLevel.HEADING_2, ...opts, children: [new TextRun(text)],
});
const bullet = (children) => new Paragraph({
  numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: 276 },
  children: Array.isArray(children) ? children : [run(children)],
});
const numbered = (children) => new Paragraph({
  numbering: { reference: "numbers", level: 0 }, spacing: { after: 60, line: 276 },
  children: Array.isArray(children) ? children : [run(children)],
});
const source = (text) => new Paragraph({
  spacing: { after: 160 },
  children: [new TextRun({ text: `Fuente: ${text}`, size: 18, italics: true, color: "555555" })],
});
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

const border = { style: BorderStyle.SINGLE, size: 2, color: "BBBBBB" };
const borders = { top: border, bottom: border, left: border, right: border };
function grid(headers, rows, widths, { align = [] } = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  if (total !== CONTENT_WIDTH) throw new Error(`anchos de tabla suman ${total}, no ${CONTENT_WIDTH}`);
  const cell = (text, i, head) => new TableCell({
    borders,
    width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { fill: "EEEEEE", type: ShadingType.CLEAR } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: align[i] === "r" ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: String(text), size: 19, bold: head })],
    })],
  });
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((t, i) => cell(t, i, true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((t, i) => cell(t, i, false)) })),
    ],
  });
}
const spacer = () => new Paragraph({ spacing: { after: 120 }, children: [] });

function figure(file, caption) {
  const data = fs.readFileSync(path.join(FIGURES, file));
  const width = 460; // píxeles a 96 ppp: 4,8 pulgadas
  // alto/ancho leído de la cabecera IHDR del PNG, para que no se quede viejo al redibujar
  const height = Math.round(width * data.readUInt32BE(20) / data.readUInt32BE(16));
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
      children: [new ImageRun({
        type: "png", data, transformation: { width, height },
        altText: { title: caption, description: caption, name: file },
      })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: caption, size: 18, italics: true, color: "555555" })],
    }),
  ];
}

// ------------------------------------------------------------------------ contenido

const cover = [
  new Paragraph({ spacing: { before: 2400, after: 200 }, children: [
    new TextRun({ text: "Nobody helps the helper", size: 56, bold: true }),
  ] }),
  new Paragraph({ spacing: { after: 120 }, children: [
    new TextRun({ text: "The wind map of ACB defences, on SkillCorner's open tracking", size: 28, color: "444444" }),
  ] }),
  new Paragraph({ spacing: { before: 600, after: 120 }, children: [
    new TextRun({ text: "Memoria del proyecto", size: 32, bold: true }),
  ] }),
  p("Entrada a la Analytics Cup 2.0 (SkillCorner x PySport), baloncesto. Entrega el 18 de diciembre de 2026."),
  p("Javier Sánchez Rueda"),
  p(`Documento vivo. Versión ${VERSION}, ${DATE}.`),
  new Paragraph({ spacing: { before: 1800 }, children: [
    new TextRun({ text: "Generado por docs/memoria/build_memoria.js a partir de reports/*.csv y del git log del repositorio skillcorner_basket_data. Las secciones llevan la fecha del trabajo que describen; el registro de versiones está al final.", size: 18, italics: true, color: "555555" }),
  ] }),
  pageBreak(),
];

// Índice estático: un campo TOC solo se rellena al actualizar campos en Word, y queda en
// blanco en cualquier otro visor y en el PDF de prueba.
const SECTIONS = [
  "1. Qué es este documento", "2. La competición", "3. El dato",
  "4. Antecedentes: las dos entradas previas", "5. La ideación (28 de octubre de 2026)",
  "6. Definiciones y reglas de esta entrada", "7. Implementación (semana 1)",
  "8. Resultados (semana 1)", "9. Las dos figuras (semana 2)",
  "10. La reorientación: una sola entrada, el council y la segunda ayuda (28 de octubre de 2026)",
  "11. La segunda ayuda: una ausencia medida", "12. La esquina, con su tasa base (29 de octubre de 2026)",
  "13. Ayuda cercana y ayuda larga (30 de octubre de 2026)",
  "14. La página (29 y 30 de octubre de 2026)",
  "15. El repositorio público y el README (30 de octubre de 2026)", "16. El vídeo (31 de octubre de 2026)",
  "17. La revisión y la reclasificación (31 de octubre de 2026)", "18. Plan y calendario",
  "19. Pendientes y decisiones abiertas", "20. Registro de versiones de este documento",
];
const toc = [
  h1("Índice"),
  ...SECTIONS.map((t) => p(t, { spacing: { after: 80 } })),
  pageBreak(),
];

const s1 = [
  h1("1. Qué es este documento"),
  p("Esta memoria recoge el proyecto completo de la segunda entrada de Javier a la Analytics Cup 2.0, desde la ideación hasta la entrega, y se amplía en cada hito. No sustituye al registro de trabajo del repositorio (tasks/todo.md, en inglés, que guarda cada decisión con su fecha) ni al README que leerá el jurado: es el relato ordenado, en castellano, de qué se hizo, por qué, y qué salió."),
  p("Los números que aparecen salen de los ficheros reports/*.csv que escriben los scripts del repositorio, los mismos que leen las figuras, de modo que memoria, figuras y README no pueden desviarse entre sí. Cuando una cifra procede de una sonda exploratoria que no dejó código en el paquete, se dice, y la cifra está también en tasks/todo.md. El documento lo genera un script (docs/memoria/build_memoria.js) a partir de esos ficheros y del historial de git, así que rehacerlo tras cada cambio no exige volver a teclear nada."),
];

const s2 = [
  h1("2. La competición"),
  p("La Analytics Cup 2.0 es la segunda edición del concurso de SkillCorner y PySport. La primera (2026) fue solo de fútbol, con un Analyst Track y un Research Track, y la ganó Amar Shah con un método de optimización posicional por recocido simulado que después se integró como módulo del paquete DataballPy; los organizadores lo destacan como precedente, lo que dice algo de lo que premian: un método reutilizable, publicado como software. La segunda edición abre dos deportes, dos competiciones regionales y dos finales presenciales."),
  grid(["Aspecto", "Dato"], [
    ["Entrega", "18 de diciembre de 2026"],
    ["Finalistas", "8 de enero de 2027"],
    ["Final europea", "17 de febrero de 2027, París (la americana, según una publicación de LinkedIn no verificada en las bases, el 24 de febrero en Boston)"],
    ["Criterios", "Cinco, al 20 % cada uno: Relevance, Methodology, Originality, Communication, Open-source potential"],
    ["Entregable", "Vídeo de un minuto con voz propia, repositorio público que funcione de cero con licencia abierta, README de 1000 palabras y dos figuras como máximo"],
    ["Participación", "Individual o por parejas"],
    ["Tema sugerido (baloncesto)", "Shot Quality, no obligatorio; en 2.0 no hay tracks"],
    ["Premios", "500 euros por finalista; 1500 euros al ganador regional como beca para un paquete de Python o una PR"],
  ], [2400, 6626]),
  source("bases del concurso verificadas en el bundle de pysport.org en septiembre de 2026 y registradas en tasks/todo.md (sección \"Official rules\"); la página de SkillCorner analytics-cup-2027 y la de presentaciones de 2026 para el precedente."),
];

const s3 = [
  h1("3. El dato"),
  p("SkillCorner publicó para la competición su primer open data de baloncesto: la temporada 2025-26 de la Liga ACB. Tres capas: tracking óptico de retransmisión a 25 fotogramas por segundo (posiciones x, y de los diez jugadores y x, y, z del balón) para diez partidos; los Dynamic Events de esos diez partidos, veinte familias (posesiones, oportunidades, tiros, pases, toques, botes, rebotes, bloqueos directos e indirectos, penetraciones, closeouts, emparejamientos defensivos...), cada una con contexto derivado del tracking; y agregados ofensivos por jugador y temporada de 293 de los 327 partidos para tiros, penetraciones y bloqueos. Licencia MIT."),
  p("Lo que el proveedor advierte: entre el 76 % y el 83 % de las posiciones de jugador están detectadas en imagen y el resto extrapoladas, con un error medio declarado de 1,5 a 1,9 pies; la calibración del balón es peor que la de los jugadores; y conviene suavizar velocidades y aceleraciones. Lo que descubrieron las dos entradas previas de Javier y que condiciona esta: la z del balón no es una medida sino una trayectoria reconstruida (su curvatura vertical sale un 12 a 15 % corta, y el campo isDetected del balón es 0 en los 829.704 fotogramas), y la cadencia efectiva de la solución está en torno a 200 ms, por debajo de la cual se mide interpolación. Nada de eso afecta a esta entrada, que usa solo posiciones horizontales de jugadores sobre ventanas de un segundo."),
  grid(["Familia de eventos", "Diez partidos", "Familia de eventos", "Diez partidos"], [
    ["Toques", "6.662", "Botes", "13.962"],
    ["Pases", "4.786", "Pases que acaban en tiro en 3 s", "754"],
    ["Tiros", "1.459", "Tiros de recepción (catch and shoot)", "615"],
    ["Penetraciones (drives)", "660", "Closeouts", "601"],
    ["Bloqueos directos", "1.520", "Bloqueos indirectos", "1.103"],
    ["Aislamientos", "180", "Rebotes", "768"],
  ], [2600, 1400, 3626, 1400], { align: ["l", "r", "l", "r"] }),
  source("recuento de la sesión del 28 de octubre de 2026 sobre los diez ficheros *_dynamic_events.json (script de sondeo count_events.py, fuera del paquete)."),
];

const s4 = [
  h1("4. Antecedentes: las dos entradas previas"),
  p("Esta es la tercera idea que Javier lleva a la competición, y la primera que renuncia a propósito al aparato de validación de las anteriores. Las dos previas existen y están en distinto estado:"),
  bullet([bold("\"Nobody reads the bounce\""), run(" (repositorio skillcorner_basket_data, el mismo de esta entrada). El rebote no se lee, se ocupa: dentro de cuatro pies del aro, llegar en dirección al aro sube la probabilidad de ganar el rebote 0,172 en los cinco partidos de calibración y 0,322 en los cinco reservados; pasados doce pies no vale nada. Pre-registrada, con umbrales congelados en commits antes de abrir los partidos reservados, con sus negativos publicados. Completa: README de 999 palabras, dos figuras, página interactiva, vídeo mudo de 60 segundos cortado al guion. Solo falta la voz.")]),
  bullet([bold("El kit de calibración"), run(" (repositorio skillcorner_screens). La física como regla externa para auditar un bundle de tracking: la gravedad ajustada a los vuelos de los tiros sale en 28,10 y 28,23 pies por segundo al cuadrado (calibración y reservados) contra los 32,17 reales; el ángulo de entrada publicado es 14,4 y 13,8 grados más plano de lo que exige el vuelo; las tres condiciones pre-registradas pasan cinco partidos de cinco. Hay página; falta el README, el guion y avisar a SkillCorner antes de enviar nada.")]),
  p("Actualización del 28 de octubre de 2026: ninguna de las dos se presenta. Esta es la única entrada de baloncesto (sección 10), y las dos previas quedan como trabajo previo, con su código como infraestructura que esta entrada ya usa."),
  p("De las dos se heredan tres reglas que esta entrada conserva: la intención no se puede reclamar desde el tracking (se publican definiciones, nunca detectores); un número sin código detrás no es un hallazgo; y lo que se mueve se verifica conduciéndolo, no mirándolo. Y se hereda también la razón estructural por la que casi todo lo demás murió en diez partidos: entre la geometría medida y el resultado que el dato registra suele mediar la decisión de otro, segundos después. Lo que funciona es lo que se decide de inmediato por la geometría misma."),
  source("README.md del repositorio y tasks/todo.md de ambos proyectos."),
];

const s5 = [
  h1("5. La ideación (28 de octubre de 2026)"),
  h2("5.1 El encargo"),
  p("Javier pidió una idea original, muy buena a nivel comunicativo y muy espectacular a nivel visual, sin volver a las revisiones adversariales y las puertas de validación de las entradas anteriores: con datos limitados, lo que salga justo se asume como error y se cuenta como sale. Añadió que en LinkedIn ya había muchos proyectos interesantes publicados sobre este dato, así que había que mirar primero qué estaba hecho. Un colega suyo, Miguel, le había sugerido mirar las ayudas defensivas."),
  h2("5.2 Lo que ya estaba publicado"),
  p("Un barrido de la web y de LinkedIn (sin acceso a los textos completos de las publicaciones, solo a lo indexado) dio este mapa: una plataforma Streamlit de doce páginas con replays animados, un modelo xFG, una curva de colapso defensivo en penetraciones y páginas de pick and roll por cobertura y de geometría de closeouts (sportsanalystf/skillcorner-basketball-intelligence); el Spacing Connectome de la Universidad de Pittsburgh (dónde se colocan los otros cuatro atacantes dada la posición de uno, por regresión kernel), cuyo autor nombra como trabajo futuro justo lo que esta entrada hace, cómo se recoloca la defensa cuando un ayudante salta a una penetración; un repositorio de aprendizaje de un entrenador con diez proyectos (dmolins/acb-tracking-101); modelos de probabilidad de rebote (basketballrelativity/spatial-rebounding); y en LinkedIn un visor 3D de posesiones, un modelo de rotaciones rotas en puntos esperados y un benchmark de detección de acciones. Nadie había dibujado la ayuda. Y la tabla drives del open data no trae campo de ayuda, aunque la versión comercial de los Dynamic Events sí lo vende (\"help involvement\"): la capa que falta, exactamente como la aproximación al rebote fue la capa que faltaba en la primera entrada."),
  h2("5.3 Las ideas sondeadas y lo que salió"),
  p("Antes de proponer nada se sondearon tres direcciones sobre los diez partidos, con scripts de sesión fuera del paquete. Las dos primeras murieron por la razón estructural de siempre; la tercera tenía estructura y pasó a plan."),
  grid(["Idea", "Qué se midió", "Resultado", "Veredicto"], [
    ["El latido del balón: la cadencia del bote como electrocardiograma de la posesión", "10.608 intervalos entre botes consecutivos del mismo toque; su coincidencia con los mínimos de la z del balón; la separación respecto al defensor emparejado 0,48 s después de un cambio de cadencia", "La cadencia es real (mediana 0,72 s, p10 0,48, p90 1,08; el 96,8 % de los botes del proveedor cae a ±2 fotogramas de un mínimo de z, el 67 % exacto). Pero un cambio de cadencia no abre distancia: −0,04 ft tras un bote rápido, −0,28 tras uno estable, −0,24 tras uno lento, con signos mezclados por partido", "Nula como hallazgo. Puede sobrevivir como escena visual, nunca como argumento"],
    ["La ventana entre el último bote (o la recepción) y la suelta, y cuánto cierra el defensor en ella", "552 tiros tras bote y 486 tras recepción; distancia del defensor emparejado al inicio de la ventana y en la suelta", "El defensor cierra lo mismo sea la ventana corta o larga: 0,50 ft tras el último bote (ventana mediana 1,12 s) y 3,97 ft tras la recepción (0,80 s); Spearman entre longitud de ventana y cierre −0,035 y +0,004", "Nula. Descriptiva, no hay mecanismo"],
    ["La ayuda defensiva en el primer segundo de la penetración", "Movimiento propio de los cuatro defensores no emparejados con el balón, proyectado hacia donde estará el balón un segundo después; origen del que más se mueve; el atacante que deja", "El 46 % de las penetraciones tiene un defensor que se mueve 4 ft o más hacia el balón; sale por el centro, del lado de la esquina entre el 0 % y el 8 % según la banda; el atacante que deja pasa de 6,7 a 8,7 ft de separación, el 59 % sin nadie a 6 ft, el 65 % a más de 22 ft del aro. El campo de flujo tiene celdas con consistencia de 0,63 a 0,85", "Elegida"],
  ], [2000, 2300, 3026, 1700]),
  source("sondas de sesión del 28 de octubre de 2026 (cadence_probe2.py, window_probe.py, help_probe2.py), cuyos números quedaron registrados en tasks/todo.md; la primera versión de la sonda de ayuda medía la reducción de distancia defensor-balón, que la domina el propio avance del balón, y se descartó."),
  p("Quedó una alternativa sin sondar, \"On time, on target\": la geometría de llegada del pase (velocidad, altura, punto respecto al cuerpo del receptor) contra el tiempo de suelta, sobre los 754 pases que acaban en tiro en tres segundos. Está en el tema sugerido y podría retomarse si hiciera falta."),
  h2("5.4 La decisión"),
  p("Título: \"Nobody helps from the corner\". Subtítulo: the wind map of ACB defences, on SkillCorner's open tracking. Tesis en una línea: en cada penetración la defensa se mueve como el tiempo atmosférico; la ayuda sopla desde el centro y desde arriba, nunca desde la esquina, y deja a un tirador libre más allá del arco. Javier la aprobó el mismo día."),
];

const s6 = [
  h1("6. Definiciones y reglas de esta entrada"),
  p("Las definiciones se fijaron una vez, antes de leer las tablas completas, y cada titular se publica con una tabla de sensibilidad al lado. No hay pre-registro, ni mitad reservada, ni puertas; los cortes por partido se publican, nunca se usan para decidir."),
  bullet([bold("Horizonte. "), run("Un segundo (25 fotogramas) desde el startFrame de la penetración, dentro de la misma oportunidad (chance).")]),
  bullet([bold("Marco de la penetración. "), run("El marco de ataque (aro atacado en x negativa) reflejado en y para que el movimiento lateral del jugador con balón durante el horizonte apunte a +y. Así las penetraciones por la izquierda y por la derecha se superponen, y \"el lado de la esquina\" es siempre el mismo lado. Las zonas de tiro se clasifican antes del reflejo.")]),
  bullet([bold("Movimiento de ayuda. "), run("Para un defensor que no es el emparejado del jugador con balón, su propio desplazamiento durante el horizonte proyectado sobre el vector unitario que va desde donde empezó hasta donde está el jugador con balón al final del horizonte. En pies; positivo significa que se movió hacia donde iba el balón. Un defensor que solo se hunde con la penetración puntúa bajo si está más cerca de la línea del aro que el punto adonde va el balón; por encima de ese punto, hundirse ya cuenta como movimiento de ayuda. Corregido el 29 de octubre: hasta entonces esta definición decía que hundirse puntuaba bajo siempre (sección 12.3).")]),
  bullet([bold("Ayudante. "), run(`El defensor no emparejado con mayor movimiento de ayuda, cuando ese movimiento es de al menos ${es(HELP_FT, 0)} pies. La tabla describe siempre al que más se mueve, de modo que el umbral puede barrerse después sin recalcular nada.`)]),
  bullet([bold("El hombre que deja. "), run(`El atacante que la tabla matchups del proveedor asigna al ayudante en el startFrame: su separación del ayudante en los dos extremos del horizonte, su distancia a cualquier defensor al final, y si esa distancia llega a ${es(OPEN_FT, 0)} pies (\"abierto\").`)]),
  bullet([bold("Sensibilidad. "), run("Umbrales de 3, 4, 5 y 6 pies; horizontes de 0,5, 1,0 y 1,5 segundos.")]),
  bullet([bold("Intención. "), run("\"Ayuda\", \"ayudante\" y \"hombre libre\" nombran vectores y distancias medidos, nunca decisiones. Nada dice que un defensor eligiera ayudar ni que dejara a un hombre a propósito. Es la misma regla de la primera entrada, y la misma posición de SkillCorner: el tracking muestra puntos que convergen, no por qué.")]),
  bullet([bold("Trazabilidad. "), run("Todo número del README y de la página sale de un reports/*.csv escrito por un script. Lo que se mueve se verifica conduciéndolo desde la consola, no mirándolo.")]),
];

const s7 = [
  h1("7. Implementación (semana 1, 28 de octubre de 2026)"),
  p("El módulo se llama scbasket.wind y no scbasket.help como decía el plan, porque help pisa el builtin de Python dentro del paquete. Reutiliza la infraestructura de la primera entrada: la caché de fotogramas por partido (data/interim/{gid}_frames.npz, con posiciones orientadas al marco de ataque, ids canónicos, portador del balón y emparejamientos resueltos), la geometría de pista de scbasket.court y el cargador de eventos de scbasket.io."),
  h2("7.1 Lo que hay en el paquete"),
  bullet([mono("drive_endpoints(frames, drives, horizon_frames)"), run(": para cada penetración, la fila de la caché en el startFrame y en el horizonte, el slot del jugador con balón, y un estado: ok, no_frame (el fotograma de inicio no está en la caché: tiempo muerto, oportunidad no usable, o no hay cinco contra cinco), no_horizon (la fila del horizonte falta, no es contigua o cae en otra oportunidad) o no_handler (el ballhandlerId del proveedor no está entre los cinco atacantes).")]),
  bullet([mono("help_table(frames, drives, horizon_frames, help_ft, open_ft)"), run(": una fila por penetración con el mayor desplazado entre los defensores no emparejados (slot, id, origen, desplazamiento, movimiento de ayuda, distancia inicial al balón, zona, detección en ambos extremos) y el hombre que deja (separación en ambos extremos, defensor más cercano al final, distancia al aro, zona, posición en el marco de la penetración). Las penetraciones no resueltas conservan su fila con el estado y mediciones vacías, para que el denominador siempre se vea.")]),
  bullet([mono("help_vectors(frames, drives, horizon_frames)"), run(": una fila por pareja (penetración, defensor no emparejado), con origen y desplazamiento en el marco de la penetración. Es la materia prima del campo de viento.")]),
  bullet([mono("flow_field(vectors, cell_x_ft, cell_y_ft, min_n)"), run(": el desplazamiento medio por celda del marco de la penetración, con su consistencia (longitud del vector medio sobre la longitud media de los vectores: 1 si todos se movieron igual, 0 si se cancelan).")]),
  bullet([mono("scripts/help_wind.py"), run(": corre todo sobre los diez partidos y escribe reports/help_table.csv, help_vectors.csv, help_flow.csv, help_sensitivity.csv (umbral por horizonte) y help_by_game.csv.")]),
  bullet([mono("tests/test_wind.py"), run(": once tests sintéticos sobre una escena construida a mano, donde la respuesta se lee de las coordenadas (el ayudante se mueve exactamente 5 pies hacia donde acaba el balón y es encontrado; un defensor que solo se hunde con la penetración puntúa negativo; el emparejado del balón nunca es el ayudante por mucho que se mueva; el marco de la penetración refleja una penetración por la derecha sobre una por la izquierda; el umbral cambia la bandera y no la medida; los tres estados no resueltos conservan su fila; el campo de flujo agrega celdas y descarta las escasas), más uno sobre el partido 114086 real. La suite completa del repositorio pasa: 283 tests.")]),
  h2("7.2 Commits"),
  p("Los commits del repositorio, del más reciente al más antiguo, leídos del historial al generar este documento:"),
  grid(["Commit", "Fecha", "Asunto"], commits.map(([h, d, s]) => [h, d, s]), [1200, 1300, 6526]),
  p("El trabajo de la página interactiva de la primera entrada (19 de septiembre de 2026) estaba en el árbol sin commit; se consolidó el 28 de octubre en un commit propio, con la suite en verde, antes de seguir."),
];

const s8 = [
  h1("8. Resultados (semana 1)"),
  p(`Sobre las ${N.drives} penetraciones de los diez partidos, ${N.resolved} se resuelven (${N.noFrame} arrancan en un fotograma que la caché no tiene, ${N.noHorizon} no tienen horizonte dentro de su oportunidad${N.noHandler ? `, ${N.noHandler} sin jugador con balón` : ""}). Con la definición fijada (${es(HELP_FT, 0)} pies en 1,0 segundos; abierto a ${es(OPEN_FT, 0)} pies):`),
  grid(["Medida", "Valor"], [
    ["Penetraciones con ayudante", `${pct(N.shareHelped, 1)} (${N.helped} de ${N.resolved})`],
    ["Distancia del ayudante al balón al arrancar (mediana)", ft(N.helperStartDist)],
    ["Distancia del ayudante al aro al arrancar (mediana)", ft(N.helperHoopDist)],
    ["Ayudantes que salen por el centro (|y| < 8 ft)", pct(N.fromMiddle, 1)],
    ["Ayudantes que salen del lado de la esquina (|y| > 18 ft)", pct(N.fromCorner, 1)],
    ["Defensores sin balón que empiezan en el lado de la esquina (su tasa base, sección 12)", pct(num(base.defenders_from_corner_side), 1)],
    ["El hombre que deja: separación al inicio y al final (medianas)", `${ft(N.leftSep0)} a ${ft(N.leftSep1)}`],
    ["El hombre que deja: distancia al defensor más cercano al final (mediana)", ft(N.leftNearest)],
    [`El hombre que deja: abierto (nadie a ${es(OPEN_FT, 0)} ft)`, pct(N.leftOpen, 1)],
    ["El hombre que deja: distancia al aro (mediana)", ft(N.leftHoop)],
    ["El hombre que deja: más allá del arco (por zona)", pct(N.leftBeyondArc, 1)],
    ["El hombre que deja: en el lado contrario a la penetración", pct(N.leftFarSide, 1)],
    ["Acuerdo entre el campo direction del proveedor y el marco de la penetración", pct(N.directionAgree, 1)],
    ["Campo de flujo: celdas con 15 vectores o más", `${N.flowCells}, consistencia mediana ${es(N.flowConsistencyMedian, 2)}, máxima ${es(N.flowConsistencyMax, 2)}`],
  ], [5826, 3200]),
  source("reports/help_table.csv y reports/help_flow.csv, calculados al generar este documento."),
  p(`Tasa base, añadida el 28 de octubre (secciones 10.3 y 11.6): el ${pct(N.leftOpen, 1)} de hombres dejados sin nadie a ${es(OPEN_FT, 0)} pies no significa que la ayuda cree un hombre libre. El hombre comparable en las penetraciones sin ayudante (el del defensor que más se movió sin llegar a ${es(HELP_FT, 0)} pies) está libre el ${pct(num(base.left_open_share_no_helper), 1)} al segundo, y el hombre dejado empezaba más vigilado: ${pct(num(base.left_open0_share), 1)} libre al arrancar, contra ${pct(num(base.left_open0_share_no_helper), 1)}. La ayuda le da espacio a quien estaba más cerca de su defensor. Las cuatro cifras (la del hombre dejado al segundo es ${pct(num(base.left_open_share), 1)}) salen de la fila de 4 pies y 1,0 s de reports/help_sensitivity.csv, donde están también las otras once celdas.`),
  p("Nota sobre la última fila: la primera versión de esa comprobación, tanto en el script como en esta memoria, comparaba el signo del movimiento lateral del jugador con balón ya reflejado al marco de la penetración, que es positivo por construcción, e imprimía un acuerdo del 100 % que no significaba nada. Se rehízo con la bandera de reflejo, que guarda el lado real en el marco de ataque, y el número de la tabla es el de esa versión."),
  h2("8.1 De dónde sale el ayudante"),
  grid(["Distancia a la línea del aro", "Ayudantes", "Cuota", "Por el centro", "Del lado de la esquina"],
    originBands.map((b) => [b.band, String(b.n), pct(b.share), pct(b.middle), pct(b.corner)]),
    [2826, 1300, 1300, 1800, 1800], { align: ["l", "r", "r", "r", "r"] }),
  source("reports/help_table.csv."),
  h2("8.2 Por desenlace de la penetración"),
  grid(["Desenlace (endType del proveedor)", "Penetraciones", "Con ayudante"],
    endTypes.map((e) => [e.et, String(e.n), pct(e.share)]),
    [4826, 2100, 2100], { align: ["l", "r", "r"] }),
  source("reports/help_table.csv."),
  h2("8.3 Por partido"),
  p(`El corte por partido se publica y no se usa para decidir. La cuota de penetraciones con ayudante va del ${pct(Math.min(...sharesHelper))} al ${pct(Math.max(...sharesHelper))}: hay defensas distintas en la muestra, con uno o dos partidos cada una, lo que basta para ilustrar y no para comparar.`),
  grid(["Partido", "Resueltas", "Con ayudante", "Hombre libre abierto", "Más allá del arco"],
    byGame.map((g) => [g.game, es(num(g.n_resolved), 0), pct(num(g.share_with_helper)), pct(num(g.left_open_share)), pct(num(g.left_beyond_arc))]),
    [1826, 1800, 1800, 1800, 1800], { align: ["l", "r", "r", "r", "r"] }),
  source("reports/help_by_game.csv."),
  h2("8.4 Sensibilidad"),
  p(`La misma tabla con el umbral y el horizonte barridos. La lectura que importa: "desde el lado de la esquina" se queda entre el ${pct(Math.min(...cornerSide))} y el ${pct(Math.max(...cornerSide))} en las ${sensitivity.length} celdas. Eso mide dónde están los defensores y no si ayudan menos desde allí: por defensor, la esquina no se distingue del centro (sección 12), y la frase que esta memoria escribió aquí en la versión 0.1, que el título aguantaba bajo cualquier definición, era cierta de la cuota y no del título. Y a medio segundo solo una de cada ${es(1 / num(halfSecThree.share_with_helper), 0)} penetraciones tiene a alguien movido tres pies: la ayuda tarda más de medio segundo en verse.`),
  grid(["Horizonte (s)", "Umbral (ft)", "Con ayudante", "Por el centro", "Lado de la esquina", "Abierto", "Más allá del arco"],
    sensitivity.map((s) => [es(num(s.horizon_s)), es(num(s.help_ft), 0), pct(num(s.share_with_helper)), pct(num(s.helper_from_middle)), pct(num(s.helper_from_corner_side), 1), pct(num(s.left_open_share)), pct(num(s.left_beyond_arc))]),
    [1226, 1200, 1300, 1300, 1400, 1200, 1400], { align: ["r", "r", "r", "r", "r", "r", "r"] }),
  source("reports/help_sensitivity.csv."),
];

const s9 = [
  h1("9. Las dos figuras (semana 2, 28 de octubre de 2026)", { pageBreakBefore: true }),
  p("El concurso permite dos figuras: cómo se mide la ausencia, sobre una penetración elegida por regla, y la ausencia medida sobre todas. Hasta el 29 de octubre la primera era el mapa de viento, que decía de dónde viene la ayuda; ese día pasó a la sección 12 (sección 12.4 y 9.3). Las dos se dibujan en el marco de la penetración y en orientación de carta de tiro: el aro abajo, la línea de fondo debajo, y el movimiento lateral del jugador con balón hacia la derecha, de modo que \"el lado de la esquina\" es siempre la esquina inferior derecha. En la figura 2 y en el mapa de viento, dentro de la pista solo están la pista, el dato y el recorrido mediano del balón; números, claves y leyendas viven en una franja debajo, donde ninguna línea de corriente puede cruzarlos. La figura 1 dibuja una sola penetración y nombra a sus jugadores donde están (corregido el 29 de octubre, sección 9.3)."),
  h2("9.1 Figura 1: cómo se mide la ausencia, en una penetración"),
  ...figure("wind_figure_1_one_drive.png", "Figura 1. ¿Se mueve alguien más hacia el hombre que deja el ayudante? En una ayuda cercana comprometida elegida por regla, el movimiento de cada uno de los otros tres defensores hacia ese hombre, frente a su movimiento hacia los demás atacantes sin balón."),
  p(`La penetración no se eligió mirándola: es la primera ayuda cercana comprometida (sección 13, con la regla del 31 de octubre de la sección 17: el defensor sin balón más cercano al balón se acerca al jugador con balón en el primer segundo y a los 2 s está más lejos del punto donde empezó su hombre que al arrancar), en el primer partido, con los diez jugadores detectados en todos los fotogramas de su ventana de 2 s (scripts/wind_scenes.py, decisión D6; en ese partido cumplen todas las condiciones ${scSel[0].all} de sus ${scSel[0].drives} penetraciones, y la regla encontró una en cada uno de los ${scSel.length} primeros partidos que probó). Desde el 30 de octubre la regla es la misma y cambian los papeles, los de la sección 13: el ayudante es el más cercano y el hombre que deja es el suyo según el proveedor al arrancar; hasta entonces era el ayudante publicado de la sección 6, y ninguna de las cuatro penetraciones de la página era una ayuda cercana comprometida. Desde el 31 de octubre la clase es la reclasificada (sección 17) y la regla, aplicada igual, da otra primera penetración: ${SC.drive_id} (endType ${SC.end_type} del proveedor) en lugar de ${OSC.drive_id} (sección 17.8). En la pista, los diez jugadores desde el arranque (círculo hueco) hasta ${es(SCT / scenes.fps, 1)} s (punta de flecha), nombrados sobre la pista y no en una leyenda; solo van en color los que entran en la medida (el ayudante, el hombre que deja y los otros tres defensores, numerados), con el jugador con balón en negro y los demás atacantes en gris, el gris del placebo: el ayudante se mueve ${ft(SC.helper_help_move)} hacia el jugador con balón dentro del primer segundo, y el hombre que dejaba está a ${ft(SC.clearance_ft["0.0s"])} del defensor más cercano al arrancar, ${ft(SC.clearance_ft["1.0s"])} a 1,0 s y ${ft(SC.clearance_ft["1.5s"])} a ${es(SCT / scenes.fps, 1)} s; a ${es(SCT / scenes.fps, 1)} s ese defensor más cercano es el propio ayudante.`),
  p(`Debajo, para cada uno de los otros tres defensores, su desplazamiento propio proyectado hacia el hombre dejado y hacia el placebo (la media sobre los atacantes sin balón que no son ni el hombre dejado ni su propio hombre): ${scToLeft.map((v) => sg(v, 1)).join(" / ")} pies hacia él y ${scPlacebo.map((v) => sg(v, 1)).join(" / ")} hacia el placebo, y a su derecha la diferencia de cada uno (${scDiffs.map(sg1).join(" / ")}) y su media, que es el número que la tira de debajo sitúa. Uno se mueve hacia él ${sg1(scHi)} pies más que hacia los demás, otro lo mismo hacia él que hacia los demás (${sg1(scMid)}) y el tercero ${sg1(scLo)}: se compensan, una penetración sola no da la regla, y como la defensa entera se cierra con la penetración, la referencia es el placebo y no el cero. La media de las tres diferencias es ${sft(SC.paired_mean_1_5s)}, el percentil ${es(scAmong.percentile, 0)} de las ${scAmong.n_helped} ayudas cercanas comprometidas (mediana ${sft(scAmong.median)}): una penetración del centro de la distribución, no un caso más claro que los demás, y la figura lo enseña: una tira bajo las barras reparte las ${scAmong.n_helped} medias por penetración, con esta jugada y la mediana marcadas. Lo que enseña esta jugada es la medida: el hombre que deja termina a ${ft(SC.clearance_ft["1.5s"])} del propio ayudante, que a ${es(SCT / scenes.fps, 1)} s es el defensor más cercano a él, y de los otros tres solo uno va hacia él más que hacia los demás. La afirmación es de la figura 2, que promedia todas las ayudas cercanas comprometidas, con la referencia al lado (las penetraciones en que el defensor más cercano se queda en casa). La figura no se genera si sus proyecciones no dan la media que guarda la escena, y la escena no se escribe si no coincide con su fila (el paso del más cercano, la distancia del hombre que deja a 0 y 1,0 s, y que a los 2 s el ayudante no ha vuelto al punto donde empezó su hombre); las pruebas la comparan con reports/help_kinds.csv, reports/near_committed_drives.csv y reports/near_committed_pairs.csv, que escribe scripts/help_kinds.py.`),
];

// El mapa de viento, desde el 29 de octubre fuera del README (sección 12.5).
const windMap = [
  ...figure("wind_map_league.png", "Mapa de viento. Adónde va la defensa en el primer segundo de una penetración, y qué cuota de los defensores que empiezan en cada punto es el ayudante."),
  p("Un campo suavizado por kernel gaussiano (ancho de banda 4 pies, rejilla de 1,5 pies) del desplazamiento de los cuatro defensores sin balón durante el primer segundo, sobre los " + thousands(vectors.length) + " vectores, dibujado como líneas de corriente cuyo grosor crece con el desplazamiento medio (clave en pies en la franja). El campo lleva a la defensa entera hundiéndose con la penetración además de la ayuda, y la franja lo dice. El viento solo se dibuja donde hubo defensores: las celdas con menos de diez vectores de masa kernel quedan en blanco, lo que eliminó un remolino espurio junto a la línea de fondo que tenía la primera versión. Desde el 29 de octubre el campo lo calcula el paquete (scbasket.wind.kernel_field) y scripts/help_wind.py lo escribe en reports/help_field.csv, una fila por punto de la rejilla con su masa kernel, el desplazamiento medio y la cuota del ayudante, de modo que la figura y la página leen el mismo fichero. Al moverlo cambiaron 3 de los 3,4 millones de píxeles de la figura: el campo sale ahora de los vectores en memoria y no de su CSV releído, que difiere en el último decimal."),
  p(`Debajo, en naranja, la cuota de los defensores que empiezan en cada punto que son el ayudante: la media kernel de una bandera 0/1 con el mismo ancho de banda, pintada solo donde empiezan al menos ${RATE_MIN_WEIGHT} defensores de masa kernel. Con ese umbral el error estándar binomial de la tasa queda cerca de ${es(100 * rateSe, 1)} puntos, por debajo del ancho de una banda de color (5 puntos), y el suavizado deja de invadir la zona del triple de esquina, donde no empieza ningún defensor. Sustituye, desde el 29 de octubre, a la densidad bruta de los orígenes del ayudante, que un cribado del council de ese día (46 sobre 100, no lista) señaló porque se leía como una tasa. El título ya no afirma de dónde viene la ayuda: dice adónde va la defensa, y la franja da la esquina como ocupación (${cornerBand.n_defenders} de ${thousands(vectors.length)} defensores, el ${pct(num(cornerBand.defender_share), 1)}) y el ${pct(num(base.helper_above_ball))} de ayudantes que empiezan por encima del balón, con sus tasas por defensor (sección 12). Todo número de la figura sale de reports/help_table.csv, help_vectors.csv y help_base_rate.csv (el campo, de help_field.csv), y la figura no se genera si los tres no coinciden en los ayudantes.`),
];

// La figura 2 lee reports/help_kinds_summary.csv (variante primaria); sus nombres, a 1,52 s y en fotogramas.
const nk = (measure, kind, h) => hk.find((r) => r.measure === measure && r.kind === kind && r.variant === "primary" && Math.round(num(r.horizon) * 25) === h);
const nkCi = (r) => `${sg(num(r.mean))} (${sg(num(r.ci_low))} a ${sg(num(r.ci_high))})`;
const nkCount = (kind, variant) => num(hk.find((r) => r.measure === "count" && r.kind === kind && r.variant === variant).n);
const F2C = nk("paired_diff", "near_committed", HEADLINE), F2R = nk("paired_diff", "near_committed_ref", HEADLINE);
// Desde el 31 de octubre la afirmación es la media propia de las comprometidas (sección 17), con su escala.
const holds0 = (r) => num(r.ci_low) <= 0 && 0 <= num(r.ci_high);
const SCALE = (variant) => hk.find((r) => r.measure === "scale" && r.kind === "near_committed" && r.variant === variant && (variant === "helper_step" || Math.round(num(r.horizon) * 25) === HEADLINE));
const ONE_ROT = SCALE("one_rotates"), STEP = SCALE("helper_step");
const F2L = nk("contrast", "long", HEADLINE);
if (F2C.reading !== "ABSENCE") throw new Error("9.2: la lectura de la ayuda comprometida a 1,5 s ya no es AUSENCIA");
if (!HORIZONS.every((h) => holds0(nk("paired_diff", "near_committed", h)))) throw new Error("9.2: algún intervalo de la ayuda comprometida ya no contiene el cero");
if (!HORIZONS.every((h) => holds0(nk("paired_diff", "near_committed_ref", h)))) throw new Error("9.2: algún intervalo de la referencia ya no contiene el cero");
if (!HORIZONS.every((h) => holds0(nk("contrast", "near_committed", h)))) throw new Error("9.2: algún contraste ya no contiene el cero, «se da y no se afirma» hay que revisarlo");
if (!(num(F2C.ci_high) < num(ONE_ROT.mean))) throw new Error("9.2: la cota ya no queda por debajo de la escala de una rotación");
const s9b = [
  h2("9.2 Figura 2: quién cubre al hombre que deja"),
  ...figure("wind_figure_2_who_covers.png", `Figura 2. Nadie se mueve hacia el hombre que deja el ayudante más que hacia cualquier otro atacante: a ${hsec(HEADLINE)} s de arrancar la penetración, cuando el defensor más cercano al balón ayuda y no vuelve al punto donde empezó su hombre, los otros tres defensores se mueven hacia él lo mismo que hacia los demás, con la referencia al lado y una línea discontinua en lo que leería una sola rotación.`),
  p(`Hasta el 30 de octubre la figura 2 promediaba a todos los ayudantes publicados (movimiento de 4 pies o más) frente a las penetraciones sin ayudante; con la tesis acotada a la ayuda cercana que se compromete (sección 13) los datos cambiaron a reports/help_kinds_summary.csv y reports/near_committed_drives.csv, con el mismo diseño. Desde el 31 de octubre la clase es la reclasificada y la figura lleva la ausencia medida, con su cota y su escala (sección 17). Un punto por ayuda cercana comprometida (${nkCount("flag", "near_committed")} de las ${nkCount("drives", "resolved")} penetraciones resueltas: el defensor sin balón más cercano al balón se acerca ${es(NEAR_STEP_FT, 0)} pies o más al jugador con balón en 1,0 s y a los 2,0 s está más de ${es(RECOVER_FT, 0)} pie más lejos del punto donde empezó su hombre que al arrancar), allí donde está a ${hsec(HEADLINE)} s el atacante al que marcaba. El color y la forma dicen quién es el defensor más cercano a él, y la leyenda da su cuota con la de la referencia entre paréntesis (las ${nkCount("flag", "near_ref")} penetraciones en que el más cercano se mueve menos de 1 pie hacia el jugador con balón: se queda en casa): su propio defensor, el ayudante, el ${pct(num(F2C.nearest_helper))} frente al ${pct(num(F2R.nearest_helper))}, el emparejado del jugador con balón el ${pct(num(F2C.nearest_handler_def))} frente al ${pct(num(F2R.nearest_handler_def))} y un tercer defensor el ${pct(num(F2C.nearest_third))} frente al ${pct(num(F2R.nearest_third))}. Que el ayudante sea el más cercano es casi cierto por construcción, porque marcaba a ese hombre al empezar; por eso el titular no es ese, sino la ausencia de rotación. Es una medida de distancia, no de intención. Los ${nkCount("flag", "near_committed")} puntos están todos: ninguna ventana termina antes de ${hsec(HEADLINE)} s. La figura ya no lleva la distancia mediana al defensor más cercano, que el CSV de la clase no guarda.`),
  p(`El panel de debajo es la afirmación: la rotación de los otros tres defensores hacia el hombre dejado menos hacia el placebo, en pies, con la media por penetración y su intervalo del 95 % para ${HORIZONS.map((h) => hsec(h)).join(" / ")} s, con la ayuda comprometida (negro) y con la referencia (gris). Junto a cada media de la serie negra van la mediana y la cuota de parejas por encima de cero (una pareja es una penetración y uno de los tres defensores). La serie negra es lo que se afirma: a ${hsec(HEADLINE)} s, ${nkCi(F2C)} ft sobre ${F2C.n} penetraciones, con lectura AUSENCIA, y sus tres intervalos contienen el cero (${HORIZONS.map((h) => nkCi(nk("paired_diff", "near_committed", h))).join(" / ")} ft); los datos descartan más de ${sg(num(F2C.ci_high))} ft hacia él, que es la cota. Una línea discontinua da la escala: ${sg(num(ONE_ROT.mean))} ft, lo que leería la media negra si uno de los tres se hubiera movido hacia el hombre dejado tanto como el ayudante se movió hacia el balón (mediana de ese paso, ${ft(num(STEP.median))}), con el placebo igual; la cota queda por debajo. La serie gris, la referencia, queda sobre el cero: ${nkCi(F2R)} ft a ${hsec(HEADLINE)} s, y sus tres intervalos contienen el cero. El contraste entre las dos, con su intervalo por bootstrap de dos muestras, se da y no se afirma: ${HORIZONS.map((h) => nkCi(nk("contrast", "near_committed", h))).join(" / ")} ft a ${HORIZONS.map((h) => hsec(h)).join(" / ")} s, con el cero dentro en los tres; hasta el 31 de octubre era la afirmación (sección 17). El pie de la figura da además el reparto por penetración (sección 17.3). La figura no se dibuja si la lectura de la serie negra no es AUSENCIA, si un intervalo de la serie negra queda por encima de cero, si uno de la referencia deja de contener el cero, si la cota no queda por debajo de la escala de una rotación, si uno de los dos rotadores designados no lee AUSENCIA o si el pase no lee LÍMITE (sección 17.6). Y cierra con dos calificativos al lado de la afirmación, no escondidos: sobre todos los ayudantes publicados el contraste a ${hsec(HEADLINE)} s es ${CT(HEADLINE) ? `${sg(num(CT(HEADLINE).contrast_mean))} (${sg(num(CT(HEADLINE).contrast_ci_low))} a ${sg(num(CT(HEADLINE).contrast_ci_high))})` : ""} ft, también sin rotación extra y con un intervalo ancho que contiene el cero; y la ayuda larga no se puede probar: ${nkCount("flag", "long")} de ${nkCount("drives", "resolved")} penetraciones cumplen su definición, con un contraste de ${nkCi(F2L)} ft (sección 13.6).`),
  p(`La cuota de hombre libre ya no va en la figura sino junto al 58,5 % de la sección 8, con su tasa base y como dato, no como coste, y es del ayudante publicado (todo movimiento de 4 pies o más): el hombre dejado está libre (nadie a ${es(OPEN_FT, 0)} pies) el ${pct(num(SH(HEADLINE, true).left_open0_share))} al arrancar y el ${pct(num(SH(HEADLINE, true).left_open_share))} a ${hsec(HEADLINE)} s, y el hombre comparable en las penetraciones sin ayudante el ${pct(num(SH(HEADLINE, false).left_open0_share))} y el ${pct(num(SH(HEADLINE, false).left_open_share))}. La figura sustituye a la primera versión de la semana 2, los puntos del hombre dejado coloreados por estar libre o no, que sin tasa base inducía a error (sección 8).`),
  h2("9.3 Lo que se corrigió tras mirar la primera versión"),
  p("Las figuras se miraron antes de darlas por buenas, y la primera versión tenía defectos que solo se ven mirándolas: en la figura 1, el bloque de texto y la etiqueta del balón quedaban tapados por las líneas de corriente y había un remolino espurio junto a la línea de fondo; en la figura 2 de entonces (los puntos del hombre libre, ya sustituida), el histograma inserto y el texto pisaban puntos de la pista, la leyenda tapaba puntos arriba a la derecha, y las líneas grises desde el origen del ayudante ensuciaban sin aportar nada que no estuviera ya en la figura 1. Se movió todo lo que no es dato a la franja inferior, se endureció la máscara del campo, se quitaron las líneas, y en el título de la figura 2 se retiró \"lejos del balón\", que el 55 % no sostiene. Una tercera pasada arregló el solape entre el texto de la franja y la clave de grosor."),
  p(`El mapa de viento redibujado el 29 de octubre (sección 12.5) se miró tres veces. La primera, con un umbral de 30 defensores, pintaba tasa dentro de la zona del triple de esquina por puro arrastre del suavizado (6 de los 24 puntos de la rejilla que caen en esa zona), contradiciendo el subtítulo; con ${RATE_MIN_WEIGHT} no se pinta ninguno. La leyenda del blanco pasó de "pocos empiezan ahí" a "pocos para dar una tasa", porque las líneas de corriente, con su propio umbral de 10, sí entran en zonas blancas. Y el "dos de cada tres" tecleado del subtítulo pasó a ser la cuota calculada. El texto de la franja va a 11 puntos, como en la figura 2; el cribado había señalado los 8 y 9 puntos de la versión anterior.`),
  p("Ese mismo día, un cribado del council de ese mapa redibujado le dio 37 sobre 100, no lista (juzgada sobre una descripción escrita, no sobre la imagen): con solo dos figuras y la tesis ya reducida a la segunda ayuda, una figura de contexto gasta la mitad del presupuesto visual en un dato de ocupación y un nulo, y el contraste por orientación es en buena parte la propia definición del ayudante. Propuso una penetración real con el ayudante saliendo, el hombre dejado y los otros tres quietos. Al construirla salió que la penetración de la regla de entonces no tenía a los otros quietos: dos se acercaban unos 7 pies al hombre dejado, y lo mismo a los demás atacantes. Elegir otra que sí lo pareciera habría sido escoger a dedo, así que la figura 1 enseña esa misma penetración como la medida y no como la conclusión, con su percentil (sección 9.1). Se miró dos veces: la primera tenía al hombre dejado hueco en los dos extremos, contra la leyenda; un ordinal mal escrito (\"23th\"); una cifra separada de su unidad por el salto de línea; y la media y la mediana con un decimal, contra los dos de la figura 2."),
  p(`Un segundo cribado del council, ya sobre esta figura, le dio 48 sobre 100, todavía no lista, con dos fortalezas compartidas (la regla y el percentil la hacen honesta; enseña el instrumento que la figura 2 no puede) y un punto ciego que se comprobó con las cifras: la media de aquella penetración la producía un solo defensor que se alejaba (era la de entonces, que ya no es la de la figura: sección 9.1), así que sin el texto se leía "dos de tres rotan", y el subtítulo "the whole defence closes in" empujaba esa lectura. Se aplicó: un subtítulo que dice que la jugada enseña la medida y no el resultado; el texto recortado a las barras y una línea; la tira de todas las medias por penetración; la pista recortada por encima de la jugada para dibujarla más grande; y se comprobó reducida a 800 píxeles de ancho, el del README, donde el texto del cuerpo queda en unos 17 píxeles. El percentil se quedó en la figura y no pasó al README, como proponía el cribado, porque es el calificador de esta jugada y va junto a ella.`),
  p("Aun así no se explicaba sola: al verla, Javier preguntó qué representaba. No se volvió a pasar por el council, porque sus cribados juzgan una descripción escrita y una descripción no puede medir si la imagen se lee sola. La prueba fue una lectura en frío de la imagen misma: un agente sin ningún contexto del proyecto, que solo podía abrir el PNG, contestó qué pregunta hace la figura, qué pasa en la pista, qué miden las barras y la tira, y qué no pudo descifrar. Sobre la versión anterior adivinó el signo de las barras, no supo si el placebo era un jugador o una media, no entendió \"la ausencia\" del título ni los rótulos de las esquinas, y leyó mal dónde empezaba el hombre dejado. Se rehízo: el título pasa a ser la pregunta (\"Does anyone else move toward the man the helper left?\", que la figura 2 contesta con \"Nobody else moves toward the man the helper left\"); la leyenda de seis entradas se sustituye por nombres sobre la pista; solo va en color el reparto de la medida; flechas en lugar de hueco y relleno; las barras toman el color de su objetivo en la pista (negro hacia el hombre dejado, gris hacia los demás); una columna con la diferencia de cada defensor y su media enlaza las barras con la tira; y la tira lleva su eje de penetraciones. Una segunda lectura en frío, sobre esa versión, leyó bien el signo, el placebo como media y la diferencia, y su conclusión fue la correcta y prudente: en esta jugada nadie rota hacia él, y si la mediana se distingue del cero es cosa de la figura 2. Sus dudas restantes se corrigieron en esta misma versión: el texto define \"hacia\" (su propio movimiento a lo largo de la línea desde donde empieza hasta donde está el objetivo en ese instante) y dice por qué hace falta el placebo (la defensa entera se hunde con la penetración); el trazo del hombre dejado, leído como un enlace, termina ahora en flecha como los demás; y \"helped drives\" pasa a \"drives with a helper\". Un modelo descifra leyendas mejor que un lector con prisa, así que esta prueba es necesaria y no suficiente: faltaba que Javier la mirase, y la aprobó el mismo 29 de octubre."),
];

const s10 = [
  h1("10. La reorientación: una sola entrada, el council y la segunda ayuda (28 de octubre de 2026)", { pageBreakBefore: true }),
  h2("10.1 Una sola entrada de baloncesto"),
  p("Al cerrar la semana 2, Javier decidió que esta será la única entrada de baloncesto que presente. El rebote y el kit de calibración no se envían: quedan como trabajo previo y como infraestructura (el paquete scbasket, la caché de fotogramas y sus tests, que esta entrada ya usa). La duda de si una persona podía presentar dos entradas deja de importar. En el mismo mensaje propuso orientar la entrada a cómo influyen las primeras y, sobre todo, las segundas ayudas: la rotación que cubre al atacante que dejó la primera."),
  h2("10.2 El council"),
  p("La propuesta pasó por un council: cinco consejeros con papeles distintos, que no se ven entre sí, y dos revisores que leen sus respuestas anonimizadas; la nota se calcula sumando puntos sobre una base de 50. Un cribado previo, con la entrada tal como estaba, había dado 51 sobre 100. Con la pregunta del efecto sobre el resultado, el council completo dio 37."),
  grid(["Consejero", "Nota", "Lo que más pesó"], [
    ["Contrarian", "43", "El enlace con el resultado es nulo, y la segunda ayuda hereda un ruido encadenado (el espejo, el retroceso de toda la defensa, dos umbrales seguidos)"],
    ["First Principles", "37", "La variable correcta es la geometría de la rotación, no los puntos; la segunda ayuda no tiene potencia para un efecto"],
    ["Expansionista", "55", "La segunda ayuda (help the helper) no la cubre nadie; medir cuánto tarda alguien en cubrir al hombre dejado"],
    ["Outsider", "30", "La pregunta es cómo influyen, y la evidencia dice que no influyen; el título debería hablar de cómo rota la defensa"],
    ["Executor", "45", "Una sonda corta antes de comprometer las siete semanas"],
  ], [2000, 900, 6126], { align: ["l", "r", "l"] }),
  p("Media 42; el peer review restó 5 por un punto ciego grave y 5 por un rojo que nadie rebatió, y sumó 5 por una fortaleza unánime (el hueco: nadie mide la ayuda en este bundle). Total 37, muy arriesgado con esa pregunta. El punto ciego se comprobó con el dato: los puntos por oportunidad son 0,911 con ayudante y 0,905 sin él (280 y 338 penetraciones), y el intervalo de confianza del 95 % de la diferencia va de −0,17 a +0,18. No es un nulo: con diez partidos no se puede ver ningún efecto que no sea enorme. Los cinco coincidieron en lo que sí se sostiene: medir la cadena de rotación como geometría, no como efecto sobre el marcador."),
  source("council de la sesión del 28 de octubre de 2026 y recuento de puntos por oportunidad (second_help_recon.py, script de sesión), registrados en tasks/todo.md."),
  h2("10.3 La sonda de la segunda ayuda"),
  p("Antes de planificar se sondeó la segunda ayuda con un diseño que lleva su propio control: para cada uno de los tres defensores que no son ni el emparejado del balón ni el ayudante, su desplazamiento propio se proyecta hacia el hombre dejado y, como placebo, hacia los demás atacantes sin balón que no son su propio hombre. Si hubiera rotación, la proyección hacia el hombre dejado superaría a la del placebo. La sonda empezó como script de sesión; su diseño y sus cifras viven ahora en el paquete (scbasket.rotation, scripts/second_help.py) y en reports/second_help_*.csv, y esta memoria las lee de ahí en la sección 11. Lo que decidió: la segunda ayuda entendida como rotación de un tercer defensor no aparece contra el placebo, y el porcentaje de hombres dejados libres de la semana 1 no tenía tasa base (sección 8)."),
  source("sonda del 28 de octubre de 2026, reproducida en reports/second_help_*.csv el 28 y el 29 de octubre (fase A de tasks/todo.md); los intervalos de 1,5 y 2,0 s difieren en pocas centésimas de los de la sonda porque el paquete siembra cada celda del bootstrap por separado."),
  h2("10.4 Lo decidido"),
  bullet([bold("Título: \"Nobody helps the helper\". "), run("Lo eligió Javier frente a la recomendación del planificador, que proponía mantener el anterior con este como subtítulo: la segunda ayuda que no llega pasa al frente. Tesis en una línea: la ayuda sopla desde el centro y nunca desde la esquina, y nadie ayuda al que ayuda; al hombre que deja le cubre el propio ayudante o nadie, medido contra un placebo. El 29 de octubre se retiró la primera mitad, que medía dónde están los defensores y no de dónde ayudan (sección 12.4).")]),
  bullet([bold("Repositorio público: este. "), run("Se etiqueta el estado actual como bounce-final y el README del rebote pasa a docs/bounce/; el paquete, la caché y los tests compartidos se quedan donde ya funcionan al clonar.")]),
  bullet([bold("Figura 2: quién cubre al hombre dejado. "), run("Los puntos se colorean según quién es su defensor más cercano y, debajo, la rotación frente al placebo con su intervalo y la tasa base en la misma frase.")]),
  bullet([bold("Cómo se trabaja. "), run("El plan por fases lo escribió Fable 5.1 como planificador, y cada tarea se ejecuta con el modelo de su etiqueta (Sonnet la mayoría, Haiku lo mecánico, Opus el motor de la página y la verificación final, Fable el guion visual de la página). A petición de Javier, una sola revisión adversarial, al cierre, y ninguna puerta que bloquee.")]),
];

// Datos de la sección 11, leídos de reports/second_help_*.csv.
const SHH = SH(HEADLINE, true);
const SHN = SH(HEADLINE, false);
const nLeft = num(SH(25, true).n_drives) + num(SH(25, false).n_drives); // penetraciones con hombre dejado
const hs = HORIZONS.map(hsec).join(" / ");
// La afirmación es "no más rotación que sin ayudante": se comprueba, no se supone. Lo mismo hace la figura.
if (HORIZONS.some((h) => num(CT(h).contrast_ci_low) > 0)) throw new Error("con ayudante menos sin ayudante queda por encima de cero: revisar el texto de la sección 11");
if (!HORIZONS.every((h) => [true, false].every((hp) => num(SH(h, hp).ci_high) < 0))) throw new Error("algún IC de la sección 11.2 incluye 0: revisar el texto");
const gameN = gameRows.map((r) => num(r.n_drives));
const gridCells = shSens.map((r) => ({ ...r, ft: num(r.help_ft), h: num(r.horizon), hp: bool(r.helped) }));
const negCells = gridCells.filter((r) => num(r.mean_diff) < 0).length;
const zeroCells = gridCells.filter((r) => num(r.ci_high) >= 0)
  .map((r) => `${r.hp ? "con" : "sin"} ayudante, ${es(r.ft, 0)} ft, ${es(num(r.horizon_s), 1)} s`);
const PH = shPass.find((r) => bool(r.helped));
const PN = shPass.find((r) => !bool(r.helped));
const seP = Math.sqrt(num(PH.share_to_left) * (1 - num(PH.share_to_left)) / num(PH.n_first_pass));
const CL = shClose.find((r) => bool(r.helped) && bool(r.receiver_is_left));
const CN = shClose.find((r) => !bool(r.helped) && !bool(r.receiver_is_left));

// Datos de la sección 11.9, leídos de reports/matchup_coherence.csv y second_help_matchup_check.csv.
const mCoh = readCsv(path.join(REPORTS, "matchup_coherence.csv"));
const mChk = readCsv(path.join(REPORTS, "second_help_matchup_check.csv"));
const MC = (metric) => mCoh.find((r) => r.metric === metric);
const MK = (sub, series, h = 1.52) => mChk.find((r) => r.subset === sub && r.series === series && Math.abs(num(r.horizon_s) - h) < 0.005);
const mcShare = (metric) => pct(num(MC(metric).n) / num(MC(metric).of), 1);
const mcOf = (metric) => `${MC(metric).n} de ${MC(metric).of}`;
const mkText = (r) => `${sg(num(r.mean))} (${sg(num(r.ci_low))} a ${sg(num(r.ci_high))})`;
const MATCH_HORIZONS = [...new Set(mChk.map((r) => num(r.horizon_s)))];
// Lectura fijada antes de correr: se cumple si el IC de cada contraste corroborado contiene el cero y la
// media con ayudante queda en o por debajo de cero; falla si un IC queda por encima de cero o si la media
// con ayudante sube de forma monótona al apretar la corroboración. Se comprueba, no se supone.
for (const h of MATCH_HORIZONS) {
  const means = ["S0", "S1", "S2", "S3"].map((s) => num(MK(s, "helped", h).mean));
  const cons = ["S1", "S2", "S3"].map((s) => MK(s, "contrast", h));
  const rising = means.every((m, i) => i === 0 || m > means[i - 1]);
  if (cons.some((r) => num(r.ci_low) > 0 || num(r.ci_high) < 0) || means.some((m) => m > 0) || rising) {
    throw new Error(`la lectura fijada de la sección 11.9 no se cumple a ${h} s: revisar el texto`);
  }
}

const sSecond = [
  h1("11. La segunda ayuda: una ausencia medida", { pageBreakBefore: true }),
  p(`La pregunta es qué pasa con el atacante que deja el ayudante: si alguien se mueve hacia él, y quién es el defensor más cercano. Se mide como geometría y no como efecto sobre el marcador, porque la sección 10.2 muestra que con diez partidos los puntos por oportunidad no tienen potencia. Todo lo de esta sección sale de reports/second_help_*.csv, escritos por scripts/second_help.py con el módulo scbasket.rotation. El resultado con su calificador: contra el placebo, los otros tres defensores se mueven hacia el hombre dejado menos que hacia los demás atacantes (media por penetración ${sft(num(SHH.mean_diff))} a ${hsec(HEADLINE)} s), pero el par típico queda cerca del placebo (mediana ${sft(num(SHH.median_diff))}) y la media la arrastran las colas; y el defensor más cercano al hombre dejado es el propio ayudante en el ${pct(num(SHH.nearest_helper))} de las penetraciones con ayudante, pero eso casi viene dado, porque marcaba a ese hombre al empezar: sin ayudante, su propio defensor es el más cercano en el ${pct(num(SHN.nearest_helper))}.`),
  h2("11.1 El diseño del placebo"),
  p(`Hay ${nLeft} penetraciones resueltas con un hombre dejado, ${SH(25, true).n_drives} con ayudante (movimiento de ayuda de ${es(HELP_FT, 0)} pies o más en 1,0 s, como en la sección 6) y ${SH(25, false).n_drives} sin él. En cada una, los tres defensores que no son ni el emparejado del jugador con balón ni el ayudante dan ${SH(25, true).n_pairs / SH(25, true).n_drives} parejas (penetración, defensor). De cada defensor se toma su desplazamiento propio durante el horizonte y se proyecta sobre dos direcciones: hacia el hombre dejado, y hacia el placebo, que son los demás atacantes sin balón que no son su propio hombre. La diferencia, hacia él menos placebo, es negativa si el defensor se movió más hacia otros atacantes que hacia el hombre dejado. Se mide a ${hs} s (25, 38 y 50 fotogramas; el segundo es 1,52 s). En las penetraciones sin ayudante, el hombre comparable es el del defensor no emparejado que más se movió sin llegar al umbral, la misma convención de la sección 8.`),
  h2("11.2 La diferencia emparejada"),
  grid(["Horizonte", "Ayudante", "Penetraciones", "Parejas", "Media por penetración, ft (IC 95 %)", "Mediana (parejas)", "Parejas > 0"],
    HORIZONS.flatMap((h) => [true, false].map((hp) => {
      const r = SH(h, hp);
      return [`${hsec(h)} s`, hp ? "con" : "sin", r.n_drives, r.n_pairs, meanCi(r), sft(num(r.median_diff)), pct(num(r.share_diff_positive))];
    })),
    [1150, 1100, 1500, 1000, 2176, 1150, 950], { align: ["l", "l", "r", "r", "r", "r", "r"] }),
  source("reports/second_help_summary.csv (mean_diff, ci_low, ci_high, median_diff, share_diff_positive). El intervalo es el de la media por penetración, por bootstrap sobre penetraciones; la mediana y la cuota son sobre parejas (una pareja es una penetración y uno de los tres defensores). El contraste con ayudante menos sin él sale de reports/second_help_contrast.csv (contrast_mean, contrast_ci_low, contrast_ci_high)."),
  p(`La media por penetración de la diferencia es negativa en los tres horizontes, con ayudante (${HORIZONS.map((h) => sg(num(SH(h, true).mean_diff))).join(" / ")} ft a ${hs} s) y sin él (${HORIZONS.map((h) => sg(num(SH(h, false).mean_diff))).join(" / ")} ft), y su intervalo del 95 % queda por debajo de cero en los seis casos. Pero la mediana sobre parejas con ayudante es ${HORIZONS.map((h) => sg(num(SH(h, true).median_diff))).join(" / ")} ft y solo el ${HORIZONS.map((h) => pct(num(SH(h, true).share_diff_positive))).join(" / ")} de las parejas está por encima de cero: el par típico queda cerca del placebo y la media la arrastran las colas, no una respuesta general de la defensa. Como la serie sin ayudante también es negativa (la métrica tiene su propio sesgo geométrico: el hombre dejado está en el perímetro), la referencia es esa serie y no el cero. La diferencia con ayudante menos sin él, de la media por penetración, con su intervalo del 95 % por bootstrap de dos muestras (cada grupo se remuestrea por separado), es ${CONTRAST_TEXT} ft a ${hs} s: ningún intervalo queda por encima de cero, así que con ayudante los otros tres defensores no rotan más hacia el hombre dejado que sin ayudante, y la ayuda no deja una rotación distinguible de la que ya había. Un movimiento de ${es(HELP_FT, 0)} pies o más hacia el hombre dejado aparece en el ${pct(num(SHH.share_mover_left))} de las penetraciones con ayudante a ${hsec(HEADLINE)} s, contra el ${pct(num(SHH.share_mover_placebo))} hacia el placebo.`),
  h2("11.3 Por partido"),
  p(`A ${hsec(HEADLINE)} s con ayudante, la mediana por partido es negativa en ${gameSigns.pairNeg} de los ${gameSigns.games} partidos tomada sobre parejas y en ${gameSigns.driveNeg} de los ${gameSigns.games} tomada sobre penetraciones; el valor negativo más cercano a cero es ${sg(gameSigns.pairClosest)} ft sobre parejas y ${sg(gameSigns.driveClosest)} ft sobre penetraciones. Cada partido aporta entre ${Math.min(...gameN)} y ${Math.max(...gameN)} penetraciones con ayudante: el corte se publica y no se usa para decidir.`),
  source("reports/second_help_by_game.csv (median_diff por penetración, median_diff_pairs por pareja), contados al generar este documento."),
  h2("11.4 Sensibilidad"),
  grid(["Umbral", "Horizonte", "Penetraciones con ayudante", "Media con ayudante (IC 95 %)", "Media sin ayudante (IC 95 %)"],
    [3, 4, 5].flatMap((f) => HORIZONS.map((h) => {
      const a = gridCells.find((r) => r.ft === f && r.h === h && r.hp);
      const b = gridCells.find((r) => r.ft === f && r.h === h && !r.hp);
      return [`${es(f, 0)} ft`, `${es(num(a.horizon_s), 1)} s`, a.n_drives, `${meanCi(a)}`, `${meanCi(b)}`];
    })),
    [1000, 1100, 1900, 2513, 2513], { align: ["l", "l", "r", "r", "r"] }),
  source("reports/second_help_sensitivity.csv: umbral de ayudante de 3, 4 y 5 pies por los tres horizontes, en pies."),
  p(`La media es negativa en ${negCells} de las ${gridCells.length} celdas, y el intervalo del 95 % deja fuera el cero en ${gridCells.length - zeroCells.length}. ${zeroCells.length ? `Lo incluyen: ${zeroCells.join("; ")}.` : ""} Con ayudante, la mediana de las parejas es negativa en ${gridCells.filter((r) => r.hp && num(r.median_diff) < 0).length} de las ${gridCells.filter((r) => r.hp).length} celdas.`),
  h2("11.5 Quién está más cerca del hombre dejado"),
  grid(["Horizonte", "Ayudante", "Su defensor (el ayudante, si lo hay)", "Emparejado del balón", "Un tercero", "Distancia mediana"],
    HORIZONS.flatMap((h) => [true, false].map((hp) => {
      const r = SH(h, hp);
      return [`${hsec(h)} s`, hp ? "con" : "sin", pct(num(r.nearest_helper)), pct(num(r.nearest_handler_def)), pct(num(r.nearest_third)), ft(num(r.nearest_dist_median))];
    })),
    [1150, 1100, 2200, 1700, 1500, 1376], { align: ["l", "l", "r", "r", "r", "r"] }),
  source("reports/second_help_summary.csv (nearest_helper, nearest_handler_def, nearest_third, nearest_dist_median). En las penetraciones sin ayudante, la primera columna es el defensor propio del hombre comparable."),
  p(`Con ayudante, el más cercano al hombre dejado es el ayudante en el ${HORIZONS.map((h) => pct(num(SH(h, true).nearest_helper))).join(", ")} de las penetraciones (${hs} s), el emparejado del balón en el ${HORIZONS.map((h) => pct(num(SH(h, true).nearest_handler_def))).join(", ")} y un tercero en el ${HORIZONS.map((h) => pct(num(SH(h, true).nearest_third))).join(", ")}; sin ayudante, un tercero es el más cercano en el ${HORIZONS.map((h) => pct(num(SH(h, false).nearest_third))).join(", ")}. Dicho como medida y no como intención: la ayuda es un paso hacia el balón de alguien que sigue siendo, con más frecuencia que ningún otro, el defensor más cercano a su hombre.`),
  h2("11.6 Cuánto de libre está, con su tasa base"),
  grid(["Horizonte", "Con ayudante: libre al arrancar", "Con ayudante: libre al horizonte", "Sin ayudante: libre al arrancar", "Sin ayudante: libre al horizonte"],
    HORIZONS.map((h) => [`${hsec(h)} s`, pct(num(SH(h, true).left_open0_share), 1), pct(num(SH(h, true).left_open_share), 1), pct(num(SH(h, false).left_open0_share), 1), pct(num(SH(h, false).left_open_share), 1)]),
    [1200, 1950, 1950, 1963, 1963], { align: ["l", "r", "r", "r", "r"] }),
  source(`reports/second_help_summary.csv (left_open0_share, left_open_share); libre es que ningún defensor esté a ${es(OPEN_FT, 0)} pies. La cuota al arrancar usa todas las penetraciones del grupo (${SH(25, true).n_clear0} con ayudante y ${SH(25, false).n_clear0} sin él); la del horizonte, las que tienen medida en ese fotograma (a ${hsec(HEADLINE)} s, ${SHH.n_clear} y ${SHN.n_clear}).`),
  p(`El hombre dejado está libre el ${pct(num(SH(25, true).left_open_share), 1)} de las veces a 1,0 s, y eso no significa que la ayuda cree un hombre libre: el hombre comparable en las penetraciones sin ayudante lo está el ${pct(num(SH(25, false).left_open_share), 1)}, y el dejado empezaba más vigilado (${pct(num(SH(25, true).left_open0_share), 1)} libre al arrancar, contra ${pct(num(SH(25, false).left_open0_share), 1)}). La ayuda da espacio a quien empezaba más cerca de su defensor.`),
  h2("11.7 El pase"),
  grid(["Ayudante", "Penetraciones", "Con primer pase", "Al hombre dejado", "Libre cuando le llegó", "Libre cuando no"],
    [[PH, "con"], [PN, "sin"]].map(([r, w]) => [w, r.n_drives, r.n_first_pass, `${r.n_to_left} (${pct(num(r.share_to_left))})`, `${sft(num(r.left_clear_when_got_it))} (n = ${r.n_left_got_it})`, `${sft(num(r.left_clear_when_not))} (n = ${r.n_left_missed})`]),
    [1200, 1500, 1300, 1600, 1713, 1713], { align: ["l", "r", "r", "r", "r", "r"] }),
  source("reports/second_help_pass.csv; libre es la distancia al defensor más cercano en el fotograma del pase."),
  p(`Con ayudante hay un primer pase en ${PH.n_first_pass} de las ${PH.n_drives} penetraciones y va al hombre dejado en ${PH.n_to_left} (${pct(num(PH.share_to_left))}, con un intervalo normal del 95 % de ${pct(num(PH.share_to_left) - 1.96 * seP)} a ${pct(num(PH.share_to_left) + 1.96 * seP)}); si el receptor fuera uno de los cuatro compañeros al azar sería el ${pct(1 / 4)}, de modo que con este tamaño no se distingue de eso. En el fotograma del pase (mediana ${es(num(PH.median_delay_s), 2)} s) el hombre dejado es el compañero más libre solo en el ${pct(num(PH.left_most_open_share), 1)} de los casos y el receptor lo fue en el ${pct(num(PH.receiver_most_open_share), 1)}. Cuando le llegó el balón tenía ${sft(num(PH.left_clear_when_got_it))} de margen, y cuando no le llegó, ${sft(num(PH.left_clear_when_not))}; son distancias medidas en el fotograma del pase y no dicen por qué se pasó a otro.`),
  h2("11.8 El X-out: un límite"),
  p(`Lo que sigue al pase, la rotación del defensor que cierra sobre el receptor (el X-out), no se puede juzgar con estos datos. Los closeouts del proveedor que caen sobre el hombre dejado con ayudante son ${CL.n}: cierra su propio defensor, que es el ayudante, en el ${pct(num(CL.closer_own_share))} y otro defensor en el ${pct(num(CL.closer_other_share))}, frente al ${pct(num(CN.closer_other_share))} de cierres de otro defensor cuando nadie ayudó (${CN.n} casos). Con ${CL.n} casos un solo closeout mueve ${es(100 / num(CL.n), 1)} puntos de la cuota: no se dice nada y viaja como límite.`),
  source("reports/second_help_closeouts.csv (n, closer_own_share, closer_other_share)."),
  h2("11.9 Los emparejamientos del proveedor"),
  p("La pregunta es si el resultado de las secciones anteriores sobrevive a un error de la tabla matchups del proveedor, que dice quién marca al jugador con balón y a qué atacante marcaba el ayudante (el hombre dejado). No hay vídeo en los datos abiertos, así que esa tabla no se ha contrastado nunca con la realidad. Un error empujaría el resultado hacia la ausencia: si el hombre dejado no es el atacante que el ayudante marcaba, es en la práctica uno más de los atacantes del placebo, y la proyección hacia él se parece a la proyección hacia el placebo, con lo que la diferencia emparejada se acerca a cero sin que haya nada que medir."),
  p("Lectura fijada antes de correr la sonda: se cumple si el intervalo del 95 % del contraste con ayudante menos sin él contiene el cero en cada subconjunto corroborado y la media con ayudante queda en o por debajo de cero; falla si el intervalo de un contraste queda por encima de cero o si la media con ayudante sube de forma monótona al apretar la corroboración. La sonda corre en scripts/matchup_check.py."),
  p(`Coherencia al fotograma de arranque, sobre las ${MC("resolved drives").n} penetraciones resueltas: el defensor del jugador con balón figura asignado en ${mcOf("handler's defender assigned")} (${mcShare("handler's defender assigned")}); de esas, ese defensor es el más cercano en ${mcOf("assigned defender is the nearest")} (${mcShare("assigned defender is the nearest")}) y coincide con el ballhandlerDefId que da el propio proveedor en la tabla de penetraciones en ${mcOf("assigned defender is drives.ballhandlerDefId")} (${mcShare("assigned defender is drives.ballhandlerDefId")}). Ningún defensor aparece asignado dos veces en una misma penetración (${mcOf("drives with a defender assigned twice")}). Con un hombre dejado, el ayudante es el defensor más cercano a él al arrancar en ${mcOf("helper is nearest to the man left at the start")} penetraciones (${mcShare("helper is nearest to the man left at the start")}), y está a 10 pies o menos en ${mcOf("helper within 10 ft of the man left at the start")} (${mcShare("helper within 10 ft of the man left at the start")}). Que el emparejado no sea el más cercano no prueba un error, porque la cercanía es solo un indicio; lo que se mide es cuánto concuerdan las dos fuentes.`),
  p(`Subconjuntos anidados: S0, todas las penetraciones con hombre dejado (reproduce las secciones 11.2 y siguientes, y el script lo comprueba contra los CSV publicados); S1, además el defensor del emparejado del balón es a la vez el más cercano y el ballhandlerDefId del proveedor; S2, además el ayudante es el defensor más cercano al hombre dejado al arrancar; S3, además el ayudante empieza a 10 pies o menos de él. A ${hsec(HEADLINE)} s:`),
  grid(["Subconjunto", "Penetraciones (con / sin)", "Media con ayudante, ft (IC 95 %)", "Media sin ayudante, ft (IC 95 %)", "Con menos sin, ft (IC 95 %)"],
    ["S0", "S1", "S2", "S3"].map((s) => [s, MK(s, "contrast").n_drives.replace("/", " / "), mkText(MK(s, "helped")), mkText(MK(s, "unhelped")), mkText(MK(s, "contrast"))]),
    [1400, 1600, 2008, 2008, 2010], { align: ["l", "r", "r", "r", "r"] }),
  source("reports/second_help_matchup_check.csv (subset, horizon_s, series, n_drives, mean, ci_low, ci_high), a 1,52 s; reports/matchup_coherence.csv (metric, n, of). Los intervalos son los de second_help.py, bootstrap sobre penetraciones con la misma semilla."),
  p(`La lectura fijada se cumple a ${MATCH_HORIZONS.map((h) => es(h, 1)).join(", ")} s: ningún intervalo de contraste queda por encima de cero, todas las medias con ayudante son negativas y no suben con la corroboración (a ${hsec(HEADLINE)} s: ${["S0", "S1", "S2", "S3"].map((s) => sg(num(MK(s, "helped").mean))).join(", ")} ft). El contraste va de ${sg(num(MK("S2", "contrast").mean))} ft en S2 a ${sg(num(MK("S3", "contrast").mean))} ft en S3, siempre con el cero dentro.`),
  p(`El límite es doble. Primero, es coherencia y no validación: las tres fuentes que se comparan (la tabla matchups, la cercanía y el ballhandlerDefId) son todas del mismo proveedor o derivan de las mismas posiciones, de modo que si coinciden es porque son consistentes, no porque estén acertadas. Segundo, los intervalos se ensanchan al estrechar el subconjunto: en S3, con ${MK("S3", "contrast").n_drives.replace("/", " con ayudante y ")} sin él, el intervalo del contraste va de ${sg(num(MK("S3", "contrast").ci_low))} a ${sg(num(MK("S3", "contrast").ci_high))} ft, de modo que solo descarta un contraste por encima de ${sg(num(MK("S3", "contrast").ci_high))} ft. Lo que la sonda dice es que, donde el emparejamiento está corroborado, la ausencia no desaparece ni se invierte; no dice que la tabla sea correcta.`),
];

const sCorner = [
  h1("12. La esquina, con su tasa base (29 de octubre de 2026)", { pageBreakBefore: true }),
  p(`La primera mitad de la tesis descansaba en que el ayudante casi nunca sale del lado de la esquina: el ${pct(N.fromCorner, 1)} de los ayudantes, entre el ${pct(Math.min(...cornerSide))} y el ${pct(Math.max(...cornerSide))} en las doce celdas de la sección 8.4. Esa cuota no tenía denominador, y un cribado del council sobre la figura 1 (46 sobre 100, no lista) lo señaló el mismo día: el naranja era la densidad bruta de los orígenes del ayudante, no una tasa por defensor. Esta sección pone esa tasa y la compara con la que predice dónde queda el balón respecto a cada defensor. Todo sale de reports/help_base_rate.csv, que escribe scripts/help_wind.py.`),
  p("Implementación: scbasket.wind añade a cada vector la distancia desde donde empieza el defensor hasta donde está el jugador con balón al final del horizonte (target_dist) y la componente a lo largo de la pista del vector unitario hacia ese punto (target_bearing_x, negativa si el punto queda hacia el aro). scripts/help_wind.py añade helper_flags, helper_rate y base_rate, escribe el CSV y lleva la tasa por defensor a las doce celdas de sensibilidad y a cada partido; el script no corre si el ayudante leído de los vectores no es el de help_table. Los intervalos son del 95 % por bootstrap sobre penetraciones (una penetración remuestreada trae a sus cuatro defensores), con semilla fija. tests/test_help_wind.py construye un caso en que un grupo ayuda solo según su estrato y comprueba que la razón es 1 estandarizando y distinta de 1 sin estandarizar; la mutación que estandariza dentro de cada grupo hace fallar el test (1,0 contra 1,28), y se vio fallar antes de revertirla. Un test nuevo de tests/test_wind.py fija que un defensor por encima del balón que solo se hunde 4 pies puntúa 4 pies de ayuda."),
  h2("12.1 Por defensor: dónde empiezan y cuántas veces son el ayudante"),
  grid(["Distancia al centro (|y|)", "Defensores (cuota)", "Ayudantes (cuota)", "Tasa por defensor (IC 95 %)"],
    yBands.map((r) => [bandName(r.group), `${r.n_defenders} (${pct(num(r.defender_share), 1)})`, `${r.n_helpers} (${pct(num(r.helper_share), 1)})`, rateCi(r)]),
    [2826, 1900, 1900, 2400], { align: ["l", "r", "r", "r"] }),
  source("reports/help_base_rate.csv (grouping y_band, standardised_by none), a 4 pies y 1,0 s."),
  p(`De los ${thousands(vectors.length)} defensores sin balón, ${cornerBand.n_defenders} (el ${pct(num(cornerBand.defender_share), 1)}) empiezan a más de 18 pies del centro, y ${nCorner3 === 0 ? "ninguno" : nCorner3} en la zona del triple de esquina. De ahí salen ${cornerBand.n_helpers} ayudantes. Cada uno de esos defensores es el ayudante el ${rateCi(cornerBand)} de las veces, frente al ${pct(num(middleBand.rate), 1)} de los que empiezan en el centro, y el ${pct(num(base.helper_rate), 1)} de todos: la esquina está vacía, y con ${cornerBand.n_defenders} defensores no se puede decir si ayuda menos. En las ocho celdas de sensibilidad a 1,0 y 1,5 s, la tasa de la esquina menos la del centro va de ${sg(100 * Math.min(...cornerMinusMiddle), 1)} a ${sg(100 * Math.max(...cornerMinusMiddle), 1)} puntos; a 0,5 s la esquina tiene como mucho ${halfSecCorner} ayudante${halfSecCorner === 1 ? "" : "s"}. "Nadie ayuda desde la esquina" significa que nadie está en la esquina.`),
  h2("12.2 Distancia u orientación"),
  p(`Por zona, la tasa por defensor es más alta en el perímetro que dentro: ${pct(num(BR("zone0", "none", "top_3").rate))} en el triple frontal y ${pct(num(BR("zone0", "none", "wing_3").rate))} en el de ala, contra ${pct(num(BR("zone0", "none", "mid_range").rate))} en media distancia, ${pct(num(BR("zone0", "none", "paint_non_ra").rate))} en la pintura y ${pct(num(BR("zone0", "none", "restricted_area").rate))} en el área restringida. Se sospechó que podía ser mecánico: el ayudante es el que más se mueve hacia donde estará el balón, y un defensor interior ya estaría cerca de ese punto. Para comprobarlo, cada zona se compara con lo que predicen sus estratos: se suma, sobre sus defensores, la tasa media del estrato en que cae cada uno, y la razón es ayudantes observados entre esperados, 1 si la zona es el ayudante tanto como dicen sus estratos. Dos estratos: la distancia hasta el punto adonde va el balón (siete bandas) y la orientación de ese punto (cinco bandas de target_bearing_x).`),
  grid(["Zona", "Defensores", "Tasa", "Razón bruta", "Por distancia", "Por orientación (IC 95 %)", "Ambas"],
    ZONES.map((z) => [ZONE_NAME[z], BR("zone0", "none", z).n_defenders, pct(num(BR("zone0", "none", z).rate), 1), ratio(BR("zone0", "none", z)), ratio(BR("zone0", "target_dist", z)), ratioCi(BR("zone0", "bearing", z)), ratio(BR("zone0", "target_dist+bearing", z))]),
    [1826, 1400, 900, 1000, 1100, 1900, 900], { align: ["l", "r", "r", "r", "r", "r", "r"] }),
  source("reports/help_base_rate.csv (grouping zone0; standardised_by none, target_dist, bearing y target_dist+bearing)."),
  p(`La distancia no lo explica: los defensores interiores no están más cerca del punto adonde va el balón (mediana de ${ft(targetDist("paint_non_ra"))} en la pintura y ${ft(targetDist("restricted_area"))} en el área restringida, contra ${ft(targetDist("top_3"))} en el triple frontal, de reports/help_vectors.csv), y con ella el triple frontal sigue en ${ratioCi(BR("zone0", "target_dist", "top_3"))}. La orientación sí. Un defensor para el que ese punto queda mayormente hacia el aro (target_bearing_x de ${bearingRows[0].group.replace(" to ", " a ").replace(/\./g, ",").replace(/-/g, "−")}) es el ayudante el ${rateCi(bearingRows[0])} de las veces; uno para el que queda mayormente hacia fuera (${bearingRows[bearingRows.length - 1].group.replace(" to ", " a ").replace(/\./g, ",").replace(/-/g, "−")}), el ${rateCi(bearingRows[bearingRows.length - 1])}. Controlando la orientación, el triple frontal queda en ${ratioCi(BR("zone0", "bearing", "top_3"))} y la pintura en ${ratioCi(BR("zone0", "bearing", "paint_non_ra"))}, y las bandas de |y| se aplanan (${yBands.slice(0, -1).map((r) => ratio(BR("y_band", "bearing", r.group))).join(" / ")}, del centro hacia fuera); el lado de la esquina queda en ${ratioCi(BR("y_band", "bearing", cornerBand.group))}, con ${cornerBand.n_defenders} defensores. Con otras particiones de la orientación (tres u ocho bandas, deciles) el veredicto no cambia, según una sonda de sesión registrada en tasks/todo.md. Queda el triple de ala, el área restringida baja (${BR("zone0", "none", "restricted_area").n_helpers} ayudante de ${BR("zone0", "none", "restricted_area").n_defenders}) y la zona lejana.`),
  h2("12.3 El matiz del ayudante"),
  p(`La consecuencia toca a la definición del ayudante (sección 6). Por encima del balón, cuando el punto adonde va queda más cerca de la línea del aro que el defensor, hundirse con la penetración ya es moverse hacia ese punto, y cuenta como movimiento de ayuda. El ${pct(num(base.helper_above_ball), 1)} de los ayudantes empieza ahí, y en la mediana la parte a lo largo de la pista es el ${pct(num(base.helper_along_court_share))} de su movimiento de ayuda. En las doce celdas de sensibilidad, los ayudantes por encima del balón van del ${pct(Math.min(...sens("helper_above_ball")))} al ${pct(Math.max(...sens("helper_above_ball")))}, y la parte a lo largo de la pista del ${pct(Math.min(...sens("helper_along_court_share")))} al ${pct(Math.max(...sens("helper_along_court_share")))}, las dos creciendo con el umbral: cuanto mayor el movimiento, más es hundirse. Los ${BR("zone0", "none", "far").n_helpers} ayudantes de la zona lejana se mueven una mediana de ${es(-farDx, 1)} pies hacia el aro en el segundo: son defensores que vuelven en transición.`),
  p(`Parte del ${pct(N.shareHelped, 1)} de penetraciones con ayudante es, por tanto, el repliegue común de la defensa visto desde arriba del balón. La segunda ayuda (sección 11) no cambia, porque su placebo y su comparación con las penetraciones sin ayudante se hacen sobre la misma definición; pero el matiz viaja junto al ${pct(N.shareHelped, 1)} en el README y en la página. El docstring de scbasket.wind decía que un defensor que solo se hunde puntúa bajo, y la sección 6 de esta memoria lo repetía; las dos cosas están corregidas.`),
  h2("12.4 Lo decidido"),
  p("Javier aceptó el 29 de octubre las tres recomendaciones del planificador:"),
  bullet([bold("La primera mitad de la tesis se retira como afirmación. "), run("La tesis queda en la segunda: nadie ayuda al que ayuda, que ya es el título (sección 10.4).")]),
  bullet([bold("La figura 1 pasa a contexto descriptivo: "), run("adónde va la defensa en el primer segundo, con la esquina como ocupación y la cuota de ayudantes por encima del balón, cada una con su n. Revisado el mismo día: tras el cribado de 37 sobre 100 (sección 9.3), Javier aceptó sacar ese mapa del README y poner en su lugar una penetración elegida por regla que enseña la medida (sección 9.1); el contexto de esta sección pasa a dos frases del README.")]),
  bullet([bold("El ayudante conserva su definición. "), run("Redefinirlo, por ejemplo solo con el movimiento lateral, obligaría a rehacer la fase A a siete semanas del cierre; el matiz va al lado de la cifra.")]),
  h2("12.5 El mapa de viento, fuera del README"),
  p("El mapa de viento ya no es una de las dos figuras del README; se queda aquí y en la página, como una sección en vista cenital (el plan lo ponía como gancho; desde el 29 de octubre el gancho es la penetración en 3D, sección 14). Esta es su versión redibujada del 29 de octubre, con la tasa por defensor en lugar de la densidad bruta de orígenes."),
  ...windMap,
];

// Ayuda cercana y ayuda larga (sección 13), leída de reports/help_kinds_summary.csv, que escribe
// scripts/help_kinds.py con scbasket.help_kinds. Las constantes del módulo están al principio.
const PRE_SHA = execSync('git log --format=%h --grep="Pre-register the near/long help split" -n 1', { cwd: ROOT }).toString().trim();
const hkn = (kind, variant) => num(hk.find((r) => r.measure === "count" && r.kind === kind && r.variant === variant).n);
const HK = (measure, kind, variant, h) => hk.find((r) => r.measure === measure && r.kind === kind && r.variant === variant && Math.round(num(r.horizon) * 25) === h);
const ni = (v) => String(Math.round(num(v)));
const hkCi = (r) => `${sg(num(r.mean))} (${sg(num(r.ci_low))} a ${sg(num(r.ci_high))})`;
const READING_ES = { ROTATION: "Rotación", ABSENCE: "Ausencia", INCONCLUSIVE: "No concluyente", "": "ninguna fijada" };
const KIND_ROWS = [
  ["LONG (el último), primaria", "long", "primary"],
  ["LONG, radio de 5 ft", "long_path5", "sensitivity"],
  ["LONG, radio de 8 ft", "long_path8", "sensitivity"],
  ["LONG, superada según blowby", "long_blowby", "sensitivity"],
  ["LONG, regla de la primera sonda", "long_move4", "sensitivity"],
  ["CERCANA, finta", "near_stunt", "primary"],
  ["CERCANA, comprometida", "near_committed", "primary"],
  ["CERCANA, comprometida, partición anterior (sensibilidad)", "near_committed_endpos", "sensitivity"],
  ["Publicados, todos", "pub_all", "published"],
  ["Publicados, el último", "pub_last", "published"],
  ["Publicados, el más cercano", "pub_nearest", "published"],
  ["Publicados, otro", "pub_other", "published"],
  ["Publicados, recuperó", "pub_recovered", "published"],
  ["Publicados, comprometido", "pub_committed", "published"],
];
const refOf = (kind, variant) => (variant === "published" ? HK("paired_diff", "pub_unhelped", "published", HEADLINE) : HK("paired_diff", `${kind}_ref`, variant, HEADLINE));
const LONG_C = HK("contrast", "long", "primary", HEADLINE);
const COMM_C = HK("contrast", "near_committed", "primary", HEADLINE);
const STUNT_C = HK("contrast", "near_stunt", "primary", HEADLINE);
const PUBC_C = HK("contrast", "pub_committed", "published", HEADLINE);
const LONG_SENS = ["long_path5", "long_path8", "long_blowby", "long_move4"].map((k) => HK("contrast", k, "sensitivity", HEADLINE));
// Lo que la sección 13 afirma se comprueba al generar, no se supone.
if (LONG_C.reading !== "INCONCLUSIVE" || num(LONG_C.n) >= 40) throw new Error("la lectura de LONG ya no es no concluyente: revisar la sección 13.6");
if (!LONG_SENS.every((r) => r.reading === "INCONCLUSIVE")) throw new Error("alguna sensibilidad de LONG ya no es no concluyente: revisar la sección 13.6");
// CERCANA comprometida: el registro de A8 (contraste por debajo de cero con la partición anterior) y lo de ahora.
const OLD_C = HK("paired_diff", "near_committed_endpos", "sensitivity", HEADLINE);
const OLD_X = HK("contrast", "near_committed_endpos", "sensitivity", HEADLINE);
if (num(OLD_X.ci_high) >= 0 || num(OLD_C.ci_high) >= 0 || num(OLD_X.n) !== hkn("flag", "near_committed_endpos")) throw new Error("la partición anterior ya no reproduce el registro de A8 (por debajo de cero): revisar las secciones 13.6 y 17.2");
if (COMM_C.reading !== "" || !holds0(COMM_C)) throw new Error("el contraste de CERCANA comprometida lleva lectura o ya no contiene el cero: revisar la sección 13.6");
const nMovers = hkn("flag", "near_committed") + hkn("flag", "near_stunt"); // la regla del paso no cambió
const oldStunts = nMovers - hkn("flag", "near_committed_endpos");
if (PUBC_C.reading !== "ABSENCE" || !(num(PUBC_C.ci_low) <= 0 && num(PUBC_C.ci_high) >= 0)) throw new Error("los publicados comprometidos ya no contienen el cero: revisar la sección 13.6");
if (STUNT_C.reading !== "") throw new Error("la finta no lleva lectura fijada");
const nResolved = hkn("drives", "resolved");
const nHelpers = hkn("drives", "published_helpers");

const sKinds = [
  h1("13. Ayuda cercana y ayuda larga (30 de octubre de 2026)", { pageBreakBefore: true }),
  h2("13.1 La distinción y por qué importa"),
  p("Javier, que es entrenador, separa dos ayudas que el ayudante publicado (sección 6) junta. La ayuda cercana: el defensor sin balón más próximo al balón se mueve hacia el jugador con balón; es una finta (stunt) si vuelve a su hombre y una ayuda comprometida si no vuelve. La ayuda larga: el jugador con balón supera a su defensor y el último defensor, el defensor sin balón más lejano del balón, salta al camino de la penetración para pararla; ahí la pregunta es quién rota al atacante del último."),
  p(`El ayudante publicado es el defensor que no es el emparejado del balón y que más se mueve hacia donde está el balón 1,0 s después, con ${es(HELP_FT, 0)} pies o más. Mezcla las dos ayudas. De los ${nHelpers} ayudantes, ${pct(hkn("helper_class", "nearest") / nHelpers)} son el defensor más cercano al balón al arrancar, ${pct(hkn("helper_class", "last") / nHelpers)} el más lejano y ${pct(hkn("helper_class", "other") / nHelpers)} otro; y ${pct(hkn("helper_stance", "recovered") / (hkn("helper_stance", "recovered") + hkn("helper_stance", "committed")))} vuelve a los 2,0 s al punto donde empezó su hombre (con la regla del 31 de octubre, sección 17; con la anterior, que medía hasta donde estaba su hombre a los 2,0 s, era el ${pct(hkn("helper_stance_endpos", "recovered") / (hkn("helper_stance_endpos", "recovered") + hkn("helper_stance_endpos", "committed")))}). Eso importa para la tesis: tras una finta se espera que nadie rote al hombre dejado, porque el defensor vuelve, de modo que una ausencia de rotación medida sobre la mezcla no dice nada de la ayuda larga, que es donde un compañero tendría que rotar de verdad. Esta sección separa las dos y pregunta si la ausencia de la sección 11 sobrevive en cada una.`),
  h2("13.2 Las definiciones"),
  p(`Todas están en scbasket.help_kinds como constantes de módulo, a los 1,0, 1,5 y 2,0 s del fotograma de arranque (el titular es 1,5 s) y con la sensibilidad indicada. Como el resto del paquete, miden desplazamientos y distancias, no decisiones: "finta" y "comprometida" son condiciones geométricas.`),
  bullet([bold("Defensores sin balón. "), run("Los cuatro que no son el emparejado del balón. El MÁS CERCANO y el ÚLTIMO son los que están más cerca y más lejos del balón al arrancar; el hombre de cada uno es el que le asigna la tabla matchups del proveedor al arrancar, sin sustituto (si falta, o es el propio jugador con balón, la penetración se descarta y se cuenta).")]),
  bullet([bold("Superado. "), run("En algún fotograma de los primeros 1,5 s el jugador con balón está más cerca del aro que su defensor. Sensibilidad: la marca blowby del proveedor.")]),
  bullet([bold("Ayuda larga (LONG). "), run(`Superado y, en algún fotograma de esos 1,5 s, el último está a ${es(PATH_FT, 0)} pies o menos del jugador con balón y más cerca del aro que él. Sensibilidades: radio de 5 y de 8 pies; superado según blowby; y la regla de la primera sonda (el último se mueve ${es(LAST_MOVE_FT, 0)} pies o más hacia el jugador con balón en 1,0 s), sin condición de camino. Referencia: no superado y el último se mueve menos de ${es(STAY_FT, 0)} pies (se queda en casa).`)]),
  bullet([bold("Ayuda cercana. "), run(`El más cercano se mueve ${es(NEAR_STEP_FT, 0)} pies o más hacia el jugador con balón (la proyección de la ayuda de la sección 6) en 1,0 s. FINTA si a los 2,0 s su distancia al punto donde empezó su hombre es la de arranque más ${es(RECOVER_FT, 0)} pie o menos; COMPROMETIDA si no (regla del 31 de octubre, sección 17; hasta entonces se medía hasta donde estaba su hombre a los 2,0 s, el mismo punto adonde apunta la medida, y esa partición queda como sensibilidad); sin definir (contada, excluida) si falta la ventana de 2,0 s o su hombre. Referencia: se mueve menos de ${es(NEAR_STAY_FT, 0)} pie.`)]),
  bullet([bold("La medida. "), run("Para cada clase, con su ayudante H (el último o el más cercano) y su hombre M: la misma diferencia emparejada de la sección 11 (los otros tres defensores, que no son el emparejado del balón ni H, hacia M menos el placebo), quién está más cerca de M al horizonte, y el contraste de la clase menos su referencia con el mismo bootstrap (unidad, remuestreos y semilla de scripts/second_help.py). Los ayudantes publicados se parten por clase (último, más cercano, otro) y por recuperó o comprometido, cada uno contra la serie publicada sin ayudante.")]),
  h2("13.3 La primera definición de la sonda y por qué se cambió"),
  p(`Una sonda previa, sin código en el paquete (sus cifras están en tasks/todo.md, tarea A8), definió la ayuda larga del último como superado y el último se mueve ${es(LAST_MOVE_FT, 0)} pies o más hacia el jugador con balón en 1,0 s. Dio entre 14 y 33 penetraciones, no concluyente, y en ellas el último seguía siendo el defensor más cercano a su propio hombre a los 1,5 s en el 75 a 86 %: la regla recogía hundimientos parciales y no saltos al camino de la penetración. Por eso la definición primaria pide estar en el camino (a ${es(PATH_FT, 0)} pies y por delante del jugador con balón) y la regla antigua queda como sensibilidad. La sonda mostró también que la referencia (el último se queda en casa) no está centrada en cero, sino en torno a ${sg(num(refOf("long", "primary").mean))} a ${sg(num(refOf("long_blowby", "sensitivity").mean))} ft a 1,5 s en esta ejecución, de modo que la lectura es siempre contra la referencia y no contra el cero.`),
  h2("13.4 Las lecturas, fijadas antes de correr"),
  p(`Se escribieron y se confirmaron en el commit ${PRE_SHA} antes de tocar los datos, y se aplican tal cual a 1,5 s.`),
  bullet([bold("LONG. "), run("ROTACIÓN si el contraste LONG menos referencia tiene el intervalo por encima de cero (los demás se mueven hacia el hombre del último más que cuando él se queda en casa): entonces la tesis se estrecha a la ayuda cercana. NADIE AYUDA AL ÚLTIMO si el intervalo contiene el cero o queda por debajo, con 40 penetraciones LONG o más. NO CONCLUYENTE si hay menos de 40, o si el intervalo se extiende más de 1 ft a los dos lados del cero.")]),
  bullet([bold("CERCANA COMPROMETIDA. "), run("La ausencia se sostiene si el contraste COMPROMETIDA menos la referencia cercana tiene el intervalo con el cero o por debajo; ROTACIÓN si queda por encima; mismas reglas de 40 y de anchura. Superada el 31 de octubre: tras la reclasificación, la lectura se hace sobre la media propia de las comprometidas y el contraste se da sin lectura (sección 17).")]),
  bullet([bold("Ayudantes publicados comprometidos "), run("contra la serie publicada sin ayudante, a 1,5 s: la misma lectura de tres vías.")]),
  h2("13.5 Qué sale"),
  p(`De las ${nResolved} penetraciones resueltas, el último tiene hombre y ventana de 1,5 s en ${hkn("last_status", "ok")} (se descartan ${hkn("last_status", "no_window")} por ventana y ${hkn("last_status", "no_man")} por falta de hombre) y el más cercano, con la ventana de 2,0 s, en ${hkn("near_status", "ok")} (${hkn("near_status", "no_man")} sin hombre y ${hkn("near_status", "no_window")} sin ventana). Superado, según la geometría, está el jugador con balón en ${hkn("flag", "beaten_geo")} y según blowby en ${hkn("flag", "blowby")}. Hay ${hkn("flag", "long")} penetraciones LONG primarias (${hkn("flag", "long_path5")} con radio de 5 ft, ${hkn("flag", "long_path8")} con 8 ft, ${hkn("flag", "long_blowby")} con blowby, ${hkn("flag", "long_move4")} con la regla de la sonda) frente a ${hkn("flag", "long_ref")} de referencia; y ${hkn("flag", "near_stunt")} fintas, ${hkn("flag", "near_committed")} comprometidas y ${hkn("flag", "near_ref")} de referencia (con la regla del 31 de octubre; con la partición anterior eran ${oldStunts} fintas y ${hkn("flag", "near_committed_endpos")} comprometidas, sección 17). Entre los ${nHelpers} ayudantes publicados: ${hkn("helper_class", "nearest")} el más cercano, ${hkn("helper_class", "last")} el último y ${hkn("helper_class", "other")} otro; ${hkn("helper_stance", "recovered")} recuperaron, ${hkn("helper_stance", "committed")} quedaron comprometidos y ${hkn("helper_stance", "undefined")} sin definir, con la regla nueva (con la anterior, ${hkn("helper_stance_endpos", "recovered")}, ${hkn("helper_stance_endpos", "committed")} y ${hkn("helper_stance_endpos", "undefined")}).`),
  grid(["Clase", "n", "Media, ft (IC 95 %)", "n ref.", "Referencia, ft (IC 95 %)", "Clase menos referencia, ft (IC 95 %)", "Lectura"],
    KIND_ROWS.map(([label, kind, variant]) => {
      const m = HK("paired_diff", kind, variant, HEADLINE);
      const c = HK("contrast", kind, variant, HEADLINE);
      const ref = refOf(kind, variant);
      return [label, ni(m.n), hkCi(m), ni(c.n_ref), hkCi(ref), hkCi(c), c.reading ? READING_ES[c.reading] : m.reading ? `${READING_ES[m.reading]} (media propia)` : READING_ES[""]];
    }),
    [1600, 600, 1450, 600, 1450, 1700, 1626], { align: ["l", "r", "r", "r", "r", "r", "l"] }),
  source("reports/help_kinds_summary.csv (measure paired_diff y contrast, a 1,52 s; mean, ci_low, ci_high, n, n_ref, reading). La media es la de la diferencia emparejada por penetración con el intervalo por bootstrap sobre penetraciones; en los publicados, la referencia es la serie sin ayudante; la finta no tiene lectura fijada. Desde el 31 de octubre la lectura de la ayuda comprometida está en su media propia (la fila paired_diff) y su contraste ya no la lleva; la partición anterior es una sensibilidad sin lectura (sección 17)."),
  p(`La referencia de la ayuda larga ronda ${sg(num(refOf("long", "primary").mean))} ft y la de la cercana ${sg(num(refOf("near_stunt", "primary").mean))} ft; la serie publicada sin ayudante, ${sg(num(refOf("pub_all", "published").mean))} ft. Ninguna está en cero, y por eso la columna que se lee es la del contraste.`),
  grid(["Clase", "Su defensor (H)", "H en la referencia", "Emparejado del balón", "Un tercero"],
    KIND_ROWS.slice(0, 8).map(([label, kind, variant]) => {
      const m = HK("paired_diff", kind, variant, HEADLINE);
      const ref = refOf(kind, variant);
      return [label, pct(num(m.nearest_helper)), pct(num(ref.nearest_helper)), pct(num(m.nearest_handler_def)), pct(num(m.nearest_third))];
    }),
    [2700, 1500, 1700, 1700, 1426], { align: ["l", "r", "r", "r", "r"] }),
  source("reports/help_kinds_summary.csv (nearest_helper, nearest_handler_def, nearest_third), a 1,52 s: quién es el defensor más cercano a M. La columna H en la referencia es el mismo defensor cuando se queda en casa; las otras dos son de la clase."),
  grid(["Clase", "1,0 s", "1,5 s", "2,0 s"],
    [["LONG (primaria)", "long", "primary"], ["CERCANA, finta", "near_stunt", "primary"], ["CERCANA, comprometida", "near_committed", "primary"], ["CERCANA, comprometida, partición anterior", "near_committed_endpos", "sensitivity"], ["Publicados comprometidos", "pub_committed", "published"]].map(([label, kind, variant]) => [label, ...HORIZONS.map((h) => hkCi(HK("contrast", kind, variant, h)))]),
    [2600, 2142, 2142, 2142], { align: ["l", "r", "r", "r"] }),
  source("reports/help_kinds_summary.csv (measure contrast): la clase menos su referencia, en pies con su intervalo del 95 %, por horizonte."),
  h2("13.6 Los veredictos"),
  p(`LONG: ${READING_ES[LONG_C.reading].toUpperCase()}. Hay ${LONG_C.n} penetraciones en que el último está en el camino de una penetración superada, frente al mínimo de 40 fijado; el contraste es ${hkCi(LONG_C)} ft. Las cuatro sensibilidades dan la misma lectura por el mismo motivo (${LONG_SENS.map((r) => `n = ${r.n}`).join(", ")}), pero no coinciden en el signo del intervalo: ${LONG_SENS.filter((r) => num(r.ci_low) > 0).length} de las ${LONG_SENS.length} dejan el intervalo por encima de cero, con tamaños de ${Math.min(...LONG_SENS.map((r) => num(r.n)))} a ${Math.max(...LONG_SENS.map((r) => num(r.n)))} penetraciones entre las cuatro, y la regla de la primera sonda (n = ${LONG_SENS[3].n}) lo deja con el cero dentro (${hkCi(LONG_SENS[3])} ft). La lectura fijada no permite concluir; la inclinación de las estimaciones apunta hacia la rotación y no hacia la ausencia, así que nada de esto autoriza a extender "nadie ayuda al último" a la ayuda larga. Tampoco estrecha la tesis, porque ese paso exigía el veredicto de rotación.`),
  p(`CERCANA COMPROMETIDA. El veredicto del 30 de octubre, con la partición de entonces, fue AUSENCIA con el contraste por debajo de cero: con ${ni(OLD_X.n)} penetraciones y ${ni(OLD_X.n_ref)} de referencia, ${hkCi(OLD_X)} ft, es decir, los otros tres se movían hacia el hombre del más cercano menos que cuando este se quedaba en casa. Se conserva como registro y está superado: la revisión del 31 de octubre halló que esa partición leía dónde estaba el hombre a los 2,0 s, el mismo punto adonde apunta la medida (sección 17). Con la clase reclasificada, ${ni(COMM_C.n)} penetraciones y ${ni(COMM_C.n_ref)} de referencia, el contraste es ${hkCi(COMM_C)} ft, con el cero dentro, y ya no lleva lectura: se da y no se afirma. Lo que se afirma ahora es la media propia de las comprometidas, ${hkCi(F2C)} ft, con lectura ${READING_ES[F2C.reading].toUpperCase()}: no se mueven hacia él más que hacia los demás atacantes (sección 17.3). La finta no tiene lectura fijada; con la regla nueva su contraste es ${hkCi(STUNT_C)} ft (n = ${STUNT_C.n}), un intervalo demasiado ancho para decir nada, y no se interpreta.`),
  p(`AYUDANTES PUBLICADOS COMPROMETIDOS contra la serie publicada sin ayudante: ${READING_ES[PUBC_C.reading].toUpperCase()}. Son ${ni(PUBC_C.n)} frente a ${ni(PUBC_C.n_ref)} sin ayudante, con un contraste de ${hkCi(PUBC_C)} ft, con el cero dentro.`),
  h2("13.7 Límites"),
  bullet("Diez partidos. La ayuda larga, tal como se define aquí, casi no ocurre en ellos: el último está en el camino en pocas penetraciones, y con ese n el contraste dice poco; no se bajó el listón de 40 ni se ensanchó la definición hasta que saliera un número."),
  bullet(`Toda la clasificación descansa en la tabla matchups del proveedor para el hombre del último y del más cercano, que no se ha contrastado con vídeo (sección 11.9); para el más cercano falta en el ${pct(hkn("near_status", "no_man") / nResolved, 1)} de las penetraciones.`),
  bullet("La referencia no está en cero y depende de cómo se define quedarse en casa; la lectura es contra ella. La parte de finta y comprometida usaba una sola regla de recuperación (1 pie a los 2,0 s), sin sensibilidad; desde el 31 de octubre la regla del paso, la de recuperación y la de quedarse en casa tienen su rejilla (sección 17.5)."),
  bullet("Superado es geométrico y empieza en el fotograma de arranque; una penetración que arranca con el jugador con balón ya por delante de su defensor cuenta como superada."),
  bullet("No se compara el desenlace (puntos, tiros libres): con diez partidos no tiene potencia (sección 10.2)."),
  p("Lectura de Javier como entrenador, el 30 de octubre, al ver estos resultados: las ayudas largas implican rotación, así se enseña. Los 7 casos de ayuda larga apuntan en esa dirección (los otros defensores se mueven hacia el hombre del último, y el último deja de ser el más cercano a su propio hombre), pero con 7 casos no es una medida, es coherencia con la doctrina. La tesis queda acotada a lo que sí se mide: detrás de la ayuda cercana que se compromete nadie acude al hombre que deja, al contrario de lo que se espera detrás de la ayuda larga. Desde el 31 de octubre, \"nadie acude\" es una media con su cota: los otros tres no se mueven hacia él más que hacia cualquier otro atacante (sección 17)."),
];


const sPage = [
  h1("14. La página (29 y 30 de octubre de 2026)", { pageBreakBefore: true }),
  p("La página (reports/nobody_helps_the_helper.html, construida por scripts/wind_html.py desde scripts/wind_template.html) es la entrega que se mira: una sola página, sin red, que abre con una penetración en 3D y sube a la vista cenital para enseñar la medida. De cada jugador solo se mide su posición en el suelo; los cuerpos, hacia dónde miran y la zancada se dibujan, y la página lo dice junto al arranque. Ninguna medida se enseña en perspectiva."),
  p(`Desde el 30 de octubre (versión 0.11) el texto de la página sigue la tesis acotada: la penetración es una ayuda cercana comprometida (el defensor más cercano al balón se mueve ${NEAR_STEP_FT} pies o más hacia el jugador con balón en 1,0 s y a los 2 s no ha vuelto con su hombre), la tira reparte las ${scAmong.n_helped} medias de esas ayudas, y el bloque de debajo de las barras (quién está más cerca del hombre dejado, el gráfico de la rotación, el contraste y la tabla de los otros dos horizontes) lee reports/help_kinds_summary.csv, con la ayuda comprometida en negro y la referencia en gris. El resultado sobre todos los ayudantes publicados se queda en un bloque aparte, "Context: the pooled helper", con su contraste, el hombre libre, la robustez, el pase y su cierre, y la ayuda larga aparece como límite declarado (${nkCount("flag", "long")} de ${nkCount("drives", "resolved")}). La construcción se negaba a escribir la página si algún intervalo del contraste de la ayuda comprometida no quedaba por debajo de cero, si el de la referencia excluía el cero o si la lectura fijada de antemano ya no era ausencia, y las pruebas lo comprobaban estropeando cada fuente; desde el 31 de octubre las guardas son otras (sección 14.6). La comprobación desde la consola, con el tiempo que mide sola en la GPU de la máquina, pasa 184 de 184; al cambiar a propósito una cifra de la referencia en el HTML, la fila de cifras inyectadas falla y nombra la celda del CSV.`),
  h2("14.1 Lo que decidió el guion"),
  p("El guion de la página (B3, tasks/wind_page.md) lo aprobó Javier el 29 de octubre, antes de construir nada. La página abre con la penetración de la figura 1 a media velocidad desde la cámara de detrás de la canasta, se congela en el instante que miden las figuras (1,5 s) y la cámara sube, sin girar, a la vista cenital, que reproduce la figura 1; solo entonces aparecen las trayectorias, las barras y la distancia del hombre dejado. Toda cifra vive en un bloque de la página que está oculto fuera de la vista cenital, y la comprobación desde la consola lo verifica. El balón se dibuja a su altura en la vista 3D y plano desde arriba, y nada se mide con él. No hay órbita libre: llevaría al lector a la perspectiva que deforma la medida. Las cifras que el guion cita se comprobaron por script contra los ficheros que nombra."),
  p("Lo que el lector puede tocar es poco y se puede enumerar: reproducir y pausar, el deslizador del tiempo, la siguiente penetración, el cambio de cámara y, sobre los tres defensores que no son el ayudante, ver su línea de hacia dónde van. No hay órbita libre, por tres razones: dejaría al lector inclinarse justo hasta la vista donde los pies sobre el suelo engañan; ya existe un visor 3D de este mismo paquete, así que explorar no aporta originalidad y arriesga la comunicación; y los controles de órbita llevan gestos táctiles que pelean con el desplazamiento de la página en 390 píxeles y un estado de cámara que ninguna comprobación podría enumerar. Quedan dos cámaras, las dos comprobables. Debajo de la penetración, la página repite los límites de esta memoria con su fuente: los diez partidos, el espejo de la penetración que en las casi rectas es casi arbitrario, que la altura del balón arrastra la anomalía del eje vertical, que la ausencia se mide contra un placebo y no como rotación, y que la esquina no se afirma."),
  h2("14.2 La construcción y los jugadores"),
  p("La página se construyó el mismo día (B4): scripts/wind_html.py inyecta en scripts/wind_template.html los datos de los CSV y de wind_scenes.json, sin una cifra escrita a mano, y mete dentro three.js (versión 0.185.1, con su licencia MIT y su huella comprobada), de modo que la página funciona sin red. La construcción se niega a escribir la página si las barras, la distancia del hombre dejado o el percentil no coinciden con sus CSV, o si alguna frase de la página dejaría de ser cierta (un intervalo del contraste que excluya el cero). Respecto al guion cambió la cámara de retransmisión, que se puso sobre el eje de la canasta porque la del guion dejaba fichas fuera de la imagen y habría girado al subir. La prueba independiente desde la consola (B5, scripts/drive_wind_page.py) la escribió otro agente a partir del guion y sin leer el código de la página: 178 comprobaciones pasan sobre la página construida, y cada una de cuatro versiones estropeadas a propósito (una cifra escrita a mano, un seek roto, una cámara en perspectiva en la vista cenital, trayectorias dibujadas en la vista 3D) la hace fallar."),
  p("Javier abrió la página y el arranque no enganchaba: \"no engancha nada; las fichas deben ser jugadores de baloncesto\" (B4b). El límite de los datos decide lo que se dice, no lo que se dibuja: los jugadores pasan a ser figuras 3D animadas (un maniquí con licencia CC0 de Quaternius, con camiseta, pantalón y número añadidos), colocadas en su posición medida, con la zancada sacada de la distancia que recorren y el bote sincronizado con la altura medida del balón; hacia dónde miran y la postura se dibujan, y la página lo dice junto al arranque. El papel de cada uno va en un aro de color en el suelo, y al subir la cámara cada jugador se funde en su ficha de la figura 1, así que la vista de la medida no cambia."),
  p("El primer montaje con jugadores se juzgó como lo vería un extraño, en vídeo y en capturas a 1440 y 390 píxeles de ancho, y se arreglaron cuatro cosas medidas: los jugadores eran pequeños (la cámara se encuadra ahora sobre los seis protagonistas, el balón y la canasta, no sobre los diez), las etiquetas caían en otro jugador en el paso de la ayuda (ahora llevan una línea hasta la cabeza de su jugador), el arranque tardaba 2,7 s (se compilaban en serie doce programas de sombreado) y faltaban pelo, tonos de piel y público. Javier vio el vídeo y dijo que engancha. Quedaba una pasada corta, cerrada el 30 de octubre: el quinto inferior de la imagen de escritorio era delantal oscuro detrás de la línea de fondo y el público apenas se veía. El encuadre se desliza ahora también en vertical (la cámara no se mueve ni gira; la subida a la vista cenital deshace el desplazamiento) y el público son figuras sentadas a pie de pista. La regla nueva del guion, como mucho un 10 % de la altura de la imagen por debajo del pie, el balón o la canasta más bajos, la mide la comprobación desde la consola: la página anterior la incumple (entre el 18,7 % y el 36,9 % según penetración y ancho) y la nueva deja un 6 % en las cuatro penetraciones y los dos anchos. En la GPU de este portátil la comprobación pasa entera (184 de 184), con 16,7 ms por fotograma y la página reproduciendo en menos de 0,7 s. Quedan como están, a propósito, el tablero en el centro de la imagen y el ayudante tapando al del balón en el paso de la ayuda, que es la geometría de la jugada vista desde detrás de la canasta."),
  h2("14.3 Lo que comprueba la consola"),
  p("scripts/drive_wind_page.py abre la página construida con Playwright y la maneja solo por su interfaz de consola (window.wind). Son 106 filas en el código, que en las dos ejecuciones de este portátil del 30 de octubre sobre la primera pantalla nueva (sección 14.5) dan 196 comprobaciones, 196 pasadas y 0 fallidas, en 74 y 82 s, con el renderizador ANGLE Intel Arc D3D11. Los valores esperados se leen en cada ejecución de los CSV y del JSON de las escenas, no se escriben en el comprobador. Comprueba, en lo esencial: que el número de cada elemento inyectado (143 con su fuente data-src) coincide con el CSV que nombra y con los dígitos impresos; que la vista cenital es de verdad cenital, con una cámara ortográfica y con el color de las fichas del ayudante y del hombre dejado devuelto por unproject a 0,1 ft de su posición medida, sin fiarse de la cuenta que lleva la propia página; que ninguna medida es visible fuera de la vista cenital y que en la vista 3D no hay ninguna trayectoria dibujada, por exploración de píxeles; que las etiquetas caen en su jugador, no se pisan entre sí y no tapan el balón; que las barras en el instante de la medida igualan los CSV a 0,01 ft; que con movimiento reducido no hay vuelo; y que ocurre lo mismo a 1440 y a 390 píxeles de ancho."),
  p("Las filas de tiempos solo valen en la GPU: con un renderizador por software fallan como \"tiempo no medible\", no pasan. En la GPU de este portátil el fotograma tiene una mediana de 16,7 ms, la página está reproduciendo entre 0,54 y 0,86 s en las seis cargas en frío de esas dos ejecuciones, y el margen inferior de la imagen, que el guion limita a un 10 % de la altura, es de un 6,0 % en las cuatro penetraciones a 1440 y a 390 píxeles."),
  h2("14.4 Las versiones estropeadas a propósito"),
  p("Una comprobación que no puede fallar no ha comprobado nada, así que cada una de estas versiones de la página se construyó aparte, con un defecto puesto a propósito, y el comprobador tenía que salir con error. Salió con error en todas."),
  grid(["Defecto puesto", "Qué lo detecta", "Resultado"], [
    ["Una cifra escrita a mano (helper_help_move)", "Los controles de data-value y de los dígitos impresos", "Sale con 1"],
    ["Un seek roto, a t * 0,5", "18 comprobaciones fallan", "Sale con 1"],
    ["Cámara en perspectiva en la vista cenital", "Las filas de cámara ortográfica y la de unproject (0,31 ft de error)", "Sale con 1"],
    ["Trayectorias dibujadas en la vista 3D", "La exploración de píxeles: de 315 a 1203 píxeles de ese color, frente a 513 a 2207 en la vista cenital", "Sale con 1"],
    ["La página del encuadre anterior a la pasada del 30 de octubre (c9e1cfe)", "Exactamente las dos filas de encuadre, con un margen inferior de 18,7 % a 36,9 % según penetración y ancho", "Falla donde debe, y la página nueva pasa"],
  ], [3000, 4226, 1800]),
  p("Lo que la comprobación no cubre, dicho junto a lo que cubre: un número escrito a mano en la página sin su atributo data-src no lo ve, porque solo recorre los elementos que declaran su fuente; y el reloj de la reproducción con la pestaña oculta tampoco. Y comprueba que la página es fiel a sus ficheros y a su guion, no que el hallazgo sea cierto ni que enganche: eso lo juzgó Javier mirándola, y que la abra en su propia máquina (B7) sigue pendiente."),
  h2("14.5 La primera pantalla (30 de octubre de 2026, versión 0.12)"),
  p("Una auditoría de diseño de solo lectura, con capturas a 390 por 844 y a 1440 por 900 píxeles, miró la página como la vería un extraño en sus tres primeros segundos. En el móvil el título ocupaba dos líneas y una nota sobre lo dibujado empujaba los controles; en el escritorio el escenario era una caja de 760 píxeles con una columna vacía al lado; tras subir a la vista cenital, en el móvil las barras empezaban a 1282 píxeles del borde superior en una pantalla de 844, debajo de los controles y de una leyenda de cinco líneas; el número grande de los resultados era la distancia de una sola penetración (8,7 ft), no el resultado; los botones medían 40 a 41 píxeles de alto y el deslizador 24; y el pie juntaba el hash del commit con su asunto. Javier aprobó seis arreglos y dejó fuera dos de gusto (las conclusiones en negrita y las etiquetas del deslizador)."),
  p(`El escenario es ahora lo primero de la página y ocupa todo el ancho: en el móvil, tan alto como deja la pantalla con los controles a la vista (688 píxeles a 390 por 844), con una barra oscura de controles debajo; en el escritorio, la ventana entera. El título, en una línea, y la frase que guía el arranque van sobre la franja superior del lienzo, donde la cámara pone el público, y en el escritorio los controles son una tarjeta arriba a la derecha. Abajo no podían ir: la regla del encuadre deja el pie más bajo a un 6 % del borde inferior. La página mide la altura de esa franja y el encuadre de la cámara la trata como fuera de la imagen, así que ningún protagonista, ni el balón, ni la canasta, ni una etiqueta quedan debajo, y la regla del 10 % sigue igual. Las barras pasan a un panel sobre el escenario, dentro del mismo bloque que se oculta fuera de la vista cenital: bajo la franja del título en el móvil y en la columna derecha en el escritorio; la vista cenital encuadra la pista en el hueco libre. En los resultados, el número grande es el resultado sobre todas las penetraciones (entonces el contraste a ${hsec(HEADLINE)} s; desde el 31 de octubre la media propia de las comprometidas, ${nkCi(F2C)} ft con su intervalo del 95 %, sección 14.6), a 64 píxeles en el escritorio y a 46 en el móvil; la distancia de la penetración de la figura queda en segundo plano, a 20. Todo objetivo táctil mide al menos 44 píxeles, también el pulgar del deslizador, y el pie separa el hash de su asunto.`),
  p("La comprobación desde la consola sustituyó las cuatro filas que describían la maquetación anterior (lienzo cuadrado en el móvil, 4:3 de 760 píxeles como mucho en el escritorio, las medidas debajo o al lado) y añadió dieciséis: la primera pantalla en cada ancho; las barras a la vista con la pista, sin que el panel ni la franja tapen la trayectoria de ningún jugador en las cuatro penetraciones ni una etiqueta, y lo mismo al aterrizar la pasada natural; la franja sin tapar a nadie en la vista 3D en ningún fotograma; los objetivos de 44 píxeles en cada vista; un pulgar del deslizador que acepta una pulsación a 20 píxeles de su centro; y el resultado como el número más grande, leído del CSV. Sobre la página anterior fallan 12 de las 16. Las otras cuatro no podían fallar allí, porque aquella página no tenía nada sobre el lienzo y en el escritorio ya enseñaba las barras al lado, así que se probaron con versiones estropeadas a propósito: un encuadre que ignora la franja deja 225 puntos de los protagonistas debajo de ella a 1440 píxeles, y una pista encuadrada debajo del panel tapa 56 puntos de trayectoria en dos penetraciones; las dos filas fallan. A 390 píxeles ignorar la franja no tapa a nadie, porque en el móvil la altura que sobra ya va arriba, y la fila del aterrizaje natural solo mira las fichas de la primera penetración. La página nueva pasa 196 de 196 dos veces seguidas; una tercera pasada, sobre la versión que se guardó, falla solo la fila del primer fotograma (1,07, 1,17 y 0,83 s), que es el coste que sigue."),
  p("Lo que cuesta. El tiempo por fotograma no cambia: mediana de 16,7 ms y percentil 95 de 16,7 a 16,8 ms en los dos anchos y en las dos páginas. El primer fotograma sí: en diez rondas alternadas a 1440 píxeles, con un navegador nuevo en cada carga, la página anterior pinta con una mediana de 0,61 s (0,44 a 0,99) y la nueva de 0,75 s (0,51 a 1,11); la nueva llega más tarde en 8 de las 10 rondas y pasa de 1,0 s en 1 de 10, la anterior en ninguna. En otra tanda de seis rondas, 0,84 s (0,52 a 0,91) contra 0,92 s (0,55 a 1,22), y 0 contra 3 de 6 por encima de 1,0 s. El script de arranque llega al primer dibujo casi igual (0,57 contra 0,63 s de mediana); lo que crece es el propio primer fotograma, de 40 ms (29 a 63) a 125 ms (81 a 190). No son los píxeles (con el lienzo dibujado a 0,58 de su tamaño sigue en 131 ms) ni las franjas (ocultas, 128 ms). Subir antes las texturas pintadas acorta ese fotograma a 95 a 106 ms pero no adelanta el primer pintado (1,01 a 1,02 s contra 1,04 en esa tanda, con la máquina más lenta), así que no se incorporó; lo más probable es que el encuadre ancho enseñe más pabellón en el primer fotograma. En el móvil no hay diferencia: 0,79 s (0,48 a 1,14) la anterior y 0,75 s (0,46 a 1,09) la nueva, con 1 de 6 cargas por encima de 1,0 s en cada una. El objetivo de 1,0 s no se ha movido."),
  p("Lo que no se tocó, a propósito: el contraste de la etiqueta del ayudante (texto naranja sobre su caja blanca translúcida) queda por debajo de 4,5 en las dos páginas, entre 3,21 y 3,73 en la nueva y entre 3,23 y 3,63 en la anterior, medido con los píxeles del lienzo que tiene debajo en la penetración de la figura; no estaba entre los seis arreglos. Las capturas antes y después y un vídeo de los primeros 8 s en el móvil quedan para que Javier los mire antes de publicar nada."),
  h2("14.6 La página tras la reclasificación (31 de octubre de 2026, versión 0.15)"),
  p(`La página sigue a la afirmación nueva (sección 17). El número grande de los resultados es la media propia de las ayudas cercanas comprometidas a ${hsec(HEADLINE)} s, ${nkCi(F2C)} ft con su intervalo del 95 %, y ya no el contraste, que se da junto a ella y no se afirma. Se quitó la frase "The drop below 0 belongs to the near help that commits, not to the metric", que la reclasificación dejó sin sostén, y hay dos párrafos nuevos: uno con los dos rotadores designados y el pase (sección 17.6) y otro con la robustez (sección 17.5). La tira reparte ahora las ${scAmong.n_helped} medias de la clase nueva, y la primera penetración es la nueva de la figura 1 (sección 17.8).`),
  p("Las guardas de la construcción cambiaron con la afirmación. scripts/wind_html.py se niega a escribir la página si un intervalo de la ayuda comprometida queda por encima de cero (\"no more than\" sería falso), si uno de la referencia deja de contener el cero, si la lectura de las comprometidas a 1,5 s no es AUSENCIA, si la cota no queda por debajo de la escala de una rotación tan larga como el paso del ayudante, si alguna celda de reports/near_sensitivity.csv no lee AUSENCIA, si alguna comprobación de reports/near_robustness.csv deja el intervalo de las comprometidas por encima de cero, si R1 o R2 no leen AUSENCIA o si el pase no lee LÍMITE; las pruebas estropean cada fuente y comprueban que la construcción se niega."),
  p("La comprobación desde la consola (B5), en la GPU de este portátil: 196 de 196 sobre la primera construcción; sobre la construcción final, 195 de 196, y la que falla es la fila ya conocida del primer fotograma (1,28, 1,29 y 1,07 s en las tres cargas en frío; el objetivo de 1,0 s no se ha movido, sección 15.4). Para saber si las filas nuevas podían fallar, se probó una copia de la página con la media de las comprometidas a 1,5 s cambiada en +0,05 dentro de los datos inyectados: fallan 4 filas, las ligadas a esa cifra (el valor inyectado, los dígitos impresos y la fila del resultado como el número más grande, a 1440 y a 390 píxeles)."),
]

const sRepo = [
  h1("15. El repositorio público y el README (30 de octubre de 2026)", { pageBreakBefore: true }),
  p("Decidido (decisión D2): este repositorio es la entrada. El estado final de la entrada del rebote queda marcado con la etiqueta bounce-final, sobre el commit 635ea4d, y su README se movió a docs/bounce/ con sus enlaces corregidos. No se borró nada: los guiones, los tests y los CSV del rebote siguen en el repositorio y siguen en verde."),
  h2("15.1 Qué dice el README nuevo y qué deja fuera"),
  p(`El README (950 palabras contadas por el comprobador, con un límite de 1000, y exactamente dos imágenes) se reescribió el 30 de octubre a la tesis acotada de entonces: la ayuda cercana que se compromete (${hkn("flag", "near_committed_endpos")} de ${nResolved} penetraciones con la partición de entonces), con la referencia en que el más cercano se queda en casa (${hkn("flag", "near_ref")}), el contraste de ${hkCi(OLD_X)} ft a ${hsec(HEADLINE)} s con su intervalo por debajo de cero, y los de 1,0 y 2,0 s; esa afirmación se retiró el 31 de octubre y el README se reescribió otra vez (secciones 15.5 y 17). El resultado sobre todos los ayudantes publicados (el contraste de ${CT(HEADLINE) ? sg(num(CT(HEADLINE).contrast_mean)) : ""} ft, con el cero dentro) y la ayuda larga (7 de 618, demasiado pocas para probar) van junto a la afirmación, como calificativo y como límite, no escondidos. Se conservan el 45,3 % y sus dos matices (la esquina es ocupación, 1,8 %, y hundirse por encima del balón cuenta como ayuda, 66 %). Se retiraron las secciones del hombre libre y de la rejilla de sensibilidad del ayudante publicado: siguen en la página y en esta memoria. Una frase nueva situaba la figura 1: en su penetración de entonces (${OSC.drive_id}) el hombre dejado estaba a ${ft(OSC.clearance_ft["1.5s"])} del defensor más cercano a 1,5 s. Ninguna frase dice de dónde viene la ayuda ni que un defensor eligiera.`),
  p("Deja fuera, a propósito, el error de 4 a 5 pies de las posiciones extrapoladas: ningún CSV lo lleva y en el README toda cifra sale de un CSV. Vive solo en esta memoria (riesgos, sección 18.1)."),
  h2("15.2 Cómo se vigila"),
  p("scripts/check_readme.py comprueba tres cosas: que el README no pase de 1000 palabras, que tenga exactamente dos imágenes y que cada cifra en negrita (33 el 30 de octubre) se recalcule desde la columna del CSV de la que sale, y falle si no la encuentra. Para saber si podía fallar se probó con una copia en la que \"45,3 %\" pasó a \"46,3 %\": el comprobador imprimió un FAIL (README 46,3 %, CSV 45,3 %), 34 aprobadas y 1 fallada, y salió con código 1. Con el README reescrito el 30 de octubre da 35 comprobaciones aprobadas (33 cifras, las palabras y las imágenes) y 0 falladas; con el del 31 de octubre, 49 aprobadas y 0 falladas, con código de salida 0 (sección 15.5)."),
  h2("15.3 El clon limpio"),
  p("Se clonó el repositorio en una carpeta nueva, sin el conjunto de datos, y se ejecutó lo que el README manda ejecutar: uv sync --extra dev, uv run pytest (288 pasan, 21 se saltan por necesitar el dato), scripts/help_figures.py, scripts/wind_html.py y esta misma memoria, con código de salida 0 en las cinco. Las figuras salieron idénticas byte a byte (no aparecen en git status); la página solo difirió en el identificador del commit que lleva incrustado, y el docx solo en la tabla del registro de versiones y en las marcas de tiempo."),
  h2("15.4 Lo que falta"),
  p("C1b, publicar la página en GitHub Pages, se hizo el mismo 30 de octubre con el visto bueno de Javier: el repositorio público es github.com/javiersr1996/nobody-helps-the-helper y la página se sirve en javiersr1996.github.io/nobody-helps-the-helper, publicada por un flujo de GitHub Actions que copia el fichero del repositorio sin reconstruirlo. El README enlaza ya a esa dirección. La dirección responde 200 y el fichero servido tiene la misma huella SHA-256 que el del repositorio. La comprobación desde la consola contra la dirección destapó un fallo del propio comprobador, no de la página: leía el estado y la barra de tiempo en dos llamadas separadas mientras la página seguía reproduciendo; ahora las lee en una sola y se probó que sigue fallando con una página estropeada a propósito."),
  p("El arranque se leyó mal primero. En tres pasadas contra la dirección el primer fotograma tardó entre 0,97 y 1,18 s, 0,57 s y entre 1,15 y 1,52 s, frente al objetivo de 1,0 s del guion, mientras en local se cumplía (entre 0,47 y 0,67 s); como la página es la misma byte a byte (877 KB comprimida), se dedujo que la diferencia estaba en la red. Medido el mismo día, la deducción era falsa. Con la comprobación desde la consola en cuatro pasadas seguidas, alternando el fichero local y la dirección, la dirección pasa entera las dos veces (184 de 184, primer fotograma entre 0,47 y 0,58 s) y el fichero local falla las dos veces esa sola fila, en la primera de sus tres cargas en frío (1,09 y 1,12 s; las otras, entre 0,53 y 0,72 s). El fallo sigue a la pasada, no a la dirección."),
  p("scripts/startup_split.py carga las dos por turnos, cada vez en un navegador nuevo y con la instrumentación de la comprobación, y separa las partes. En sus doce cargas, la red pone la descarga: la respuesta termina entre 49 y 246 ms después de empezar la navegación, contra 27 a 47 ms del fichero local; sin traza, el primer fotograma llegó entre 0,72 y 0,82 s por la dirección y entre 0,50 y 0,72 s en local. Lo demás es el hilo principal del navegador ejecutando los scripts, y no espera a nada más: el primer dibujo se hace en cuanto termina el script, sin esperar a que se compilen los shaders. En cuatro cargas trazadas (la traza ralentiza la página, así que de ellas solo vale el reparto), three.js se compila y ejecuta en 36 a 49 ms y el script de la página corre entre 343 y 486 ms de los 564 a 804 ms que pasan hasta el primer dibujo. Lo más caro de ese script es el encuadre de la cámara de retransmisión, que calcula el plano de toda la penetración (91 a 145 ms); le siguen el primer dibujo ya con los shaders listos (65 a 99 ms), las texturas, los números de las camisetas y la zancada (61 a 87 ms), medir el lienzo, que obliga a maquetar la página (42 a 73 ms), la construcción de la escena (49 a 54 ms) y poner a compilar los shaders (42 a 63 ms). No está medido qué hace lenta una carga en frío concreta. El objetivo no se ha movido: recortar bytes ahorraría como mucho la descarga, y un objetivo solo para local no tiene sentido porque la fila también falla en local, así que lo que queda es hacer menos trabajo antes del primer fotograma, y eso lo decide Javier. Javier no ha leído aún el README (C5)."),
  p("El primer recorte se hizo después: el encuadre de la cámara de retransmisión. Calculaba, para cada uno de los 39 fotogramas, unas 45 posiciones de la mirada, y de cada una la distancia mínima por bisección con 22 mitades fijas. Ahora una posición se descarta con una sola comprobación cuando su distancia mínima ya no puede mejorar el coste de la mejor hasta el momento (el coste nunca baja de la distancia), y solo se ajusta del todo la que puede ganar; además el cálculo de límites recorre una tabla plana de números en vez de matrices anidadas. Las 22 mitades no se tocaron: el resultado es el mismo número a número. Se comprobó en el navegador, las cuatro escenas con 390 por 844 (formato cuadrado), 1440 por 900 y 1920 por 1080 (apaisado), comparando la mirada, la distancia y los dos desplazamientos de cada fotograma con los de la versión anterior: la diferencia máxima es 0 en las doce combinaciones. El comparador falla donde debe: con 6 mitades en vez de 22 sale una diferencia de hasta 4,2 ft en la distancia, y lo da por malo. El encuadre se calcula una sola vez en el arranque (una escena, un tamaño), así que no había cálculo repetido que quitar. Tiempo del encuadre solo, en la GPU de la máquina, cuatro bloques alternados de cinco repeticiones por versión: 128 ms de mediana por escena la versión anterior (97 a 174) y 22,5 ms la nueva (15 a 31) con 1440 por 900; 111 ms (78 a 178) y 23,2 ms (17 a 31) con 390 por 844. En arranque, con scripts/startup_split.py en doce rondas alternadas: el fin del análisis de la página (en el que va el encuadre) tarda entre 528 y 1267 ms con mediana de 837 antes y entre 561 y 777 ms con mediana de 684 ahora; el primer fotograma, entre 658 y 1410 ms (mediana 977) antes y entre 719 y 972 ms (mediana 858) ahora. La máquina estaba más lenta que en las medidas anteriores, así que las cifras absolutas no se comparan con las de arriba. La comprobación desde la consola, en tres pasadas contra la página nueva: 184 de 184, 181 de 184 y 184 de 184. La que falló lo hizo solo en el arranque, con cargas en frío de 0,80, 1,08 y 1,52 s; el objetivo de 1,0 s no se ha movido y esa carga lenta sigue sin explicar."),
  h2("15.5 El README tras la reclasificación (31 de octubre de 2026, versión 0.15)"),
  p(`El README se reescribió a la afirmación nueva (sección 17): 997 palabras según el comprobador, dos imágenes, y scripts/check_readme.py sale con código 0 con 49 filas aprobadas y ninguna fallada. La primera frase define "nobody" como una media: tras una ayuda cercana que se compromete, los otros tres no se mueven hacia el hombre que deja más que hacia cualquier otro atacante. La definición de la clase usa solo el movimiento del ayudante (${hkn("flag", "near_committed")} de ${nResolved} penetraciones; referencia, ${hkn("flag", "near_ref")}), y la figura 1 se sitúa con su penetración nueva (el hombre dejado a ${ft(SC.clearance_ft["1.5s"])} del defensor más cercano a 1,5 s). El resultado es la media propia de las comprometidas con su cota y su escala (el paso mediano del ayudante y lo que leería una rotación), los otros dos horizontes, la referencia y el contraste dado y no afirmado; después, los dos rotadores designados y el pase, fijados antes de correr (sección 17.6), y el reparto por penetración. Una sección nueva, "How solid it is", dice que no es un pre-registro y nombra los dos caminos que se bifurcaron (sección 17.4), con la afirmación retirada de ${hkCi(OLD_X)} ft; da la robustez (sección 17.5) y sitúa el trabajo frente a la literatura (Franks y otros, 2015; Keshri y otros, 2019; Supola y otros, 2023; Lucey y otros, 2014). En los límites, la ayuda larga lleva ya sus números (sección 17.7) y los emparejamientos del más cercano, su coherencia (sección 17.5).`),
];

const sVideo = [
  h1("16. El vídeo (31 de octubre de 2026, versión 0.13 y 0.14)", { pageBreakBefore: true }),
  p("El vídeo de un minuto, mudo y listo para poner la voz encima, lo construye scripts/wind_video.py (D2). No es una animación aparte: son los fotogramas de la propia página, a 1920 por 1080 píxeles, 25 por segundo, conducida solo desde la consola (wind.seek, wind.flight, wind.view; nunca reproducción en tiempo real) y fotografiada fotograma a fotograma en la GPU del portátil. Las ventanas de las seis escenas se leen de las cabeceras [m:ss-m:ss] de tasks/video_script_wind.md, así que el guion y el corte no pueden separarse: 0 a 6, 6 a 14, 14 a 20, 20 a 29, 29 a 51 y 51 a 60 s, es decir 150, 200, 150, 225, 550 y 225 fotogramas. Sale un MP4 H.264 sin audio de 1500 fotogramas, y ffprobe lee 60,000 s (la primera pasada salió de 61 s, un segundo de más; el analizador rechaza ahora cualquier total fuera de 59 a 60 s)."),
  h2("16.1 Qué enseña cada escena"),
  p("Escena 1, la regla: la página en la vista de retransmisión en t = 0, quieta, con la tarjeta del título. Escena 2, la ayuda: la carrera a cámara lenta de t = 0 a t_h = 0,60 s, el centro de la ralentización, que el script recalcula del JSON de las escenas con la regla de la página (el primer fotograma en que el ayudante ha recorrido la mitad de su camino hasta el 25) y contrasta con la propia página: el mínimo de la velocidad de wind.hookTime cae en 0,597 s. Como la carrera natural de la página dura 1,24 s hasta ese punto y la ventana son 8 s, el reloj de la página se estira por igual (unas 6,5 veces más lento); el vídeo es, pues, la misma curva de ralentización de la página, mucho más lenta. La tarjeta del título se desvanece al empezar la escena. Escena 3, el suspense: congelada en t_h, con un anillo blanco sobre el hombre dejado. La página ya lleva su etiqueta \"the man he left\" y un aro negro en el suelo, y se conservan; el anillo se añade porque en un vídeo el aro negro no se lee como marca. Su posición no está puesta a ojo: es la proyección que hace la propia página (wind.project) de la posición del hombre dejado, y en cada fotograma el script comprueba que coincide a menos de 0,5 píxeles con la que sale de las matrices de la cámara, que la posición es la del JSON a 0,01 ft y que la etiqueta de la página queda sobre el anillo. Escena 4: la carrera sigue de t_h a 1,52 s en 4,0 s, una pausa de 0,4 s, la subida a la vista cenital en 2,6 s (el anillo se apaga al empezar a subir) y el aterrizaje con las barras y el cuadro de 8,7 ft (de la penetración de entonces, sección 16.4), 2 s. Escena 5, el resultado: la figura 2, entera."),
  p("Dos concesiones. La figura 2 mide 1440 por 2678 píxeles y no cabe legible en un fotograma de 1080 de alto (a esa escala el texto queda en unos 10 píxeles), así que se enseña a su tamaño en dos recortes fijos del mismo PNG, sin redibujar (el panel de la pista con los puntos hasta 13,5 s y el de los intervalos después, con un fundido de 6 fotogramas; el corte está 0,2 s antes de que la voz de guía diga \"Compared with\", según los límites de palabra de edge-tts), con una franja inferior que lleva las cifras de la locución: 159 de 618 penetraciones y -0,63 ft (IC de -1,25 a -0,03), las de antes de la reclasificación (sección 16.4). El script falla si una cifra escrita en una diapositiva no está en su CSV (help_kinds_summary.csv). Escena 6, el límite: la página en la vista cenital en 1,52 s con las barras y el cuadro del resultado (-0,63 ft, antes de la reclasificación), con la tarjeta del título de nuevo. Se prefirió a una diapositiva de título porque cierra con la misma imagen que la afirmación y lleva el título igualmente. Para que cupiera, el vídeo mueve el cuadro del resultado de la página (que está debajo del pliegue en un escritorio de 1920 por 1080) a la columna de las barras, con CSS inyectado al grabar, y oculta los controles y la línea de pie del escenario; ni la página ni la plantilla se tocan."),
  h2("16.2 Lo que se comprobó"),
  p("Durante la grabación, en cada fotograma distinto (los fijos repiten la captura anterior) y en una sola llamada de consola, el script lee la escena, t, la vista y el tipo de cámara y falla si no son los esperados: la escena 0 de la página en todos, la vista de retransmisión hasta el último fotograma antes de aterrizar, la subida estrictamente creciente en altura de cámara y la vista cenital ortográfica al final. La página no expone la fracción p del vuelo; se comprueba su efecto (vista, tipo de cámara y altura del ojo). Tras construir el MP4: ffprobe lee 60,000 s, 1500 fotogramas y 1920x1080, sin pista de audio, y una pasada de blackdetect no halla ningún fotograma negro. Se extrajeron el principio, el medio y el final de cada escena y se miraron: sin recortes, sin controles, el anillo sobre el hombre correcto, la subida aterriza en la vista cenital con las barras. Los tests de tests/test_wind_video.py (ventanas contiguas y 60 ± 1 s, y la comprobación de cifras de la diapositiva) se mostraron fallando sobre entradas estropeadas: un hueco entre ventanas, un corte de 80 s, un 160, un -0,64 y un -0,30 en lugar de las cifras del CSV. Los fotogramas intermedios no se miraron uno a uno."),
  p("La voz de guía es solo una vista previa, nunca la voz de la entrada, que ha de ser la de Javier: con una voz neuronal inglesa (en-GB-RyanNeural, velocidad por defecto) cada línea dura 5,23, 7,08, 4,80, 7,87, 21,77 y 8,71 s frente a ventanas de 6, 8, 6, 9, 22 y 9 s: caben todas, con 0,77, 0,92, 1,20, 1,13, 0,23 y 0,29 s de holgura. Es una lectura sintética, no la de Javier, que decide el corte real (D1); la holgura de las escenas 5 y 6 es la menor."),
  h2("16.3 El móvil y el minuto (31 de octubre de 2026, versión 0.14)"),
  p("El propietario ve el vídeo en el móvil y vio la vista previa con voz. Dos cambios de guion: la línea de la escena 6 pasa a \"Long help is taught with a rotation; we found only seven, too few to test. On near help, nobody helps the helper.\" (133 palabras en total, y las cifras que se dicen siguen en el README) y las ventanas se acortan para sumar 60,000 s, con la prueba del analizador endurecida a un total de 59 a 60 s (las cabeceras de 61 s ahora fallan). Para el móvil, solo en la captura: la página se graba a escala de dispositivo 2 y las etiquetas, que son un tamaño de letra de CSS que la página mide una vez, se ponen en 24 y 26 píxeles con CSS inyectado antes de cargarla, de modo que la colocación propia de la página ve las cajas grandes; y cada fotograma de las escenas 1 a 4 se recorta a la ventana 16:9 más ajustada que contiene a los jugadores, sus etiquetas y el anillo, con 40 píxeles de margen, suavizada en el tiempo y con un zoom máximo de 2x. Encuadrar a los diez jugadores deja el zoom en 1,00x en todos los fotogramas, porque los atacantes sin balón están en el borde de la imagen; el vídeo encuadra a los siete protagonistas (el del balón y su defensor, el ayudante, el hombre dejado y los otros tres), con zoom de 1,00x en la escena 1 (la tarjeta del título) a 1,32x en las escenas 2 y 3, y vuelve a 1,00x durante la subida (mediana 1,26x). Los tres atacantes grises sin balón pueden quedar cortados en el borde, como los corta ya el encuadre de la página, y la comprobación por fotograma exige, en coordenadas del recorte, que los siete, todas las etiquetas y el anillo estén dentro. El ayudante, en la escena 3, está detrás del tablero translúcido: se lee como una figura tenue bajo su etiqueta, ahora grande, y no se tocó el aspecto de la página. Las hojas de contacto a 844 píxeles de ancho se miraron: las etiquetas se leen. La escena 5 son dos recortes fijos de la figura 2, no la panorámica continua. La pasada completa tarda unos 25 minutos."),
  h2("16.4 Tras la reclasificación (31 de octubre de 2026, versión 0.15)"),
  p(`El vídeo no se ha vuelto a grabar, y lo que describen las secciones 16.1 a 16.3 es el MP4 que existe, con las cifras de antes de la reclasificación (sección 17): ${hkn("flag", "near_committed_endpos")} penetraciones y ${sg(num(OLD_X.mean))} ft en la franja de la escena 5 y en el cuadro del resultado de la escena 6, y el cuadro de ${ft(OSC.clearance_ft["1.5s"])} de la escena 4, que era la penetración de entonces. En el código, la franja y el cuadro del resultado leen ya la media propia de las comprometidas (${nkCi(F2C)} ft), y la escena 0 de la página es la nueva (${SC.drive_id}). La locución dice "${OSC.clearance_ft["1.5s"].toFixed(1)} ft", y eso ya es falso: en la penetración nueva el hombre dejado está a ${ft(SC.clearance_ft["1.5s"])} del defensor más cercano a 1,5 s. Queda el paso c: rehacer el guion de las escenas 2 y 4 a 6 (la revisión señaló además que "steps in to stop it" implica intención), que Javier apruebe las palabras, dar su clave de color a la pausa sobre los puntos de la figura 2, volver a grabar y mandar la vista previa a su móvil.`),
];

// La revisión y la reclasificación (sección 17): help_kinds_summary.csv y los near_*.csv de scripts/near_robustness.py.
const atH = (r) => Math.round(num(r.horizon) * 25) === HEADLINE;
const RB = (check, group, detail = "") => nRob.find((r) => r.check === check && r.group === group && r.detail === detail && atH(r));
const RT = (rotator, group) => nRot.find((r) => r.rotator === rotator && r.group === group && atH(r));
const PCOUNT = (who, group) => num(nPass.find((r) => r.measure === "count" && r.who === who && r.group === group).n);
const PAFTER = (who) => nPass.find((r) => r.measure === "after_pass" && r.who === who && r.group === "committed");
const COH = (group) => nCoh.find((r) => r.group === group);
const cohText = (group) => `${COH(group).n_coherent} de ${COH(group).n} (${pct(num(COH(group).share))})`;
const span = (rows, col, d = 2) => `${sg(Math.min(...rows.map((r) => num(r[col]))), d)} a ${sg(Math.max(...rows.map((r) => num(r[col]))), d)}`;
const cells = nSens.filter(atH);
const gridVals = (col) => [...new Set(cells.map((r) => num(r[col])))].sort((a, b) => a - b);
const LOO = nRob.filter((r) => r.check === "leave_one_out" && r.group === "committed" && atH(r));
const LOOX = nRob.filter((r) => r.check === "leave_one_out" && r.group === "contrast" && atH(r));
const SPLIT_SHA = gitSha("Split the published helper into near and long help");
const SCOPE_SHA = gitSha("Scope the thesis to committed near help");
const A2_SHA = gitSha("Pre-register the designated-rotator and pass readings");
const CHECK_ES = {
  primary: "Principal: el punto donde empezó su hombre",
  endpos: "Partición anterior: dónde está su hombre a los 2,0 s",
  fixed_targets: "Objetivos fijos donde estaban al arrancar",
  no_pass: `Sin pase en los primeros ${hsec(HEADLINE)} s`,
  detected: `Los tres y el hombre dejado detectados hasta ${hsec(HEADLINE)} s`,
  coherent: "El más cercano es el más próximo a su propio hombre al arrancar",
  game_cluster: "Intervalo remuestreando partidos",
};
// Lo que la sección 17 afirma se comprueba al generar, no se supone.
if (Math.abs(num(RB("primary", "committed").mean) - num(F2C.mean)) > 1e-9) throw new Error("17: near_robustness.csv y help_kinds_summary.csv no coinciden en la fila principal");
if (cells.filter((r) => r.primary === "True").length !== 1 || Math.abs(num(cells.find((r) => r.primary === "True").mean) - num(F2C.mean)) > 1e-9) throw new Error("17.5: la celda principal de la rejilla no es la fila de la afirmación");
if (!cells.every((r) => r.reading === "ABSENCE" && holds0(r))) throw new Error("17.5: alguna celda de la rejilla ya no lee AUSENCIA con el cero dentro");
if (!cells.every((r) => num(r.contrast_ci_low) <= 0 && 0 <= num(r.contrast_ci_high))) throw new Error("17.5: algún contraste de la rejilla ya no contiene el cero");
if (!["primary", "no_pass", "detected", "coherent", "game_cluster"].every((c) => holds0(RB(c, "committed"))) || !LOO.every(holds0)) throw new Error("17.5: alguna comprobación deja el intervalo de las comprometidas fuera del cero");
if (!(num(RB("fixed_targets", "committed").ci_high) < 0 && num(RB("fixed_targets", "reference").ci_high) < 0 && holds0(RB("fixed_targets", "contrast")))) throw new Error("17.5: con objetivos fijos la referencia ya no cae también por debajo de cero");
if (!["R1", "R2"].every((r) => RT(r, "committed").reading === "ABSENCE")) throw new Error("17.6: un rotador designado ya no lee AUSENCIA: la afirmación tiene que decir que él rota");
if (!(num(RT("R1", "committed").ci_high) < 0 && holds0(RT("R2", "committed")))) throw new Error("17.6: R1 ya no queda por debajo de cero o R2 ya no contiene el cero");
if (!["three", "R1"].every((w) => PAFTER(w).reading === "LIMIT") || num(PAFTER("three").n) >= PASS_MIN_N || num(PAFTER("three").n) !== PCOUNT("post_pass_window", "committed")) throw new Error("17.6: el pase ya no es un límite declarado");
if (!(num(F2C.share_mover_left) > num(F2C.share_mover_placebo) && num(F2R.share_mover_left) > num(F2R.share_mover_placebo))) throw new Error("17.3: «en las dos clases algo más hacia él que hacia el placebo» ya no es cierto");
if (LONG_C.reading !== "INCONCLUSIVE") throw new Error("17.7: la ayuda larga ya no es no concluyente");

const sReview = [
  h1("17. La revisión y la reclasificación (31 de octubre de 2026)", { pageBreakBefore: true }),
  p("El 31 de octubre, a petición de Javier, se adelantó la única revisión adversarial del plan (tarea V, con un agente revisor de solo lectura sobre todo el repositorio). Su primer hallazgo se reprodujo en la sesión principal y cambió la clase sobre la que descansaba la afirmación. Esta sección cuenta qué se rompió, los números antes y después, qué se afirma ahora y con qué cota, por qué no es un pre-registro, la robustez, las dos lecturas que sí se fijaron antes de correr, la ayuda larga y la penetración nueva de la figura 1. Los números salen de reports/help_kinds_summary.csv, que escribe scripts/help_kinds.py, y de reports/near_sensitivity.csv, near_robustness.csv, near_matchup_coherence.csv, near_rotator.csv y near_pass.csv, que escribe scripts/near_robustness.py."),
  h2("17.1 Lo que se rompió"),
  p(`La partición de la ayuda cercana en finta y comprometida (sección 13.2) leía dónde estaba el hombre que deja el ayudante a los 2,0 s: comprometida si a los 2,0 s el ayudante estaba más de ${es(RECOVER_FT, 0)} pie más lejos de su hombre que al arrancar. La medida apunta a ese mismo punto: proyecta el movimiento de los otros tres hacia donde está el hombre dejado al horizonte. La clase dependía así de lo que después se medía en ella. Un hombre que corta hacia el aro, donde está el ayudante, termina cerca de él y saca la penetración de las comprometidas (pasa a finta); y como corre hacia donde está la defensa, los otros tres parecen moverse hacia él. Las penetraciones que más se parecían a una rotación salían de la clase de la afirmación por cómo se movía el atacante, no por cómo se movía el ayudante.`),
  p(`La reclasificación usa solo el movimiento del propio ayudante: comprometida si a los 2,0 s su distancia al punto donde EMPEZÓ su hombre supera la de arranque en más de ${es(RECOVER_FT, 0)} pie. La partición anterior no se borra: queda como sensibilidad (near_committed_endpos en el CSV), y la postura de los ayudantes publicados (sección 13.1) sigue la regla nueva, con la anterior al lado (helper_stance_endpos).`),
  h2("17.2 Antes y después"),
  grid(["Medida, a " + hsec(HEADLINE) + " s", "Partición anterior (dónde está su hombre a los 2,0 s)", "Regla nueva (dónde empezó su hombre)"], [
    ["Comprometidas", ni(OLD_C.n), ni(F2C.n)],
    ["Fintas", String(oldStunts), String(hkn("flag", "near_stunt"))],
    ["Referencia (el más cercano se queda en casa)", ni(F2R.n), ni(F2R.n)],
    ["Comprometidas: media propia, ft (IC 95 %)", hkCi(OLD_C), hkCi(F2C)],
    ["Referencia: media, ft (IC 95 %)", hkCi(HK("paired_diff", "near_committed_endpos_ref", "sensitivity", HEADLINE)), hkCi(F2R)],
    ["Comprometidas menos referencia, ft (IC 95 %)", hkCi(OLD_X), hkCi(COMM_C)],
    ["Ayudantes publicados: recuperan / comprometidos / sin definir", ["recovered", "committed", "undefined"].map((v) => hkn("helper_stance_endpos", v)).join(" / "), ["recovered", "committed", "undefined"].map((v) => hkn("helper_stance", v)).join(" / ")],
    ["El más cercano es el más próximo a su propio hombre al arrancar", cohText("committed_endpos"), cohText("committed")],
  ], [3426, 2800, 2800], { align: ["l", "r", "r"] }),
  source("reports/help_kinds_summary.csv (kind near_committed y near_committed_endpos, a 1,52 s; los recuentos flag y helper_stance) y reports/near_matchup_coherence.csv. Las fintas de la partición anterior son las penetraciones con el paso del más cercano menos sus comprometidas: la regla del paso no cambió."),
  p(`De las ${nMovers} penetraciones en que el más cercano da el paso (${es(NEAR_STEP_FT, 0)} pies o más hacia el jugador con balón en 1,0 s), con la regla nueva ${hkn("flag", "near_committed")} son comprometidas y ${hkn("flag", "near_stunt")} fintas; con la anterior eran ${ni(OLD_C.n)} y ${oldStunts}. La afirmación de antes, el contraste de ${hkCi(OLD_X)} ft por debajo de cero, salía de la partición: con la clase nueva el contraste es ${hkCi(COMM_C)} ft, con el cero dentro. Se retira.`),
  h2("17.3 Lo que se afirma ahora"),
  p(`Decidido por Javier el 31 de octubre: la afirmación pasa a ser la ausencia medida. Tras una ayuda cercana que se compromete, los otros tres defensores no se mueven hacia el hombre que deja más que hacia cualquier otro atacante (el placebo), y la cota es el tope del intervalo del 95 %. Es la diferencia emparejada propia del grupo comprometido, no un contraste: a ${hsec(HEADLINE)} s, ${hkCi(F2C)} ft sobre ${ni(F2C.n)} penetraciones, con lectura ${READING_ES[F2C.reading].toUpperCase()} (la regla de la columna reading: ROTACIÓN si el intervalo queda por encima de cero; si no, AUSENCIA; NO CONCLUYENTE con menos de 40 penetraciones o con un intervalo que pase de 1 pie a los dos lados del cero). La cota: los datos descartan más de ${sg(num(F2C.ci_high))} ft hacia él. Para dar escala, el paso propio de los ayudantes hacia el jugador con balón tiene una mediana de ${ft(num(STEP.median))}; si uno de los tres se hubiera movido hacia el hombre dejado tanto como ese paso y el placebo no cambiara, la media sería ${sg(num(ONE_ROT.mean))} ft, y la cota queda por debajo. A ${hsec(25)} y ${hsec(50)} s la media es ${hkCi(HK("paired_diff", "near_committed", "primary", 25))} y ${hkCi(HK("paired_diff", "near_committed", "primary", 50))} ft. La referencia, en que el más cercano se mueve menos de ${es(NEAR_STAY_FT, 0)} pie hacia el jugador con balón, queda en ${hkCi(F2R)} ft. El contraste comprometida menos referencia, ${hkCi(COMM_C)} ft, se da y no se afirma: ya no lleva lectura.`),
  p(`Es una media, y penetración a penetración la defensa no está quieta. La mediana de las parejas (una penetración y uno de los tres) es ${sft(num(F2C.median))} y el ${pct(num(F2C.share_pos))} queda por encima de cero. En el ${pct(num(F2C.share_mover_left))} de las comprometidas al menos uno de los tres se mueve ${es(HELP_FT, 0)} pies o más hacia el hombre dejado, y en el ${pct(num(F2C.share_mover_placebo))} hacia los demás atacantes en promedio; en la referencia, el ${pct(num(F2R.share_mover_left))} y el ${pct(num(F2R.share_mover_placebo))}: en las dos clases, algo más hacia él que hacia el placebo, y por unos pocos puntos en las dos. A ${hsec(HEADLINE)} s un tercer defensor es el más cercano al hombre dejado en el ${pct(num(F2C.nearest_third))} de las comprometidas y en el ${pct(num(F2R.nearest_third))} de la referencia. Hay penetraciones en que uno de los tres va hacia él, como en la de la figura 1 (sección 9.1); lo que dice la media es que, en conjunto, no van hacia él más que hacia los demás.`),
  h2("17.4 No es un pre-registro"),
  p(`Estos números se vieron antes de escribir la afirmación, así que no es un pre-registro, y el README y la página lo dicen. Hay dos caminos que se bifurcaron después de ver resultados, y se declaran. Primero, el alcance se estrechó a la ayuda cercana después de los resultados de A8: el reparto en ayuda cercana y larga se fijó en ${PRE_SHA} antes de correr, se corrió en ${SPLIT_SHA}, y la tesis se acotó a la ayuda cercana comprometida en ${SCOPE_SHA}, sobre la lectura del entrenador (sección 13.7). Segundo, la clasificación cambió después de la revisión, y con ella lo que se podía afirmar: ya no un contraste por debajo de cero, sino una ausencia con su cota. En esta ronda solo se fijaron antes de correr las dos lecturas de la sección 17.6.`),
  h2("17.5 Robustez"),
  p("scripts/near_robustness.py mide la diferencia emparejada una sola vez por penetración y reagrupa las penetraciones según cada comprobación, con la unidad, los remuestreos y la semilla de scripts/second_help.py; antes de escribir nada comprueba que sus filas principales y las de la partición anterior son las de reports/help_kinds_summary.csv. Todo esto se vio después de escribir la afirmación: es un registro de robustez, no un pre-registro."),
  p(`La rejilla de los tres umbrales de la ayuda cercana (el paso del más cercano de ${es(gridVals("step_ft")[0], 1)} a ${es(gridVals("step_ft").slice(-1)[0], 1)} pies, la recuperación de ${es(gridVals("recover_ft")[0], 1)} a ${es(gridVals("recover_ft").slice(-1)[0], 1)} y el umbral de quedarse en casa de ${es(gridVals("stay_ft")[0], 1)} a ${es(gridVals("stay_ft").slice(-1)[0], 1)}), a ${hsec(HEADLINE)} s, da ${cells.length} celdas: en todas la lectura es AUSENCIA y el intervalo de las comprometidas contiene el cero. Su tope va de ${span(cells, "ci_high")} ft, la media de ${span(cells, "mean")} ft y el número de comprometidas de ${Math.min(...cells.map((r) => num(r.n)))} a ${Math.max(...cells.map((r) => num(r.n)))}; el intervalo del contraste contiene el cero en las ${cells.length}.`),
  grid(["Comprobación", "n", "Comprometidas, ft (IC 95 %)", "n ref.", "Referencia, ft (IC 95 %)", "Contraste, ft (IC 95 %)"],
    ["primary", "endpos", "fixed_targets", "no_pass", "detected", "coherent", "game_cluster"].map((c) => [CHECK_ES[c], RB(c, "committed").n, hkCi(RB(c, "committed")), RB(c, "reference").n, hkCi(RB(c, "reference")), hkCi(RB(c, "contrast"))]),
    [1926, 550, 1950, 600, 1950, 2050], { align: ["l", "r", "r", "r", "r", "r"] }),
  source(`reports/near_robustness.csv (check, group, n, mean, ci_low, ci_high), a ${hsec(HEADLINE)} s. En la comprobación por partidos la media es la de toda la muestra y el intervalo sale de remuestrear partidos.`),
  p(`Dejando fuera un partido cada vez (${LOO.length} partidos), la media de las comprometidas va de ${span(LOO, "mean")} ft y su intervalo contiene el cero en todos; el contraste va de ${span(LOOX, "mean")} ft. Remuestreando partidos en lugar de penetraciones, el intervalo de las comprometidas va de ${sg(num(RB("game_cluster", "committed").ci_low))} a ${sg(num(RB("game_cluster", "committed").ci_high))} ft. Sin pase en los primeros ${hsec(HEADLINE)} s queda en ${hkCi(RB("no_pass", "committed"))} ft (n = ${RB("no_pass", "committed").n}), con todos detectados en ${hkCi(RB("detected", "committed"))} ft (n = ${RB("detected", "committed").n}). Con los objetivos fijos donde estaban al arrancar, para que ninguna carrera de un atacante mueva el punto adonde apunta la medida, las comprometidas bajan a ${hkCi(RB("fixed_targets", "committed"))} ft, por debajo de cero, pero la referencia también (${hkCi(RB("fixed_targets", "reference"))} ft): esa variante se inclina hacia abajo por sí sola, y su contraste contiene el cero.`),
  p(`Los emparejamientos del más cercano: el más cercano es el defensor más próximo a su propio hombre según la tabla del proveedor, sin sustituir, al arrancar en ${cohText("committed")} de las comprometidas, ${cohText("reference")} de la referencia y ${cohText("committed_endpos")} con la partición anterior; sobre las ${COH("all_near_ok").n} penetraciones con el más cercano resuelto, ${COH("all_near_ok").n_coherent} (${pct(num(COH("all_near_ok").share))}). Donde coincide, las comprometidas quedan en ${hkCi(RB("coherent", "committed"))} ft. Es coherencia entre fuentes del mismo proveedor, no validación (sección 11.9).`),
  h2("17.6 Lo fijado antes de correr: el rotador designado y el pase"),
  p(`La revisión bibliográfica (docs/research/help_defense_literature.md) encontró que la doctrina de los entrenadores da la rotación que cubre al que ayuda a un solo defensor, y la sitúa en el pase; una media sobre los tres podría esconder las dos cosas. Antes de correr ninguna de las dos medidas, sus lecturas se escribieron en tasks/todo.md (tarea 13, punto a2) y se confirmaron en el commit ${A2_SHA}; los resultados están en reports/near_rotator.csv y reports/near_pass.csv.`),
  p(`El rotador designado. De los tres, R1 es el más cercano al hombre dejado al arrancar y R2 el hombre bajo, el más cercano al aro al arrancar. Lectura fijada, a ${hsec(HEADLINE)} s y para cada uno: si el intervalo de las comprometidas queda por encima de cero, la afirmación de ausencia es falsa para él y se cambia para decir que él rota; si contiene el cero o queda por debajo, la ausencia se sostiene también para él y el tope de su intervalo es una segunda cota. R1: ${hkCi(RT("R1", "committed"))} ft (n = ${RT("R1", "committed").n}), ${READING_ES[RT("R1", "committed").reading].toUpperCase()}, con la referencia en ${hkCi(RT("R1", "reference"))} ft. R2: ${hkCi(RT("R2", "committed"))} ft, ${READING_ES[RT("R2", "committed").reading].toUpperCase()}, con la referencia en ${hkCi(RT("R2", "reference"))} ft. La ausencia se sostiene para cada rotador designado, y el tope de R2, ${sg(num(RT("R2", "committed").ci_high))} ft, es la segunda cota.`),
  p(`El pase. La ventana es la del titular, del arranque a ${hsec(HEADLINE)} s; se cuentan las penetraciones con un pase de su oportunidad que empieza dentro y las que lo tienen hacia el hombre dejado, y desde la suelta del primero se mide 1,0 s, para los tres y para R1. Lectura fijada: con menos de ${PASS_MIN_N} comprometidas con ese segundo medible, un límite declarado con su n y sin afirmación. Empieza un pase dentro de la ventana en ${PCOUNT("pass_in_window", "committed")} de las ${PCOUNT("drives", "committed")} comprometidas (${PCOUNT("pass_to_man_left", "committed")} hacia el hombre dejado) y ${PCOUNT("post_pass_window", "committed")} tienen el segundo posterior medible: menos de ${PASS_MIN_N}, así que la lectura es LÍMITE, para los tres y para R1, y no se afirma nada. En la referencia hay ${PCOUNT("pass_in_window", "reference")}. La ventana de la afirmación ve sobre todo a la defensa antes de cualquier pase.`),
  h2("17.7 La ayuda larga, con sus números"),
  p(`El README del 30 de octubre decía de la ayuda larga que los entrenadores enseñan una rotación detrás de ella y que no se había buscado ninguna. Era falso: se buscó, con su definición fijada antes de correr (sección 13.4), y salen ${LONG_C.n} penetraciones de ${nResolved}. Contra las ${ni(LONG_C.n_ref)} en que el último se queda en casa, los otros tres se mueven hacia su hombre ${hkCi(LONG_C)} ft más a ${hsec(HEADLINE)} s, la dirección que enseñan los entrenadores, pero con ${LONG_C.n} penetraciones la lectura es ${READING_ES[LONG_C.reading].toUpperCase()} (sección 13.6). El README y la página dan ahora esos números, como límite.`),
  h2("17.8 La penetración de la figura 1"),
  p(`La regla de la figura 1 y de la página no cambió (sección 9.1), pero al cambiar la clase cambió la primera penetración que la cumple: la escena 0 era ${OSC.drive_id} (commit ${REPICK_SHA}) y ahora es ${SC.drive_id}; las otras tres (${scenes.scenes.slice(1).map((s) => s.drive_id).join(", ")}) no cambian. La nueva es un ejemplo de lo que corrigió la revisión. Con la partición anterior era una finta: a los 2,0 s el ayudante estaba a ${ft(scToManNow)} de su hombre, menos que sus ${ft(scStart)} de arranque más ${es(RECOVER_FT, 0)} pie. Pero no había vuelto: fue su hombre el que se desplazó ${ft(scManMoved)}, y el ayudante está a ${ft(scToManStart)} del punto donde empezó su hombre. Lo que enseña está en la sección 9.1: el ayudante es a ${es(SCT / scenes.fps, 1)} s el defensor más cercano al hombre que deja (${ft(SC.clearance_ft["1.5s"])}), y la media de los otros tres, ${sft(SC.paired_mean_1_5s)}, cae en el percentil ${es(scAmong.percentile, 0)} de las ${scAmong.n_helped}.`),
  h2("17.9 Lo que cambió en el resto"),
  p("La figura 2 lleva la ausencia con su cota y la escala de una rotación, y no se dibuja si la afirmación deja de sostenerse (sección 9.2); la figura 1 y la página tienen la penetración nueva (secciones 9.1 y 14.6); el README se reescribió (sección 15.5); el vídeo no se ha vuelto a grabar (sección 16.4). Javier tiene que ver la figura 2 y la escena 0 nuevas antes de darlas por buenas (sección 19)."),
];

const s12 = [
  h1("18. Plan y calendario", { pageBreakBefore: true }),
  grid(["Fase", "Fechas", "Trabajo", "Estado"], [
    ["Semanas 1 y 2", "28 de octubre", "scbasket.wind, el script, los tests y los CSV; las dos figuras", "Hecho"],
    ["A", "29 de octubre a 8 de noviembre", "La ausencia, medida: scbasket.rotation con su placebo, sus tests, scripts/second_help.py y sus CSV; la tasa base en la tabla de ayuda; la figura 2 nueva; memoria v0.3", "Cerrada el 29 de octubre: A1 a A4 el 28, A5 a A7 el 29, con la figura 2 aprobada por Javier. El mismo día, antes de la fase B, la tasa base de la esquina, la primera mitad de la tesis retirada y la figura 1 redibujada (sección 12; memoria v0.4)"],
    ["B", "9 a 29 de noviembre", "La página: el campo kernel dentro del paquete, cuatro penetraciones elegidas por una regla, el guion visual antes del motor, la página en 3D (WebGL con three.js dentro del HTML, sin CDN) que abre con la penetración y sube a vista cenital para la medida, conducida desde la consola; memoria v0.5", "En curso, adelantada: B1 a B5 hechas entre el 29 y el 30 de octubre, con el arranque rehecho con jugadores (B4b) y aprobado por Javier; la sección de la página en esta memoria (B6, sección 14) hecha el 30 de octubre; queda que Javier la abra en su máquina (B7)"],
    ["C", "30 de noviembre a 6 de diciembre", "El repositorio público; la página publicada en GitHub Pages y enlazada desde el README; el README de 1000 palabras con su comprobador; un clon limpio; memoria v0.6", "C1 a C4 hechas el 30 de octubre, antes de su ventana: el README anterior archivado en docs/bounce con la etiqueta bounce-final, el README nuevo de 890 palabras con dos figuras y un comprobador (scripts/check_readme.py) que recalcula desde los CSV sus 29 cifras en negrita, el clon limpio y la sección 15 de esta memoria. C1b publicada el mismo día con el visto bueno de Javier y aceptada (la comprobación desde la consola pasa entera contra la dirección); el arranque, que a veces pasa de 1,0 s en local y por red, queda abierto como asunto de la página (sección 15.4); C5 (que Javier lea el README) espera a Javier"],
    ["D", "7 a 13 de diciembre", "El vídeo: guion, diapositivas, corte mudo y la voz de Javier; memoria v0.7", "Adelantada: el corte mudo de 60 s, encuadrado para el móvil, hecho el 31 de octubre (sección 16). Tras la reclasificación hay que volver a grabarlo (paso c, sección 16.4) con el guion que apruebe Javier; la voz de Javier, pendiente"],
    ["E", "14 a 18 de diciembre", "Dispositivos reales, memoria v1.0, la verificación final con la única revisión adversarial, y el envío antes del 17", "Pendiente"],
  ], [1100, 1700, 3626, 2600]),
  p("Cada fase cierra con ruff y pytest en verde y una revisión con Javier. El detalle de cada tarea, con su criterio de aceptación y su modelo, está en tasks/todo.md."),
  p("Decidido el 29 de octubre (Javier, decisión D8): la página abre con la penetración de la regla en 3D, con una cámara parecida a la de la retransmisión, y la cámara sube a la vista cenital para la medida; el vídeo la graba desde la propia página. El 3D no entra en el README: GitHub solo muestra imágenes, las bases permiten dos figuras, y la perspectiva deforma justo lo que se mide (pies sobre el suelo hacia un punto: un pie cerca de la cámara no se ve igual que uno al fondo), así que solo en la vista cenital el lector puede juzgar \"hacia\" a ojo. Por eso ninguna medida se enseña en la vista en perspectiva, y la comprobación desde la consola lo exige. Límites que viajan con la decisión: el tracking no trae cuerpos, así que de cada jugador solo se mide su posición en el suelo (al principio se dibujaron fichas; véase la sección 14); la altura del balón arrastra la anomalía del eje vertical (sección 4); y ya existe un visor 3D de este mismo bundle, así que el 3D puntúa en comunicación si enseña al ayudante y al hombre que deja, y en originalidad nada."),
  p("Decidido el mismo día (Javier): la página se publica en GitHub Pages, gratis y desde el mismo repositorio público, y el README enlaza a esa dirección. GitHub enseña un HTML guardado en el repositorio como código fuente, así que un enlace al fichero mostraría el código y no la página. Hoy el repositorio no tiene remoto; crearlo en GitHub y subirlo es publicar hacia fuera, y Javier lo confirma en ese momento (tarea C1b). La publicación se da por buena cuando la dirección responde, sirve el mismo fichero que está en el repositorio y la comprobación desde la consola pasa contra ella, no contra la copia local."),
  p("Decidido el 31 de octubre (Javier), tras la revisión adelantada de la fase E: la afirmación pasa a ser la ausencia medida, con la cota del intervalo y la escala de una rotación, y el título se queda (sección 17). La revisión desencadena una cascada en tres pasos, uno detrás de otro porque comparten los CSV, la plantilla, la comprobación desde la consola y la GPU: a, el análisis, la reclasificación y las figuras; b, la página, el README y esta memoria; c, el vídeo."),
  h2("18.1 Riesgos asumidos"),
  bullet("La fase B tiene tres semanas a tiempo parcial para la escena 3D, la reproducción de las penetraciones y la conducción desde la consola, sin holgura dentro; el 3D (WebGL) cuesta más que el canvas 2D que había en el plan, sin horas medidas; la voz necesita a Javier en una ventana de siete días."),
  bullet("Parte del viento hacia el aro es la defensa entera hundiéndose con la penetración, no ayuda. Se nombra desplazamiento colectivo; el ayudante es el que más se mueve hacia el balón futuro, y eso no separa del todo las dos cosas: por encima del balón, hundirse cuenta como ayuda (sección 12.3)."),
  bullet("Todo depende de la tabla matchups del proveedor para saber quién es el emparejado del balón y a quién marcaba el ayudante. Donde falta, se usa el defensor más cercano para el primero y se deja vacío el segundo. Esa tabla no se ha contrastado con vídeo (no lo hay en los datos abiertos); la sección 11.9 mide cuánto concuerda con la cercanía y repite el contraste donde está corroborada, y es coherencia, no validación."),
  bullet("Diez partidos: las firmas por equipo son ilustración; el campo de la liga es el entregable."),
  bullet(`El marco de la penetración se define por el movimiento lateral neto del jugador con balón en el primer segundo. En penetraciones casi rectas ese signo es casi arbitrario, lo que difumina qué es "lado de la penetración" y qué "lado contrario" (y explica en parte que el hombre libre se reparta ${pct(N.leftFarSide)} contra ${pct(1 - N.leftFarSide)}); no afecta a "desde la esquina", que es simétrico. El campo direction del proveedor coincide con ese signo en ${pct(N.directionAgree)} de las penetraciones: dos de cada tres, así que ni valida ni sustituye al espejo sin más estudio.`),
  bullet("Las posiciones extrapoladas (jugadores fuera de plano) tienen un error de 4 a 5 pies. La tabla guarda la bandera de detección del ayudante en los dos extremos para poder contar cuántas ayudas descansan en una posición extrapolada."),
];

const s13 = [
  h1("19. Pendientes y decisiones abiertas"),
  numbered("Cerrado el 29 de octubre: range.bin, un fichero suelto de 100 bytes (el principio de un frame de tracking en JSON) en la raíz del repo y sin referencia alguna, se borró por decisión de Javier."),
  numbered("La rotación después del pase (el X-out) no se puede juzgar con 18 casos; se publica como límite."),
  numbered("Cerrados el 28 de octubre por la decisión de entrada única: confirmar si una persona puede presentar dos entradas (ya no aplica), avisar a SkillCorner del kit de calibración y grabar la voz del vídeo del rebote (ninguno de los dos se envía). Decidido el mismo día: el repositorio público de la entrada es este (sección 10.4)."),
  numbered("Cerrado el 29 de octubre: la figura 1 (la penetración que enseña la medida) no se explicaba sola: al verla, Javier preguntó qué representa, el riesgo de comunicación que señaló el segundo cribado del council (48 sobre 100). Se rehízo ese día para que se lea sola, con una lectura en frío antes y después en lugar de otro cribado (sección 9.3), y Javier la aprobó."),
  numbered(`El README y la página tienen que llevar el matiz del ayudante (sección 12.3) junto al ${pct(N.shareHelped, 1)}, y la esquina como ocupación, no como afirmación.`),
  numbered("El arranque de la página: en una carga en frío el primer fotograma pasa a veces de 1,0 s, contra la dirección o en local (sección 15.4). La red no es la causa; el encuadre de la cámara ya cuesta cinco veces menos (sección 15.4); queda una carga en frío lenta ocasional sin explicar, y el objetivo no se mueve."),
  numbered("Javier tiene que ver la figura 2 nueva (la ausencia con su cota y la línea de una rotación) y la escena 0 nueva, que es la figura 1 y la primera penetración de la página (sección 17.8), antes de darlas por buenas."),
  numbered("El vídeo, paso c (sección 16.4): el guion de las escenas 2 y 4 a 6, que Javier apruebe las palabras, la clave de color de la pausa sobre los puntos de la figura 2, volver a grabar y la vista previa a su móvil. Hasta entonces el MP4 lleva las cifras de antes de la reclasificación, y la locución, una distancia que ya es falsa."),
];

const s14 = [
  h1("20. Registro de versiones de este documento"),
  grid(["Versión", "Fecha", "Cambios"], [
    ["0.1", "28 de octubre de 2026", "Creación. Competición, dato, antecedentes, ideación con las tres sondas, definiciones, implementación y resultados de la semana 1, las dos figuras de la semana 2, plan y pendientes."],
    ["0.2", "28 de octubre de 2026", "Título nuevo, \"Nobody helps the helper\". Sección 10 nueva: una sola entrada de baloncesto, el council (37 sobre 100) y la sonda de la segunda ayuda. Tasa base junto al porcentaje de hombres libres en las secciones 8 y 9. Plan por fases A a E en la sección 11. Pendientes depurados por la decisión de entrada única."],
    ["0.3", "29 de octubre de 2026", "Sección 11 nueva, \"La segunda ayuda: una ausencia medida\", leída de reports/second_help_*.csv: el diseño del placebo, la diferencia emparejada con su media, su intervalo, la mediana y la cuota de parejas, los signos por partido, la sensibilidad, quién está más cerca del hombre dejado, su cuota de libre con la tasa base, el pase y el X-out como límite. Figura 2 nueva (quién cubre al hombre que deja) en 9.2. Sección 10.3 reducida: sus cifras pasan a la 11 y vienen de los CSV. Tasa base y rangos de las secciones 8.3 y 8.4 leídos de help_by_game.csv y help_sensitivity.csv, no tecleados. Plan: A1 a A5 hechas. Secciones 11 a 13 anteriores renumeradas a 12 a 14."],
    ["0.4", "29 y 30 de octubre de 2026", "Sección 12 nueva, \"La esquina, con su tasa base\", leída de reports/help_base_rate.csv: la tasa por defensor por banda de |y| y por zona, con su intervalo; la comparación con lo que predicen la distancia y la orientación del punto adonde va el balón; el matiz del ayudante (por encima del balón, hundirse cuenta como ayuda); y lo decidido: primera mitad de la tesis retirada, figura 1 descriptiva, ayudante sin redefinir. Corregidas la definición de la sección 6, la frase de la 8.4 sobre el título, la tesis de la 10.4 (con nota) y un riesgo de la 13.1. El mapa de viento, redibujado con la tasa por defensor y su franja a 11 puntos, sale del README tras un cribado de 37 sobre 100 y pasa a 12.5; la figura 1 nueva (9.1) es una penetración elegida por regla (scripts/wind_scenes.py, B2 adelantada) que enseña la medida con su percentil y la tira de todas las penetraciones con ayudante; 9.3 cuenta las miradas y los dos cribados (37 y 48 sobre 100), y cómo se rehízo la figura 1 para que se lea sola, probada con una lectura en frío antes y después, y aprobada por Javier. El campo kernel del mapa de viento pasa al paquete y a reports/help_field.csv (12.5). Guion de la página aprobado, página construida y probada desde la consola; el arranque se rehace con jugadores 3D (sección 13). Plan: la página abre con la penetración en 3D y sube a vista cenital para la medida (decisión D8, sección 13), y se publica en GitHub Pages en la fase C. La tabla de la sección 8 lleva la tasa base de la esquina. Plan y pendientes al día; secciones 12 a 14 anteriores renumeradas a 13 a 15. El 30 de octubre, antes de compartirla: el arranque con jugadores, cerrado (B4b, sección 13), con sus cuatro arreglos, la pasada del encuadre y el público, y la regla del margen inferior medida contra la página anterior."],
    ["0.5", "30 de octubre de 2026", "Sección 13 nueva, \"La página\": lo que decidió el guion, cómo se construyó y se rehízo el arranque (movido desde el plan), lo que comprueba la consola (184 comprobaciones en la GPU, con sus tiempos y el margen inferior) y las versiones de la página estropeadas a propósito que la hacen fallar, con lo que no cubre. Plan, pendientes y registro pasan a las secciones 14, 15 y 16; el plan conserva la decisión D8 y la publicación en GitHub Pages, con un puntero a la 13. El 30 de octubre, además, el README de la entrada (876 palabras, dos figuras, 31 cifras en negrita recalculadas desde los CSV por scripts/check_readme.py) sustituye al del rebote, archivado en docs/bounce; la dirección de la página en el README sigue siendo el fichero local hasta C1b."],
    ["0.6", "30 de octubre de 2026", "Sección 14 nueva, \"El repositorio público y el README\": la decisión D2 (este repositorio es la entrada, etiqueta bounce-final, README del rebote en docs/bounce), lo que dice y lo que deja fuera el README nuevo, cómo lo vigila scripts/check_readme.py con su prueba de fallo, el resultado del clon limpio y lo que espera a Javier (C1b). Plan, pendientes y registro pasan a las secciones 15, 16 y 17; la fila de la fase C del plan se pone al día (890 palabras, 29 cifras en negrita). El mismo día, la página publicada en GitHub Pages (C1b) con su verificación y el arranque por red como pendiente. Después, la subsección 11.9, \"Los emparejamientos del proveedor\": la coherencia de la tabla matchups al arrancar y el contraste de la segunda ayuda en subconjuntos donde el emparejamiento está corroborado."],
    ["0.7", "30 de octubre de 2026", "Sección 13 nueva, \"Ayuda cercana y ayuda larga\", leída de reports/help_kinds_summary.csv: la distinción del entrenador entre la ayuda cercana (finta o comprometida) y la ayuda larga del último, las definiciones de scbasket.help_kinds, por qué se cambió la regla de la primera sonda, las lecturas fijadas en un commit antes de correr, los resultados a 1,5 s con sus sensibilidades, los tres veredictos y los límites. La página, el repositorio, el plan, los pendientes y el registro pasan a las secciones 14 a 18."],
    ["0.8", "30 de octubre de 2026", "Sección 15.4: el arranque por red, medido. La deducción anterior (la diferencia está en la red) era falsa: con la comprobación desde la consola alternando el fichero local y la dirección, la dirección pasa entera y el local falla la fila del primer fotograma. scripts/startup_split.py separa la descarga del trabajo del hilo principal y reparte el script de la página por sus llamadas de arranque. Pendientes (sección 17) y fila de la fase C al día."],
    ["0.9", "30 de octubre de 2026", "Sección 15.4: el encuadre de la cámara de retransmisión, recortado sin cambiar su resultado (diferencia 0 contra la versión anterior en cuatro escenas y tres tamaños); de 128 a 22,5 ms por escena y la mediana del fin del análisis de la página de 837 a 684 ms. Una carga en frío de la comprobación sigue pasando de 1,0 s."],
    ["0.10", "30 de octubre de 2026", `Sección 9.1: la figura 1 y las cuatro penetraciones de la página, elegidas de nuevo con la misma regla entre las ${scAmong.n_helped} ayudas cercanas comprometidas (el ayudante es el más cercano y el hombre que deja, el suyo); la figura 1 es otra penetración del mismo partido, en el percentil ${es(scAmong.percentile, 0)} de las ${scAmong.n_helped}. El texto de la página, el README y la figura 2 siguen con el ayudante publicado hasta los pasos siguientes.`],
    ["0.11", "30 de octubre de 2026", "Secciones 9.2, 14 y 15: la figura 2, el texto de la página y el README, reescritos a la tesis acotada (ayuda cercana comprometida contra la referencia en que el más cercano se queda en casa; el resultado de todos los ayudantes publicados y la ayuda larga, como calificativo y límite). La fila anterior se había etiquetado 1.0, que está reservada para la versión final (tarea E2); pasa a 0.10."],
    ["0.12", "30 de octubre de 2026", "Sección 14.5 nueva, \"La primera pantalla\": los seis arreglos de la auditoría de diseño que aprobó Javier (el escenario primero y a todo el ancho, con el título y en el escritorio los controles sobre el lienzo; las barras a la vista tras subir a la vista cenital; el resultado como número grande; objetivos táctiles de 44 píxeles; el hash del pie separado de su asunto), las filas nuevas de la comprobación desde la consola con sus pruebas de fallo, y el coste medido en el primer fotograma, alternando la página anterior y la nueva. Sección 14.3 al día (106 filas, 196 comprobaciones)."],
    ["0.13", "31 de octubre de 2026", "Sección 16 nueva, \"El vídeo\": scripts/wind_video.py graba la propia página, fotograma a fotograma desde la consola, en un MP4 mudo de 61,000 s y 1525 fotogramas (ffprobe), con las ventanas leídas del guion, el anillo sobre el hombre dejado a partir de la proyección de la página, la figura 2 deslizada con las cifras comprobadas contra su CSV y el cierre en la vista cenital; la voz de guía de prueba y cuánto se pasa cada línea. Plan, Pendientes y Registro pasan a 17, 18 y 19."],
    ["0.14", "31 de octubre de 2026", "Sección 16.3: segunda pasada del vídeo. La línea de la escena 6 recortada por el propietario y las ventanas a 60,000 s exactos (1500 fotogramas), con el analizador que rechaza más de 60 s; captura a escala 2 con etiquetas de 24 y 26 píxeles por CSS inyectado y recorte por fotograma a los siete protagonistas (zoom de 1,00x a 1,32x; con los diez no hay recorte); la figura 2 en dos recortes fijos cortados con los límites de palabra de la voz de guía; la tabla de ajuste voz-ventana otra vez, ahora sin desbordes."],
    ["0.15", "31 de octubre de 2026", "Sección 17 nueva, \"La revisión y la reclasificación\": la partición finta / comprometida leía el punto adonde apunta la medida; la regla nueva (solo el movimiento del ayudante) con los números antes y después; la afirmación nueva, la ausencia medida con su cota y su escala, y su reparto por penetración; que no es un pre-registro y los dos caminos que se bifurcaron; la robustez (rejilla, comprobaciones y emparejamientos, de reports/near_*.csv); las lecturas fijadas en un commit antes de correr (los rotadores designados y el pase); la ayuda larga con sus números; la penetración nueva de la figura 1. Corregidas al mismo cambio las secciones 9.1 (la escena 0 nueva), 9.2 (la figura 2 lleva la ausencia; el contraste se da y no se afirma), 9.3, 13 (la regla, los recuentos, la postura de los publicados y el veredicto de la ayuda comprometida, con el de A8 conservado y marcado como superado), 14.6 nueva (la página, sus guardas y la comprobación desde la consola), 15.1, 15.2 y 15.5 nueva (el README de 997 palabras), 16.4 nueva (el vídeo, sin volver a grabar). Plan, Pendientes y Registro pasan a 18, 19 y 20."],
  ], [1200, 2200, 5626]),
];

// ------------------------------------------------------------------------- documento

const doc = new Document({
  creator: "Javier Sánchez Rueda",
  title: "Nobody helps the helper: memoria del proyecto",
  description: "Memoria viva de la entrada a la Analytics Cup 2.0",
  styles: {
    default: { document: { run: { font: "Arial", size: BODY } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 140 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
        alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: 11906, height: 16838 },
              margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } },
    },
    headers: { default: new Header({ children: [new Paragraph({ children: [
      new TextRun({ text: "Nobody helps the helper | memoria del proyecto", size: 16, color: "777777" }),
    ] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: `v${VERSION} | página `, size: 16, color: "777777" }),
      new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "777777" }),
    ] })] }) },
    children: [...cover, ...toc, ...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...s8, ...s9,
               ...s9b, ...s10, ...sSecond, ...sCorner, ...sKinds, ...sPage, ...sRepo, ...sVideo, ...sReview, ...s12, ...s13, ...s14],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  console.log(`wrote ${OUT} (${(buffer.length / 1024).toFixed(0)} KB)`);
  console.log(`drives ${N.drives}, resolved ${N.resolved}, helped ${N.helped} (${pct(N.shareHelped, 1)}), ` +
              `corner side ${pct(N.fromCorner, 1)}, open ${pct(N.leftOpen, 1)}, beyond arc ${pct(N.leftBeyondArc, 1)}`);
});
