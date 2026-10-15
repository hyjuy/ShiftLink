var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
// First entry is the existing account-login design; keep the old landing as an archive.
(function () {
    return __awaiter(this, void 0, void 0, function* () {
        const page = figma.root.children.find(p => p.name === '02. 2차 시안');
        if (!page)
            throw Error('2차 시안 페이지가 없습니다.');
        yield figma.setCurrentPageAsync(page);
        const landing = yield figma.getNodeByIdAsync('115:309'), account = yield figma.getNodeByIdAsync('115:341');
        if (!landing || !account || account.type !== 'FRAME')
            throw Error('로그인 화면 확인 필요');
        let redirected = 0;
        for (const n of page.findAll(n => 'reactions' in n)) {
            const reactions = n.reactions.map(r => (Object.assign(Object.assign({}, r), { actions: (r.actions || []).map(a => a.type === 'NODE' && a.destinationId === landing.id ? Object.assign(Object.assign({}, a), { destinationId: account.id }) : a) })));
            if (JSON.stringify(reactions) !== JSON.stringify(n.reactions)) {
                yield n.setReactionsAsync(reactions);
                redirected++;
            }
        }
        for (const n of account.findAll(n => /^Button/.test(n.name))) {
            const label = n.findAll(t => t.type === 'TEXT').map(t => t.characters).join(' ').trim();
            if (/^(뒤로\s?가기|이전)$/.test(label))
                n.visible = false;
        }
        landing.visible = false;
        account.visible = true;
        page.flowStartingPoints = [{ nodeId: account.id, name: '시작 · 계정 로그인' }, ...page.flowStartingPoints.filter(p => p.nodeId !== landing.id && p.nodeId !== account.id)];
        page.selection = [account];
        figma.viewport.scrollAndZoomIntoView([account]);
        figma.showUI('<pre id="result"></pre><script>onmessage=e=>result.textContent=JSON.stringify(e.data.pluginMessage,null,2);</script>', { width: 480, height: 240 });
        figma.ui.postMessage({ status: '첫 화면 변경 완료', start: page.flowStartingPoints[0], landingVisible: landing.visible, redirected });
    });
})().catch(e => figma.closePlugin(String(e)));
