"""Capture actual Textual screens. Demo records are labeled; the terminal is a real PTY."""
import asyncio
from pathlib import Path
import tempfile
from forge.tui import ForgeApp
from textual.widgets import Input, Select, TextArea

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/screenshots"
OUTPUT.mkdir(parents=True, exist_ok=True)


async def capture():
    with tempfile.TemporaryDirectory(prefix="forge-ui-demo-") as folder:
        app = ForgeApp(folder)
        try:
            async with app.run_test(size=(160, 50)) as pilot:
                await pilot.pause()
                app.action_tab("workbench")
                await pilot.pause()
                app.save_screenshot("01-workspace.svg", str(OUTPUT))
                app.execute("/remember decision UI demo: changes need tests and human review.")
                app.execute("/task claude UI demo: parser tests :: Add bounded parser tests. Report verification results.")
                app.refresh_state()
                app.action_tab("missions")
                await pilot.pause()
                app.save_screenshot("02-missions.svg", str(OUTPUT))
                app.action_tab("memory")
                await pilot.pause()
                app.save_screenshot("03-memory.svg", str(OUTPUT))
                app.execute("/send supervisor reviewer UI demo: review the parser once tests pass.")
                app.refresh_state()
                await pilot.pause()
                app.save_screenshot("04-mail.svg", str(OUTPUT))
                app.action_tab("workbench")
                app.new_task()
                await pilot.pause()
                app.screen.query_one("#task-title", Input).value = "UI demo: implement a settings parser"
                app.screen.query_one("#task-prompt", TextArea).load_text("Keep the change bounded. Add tests. Report changed files and checks. No automatic merge.")
                app.screen.query_one("#task-engine", Select).value = "claude"
                await pilot.pause()
                app.save_screenshot("05-task-editor.svg", str(OUTPUT))
                await pilot.click("#task-cancel")
                app.execute("/launch shell")
                await pilot.pause()
                session = app.runtime.session(app.active)
                session.write("printf '\\033[38;2;101;215;255mAGENT FORGE / REAL LOCAL SHELL\\033[0m\\nNo provider model is running in this screenshot.\\n'\n")
                await pilot.pause(0.6)
                app.save_screenshot("06-embedded-terminal.svg", str(OUTPUT))
                app.execute("/stop " + session.id)
                await pilot.pause()
                app.save_screenshot("07-approval.svg", str(OUTPUT))
                await pilot.click("#cancel")
                app.execute("/theme ember")
                app.action_help()
                await pilot.pause()
                app.save_screenshot("08-ember.svg", str(OUTPUT))
                await pilot.resize_terminal(100, 36)
                await pilot.pause()
                app.save_screenshot("09-compact.svg", str(OUTPUT))
        finally:
            app.runtime.close()
    print("Captured 9 real TUI screen states; labeled demo records, real local PTY.")


if __name__ == "__main__":
    asyncio.run(capture())
