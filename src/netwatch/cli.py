from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .database import export_csv, initialize, insert_result
from .measure import collect


LOG = logging.getLogger("netwatch")


def perform_test(settings: Settings) -> int:
    LOG.info("Starting network measurement")
    result = collect(settings)
    run_id = insert_result(settings.database_url, result)
    LOG.info(
        "Stored run %s: %.2f Mbps down, %.2f Mbps up, DNS %s loss %.2f%%",
        run_id,
        result["download_mbps"],
        result["upload_mbps"],
        result["dns_target"],
        result["dns_result"]["packet_loss_pct"],
    )
    return run_id


def run_scheduler(settings: Settings) -> None:
    initialize(settings.database_url)
    scheduler = BlockingScheduler(timezone=settings.timezone)
    trigger = CronTrigger.from_crontab(settings.schedule, timezone=settings.timezone)
    scheduler.add_job(
        perform_test,
        trigger=trigger,
        args=[settings],
        id="network-measurement",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    if settings.run_on_start:
        scheduler.add_job(perform_test, args=[settings], id="startup-measurement")
    LOG.info("Scheduler active: %s (%s)", settings.schedule, settings.timezone)
    scheduler.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scheduled home network monitor")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run the scheduler")
    subparsers.add_parser("once", help="Run one measurement immediately")
    export_parser = subparsers.add_parser("export", help="Export all stored results as CSV")
    export_parser.add_argument("--output", default="-", help="Output file, or - for stdout")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()

    if args.command == "run":
        run_scheduler(settings)
    elif args.command == "once":
        initialize(settings.database_url)
        perform_test(settings)
    elif args.command == "export":
        initialize(settings.database_url)
        if args.output == "-":
            export_csv(settings.database_url, sys.stdout)
        else:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="") as destination:
                count = export_csv(settings.database_url, destination)
            LOG.info("Exported %s rows to %s", count, path)


if __name__ == "__main__":
    main()
