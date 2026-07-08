#!/usr/bin/env python
"""Django management entry point."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cocoweb.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install the 'web' extra: uv sync --extra web"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
