"""Actual TUI captures. Preview plan is labeled; no private credentials are entered.

Use --speech-record PATH to show a previously verified public-sample transcript.
The record's source and microphone_tested=false remain explicit in validation.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile
from forge.tui import ForgeApp
from forge.settings import PALETTES
from forge.profiles import Profile
from textual.widgets import Select,TextArea
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'docs/screenshots'

async def capture(speech_record=None):
    with tempfile.TemporaryDirectory(prefix='forge-v04-preview-') as folder:
        os.environ['FORGE_CONFIG_HOME']=folder+'/user-preferences'
        app=ForgeApp(folder)
        try:
            async with app.run_test(size=(160,50)) as pilot:
                await pilot.pause(.3)
                app.save_screenshot('16-setup.svg',str(OUTPUT))
                app.ui('#setup-scroll').scroll_to_widget(app.ui('#key-provider'),animate=False,top=True)
                await pilot.pause()
                app.save_screenshot('17-provider-setup.svg',str(OUTPUT))
                for index,name in enumerate(PALETTES,18):
                    app.set_palette(name)
                    app.action_tab('workbench')
                    await pilot.pause()
                    app.save_screenshot(f'{index}-{name}.svg',str(OUTPUT))
                app.set_palette('forest')
                app.execute('/plan UI preview: add bounded parser tests')
                draft={'tasks':[{'title':'UI preview: add parser tests','instructions':'Add bounded tests. Report checks and changed files.','risk':'routine','depends_on':[]},{'title':'UI preview: review edge cases','instructions':'Inspect tests and report remaining risks.','risk':'high','depends_on':[0]}]}
                app.ui('#planner-draft',TextArea).load_text(json.dumps(draft,indent=2))
                app.planner.state='UI fixture draft — no Ollama model was called'
                app.refresh_state()
                await pilot.pause()
                app.save_screenshot('26-planner.svg',str(OUTPUT))
                app.runtime.profiles['preview-coder']=Profile('preview-coder','UI fixture coder',('/bin/sh',),('/bin/sh','-c','printf UI_FIXTURE'),'free')
                app.setup_action('plan-queue')
                await pilot.pause()
                app.save_screenshot('27-plan-review.svg',str(OUTPUT))
                await pilot.press('n')
                app.action_tab('setup')
                app.ui('#setup-scroll').scroll_end(animate=False)
                if speech_record:
                    record=json.loads(Path(speech_record).read_text())
                    app.voice.cache=Path(speech_record).parent/'speech-models'
                    app.voice.prepare('tiny.en')
                    for _ in range(120):
                        if not app.voice.busy:break
                        await pilot.pause(.1)
                    assert app.voice.model is not None,app.voice.state
                    app.voice.state='Public-sample local transcription verified; microphone not tested'
                    app.ui('#voice-model',Select).value='tiny.en'
                    app.refresh_setup()
                await pilot.pause()
                app.save_screenshot('28-voice-setup.svg',str(OUTPUT))
                if speech_record:
                    app.show_voice_draft(record['transcript'])
                    await pilot.pause()
                    app.save_screenshot('29-real-speech-draft.svg',str(OUTPUT))
                    await pilot.click('#voice-discard')
                app.action_tab('setup')
                app.ui('#setup-scroll').scroll_home(animate=False)
                await pilot.resize_terminal(100,36)
                await pilot.pause()
                app.save_screenshot('30-compact-setup.svg',str(OUTPUT))
        finally:
            app.ollama.close();app.planner.close();app.voice.close();app.runtime.close()
    print('Captured setup, eight themes, labeled preview plan, voice controls and compact layout.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--speech-record');args=parser.parse_args()
    asyncio.run(capture(args.speech_record))
