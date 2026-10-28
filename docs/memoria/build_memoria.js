// La memoria del proyecto "Nobody helps from the corner", como .docx, generada desde el repo.
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
const OUT = path.join(__dirname, "memoria_nobody_helps_from_the_corner.docx");

const VERSION = "0.1";
const DATE = "28 de octubre de 2026";
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
  const width = 460; // píxeles a 96 ppp: 4,8 pulgadas; las figuras son 7,2 x 8,9 pulgadas
  const height = Math.round(width * 8.9 / 7.2);
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
    new TextRun({ text: "Nobody helps from the corner", size: 56, bold: true }),
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
  "8. Resultados (semana 1)", "9. Las dos figuras (semana 2)", "10. Plan y calendario",
  "11. Pendientes y decisiones abiertas", "12. Registro de versiones de este documento",
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
  p("El corte por partido se publica y no se usa para decidir. La cuota de penetraciones con ayudante va del 33 % al 67 %: hay defensas distintas en la muestra, con uno o dos partidos cada una, lo que basta para ilustrar y no para comparar."),
  grid(["Partido", "Resueltas", "Con ayudante", "Hombre libre abierto", "Más allá del arco"],
    byGame.map((g) => [g.game, es(num(g.n_resolved), 0), pct(num(g.share_with_helper)), pct(num(g.left_open_share)), pct(num(g.left_beyond_arc))]),
    [1826, 1800, 1800, 1800, 1800], { align: ["l", "r", "r", "r", "r"] }),
  source("reports/help_by_game.csv."),
  h2("8.4 Sensibilidad"),
  p("La misma tabla con el umbral y el horizonte barridos. La lectura que importa: \"desde el lado de la esquina\" se queda entre el 0 % y el 4 % en las doce celdas, así que el título aguanta bajo cualquier definición razonable; y a medio segundo solo una de cada siete penetraciones tiene a alguien movido tres pies: la ayuda tarda más de medio segundo en verse."),
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
  p("Un campo suavizado por kernel gaussiano (ancho de banda 4 pies, rejilla de 1,5 pies) del desplazamiento de los cuatro defensores sin balón durante el primer segundo, sobre los 2.472 vectores, dibujado como líneas de corriente cuyo grosor crece con el desplazamiento medio (clave en pies en la franja). Debajo, en naranja, la densidad de los puntos de origen del ayudante. El campo lleva a la defensa entera hundiéndose con la penetración además de la ayuda; la tabla separa las dos cosas (el movimiento de ayuda es la proyección hacia la posición futura del balón), la imagen no, y el pie lo dice. El viento solo se dibuja donde hubo defensores: las celdas con menos de diez vectores de masa kernel quedan en blanco, lo que eliminó un remolino espurio junto a la línea de fondo que tenía la primera versión."),
  h2("9.2 Figura 2: el hombre que deja"),
  ...figure("wind_figure_2_open_man.png", "Figura 2. El precio de la ayuda: el hombre que deja, un segundo después, y a qué distancia tiene al defensor más cercano."),
  p(`Dónde está, un segundo después del inicio de la penetración, el atacante al que marcaba el ayudante: naranja si no hay ningún defensor a ${es(OPEN_FT, 0)} pies, gris si lo hay, con el histograma de esa distancia en la franja inferior. La mayoría está más allá del arco y sin nadie cerca; en cambio se reparte casi a partes iguales entre el lado de la penetración y el contrario (${pct(N.leftFarSide)} en el contrario), de modo que la idea de \"el lado débil\" no tiene apoyo en el dato y el título de la figura no la menciona.`),
  h2("9.3 Lo que se corrigió tras mirar la primera versión"),
  p("Las figuras se miraron antes de darlas por buenas, y la primera versión tenía defectos que solo se ven mirándolas: en la figura 1, el bloque de texto y la etiqueta del balón quedaban tapados por las líneas de corriente y había un remolino espurio junto a la línea de fondo; en la figura 2, el histograma inserto y el texto pisaban puntos de la pista, la leyenda tapaba puntos arriba a la derecha, y las líneas grises desde el origen del ayudante ensuciaban sin aportar nada que no estuviera ya en la figura 1. Se movió todo lo que no es dato a la franja inferior, se endureció la máscara del campo, se quitaron las líneas, y en el título de la figura 2 se retiró \"lejos del balón\", que el 55 % no sostiene. Una tercera pasada arregló el solape entre el texto de la franja y la clave de grosor."),
];

const s10 = [
  h1("10. Plan y calendario"),
  grid(["Semana", "Hasta", "Trabajo", "Estado"], [
    ["1", "4 de noviembre", "Módulo scbasket.wind, script, tests, CSVs", "Hecho el 28 de octubre"],
    ["2", "11 de noviembre", "Las dos figuras; tablas de sensibilidad y por partido", "Hecho el 28 de octubre"],
    ["3 y 4", "25 de noviembre", "La página: animación de viento con partículas sobre la pista (canvas HTML, sin CDN), una penetración real con sus cuatro estelas, el campo, el hombre libre; conducida desde la consola", "Pendiente"],
    ["5", "2 de diciembre", "README de 1000 palabras; diapositivas del vídeo y corte mudo cronometrado al guion", "Pendiente"],
    ["6", "9 de diciembre", "La voz; la página en un móvil y una ventana reales", "Pendiente"],
    ["7", "18 de diciembre", "Margen. Comprobar en las bases si una persona puede presentar dos entradas", "Pendiente"],
  ], [1000, 1700, 4826, 1500]),
  h2("10.1 Riesgos asumidos"),
  bullet("Parte del viento hacia el aro es la defensa entera hundiéndose con la penetración, no ayuda. Se nombra desplazamiento colectivo; el ayudante es el que más se mueve hacia el balón futuro, lo que separa las dos cosas en la tabla pero no en la imagen."),
  bullet("Todo depende de la tabla matchups del proveedor para saber quién es el emparejado del balón y a quién marcaba el ayudante. Donde falta, se usa el defensor más cercano para el primero y se deja vacío el segundo."),
  bullet("Diez partidos: las firmas por equipo son ilustración; el campo de la liga es el entregable."),
  bullet(`El marco de la penetración se define por el movimiento lateral neto del jugador con balón en el primer segundo. En penetraciones casi rectas ese signo es casi arbitrario, lo que difumina qué es "lado de la penetración" y qué "lado contrario" (y explica en parte que el hombre libre se reparta ${pct(N.leftFarSide)} contra ${pct(1 - N.leftFarSide)}); no afecta a "desde la esquina", que es simétrico. El campo direction del proveedor coincide con ese signo en ${pct(N.directionAgree)} de las penetraciones: dos de cada tres, así que ni valida ni sustituye al espejo sin más estudio.`),
  bullet("Las posiciones extrapoladas (jugadores fuera de plano) tienen un error de 4 a 5 pies. La tabla guarda la bandera de detección del ayudante en los dos extremos para poder contar cuántas ayudas descansan en una posición extrapolada."),
];

const s11 = [
  h1("11. Pendientes y decisiones abiertas"),
  numbered("Confirmar en las bases si una persona puede presentar más de una entrada. Hay tres en distinto estado: el rebote (completo, a falta de la voz), el kit de calibración (sondas y página) y esta."),
  numbered("Decidir dónde vive el repositorio público de esta entrada. Hoy se construye dentro de skillcorner_basket_data, el repo del rebote, porque comparte la caché de fotogramas y el paquete; para enviar harán falta un README y un repo propios, con scbasket como dependencia o con los módulos necesarios dentro."),
  numbered("Avisar a SkillCorner del hallazgo del kit de calibración antes de enviarlo, si se envía."),
  numbered("Grabar la voz del vídeo del rebote."),
  numbered("Un fichero suelto, range.bin (100 bytes de JSON con otro esquema), en la raíz del repo sin referencia alguna; Javier decide si se borra."),
];

const s12 = [
  h1("12. Registro de versiones de este documento"),
  grid(["Versión", "Fecha", "Cambios"], [
    ["0.1", "28 de octubre de 2026", "Creación. Competición, dato, antecedentes, ideación con las tres sondas, definiciones, implementación y resultados de la semana 1, las dos figuras de la semana 2, plan y pendientes."],
  ], [1200, 2200, 5626]),
];

// ------------------------------------------------------------------------- documento

const doc = new Document({
  creator: "Javier Sánchez Rueda",
  title: "Nobody helps from the corner: memoria del proyecto",
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
      new TextRun({ text: "Nobody helps from the corner | memoria del proyecto", size: 16, color: "777777" }),
    ] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: `v${VERSION} | página `, size: 16, color: "777777" }),
      new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "777777" }),
    ] })] }) },
    children: [...cover, ...toc, ...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...s8, ...s9,
               ...s10, ...s11, ...s12],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  console.log(`wrote ${OUT} (${(buffer.length / 1024).toFixed(0)} KB)`);
  console.log(`drives ${N.drives}, resolved ${N.resolved}, helped ${N.helped} (${pct(N.shareHelped, 1)}), ` +
              `corner side ${pct(N.fromCorner, 1)}, open ${pct(N.leftOpen, 1)}, beyond arc ${pct(N.leftBeyondArc, 1)}`);
});
