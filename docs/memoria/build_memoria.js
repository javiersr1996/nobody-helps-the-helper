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

const VERSION = "0.3";
const DATE = "29 de octubre de 2026";
const HOOP_X = -40.76; // scbasket.court.HOOP_X
const HELP_FT = 4.0;
const OPEN_FT = 6.0;
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
const sh = readCsv(path.join(REPORTS, "second_help_summary.csv"));
const shGame = readCsv(path.join(REPORTS, "second_help_by_game.csv"));
const shSens = readCsv(path.join(REPORTS, "second_help_sensitivity.csv"));
const shPass = readCsv(path.join(REPORTS, "second_help_pass.csv"));
const shClose = readCsv(path.join(REPORTS, "second_help_closeouts.csv"));

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

function figure(file, caption, ratio = 8.9 / 7.2) { // ratio alto/ancho; la figura 2 es 7,2 x 10,8 pulgadas
  const data = fs.readFileSync(path.join(FIGURES, file));
  const width = 460; // píxeles a 96 ppp: 4,8 pulgadas; las figuras son 7,2 x 8,9 pulgadas
  const height = Math.round(width * ratio);
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
  "11. La segunda ayuda: una ausencia medida", "12. Plan y calendario", "13. Pendientes y decisiones abiertas",
  "14. Registro de versiones de este documento",
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
  bullet([bold("Movimiento de ayuda. "), run("Para un defensor que no es el emparejado del jugador con balón, su propio desplazamiento durante el horizonte proyectado sobre el vector unitario que va desde donde empezó hasta donde está el jugador con balón al final del horizonte. En pies; positivo significa que se movió hacia donde iba el balón. Un defensor que solo se hunde con la penetración puntúa bajo, porque hundirse va a lo largo de la pista y la posición futura del balón le queda casi siempre de través.")]),
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
  p(`La misma tabla con el umbral y el horizonte barridos. La lectura que importa: "desde el lado de la esquina" se queda entre el ${pct(Math.min(...cornerSide))} y el ${pct(Math.max(...cornerSide))} en las ${sensitivity.length} celdas, así que el título aguanta bajo cualquier definición razonable; y a medio segundo solo una de cada ${es(1 / num(halfSecThree.share_with_helper), 0)} penetraciones tiene a alguien movido tres pies: la ayuda tarda más de medio segundo en verse.`),
  grid(["Horizonte (s)", "Umbral (ft)", "Con ayudante", "Por el centro", "Lado de la esquina", "Abierto", "Más allá del arco"],
    sensitivity.map((s) => [es(num(s.horizon_s)), es(num(s.help_ft), 0), pct(num(s.share_with_helper)), pct(num(s.helper_from_middle)), pct(num(s.helper_from_corner_side), 1), pct(num(s.left_open_share)), pct(num(s.left_beyond_arc))]),
    [1226, 1200, 1300, 1300, 1400, 1200, 1400], { align: ["r", "r", "r", "r", "r", "r", "r"] }),
  source("reports/help_sensitivity.csv."),
];

const s9 = [
  h1("9. Las dos figuras (semana 2, 28 de octubre de 2026)", { pageBreakBefore: true }),
  p("El concurso permite dos figuras y el argumento tiene dos mitades, así que no hay elección: de dónde viene la ayuda, y a quién deja. Las dos se dibujan en el marco de la penetración y en orientación de carta de tiro: el aro abajo, la línea de fondo debajo, y el movimiento lateral del jugador con balón hacia la derecha, de modo que \"el lado de la esquina\" es siempre la esquina inferior derecha. Dentro de la pista solo están la pista, el dato y el recorrido mediano del balón; números, claves y leyendas viven en una franja debajo, donde ninguna línea de corriente puede cruzarlos."),
  h2("9.1 Figura 1: el mapa de viento"),
  ...figure("wind_figure_1_wind_map.png", "Figura 1. El mapa de viento de las defensas de la ACB en el primer segundo de una penetración, y dónde arranca el ayudante."),
  p("Un campo suavizado por kernel gaussiano (ancho de banda 4 pies, rejilla de 1,5 pies) del desplazamiento de los cuatro defensores sin balón durante el primer segundo, sobre los " + thousands(vectors.length) + " vectores, dibujado como líneas de corriente cuyo grosor crece con el desplazamiento medio (clave en pies en la franja). Debajo, en naranja, la densidad de los puntos de origen del ayudante. El campo lleva a la defensa entera hundiéndose con la penetración además de la ayuda; la tabla separa las dos cosas (el movimiento de ayuda es la proyección hacia la posición futura del balón), la imagen no, y el pie lo dice. El viento solo se dibuja donde hubo defensores: las celdas con menos de diez vectores de masa kernel quedan en blanco, lo que eliminó un remolino espurio junto a la línea de fondo que tenía la primera versión."),
  h2("9.2 Figura 2: quién cubre al hombre que deja"),
  ...figure("wind_figure_2_who_covers.png", `Figura 2. Nadie más se mueve hacia el hombre que deja el ayudante: a ${hsec(HEADLINE)} s de arrancar la penetración, los otros tres defensores se mueven hacia él no más que hacia los demás atacantes sin balón, con o sin ayudante.`, 2262 / 1440),
  p(`Un punto por penetración con ayudante (${SH(HEADLINE, true).n_drives} de ${SH(25, true).n_drives}; en las demás la ventana no llega a ${hsec(HEADLINE)} s), allí donde está el atacante al que marcaba el ayudante. El color y la forma dicen quién es el defensor más cercano a él, y la leyenda da su cuota con la tasa base entre paréntesis: el propio defensor del hombre (el ayudante; sin ayudante, el que más se mueve por debajo del umbral, que marcaba al hombre comparable) el ${pct(num(SH(HEADLINE, true).nearest_helper))} frente al ${pct(num(SH(HEADLINE, false).nearest_helper))}, el emparejado del jugador con balón el ${pct(num(SH(HEADLINE, true).nearest_handler_def))} frente al ${pct(num(SH(HEADLINE, false).nearest_handler_def))} y un tercer defensor el ${pct(num(SH(HEADLINE, true).nearest_third))} frente al ${pct(num(SH(HEADLINE, false).nearest_third))}. Que el ayudante sea el más cercano es casi cierto por construcción, porque marcaba a ese hombre al empezar; por eso el titular no es ese, sino la ausencia de rotación. Es una medida de distancia, no de intención.`),
  p(`El panel de debajo es la prueba: la rotación de los otros tres defensores hacia el hombre dejado menos hacia el placebo (los demás atacantes sin balón), en pies, con la media por penetración y su intervalo del 95 % para ${HORIZONS.map((h) => hsec(h)).join(" / ")} s, con ayudante y sin él. Junto a cada media de las penetraciones con ayudante van la mediana y la cuota de parejas por encima de cero (una pareja es una penetración y uno de los tres defensores): el par típico queda cerca del placebo y la media la arrastran las colas. La serie sin ayudante también es negativa y los intervalos se solapan en los tres horizontes (la figura no se genera si dejaran de solaparse), así que la ayuda no provoca rotación hacia él más allá de la que ocurre sin ayudante. Robustez, contada al generar la figura: ${shSens.filter((r) => num(r.ci_low) > 0 || num(r.ci_high) < 0).length} de las ${shSens.length} celdas de la tabla de sensibilidad tienen un intervalo que excluye el cero, y a ${hsec(HEADLINE)} s ${shGame.filter((r) => num(r.horizon) === HEADLINE && bool(r.helped) && num(r.median_diff_pairs) < 0).length} de ${shGame.filter((r) => num(r.horizon) === HEADLINE && bool(r.helped)).length} partidos tienen una mediana por parejas negativa.`),
  p(`Al pie, la tasa base como dato y no como coste: el hombre dejado está libre (nadie a ${es(OPEN_FT, 0)} pies) el ${pct(num(SH(HEADLINE, true).left_open0_share))} al arrancar y el ${pct(num(SH(HEADLINE, true).left_open_share))} a ${hsec(HEADLINE)} s, y el hombre comparable en las penetraciones sin ayudante el ${pct(num(SH(HEADLINE, false).left_open0_share))} y el ${pct(num(SH(HEADLINE, false).left_open_share))}. La figura sustituye a la primera versión de la semana 2, los puntos del hombre dejado coloreados por estar libre o no, que sin tasa base inducía a error (sección 8).`),
  h2("9.3 Lo que se corrigió tras mirar la primera versión"),
  p("Las figuras se miraron antes de darlas por buenas, y la primera versión tenía defectos que solo se ven mirándolas: en la figura 1, el bloque de texto y la etiqueta del balón quedaban tapados por las líneas de corriente y había un remolino espurio junto a la línea de fondo; en la figura 2 de entonces (los puntos del hombre libre, ya sustituida), el histograma inserto y el texto pisaban puntos de la pista, la leyenda tapaba puntos arriba a la derecha, y las líneas grises desde el origen del ayudante ensuciaban sin aportar nada que no estuviera ya en la figura 1. Se movió todo lo que no es dato a la franja inferior, se endureció la máscara del campo, se quitaron las líneas, y en el título de la figura 2 se retiró \"lejos del balón\", que el 55 % no sostiene. Una tercera pasada arregló el solape entre el texto de la franja y la clave de grosor."),
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
  bullet([bold("Título: \"Nobody helps the helper\". "), run("Lo eligió Javier frente a la recomendación del planificador, que proponía mantener el anterior con este como subtítulo: la segunda ayuda que no llega pasa al frente. Tesis en una línea: la ayuda sopla desde el centro y nunca desde la esquina, y nadie ayuda al que ayuda; al hombre que deja le cubre el propio ayudante o nadie, medido contra un placebo.")]),
  bullet([bold("Repositorio público: este. "), run("Se etiqueta el estado actual como bounce-final y el README del rebote pasa a docs/bounce/; el paquete, la caché y los tests compartidos se quedan donde ya funcionan al clonar.")]),
  bullet([bold("Figura 2: quién cubre al hombre dejado. "), run("Los puntos se colorean según quién es su defensor más cercano y, debajo, la rotación frente al placebo con su intervalo y la tasa base en la misma frase.")]),
  bullet([bold("Cómo se trabaja. "), run("El plan por fases lo escribió Fable 5.1 como planificador, y cada tarea se ejecuta con el modelo de su etiqueta (Sonnet la mayoría, Haiku lo mecánico, Opus el motor de la página y la verificación final, Fable el guion visual de la página). A petición de Javier, una sola revisión adversarial, al cierre, y ninguna puerta que bloquee.")]),
];

// Datos de la sección 11, leídos de reports/second_help_*.csv.
const SHH = SH(HEADLINE, true);
const SHN = SH(HEADLINE, false);
const nLeft = num(SH(25, true).n_drives) + num(SH(25, false).n_drives); // penetraciones con hombre dejado
const hs = HORIZONS.map(hsec).join(" / ");
// Los intervalos con y sin ayudante se solapan en los tres horizontes (se comprueba, no se supone).
const ciOverlap = HORIZONS.every((h) => {
  const a = SH(h, true); const b = SH(h, false);
  return num(a.ci_low) <= num(b.ci_high) && num(b.ci_low) <= num(a.ci_high);
});
if (!ciOverlap) throw new Error("los IC con y sin ayudante ya no se solapan: revisar el texto de la sección 11");
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
  source("reports/second_help_summary.csv (mean_diff, ci_low, ci_high, median_diff, share_diff_positive). El intervalo es el de la media por penetración, por bootstrap sobre penetraciones; la mediana y la cuota son sobre parejas (una pareja es una penetración y uno de los tres defensores)."),
  p(`La media por penetración de la diferencia es negativa en los tres horizontes, con ayudante (${HORIZONS.map((h) => sg(num(SH(h, true).mean_diff))).join(" / ")} ft a ${hs} s) y sin él (${HORIZONS.map((h) => sg(num(SH(h, false).mean_diff))).join(" / ")} ft), y su intervalo del 95 % queda por debajo de cero en los seis casos. Pero la mediana sobre parejas con ayudante es ${HORIZONS.map((h) => sg(num(SH(h, true).median_diff))).join(" / ")} ft y solo el ${HORIZONS.map((h) => pct(num(SH(h, true).share_diff_positive))).join(" / ")} de las parejas está por encima de cero: el par típico queda cerca del placebo y la media la arrastran las colas, no una respuesta general de la defensa. Con ayudante y sin él los intervalos se solapan en los tres horizontes, de modo que la ayuda no deja una rotación distinguible de la que ya había. Un movimiento de ${es(HELP_FT, 0)} pies o más hacia el hombre dejado aparece en el ${pct(num(SHH.share_mover_left))} de las penetraciones con ayudante a ${hsec(HEADLINE)} s, contra el ${pct(num(SHH.share_mover_placebo))} hacia el placebo.`),
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
];


const s12 = [
  h1("12. Plan y calendario", { pageBreakBefore: true }),
  grid(["Fase", "Fechas", "Trabajo", "Estado"], [
    ["Semanas 1 y 2", "28 de octubre", "scbasket.wind, el script, los tests y los CSV; las dos figuras", "Hecho"],
    ["A", "29 de octubre a 8 de noviembre", "La ausencia, medida: scbasket.rotation con su placebo, sus tests, scripts/second_help.py y sus CSV; la tasa base en la tabla de ayuda; la figura 2 nueva; memoria v0.3", "A1 a A4 hechas el 28 de octubre; A5 hecha el 29 de octubre; A6 (esta memoria) y A7 (cierre de fase) pendientes"],
    ["B", "9 a 29 de noviembre", "La página: el campo kernel dentro del paquete, cuatro penetraciones elegidas por una regla, el guion visual antes del motor, la página en canvas sin CDN conducida desde la consola; memoria v0.4", "Pendiente"],
    ["C", "30 de noviembre a 6 de diciembre", "El repositorio público y el README de 1000 palabras con su comprobador; un clon limpio; memoria v0.5", "Pendiente"],
    ["D", "7 a 13 de diciembre", "El vídeo: guion, diapositivas, corte mudo y la voz de Javier; memoria v0.6", "Pendiente"],
    ["E", "14 a 18 de diciembre", "Dispositivos reales, memoria v1.0, la verificación final con la única revisión adversarial, y el envío antes del 17", "Pendiente"],
  ], [1100, 1700, 3626, 2600]),
  p("Cada fase cierra con ruff y pytest en verde y una revisión con Javier. El detalle de cada tarea, con su criterio de aceptación y su modelo, está en tasks/todo.md."),
  h2("12.1 Riesgos asumidos"),
  bullet("La fase B tiene tres semanas a tiempo parcial para el canvas, la reproducción de las penetraciones y la conducción desde la consola, sin holgura dentro; la voz necesita a Javier en una ventana de siete días."),
  bullet("Parte del viento hacia el aro es la defensa entera hundiéndose con la penetración, no ayuda. Se nombra desplazamiento colectivo; el ayudante es el que más se mueve hacia el balón futuro, lo que separa las dos cosas en la tabla pero no en la imagen."),
  bullet("Todo depende de la tabla matchups del proveedor para saber quién es el emparejado del balón y a quién marcaba el ayudante. Donde falta, se usa el defensor más cercano para el primero y se deja vacío el segundo."),
  bullet("Diez partidos: las firmas por equipo son ilustración; el campo de la liga es el entregable."),
  bullet(`El marco de la penetración se define por el movimiento lateral neto del jugador con balón en el primer segundo. En penetraciones casi rectas ese signo es casi arbitrario, lo que difumina qué es "lado de la penetración" y qué "lado contrario" (y explica en parte que el hombre libre se reparta ${pct(N.leftFarSide)} contra ${pct(1 - N.leftFarSide)}); no afecta a "desde la esquina", que es simétrico. El campo direction del proveedor coincide con ese signo en ${pct(N.directionAgree)} de las penetraciones: dos de cada tres, así que ni valida ni sustituye al espejo sin más estudio.`),
  bullet("Las posiciones extrapoladas (jugadores fuera de plano) tienen un error de 4 a 5 pies. La tabla guarda la bandera de detección del ayudante en los dos extremos para poder contar cuántas ayudas descansan en una posición extrapolada."),
];

const s13 = [
  h1("13. Pendientes y decisiones abiertas"),
  numbered("Cerrado el 29 de octubre: range.bin, un fichero suelto de 100 bytes (el principio de un frame de tracking en JSON) en la raíz del repo y sin referencia alguna, se borró por decisión de Javier."),
  numbered("La rotación después del pase (el X-out) no se puede juzgar con 18 casos; se publica como límite."),
  numbered("Cerrados el 28 de octubre por la decisión de entrada única: confirmar si una persona puede presentar dos entradas (ya no aplica), avisar a SkillCorner del kit de calibración y grabar la voz del vídeo del rebote (ninguno de los dos se envía). Decidido el mismo día: el repositorio público de la entrada es este (sección 10.4)."),
];

const s14 = [
  h1("14. Registro de versiones de este documento"),
  grid(["Versión", "Fecha", "Cambios"], [
    ["0.1", "28 de octubre de 2026", "Creación. Competición, dato, antecedentes, ideación con las tres sondas, definiciones, implementación y resultados de la semana 1, las dos figuras de la semana 2, plan y pendientes."],
    ["0.2", "28 de octubre de 2026", "Título nuevo, \"Nobody helps the helper\". Sección 10 nueva: una sola entrada de baloncesto, el council (37 sobre 100) y la sonda de la segunda ayuda. Tasa base junto al porcentaje de hombres libres en las secciones 8 y 9. Plan por fases A a E en la sección 11. Pendientes depurados por la decisión de entrada única."],
    ["0.3", "29 de octubre de 2026", "Sección 11 nueva, \"La segunda ayuda: una ausencia medida\", leída de reports/second_help_*.csv: el diseño del placebo, la diferencia emparejada con su media, su intervalo, la mediana y la cuota de parejas, los signos por partido, la sensibilidad, quién está más cerca del hombre dejado, su cuota de libre con la tasa base, el pase y el X-out como límite. Figura 2 nueva (quién cubre al hombre que deja) en 9.2. Sección 10.3 reducida: sus cifras pasan a la 11 y vienen de los CSV. Tasa base y rangos de las secciones 8.3 y 8.4 leídos de help_by_game.csv y help_sensitivity.csv, no tecleados. Plan: A1 a A5 hechas. Secciones 11 a 13 anteriores renumeradas a 12 a 14."],
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
               ...s10, ...sSecond, ...s12, ...s13, ...s14],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  console.log(`wrote ${OUT} (${(buffer.length / 1024).toFixed(0)} KB)`);
  console.log(`drives ${N.drives}, resolved ${N.resolved}, helped ${N.helped} (${pct(N.shareHelped, 1)}), ` +
              `corner side ${pct(N.fromCorner, 1)}, open ${pct(N.leftOpen, 1)}, beyond arc ${pct(N.leftBeyondArc, 1)}`);
});
