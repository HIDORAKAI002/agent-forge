"""Full-screen, keyboard-first terminal interface. No Electron and no browser host."""
from __future__ import annotations
import json
import shlex
from pathlib import Path
from datetime import datetime
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.style import Style
from textual import on, events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.widgets import Button, DataTable, Footer, Input, Label, OptionList, RichLog, Select, Static, TabbedContent, TabPane, TextArea
from textual.widgets.option_list import Option
from .runtime import Runtime
from .terminal import Session
from .profiles import recommend, Profile
from .ollama import OllamaHub, model_name, bytes_text
import shutil
import platform
import time
import psutil

COMMANDS = ["/models", "/tutorial", "/ollama", "/help", "/launch", "/sessions", "/focus", "/stop", "/task", "/tasks", "/run", "/approve", "/remember", "/memory", "/send", "/inbox", "/ack", "/engines", "/route", "/theme", "/quit"]
PALETTES = {"nebula": ("#65d7ff", "#b299ff", "#0a101e"), "ember": ("#ffbd73", "#fb86a5", "#160f13")}
KEY_BYTES = {"enter":"\r", "tab":"\t", "shift+tab":"\x1b[Z", "backspace":"\x7f", "escape":"\x1b", "up":"\x1b[A", "down":"\x1b[B", "right":"\x1b[C", "left":"\x1b[D", "home":"\x1b[H", "end":"\x1b[F", "delete":"\x1b[3~", "insert":"\x1b[2~", "pageup":"\x1b[5~", "pagedown":"\x1b[6~"}
ANSI_COLORS = {"default":"#d9e4f4", "black":"#172236", "red":"#f37e91", "green":"#78ddae", "brown":"#f2ca7c", "blue":"#75a7ff", "magenta":"#c3a0ff", "cyan":"#75dcf0", "white":"#e4edfa", "brightblack":"#788aa5", "brightred":"#ff95a7", "brightgreen":"#9bf6c6", "brightbrown":"#ffe49b", "brightblue":"#a3c4ff", "brightmagenta":"#d7b5ff", "brightcyan":"#9df1ff", "brightwhite":"#ffffff"}


def ansi_color(value: str, background=False) -> str:
    if value == "default":
        return "#090e18" if background else "#d9e4f4"
    if value in ANSI_COLORS:
        return ANSI_COLORS[value]
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        return "#" + value
    return "#090e18" if background else "#d9e4f4"


class TerminalSurface(Static):
    can_focus = True
    session: Session | None = None
    default_background = "#090e18"

    def attach(self, session: Session):
        self.session = session
        self.resize_child()
        self.refresh()
        self.focus()

    def resize_child(self):
        if self.session and self.content_size.width > 1 and self.content_size.height > 1:
            self.session.resize(self.content_size.height, self.content_size.width)

    def on_resize(self, _: events.Resize):
        self.resize_child()

    def render(self):
        if not self.session:
            return Text("No session selected.", style="#788aa5")
        screen = self.session.screen
        output = Text(no_wrap=True, overflow="crop")
        for y in range(screen.lines):
            row = screen.buffer[y]
            for x in range(screen.columns):
                char = row[x]
                if not char.data:  # continuation cell for full-width glyphs
                    continue
                reverse = bool(char.reverse) ^ (self.has_focus and self.session.status == "running" and screen.cursor.x == x and screen.cursor.y == y and not screen.cursor.hidden)
                output.append(char.data, Style(color=ansi_color(char.fg), bgcolor=self.default_background if char.bg == "default" else ansi_color(char.bg, True), bold=char.bold, italic=char.italics, underline=char.underscore, reverse=reverse, strike=char.strikethrough))
            if y < screen.lines - 1:
                output.append("\n")
        return output

    def on_key(self, event: events.Key):
        if not self.session or self.session.status != "running":
            return
        key = event.key
        sequence = KEY_BYTES.get(key)
        if sequence is None and key.startswith("ctrl+") and len(key) == 6:
            sequence = chr(ord(key[-1].lower()) & 31)
        if sequence is None and key.startswith("alt+") and event.character:
            sequence = "\x1b" + event.character
        if sequence is None:
            sequence = event.character
        if sequence is not None:
            try:
                self.session.write(sequence)
            except (ValueError, BrokenPipeError, OSError) as error:
                self.notify(str(error), severity="warning")
            event.prevent_default()
            event.stop()

    def on_paste(self, event: events.Paste):
        if self.session and self.session.status == "running":
            # Respect bracketed-paste mode; do not append Enter or auto-submit.
            text = event.text
            if (2004 << 5) in self.session.screen.mode:
                text = "\x1b[200~" + text + "\x1b[201~"
            try:
                for start in range(0, len(text), 32000):
                    self.session.write(text[start:start + 32000])
            except (ValueError, BrokenPipeError, OSError) as error:
                self.notify(str(error), severity="warning")
            event.stop()


class CommandInput(Input):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history: list[str] = []
        self.position = 0

    def on_key(self, event: events.Key):
        if event.key in ("up", "down") and self.history:
            self.position = max(0, min(len(self.history), self.position + (-1 if event.key == "up" else 1)))
            self.value = self.history[self.position] if self.position < len(self.history) else ""
            self.cursor_position = len(self.value)
            event.stop()


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("y", "accept", "Confirm", priority=True), Binding("n", "reject", "Cancel", priority=True), Binding("escape", "reject", show=False, priority=True), Binding("tab", "toggle", show=False, priority=True), Binding("shift+tab", "toggle", show=False, priority=True), Binding("enter", "submit_choice", show=False, priority=True)]
    def __init__(self, title: str, body: str):
        super().__init__()
        self.heading, self.body = title, body
        self.confirm_selected = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.heading, classes="dialog-title")
            yield Static(self.body, markup=False)
            with Horizontal(classes="dialog-actions"):
                yield Button("Cancel", id="cancel")
                yield Button("Confirm", id="confirm", variant="primary")

    def on_mount(self):
        self.query_one("#cancel", Button).focus()

    def action_accept(self):
        self.dismiss(True)

    def action_reject(self):
        self.dismiss(False)

    def action_toggle(self):
        self.confirm_selected = not self.confirm_selected
        self.query_one("#confirm" if self.confirm_selected else "#cancel", Button).focus()

    def action_submit_choice(self):
        self.dismiss(self.confirm_selected)

    @on(Button.Pressed)
    def choose(self, event: Button.Pressed):
        self.dismiss(event.button.id == "confirm")

    def on_key(self, event: events.Key):
        if event.key == "escape":
            self.dismiss(False)
            event.stop()


class TaskScreen(ModalScreen[dict | None]):
    def __init__(self, engine_options: list[tuple[str, str]]):
        super().__init__()
        self.options = engine_options

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog task-dialog"):
            yield Label("NEW MISSION / bounded task", classes="dialog-title")
            yield Input(placeholder="Task title", id="task-title")
            yield TextArea(id="task-prompt")
            with Horizontal(classes="task-selectors"):
                yield Select(self.options, prompt="Choose a CLI", id="task-engine")
                yield Select([("Routine", "routine"), ("High risk", "high")], value="routine", allow_blank=False, id="task-risk")
            yield Input(placeholder="Prerequisite task IDs, comma-separated (optional)", id="task-deps")
            yield Static("Creates a queued task only. Launching requires a separate confirmation.", classes="muted")
            with Horizontal(classes="dialog-actions"):
                yield Button("Cancel", id="task-cancel")
                yield Button("Create task", id="task-create", variant="primary")

    def on_mount(self):
        self.query_one("#task-title", Input).focus()

    @on(Button.Pressed)
    def choose(self, event: Button.Pressed):
        if event.button.id == "task-cancel":
            self.dismiss(None)
        elif event.button.id == "task-create":
            engine = self.query_one("#task-engine", Select).value
            title = self.query_one("#task-title", Input).value.strip()
            prompt = self.query_one("#task-prompt", TextArea).text.strip()
            if engine is Select.BLANK or not title or not prompt:
                self.notify("Choose an engine and enter a title and task instructions", severity="warning")
                return
            self.dismiss(dict(title=title, prompt=prompt, engine=engine, risk=self.query_one("#task-risk", Select).value, dependencies=[x.strip() for x in self.query_one("#task-deps", Input).value.split(",") if x.strip()]))


class ForgeApp(App):
    TITLE = "AGENT FORGE"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: #0a101e; color: #d9e4f4; scrollbar-background: #0c1423; scrollbar-color: #456887; }
    #masthead { height: 5; background: #111c30; padding: 0 2; border-bottom: heavy #65d7ff; }
    #metrics { height: 3; padding: 0 2; background: #121e31; border-bottom: solid #293954; }
    #workspace { height: 1fr; }
    #rail { width: 31; background: #0e182a; padding: 0 1; border-right: solid #33415e; }
    .rail-title { height: 2; margin-top: 1; color: #b299ff; text-style: bold; }
    #project { height: 3; color: #c4d2e8; }
    #engines { height: 12; border: round #527b99; background: #101c30; }
    #sessions { height: 1fr; min-height: 5; border: round #78688f; background: #151a30; }
    #policy { height: 6; padding: 0 1; border: round #94774d; color: #dac298; }
    #center { width: 1fr; padding: 0 1; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 0; }
    Tabs { background: #111c30; }
    #conversation { height: 1fr; padding: 1 2; border: round #527b99; background: #0c1423; }
    #terminal-meta { height: 2; padding: 0 1; color: #88def1; }
    #terminal-view { height: 1fr; min-height: 4; padding: 0 1; border: round #356d89; background: #090e18; }
    #terminal-view:focus { border: heavy #65d7ff; }
    #task-table, #memory-table, #mail-table { height: 1fr; border: round #78688f; }
    .tab-note { height: auto; padding: 1; color: #a4b5d2; }
    #activity { height: 6; border: round #527b99; padding: 0 1; background: #0e1727; }
    #toolbar { height: 3; background: #101c2f; }
    #toolbar Button { height: 3; min-width: 13; margin-right: 1; }
    #toolbar Static { width: 1fr; padding: 1 1; color: #8497b5; }
    #command { height: 3; margin: 0 1; border: tall #5a5382; background: #101c2f; }
    #command:focus { border: tall #65d7ff; }
    #models-scroll { height: 1fr; padding: 0 1; }
    #model-status { height: auto; min-height: 3; padding: 1; background: #142139; color: #91e3ff; }
    #model-tutorial { height: auto; padding: 1; border-left: heavy #b299ff; color: #c4d2e8; }
    #model-tag, #model-preset { height: 3; }
    .model-actions { height: 3; }
    .model-actions Button { min-width: 10; margin-right: 1; }
    #model-progress { height: auto; min-height: 3; padding: 0 1; color: #78ddae; }
    #model-table { height: 7; border: round #78688f; }
    #model-hardware, #model-commands { height: auto; padding: 1; color: #b9cce6; }
    Footer { background: #182238; color: #b9cce6; }
    ConfirmScreen, TaskScreen { align: center middle; background: #060912 80%; }
    .dialog { width: 76; height: auto; max-height: 95%; border: heavy #b299ff; padding: 1 2; background: #142139; }
    .dialog-title { height: 2; text-style: bold; color: #91e3ff; }
    .dialog Static { height: auto; margin-bottom: 1; }
    .dialog-actions { height: 3; align-horizontal: right; margin-top: 1; }
    .dialog-actions Button { margin-left: 1; }
    .task-dialog { width: 88; }
    #task-prompt { height: 9; border: round #445773; }
    .task-selectors { height: 3; }
    .task-selectors Select { width: 1fr; }
    .muted { color: #8fa2c1; }
    .compact #rail { width: 23; }
    .compact #model-status, .compact #model-tutorial { padding: 0 1; }
    .compact #policy { display: none; }
    .compact #masthead { height: 4; }
    .compact .rail-title { height: 1; margin-top: 0; }
    .compact #project { height: 2; overflow: hidden; }
    .compact #engines { height: 9; }
    .compact #sessions { min-height: 4; }
    .compact #toolbar-hint { display: none; }
    """
    BINDINGS = [Binding("f6", "tab('models')", "Models", priority=True), Binding("ctrl+space", "composer", "Command", priority=True), Binding("ctrl+@", "composer", show=False, priority=True), Binding("ctrl+at", "composer", show=False, priority=True), Binding("f1", "help", "Help", priority=True), Binding("f2", "tab('workbench')", "Agents", priority=True), Binding("f3", "tab('missions')", "Tasks", priority=True), Binding("f4", "tab('memory')", "Memory", priority=True), Binding("f5", "tab('mail')", "Mail", priority=True), Binding("ctrl+q", "request_quit", "Quit", priority=True)]

    def __init__(self, project: str | Path):
        super().__init__()
        self.runtime = Runtime(project)
        self.active: str | None = None
        self.palette = "nebula"
        self.memory_query = ""
        self.mail_recipient = "supervisor"
        self.cache: dict[str, str] = {}
        self._forge_closing = False
        try:
            self.ollama = OllamaHub(self.runtime.store.directory)
        except Exception:
            self.runtime.close()
            raise
        self._ollama_refresh = 0.0

    def compose(self) -> ComposeResult:
        yield Static(id="masthead")
        yield Static(id="metrics")
        with Horizontal(id="workspace"):
            with Vertical(id="rail"):
                yield Static("PROJECT / LOCAL", classes="rail-title")
                yield Static(str(self.runtime.store.project), id="project", markup=False)
                yield Static("AVAILABLE HARNESSES", classes="rail-title")
                yield OptionList(id="engines")
                yield Static("LIVE SESSIONS", classes="rail-title")
                yield OptionList(id="sessions")
                yield Static(id="policy")
            with Vertical(id="center"):
                with TabbedContent(initial="workbench", id="tabs"):
                    with TabPane(">_ Agents", id="workbench"):
                        yield RichLog(id="conversation", wrap=True, markup=False)
                        yield Static(id="terminal-meta", markup=False)
                        yield TerminalSurface(id="terminal-view")
                    with TabPane("≡ Missions", id="missions"):
                        yield Static("Queued → isolated worktree → review → human approval. Select a row to prepare /run; nothing auto-executes.", classes="tab-note")
                        yield DataTable(id="task-table", cursor_type="row")
                    with TabPane("◇ Memory", id="memory"):
                        yield Static("One project memory. Facts / decisions / handoffs with provenance. /remember <kind> <text> · /memory <search>", classes="tab-note")
                        yield DataTable(id="memory-table", cursor_type="row")
                    with TabPane("↔ Mail", id="mail"):
                        yield Static("Project-local agent inbox. /inbox <name> · /send <from> <to> <text> · /ack <id> <recipient>", classes="tab-note")
                        yield DataTable(id="mail-table", cursor_type="row")
                    with TabPane("◉ Models", id="models"):
                        with VerticalScroll(id="models-scroll"):
                            yield Static(id="model-status", markup=False)
                            yield Static(id="model-tutorial", markup=False)
                            yield Select([("Qwen2.5-Coder · 1.5B", "qwen2.5-coder:1.5b"), ("Qwen2.5-Coder · 3B", "qwen2.5-coder:3b"), ("Qwen2.5-Coder · 7B", "qwen2.5-coder:7b")], prompt="Model suggestions · or enter any local tag below", id="model-preset")
                            yield Input(value="qwen2.5-coder:3b", placeholder="Local model tag (any installed or library model)", id="model-tag")
                            with Horizontal(classes="model-actions"):
                                yield Button("Refresh", id="model-refresh")
                                yield Button("Pull + use", id="model-pull", variant="primary")
                                yield Button("Use installed", id="model-use")
                                yield Button("Cancel", id="model-cancel")
                            yield Static(id="model-progress", markup=False)
                            yield DataTable(id="model-table", cursor_type="row")
                            with Horizontal(classes="model-actions"):
                                yield Button("Open chat", id="model-chat", variant="primary")
                                yield Button("Start server", id="model-serve")
                                yield Button("Setup shell", id="model-setup")
                                yield Button("Unload", id="model-unload")
                            yield Static(id="model-hardware", markup=False)
                            yield Static(id="model-commands", markup=False)
                            yield Button("Finish / skip tutorial", id="model-tutorial-done")
                yield Static(id="activity", markup=False)
        with Horizontal(id="toolbar"):
            yield Button("+ New task", id="new-task", variant="primary")
            yield Button(">_ Shell", id="new-shell")
            yield Button("Theme", id="theme")
            yield Button("Voice · soon", id="voice", disabled=True)
            yield Static("Keyboard-first / real CLIs / shared state", id="toolbar-hint")
        yield CommandInput(id="command", placeholder="› /launch claude   /task   /remember decision …   /help", suggester=SuggestFromList(COMMANDS, case_sensitive=False))
        yield Footer()

    def exit(self, *args, **kwargs):
        self._forge_closing = True
        self.ollama.close()
        if hasattr(self, "_pump_timer"):
            self._pump_timer.stop()
        return super().exit(*args, **kwargs)

    def ui(self, selector, expected=None):
        return self.workspace_screen.query_one(selector, expected)

    def on_mount(self):
        self.workspace_screen = self.screen
        for selector in ("#terminal-view", "#terminal-meta"):
            self.ui(selector).display = False
        self.refresh_engines()
        self.ui("#engines").border_title = "Enter to launch"
        self.ui("#sessions").border_title = "Enter to focus"
        self.ui("#conversation").border_title = "Mission control"
        self.ui("#terminal-view").border_title = "Embedded PTY / native input"
        self.ui("#activity").border_title = "Event stream / local ledger"
        self.ui("#model-table", DataTable).add_columns("Model", "Disk size", "Parameters", "Quant", "Loaded")
        self.ui("#model-table").border_title = "Installed locally · Enter selects"
        self.ui("#task-table", DataTable).add_columns("ID", "Status", "Engine", "Mission")
        self.ui("#memory-table", DataTable).add_columns("Kind", "Trust", "Author", "Memory")
        self.ui("#mail-table", DataTable).add_columns("ID", "From", "To", "Message")
        welcome = Text("AGENTS, NOT JUST TABS\n", style="bold #65d7ff")
        welcome.append("Real CLI processes live inside this terminal.\nShared memory and mail connect their work.\n\n", style="#c4d2e8")
        welcome.append("01  Launch a harness     /launch claude\n02  Give work an owner  /task\n03  Keep the context    /remember decision …\n04  Inspect & approve   /tasks", style="#b7a3eb")
        self.say(Panel(welcome, border_style="#685791", padding=(1, 2), title="░▒▓  LOCAL AGENT WORKSPACE  ▓▒░"))
        self.say(Text("Native CLI permissions still apply. Worktrees isolate files, not OS access.\nVoice and automatic orchestration are not enabled in v0.3. Local Ollama chat is available in Models (F6).", style="#e1bc7c"))
        self.refresh_state()
        self.action_composer()
        self._pump_timer = self.set_interval(0.08, self.pump)
        self.ollama.start("refresh")
        self._ollama_refresh = time.monotonic()
        if not self.ollama.settings["tutorial_completed"]:
            self.action_tab("models")

    def on_resize(self, event: events.Resize):
        self.set_class(event.size.width < 110, "compact")

    def say(self, value):
        self.ui("#conversation", RichLog).write(value if not isinstance(value, str) else Text(value))

    def error(self, error):
        self.notify(str(error), severity="error", timeout=7)
        self.say(Text(f"✕ {error}", style="#ff93a8"))

    def refresh_state(self):
        self.refresh_engines()
        self.refresh_models()
        store = self.runtime.store
        running = sum(s.status == "running" for s in self.runtime.sessions.values())
        tasks = store.tasks()
        memories = store.memories(query=self.memory_query, limit=100)
        a, b, _ = PALETTES[self.palette]
        head = Text("░▒▓  AGENT / FORGE  ▓▒░", style=f"bold {a}")
        head.append("    MULTI-AGENT TERMINAL WORKSTATION\n", style=b)
        head.append("   Native CLIs · shared context · explicit control", style="#bacbe3")
        head.append("\n   " + "─" * max(10, min(self.size.width - 8, 150)), style="#344866")
        self.ui("#masthead", Static).update(head)
        metrics = Text(f" ◉ {running:02d} LIVE   │   ≡ {len(tasks):02d} TASKS   │   ◇ {len(store.memories(limit=500)):02d} MEMORIES   │   QUOTA / COST: unknown", style=a)
        metrics.append(f"   │   {self.palette.upper()} / v0.3", style=b)
        self.ui("#metrics", Static).update(metrics)
        self.ui("#policy", Static).update(Text("ROUTING / POLICY\nUser-set cost tiers\n/run asks before launch\nNo automatic merges", style="#dac298"))
        session_signature = json.dumps([(s.id, s.engine, s.status) for s in self.runtime.sessions.values()])
        if self.cache.get("sessions") != session_signature:
            widget = self.ui("#sessions", OptionList)
            previous = widget.highlighted
            widget.clear_options()
            for session in self.runtime.sessions.values():
                label = Text("● " if session.status == "running" else "■ ", style="#78ddae" if session.status == "running" else "#73849f")
                label.append(f"{session.engine} / {session.id[:6]}\n  {session.status}", style="#bccae1")
                widget.add_option(Option(label, id=session.id))
            if widget.option_count and previous is not None:
                widget.highlighted = min(previous, widget.option_count - 1)
            self.cache["sessions"] = session_signature
        rows = {
            "task-table": [(t["id"], (t["id"][:8], t["status"], t["engine"], t["title"])) for t in tasks],
            "memory-table": [(m["id"], (m["kind"], "verified" if m["verified"] else "unverified", m["author"], m["text"].replace("\n", " "))) for m in memories],
            "mail-table": [(m["id"], (m["id"][:8], m["sender"], m["recipient"], m["text"].replace("\n", " "))) for m in store.inbox(self.mail_recipient)],
        }
        for identifier, items in rows.items():
            signature = json.dumps(items)
            if self.cache.get(identifier) != signature:
                table = self.ui("#" + identifier, DataTable)
                position = table.cursor_row
                table.clear()
                for key, row in items:
                    table.add_row(*(Text(str(value)) for value in row), key=key)
                if table.row_count:
                    table.move_cursor(row=min(position, table.row_count - 1))
                self.cache[identifier] = signature
        self.ui("#activity", Static).update("\n".join(f"{e['created_at'][11:19]}  ┊  {e['kind']}" for e in store.events(3)) or "Local ledger ready. Models status is shown in F6; /launch or /task to begin coding.")

    def pump(self):
        if self._forge_closing or not getattr(self, "workspace_screen", None) or not self.workspace_screen.is_mounted or not self.workspace_screen.query("#masthead"):
            return
        self.ollama.poll()
        if not self.ollama.busy and time.monotonic() - self._ollama_refresh > 10:
            self.ollama.start("refresh")
            self._ollama_refresh = time.monotonic()
        events = self.runtime.poll()
        if events:
            self.ui("#terminal-view").refresh()
        for identifier, kind, value in events:
            if kind == "exit":
                self.say(f"Session {identifier[:8]} exited ({value}). Task results require human review.")
        # State can change through independent CLI/MCP clients.
        self.refresh_state()

    def on_unmount(self):
        self.ollama.close()

    def refresh_engines(self):
        selected = self.ollama.settings.get("selected_model")
        if selected:
            self.runtime.profiles["ollama"] = Profile("ollama", "Ollama / " + selected, ("ollama", "run", selected), tier="local")
        signature = [(p.id, p.label, p.available) for p in self.runtime.profiles.values()]
        if self.cache.get("engines") == str(signature):
            return
        widget = self.ui("#engines", OptionList)
        widget.clear_options()
        for profile in self.runtime.profiles.values():
            label = Text("● " if profile.available else "○ ", style="#78ddae" if profile.available else "#62758f")
            label.append(profile.label, style="#d9e4f4" if profile.available else "#73849f")
            widget.add_option(Option(label, id=profile.id, disabled=not profile.available))
        self.cache["engines"] = str(signature)

    def refresh_models(self):
        hub = self.ollama
        selected = hub.settings.get("selected_model") or "none selected"
        installed = hub.inventory["installed"]
        loaded = {m.get("name", m.get("model")): m for m in hub.inventory["loaded"]}
        self.ui("#model-status", Static).update(f"LOCAL OPERATOR / {selected}  ·  {hub.state}\nServer: {hub.api.host} · Ollama {hub.inventory['version']} · CLI: {'on PATH' if shutil.which('ollama') else 'not installed'}\nAuto-activate on reopen: {'ON' if hub.settings['auto_activate'] else 'OFF'} · model chat ≠ a file-editing coding agent")
        if self.size.width < 110:
            cli = "ready" if shutil.which("ollama") else "missing"
            self.ui("#model-status", Static).update(f"OPERATOR {selected} · {hub.state}\n{hub.api.host} · CLI {cli}\nAUTO {'ON' if hub.settings['auto_activate'] else 'OFF'} · CHAT ONLY; no coding tools")
        tutorial = self.ui("#model-tutorial", Static)
        tutorial.display = not hub.settings["tutorial_completed"]
        tutorial.update("FIRST-RUN FLIGHT CHECK\n01 Install Ollama using the commands below; Setup shell never auto-runs an installer.\n02 Start server → Refresh.  03 Choose a model tag or select an installed row.\n04 Pull + use asks first, shows real layer %, then activates automatically.\n05 Open chat runs Ollama here. Scroll ↓ for commands / RAM meters; selection persists.")
        if self.size.width < 110:
            tutorial.update("TUTORIAL · Scroll ↓ for install commands + RAM/VRAM\n1 Install → Start server → Refresh → Choose tag.\n2 Pull + use → Confirm → Auto-activate → Open chat.")
        self.ui("#model-progress", Static).update(hub.progress_text())
        self.ui("#model-progress").styles.color = "#ff93a8" if hub.state.startswith("Error:") else "#78ddae"
        signature = json.dumps([installed, list(loaded)])
        if self.cache.get("model-table") != signature:
            table = self.ui("#model-table", DataTable)
            table.clear()
            for item in installed:
                name = item.get("name", item.get("model"))
                detail = item.get("details", {})
                table.add_row(Text(name), bytes_text(item.get("size", 0)), str(detail.get("parameter_size", "?")), str(detail.get("quantization_level", "?")), "YES" if name in loaded else "no", key=name)
            self.cache["model-table"] = signature
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(self.runtime.store.project)
        lines = [f"HOST RAM {vm.percent:.0f}% used · {vm.available/1e9:.1f}/{vm.total/1e9:.1f} GB available · project disk free {disk.free/1e9:.1f} GB"]
        for name, item in loaded.items():
            size, vram = item.get("size", 0), item.get("size_vram", 0)
            ratio = f"{vram/size*100:.1f}%" if size else "unknown"
            lines.append(f"{name}: loaded {bytes_text(size)} · VRAM {bytes_text(vram)} · GPU residency {ratio} (not utilization)")
        if not loaded:
            lines.append("Loaded model memory / GPU residency: unavailable until /api/ps reports a model.")
        self.ui("#model-hardware", Static).update("\n".join(lines))
        value = self.ui("#model-tag", Input).value.strip()
        try:
            value = model_name(value)
        except ValueError:
            value = "MODEL_TAG"
        install = "Open https://ollama.com/download (macOS installer)" if platform.system() == "Darwin" else "curl -fsSL https://ollama.com/install.sh | sh  # Linux / WSL; review first"
        self.ui("#model-commands", Static).update(f"SETUP / exact commands — no silent installs\n{install}\nOLLAMA_HOST={shlex.quote(hub.api.host)} ollama serve\nOLLAMA_HOST={shlex.quote(hub.api.host)} ollama pull {shlex.quote(value)}\nOLLAMA_HOST={shlex.quote(hub.api.host)} ollama run {shlex.quote(value)}\nDownload requires internet + disk. Generation uses the loopback server. Cloud models are excluded.\nLayer % is byte-based; manifest / verification / RAM loading are indeterminate.\nOllama chooses hardware automatically; keep-alive is 5 minutes, not permanent GPU allocation.")
        for key in ("model-refresh", "model-pull", "model-use", "model-serve", "model-unload"):
            self.ui("#" + key, Button).disabled = hub.busy
        self.ui("#model-cancel", Button).disabled = not hub.busy
        self.ui("#model-chat", Button).disabled = not (hub.online and selected in loaded and shutil.which("ollama"))

    @on(Select.Changed, "#model-preset")
    def model_preset(self, event: Select.Changed):
        if event.value is not Select.BLANK:
            self.ui("#model-tag", Input).value = str(event.value)
            self.refresh_models()

    @on(DataTable.RowSelected, "#model-table")
    def select_model(self, event: DataTable.RowSelected):
        self.ui("#model-tag", Input).value = str(event.row_key.value)
        self.refresh_models()

    def model_action(self, action):
        hub = self.ollama
        model = self.ui("#model-tag", Input).value.strip()
        if action == "model-refresh":
            hub.start("refresh")
        elif action == "model-pull":
            model = model_name(model)
            self.push_screen(ConfirmScreen("PULL LOCAL MODEL / disk and network", f"Download {model} from Ollama's registry? Model sizes vary; this consumes network and model-storage disk space. After verified download, Forge will load it into RAM and save it as this project's operator. No installer, coding task or paid API is launched."), lambda approved: self.start_model("pull", model) if approved else None)
        elif action == "model-use":
            model = model_name(model)
            self.push_screen(ConfirmScreen("ACTIVATE LOCAL MODEL", f"Load installed {model} into RAM/VRAM and remember it for automatic activation on project reopen? This does not download a model or grant it file-editing tools."), lambda approved: self.start_model("activate", model) if approved else None)
        elif action == "model-cancel":
            hub.cancel()
        elif action == "model-unload":
            selected = hub.settings.get("selected_model")
            if not selected:
                raise ValueError("No selected operator")
            hub.start("unload", selected)
        elif action == "model-chat":
            selected = hub.settings.get("selected_model")
            if not hub.online or not any(m.get("name", m.get("model")) == selected for m in hub.inventory["loaded"]):
                raise ValueError("Activate an installed local model first")
            self.refresh_engines()
            self.focus_session(self.runtime.launch("ollama", env_overrides={"OLLAMA_HOST": hub.api.host}))
        elif action == "model-serve":
            self.runtime.profiles["ollama-server"] = Profile("ollama-server", "Ollama server", ("ollama", "serve"), tier="local")
            self.focus_session(self.runtime.launch("ollama-server", env_overrides={"OLLAMA_HOST": hub.api.host}))
        elif action == "model-setup":
            self.focus_session(self.runtime.launch("shell"))
            self.say("Review the official install command in Models; nothing was executed automatically.")
            # Show setup commands but never write an installer into a live shell or press Enter.
        elif action == "model-tutorial-done":
            hub.settings["tutorial_completed"] = True
            hub.save()
        self.refresh_models()

    def start_model(self, operation, model):
        try:
            self.ollama.start(operation, model)
        except Exception as error:
            self.error(error)

    def focus_session(self, session: Session):
        self.active = session.id
        self.action_tab("workbench")
        self.ui("#conversation").display = False
        self.ui("#terminal-view").display = True
        self.ui("#terminal-meta").display = True
        self.ui("#terminal-meta", Static).update(f"{session.engine} / {session.id[:8]} · {session.cwd} · Ctrl+Space returns to commands")
        self.ui("#terminal-view", TerminalSurface).attach(session)
        self.refresh_state()

    def action_composer(self):
        if self.screen is not self.workspace_screen:
            return
        self.ui("#command", Input).focus()

    def action_tab(self, tab: str):
        self.ui("#tabs", TabbedContent).active = tab

    def action_help(self):
        self.action_tab("workbench")
        self.ui("#conversation").display = True
        self.ui("#terminal-view").display = False
        self.ui("#terminal-meta").display = False
        table = Table(title="COMMAND DECK", border_style="#685791")
        table.add_column("Command", style="#65d7ff")
        table.add_column("Action", style="#c4d2e8")
        for command, description in [("/models · /tutorial", "Local Ollama selection, live layer % and setup guide"), ("/ollama pull|use <model>", "Confirm download; preload and persist local operator"), ("/launch <engine>", "Embed a real CLI; no API simulation"), ("/focus <session-id>", "Return to a terminal; Ctrl+C goes to the CLI"), ("/task", "Guided task editor; does not launch work"), ("/task <engine> <title> :: <prompt>", "Create a queued task"), ("/run <task-id>", "Confirm isolated task execution"), ("/approve <task-id>", "Record human review; no merge"), ("/remember <fact|decision|handoff> <text>", "Save human-verified project context"), ("/memory [search]", "Inspect/filter persistent memory"), ("/send <from> <to> <text>", "Send project-local agent mail"), ("/inbox <name> /ack <id> <recipient>", "Read or acknowledge durable mail"), ("/route <routine|high>", "Recommend a user-configured tier; never dispatch"), ("/theme <nebula|ember>", "Switch accent and terminal surface"), ("/stop <session-id>", "Confirm process-group termination"), ("/quit", "Confirm stopping running sessions and exit")]:
            table.add_row(command, description)
        self.say(table)
        self.action_composer()

    def new_task(self):
        options = [(p.label + (" · missing" if not p.available else ""), p.id) for p in self.runtime.profiles.values() if p.id != "shell"]
        def created(values):
            if values:
                try:
                    task = self.runtime.store.create_task(**values)
                    self.say(f"Queued {task['id'][:8]} / {task['title']}")
                    self.action_tab("missions")
                    self.refresh_state()
                except (ValueError, OSError) as error:
                    self.error(error)
            self.action_composer()
        self.push_screen(TaskScreen(options), created)

    def confirm_run(self, identifier: str):
        task = self.runtime.store.ready(identifier)
        def confirmed(approved):
            if approved:
                try:
                    self.focus_session(self.runtime.run_task(task["id"]))
                except Exception as error:
                    self.error(error)
        self.push_screen(ConfirmScreen("LAUNCH MISSION / your approval", "This starts a real CLI in an isolated worktree from committed HEAD. It may consume your subscription or API credits. Native CLI permissions still apply; worktrees are not a security sandbox. No automatic merge. Commit or stash changes before proceeding."), confirmed)

    def action_request_quit(self):
        if not any(s.status == "running" for s in self.runtime.sessions.values()):
            self.exit()
            return
        self.push_screen(ConfirmScreen("CLOSE WORKSPACE", "Stop all active session process groups and exit? Files, memory and worktrees are preserved."), lambda approved: self.exit() if approved else None)

    @on(Button.Pressed)
    def toolbar(self, event: Button.Pressed):
        if event.button.id and event.button.id.startswith("model-"):
            try:
                self.model_action(event.button.id)
            except Exception as error:
                self.error(error)
        elif event.button.id == "new-task":
            self.new_task()
        elif event.button.id == "new-shell":
            try:
                self.focus_session(self.runtime.launch("shell"))
            except Exception as error:
                self.error(error)
        elif event.button.id == "theme":
            self.set_palette("ember" if self.palette == "nebula" else "nebula")

    @on(OptionList.OptionSelected, "#engines")
    def launch_engine(self, event: OptionList.OptionSelected):
        try:
            self.focus_session(self.runtime.launch(event.option.id))
        except Exception as error:
            self.error(error)

    @on(OptionList.OptionSelected, "#sessions")
    def select_session(self, event: OptionList.OptionSelected):
        self.focus_session(self.runtime.session(event.option.id))

    @on(DataTable.RowSelected, "#task-table")
    def select_task(self, event: DataTable.RowSelected):
        self.ui("#command", Input).value = f"/run {event.row_key.value}"
        self.action_composer()

    def set_palette(self, name: str):
        if name not in PALETTES:
            raise ValueError("Theme: nebula or ember")
        self.palette = name
        primary, secondary, background = PALETTES[name]
        self.workspace_screen.styles.background = background
        self.ui("#masthead").styles.background = "#251b24" if name == "ember" else "#111c30"
        self.ui("#metrics").styles.background = "#211823" if name == "ember" else "#121e31"
        terminal = self.ui("#terminal-view", TerminalSurface)
        terminal.default_background = "#170e14" if name == "ember" else "#090e18"
        terminal.styles.background = terminal.default_background
        terminal.refresh()
        self.ui("#masthead").styles.border_bottom = ("heavy", primary)
        self.ui("#command").styles.border = ("tall", secondary)
        self.refresh_state()

    @on(Input.Submitted, "#command")
    def submitted(self, event: Input.Submitted):
        command = event.value.strip()
        event.input.value = ""
        if not command:
            return
        event.input.history.append(command)
        event.input.position = len(event.input.history)
        try:
            self.execute(command)
        except Exception as error:
            self.error(error)
        self.refresh_state()

    def execute(self, command: str):
        name, _, rest = command.partition(" ")
        if name in ("/models", "/tutorial"):
            if name == "/tutorial":
                self.ollama.settings["tutorial_completed"] = False
                self.ollama.save()
            self.action_tab("models")
        elif name == "/ollama":
            operation, _, model = rest.partition(" ")
            if model:
                self.ui("#model-tag", Input).value = model_name(model.strip())
            actions = {"refresh":"model-refresh", "pull":"model-pull", "use":"model-use", "chat":"model-chat", "serve":"model-serve", "setup":"model-setup", "unload":"model-unload", "cancel":"model-cancel"}
            if operation not in actions:
                raise ValueError("/ollama refresh|pull MODEL|use MODEL|chat|serve|setup|unload|cancel")
            self.model_action(actions[operation])
        elif name == "/help":
            self.action_help()
        elif name == "/launch":
            self.focus_session(self.runtime.launch(rest.strip()))
        elif name == "/focus":
            self.focus_session(self.runtime.session(rest.strip()))
        elif name in ("/sessions", "/engines"):
            self.action_tab("workbench")
            self.ui("#conversation").display = True
            self.ui("#terminal-view").display = False
            self.say("\n".join(f"{s.id[:8]} / {s.engine} / {s.status}" for s in self.runtime.sessions.values()) or "No sessions yet.") if name == "/sessions" else self.say("\n".join(f"{p.id}: {'available' if p.available else 'missing'} / tier {p.tier}" for p in self.runtime.profiles.values()))
        elif name == "/stop":
            session = self.runtime.session(rest.strip())
            self.push_screen(ConfirmScreen("STOP SESSION", f"Terminate the process group for {session.engine} / {session.id[:8]}? Worktree changes are preserved."), lambda approved: session.stop() if approved else None)
        elif name == "/task":
            if not rest:
                self.new_task()
            else:
                header, separator, prompt = rest.partition(" :: ")
                engine, _, title = header.partition(" ")
                if not separator or engine not in self.runtime.profiles or engine == "shell":
                    raise ValueError("Usage: /task <engine> <title> :: <instructions>")
                task = self.runtime.store.create_task(title, prompt, engine)
                self.say(f"Queued {task['id'][:8]}; /run asks before launching.")
                self.action_tab("missions")
        elif name == "/tasks":
            self.action_tab("missions")
        elif name == "/run":
            self.confirm_run(rest.strip())
        elif name == "/approve":
            task = self.runtime.store.task(rest.strip())
            def reviewed(approved):
                if approved:
                    try:
                        self.runtime.approve(task["id"])
                    except Exception as error:
                        self.error(error)
            self.push_screen(ConfirmScreen("RECORD HUMAN REVIEW", "Confirm that you inspected the diff and ran the required checks. Approval does not merge changes. Merge prerequisite work manually before dependent tasks."), reviewed)
        elif name == "/remember":
            kind, _, text = rest.partition(" ")
            self.runtime.store.remember(text, kind, "user", True)
            self.action_tab("memory")
        elif name == "/memory":
            self.memory_query = rest
            self.action_tab("memory")
        elif name == "/send":
            parts = rest.split(" ", 2)
            if len(parts) != 3:
                raise ValueError("Usage: /send <sender> <recipient> <text>")
            self.runtime.store.send(*parts)
            self.mail_recipient = parts[1]
            self.action_tab("mail")
        elif name == "/inbox":
            self.mail_recipient = rest.strip() or "supervisor"
            self.action_tab("mail")
        elif name == "/ack":
            parts = rest.split()
            if len(parts) != 2:
                raise ValueError("Usage: /ack <full-message-id> <recipient>")
            self.runtime.store.acknowledge(*parts)
        elif name == "/route":
            if rest not in ("routine", "high"):
                raise ValueError("Usage: /route routine|high")
            result = recommend(list(self.runtime.profiles.values()), rest)
            self.say(f"Policy recommendation: {result or 'no available task-capable profile'}. No dispatch; tiers are user-configured, not vendor pricing.")
        elif name == "/theme":
            self.set_palette(rest.strip())
        elif name in ("/quit", "/exit"):
            self.action_request_quit()
        else:
            raise ValueError("Use /help for the command deck. Natural-language supervisor planning is not enabled yet.")
