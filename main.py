"""Camunda 8 SaaS Worker for Premiumkreditkarte."""

import asyncio
import logging
import os

from grpc import aio as grpc_aio
from dotenv import load_dotenv
from pyzeebe import ZeebeWorker, create_camunda_cloud_channel

import db
import workers

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")

# pyzeebe loggt DEADLINE_EXCEEDED als WARNING wenn keine Jobs anstehen – das ist normal
logging.getLogger("pyzeebe.worker.job_poller").setLevel(logging.ERROR)

# gRPC-Keepalive: verhindert dass die Verbindung zu Camunda SaaS nach Inaktivität stirbt
GRPC_OPTIONS = [
    ("grpc.keepalive_time_ms", 60_000),          # Ping alle 60s
    ("grpc.keepalive_timeout_ms", 10_000),        # 10s auf Pong warten
    ("grpc.keepalive_permit_without_calls", 1),   # Auch pingen wenn keine Requests laufen
    ("grpc.http2.max_pings_without_data", 0),     # Unbegrenzt Pings ohne Daten
]


def create_worker() -> ZeebeWorker:
    channel = create_camunda_cloud_channel(
        client_id=os.environ["CAMUNDA_CLIENT_ID"],
        client_secret=os.environ["CAMUNDA_CLIENT_SECRET"],
        cluster_id=os.environ["CAMUNDA_CLUSTER_ID"],
        region=os.getenv("CAMUNDA_REGION", "bru-2"),
        channel_options=GRPC_OPTIONS,
    )
    worker = ZeebeWorker(channel, request_timeout=30000)

    worker.task(task_type="validate-card")(workers.validate_card)
    worker.task(task_type="activate-card")(workers.activate_card)
    worker.task(task_type="set-pin")(workers.set_pin)
    worker.task(task_type="lock-card")(workers.lock_card)
    worker.task(task_type="check-lock-status")(workers.check_lock_status)
    worker.task(task_type="send-mail")(workers.send_mail)
    worker.task(task_type="process-transaction")(workers.process_transaction)
    worker.task(task_type="create-insurance-offer")(workers.create_insurance_offer)
    worker.task(task_type="activate-insurance")(workers.activate_insurance)

    return worker


async def main():
    db_path = os.getenv("DB_PATH", "premiumkreditkarte.db")
    db.init(db_path)
    logger.info("Datenbank initialisiert: %s", db_path)

    worker = create_worker()
    logger.info("Worker gestartet – warte auf Jobs...")
    await worker.work()


if __name__ == "__main__":
    asyncio.run(main())
