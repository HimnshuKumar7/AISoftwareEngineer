import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%Y-%m-%dT%H:%M:%S%z")
    )
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Keep third-party chatter down.
    for noisy in ("httpx", "httpcore", "urllib3", "sentence_transformers", "faiss.loader"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
