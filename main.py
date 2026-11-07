"""Launch VIGILENS desktop application."""
import sys


def main():
    try:
        from ui.app import run_app
        run_app()
    except ModuleNotFoundError as exc:
        missing = exc.name or "a required package"
        print(f"VIGILENS could not start because {missing!r} is not installed.")
        print("Activate your virtual environment and run: pip install -r requirements.txt")
        raise


if __name__ == "__main__":
    main()
