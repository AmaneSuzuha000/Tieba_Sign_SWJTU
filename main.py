from __future__ import annotations

import logging

from client import DeviceProfile, TiebaMobileClient
from login import Settings
from service import TiebaSignService


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> int:
    _configure_logging()
    settings = Settings.from_env()
    seed = settings.device_seed or settings.bduss
    device = DeviceProfile.from_seed(seed)
    client = TiebaMobileClient(settings, device)
    service = TiebaSignService(client, settings)
    summary = service.run()

    logging.info(
        "Finished signing for %s: total_signable=%s success=%s failed=%s official_selected=%s official_succeeded=%s dry_run=%s",
        summary.username,
        summary.total_signable,
        summary.success_count,
        summary.failure_count,
        summary.official_selected,
        summary.official_succeeded,
        summary.dry_run,
    )

    for failure in summary.failures:
        logging.warning("Failure: %s (%s) -> %s", failure.forum_name, failure.forum_id, failure.error_message)

    if settings.fail_on_partial_failure and summary.failure_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
