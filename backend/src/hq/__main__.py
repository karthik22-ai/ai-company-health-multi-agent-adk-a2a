"""python -m hq  → run the backend with the settings from the environment / .env"""
import logging

import uvicorn

from hq.core.config import get_settings


def main() -> None:
    s = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(f"\n  AI Company HQ backend\n  UI        http://{s.host}:{s.port}/\n  API docs  http://{s.host}:{s.port}/docs\n"
          f"  LLM       {s.llm_label}\n")
    uvicorn.run("hq.main:app", host=s.host, port=s.port, log_level="info")


if __name__ == "__main__":
    main()
