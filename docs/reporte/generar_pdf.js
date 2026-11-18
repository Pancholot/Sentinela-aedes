// Genera docs/Reporte_Tecnico_Sentinela_Aedes.pdf a partir de reporte_tecnico.html.
// Uso:  node docs/reporte/generar_pdf.js        (requiere: npm i playwright && npx playwright install chromium)
// Alternativa sin Node: abrir reporte_tecnico.html en Chrome → Imprimir → Guardar como PDF
// (tamaño Carta, márgenes predeterminados, activar "Gráficos de fondo").
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const html = path.resolve(__dirname, 'reporte_tecnico.html');
  const out = path.resolve(__dirname, '..', 'Reporte_Tecnico_Sentinela_Aedes.pdf');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + html, { waitUntil: 'networkidle' });
  await page.pdf({
    path: out,
    format: 'Letter',
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate:
      '<div style="width:100%;font-size:7.5pt;color:#6B7B7E;padding:0 0.6in;display:flex;justify-content:space-between;font-family:Arial,sans-serif">' +
      '<span>Sentinela Aedes · Prototipo Alfa · Reporte técnico</span>' +
      '<span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>',
  });
  await browser.close();
  console.log('PDF generado:', out);
})();
