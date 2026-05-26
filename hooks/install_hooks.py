"""
Hook Installer
==============

Installs the post-commit hook into configured repos.
The hook calls the commit ingestor for each new commit.

CLI:
    python -m hooks.install_hooks
    python -m hooks.install_hooks --dry-run
"""

import argparse
import logging
import shutil
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings

logger = logging.getLogger(__name__)

HOOK_SOURCE = Path(__file__).parent / "post-commit"


def install_hook(repo_path: Path, dry_run: bool = False) -> bool:
    """Install the post-commit hook into a git repo."""
    hooks_dir = repo_path / ".git" / "hooks"
    if not hooks_dir.exists():
        logger.error("Not a git repo (no .git/hooks): %s", repo_path)
        return False

    target = hooks_dir / "post-commit"

    # Check for existing hook
    if target.exists():
        # Check if it's our hook
        existing_content = target.read_text(encoding="utf-8", errors="replace")
        if "dev-brain" in existing_content.lower() or "Dev Brain" in existing_content:
            logger.info("Hook already installed at %s", target)
            return True
        else:
            logger.warning(
                "Existing post-commit hook at %s — backing up to post-commit.bak", target
            )
            if not dry_run:
                shutil.copy2(target, target.with_suffix(".bak"))

    if dry_run:
        logger.info("[DRY RUN] Would install hook to %s", target)
        return True

    # Copy hook
    shutil.copy2(HOOK_SOURCE, target)

    # Make executable
    target.chmod(target.stat().st_mode | stat.S_IEXEC)

    logger.info("Hook installed at %s", target)
    return True


def main():
    parser = argparse.ArgumentParser(description="Install Dev Brain git hooks")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    settings = get_settings()
    repos = []

    if settings.PRIMARY_REPO_PATH:
        repos.append(("primary", Path(settings.PRIMARY_REPO_PATH)))
    if settings.SECONDARY_REPO_PATH:
        repos.append(("secondary", Path(settings.SECONDARY_REPO_PATH)))

    if not repos:
        logger.error("No repo paths configured. Set PRIMARY_REPO_PATH and/or SECONDARY_REPO_PATH in .env")
        return

    for name, path in repos:
        logger.info("Installing hook for %s at %s", name, path)
        success = install_hook(path, dry_run=args.dry_run)
        if not success:
            logger.error("Failed to install hook for %s", name)


if __name__ == "__main__":
    main()
