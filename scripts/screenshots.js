// Erzeugt die Bilder für die README aus der Demo (docs/screenshots/*.png).
// Start: python3 scripts/build_demo.py && node scripts/screenshots.js   (braucht Playwright mit Chromium)
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const demo = "file://" + path.join(root, "demo/zigbee-devices-manager-demo.html");
const out = path.join(root, "docs/screenshots");

async function open(browser, colorScheme = "light") {
  const page = await browser.newPage({ viewport: { width: 1280, height: 820 }, colorScheme });
  await page.goto(demo);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForSelector("#tab-devices table");
  // Typ „Lampe“ für die Lampen, damit Namensvorschläge erscheinen; Demo-Hinweis ausblenden
  for (const n of ["0x680ae2fffe1a0003", "Wohnzimmer Stehlampe"]) await page.locator("tr", { hasText: n }).first().locator(".sel").check();
  const lp = await page.locator("#bType option", { hasText: "Lampe" }).first().getAttribute("value");
  await page.locator("#bType").selectOption(lp);
  await page.locator("#bAssign").click();
  await clearSelection(page);
  await page.evaluate(() => { document.querySelector("#banner").innerHTML = ""; });
  return page;
}

// Auswahl aufheben – jeder Klick zeichnet die Liste neu, daher immer wieder frisch suchen
const clearSelection = page => page.evaluate(() => { for (let i = 0; i < 100; i++) { const x = document.querySelector(".sel:checked"); if (!x) break; x.click(); } });

const shot = async (page, name) => {
  await page.evaluate(() => { const c = document.querySelector("#tab-devices .card"); if (c) c.scrollLeft = 0; });
  await page.screenshot({ path: path.join(out, name) });
};

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();

  // 1. Geräteliste mit Filtern und Vorschlägen
  let page = await open(browser);
  await shot(page, "geraete.png");

  // 2. Vorschau beim Umbenennen (Entity-IDs, Verweise)
  await page.locator("tr", { hasText: "0x680ae2fffe1a0003" }).first().locator(".apply").click();
  await page.waitForSelector("dialog[open] #yes");
  await shot(page, "umbenennen.png");
  await page.locator("dialog[open] #no").click();
  await clearSelection(page);

  // 3. Spots neu zuordnen (Assistent mit Blinken)
  for (const n of ["WZ_LP_05", "WZ_LP_02", "Wohnzimmer Stehlampe"]) await page.locator("tr", { hasText: n }).first().locator(".sel").check();
  await page.locator("#bSwap").click();
  await page.waitForSelector("dialog[open] #pickName");
  await page.waitForTimeout(500);
  await page.locator("#pickName").selectOption("WZ_LP_05");
  await page.waitForTimeout(200);
  await shot(page, "neu-zuordnen.png");
  await page.locator("dialog[open] #cancel").click();
  await page.close();

  // 4. Verweise prüfen (Suchfeld, aus Szenen entfernen)
  page = await open(browser);
  await page.locator("#checkRefs").click();
  await page.waitForSelector("dialog[open] #go");
  await page.locator("dialog[open] .dropScene").check();
  const inp = page.locator("dialog[open] .pick input").first();
  await inp.click();
  await inp.fill("wz lp");
  await page.waitForTimeout(200);
  await shot(page, "verweise.png");
  await page.close();

  // 5. Netzwerk (Baum mit Verbindungsqualität, Details)
  page = await open(browser);
  await page.locator('nav button[data-tab="network"]').click();
  await page.waitForTimeout(800);
  const router = page.locator("#tab-network .tn.router").nth(1);
  if (await router.count()) await router.click();
  await page.waitForTimeout(300);
  await shot(page, "netzwerk.png");
  await page.close();

  // 6. Namensschema
  page = await open(browser);
  await page.locator('nav button[data-tab="scheme"]').click();
  await page.waitForTimeout(300);
  await shot(page, "namensschema.png");
  await page.close();

  // 7. Geräteliste im dunklen Design
  page = await open(browser, "dark");
  await shot(page, "geraete-dunkel.png");
  await page.close();

  await browser.close();
  console.log("Bilder in", out);
})();
