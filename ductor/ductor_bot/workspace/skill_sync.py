"""Cross-platform skill directory sync between ductor workspace and CLI tools.

Provides multi-way symlink synchronization so skills installed via Claude Code,
Codex CLI, Gemini CLI, or the ductor workspace are visible to all agents.

Includes bundled-skill linking (package → workspace), sync-time external-symlink
protection, and cleanup of ductor-created links on shutdown.

When Docker sandboxing is active, symlinks are replaced with directory copies
(marked with ``.ductor_managed``) because absolute host paths do not resolve
inside the container's mount namespace.

Sync runs once during ``init_workspace`` and periodically as a background task.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ductor_bot.workspace.paths import DuctorPaths

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"

_SKIP_DIRS: frozenset[str] = frozenset(
    {".claude", ".system", ".git", ".venv", "__pycache__", "node_modules"}
)

_SKILL_SYNC_INTERVAL = 30.0
_MANAGED_MARKER = ".ductor_managed"
_RULE_DOCS = frozenset({"AGENTS.md", "CLAUDE.md", "GEMINI.md"})
_ROSTER_PATTERN = re.compile(r"- `([^`]+)`")
_CODEX_HOME_FILES = frozenset({"auth.json", "config.toml", "installation_id", "version.json"})
_CODEX_HOME_DIRS = frozenset({"plugins", "rules", "vendor_imports"})
_CODEX_SYSTEM_SKILL = ".system"


def _is_under(child: Path, parent: Path) -> bool:
    """Return ``True`` if *child* is located under *parent* directory."""
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    else:
        return True


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _discover_skills(base: Path) -> dict[str, Path]:
    """Scan a skills directory and return ``{name: path}`` for valid entries.

    Skips hidden/internal directories and broken symlinks.
    Only includes subdirectories (plain files are ignored).
    """
    if not base.is_dir():
        return {}
    skills: dict[str, Path] = {}
    for entry in sorted(base.iterdir()):
        if entry.name.startswith(".") or entry.name in _SKIP_DIRS:
            continue
        if entry.is_symlink():
            if entry.exists():
                skills[entry.name] = entry
            continue
        if entry.is_dir():
            skills[entry.name] = entry
    return skills


def _cli_skill_dirs() -> dict[str, Path]:
    """Return skill directories for installed CLIs.

    Only includes CLIs whose home directory exists on disk.
    Uses the same detection pattern as ``cli/auth.py``.
    """
    dirs: dict[str, Path] = {}
    claude_home = Path.home() / ".claude"
    if claude_home.is_dir():
        dirs["claude"] = claude_home / "skills"
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    if codex_home.is_dir():
        dirs["codex"] = codex_home / "skills"
    gemini_home = Path.home() / ".gemini"
    if gemini_home.is_dir():
        dirs["gemini"] = gemini_home / "skills"
    return dirs


def _effective_codex_home() -> Path:
    """Return the host Codex home used as the auth/config source."""
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()


def _parse_skill_roster(roster_path: Path) -> list[str]:
    """Return skill ids listed in a SkillRoster markdown file."""
    if not roster_path.is_file():
        return []
    skills: list[str] = []
    in_default_block = False
    for line in roster_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_default_block = "Default-first skills" in line
            continue
        if not in_default_block:
            continue
        match = _ROSTER_PATTERN.search(line)
        if match:
            skills.append(match.group(1))
    return skills


def _ductor_allowed_skills(paths: DuctorPaths) -> set[str] | None:
    """Return allowed skill names for a ductor workspace with a local roster.

    Any workspace that defines ``memory_system/profile/SkillRoster.md`` uses it
    as the default publication allow-list, while preserving real local skill
    directories already present in the workspace.
    """
    roster_path = paths.memory_system_dir / "profile" / "SkillRoster.md"
    allowed = set(_parse_skill_roster(roster_path))
    if not allowed:
        return None

    if paths.skills_dir.is_dir():
        for entry in paths.skills_dir.iterdir():
            if entry.name in _RULE_DOCS or entry.name.startswith(".") or entry.name in _SKIP_DIRS:
                continue
            if entry.exists() and not entry.is_symlink():
                allowed.add(entry.name)
    return allowed


# ---------------------------------------------------------------------------
# Canonical resolution
# ---------------------------------------------------------------------------


def _resolve_canonical(
    name: str,
    *registries: dict[str, Path],
) -> Path | None:
    """Find the canonical (real, non-symlink) path for a skill.

    Priority follows argument order (typically ductor > claude > codex > gemini).
    Falls back to resolving the first valid symlink if no real dir exists.
    """
    for registry in registries:
        entry = registry.get(name)
        if entry is not None and not entry.is_symlink():
            return entry
    for registry in registries:
        entry = registry.get(name)
        if entry is not None and entry.is_symlink() and entry.exists():
            return entry.resolve()
    return None


# ---------------------------------------------------------------------------
# Cross-platform symlink creation
# ---------------------------------------------------------------------------


def _create_dir_link(link_path: Path, target: Path) -> None:
    """Create a directory symlink with Windows junction fallback.

    Linux/macOS/WSL: standard ``os.symlink``.
    Windows: tries ``os.symlink`` (requires Developer Mode or admin),
    then falls back to NTFS junction via ``mklink /J`` (no admin needed).
    """
    if not _IS_WINDOWS:
        link_path.symlink_to(target)
        return

    try:
        link_path.symlink_to(target, target_is_directory=True)
    except OSError:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_path), str(target)],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            msg = f"Failed to create symlink or junction: {link_path} -> {target}"
            raise OSError(msg) from None


def _ensure_link(link_path: Path, target: Path) -> bool:
    """Idempotently ensure *link_path* is a symlink to *target*.

    Returns ``True`` if a new link was created, ``False`` if already correct
    or if *link_path* is a real directory (never destroyed).
    """
    if link_path.exists() and not link_path.is_symlink():
        return False
    if link_path.is_symlink():
        if link_path.resolve() == target.resolve():
            return False
        link_path.unlink()
    _create_dir_link(link_path, target)
    return True


# ---------------------------------------------------------------------------
# Docker-aware copy helpers
# ---------------------------------------------------------------------------


def _is_managed_copy(path: Path) -> bool:
    """Return ``True`` if *path* is a ductor-managed copy (has marker file)."""
    return path.is_dir() and not path.is_symlink() and (path / _MANAGED_MARKER).is_file()


def _newest_mtime(directory: Path) -> float:
    """Return the newest mtime of any file or directory under *directory*.

    Tolerates files disappearing during iteration (concurrent modifications).
    """
    newest = directory.stat().st_mtime
    for entry in directory.rglob("*"):
        try:
            newest = max(newest, entry.stat().st_mtime)
        except OSError:
            continue
    return newest


def _ensure_copy(dest: Path, source: Path) -> bool:
    """Copy *source* directory to *dest* with a ``.ductor_managed`` marker.

    Skips the copy when *dest* already has the marker and *source* has not
    been modified since the last copy (recursive mtime comparison).

    Tolerates concurrent modifications from other agents running skill sync
    in parallel (marker may vanish between check and stat, rmtree may race
    with Python's import machinery or another agent's copytree).

    Returns ``True`` if a new copy was made.
    """
    marker = dest / _MANAGED_MARKER
    if _is_managed_copy(dest):
        try:
            if _newest_mtime(source) <= marker.stat().st_mtime:
                return False
        except OSError:
            pass  # marker removed concurrently — proceed with fresh copy
        shutil.rmtree(dest, ignore_errors=True)
    elif dest.exists() and not dest.is_symlink():
        return False

    if dest.is_symlink():
        dest.unlink()

    shutil.copytree(source, dest, symlinks=True, dirs_exist_ok=True)
    marker.touch()
    return True


def _ensure_file_copy(dest: Path, source: Path) -> bool:
    """Copy *source* file to *dest* when missing or stale."""
    if not source.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        dest.unlink()
    elif dest.exists() and dest.is_dir():
        return False

    src_stat = source.stat()
    if dest.is_file():
        dst_stat = dest.stat()
        if dst_stat.st_size == src_stat.st_size and dst_stat.st_mtime_ns >= src_stat.st_mtime_ns:
            return False

    shutil.copy2(source, dest)
    return True


def _visible_workspace_skills(skills_dir: Path) -> dict[str, Path]:
    """Return visible runtime skills from the workspace publication layer."""
    if not skills_dir.is_dir():
        return {}
    visible: dict[str, Path] = {}
    for entry in sorted(skills_dir.iterdir()):
        if entry.name in _RULE_DOCS or entry.name.startswith(".") or entry.name in _SKIP_DIRS:
            continue
        if not entry.exists():
            continue
        visible[entry.name] = entry.resolve() if entry.is_symlink() else entry
    return visible


def _trim_managed_skill_surface(skills_dir: Path, allowed_names: set[str]) -> int:
    """Trim stale managed Codex skill links that no longer belong in the surface."""
    if not skills_dir.is_dir():
        return 0
    removed = 0
    for entry in skills_dir.iterdir():
        if entry.name in allowed_names:
            continue
        if entry.is_symlink():
            entry.unlink()
            removed += 1
            continue
        if _is_managed_copy(entry):
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed


def sync_managed_codex_home(paths: DuctorPaths) -> None:
    """Project a narrow per-runtime Codex home for Ductor-launched Codex sessions.

    The managed home keeps authentication/config/plugin state from the user's
    host Codex installation, but rebuilds the skill surface from the runtime's
    own published `workspace/skills` plus Codex built-ins from `.system`.
    """
    managed_home = paths.codex_home_dir
    managed_home.mkdir(parents=True, exist_ok=True)
    source_home = _effective_codex_home()
    source_is_managed = source_home.exists() and source_home.resolve() == managed_home.resolve()

    copied = 0
    linked = 0

    if not source_is_managed:
        for name in sorted(_CODEX_HOME_FILES):
            try:
                if _ensure_file_copy(managed_home / name, source_home / name):
                    copied += 1
            except OSError:
                logger.warning("Failed to sync managed Codex file %s", name, exc_info=True)

        for name in sorted(_CODEX_HOME_DIRS):
            source_dir = source_home / name
            dest_dir = managed_home / name
            if not source_dir.is_dir():
                continue
            if dest_dir == source_dir:
                continue
            try:
                if _ensure_link(dest_dir, source_dir):
                    linked += 1
            except OSError:
                logger.warning("Failed to sync managed Codex dir %s", name, exc_info=True)

    managed_skills_dir = paths.codex_skills_dir
    managed_skills_dir.mkdir(parents=True, exist_ok=True)

    keep_names: set[str] = set()

    system_skill = source_home / "skills" / _CODEX_SYSTEM_SKILL
    if not source_is_managed and system_skill.is_dir():
        keep_names.add(_CODEX_SYSTEM_SKILL)
        try:
            if _ensure_link(managed_skills_dir / _CODEX_SYSTEM_SKILL, system_skill):
                linked += 1
        except OSError:
            logger.warning("Failed to sync managed Codex built-ins", exc_info=True)

    for skill_name, source in _visible_workspace_skills(paths.skills_dir).items():
        keep_names.add(skill_name)
        try:
            if _ensure_link(managed_skills_dir / skill_name, source):
                linked += 1
        except OSError:
            logger.warning("Failed to sync managed Codex skill %s", skill_name, exc_info=True)

    trimmed = _trim_managed_skill_surface(managed_skills_dir, keep_names)
    cleaned = _clean_broken_links(managed_skills_dir)

    if copied or linked or trimmed or cleaned:
        logger.info(
            "Managed Codex home sync applied %d file copy(s), %d link(s), trimmed %d skill entry(s), cleaned %d broken link(s)",
            copied,
            linked,
            trimmed,
            cleaned,
        )


# ---------------------------------------------------------------------------
# Broken link cleanup
# ---------------------------------------------------------------------------


def _clean_broken_links(directory: Path) -> int:
    """Remove broken symlinks in *directory*. Returns count removed."""
    if not directory.is_dir():
        return 0
    removed = 0
    for entry in directory.iterdir():
        if entry.is_symlink() and not entry.exists():
            entry.unlink()
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _should_skip_link(dest: Path, sync_roots: frozenset[Path]) -> bool:
    """Return ``True`` if *dest* should be left alone during symlink sync."""
    if dest.exists() and not dest.is_symlink():
        return True
    if dest.is_symlink() and dest.exists():
        resolved = dest.resolve()
        return not any(_is_under(resolved, root) for root in sync_roots)
    return False


def _should_skip_copy(dest: Path) -> bool:
    """Return ``True`` if *dest* should be left alone during copy sync."""
    return dest.exists() and not dest.is_symlink() and not _is_managed_copy(dest)


def _link_skill_everywhere(
    skill_name: str,
    canonical: Path,
    all_dirs: dict[str, Path],
    *,
    use_copies: bool = False,
    allowed_ductor_skills: set[str] | None = None,
) -> int:
    """Create symlinks (or copies) for *skill_name* in every location that lacks it.

    Preserves existing symlinks that point outside the known sync directories
    (user-managed external links are never touched).

    When *use_copies* is ``True`` (Docker mode), directories are copied
    instead of symlinked so they resolve inside the container.
    """
    sync_roots = frozenset(d.resolve() for d in all_dirs.values() if d.is_dir())
    synced = 0
    for loc_name, base_dir in all_dirs.items():
        if (
            loc_name == "ductor"
            and allowed_ductor_skills is not None
            and skill_name not in allowed_ductor_skills
        ):
            continue
        if not base_dir.is_dir():
            base_dir.mkdir(parents=True, exist_ok=True)
        dest = base_dir / skill_name
        if dest == canonical:
            continue
        skip = _should_skip_copy(dest) if use_copies else _should_skip_link(dest, sync_roots)
        if skip:
            continue
        try:
            if use_copies:
                if _ensure_copy(dest, canonical):
                    logger.debug("Skill copied: %s -> %s", dest, canonical)
                    synced += 1
            elif _ensure_link(dest, canonical):
                logger.debug("Skill link created: %s -> %s", dest, canonical)
                synced += 1
        except OSError:
            logger.warning("Failed to sync skill %s in %s", skill_name, loc_name, exc_info=True)
    return synced


def _trim_ductor_surface(skills_dir: Path, allowed_names: set[str]) -> int:
    """Remove disallowed symlinked or managed-copy skills from ductor workspace."""
    if not skills_dir.is_dir():
        return 0
    removed = 0
    for entry in skills_dir.iterdir():
        if entry.name in _RULE_DOCS or entry.name.startswith(".") or entry.name in _SKIP_DIRS:
            continue
        if entry.name in allowed_names:
            continue
        if entry.is_symlink():
            entry.unlink()
            removed += 1
            continue
        if _is_managed_copy(entry):
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed


def sync_skills(paths: DuctorPaths, *, docker_active: bool = False) -> None:
    """Multi-way skill directory sync: ductor workspace <-> CLI skill dirs.

    Syncs between ductor workspace, ~/.claude/skills, ~/.codex/skills,
    and ~/.gemini/skills.

    When *docker_active* is ``True``, copies are used instead of symlinks
    so skills resolve inside the Docker container.

    Safety guarantees:
    - Real directories are never overwritten or removed.
    - Existing valid symlinks pointing elsewhere are left alone.
    - Internal directories (.system, .claude, .git, .venv) are skipped.
    """
    cli_dirs = _cli_skill_dirs()
    all_dirs: dict[str, Path] = {"ductor": paths.skills_dir, **cli_dirs}
    allowed_ductor_skills = _ductor_allowed_skills(paths)

    registries = {name: _discover_skills(d) for name, d in all_dirs.items()}

    all_names: set[str] = set()
    for reg in registries.values():
        all_names.update(reg.keys())

    # Priority order: ductor > claude > codex > gemini
    priority = ("ductor", "claude", "codex", "gemini")
    synced = 0
    for skill_name in sorted(all_names):
        canonical = _resolve_canonical(
            skill_name,
            *(registries.get(n, {}) for n in priority),
        )
        if canonical is not None:
            synced += _link_skill_everywhere(
                skill_name,
                canonical,
                all_dirs,
                use_copies=docker_active,
                allowed_ductor_skills=allowed_ductor_skills,
            )

    trimmed = 0
    if allowed_ductor_skills is not None:
        trimmed = _trim_ductor_surface(paths.skills_dir, allowed_ductor_skills)
        if trimmed:
            logger.info("Trimmed %d skill surface entry(s) in %s", trimmed, paths.skills_dir)

    cleaned_total = 0
    for base_dir in all_dirs.values():
        removed = _clean_broken_links(base_dir)
        cleaned_total += removed
        if removed:
            logger.info("Cleaned %d broken skill link(s) in %s", removed, base_dir)

    sync_managed_codex_home(paths)

    if synced or trimmed or cleaned_total:
        logger.info(
            "Skill sync applied %d update(s), trimmed %d entry(s), cleaned %d broken link(s)",
            synced,
            trimmed,
            cleaned_total,
        )


def _iter_bundled_entries(paths: DuctorPaths) -> list[tuple[Path, Path]]:
    """Return ``(source, target)`` pairs for each bundled skill."""
    bundled = paths.bundled_skills_dir
    if not bundled.is_dir():
        return []
    target_dir = paths.skills_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[tuple[Path, Path]] = []
    for entry in sorted(bundled.iterdir()):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name in _SKIP_DIRS:
            continue
        pairs.append((entry, target_dir / entry.name))
    return pairs


def sync_bundled_skills(paths: DuctorPaths, *, docker_active: bool = False) -> None:
    """Sync bundled skills from the package into the ductor workspace.

    Creates symlinks (or copies when *docker_active*) from
    ``~/.ductor/workspace/skills/<name>`` to the package's
    ``_home_defaults/workspace/skills/<name>`` so bundled skills
    stay up-to-date with the installed ductor version.

    Real directories are never overwritten (preserves user modifications
    from older Zone 3 copies or manually created skills with the same name).
    """
    synced = 0
    for source, target in _iter_bundled_entries(paths):
        if docker_active:
            try:
                if _ensure_copy(target, source):
                    logger.debug("Bundled skill copied: %s -> %s", target, source)
                    synced += 1
            except OSError:
                logger.warning("Failed to copy bundled skill %s", source.name, exc_info=True)
            continue

        if target.exists() and not target.is_symlink():
            continue
        if target.is_symlink():
            if target.resolve() == source.resolve():
                continue
            target.unlink()
        try:
            _create_dir_link(target, source)
            logger.debug("Bundled skill linked: %s -> %s", target, source)
            synced += 1
        except OSError:
            logger.warning("Failed to link bundled skill %s", source.name, exc_info=True)

    if synced:
        logger.info("Bundled skill sync applied %d update(s)", synced)


def cleanup_ductor_links(paths: DuctorPaths) -> int:
    """Remove symlinks created by ductor in CLI skill directories.

    Only removes symlinks whose resolved target is under the ductor workspace
    skills directory or the bundled skills directory.  Everything else
    (real directories, user-managed symlinks) is left untouched.

    Returns the total count of removed links.
    """
    managed_roots = [paths.skills_dir]
    bundled = paths.bundled_skills_dir
    if bundled.is_dir():
        managed_roots.append(bundled)

    removed = 0
    for cli_dir in _cli_skill_dirs().values():
        if not cli_dir.is_dir():
            continue
        for entry in cli_dir.iterdir():
            if not entry.is_symlink():
                continue
            try:
                resolved = entry.resolve()
            except OSError:
                continue
            if any(_is_under(resolved, root) for root in managed_roots):
                entry.unlink()
                removed += 1
                logger.info("Removed ductor skill link: %s", entry)

    if removed:
        logger.info("Cleaned up %d ductor skill link(s) from CLI directories", removed)
    return removed


async def watch_skill_sync(
    paths: DuctorPaths,
    *,
    docker_active: bool = False,
    interval: float = _SKILL_SYNC_INTERVAL,
) -> None:
    """Continuously sync skill directories across all agents.

    Runs ``sync_skills`` in a thread every *interval* seconds.
    Follows the same pattern as ``watch_rule_files``.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(sync_skills, paths, docker_active=docker_active)
        except Exception:
            logger.exception("Skill sync failed")
