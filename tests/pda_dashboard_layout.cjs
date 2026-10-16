const assert = require('node:assert/strict');
const {mkdirSync} = require('node:fs');
const {chromium} = require('playwright');
(async () => {
  mkdirSync('output', {recursive:true});
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.PDA_URL || 'http://127.0.0.1:8765/pda.html');
    await page.locator('#s-account.on').waitFor();
    assert.equal(await page.getByRole('heading', {name:'계정 로그인', exact:true}).count(), 0);
    await page.evaluate(() => {S.operator={name:'레이아웃 검증',id:'local-review'};show('home');});
    await page.locator('#toDashboard').click();
    await page.locator('.g-lost[role=button]').waitFor();
    for (const width of [1280,375]) {
      await page.setViewportSize({width,height:800});
      await page.evaluate(() => show('home'));
      const anchor = await page.locator('#globalHeader>.brand svg').boundingBox();
      for (const screen of ['manual','reportSelect','reportWrite','scan','faceSetup','face','dashboard']) {
        await page.evaluate(screen => show(screen),screen);
        const icon = await page.locator('#navigationBack svg').boundingBox();
        assert.ok(Math.abs(icon.x+icon.width/2-anchor.x-anchor.width/2)<1,`${width} ${screen}: logo x`);
        assert.ok(Math.abs(icon.y+icon.height/2-anchor.y-anchor.height/2)<1,`${width} ${screen}: logo y ${JSON.stringify({icon,anchor})}`);
      }
      await page.evaluate(() => show('reportSelect'));
      assert.equal(await page.locator('#s-reportSelect h1').innerText(),'ShiftLink');
      await page.screenshot({path:`output/pda-layout-targets-${width}.png`});
      await page.evaluate(() => {S.lossEquipmentOpen=false;show('home');});
      await page.locator('#toDashboard').click();
      assert.deepEqual(await page.locator('.loss-sum th').allTextContents(),['계획','생산','손실률']);
      for (const selector of ['.loss-sum th','.loss-sum td','#anGap .an-flow>div']) {
        const styles=await page.locator(selector).evaluateAll(els=>els.map(el=>({align:getComputedStyle(el).textAlign,border:getComputedStyle(el).borderLeftWidth})));
        assert.ok(styles.every(s=>s.align==='center'),selector);
        assert.ok(styles.slice(1).every(s=>s.border==='1px'),selector);
      }
      const toggle = page.locator('.g-lost[role=button]');
      assert.ok(await page.locator('#anLossEquipment').isHidden());
      await toggle.click();
      assert.equal(await toggle.getAttribute('aria-expanded'),'true');
      assert.ok(await page.locator('#anLossEquipment').isVisible());
      const expected = await page.evaluate(()=>S.an.loss.map(r=>r.incidents.length+'회 · 총 '+r.stop_min+'분 정지'));
      assert.deepEqual(await page.locator('#anLossEquipment .loss-row .s').allTextContents(),expected);
      await page.locator('#headerHome').click();await page.locator('#toDashboard').click();
      assert.equal(await toggle.getAttribute('aria-expanded'),'true');
      await toggle.focus();await page.keyboard.press('Enter');
      assert.ok(await page.locator('#anLossEquipment').isHidden());
      await toggle.focus();await page.keyboard.press('Space');
      assert.ok(await page.locator('#anLossEquipment').isVisible());
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
      await page.screenshot({path:`output/pda-layout-dashboard-${width}.png`});
    }
    assert.deepEqual(errors,[]);
    console.log('PASS: home logo alignment, login/title, centered separated metrics, loss toggle and refresh persistence, stop counts/time, keyboard and responsive layout');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
