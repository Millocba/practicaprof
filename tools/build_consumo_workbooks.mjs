import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputRoot] = process.argv.slice(2);
if (!inputPath || !outputRoot) throw new Error("Uso: node build_consumo_workbooks.mjs input.json output_root");
const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const qaDir = path.dirname(inputPath);

const definitions = [
  {
    key: "interno", folder: "consumo_interno", file: "consumo_interno.xlsx",
    sheet: "Consumo interno", table: "ConsumoInternoTable", color: "#1F4E78",
    widths: [15, 13, 18, 16, 16], numberFormats: { C: "0.00" },
    quality: { claves_naturales_imperfectas: true, tipos_mixtos_matricula: true },
  },
  {
    key: "externo", folder: "consumo_externo", file: "consumo_externo.xlsx",
    sheet: "Consumo externo", table: "ConsumoExternoTable", color: "#9E480E",
    widths: [23, 25, 24, 18, 25, 14, 18, 25, 27, 24, 19, 24],
    numberFormats: { F: "#,##0", G: "0.00", H: "#,##0.00", I: "#,##0.00" },
    quality: { claves_naturales_imperfectas: true, contingencias: true },
  },
];

for (const definition of definitions) {
  const source = payload[definition.key];
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add(definition.sheet);
  sheet.showGridLines = false;
  const matrix = [source.columns, ...source.rows.map((row) => source.columns.map((column) => row[column] ?? null))];
  const used = sheet.getRangeByIndexes(0, 0, matrix.length, source.columns.length);
  used.values = matrix;
  used.format.font = { name: "Aptos", size: 10, color: "#1F2937" };
  used.format.rowHeight = 20;
  const header = sheet.getRangeByIndexes(0, 0, 1, source.columns.length);
  header.format = {
    fill: definition.color,
    font: { name: "Aptos Display", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
    borders: { preset: "outside", style: "medium", color: definition.color },
  };
  header.format.rowHeight = 38;
  definition.widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, matrix.length, 1).format.columnWidth = width;
  });
  for (const [column, numberFormat] of Object.entries(definition.numberFormats)) {
    sheet.getRange(`${column}2:${column}${matrix.length}`).format.numberFormat = numberFormat;
  }
  sheet.freezePanes.freezeRows(1);
  const lastColumn = String.fromCharCode(64 + source.columns.length);
  const table = sheet.tables.add(`A1:${lastColumn}${matrix.length}`, true, definition.table);
  table.style = definition.key === "interno" ? "TableStyleMedium2" : "TableStyleMedium9";
  table.showFilterButton = true;
  table.showBandedRows = true;

  const outputDir = path.join(outputRoot, definition.folder);
  await fs.mkdir(outputDir, { recursive: true });
  const outputPath = path.join(outputDir, definition.file);
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
  const inspection = await workbook.inspect({ kind: "table", range: `${definition.sheet}!A1:${lastColumn}8`, include: "values,formulas", tableMaxRows: 8, tableMaxCols: source.columns.length, maxChars: 6000 });
  await fs.writeFile(path.join(qaDir, `${definition.key}_inspection.ndjson`), inspection.ndjson, "utf8");
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: `errores de ${definition.key}` });
  await fs.writeFile(path.join(qaDir, `${definition.key}_errors.ndjson`), errors.ndjson, "utf8");
  const preview = await workbook.render({ sheetName: definition.sheet, range: `A1:${lastColumn}24`, scale: 1.25, format: "png" });
  await fs.writeFile(path.join(qaDir, `${definition.key}_preview.png`), new Uint8Array(await preview.arrayBuffer()));

  const bytes = await fs.readFile(outputPath);
  const manifest = {
    source: definition.key === "interno" ? "consumo_interno" : "consumo_externo",
    synthetic: true, seed: payload.seed, period: payload.period, rows: source.rows.length,
    columns: source.columns, vehicle_coverage: payload.coverage, shared_event_projection: true,
    injected_quality: definition.quality,
    sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
  };
  await fs.writeFile(path.join(outputDir, definition.file.replace(".xlsx", ".manifest.json")), JSON.stringify(manifest, null, 2) + "\n", "utf8");
  await fs.rm(`${outputPath}.inspect.ndjson`, { force: true });
}
