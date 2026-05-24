from __future__ import annotations

import base64
import hashlib
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests

from login import Settings


LOGGER = logging.getLogger(__name__)


class TiebaError(Exception):
    """Base exception for tieba sign workflow."""


class TiebaAPIError(TiebaError):
    def __init__(self, code: int | str, message: str):
        self.code = code
        self.message = message or "Unknown Tieba API error"
        super().__init__(f"[{code}] {self.message}")


@dataclass(slots=True)
class AuthInfo:
    uid: str
    user_name: str
    nickname: str
    tbs: str
    portrait: str

    @property
    def display_name(self) -> str:
        return self.nickname or self.user_name


@dataclass(slots=True)
class ForumListConfig:
    msign_min_level: int
    msign_step_num: int


@dataclass(slots=True)
class ForumInfo:
    forum_id: int
    forum_name: str
    level_id: int
    is_signed: bool


@dataclass(slots=True)
class OfficialSignResult:
    forum_id: int
    forum_name: str
    signed: bool
    error_message: str = ""


@dataclass(slots=True)
class NormalSignResult:
    forum_id: int
    forum_name: str
    signed: bool
    sign_bonus_point: int | None = None
    user_sign_rank: int | None = None


def _seed_bytes(seed: str, label: str) -> bytes:
    return hashlib.sha256(f"{seed}:{label}".encode("utf-8")).digest()


def _md5_upper(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest().upper()


def _base32_no_padding(value: bytes) -> str:
    return base64.b32encode(value).decode("ascii").rstrip("=")


def _uuid_from_seed(seed: str) -> str:
    raw = bytearray(_seed_bytes(seed, "uuid")[:16])
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(raw)))


@dataclass(slots=True)
class DeviceProfile:
    model: str
    brand: str
    os_version: str
    imei: str
    android_id: str
    uuid: str
    cuid: str
    cuid_galaxy2: str
    cuid_gid: str
    aid: str
    baiduid: str
    client_id: str
    sample_id: str | None
    active_timestamp: int
    first_install_time: int
    last_update_time: int
    client_logid: str

    @property
    def encoded_android_id(self) -> str:
        return base64.b64encode(self.android_id.encode("utf-8")).decode("ascii")

    @property
    def oaid_payload(self) -> dict[str, int | str]:
        return {
            "v": "",
            "sc": -200,
            "sup": 0,
            "isTrackLimited": 0,
        }

    @property
    def event_day(self) -> str:
        now = time.localtime()
        return f"{now.tm_year}{now.tm_mon}{now.tm_mday:02d}"

    @classmethod
    def from_seed(cls, seed: str) -> "DeviceProfile":
        now_ms = int(time.time() * 1000)
        android_id = _seed_bytes(seed, "android_id").hex()[:16]
        uuid_value = _uuid_from_seed(seed)
        cuid_base = _md5_upper(f"com.baidu{android_id}")
        cuid = f"{cuid_base}|V{_base32_no_padding(hashlib.sha1(cuid_base.encode('utf-8')).digest()[:5])}"
        raw_aid = (
            "A00-"
            f"{_base32_no_padding(hashlib.sha1(f'com.helios{android_id}{uuid_value}'.encode('utf-8')).digest())}-"
        )
        aid_sign = _base32_no_padding(hashlib.sha1(raw_aid.encode("utf-8")).digest()[:5])
        install_offset = int.from_bytes(_seed_bytes(seed, "install_offset")[:2], "big") % (180 * 24 * 3600 * 1000)
        update_offset = int.from_bytes(_seed_bytes(seed, "update_offset")[:2], "big") % (30 * 24 * 3600 * 1000)
        client_suffix = int.from_bytes(_seed_bytes(seed, "client_suffix")[:2], "big") % 1000

        return cls(
            model="M2012K11AC",
            brand="Xiaomi",
            os_version="34",
            imei="000000000000000",
            android_id=android_id,
            uuid=uuid_value,
            cuid=cuid,
            cuid_galaxy2=cuid,
            cuid_gid="",
            aid=f"{raw_aid}{aid_sign}",
            baiduid=f"{_seed_bytes(seed, 'baiduid').hex()[:32].upper()}:FG=1",
            client_id=f"wappc_{now_ms}_{client_suffix}",
            sample_id=None,
            active_timestamp=now_ms,
            first_install_time=now_ms - install_offset,
            last_update_time=now_ms - update_offset,
            client_logid=str(now_ms),
        )


class TiebaMobileClient:
    APP_SECRET = "tiebaclient!!!"
    BASE_URL = "http://c.tieba.baidu.com"
    DEFAULT_CLIENT_VERSION = "12.41.7.1"
    DEFAULT_USER_AGENT = f"bdtb for Android {DEFAULT_CLIENT_VERSION}"
    SIGN_CLIENT_VERSION = "11.10.8.6"
    SIGN_USER_AGENT = f"bdtb for Android {SIGN_CLIENT_VERSION}"

    def __init__(self, settings: Settings, device: DeviceProfile):
        self.settings = settings
        self.device = device
        if settings.baiduid:
            self.device.baiduid = settings.baiduid
        self.session = requests.Session()

    def authenticate(self) -> AuthInfo:
        login_data = self._post_form(
            "/c/s/login",
            data={
                "bdusstoken": f"{self.settings.bduss}|null",
                "stoken": self.settings.stoken,
                "channel_id": "",
                "channel_uid": "",
                "authsid": "null",
            },
            skip_common={"BDUSS"},
            cookie="ka=open",
            include_charset=False,
            include_client_type_header=False,
            client_version=self.SIGN_CLIENT_VERSION,
            user_agent=self.SIGN_USER_AGENT,
        )
        self._raise_on_error(
            login_data,
            message=login_data.get("error_msg") or "Login failed",
        )

        nickname_data = self._post_form(
            "/c/s/initNickname",
            data={
                "BDUSS": self.settings.bduss,
                "stoken": self.settings.stoken,
            },
            skip_common={"BDUSS"},
            cookie="ka=open",
            include_charset=False,
            include_client_type_header=False,
            client_version=self.SIGN_CLIENT_VERSION,
            user_agent=self.SIGN_USER_AGENT,
        )
        self._raise_on_error(
            nickname_data,
            message=nickname_data.get("error_msg") or "Init nickname failed",
        )

        auth = AuthInfo(
            uid=str(login_data["user"]["id"]),
            user_name=login_data["user"]["name"],
            nickname=nickname_data["user_info"]["name_show"],
            tbs=login_data["anti"]["tbs"],
            portrait=login_data["user"]["portrait"],
        )
        LOGGER.info("Authenticated as %s (uid=%s)", auth.display_name, auth.uid)
        return auth

    def get_forum_list_config(self, auth: AuthInfo) -> ForumListConfig:
        data = self._post_form(
            "/c/f/forum/getforumlist",
            data={
                "BDUSS": self.settings.bduss,
                "stoken": self.settings.stoken,
                "user_id": auth.uid,
            },
            skip_common={"BDUSS"},
            client_version=self.SIGN_CLIENT_VERSION,
            user_agent=self.SIGN_USER_AGENT,
        )
        error = data.get("error", {})
        error_code = self._to_int(data.get("error_code"))
        if error_code != 0:
            raise TiebaAPIError(error_code, error.get("usermsg") or error.get("errmsg") or "Get forum list failed")

        return ForumListConfig(
            msign_min_level=self._to_int(data.get("level")),
            msign_step_num=self._to_int(data.get("msign_step_num")),
        )

    def get_all_liked_forums(self, auth: AuthInfo) -> list[ForumInfo]:
        forums: list[ForumInfo] = []
        page_no = 0

        while True:
            data = self._post_form(
                "/c/f/forum/forumGuide",
                data={
                    "sort_type": "3",
                    "call_from": "4",
                    "page_no": str(page_no),
                    "res_num": "50",
                    "top_forum_num": "0",
                    "tbs": auth.tbs,
                    "stoken": self.settings.stoken,
                },
            )
            error_code = self._to_int(data.get("error_code"))
            if error_code != 0:
                raise TiebaAPIError(error_code, data.get("error_msg") or "Get forum guide failed")

            for item in data.get("like_forum", []):
                forums.append(
                    ForumInfo(
                        forum_id=self._to_int(item.get("forum_id")),
                        forum_name=item.get("forum_name", ""),
                        level_id=self._to_int(item.get("level_id")),
                        is_signed=self._to_int(item.get("is_sign")) == 1,
                    )
                )

            if self._to_int(data.get("like_forum_has_more")) != 1:
                break
            page_no += 1

        LOGGER.info("Loaded %s liked forums", len(forums))
        return forums

    def m_sign(self, auth: AuthInfo, forums: list[ForumInfo]) -> list[OfficialSignResult]:
        payload = self._post_form(
            "/c/c/forum/msign",
            data={
                "forum_ids": ",".join(str(forum.forum_id) for forum in forums),
                "tbs": auth.tbs,
                "authsid": "null",
                "stoken": self.settings.stoken,
                "user_id": auth.uid,
            },
            client_version=self.SIGN_CLIENT_VERSION,
            user_agent=self.SIGN_USER_AGENT,
        )
        error = payload.get("error", {})
        error_code = self._to_int(payload.get("error_code"))
        if error_code != 0:
            raise TiebaAPIError(error_code, error.get("usermsg") or error.get("errmsg") or "Official sign failed")

        info = payload.get("info")
        if isinstance(info, str):
            raise TiebaAPIError(error.get("errno", error_code), payload.get("sign_notice") or error.get("usermsg") or info)

        results: list[OfficialSignResult] = []
        for item in info or []:
            item_error = item.get("error", {})
            results.append(
                OfficialSignResult(
                    forum_id=self._to_int(item.get("forum_id")),
                    forum_name=item.get("forum_name", ""),
                    signed=item.get("signed") == "1",
                    error_message=item_error.get("usermsg") or item_error.get("errmsg") or "",
                )
            )
        return results

    def sign(self, auth: AuthInfo, forum: ForumInfo) -> NormalSignResult:
        payload = self._post_form(
            "/c/c/forum/sign",
            data={
                "fid": str(forum.forum_id),
                "kw": forum.forum_name,
                "tbs": auth.tbs,
            },
            skip_common={"oaid"},
            cookie="ka=open",
            include_charset=False,
            include_client_type_header=False,
            client_user_token=auth.uid,
            client_version=self.SIGN_CLIENT_VERSION,
            user_agent=self.SIGN_USER_AGENT,
        )
        error_code = self._to_int(payload.get("error_code"))
        if error_code != 0:
            raise TiebaAPIError(error_code, payload.get("error_msg") or "Sign failed")

        user_info = payload.get("user_info") or {}
        return NormalSignResult(
            forum_id=forum.forum_id,
            forum_name=forum.forum_name,
            signed=self._to_int(user_info.get("is_sign_in")) == 1,
            sign_bonus_point=self._optional_int(user_info.get("sign_bonus_point")),
            user_sign_rank=self._optional_int(user_info.get("user_sign_rank")),
        )

    def _post_form(
        self,
        path: str,
        data: dict[str, Any],
        *,
        skip_common: set[str] | None = None,
        cookie: str | None = None,
        include_charset: bool = True,
        include_client_type_header: bool = True,
        client_user_token: str | None = None,
        client_version: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            **{key: value for key, value in data.items() if value is not None},
            **self._st_params(),
            **self._common_params(skip_common=skip_common, client_version=client_version),
        }
        string_payload = {key: str(value) for key, value in payload.items()}
        string_payload["sign"] = self._sign(string_payload)

        headers = self._headers(
            user_agent=user_agent,
            cookie=cookie,
            include_charset=include_charset,
            include_client_type_header=include_client_type_header,
            client_user_token=client_user_token,
        )
        response = self.session.post(
            f"{self.BASE_URL}{path}",
            data=string_payload,
            headers=headers,
            timeout=self.settings.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    def _headers(
        self,
        *,
        user_agent: str | None,
        cookie: str | None,
        include_charset: bool,
        include_client_type_header: bool,
        client_user_token: str | None,
    ) -> dict[str, str]:
        headers = {
            "User-Agent": user_agent or self.DEFAULT_USER_AGENT,
            "cookie": cookie
            or f"CUID={self.device.cuid};ka=open;TBBRAND={self.device.model};BAIDUID={self.device.baiduid};",
            "cuid": self.device.cuid,
            "cuid_galaxy2": self.device.cuid_galaxy2,
            "cuid_gid": self.device.cuid_gid,
            "c3_aid": self.device.aid,
            "client_logid": self.device.client_logid,
        }
        if include_charset:
            headers["Charset"] = "UTF-8"
        if include_client_type_header:
            headers["client_type"] = "2"
        if client_user_token:
            headers["client_user_token"] = client_user_token
        return headers

    def _common_params(
        self,
        *,
        skip_common: set[str] | None = None,
        client_version: str | None = None,
    ) -> dict[str, str]:
        skip = skip_common or set()
        params = {
            "BDUSS": self.settings.bduss,
            "_client_id": self.device.client_id,
            "_client_type": "2",
            "_os_version": self.device.os_version,
            "model": self.device.model,
            "net_type": "1",
            "_phone_imei": self.device.imei,
            "timestamp": str(int(time.time() * 1000)),
            "active_timestamp": str(self.device.active_timestamp),
            "android_id": self.device.encoded_android_id,
            "baiduid": self.device.baiduid,
            "brand": self.device.brand,
            "cmode": "1",
            "cuid": self.device.cuid,
            "cuid_galaxy2": self.device.cuid_galaxy2,
            "cuid_gid": self.device.cuid_gid,
            "event_day": self.device.event_day,
            "extra": "",
            "first_install_time": str(self.device.first_install_time),
            "framework_ver": "3340042",
            "from": "tieba",
            "is_teenager": "0",
            "last_update_time": str(self.device.last_update_time),
            "mac": "02:00:00:00:00:00",
            "sdk_ver": "2.34.0",
            "start_scheme": "",
            "start_type": "1",
            "swan_game_ver": "1038000",
            "_client_version": client_version or self.DEFAULT_CLIENT_VERSION,
            "c3_aid": self.device.aid,
            "oaid": json.dumps(self.device.oaid_payload, separators=(",", ":")),
        }
        if self.device.sample_id:
            params["sample_id"] = self.device.sample_id
        return {key: value for key, value in params.items() if key not in skip}

    def _st_params(self) -> dict[str, str]:
        number = random.randint(100, 849)
        if 100 <= number <= 120:
            return {"stErrorNums": "0"}
        st_size = round((random.random() * 8 + 0.4) * number)
        return {
            "stErrorNums": "1",
            "stMethod": "1",
            "stMode": "1",
            "stTimesNum": "1",
            "stTime": str(number),
            "stSize": str(st_size),
        }

    def _sign(self, data: dict[str, str]) -> str:
        raw = "".join(f"{key}={value}" for key, value in sorted(data.items()))
        return hashlib.md5(f"{raw}{self.APP_SECRET}".encode("utf-8")).hexdigest().upper()

    @staticmethod
    def _raise_on_error(payload: dict[str, Any], *, message: str) -> None:
        error_code = TiebaMobileClient._to_int(payload.get("error_code"))
        if error_code != 0:
            raise TiebaAPIError(error_code, message)

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None
