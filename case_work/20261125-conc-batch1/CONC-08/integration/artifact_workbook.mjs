import fs from 'node:fs/promises';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const [payloadFile, xlsxPath, previewDir] = process.argv.slice(2);
const data = JSON.parse(await fs.readFile(payloadFile, 'utf8'));
const wb = Workbook.create();
const fx = wb.worksheets.add('FX_Tax_Rates');
const rev = wb.worksheets.add('Rev_Ledger');
const hr = wb.worksheets.add('HR_Cost');
const navy = '#173B63';
const light = '#EAF1F7';
const border = '#CFD8E2';
const header = {fill: navy, font: {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'}, horizontalAlignment: 'center', verticalAlignment: 'center', wrapText: true};
const body = {font: {name: 'Arial', size: 10, color: '#25364A'}, verticalAlignment: 'center'};
function table(sheet, range, values) {
  const r = sheet.getRange(range); r.values = values; r.format = body;
}
function styleHeader(sheet, range) { sheet.getRange(range).format = header; }
function styleUsed(sheet, range) {
  sheet.showGridLines = false;
  sheet.getRange(range).format = body;
  sheet.getRange(range).format.borders = {insideHorizontal: {style: 'thin', color: border}};
}

fx.getRange('A1:C4').values = [['Currency','USD Rate','Employer Tax Rate'], ...Object.entries(data.fx).map(([currency, rates])=>[currency,rates[0],rates[1]])];
fx.getRange('A1:C1').format = header;
fx.getRange('A2:A4').format.font = {name:'Arial',size:10,color:'#17603F'};
fx.getRange('B2:C4').format.numberFormat = '0.00%';
fx.getRange('B2:B4').format.numberFormat = '0.0000';
fx.getRange('A1:C4').format.columnWidth = 21;
fx.showGridLines = false;
fx.freezePanes.freezeRows(1);

const revHeaders = ['Quarter','Document ID','Currency','Gross Amount','Credit Adjustment','USD Rate','Net Revenue USD','Review Note'];
rev.getRange('A1:H1').values = [revHeaders];
rev.getRange('A2:H37').values = Array.from({length:36},()=>Array(8).fill(''));
rev.getRange('F2').formulas = [['=IFERROR(VLOOKUP(C2,FX_Tax_Rates!$A$2:$C$4,2,FALSE),0)']];
rev.getRange('F2:F37').fillDown();
rev.getRange('G2').formulas = [['=(D2-E2)*F2']];
rev.getRange('G2:G37').fillDown();
rev.getRange('J1:K1').values = [['Quarter','Net revenue USD']];
rev.getRange('J2:J5').values = [['Q1'],['Q2'],['Q3'],['Q4']];
rev.getRange('K2').formulas = [['=SUMIF($A$2:$A$37,J2,$G$2:$G$37)']];rev.getRange('K2:K5').fillDown();
rev.getRange('J7:J8').values = [['Credit memos USD'],['Annual net revenue USD']];
rev.getRange('K7:K8').formulas = [['=SUMPRODUCT($E$2:$E$37,$F$2:$F$37)'],['=SUM(K2:K5)']];
styleUsed(rev,'A1:H37');styleUsed(rev,'J1:K8');
styleHeader(rev,'A1:H1');styleHeader(rev,'J1:K1');styleHeader(rev,'J7:J8');
rev.getRange('D2:E37').format.numberFormat = '$#,##0.00;[Red]($#,##0.00)';rev.getRange('F2:F37').format.numberFormat='0.0000';rev.getRange('G2:G37').format.numberFormat='$#,##0.00;[Red]($#,##0.00)';
rev.getRange('K2:K8').format.numberFormat = '$#,##0.00;[Red]($#,##0.00)';
rev.getRange('A1:H37').format.columnWidth = 18;rev.getRange('B1:B37').format.columnWidth = 22;rev.getRange('H1:H37').format.columnWidth = 25;
rev.freezePanes.freezeRows(1);

const hrHeaders=['Quarter','Employee ID','Department','Currency','Base Pay','Overtime Hours','Overtime Multiplier','Allowance','USD Rate','Employer Tax Rate','Total Cost USD','Review Note'];
hr.getRange('A1:L1').values=[hrHeaders];hr.getRange('A2:L37').values=Array.from({length:36},()=>Array(12).fill(''));
hr.getRange('I2').formulas=[['=IFERROR(VLOOKUP(D2,FX_Tax_Rates!$A$2:$C$4,2,FALSE),0)']];hr.getRange('I2:I37').fillDown();
hr.getRange('J2').formulas=[['=IFERROR(VLOOKUP(D2,FX_Tax_Rates!$A$2:$C$4,3,FALSE),0)']];hr.getRange('J2:J37').fillDown();
hr.getRange('K2').formulas=[['=(E2+E2/173*F2*G2+H2)*I2*(1+J2)']];hr.getRange('K2:K37').fillDown();
hr.getRange('N1:O1').values=[['Quarter','Total cost USD']];hr.getRange('N2:N5').values=[['Q1'],['Q2'],['Q3'],['Q4']];
hr.getRange('O2').formulas=[['=SUMIF($A$2:$A$37,N2,$K$2:$K$37)']];hr.getRange('O2:O5').fillDown();
hr.getRange('N7:N8').values=[['Allowances USD'],['Annual people cost USD']];hr.getRange('O7:O8').formulas=[['=SUMIF($B$2:$B$37,"ALW-*",$K$2:$K$37)'],['=SUM(O2:O5)']];
hr.getRange('Q1:R1').values=[['Department','Annual Budget USD']];
hr.getRange('Q2:R5').values=Object.entries(data.hr_budgets);
styleUsed(hr,'A1:L37');styleUsed(hr,'N1:O8');styleUsed(hr,'Q1:R5');
styleHeader(hr,'A1:L1');styleHeader(hr,'N1:O1');styleHeader(hr,'N7:N8');styleHeader(hr,'Q1:R1');
hr.getRange('E2:E37').format.numberFormat='$#,##0.00';hr.getRange('H2:H37').format.numberFormat='$#,##0.00';hr.getRange('I2:I37').format.numberFormat='0.0000';hr.getRange('J2:J37').format.numberFormat='0.00%';hr.getRange('K2:K37').format.numberFormat='$#,##0.00';hr.getRange('O2:O8').format.numberFormat='$#,##0.00';hr.getRange('R2:R5').format.numberFormat='$#,##0.00';
hr.getRange('A1:L37').format.columnWidth=17;hr.getRange('B1:B37').format.columnWidth=20;hr.getRange('C1:C37').format.columnWidth=19;hr.getRange('L1:L37').format.columnWidth=22;hr.getRange('N1:O8').format.columnWidth=22;hr.getRange('Q1:R5').format.columnWidth=23;
hr.getRange('A2:K37').conditionalFormats.addCustom('SUMIF($C$2:$C$37,$C2,$K$2:$K$37)>VLOOKUP($C2,$Q$2:$R$5,2,FALSE)',{fill:'#FCE4D6',font:{color:'#8A2D22',bold:true}});
hr.freezePanes.freezeRows(1);

wb.recalculate();
await fs.mkdir(previewDir,{recursive:true});
for (const sheetName of ['FX_Tax_Rates','Rev_Ledger','HR_Cost']) {
  const preview=await wb.render({sheetName,autoCrop:'all',scale:1,format:'png'});
  await fs.writeFile(`${previewDir}/${sheetName}.png`,new Uint8Array(await preview.arrayBuffer()));
}
const inspection=await wb.inspect({kind:'workbook,sheet,formula',maxChars:3500,tableMaxRows:8,tableMaxCols:16,options:{maxResults:60}});
await fs.writeFile(`${previewDir}/inspect.ndjson`,inspection.ndjson,'utf8');
const output=await SpreadsheetFile.exportXlsx(wb);await output.save(xlsxPath);
console.log(JSON.stringify({xlsxPath,previewDir,inspectionChars:inspection.ndjson.length}));
