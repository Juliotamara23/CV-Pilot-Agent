"""Clean up temporary files created by CV-Pilot during task execution.

Removes all files and subdirectories inside ``cv-pilot-agent/temp/``,
preserving the ``.gitkeep`` marker. Designed to be invoked by the agent
after completing any task that wrote temporary artifacts (drafts, scrapes,
generated scripts, etc.).
"""

from pathlib import Path
import shutil
import sys

TEMP_DIR = Path(__file__).resolve().parent.parent / "temp"


def cleanup() -> None:
    if not TEMP_DIR.is_dir():
        print(f"temp dir not found: {TEMP_DIR}", file=sys.stderr)
        sys.exit(1)

    removed = 0
    for item in TEMP_DIR.iterdir():
        if item.name == ".gitkeep":
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed += 1
        except OSError as exc:
            print(f"Failed to remove {item}: {exc}", file=sys.stderr)

    print(f"Cleaned {removed} item(s) from {TEMP_DIR}")


if __name__ == "__main__":
    cleanup()
