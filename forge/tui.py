"""Full-screen, keyboard-first terminal interface. No Electron and no browser host."""
from __future__ import annotations
import os
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
from textual.theme import Theme
from textual.suggester import SuggestFromList
from textual.widgets import Button, DataTable, Footer, Input, Label, OptionList, RichLog, Select, Static, TabbedContent, TabPane, TextArea
from textual.widgets.option_list import Option
from .runtime import Runtime
from .terminal import Session
from .profiles import recommend, Profile, profiles
from .ollama import OllamaHub, model_name, bytes_text
import shutil
import platform
import time
import psutil
from .settings import Preferences, PALETTES, surface
from .credentials import PROVIDERS, INSTALL_COMMANDS
from .planner import Planner, DispatchBatch, queue_plan, validate_plan
from .voice import Voice, MODELS
from .store import managed

COMMANDS = ["/sandbox", "/ruflo", "/setup", "/plan", "/dispatch", "/pause", "/voice", "/models", "/tutorial", "/ollama", "/help", "/launch", "/sessions", "/focus", "/stop", "/task", "/tasks", "/run", "/approve", "/remember", "/memory", "/send", "/inbox", "/ack", "/engines", "/route", "/theme", "/quit"]
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


class DictationScreen(ModalScreen[tuple[str,str] | None]):
    BINDINGS=[Binding("escape","cancel",show=False)]
    def __init__(self,text):super().__init__();self.text=text
    def compose(self):
        with Vertical(classes="dialog task-dialog"):
            yield Label("VOICE DRAFT / review before inserting",classes="dialog-title")
            yield Static("Local transcription may contain mistakes. Insertion never presses Enter or runs commands.",markup=False)
            yield TextArea(self.text,id="voice-draft")
            with Horizontal(classes="dialog-actions"):
                yield Button("Discard",id="voice-discard")
                yield Button("To goal",id="voice-goal")
                yield Button("To composer",id="voice-composer")
                yield Button("To active CLI",id="voice-cli",variant="primary")
    def action_cancel(self):self.dismiss(None)
    @on(Button.Pressed)
    def choose(self,event):
        if event.button.id=="voice-discard":self.dismiss(None)
        elif event.button.id in ("voice-goal","voice-composer","voice-cli"):
            value=self.query_one("#voice-draft",TextArea).text
            self.dismiss((event.button.id,value))


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
    .permission-paths { height: 6; margin: 0 1; }
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
    ConfirmScreen, TaskScreen, DictationScreen { align: center middle; background: #060912 80%; }
    .dialog { width: 76; height: auto; max-height: 95%; border: heavy #b299ff; padding: 1 2; background: #142139; }
    .dialog-title { height: 2; text-style: bold; color: #91e3ff; }
    .dialog Static { height: auto; margin-bottom: 1; }
    .dialog-actions { height: 3; align-horizontal: right; margin-top: 1; }
    .dialog-actions Button { margin-left: 1; }
    .task-dialog { width: 88; }
    #setup-scroll, #planner-scroll { height: 1fr; padding: 0 1; }
    .setup-note { height: auto; padding: 1; color: #b9cce6; }
    .setup-section { height: 2; margin-top: 1; color: #b299ff; text-style: bold; }
    #key-status, #planner-status, #voice-status { height: auto; min-height: 2; color: #8fdecc; padding: 0 1; }
    #planner-goal { height: 5; }
    #planner-draft { height: 12; }
    #voice-draft { height: 9; }
    #setup-scroll Select, #setup-scroll Input { height: 3; }
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
    BINDINGS = [Binding("f7", "tab('setup')", "Setup", priority=True), Binding("f8", "tab('planning')", "Plan", priority=True), Binding("f6", "tab('models')", "Models", priority=True), Binding("ctrl+space", "composer", "Command", priority=True), Binding("ctrl+@", "composer", show=False, priority=True), Binding("ctrl+at", "composer", show=False, priority=True), Binding("f1", "help", "Help", priority=True), Binding("f2", "tab('workbench')", "Agents", priority=True), Binding("f3", "tab('missions')", "Tasks", priority=True), Binding("f4", "tab('memory')", "Memory", priority=True), Binding("f5", "tab('mail')", "Mail", priority=True), Binding("ctrl+q", "request_quit", "Quit", priority=True)]

    def __init__(self, project: str | Path):
        super().__init__()
        self.runtime = Runtime(project)
        self.active: str | None = None
        try:
            self.preferences = Preferences()
        except Exception:
            self.runtime.close()
            raise
        for name,(primary,secondary,background) in PALETTES.items():
            self.register_theme(Theme(name="forge-"+name,primary=primary,secondary=secondary,accent=secondary,foreground="#d9e4f4",background=background,surface=surface(background,primary,.07),panel=surface(background,primary,.11),success="#78ddae",warning="#e1bc7c",error="#ff93a8",dark=True))
        self.palette = self.preferences.data["theme"]
        from .ruflo import RufloBridge
        self.ruflo=RufloBridge(self.runtime.store)
        self.pending_plan=None;self.ruflo_hint="No routing hint requested"
        self.planner = Planner()
        self.dispatch = DispatchBatch()
        self.voice = Voice(self.preferences.root/"speech-models")
        self.key_status = "No provider key entered or verified"
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
                        yield Static("Queued → isolated worktree → review → human approval. Select a row to prepare /run. Approved dispatch can launch ready tasks; reviews remain manual.", classes="tab-note")
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
                    with TabPane("✦ Plan", id="planning"):
                        with VerticalScroll(id="planner-scroll"):
                            yield Static("LOCAL SUPERVISOR / bounded plans, explicit dispatch",classes="setup-section")
                            yield Static("Uses the selected local Ollama model and recent project memories. A plan is a proposal—not permission to run commands. High/routine assignments use your tier labels; free is a user assertion, not a billing guarantee.",classes="setup-note",markup=False)
                            yield TextArea(id="planner-goal")
                            with Horizontal(classes="model-actions"):
                                yield Button("Make plan",id="plan-generate",variant="primary")
                                yield Button("Queue draft",id="plan-queue")
                                yield Button("Dispatch",id="plan-dispatch")
                                yield Button("Pause",id="plan-pause")
                            yield Static(id="planner-status",markup=False)
                            yield TextArea(id="planner-draft",language="json")
                            yield Static("Edit the JSON before queueing. depends_on uses zero-based earlier task indices. Dispatch asks once for the selected queued tasks, runs at most two task sessions, and waits for prerequisite human approvals. Merge prerequisite changes manually. Pause stops future launches, not running CLIs. No automatic retries or merges; this is not an OS sandbox.",classes="setup-note",markup=False)
                    with TabPane("⚙ Setup", id="setup"):
                        with VerticalScroll(id="setup-scroll"):
                            yield Static("FIRST RUN / install → connect → choose → work",classes="setup-section")
                            yield Static("agent-command is the temporary launcher. Core installation does not silently install provider CLIs. Ollama needs no API key for local use. Native provider login remains available; an API key is not a subscription credential.",classes="setup-note",markup=False)
                            yield Static("APPEARANCE / 8 terminal palettes",classes="setup-section")
                            yield Select([(name.title(),name) for name in PALETTES],value=self.palette,allow_blank=False,id="setup-theme")
                            yield Static("PROVIDER KEYS / never stored in project memory",classes="setup-section")
                            yield Select([(label,provider) for provider,(label,_) in PROVIDERS.items()],value="claude",allow_blank=False,id="key-provider")
                            yield Static(id="provider-install-command",classes="setup-note",markup=False)
                            yield Input(password=True,placeholder="API key (masked; never command history)",id="provider-key")
                            yield Select([("This session only","session"),("OS credential store","vault")],value="session",allow_blank=False,id="key-storage")
                            with Horizontal(classes="model-actions"):
                                yield Button("Install CLI",id="setup-install-cli")
                                yield Button("Save key",id="setup-save-key",variant="primary")
                                yield Button("Remove key",id="setup-remove-key")
                                yield Button("Open CLI",id="setup-open-cli")
                                yield Button("Codex auth",id="setup-codex-auth")
                            yield Static(id="key-status",markup=False)
                            yield Static("Claude/Gemini keys are passed only to their corresponding CLI. Codex API-key login is a separate native step; Codex auth uses a non-echoed pipe and requires an OS vault. Without a vault, use native Codex login. Keys are never included in argv, preferences, project JSON or event logs. Existing CLI sessions must restart to receive a newly saved key.",classes="setup-note",markup=False)
                            yield Static("ROUTING / your strong, free and local tiers",classes="setup-section")
                            yield Select([(profile.label,profile.id) for profile in self.runtime.profiles.values() if profile.id not in ("shell","ollama","ollama-server")],prompt="Choose a coding engine",id="route-engine")
                            yield Select([(v.title(),v) for v in ("strong","free","economy","local","unknown")],value="unknown",allow_blank=False,id="route-tier")
                            yield Button("Save routing tier",id="setup-route")
                            yield Static("Routine: local → free → economy → unknown → strong. High risk: strong first, then available fallbacks. Tier labels do not guarantee capability or price; inspect the draft's selected engine before dispatch. Live provider quotas are intentionally out of scope.",classes="setup-note",markup=False)
                            yield Static("PERMISSIONS / enforced project folder boundary",classes="setup-section",id="sandbox-section")
                            yield Select([("Off — native host permissions",False),("Enforce — Linux/WSL Bubblewrap",True)],value=self.runtime.sandbox.policy["enabled"],allow_blank=False,id="sandbox-enabled")
                            yield Static("Approved read-only reference/runtime folders — one full path per line",classes="setup-note",markup=False)
                            yield TextArea("\n".join(self.runtime.sandbox.policy["read_only"]),id="sandbox-grants",classes="permission-paths")
                            yield Select([("Network blocked",False),("Allow host network — providers / local Ollama",True)],value=self.runtime.sandbox.policy["network"],allow_blank=False,id="sandbox-network")
                            yield Button("Review permissions",id="setup-sandbox-save")
                            yield Static(id="sandbox-status",markup=False)
                            yield Static("Only the project is persistently writable. Approved references and standard OS runtime trees are read-only; temporary HOME/tmp are disposable. Other user folders and host procfs are hidden. Install Forge outside the project. Bubblewrap is required; unsupported hosts fail closed. Grants apply to NEW sessions; existing sessions retain their old permissions. Network allowance exposes host networking, not a provider-only firewall. Native Windows/macOS isolation is not available.",classes="setup-note",markup=False)
                            yield Static("RUFLO / pinned memory retrieval + advisory routing",classes="setup-section",id="ruflo-section")
                            yield Static("Install separately: npm install -g ruflo@3.56.9 (Node.js 20+). Connect allows initial local embedding-weight downloads. Provider keys are not passed. Forge SQLite remains authoritative; Ruflo is a derived index. Ruflo service is trusted host-side software, NOT a sandboxed agent.",classes="setup-note",markup=False)
                            with Horizontal(classes="model-actions"):
                                yield Button("Connect Ruflo",id="setup-ruflo-connect")
                                yield Button("Sync memories",id="setup-ruflo-sync")
                                yield Button("Disconnect",id="setup-ruflo-close")
                            yield Static(id="ruflo-status",markup=False)
                            yield Static("VOICE / optional local dictation",classes="setup-section")
                            yield Select([(name,name) for name in MODELS],value=self.preferences.data["voice_model"],allow_blank=False,id="voice-model")
                            with Horizontal(classes="model-actions"):
                                yield Button("Prepare voice",id="setup-voice-prepare")
                                yield Button("Record / stop",id="setup-voice-record")
                                yield Button("Discard audio",id="setup-voice-discard")
                            yield Static(id="voice-status",markup=False)
                            yield Static("Install with FORGE_VOICE=1 bash scripts/install.sh. Linux capture may require PortAudio. Preparing downloads speech weights from Hugging Face with your confirmation; later transcription runs locally. Audio stays in RAM and is cleared after processing. Microphone/model-loading progress is indeterminate, not a fabricated percentage. Maximum recording: 60 seconds.",classes="setup-note",markup=False)
                            yield Static("PLATFORM / Native Windows ConPTY backend added; Windows CI/device validation pending. Linux/WSL folder enforcement uses Bubblewrap. Ruflo is an optional pinned MCP integration; not vendored.",classes="setup-note",markup=False)
                            yield Button("Finish setup / go to Models",id="setup-finish",variant="primary")
                yield Static(id="activity", markup=False)
        with Horizontal(id="toolbar"):
            yield Button("+ New task", id="new-task", variant="primary")
            yield Button(">_ Shell", id="new-shell")
            yield Button("Theme", id="theme")
            yield Button("Voice", id="voice")
            yield Static("Keyboard-first / real CLIs / shared state", id="toolbar-hint")
        yield CommandInput(id="command", placeholder="› /launch claude   /task   /remember decision …   /help", suggester=SuggestFromList(COMMANDS, case_sensitive=False))
        yield Footer()

    def exit(self, *args, **kwargs):
        self._forge_closing = True
        self.ollama.close()
        self.planner.close()
        self.voice.close()
        self.ruflo.close()
        self.dispatch.pause()
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
        self.say(Text("Native CLI permissions still apply. Worktrees isolate files, not OS access.\nLocal planning and review-gated dispatch are available. Voice needs optional dependencies. Worktrees are not an OS sandbox.", style="#e1bc7c"))
        self.set_palette(self.palette)
        self.refresh_state()
        self.action_composer()
        self._pump_timer = self.set_interval(0.08, self.pump)
        self.ollama.start("refresh")
        self._ollama_refresh = time.monotonic()
        if not self.preferences.data["setup_completed"]:
            self.action_tab("setup")
        elif not self.ollama.settings["tutorial_completed"]:
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
        self.refresh_setup()
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
        metrics = Text(f" ◉ {running:02d} LIVE   │   ≡ {len(tasks):02d} TASKS   │   ◇ {len(store.memories(limit=500)):02d} MEMORIES   │   REVIEW-GATED DISPATCH", style=a)
        metrics.append(f"   │   {self.palette.upper()} / v0.5", style=b)
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
        for kind,value in self.ruflo.poll():
            if kind=="error":
                self.pending_plan=None;self.planner.state=value['message'];self.say(value['message'])
            elif kind=="context" and self.pending_plan:
                selected,goal=self.pending_plan;self.pending_plan=None
                hint=value.get('route_hint',{});self.ruflo_hint="Upstream hint: "+str(hint.get('model','unknown'))+" / "+str(hint.get('implementation','not reported'))+"; user tiers still control engines"
                try:self.planner.start(self.ollama.api,selected,goal,value.get('memories',[]))
                except Exception as error:self.error(error)
            elif kind=="search":
                self.action_tab('workbench');self.ui('#conversation').display=True;self.ui('#terminal-view').display=False
                self.say("Ruflo retrieval: "+value.get('retrieval_backend','not reported'))
                for memory in value.get('memories',[]):self.say(f"[{memory['kind']}; {'verified' if memory['verified'] else 'unverified'}] {memory['text']}")

        if self.planner.poll() and self.planner.draft:
            draft={'tasks':[dict(title=t['title'],instructions=t['prompt'],risk=t['risk'],depends_on=t['depends_on']) for t in self.planner.draft]}
            self.ui("#planner-draft",TextArea).load_text(json.dumps(draft,indent=2))
        while not self.runtime.credentials.events.empty():
            self.key_status=self.runtime.credentials.events.get_nowait()
        for kind,value in self.voice.poll():
            if kind=='draft':self.show_voice_draft(value)
        self.dispatch.tick(self.runtime)
        if self.dispatch.errors:
            for error in self.dispatch.errors:self.say(Text("Dispatch paused task: "+error,style="#ff93a8"))
            self.dispatch.errors.clear()
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
        self.planner.close()
        self.voice.close()
        self.ruflo.close()
        self.dispatch.pause()

    def refresh_engines(self):
        selected = self.ollama.settings.get("selected_model")
        if selected and self.cache.get("selected-model-profile") != selected:
            current = profiles(self.runtime.store.project)
            self.runtime.profiles.update(current)
            self.cache["selected-model-profile"] = selected
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
        disk = psutil.disk_usage(str(self.runtime.store.project))
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
        self.ui("#terminal-meta", Static).update(f"{session.engine} / {session.id[:8]} · {session.cwd} · {getattr(session,'isolation','OFF / host permissions')} · Ctrl+Space returns to commands")
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
        for command, description in [("/sandbox", "Project write scope, approved read-only references and network permission"), ("/ruflo connect|sync|search QUERY|off", "Pinned semantic-memory index and advisory routing; no agent execution"), ("/setup · F7", "Provider keys, theme picker, routing and local dictation"), ("/plan · F8", "Local supervisor plan; preview/edit before queueing"), ("/dispatch · /pause", "Authorize bounded ready-task dispatch / stop future launches"), ("/voice", "Local speech draft; never auto-submit"), ("/models · /tutorial", "Local Ollama selection, live layer % and setup guide"), ("/ollama pull|use <model>", "Confirm download; preload and persist local operator"), ("/launch <engine>", "Embed a real CLI; no API simulation"), ("/focus <session-id>", "Return to a terminal; Ctrl+C goes to the CLI"), ("/task", "Guided task editor; does not launch work"), ("/task <engine> <title> :: <prompt>", "Create a queued task"), ("/run <task-id>", "Confirm isolated task execution"), ("/approve <task-id>", "Record human review; no merge"), ("/remember <fact|decision|handoff> <text>", "Save human-verified project context"), ("/memory [search]", "Inspect/filter persistent memory"), ("/send <from> <to> <text>", "Send project-local agent mail"), ("/inbox <name> /ack <id> <recipient>", "Read or acknowledge durable mail"), ("/route <routine|high>", "Recommend a user-configured tier; never dispatch"), ("/theme <name>", "Eight saved terminal palettes; Setup has a picker"), ("/stop <session-id>", "Confirm process-group termination"), ("/quit", "Confirm stopping running sessions and exit")]:
            table.add_row(command, description)
        self.say(table)
        self.action_composer()

    def new_task(self):
        options = [(p.label + (" · missing" if not p.available else ""), p.id) for p in self.runtime.profiles.values() if p.id not in ("shell","ollama","ollama-server")]
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
        if event.button.id and event.button.id.startswith(("setup-","plan-")):
            try:self.setup_action(event.button.id)
            except Exception as error:self.error(error)
        elif event.button.id and event.button.id.startswith("model-"):
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
            names=list(PALETTES)
            self.set_palette(names[(names.index(self.palette)+1)%len(names)])
        elif event.button.id == "voice":
            self.action_tab("setup")
            self.ui("#setup-scroll").scroll_to_widget(self.ui("#voice-status"))

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
        if name not in PALETTES:raise ValueError("Themes: "+", ".join(PALETTES))
        self.palette=name
        with self.prevent(Select.Changed):
            self.ui("#setup-theme",Select).value=name
        self.theme="forge-"+name
        primary,secondary,background=PALETTES[name]
        self.preferences.data["theme"]=name;self.preferences.save()
        self.workspace_screen.styles.background=background
        for selector in ("#rail","#toolbar","#metrics","#masthead","#activity","#model-status"):
            self.ui(selector).styles.background=surface(background,primary,.07)
        for selector in ("#center","#conversation","#terminal-view","#engines","#sessions","#command"):
            self.ui(selector).styles.background=surface(background,primary,.025)
        for selector in ("#engines","#conversation","#activity","#model-table"):
            self.ui(selector).styles.border=("round",surface(background,primary,.55))
        self.ui("#masthead").styles.border_bottom=("heavy",primary)
        self.ui("#command").styles.border=("tall",secondary)
        terminal=self.ui("#terminal-view",TerminalSurface)
        terminal.default_background=surface(background,primary,.025);terminal.refresh()
        self.ui("#model-status").styles.color=primary
        for widget in self.workspace_screen.query("Tabs,Footer"):
            widget.styles.background=surface(background,primary,.07)
        self.ui("#project").styles.background=surface(background,primary,.07)
        self.ui("#toolbar-hint").styles.background=surface(background,primary,.07)
        self.ui("#conversation",RichLog).notify_style_update()
        for widget in self.workspace_screen.query(".rail-title,.setup-section"):
            widget.styles.color=secondary
        self.refresh_state()

    @on(Select.Changed,"#setup-theme")
    def theme_selected(self,event):
        if event.value is not Select.BLANK and getattr(self,"workspace_screen",None):self.set_palette(str(event.value))

    @on(Select.Changed,"#key-provider")
    def key_provider_changed(self,event):
        if event.value is not Select.BLANK and getattr(self,"workspace_screen",None):
            self.ui("#provider-key",Input).value=""
            self.key_status="Provider selected; enter a key or use its native CLI login"

    @on(Select.Changed,"#route-engine")
    def route_engine_changed(self,event):
        if event.value is not Select.BLANK and str(event.value) in self.runtime.profiles:
            self.ui("#route-tier",Select).value=self.runtime.profiles[str(event.value)].tier

    def refresh_setup(self):
        self.ui("#sandbox-status",Static).update(self.runtime.sandbox.summary())
        self.ui("#ruflo-status",Static).update(self.ruflo.state+"\n"+self.ruflo_hint)
        provider=str(self.ui("#key-provider",Select).value)
        self.ui("#provider-install-command",Static).update("INSTALL / "+INSTALL_COMMANDS[provider]+"\nInstall CLI asks before running this official command. npm installs need Node.js; no sudo is added.")
        self.ui("#key-status",Static).update(self.runtime.credentials.storage_label+"\n"+self.key_status)
        self.ui("#planner-status",Static).update(self.planner.state+f" · {len(self.dispatch.grants)} authorized tasks waiting")
        self.ui("#voice-status",Static).update(f"Voice dependencies: {'installed' if self.voice.available else 'not installed'} · prepared {self.voice.model_name or 'none'} · {self.voice.state} · {self.voice.seconds:.1f}s captured")
        self.ui("#setup-ruflo-connect",Button).disabled=self.ruflo.enabled
        self.ui("#setup-ruflo-sync",Button).disabled=not self.ruflo.connected or self.ruflo.busy
        self.ui("#setup-ruflo-close",Button).disabled=not self.ruflo.enabled
        self.ui("#setup-save-key",Button).disabled=self.runtime.credentials.busy
        self.ui("#plan-generate",Button).disabled=self.planner.busy or self.ruflo.busy or self.pending_plan is not None
        self.ui("#setup-voice-prepare",Button).disabled=self.voice.busy or self.voice.recording
        self.ui("#setup-voice-record",Button).disabled=self.voice.busy
        self.ui("#setup-voice-record",Button).label="Stop + transcribe" if self.voice.recording else "Record"
        options=[(p.label,p.id) for p in self.runtime.profiles.values() if p.id not in ("shell","ollama","ollama-server")]
        signature=str(options)
        if self.cache.get("route-options")!=signature:
            self.ui("#route-engine",Select).set_options(options);self.cache["route-options"]=signature

    def setup_action(self,action):
        if action=="setup-sandbox-save":
            policy=self.runtime.sandbox.validate(dict(enabled=self.ui("#sandbox-enabled",Select).value,network=self.ui("#sandbox-network",Select).value,read_only=[v.strip() for v in self.ui("#sandbox-grants",TextArea).text.splitlines() if v.strip()]))
            body=f"Apply permissions to new sessions only? Existing sessions are unchanged; dispatch grants will be cleared. Mode: {'ENFORCE' if policy['enabled'] else 'OFF / full host permissions'}. Network: {'not restricted while mode is OFF' if not policy['enabled'] else 'host network allowed' if policy['network'] else 'blocked'}. Project writable: {self.runtime.store.project}. References read-only:\n"+"\n".join(policy['read_only'])
            self.push_screen(ConfirmScreen("REVIEW FOLDER PERMISSIONS",body),lambda approved:self.save_permissions(policy) if approved else None)
        elif action=="setup-ruflo-connect":
            self.push_screen(ConfirmScreen("CONNECT PINNED RUFLO", "Start installed Ruflo 3.56.9 MCP as trusted host-side software? It can download local embedding weights and index up to 500 project memories on request. No provider keys are passed; no paid model or agent is launched. This does NOT sandbox the Ruflo service itself."),lambda approved:self.connect_ruflo() if approved else None)
        elif action=="setup-ruflo-sync":self.ruflo.request("sync")
        elif action=="setup-ruflo-close":self.ruflo.close();self.pending_plan=None
        elif action=="setup-install-cli":
            provider=str(self.ui("#key-provider",Select).value)
            if provider in ("codex","gemini") and not shutil.which("npm"):
                raise ValueError("Install Node.js LTS / npm first (https://nodejs.org); no system package installer was run")
            command=INSTALL_COMMANDS[provider]
            self.push_screen(ConfirmScreen("INSTALL PROVIDER CLI / official command",f"Run this third-party installer with your current user's permissions? It downloads software and can modify tool directories. No managed API key is passed to the installer. No sudo is added. Review before proceeding.\n\n{command}"),lambda approved:self.install_provider(provider) if approved else None)
        elif action=="setup-save-key":
            widget=self.ui("#provider-key",Input)
            value=widget.value;widget.value=""
            provider=str(self.ui("#key-provider",Select).value)
            persistent=self.ui("#key-storage",Select).value=="vault"
            self.runtime.credentials.save_async(provider,value,persistent)
            self.key_status="Saving key; provider validity has not been checked"
        elif action=="setup-remove-key":
            self.runtime.credentials.remove(str(self.ui("#key-provider",Select).value))
            self.ui("#provider-key",Input).value=""
            self.key_status="Managed key removed; native CLI login/cache is unchanged"
        elif action=="setup-open-cli":
            self.focus_session(self.runtime.launch(str(self.ui("#key-provider",Select).value)))
        elif action=="setup-codex-auth":
            self.push_screen(ConfirmScreen("CODEX API AUTHENTICATION", "Authenticate the installed Codex CLI using the saved OpenAI key through a non-echoed pipe? Codex's own credential store is forced to OS keyring. This can change its active account/login. No model call is made."),lambda approved:self.safe_codex_auth() if approved else None)
        elif action=="setup-route":
            engine=self.ui("#route-engine",Select).value
            if engine is Select.BLANK:raise ValueError("Choose a coding engine")
            path=managed(self.runtime.store.directory,"routing.json")
            value=json.loads(path.read_text()) if path.exists() else {}
            value[str(engine)]=str(self.ui("#route-tier",Select).value)
            temp=managed(self.runtime.store.directory,"routing.json.tmp");temp.write_text(json.dumps(value,indent=2));temp.chmod(0o600);temp.replace(path)
            self.runtime.profiles.update(profiles(self.runtime.store.project))
            self.key_status="Routing tier saved; free is your policy label, not a billing guarantee"
        elif action=="setup-finish":
            self.preferences.data["setup_completed"]=True;self.preferences.save();self.action_tab("models")
        elif action=="setup-voice-prepare":
            model=str(self.ui("#voice-model",Select).value)
            self.push_screen(ConfirmScreen("PREPARE LOCAL DICTATION",f"Download/load the {model} Whisper speech model via faster-whisper? Download requires internet and disk; microphone access happens only after Record. Transcription then runs locally on CPU. Nothing is auto-submitted."),lambda approved:self.prepare_voice(model) if approved else None)
        elif action=="setup-voice-record":
            if self.voice.recording:self.voice.stop()
            else:self.voice.start()
        elif action=="setup-voice-discard":
            self.voice.stop(False)
        elif action=="plan-generate":
            selected=self.ollama.settings.get("selected_model")
            if not selected:raise ValueError("Activate a local operator in Models first")
            goal=self.ui("#planner-goal",TextArea).text
            if self.ruflo.enabled:
                self.ruflo.request("context",goal);self.pending_plan=(selected,goal);self.planner.state="Waiting for Ruflo memory retrieval / advisory route"
            else:self.planner.start(self.ollama.api,selected,goal,self.runtime.store.memories(limit=20))
        elif action=="plan-queue":
            raw=json.loads(self.ui("#planner-draft",TextArea).text)
            draft=validate_plan(raw)
            assignments=[recommend(list(self.runtime.profiles.values()),t['risk']) for t in draft]
            body="Queue these routed tasks without launching them?\n"+"\n".join(f"{i+1}. {t['title']} → {engine or 'NO AVAILABLE ENGINE'} ({t['risk']})" for i,(t,engine) in enumerate(zip(draft,assignments)))
            self.push_screen(ConfirmScreen("REVIEW PLAN / queue only",body),lambda approved:self.safe_queue(draft) if approved else None)
        elif action=="plan-dispatch":self.confirm_dispatch()
        elif action=="plan-pause":self.dispatch.pause()
        self.refresh_setup()

    def save_permissions(self,policy):
        try:
            self.runtime.sandbox.save(policy);self.dispatch.pause();self.refresh_setup()
        except Exception as error:self.error(error)

    def connect_ruflo(self):
        try:self.ruflo.enable()
        except Exception as error:self.error(error)

    def install_provider(self,provider):
        engine="install-"+provider
        try:
            argv=("powershell.exe","-NoLogo","-NoProfile","-Command",INSTALL_COMMANDS[provider]) if os.name=="nt" else ("/bin/bash","-o","pipefail","-c",INSTALL_COMMANDS[provider])
            self.runtime.profiles[engine]=Profile(engine,"Installer / "+provider,argv)
            session=self.runtime.launch(engine)
            self.runtime.profiles.pop(engine,None)
            self.focus_session(session)
        except Exception as error:
            self.runtime.profiles.pop(engine,None)
            self.error(error)

    def safe_codex_auth(self):
        try:self.runtime.credentials.codex_login()
        except Exception as error:self.error(error)

    def prepare_voice(self,model):
        try:
            self.voice.prepare(model)
            self.preferences.data['voice_model']=model;self.preferences.save()
        except Exception as error:self.error(error)

    def safe_queue(self,draft):
        try:
            tasks=queue_plan(self.runtime,draft)
            self.say(f"Queued {len(tasks)} planned tasks; no CLI launched.")
            self.action_tab("missions");self.refresh_state()
        except Exception as error:self.error(error)

    def confirm_dispatch(self):
        tasks=[t for t in self.runtime.store.tasks() if t['status']=='queued'][:20]
        if not tasks:raise ValueError("No queued tasks")
        body=f"Authorize these {len(tasks)} tasks (up to 20 per approval) for automatic ready-task dispatch (maximum two task sessions)? Provider CLIs may incur API charges or use subscriptions. Free labels do not guarantee free calls. Native permissions still apply. Worktrees are not a sandbox; reviews and prerequisite merges remain manual.\n"+"\n".join(t['title']+" → "+t['engine'] for t in tasks[:20])
        def confirmed(approved):
            if approved:
                try:self.dispatch.authorize(self.runtime,tasks)
                except Exception as error:self.error(error)
        self.push_screen(ConfirmScreen("AUTHORIZE DISPATCH / your approval",body),confirmed)

    def show_voice_draft(self,text):
        def insert(result):
            if not result:return
            target,value=result
            try:
                if target=='voice-goal':
                    self.ui("#planner-goal",TextArea).load_text(value);self.action_tab("planning")
                elif target=='voice-composer':
                    self.ui("#command",Input).value=' '.join(value.splitlines());self.action_composer()
                elif target=='voice-cli':
                    if not self.active:raise ValueError("No active CLI; transcript was not submitted")
                    clean=''.join(c if c>=' ' else ' ' for c in value)
                    self.runtime.session(self.active).write(clean)
                    self.focus_session(self.runtime.session(self.active))
            except Exception as error:self.error(error)
        self.push_screen(DictationScreen(text),insert)

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
        if name=="/ruflo":
            operation,_,query=rest.partition(" ")
            if operation=="search":self.ruflo.request("search",query)
            elif operation=="sync":self.ruflo.request("sync")
            elif operation=="off":self.ruflo.close();self.pending_plan=None
            elif operation=="connect":self.setup_action("setup-ruflo-connect")
            else:raise ValueError("/ruflo connect|sync|search QUERY|off")
        elif name=="/sandbox":
            self.action_tab('setup');self.ui('#setup-scroll').scroll_to_widget(self.ui('#sandbox-enabled'))
        elif name=="/setup":self.action_tab("setup")
        elif name=="/plan":
            self.action_tab("planning")
            if rest:self.ui("#planner-goal",TextArea).load_text(rest)
        elif name=="/dispatch":self.confirm_dispatch()
        elif name=="/pause":self.dispatch.pause()
        elif name=="/voice":
            self.action_tab("setup")
            self.ui("#setup-scroll").scroll_to_widget(self.ui("#voice-status"))
        elif name in ("/models", "/tutorial"):
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
