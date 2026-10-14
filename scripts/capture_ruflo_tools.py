"""Capture actual pinned Ruflo UI states; no fake tool results or credential input."""
import asyncio,os,tempfile,shutil
from pathlib import Path
from forge.tui import ForgeApp
from textual.widgets import Select,TextArea
OUT=Path(__file__).resolve().parents[1]/'docs/screenshots'
async def main():
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='forge-tools-ui-') as tmp:
        root=Path(tmp);project=root/'project';project.mkdir();os.environ['FORGE_CONFIG_HOME']=str(root/'trusted')
        app=ForgeApp(project)
        try:
            grants=[]
            for p in (Path(os.environ['FORGE_RUFLO_BIN']).resolve().parents[3],Path(shutil.which('node')).resolve().parent.parent):
                if not p.is_relative_to(Path('/usr')) and p!=Path('/') and str(p) not in grants:grants.append(str(p))
            app.runtime.sandbox.save({'enabled':True,'read_only':grants,'network':False})
            async with app.run_test(size=(160,50)) as pilot:
                await pilot.pause();app.action_tab('setup');app.setup_action('setup-ruflo-tools');await pilot.pause();await pilot.press('y')
                for _ in range(600):
                    await pilot.pause(.05)
                    if app.tool_gateway.catalog and not app.tool_gateway.busy:break
                assert len(app.tool_gateway.catalog)>300,app.tool_gateway.state
                app.pump();await pilot.pause();app.ui('#ruflo-tool-name',Select).value='memory_stats';await pilot.pause()
                scroll=app.ui('#setup-scroll');scroll.scroll_to_widget(app.ui('#ruflo-tools-section'),animate=False,top=True);await pilot.pause()
                app.save_screenshot('40-ruflo-tools-catalog.svg',str(OUT))
                app.setup_action('setup-ruflo-tool-review')
                for _ in range(600):
                    await pilot.pause(.05)
                    if app.screen is not app.workspace_screen:break
                assert app.screen is not app.workspace_screen,app.tool_gateway.state
                await pilot.pause(.5)
                app.save_screenshot('41-ruflo-tools-review.svg',str(OUT));await pilot.press('y')
                for _ in range(600):
                    await pilot.pause(.05)
                    if app.ui('#ruflo-tool-result',TextArea).text:break
                assert 'memory_stats' in app.ui('#ruflo-tool-result',TextArea).text
                scroll.scroll_to_widget(app.ui('#setup-ruflo-tool-review'),animate=False,top=True);await pilot.pause();app.save_screenshot('42-ruflo-tools-result.svg',str(OUT))
                await pilot.resize_terminal(100,36);scroll.scroll_to_widget(app.ui('#ruflo-tools-section'),animate=False,top=True);await pilot.pause();app.save_screenshot('43-ruflo-tools-compact.svg',str(OUT))
        finally:
            app.tool_gateway.close();app.ruflo.close();app.ollama.close();app.planner.close();app.voice.close();app.runtime.close()
    print('Captured four actual pinned-Ruflo UI states.')
asyncio.run(main())
