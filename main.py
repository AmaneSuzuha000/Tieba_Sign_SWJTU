from __future__ import annotations

import logging

from client import DeviceProfile, TiebaMobileClient
from comment_review import run as run_comment_review
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

    logging.info("Starting comment review task")
    comment_summary = run_comment_review()
    logging.info(
        "Finished comment review: thread_id=%s forum_name=%s comments=%s results=%s dry_run=%s",
        comment_summary.get("target", {}).get("thread_id"),
        comment_summary.get("target", {}).get("forum_name"),
        len(comment_summary.get("comments", [])),
        len(comment_summary.get("results", [])),
        comment_summary.get("dry_run"),
    )

    for result in comment_summary.get("results", []):
        if comment_summary.get("dry_run"):
            logging.info(
                "Comment dry-run #%s: content=%s protobuf_size=%s",
                result.get("index"),
                result.get("comment"),
                result.get("protobuf_size"),
            )
            continue
        logging.info(
            "Comment success #%s: content=%s pid=%s msg=%s",
            result.get("index"),
            result.get("comment"),
            result.get("pid"),
            result.get("msg"),
        )

    if settings.fail_on_partial_failure and summary.failure_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
