from textual.widgets import DataTable, Input, Select, TextArea
from forge.tui import ForgeApp, ConfirmScreen


async def test_ui_memory_mail_and_command_history(project):
    app = ForgeApp(project)
    try:
        async with app.run_test(size=(150, 48)) as pilot:
            app.execute("/remember decision Fixture: run tests before merging")
            app.execute("/send claude codex Fixture: review the parser")
            app.refresh_state()
            await pilot.pause()
            assert app.query_one("#memory-table", DataTable).row_count == 1
            assert app.query_one("#mail-table", DataTable).row_count == 1
            app.execute("/theme ember")
            assert app.palette == "ember"
            app.action_help()
            await pilot.pause()
            assert app.query_one("#command", Input).has_focus
    finally: app.runtime.close()


async def test_task_editor_creates_without_dispatch(project):
    app = ForgeApp(project)
    try:
        async with app.run_test(size=(150, 50)) as pilot:
            await pilot.click("#new-task")
            app.screen.query_one("#task-title", Input).value = "Fixture: parser tests"
            app.screen.query_one("#task-prompt", TextArea).load_text("Write bounded tests and report results.")
            app.screen.query_one("#task-engine", Select).value = "claude"
            await pilot.click("#task-create")
            await pilot.pause()
            assert len(app.runtime.store.tasks()) == 1
            assert app.runtime.store.tasks()[0]["status"] == "queued"
            assert not app.runtime.sessions
    finally: app.runtime.close()


async def test_embedded_terminal_receives_keys_and_composer_escape(project):
    app = ForgeApp(project)
    try:
        async with app.run_test(size=(150, 50)) as pilot:
            app.execute("/launch shell")
            await pilot.pause()
            terminal = app.query_one("#terminal-view")
            assert terminal.has_focus
            await pilot.press("e", "c", "h", "o", "space", "T", "U", "I", "_", "O", "K", "enter")
            await pilot.pause(0.4)
            assert "TUI_OK" in "\n".join(terminal.session.screen.display)
            await pilot.press("ctrl+space")
            assert app.query_one("#command", Input).has_focus
            app.execute("/stop " + terminal.session.id)
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)
            await pilot.click("#cancel")
            assert terminal.session.status == "running"
    finally: app.runtime.close()


async def test_narrow_terminal_still_mounts(project):
    app = ForgeApp(project)
    try:
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            assert app.query_one("#command", Input).display
            sessions = app.query_one("#sessions")
            rail = app.query_one("#rail")
            assert sessions.region.bottom <= rail.region.bottom
            app.action_tab("memory")
            await pilot.pause()
            assert app.query_one("#memory-table", DataTable).row_count == 0
    finally: app.runtime.close()
