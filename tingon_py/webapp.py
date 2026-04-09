import importlib


def main():
    try:
        module = importlib.import_module("tingon_py.webapp_impl")
    except ModuleNotFoundError as exc:
        missing = exc.name or "web dependency"
        if missing in {"fastapi", "uvicorn", "pydantic"}:
            raise SystemExit(
                "tingon-web requires the optional web dependencies. Install them with: pip install tingon-py[web]"
            ) from exc
        raise
    module.main()


if __name__ == "__main__":
    main()
