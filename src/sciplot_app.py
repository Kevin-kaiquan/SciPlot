from __future__ import annotations


def main() -> int:
    from sciplot_launcher import guarded_main as launcher_main

    return launcher_main()


def guarded_main() -> int:
    return main()


def run_smoke_test() -> None:
    from sciplot.app import run_smoke_test as app_smoke_test

    app_smoke_test()


def run_gui_smoke_test() -> None:
    from sciplot.app import run_gui_smoke_test as app_gui_smoke_test

    app_gui_smoke_test()


def run_updater_smoke_test() -> None:
    from sciplot.app import run_updater_smoke_test as app_updater_smoke_test

    app_updater_smoke_test()


__all__ = ["main", "guarded_main", "run_smoke_test", "run_gui_smoke_test", "run_updater_smoke_test"]


if __name__ == "__main__":
    raise SystemExit(main())
