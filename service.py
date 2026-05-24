from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field

from client import ForumInfo, TiebaAPIError, TiebaMobileClient
from login import Settings


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SignFailure:
    forum_id: int
    forum_name: str
    error_message: str


@dataclass(slots=True)
class SignSummary:
    username: str
    total_signable: int
    all_forums: int
    official_selected: int = 0
    official_succeeded: int = 0
    official_error: str | None = None
    dry_run: bool = False
    signed_forums: list[str] = field(default_factory=list)
    failures: list[SignFailure] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.signed_forums)

    @property
    def failure_count(self) -> int:
        return len(self.failures)


class TiebaSignService:
    def __init__(self, client: TiebaMobileClient, settings: Settings):
        self.client = client
        self.settings = settings

    def run(self) -> SignSummary:
        auth = self.client.authenticate()
        forum_config = self.client.get_forum_list_config(auth)
        all_forums = self.client.get_all_liked_forums(auth)
        signable_forums = [forum for forum in all_forums if not forum.is_signed]

        summary = SignSummary(
            username=auth.display_name,
            total_signable=len(signable_forums),
            all_forums=len(all_forums),
            dry_run=self.settings.dry_run,
        )
        if not signable_forums:
            LOGGER.info("No signable forums found")
            return summary

        normal_forums: list[ForumInfo] = []
        official_forums: list[ForumInfo] = []
        for forum in signable_forums:
            can_use_msign = (
                self.settings.use_official_msign
                and forum.level_id >= forum_config.msign_min_level
                and len(official_forums) < forum_config.msign_step_num
            )
            if can_use_msign:
                official_forums.append(forum)
            else:
                normal_forums.append(forum)

        summary.official_selected = len(official_forums)
        LOGGER.info(
            "Prepared %s signable forums: official=%s normal=%s",
            len(signable_forums),
            len(official_forums),
            len(normal_forums),
        )

        if self.settings.dry_run:
            return summary

        if official_forums:
            try:
                official_results = self.client.m_sign(auth, official_forums)
            except Exception as exc:
                summary.official_error = str(exc)
                LOGGER.warning("Official msign failed, fallback to normal sign: %s", exc)
                normal_forums = [*official_forums, *normal_forums]
            else:
                forum_by_id = {forum.forum_id: forum for forum in official_forums}
                for result in official_results:
                    if result.signed:
                        summary.signed_forums.append(result.forum_name)
                        summary.official_succeeded += 1
                        LOGGER.info("Official sign success: %s", result.forum_name)
                    else:
                        LOGGER.warning(
                            "Official sign failed for %s, fallback to normal sign: %s",
                            result.forum_name,
                            result.error_message or "unknown error",
                        )
                        normal_forums.append(forum_by_id[result.forum_id])

        for index, forum in enumerate(normal_forums):
            try:
                result = self.client.sign(auth, forum)
                if result.signed:
                    summary.signed_forums.append(forum.forum_name)
                    LOGGER.info("Normal sign success: %s", forum.forum_name)
                else:
                    summary.failures.append(
                        SignFailure(
                            forum_id=forum.forum_id,
                            forum_name=forum.forum_name,
                            error_message="API returned unsigned status",
                        )
                    )
                    LOGGER.warning("Normal sign returned unsigned status: %s", forum.forum_name)
            except TiebaAPIError as exc:
                summary.failures.append(
                    SignFailure(
                        forum_id=forum.forum_id,
                        forum_name=forum.forum_name,
                        error_message=exc.message,
                    )
                )
                LOGGER.warning("Normal sign failed: %s -> %s", forum.forum_name, exc.message)

            if index + 1 < len(normal_forums):
                time.sleep(self._delay_seconds())

        return summary

    def _delay_seconds(self) -> float:
        if self.settings.slow_mode:
            return random.randint(3500, 8000) / 1000
        return max(self.settings.sign_delay_ms, 0) / 1000
