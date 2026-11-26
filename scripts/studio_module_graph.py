"""Single source of truth for Studio's ordered, explicitly approved JS modules.

All modules remain self-contained IIFEs or their existing reviewed scripts. The
manifest makes runtime global dependencies visible without adding a loader,
new network requests, dynamic evaluation, or changes to the generated bundle.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re


MARKER_RE = re.compile(r"/\*STUDIO_[A-Z_]+\*/")
SYMBOL_RE = re.compile(r"\bNexus[A-Za-z0-9_]+\b")
EXPORT_RE = re.compile(r"(?:root|window|globalThis)\.(Nexus[A-Za-z0-9_]+)\s*=")
# The optional device model is loaded separately only by the installable site.
EXTERNAL_DEFERRED = frozenset({"NexusDevice"})


@dataclass(frozen=True, slots=True)
class Module:
    marker: str
    filename: str
    provides: str | None = None
    requires: tuple[str, ...] = ()
    deferred: tuple[str, ...] = ()


MODULES = (
    Module("/*STUDIO_TABLE*/", "table-core.js", "NexusTable"),
    Module("/*STUDIO_ASTRONOMY_VENDOR*/", "vendor/astronomy-2.1.19.min.js"),
    Module("/*STUDIO_ASTROLOGY*/", "studio-astrology.js", "NexusAstrology"),
    Module("/*STUDIO_SKY*/", "studio-sky.js", "NexusSky", ("NexusAstrology",)),
    Module("/*STUDIO_CORE*/", "studio-core.js", "NexusStudio", ("NexusAstrology", "NexusSky")),
    Module("/*STUDIO_LAB*/", "studio-lab.js", "NexusLab"),
    Module("/*STUDIO_TASKS*/", "studio-tasks.js", "NexusTasks", ("NexusLab",)),
    Module("/*STUDIO_LOCALES*/", "studio-locales.js", "NexusLocales"),
    Module("/*STUDIO_REPLY_FORMAT*/", "studio-reply-format.js", "NexusReplyFormat"),
    Module("/*STUDIO_OFFICE_ZIP*/", "studio-office-zip.js", "NexusOfficeZip"),
    Module("/*STUDIO_APP*/", "studio-app.js", "NexusStudioUI",
           ("NexusStudio", "NexusLocales", "NexusAstrology", "NexusReplyFormat", "NexusOfficeZip"),
           ("NexusSpeechPlayback", "NexusLabUI", "NexusTasksUI", "NexusAstrologyUI", "NexusQualityUI", "NexusDevice", "NexusCalendar", "NexusMusicUI", "NexusOrchestraUI", "NexusStudioVision", "NexusStudioFocus")),
    Module("/*STUDIO_LAB_UI*/", "studio-lab-ui.js", "NexusLabUI", ("NexusLab", "NexusStudioUI"), ("NexusMusicUI",)),
    Module("/*STUDIO_TASKS_UI*/", "studio-tasks-ui.js", "NexusTasksUI", ("NexusTasks",)),
    Module("/*STUDIO_ASTROLOGY_UI*/", "studio-astrology-ui.js", "NexusAstrologyUI",
           ("NexusAstrology", "NexusSky")),
    Module("/*STUDIO_SKY_UI*/", "studio-sky-ui.js", None, ("NexusSky",)),
    Module("/*STUDIO_QUALITY_UI*/", "studio-quality-ui.js", "NexusQualityUI",
           ("NexusTable", "NexusLabUI", "NexusStudioUI"), ("NexusMusicUI",)),
    Module("/*STUDIO_FOCUS_UI*/", "studio-focus-ui.js", "NexusStudioFocus", ("NexusStudioUI",)),
    Module("/*STUDIO_COMPOSER_UI*/", "studio-composer-ui.js", "NexusStudioCompose",
           ("NexusStudio", "NexusStudioUI", "NexusStudioFocus"), ("NexusStudioConnections",)),
    Module("/*STUDIO_VISION_UI*/", "studio-vision-ui.js", "NexusStudioVision", ("NexusStudioUI",)),
    Module("/*STUDIO_SPEECH_PLAYBACK*/", "studio-speech-playback.js", "NexusSpeechPlayback"),
    Module("/*STUDIO_VOICE_UI*/", "studio-voice-ui.js", None, ("NexusStudioUI", "NexusSpeechPlayback")),
    Module("/*STUDIO_CALENDAR*/", "studio-calendar.js", "NexusCalendar"),
    Module("/*STUDIO_CONNECTIONS_UI*/", "studio-connections-ui.js",
           "NexusStudioConnections", ("NexusStudioUI", "NexusStudioFocus")),
    Module("/*STUDIO_MUSIC_AUDIO*/", "studio-music-audio.js", "NexusMusicAudio"),
    Module("/*STUDIO_MUSIC*/", "studio-music.js", "NexusMusic", ("NexusMusicAudio",)),
    Module("/*STUDIO_MUSIC_UI*/", "studio-music-ui.js", "NexusMusicUI", ("NexusMusic",)),
    Module("/*STUDIO_ORCHESTRA*/", "studio-orchestra.js", "NexusOrchestra"),
    Module("/*STUDIO_VOCAL_MIX*/", "studio-vocal-mix.js", "NexusVocalMix"),
    Module("/*STUDIO_ORCHESTRA_UI*/", "studio-orchestra-ui.js", "NexusOrchestraUI",
           ("NexusOrchestra", "NexusVocalMix", "NexusMusicUI")),
)


def validate_module_graph(shell: str, web: Path, modules: tuple[Module, ...] = MODULES) -> tuple[Module, ...]:
    """Refuse missing slots, unreviewed global coupling, or invalid load order.

    'requires' are global exports that must already exist at script evaluation.
    'deferred' are intentionally late references; all must be known reviewed
    exports or the one separately loaded device API. The lexical check is a
    conservative guardrail, not a replacement for browser integration tests.
    """
    markers = [item.marker for item in modules]
    paths = [item.filename for item in modules]
    providers = [item.provides for item in modules if item.provides]
    if len(set(markers)) != len(markers) or len(set(paths)) != len(paths):
        raise ValueError("duplicate Studio module slot or source path")
    if len(set(providers)) != len(providers):
        raise ValueError("duplicate Studio global provider")
    for item in modules:
        path = PurePosixPath(item.filename)
        if (path.is_absolute() or ".." in path.parts or "." in path.parts or
                not item.filename or "\\" in item.filename or
                not MARKER_RE.fullmatch(item.marker)):
            raise ValueError("invalid Studio module source path or marker")
    expected = set(markers) | {"/*STUDIO_THEME*/"}
    actual = MARKER_RE.findall(shell)
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("missing, duplicated or unreviewed Studio module marker")
    locations = [shell.index(item.marker) for item in modules]
    if locations != sorted(locations):
        raise ValueError("Studio module slots are out of reviewed loading order")

    seen_providers: set[str] = set()
    approved_providers = set(providers)
    for item in modules:
        file = web / item.filename
        if not file.is_file() or not file.resolve().is_relative_to(web.resolve()):
            raise ValueError("missing or escaped Studio module source: " + item.filename)
        source = file.read_text(encoding="utf-8")
        exported = set(EXPORT_RE.findall(source))
        expected_exported = {item.provides} if item.provides else set()
        if exported != expected_exported:
            raise ValueError("undeclared or missing Studio module global export: " + item.filename)
        required = set(item.requires)
        deferred = set(item.deferred)
        if len(required) != len(item.requires) or len(deferred) != len(item.deferred):
            raise ValueError("duplicate declared Studio dependency")
        if required & deferred or required - seen_providers:
            raise ValueError("Studio module has a forward or conflicting eager dependency: " + item.filename)
        if deferred - (approved_providers | EXTERNAL_DEFERRED):
            raise ValueError("Studio module has an unknown deferred dependency: " + item.filename)
        observed = set(SYMBOL_RE.findall(source))
        approved = required | deferred | expected_exported
        if observed != approved:
            raise ValueError("undeclared or obsolete Studio global dependency: " + item.filename)
        seen_providers.update(expected_exported)
    return modules
