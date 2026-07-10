from sciplot.app import guarded_main, main, run_gui_smoke_test, run_smoke_test

__all__ = ["main", "run_smoke_test", "run_gui_smoke_test"]


if __name__ == "__main__":
    raise SystemExit(guarded_main())
