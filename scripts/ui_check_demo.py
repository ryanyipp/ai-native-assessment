import asyncio,httpx,re
from playwright.async_api import async_playwright
UI='http://localhost:5283';API='http://127.0.0.1:8013';R=[]
def ck(n,ok,d=''):
    R.append(bool(ok));print('PASS' if ok else 'FAIL',n,str(d)[:130],flush=True)
async def tab(p,n):
    await p.get_by_role('tab',name=re.compile(n)).first.click() if await p.get_by_role('tab',name=re.compile(n)).count() else await p.get_by_role('button',name=re.compile('^'+n)).first.click()
async def m():
  async with async_playwright() as w:
    b=await w.chromium.launch();c=await b.new_context(viewport={'width':1600,'height':1000},accept_downloads=True);p=await c.new_page()
    errs=[];p.on('pageerror',lambda e:errs.append(str(e)))
    await p.goto(UI+'/workspace');pn=p.get_by_role('complementary',name='New review run');await pn.wait_for()
    warn=pn.get_by_text('No requirements: suspected defects')
    ck('warning when empty',await warn.count()==1)
    reqs='R5. A publish date in the past must be rejected: "Past" means before.\nR4. A creator can schedule a post.'
    await pn.get_by_label('Requirements (optional)').fill(reqs);ck('warning gone when filled',await warn.count()==0)
    await pn.get_by_label('Target website').fill('http://localhost:5174/');await pn.get_by_label('Review goal').fill('Explore the dashboard forms')
    await p.get_by_role('button',name='Start live run').click();await p.wait_for_url(re.compile('run=run_'),timeout=20000)
    rid=re.search(r'run=(run_\w+)',p.url).group(1)
    for _ in range(240):
        d=httpx.get(f'{API}/api/runs/{rid}').json()
        if d['run']['status'] not in('queued','running'):break
        await asyncio.sleep(.5)
    ck('requirements saved unchanged',d['run']['requirements']==reqs.split('\n'),d['run']['requirements']);ck('scripted run labelled',d['run']['provenance']['mocked_model'] and not d['run']['provenance']['live'])
    # inconclusive run
    await p.goto(UI+'/workspace?run=run_43de5b592245');await p.get_by_role('button',name='Report').wait_for()
    await p.get_by_text('Findings',exact=False).first.click();card=p.locator('article[aria-label^="Finding"]').first;await card.wait_for()
    t=await card.inner_text()
    ck('finding: exact inconclusive wording','Inconclusive: no supplied requirement defines the expected behaviour. Browser replay was not attempted.' in t)
    ck('finding: reviewed by, not verified by','reviewed by verifier' in t and 'verified by' not in t)
    ck('finding: tester-proposed expectation','Tester-proposed expectation' in t);ck('finding: assessment heading','verification assessment' in t.lower() and 'independent' not in t.lower())
    ck('finding: assessment label, no replay claim','Assessment' in t and 'Replay 1' not in t and 'browser replay not attempted' in t, t[-200:])
    link=card.get_by_role('button',name=re.compile('Show the test case on the map'));ck('finding has map link',await link.count()==1)
    await link.click();await p.wait_for_timeout(600)
    body=await p.locator('body').inner_text();ck('map link opens test evidence','Input test case' in body)
    ck('evidence tester-proposed label','Tester-proposed expectation' in body)
    inp=p.get_by_label('Go to step');ck('step box present',await inp.count()==1);s0=await inp.input_value()
    await inp.fill('1');await inp.press('Enter');await p.wait_for_timeout(500);ck('step jump to 1',await p.get_by_label('Go to step').input_value()=='1',s0)
    await p.get_by_label('Go to step').fill('9999');await p.get_by_label('Go to step').press('Enter');await p.wait_for_timeout(300);ck('bad step restored',await p.get_by_label('Go to step').input_value()=='1')
    ac=p.locator('summary',has_text=re.compile('^(Action|Last browser action)$'));ck('action closed by default',await ac.count()>=1 and not await ac.first.evaluate('e=>e.parentElement.open'))
    await ac.first.click();ck('action expands',await ac.first.evaluate('e=>e.parentElement.open'))
    # confirmed run
    await p.goto(UI+'/workspace?run=run_9697459edc50');await p.get_by_role('button',name='Report').wait_for()
    await p.get_by_text('Findings',exact=False).first.click();card=p.locator('article[aria-label^="Finding"]').first;await card.wait_for();t=await card.inner_text()
    ck('confirmed: verified by','verified by verifier' in t);ck('confirmed: Verification heading','verification' in t.lower() and 'assessment' not in t.lower() and 'independent' not in t.lower())
    ck('confirmed: two replays and assertion','Replay 1' in t and 'Replay 2' in t and 'Assertion failed' in t and 'validation_message_present' in t and 'evaluated by code' in t)
    th=card.locator('img').first;ck('thumb present',await th.count()==1 and await th.evaluate('e=>e.complete&&e.naturalWidth>0'))
    async with c.expect_page() as np:
        await th.click()
    q=await np.value;await q.wait_for_load_state();ck('finding thumbnail opens screenshot',q.url.count('/api/artifacts/')==1,q.url);await q.close()
    await card.get_by_role('button',name=re.compile('Show this replay on the map')).first.click();await p.wait_for_timeout(600)
    big=p.get_by_role('button',name=re.compile('Enlarge screenshot'));ck('replay reaches evidence preview',await big.count()>=1)
    await big.first.click();await p.wait_for_timeout(400);ck('preview dialog opens',await p.locator('[role=dialog] img').count()>=1)
    await p.keyboard.press('Escape');await p.wait_for_timeout(200)
    ck('report html',httpx.get(f'{API}/api/runs/run_9697459edc50/report').text.count('fresh browser replay')>=1)
    async with c.expect_page() as np:
        await p.get_by_role('link',name='Report').first.click() if await p.get_by_role('link',name='Report').count() else await p.get_by_role('button',name='Report').click()
    q=await np.value;await q.wait_for_load_state();ht=await q.locator('body').inner_text();ck('report opens in browser','Assertion chosen by a separate verifier agent' in ht,q.url);await q.close()
    async with p.expect_download(timeout=8000) as dl:
        await (p.get_by_role('link',name='Markdown').first if await p.get_by_role('link',name='Markdown').count() else p.get_by_role('button',name='Markdown')).click()
    v=await dl.value;ck('markdown downloads',v.suggested_filename.endswith('.md'),v.suggested_filename)
    ck('no page errors',not errs,errs[:2]);await b.close()
  print(sum(R),'/',len(R))
asyncio.run(m())
