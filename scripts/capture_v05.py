"""Actual permissions controls and live pinned Ruflo bridge; no provider accounts."""
import asyncio,os,tempfile
from pathlib import Path
from forge.tui import ForgeApp
ROOT=Path(__file__).resolve().parents[1];OUTPUT=ROOT/'docs/screenshots'
async def main():
 with tempfile.TemporaryDirectory(prefix='forge-v05-') as tmp:
  root=Path(tmp);project=root/'project';project.mkdir();reference=root/'reference';reference.mkdir();(reference/'readme.txt').write_text('Approved reference fixture')
  os.environ['FORGE_CONFIG_HOME']=str(root/'trusted-config')
  app=ForgeApp(project)
  try:
   async with app.run_test(size=(160,50)) as pilot:
    await pilot.pause(.3);app.set_palette('ocean')
    from textual.widgets import Select,TextArea
    app.ui('#sandbox-enabled',Select).value=True;app.ui('#sandbox-grants',TextArea).load_text(str(reference));await pilot.pause()
    app.ui('#setup-scroll').scroll_to_widget(app.ui('#sandbox-section'),animate=False,top=True);await pilot.pause();app.save_screenshot('31-folder-permissions.svg',str(OUTPUT))
    app.setup_action('setup-sandbox-save');await pilot.pause();app.save_screenshot('32-permission-review.svg',str(OUTPUT));await pilot.press('y');await pilot.pause()
    assert app.runtime.sandbox.policy['enabled']
    app.runtime.store.remember('Run parser tests before review','decision','user',True)
    app.ruflo.enable()
    for _ in range(600):
     if app.ruflo.connected:break
     await pilot.pause(.1)
    assert app.ruflo.connected,app.ruflo.state
    app.ruflo.request('sync')
    for _ in range(1500):
     if not app.ruflo.busy:break
     await pilot.pause(.1)
    assert not app.ruflo.busy,app.ruflo.state
    app.ui('#setup-scroll').scroll_to_widget(app.ui('#ruflo-section'),animate=False,top=True);await pilot.pause();app.save_screenshot('33-ruflo-connected.svg',str(OUTPUT))
    app.execute('/ruflo search parser tests')
    for _ in range(1500):
     if not app.ruflo.busy:break
     await pilot.pause(.1)
    await pilot.pause(.3);app.save_screenshot('34-ruflo-retrieval.svg',str(OUTPUT))
    app.action_tab('setup');await pilot.resize_terminal(100,36);app.ui('#setup-scroll').scroll_to_widget(app.ui('#setup-sandbox-save'),animate=False,top=True);await pilot.pause();app.save_screenshot('35-compact-permissions.svg',str(OUTPUT))
  finally:app.ruflo.close();app.ollama.close();app.planner.close();app.voice.close();app.runtime.close()
 print('Captured five actual v0.5 states with a real Ruflo connection and memory retrieval.')
asyncio.run(main())
