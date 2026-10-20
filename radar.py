"""Compatibility entry point; no legacy demo/send path exists in production."""

from radar_gamer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
