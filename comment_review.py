from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import ssl
import struct
import time
from dataclasses import dataclass
from typing import Any

from client import DeviceProfile, TiebaAPIError, TiebaMobileClient
from login import Settings
from requests.adapters import HTTPAdapter


THREAD_URL_RE = re.compile(r"/p/(\d+)")
BOUNDARY = "--------7da3d81520810*"
PROTOBUF_POST_URL = "https://tiebac.baidu.com/c/c/post/add?cmd=309731&format=protobuf"
PROTOBUF_POST_VERSION = "12.35.1.0"
PROTOBUF_POST_MOUNT_PREFIX = "https://tiebac.baidu.com/"
DEFAULT_THREAD_URL = "https://tieba.baidu.com/p/9983496041"
DEFAULT_BASE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/135.0.0.0 Mobile Safari/537.36"
)
DEFAULT_SCREEN_WIDTH = 1440
DEFAULT_SCREEN_HEIGHT = 3200
DEFAULT_SCREEN_DENSITY = 3.5
DEFAULT_COMMENTS = ["3", "3", "3", "3"]
DEFAULT_COMMENT_DELAY_MS = 1200
DEFAULT_COMMENT_DELAY_JITTER_MS = 1800


@dataclass(frozen=True, slots=True)
class FieldSpec:
    number: int
    kind: str
    nested: dict[str, "FieldSpec"] | None = None


@dataclass(slots=True)
class ThreadTarget:
    forum_id: str
    forum_name: str
    thread_id: str
    thread_title: str
    author_uid: str
    author_name_show: str
    first_post_id: str
    reply_num: str


@dataclass(slots=True)
class AuthContext:
    uid: str
    nickname: str
    tbs: str
    baiduid: str
    baiduzid: str
    z_id: str
    sample_id: str | None
    screen_width: int
    screen_height: int
    screen_density: float
    base_user_agent: str
    encoded_oaid: str
    oaid_status_code: int
    oaid_supported: int
    is_track_limited: int
    device_score: str


COMMON_REQUEST_SPEC: dict[str, FieldSpec] = {
    "_client_type": FieldSpec(1, "int32"),
    "_client_version": FieldSpec(2, "string"),
    "_client_id": FieldSpec(3, "string"),
    "_phone_imei": FieldSpec(5, "string"),
    "from": FieldSpec(6, "string"),
    "cuid": FieldSpec(7, "string"),
    "_timestamp": FieldSpec(8, "int64"),
    "model": FieldSpec(9, "string"),
    "BDUSS": FieldSpec(10, "string"),
    "tbs": FieldSpec(11, "string"),
    "net_type": FieldSpec(12, "int32"),
    "_phone_newimei": FieldSpec(14, "string"),
    "sign": FieldSpec(23, "string"),
    "pversion": FieldSpec(24, "string"),
    "_os_version": FieldSpec(25, "string"),
    "brand": FieldSpec(26, "string"),
    "lego_lib_version": FieldSpec(28, "string"),
    "applist": FieldSpec(29, "string"),
    "stoken": FieldSpec(30, "string"),
    "z_id": FieldSpec(31, "string"),
    "cuid_galaxy2": FieldSpec(32, "string"),
    "cuid_gid": FieldSpec(33, "string"),
    "oaid": FieldSpec(34, "string"),
    "c3_aid": FieldSpec(35, "string"),
    "sample_id": FieldSpec(36, "string"),
    "scr_w": FieldSpec(37, "int32"),
    "scr_h": FieldSpec(38, "int32"),
    "scr_dip": FieldSpec(39, "double"),
    "q_type": FieldSpec(40, "int32"),
    "is_teenager": FieldSpec(41, "int32"),
    "sdk_ver": FieldSpec(42, "string"),
    "framework_ver": FieldSpec(43, "string"),
    "swan_game_ver": FieldSpec(44, "string"),
    "active_timestamp": FieldSpec(49, "int64"),
    "first_install_time": FieldSpec(50, "int64"),
    "last_update_time": FieldSpec(51, "int64"),
    "event_day": FieldSpec(53, "string"),
    "android_id": FieldSpec(54, "string"),
    "cmode": FieldSpec(55, "int32"),
    "start_scheme": FieldSpec(56, "string"),
    "start_type": FieldSpec(57, "int32"),
    "extra": FieldSpec(61, "string"),
    "user_agent": FieldSpec(62, "string"),
    "personalized_rec_switch": FieldSpec(63, "int32"),
    "device_score": FieldSpec(70, "string"),
}

ADD_POST_REQUEST_DATA_SPEC: dict[str, FieldSpec] = {
    "common": FieldSpec(1, "message", COMMON_REQUEST_SPEC),
    "authsid": FieldSpec(2, "string"),
    "sig": FieldSpec(3, "string"),
    "tbs": FieldSpec(4, "string"),
    "video_other": FieldSpec(5, "string"),
    "anonymous": FieldSpec(6, "string"),
    "can_no_forum": FieldSpec(7, "string"),
    "is_feedback": FieldSpec(8, "string"),
    "takephoto_num": FieldSpec(9, "string"),
    "entrance_type": FieldSpec(10, "string"),
    "voice_md5": FieldSpec(11, "string"),
    "during_time": FieldSpec(12, "string"),
    "vcode": FieldSpec(13, "string"),
    "vcode_md5": FieldSpec(14, "string"),
    "vcode_type": FieldSpec(15, "string"),
    "vcode_tag": FieldSpec(16, "string"),
    "topic_id": FieldSpec(17, "string"),
    "new_vcode": FieldSpec(18, "string"),
    "content": FieldSpec(19, "string"),
    "reply_uid": FieldSpec(20, "string"),
    "meme_text": FieldSpec(21, "string"),
    "meme_cont_sign": FieldSpec(22, "string"),
    "item_id": FieldSpec(23, "string"),
    "comment_head": FieldSpec(24, "string"),
    "works_tag": FieldSpec(25, "string"),
    "fid": FieldSpec(26, "string"),
    "transform_forums": FieldSpec(27, "string"),
    "v_fid": FieldSpec(28, "string"),
    "v_fname": FieldSpec(29, "string"),
    "kw": FieldSpec(30, "string"),
    "is_barrage": FieldSpec(31, "string"),
    "barrage_time": FieldSpec(32, "string"),
    "st_param": FieldSpec(33, "string"),
    "ptype": FieldSpec(34, "string"),
    "ori_ugc_nid": FieldSpec(35, "string"),
    "ori_ugc_vid": FieldSpec(36, "string"),
    "ori_ugc_tid": FieldSpec(37, "string"),
    "ori_ugc_type": FieldSpec(38, "string"),
    "is_location": FieldSpec(39, "string"),
    "lat": FieldSpec(40, "string"),
    "lng": FieldSpec(41, "string"),
    "name": FieldSpec(42, "string"),
    "sn": FieldSpec(43, "string"),
    "from_fourm_id": FieldSpec(44, "string"),
    "tid": FieldSpec(45, "string"),
    "quote_id": FieldSpec(46, "string"),
    "is_twzhibo_thread": FieldSpec(47, "string"),
    "floor_num": FieldSpec(48, "string"),
    "repostid": FieldSpec(49, "string"),
    "sub_post_id": FieldSpec(50, "string"),
    "is_ad": FieldSpec(51, "string"),
    "is_addition": FieldSpec(52, "string"),
    "is_giftpost": FieldSpec(53, "string"),
    "st_type": FieldSpec(54, "string"),
    "post_from": FieldSpec(55, "string"),
    "real_lat": FieldSpec(56, "string"),
    "real_lng": FieldSpec(57, "string"),
    "name_show": FieldSpec(58, "string"),
    "is_works": FieldSpec(59, "string"),
    "is_pictxt": FieldSpec(60, "string"),
    "is_story": FieldSpec(61, "string"),
    "jid": FieldSpec(62, "string"),
    "jfrom": FieldSpec(63, "string"),
    "show_custom_figure": FieldSpec(64, "int32"),
    "from_category_id": FieldSpec(65, "string"),
    "to_category_id": FieldSpec(66, "string"),
    "is_show_bless": FieldSpec(67, "int32"),
}

ADD_POST_REQUEST_SPEC: dict[str, FieldSpec] = {
    "data": FieldSpec(1, "message", ADD_POST_REQUEST_DATA_SPEC),
}

ERROR_SPEC: dict[str, FieldSpec] = {
    "error_code": FieldSpec(1, "int32"),
    "error_msg": FieldSpec(2, "string"),
    "user_msg": FieldSpec(3, "string"),
}

ADD_POST_RESPONSE_DATA_SPEC: dict[str, FieldSpec] = {
    "tid": FieldSpec(2, "string"),
    "pid": FieldSpec(3, "string"),
    "msg": FieldSpec(5, "string"),
    "pre_msg": FieldSpec(6, "string"),
    "color_msg": FieldSpec(7, "string"),
    "ext_msg": FieldSpec(18, "string"),
}

ADD_POST_RESPONSE_SPEC: dict[str, FieldSpec] = {
    "error": FieldSpec(1, "message", ERROR_SPEC),
    "data": FieldSpec(2, "message", ADD_POST_RESPONSE_DATA_SPEC),
}


def parse_thread_id(explicit_thread_id: str | None, thread_url: str | None) -> str:
    if explicit_thread_id and explicit_thread_id.strip():
        return explicit_thread_id.strip()
    if thread_url:
        match = THREAD_URL_RE.search(thread_url)
        if match:
            return match.group(1)
    raise ValueError("Missing Tieba thread id. Provide TIEBA_TEST_THREAD_ID or TIEBA_TEST_THREAD_URL.")


def parse_comment_source(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return list(DEFAULT_COMMENTS)

    text = raw.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        comments = [str(item).strip() for item in parsed if str(item).strip()]
    else:
        comments = [line.strip() for line in text.splitlines() if line.strip()]

    if not comments:
        raise ValueError("At least one comment is required.")
    if len(comments) > 4:
        raise ValueError("TiebaLite comment review accepts at most 4 comments.")
    return comments


def default_device_score() -> str:
    return "0.42320722"


class TLS12HttpAdapter(HTTPAdapter):
    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        # urllib3/OpenSSL can stall during default TLS negotiation with this host
        # on some Windows Python builds. Pinning TLS 1.2 matches the host's
        # working handshake path and keeps the request stack stable.
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = context
        super().init_poolmanager(*args, **kwargs)


def build_cookie_header(cookies: list[tuple[str, str | None]]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookies if value)


def build_user_agent(base_user_agent: str, suffix: str | None) -> str:
    if not suffix:
        return base_user_agent
    return f"{base_user_agent} {suffix.strip()}"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


def resolve_comment_delay_range() -> tuple[int, int]:
    raw_min = os.getenv("TIEBA_COMMENT_DELAY_MIN_MS")
    raw_max = os.getenv("TIEBA_COMMENT_DELAY_MAX_MS")
    base_delay_ms = _int_env("TIEBA_COMMENT_DELAY_MS", DEFAULT_COMMENT_DELAY_MS)

    if raw_min is None and raw_max is None:
        if base_delay_ms <= 0:
            return 0, 0
        return base_delay_ms, base_delay_ms + DEFAULT_COMMENT_DELAY_JITTER_MS

    min_delay_ms = _int_env("TIEBA_COMMENT_DELAY_MIN_MS", base_delay_ms)
    max_delay_ms = _int_env("TIEBA_COMMENT_DELAY_MAX_MS", max(base_delay_ms, min_delay_ms))
    min_delay_ms = max(0, min_delay_ms)
    max_delay_ms = max(0, max_delay_ms)
    if min_delay_ms > max_delay_ms:
        min_delay_ms, max_delay_ms = max_delay_ms, min_delay_ms
    return min_delay_ms, max_delay_ms


def choose_comment_delay_ms(min_delay_ms: int, max_delay_ms: int) -> int:
    if max_delay_ms <= 0:
        return 0
    if min_delay_ms >= max_delay_ms:
        return max(0, min_delay_ms)
    return random.randint(max(0, min_delay_ms), max_delay_ms)


def _encode_varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1
    encoded = bytearray()
    while True:
        current = value & 0x7F
        value >>= 7
        if value:
            encoded.append(current | 0x80)
        else:
            encoded.append(current)
            return bytes(encoded)


def _decode_varint(buffer: bytes, offset: int) -> tuple[int, int]:
    shift = 0
    value = 0
    while True:
        current = buffer[offset]
        offset += 1
        value |= (current & 0x7F) << shift
        if current < 0x80:
            return value, offset
        shift += 7


def _encode_key(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_scalar(kind: str, value: Any) -> tuple[int, bytes]:
    if kind == "string":
        raw = str(value).encode("utf-8")
        return 2, _encode_varint(len(raw)) + raw
    if kind in {"int32", "int64"}:
        return 0, _encode_varint(int(value))
    if kind == "double":
        return 1, struct.pack("<d", float(value))
    raise ValueError(f"Unsupported scalar kind: {kind}")


def _serialize_message(spec: dict[str, FieldSpec], payload: dict[str, Any]) -> bytes:
    encoded = bytearray()
    ordered_items = sorted(
        ((name, payload[name], field) for name, field in spec.items() if name in payload and payload[name] is not None),
        key=lambda item: item[2].number,
    )
    for _, value, field in ordered_items:
        if field.kind == "message":
            nested = _serialize_message(field.nested or {}, value)
            encoded.extend(_encode_key(field.number, 2))
            encoded.extend(_encode_varint(len(nested)))
            encoded.extend(nested)
            continue
        wire_type, raw = _encode_scalar(field.kind, value)
        encoded.extend(_encode_key(field.number, wire_type))
        encoded.extend(raw)
    return bytes(encoded)


def _skip_unknown(buffer: bytes, offset: int, wire_type: int) -> int:
    if wire_type == 0:
        _, offset = _decode_varint(buffer, offset)
        return offset
    if wire_type == 1:
        return offset + 8
    if wire_type == 2:
        size, offset = _decode_varint(buffer, offset)
        return offset + size
    if wire_type == 5:
        return offset + 4
    raise ValueError(f"Unsupported wire type: {wire_type}")


def _parse_message(spec: dict[str, FieldSpec], buffer: bytes) -> dict[str, Any]:
    reverse = {field.number: (name, field) for name, field in spec.items()}
    offset = 0
    parsed: dict[str, Any] = {}

    while offset < len(buffer):
        key, offset = _decode_varint(buffer, offset)
        field_number = key >> 3
        wire_type = key & 0x07
        name_field = reverse.get(field_number)
        if name_field is None:
            offset = _skip_unknown(buffer, offset, wire_type)
            continue

        name, field = name_field
        if field.kind == "message":
            size, offset = _decode_varint(buffer, offset)
            parsed[name] = _parse_message(field.nested or {}, buffer[offset : offset + size])
            offset += size
            continue

        if field.kind == "string":
            size, offset = _decode_varint(buffer, offset)
            parsed[name] = buffer[offset : offset + size].decode("utf-8")
            offset += size
            continue

        if field.kind == "double":
            parsed[name] = struct.unpack("<d", buffer[offset : offset + 8])[0]
            offset += 8
            continue

        value, offset = _decode_varint(buffer, offset)
        if field.kind == "int32" and value >= (1 << 31):
            value -= 1 << 32
        elif field.kind == "int64" and value >= (1 << 63):
            value -= 1 << 64
        parsed[name] = value

    return parsed


def build_add_post_request(payload: dict[str, Any]) -> bytes:
    return _serialize_message(ADD_POST_REQUEST_SPEC, payload)


def parse_add_post_response(payload: bytes) -> dict[str, Any]:
    return _parse_message(ADD_POST_RESPONSE_SPEC, payload)


class TiebaLiteCommentReview(TiebaMobileClient):
    def __init__(self, settings: Settings, device: DeviceProfile):
        super().__init__(settings, device)
        self.session.mount(PROTOBUF_POST_MOUNT_PREFIX, TLS12HttpAdapter())

    def authenticate(self) -> AuthContext:
        auth = super().authenticate()
        cookies = self.settings.cookies or {}
        return AuthContext(
            uid=auth.uid,
            nickname=auth.nickname,
            tbs=auth.tbs,
            baiduid=str(self.settings.baiduid or self.device.baiduid),
            baiduzid=str(cookies.get("BAIDUZID") or ""),
            z_id=str(cookies.get("BAIDUZID") or ""),
            sample_id=self.settings.device_seed or self.device.android_id,
            screen_width=DEFAULT_SCREEN_WIDTH,
            screen_height=DEFAULT_SCREEN_HEIGHT,
            screen_density=DEFAULT_SCREEN_DENSITY,
            base_user_agent=DEFAULT_BASE_USER_AGENT,
            encoded_oaid="",
            oaid_status_code=-100,
            oaid_supported=0,
            is_track_limited=1,
            device_score=default_device_score(),
        )

    def resolve_thread_target(self, thread_id: str) -> ThreadTarget:
        payload = self._post_form(
            "/c/f/pb/page",
            data={
                "kz": thread_id,
                "pn": "1",
                "lz": "0",
                "st_type": "tb_frslist",
                "back": "0",
                "floor_rn": "3",
                "mark": "0",
                "rn": "30",
                "with_floor": "1",
                "scr_dip": str(DEFAULT_SCREEN_DENSITY),
                "scr_h": str(DEFAULT_SCREEN_HEIGHT),
                "scr_w": str(DEFAULT_SCREEN_WIDTH),
            },
        )
        forum = payload.get("forum") or {}
        thread = payload.get("thread") or {}
        origin_thread = thread.get("origin_thread_info") or {}

        forum_id = forum.get("id") or origin_thread.get("fid")
        forum_name = forum.get("name") or origin_thread.get("fname")
        resolved_thread_id = thread.get("id") or origin_thread.get("tid") or thread_id
        if not forum_id or not forum_name:
            raise ValueError("Unable to resolve forum_id/forum_name from the target thread.")

        return ThreadTarget(
            forum_id=str(forum_id),
            forum_name=str(forum_name),
            thread_id=str(resolved_thread_id),
            thread_title=str(thread.get("title") or origin_thread.get("title") or ""),
            author_uid=str((thread.get("author") or {}).get("id") or ""),
            author_name_show=str((thread.get("author") or {}).get("name_show") or ""),
            first_post_id=str(thread.get("post_id") or ""),
            reply_num=str(thread.get("reply_num") or ""),
        )

    def build_common_request(
        self,
        auth: AuthContext,
        *,
        request_timestamp_ms: int,
    ) -> dict[str, Any]:
        common = {
            "_client_type": 2,
            "_client_version": PROTOBUF_POST_VERSION,
            "_client_id": self.device.client_id,
            "_phone_imei": self.device.imei,
            "from": "1020031h",
            "cuid": self.device.cuid,
            "_timestamp": request_timestamp_ms,
            "model": self.device.model,
            "BDUSS": self.settings.bduss,
            "tbs": auth.tbs,
            "net_type": 1,
            "pversion": "1.0.3",
            "_os_version": self.device.os_version,
            "brand": self.device.brand,
            "lego_lib_version": "3.0.0",
            "applist": "",
            "stoken": self.settings.stoken,
            "z_id": auth.z_id,
            "cuid_galaxy2": self.device.cuid_galaxy2,
            "cuid_gid": self.device.cuid_gid,
            "oaid": auth.encoded_oaid,
            "c3_aid": self.device.aid,
            "scr_w": auth.screen_width,
            "scr_h": auth.screen_height,
            "scr_dip": auth.screen_density,
            "q_type": 0,
            "is_teenager": 0,
            "sdk_ver": "2.34.0",
            "framework_ver": "3340042",
            "swan_game_ver": "1038000",
            "active_timestamp": self.device.active_timestamp,
            "first_install_time": self.device.first_install_time,
            "last_update_time": self.device.last_update_time,
            "event_day": self.device.event_day,
            "android_id": self.device.android_id,
            "cmode": 1,
            "start_scheme": "",
            "start_type": 1,
            "extra": "",
            "user_agent": build_user_agent(auth.base_user_agent, f"tieba/{PROTOBUF_POST_VERSION}"),
            "personalized_rec_switch": 1,
            "device_score": auth.device_score,
        }
        if auth.sample_id:
            common["sample_id"] = auth.sample_id
        return common

    def build_add_post_request_data(
        self,
        target: ThreadTarget,
        auth: AuthContext,
        comment: str,
        *,
        request_timestamp_ms: int,
    ) -> dict[str, Any]:
        return {
            "anonymous": "1",
            "can_no_forum": "0",
            "common": self.build_common_request(auth, request_timestamp_ms=request_timestamp_ms),
            "content": comment,
            "entrance_type": "0",
            "fid": target.forum_id,
            "floor_num": "0",
            "kw": target.forum_name,
            "is_ad": "0",
            "is_addition": "0",
            "is_barrage": "0",
            "is_feedback": "0",
            "is_giftpost": "0",
            "is_pictxt": "0",
            "is_show_bless": 0,
            "is_twzhibo_thread": "0",
            "name_show": auth.nickname,
            "new_vcode": "1",
            "show_custom_figure": 0,
            "takephoto_num": "0",
            "tid": target.thread_id,
            "vcode_tag": "12",
            "barrage_time": "0",
            "post_from": "13",
            "v_fid": "",
            "v_fname": "",
        }

    def build_form_parts(self, auth: AuthContext, *, request_timestamp_ms: int, protobuf_payload: bytes) -> list[dict[str, Any]]:
        scalar_parts = {
            "BDUSS": self.settings.bduss,
            "_client_id": self.device.client_id,
            "_client_type": "2",
            "_client_version": PROTOBUF_POST_VERSION,
            "_phone_imei": self.device.imei,
            "active_timestamp": str(self.device.active_timestamp),
            "android_id": self.device.encoded_android_id,
            "baiduid": auth.baiduid,
            "brand": self.device.brand,
            "c3_aid": self.device.aid,
            "cmode": "1",
            "cuid": self.device.cuid,
            "cuid_galaxy2": self.device.cuid_galaxy2,
            "cuid_gid": self.device.cuid_gid,
            "device_score": auth.device_score,
            "event_day": self.device.event_day,
            "extra": "",
            "first_install_time": str(self.device.first_install_time),
            "from": "tieba",
            "framework_ver": "3340042",
            "is_teenager": "0",
            "last_update_time": str(self.device.last_update_time),
            "mac": "02:00:00:00:00:00",
            "model": self.device.model,
            "naws_game_ver": "1038000",
            "net_type": "1",
            "oaid": json.dumps(
                {
                    "v": auth.encoded_oaid,
                    "sc": auth.oaid_status_code,
                    "sup": auth.oaid_supported,
                    "isTrackLimited": auth.is_track_limited,
                },
                separators=(",", ":"),
            ),
            "personalized_rec_switch": "1",
            "sdk_ver": "2.34.0",
            "start_scheme": "",
            "start_type": "1",
            "stoken": self.settings.stoken,
            "timestamp": str(request_timestamp_ms),
            "z_id": auth.z_id,
        }
        if auth.sample_id:
            scalar_parts["sample_id"] = auth.sample_id
        scalar_parts.update(self._st_params())

        parts = [{"name": name, "value": scalar_parts[name]} for name in sorted(scalar_parts)]
        parts.append({"name": "sign", "value": self._sign({key: str(value) for key, value in scalar_parts.items()})})
        parts.append(
            {
                "name": "data",
                "filename": "file",
                "content_type": "application/octet-stream",
                "payload": protobuf_payload,
            }
        )
        return parts

    def build_headers(self, auth: AuthContext) -> dict[str, str]:
        headers = self._headers(
            user_agent=build_user_agent(auth.base_user_agent, f"tieba/{PROTOBUF_POST_VERSION}"),
            cookie=build_cookie_header(
                [
                    ("BAIDUZID", auth.baiduzid),
                    ("ka", "open"),
                    ("CUID", self.device.cuid),
                    ("TBBRAND", self.device.model),
                ]
            ),
            include_charset=True,
            include_client_type_header=False,
            client_user_token=auth.uid,
        )
        headers["x_bd_data_type"] = "protobuf"
        headers["Content-Type"] = f"multipart/form-data; boundary={BOUNDARY}"
        return headers

    def build_multipart_body(self, parts: list[dict[str, Any]]) -> bytes:
        chunks: list[bytes] = []
        for part in parts:
            chunks.append(f"--{BOUNDARY}\r\n".encode("ascii"))
            if part["name"] == "data":
                chunks.append(b'Content-Disposition: form-data; name="data"; filename="file"\r\n')
                chunks.append(b"Content-Type: application/octet-stream\r\n\r\n")
                chunks.append(part["payload"])
                chunks.append(b"\r\n")
                continue
            chunks.append(f'Content-Disposition: form-data; name="{part["name"]}"\r\n\r\n'.encode("utf-8"))
            chunks.append(str(part["value"]).encode("utf-8"))
            chunks.append(b"\r\n")
        chunks.append(f"--{BOUNDARY}--\r\n".encode("ascii"))
        return b"".join(chunks)

    def send_comment(self, target: ThreadTarget, auth: AuthContext, comment: str, *, request_timestamp_ms: int) -> dict[str, Any]:
        request_data = self.build_add_post_request_data(
            target,
            auth,
            comment,
            request_timestamp_ms=request_timestamp_ms,
        )
        protobuf_payload = build_add_post_request({"data": request_data})
        parts = self.build_form_parts(auth, request_timestamp_ms=request_timestamp_ms, protobuf_payload=protobuf_payload)
        body = self.build_multipart_body(parts)

        response = self.session.post(
            PROTOBUF_POST_URL,
            data=body,
            headers=self.build_headers(auth),
            timeout=self.settings.request_timeout,
        )
        response.raise_for_status()

        parsed = parse_add_post_response(response.content)
        error = parsed.get("error") or {}
        error_code = int(error.get("error_code") or 0)
        if error_code != 0:
            message = str(error.get("user_msg") or error.get("error_msg") or "Add post failed")
            raise TiebaAPIError(error_code, message)

        data = parsed.get("data") or {}
        return {
            "comment": comment,
            "pid": str(data.get("pid") or ""),
            "tid": str(data.get("tid") or target.thread_id),
            "msg": str(data.get("msg") or ""),
            "raw_response_size": len(response.content),
        }


def run() -> dict[str, Any]:
    settings = Settings.from_env()
    device = DeviceProfile.from_seed(settings.device_seed or "comment-review")
    review = TiebaLiteCommentReview(settings, device)

    thread_id = parse_thread_id(
        os.getenv("TIEBA_TEST_THREAD_ID"),
        os.getenv("TIEBA_TEST_THREAD_URL") or DEFAULT_THREAD_URL,
    )
    comments = parse_comment_source(os.getenv("TIEBA_TEST_COMMENTS"))
    delay_min_ms, delay_max_ms = resolve_comment_delay_range()
    dry_run = _bool_env("TIEBA_DRY_RUN", False) or _bool_env("TIEBA_COMMENT_DRY_RUN", False)

    auth = review.authenticate()
    target = review.resolve_thread_target(thread_id)

    summary: dict[str, Any] = {
        "target": {
            "forum_id": target.forum_id,
            "forum_name": target.forum_name,
            "thread_id": target.thread_id,
            "thread_title": target.thread_title,
            "author_uid": target.author_uid,
            "author_name_show": target.author_name_show,
            "first_post_id": target.first_post_id,
            "reply_num": target.reply_num,
        },
        "comments": comments,
        "delay_range_ms": {"min": delay_min_ms, "max": delay_max_ms},
        "dry_run": dry_run,
        "results": [],
    }

    if dry_run:
        base_timestamp_ms = int(time.time() * 1000)
        for index, comment in enumerate(comments, start=1):
            request_timestamp_ms = base_timestamp_ms + index - 1
            request_data = review.build_add_post_request_data(
                target,
                auth,
                comment,
                request_timestamp_ms=request_timestamp_ms,
            )
            protobuf_payload = build_add_post_request({"data": request_data})
            summary["results"].append(
                {
                    "index": index,
                    "comment": comment,
                    "next_delay_ms": (
                        choose_comment_delay_ms(delay_min_ms, delay_max_ms) if index < len(comments) else 0
                    ),
                    "request_data": request_data,
                    "protobuf_size": len(protobuf_payload),
                    "protobuf_sha256": hashlib.sha256(protobuf_payload).hexdigest(),
                    "protobuf_base64_prefix": base64.b64encode(protobuf_payload).decode("ascii")[:48],
                }
            )
        return summary

    for index, comment in enumerate(comments, start=1):
        request_timestamp_ms = int(time.time() * 1000)
        result = review.send_comment(target, auth, comment, request_timestamp_ms=request_timestamp_ms)
        next_delay_ms = choose_comment_delay_ms(delay_min_ms, delay_max_ms) if index < len(comments) else 0
        result["next_delay_ms"] = next_delay_ms
        summary["results"].append({"index": index, **result})
        if next_delay_ms > 0:
            time.sleep(next_delay_ms / 1000)

    return summary


def main() -> int:
    summary = run()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
