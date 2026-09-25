import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputDir] = process.argv.slice(2);
if (!inputPath || !outputDir) throw new Error("Uso: node build_flota_workbook.mjs input.json output_dir");

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const qaDir = path.dirname(inputPath);
const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Flota");
sheet.showGridLines = false;

const matrix = [payload.columns, ...payload.rows.map((row) => payload.columns.map((column) => row[column] ?? null))];
const used = sheet.getRangeByIndexes(0, 0, matrix.length, payload.columns.length);
used.values = matrix;
used.format.font = { name: "Aptos", size: 10, color: "#1F2937" };
used.format.rowHeight = 20;

const header = sheet.getRangeByIndexes(0, 0, 1, payload.columns.length);
header.format = {
  fill: "#1F4E78",
  font: { name: "Aptos Display", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "medium", color: "#17365D" },
};
header.format.rowHeight = 34;

sheet.getRange(`A2:D${matrix.length}`).format.numberFormat = "@";
sheet.getRange(`K2:K${matrix.length}`).format.numberFormat = "0";
sheet.getRange(`P2:Q${matrix.length}`).format.numberFormat = "0.00";
sheet.getRange(`U2:V${matrix.length}`).format.numberFormat = "@";
sheet.getRange(`W2:X${matrix.length}`).format.numberFormat = "#,##0.00";
sheet.getRange(`T2:T${matrix.length}`).format.numberFormat = "dd/mm/yyyy";

sheet.getRange("A:AA").format.columnWidth = 14;
sheet.getRange("C:D").format.columnWidth = 19;
sheet.getRange("E:F").format.columnWidth = 24;
sheet.getRange("G:J").format.columnWidth = 17;
sheet.getRange("L:O").format.columnWidth = 18;
sheet.getRange("T:T").format.columnWidth = 22;
sheet.getRange("Y:Z").format.columnWidth = 22;
sheet.freezePanes.freezeRows(1);

const table = sheet.tables.add(`A1:AA${matrix.length}`, true, "FlotaCrudaTable");
table.style = "TableStyleMedium2";
table.showFilterButton = true;
table.showBandedRows = true;

await fs.mkdir(outputDir, { recursive: true });
const outputPath = path.join(outputDir, "flota_vehicular.xlsx");
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);

const inspection = await workbook.inspect({ kind: "table", range: "Flota!A1:AA8", include: "values,formulas", tableMaxRows: 8, tableMaxCols: 27, maxChars: 8000 });
await fs.writeFile(path.join(qaDir, "flota_inspection.ndjson"), inspection.ndjson, "utf8");
const preview = await workbook.render({ sheetName: "Flota", range: "A1:J24", scale: 1.5, format: "png" });
await fs.writeFile(path.join(qaDir, "flota_preview.png"), new Uint8Array(await preview.arrayBuffer()));

const bytes = await fs.readFile(outputPath);
const manifest = {
  source: "flota",
  synthetic: true,
  seed: payload.seed,
  rows: payload.rows.length,
  columns: payload.columns,
  injected_quality: {
    duplicate_matricula_normalized: 32,
    duplicate_dominio_normalized: 32,
    mixed_representations: true,
  },
  sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
};
await fs.writeFile(path.join(outputDir, "flota_vehicular.manifest.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");
await fs.rm(`${outputPath}.inspect.ndjson`, { force: true });
await fs.rm(path.join(outputDir, "flota_inspection.ndjson"), { force: true });
await fs.rm(path.join(outputDir, "flota_preview.png"), { force: true });
