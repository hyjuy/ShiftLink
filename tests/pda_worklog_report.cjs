const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 800}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.resolve(__dirname, '../docs/design/pda_ui/worklog-report.html')).href);

    // A normal shift requires no narrative, cause, or result fields.
    assert.equal(await page.locator('[contenteditable]').count(), 0);
    assert.equal(await page.locator('.record').count(), 0);
    await page.locator('#close-day').click();
    assert.match(await page.locator('#status').textContent(), /마감 가능.*추가 입력 없음/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 1280);
    assert.equal(await page.evaluate(() => document.documentElement.scrollHeight), 800);

    // An added record requires only equipment and the situation/action description.
    await page.locator('#add').click();
    await page.locator('#close-day').click();
    assert.match(await page.locator('#status').textContent(), /대상 설비, 상황·조치/);
    await page.locator('[data-eq="HPU-01"]').check();
    await page.locator('[data-eq="CL-01"]').check();
    await page.locator('[data-key="story"]').fill('유압 유닛과 냉각기 연계 점검 실시');
    await page.locator('#close-day').click();
    assert.match(await page.locator('#status').textContent(), /마감 가능/);

    // Optional causes and PMS data preserve the original narrative and equipment.
    await page.locator('[data-action="cause"]').click();
    await page.locator('[data-key="note"]').fill('오염 확인 후 청소');
    await page.locator('[data-action="cause"]').click();
    assert.equal(await page.locator('.cause-row').count(), 2);
    assert.equal(await page.locator('[data-key="story"]').innerText(), '유압 유닛과 냉각기 연계 점검 실시');
    await page.locator('[data-action="pms"]').click();
    await page.locator('[data-key="pms"]').fill('PMS-DEMO-01');
    await page.locator('[data-action="result"]').click();
    await page.locator('[data-key="result"]').fill('다음 조 상태 확인');
    await page.locator('[data-key="candidate"]').check();

    await page.locator('#add').click();
    assert.equal(await page.locator('.record').count(), 2);
    assert.equal(await page.locator('[data-key="pms"]').innerText(), 'PMS-DEMO-01');
    assert.ok(await page.locator('[data-key="candidate"]').first().isChecked());

    // Replacing user content requires confirmation; examples remain explicitly synthetic.
    page.once('dialog', dialog => dialog.accept());
    await page.locator('#example').click();
    assert.equal(await page.locator('.record').count(), 1);
    assert.equal(await page.locator('.cause-row').count(), 2);
    assert.equal(await page.locator('[data-key="certainty"]').nth(1).inputValue(), '추정');
    assert.match(await page.locator('#mes-source').textContent(), /가상 작성 예시/);
    await page.locator('#close-day').click();
    assert.match(await page.locator('#status').textContent(), /실제 제출·저장은 수행하지 않습니다/);

    // Print output is renderable and excludes the surrounding PDA controls.
    await page.emulateMedia({media: 'print'});
    assert.equal(await page.locator('.toolbar').isVisible(), false);
    assert.equal(await page.locator('.footer').isVisible(), false);
    const pdf = await page.pdf({preferCSSPageSize: true, printBackground: true});
    assert.ok(pdf.subarray(0, 5).toString().startsWith('%PDF-'));
    await page.emulateMedia({media: 'screen'});
    await page.locator('#data').click();
    assert.ok(await page.locator('#data-dialog').isVisible());
    await page.locator('#data-close').click();
    assert.deepEqual(errors, []);
    console.log('PASS: 1280x800 report, zero-input normal shift, required fields, multiple equipment/causes, optional PMS/handover/candidate, print, zero browser errors.');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
