"""Capture real Textual Ollama UI with an explicitly labeled local HTTP fixture."""
import asyncio
import importlib.util
import os
import sys
from pathlib import Path
import tempfile
from forge.tui import ForgeApp
from textual.widgets import Input
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'docs/screenshots'

async def capture():
    spec=importlib.util.spec_from_file_location('ollama_fixture',ROOT/'tests/test_ollama.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    fixture=module.ollama_server.__wrapped__(); host,state=next(fixture)
    os.environ['OLLAMA_HOST']=host
    state['delay']=.35
    with tempfile.TemporaryDirectory(prefix='forge-model-ui-') as project:
        app=ForgeApp(project)
        def save(name):
            if '--compact-only' not in sys.argv or name == '15-ollama-compact.svg':
                app.save_screenshot(name,str(OUTPUT))
        try:
            async with app.run_test(size=(160,50)) as pilot:
                await pilot.pause(.3)
                app.ui('#model-tag',Input).value='fixture:local'
                app.refresh_models()
                save('10-ollama-hub.svg')
                app.model_action('model-pull')
                await pilot.pause()
                save('11-ollama-confirm.svg')
                await pilot.press('y')
                await pilot.pause(.6)
                save('12-ollama-progress.svg')
                await pilot.pause(2.2)
                app.refresh_models()
                assert app.ollama.state == 'Ready', app.ollama.state
                app.model_action('model-tutorial-done')
                await pilot.pause()
                save('13-ollama-ready.svg')
                app.ui('#models-scroll').scroll_end(animate=False)
                await pilot.pause()
                save('14-ollama-setup.svg')
                app.execute('/tutorial')
                app.refresh_models()
                await pilot.resize_terminal(100,36)
                app.ui('#models-scroll').scroll_home(animate=False)
                await pilot.pause()
                save('15-ollama-compact.svg')
        finally:
            app.ollama.close(); app.runtime.close()
    fixture.close()
    print('Captured six real TUI states using a labeled HTTP fixture. No real Ollama model used.')

if __name__=='__main__': asyncio.run(capture())
