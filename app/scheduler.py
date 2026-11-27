"""Single low-volume ingestion worker; run once at boot and every 12 hours."""

import logging
from threading import Event

from app.ingest import run

INTERVAL_SECONDS = 12 * 60 * 60


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            logging.info("Ingesta terminada: %s", run())
        except Exception:
            logging.exception("Falló la ingesta; se reintentará en 12 horas")
        Event().wait(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
