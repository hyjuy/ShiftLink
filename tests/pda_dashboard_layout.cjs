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
    await page.locator('.ls-detail').waitFor();
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
      assert.ok(await page.locator('#globalHeader').isVisible());   // 대상 선택은 홈과 같은 상단 메뉴
      await page.screenshot({path:`output/pda-layout-targets-${width}.png`});
      await page.evaluate(() => {S.lossDetail=false;show('home');});
      await page.locator('#toDashboard').click();
      for (const selector of ['#anGap .an-flow>div']) {
        const styles=await page.locator(selector).evaluateAll(els=>els.map(el=>({align:getComputedStyle(el).textAlign,border:getComputedStyle(el).borderLeftWidth})));
        assert.ok(styles.every(s=>s.align==='center'),selector);
        assert.ok(styles.slice(1).every(s=>s.border==='1px'),selector);
      }
      // 정지 손실: 요약 카드 → 설비별 상세(탭·표) → 이전
      assert.ok(await page.locator('.ls-card').first().isVisible());
      await page.locator('.ls-detail').click();
      assert.ok(await page.locator('.ld-tabs').isVisible());
      assert.ok(await page.locator('.ld-row').count()>0);
      await page.locator('.ld-back').click();
      assert.ok(await page.locator('.ls-detail').isVisible());
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
      await page.screenshot({path:`output/pda-layout-dashboard-${width}.png`});
    }
    assert.deepEqual(errors,[]);
    console.log('PASS: home logo alignment, login/title, centered separated metrics, loss summary/detail and responsive layout');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
