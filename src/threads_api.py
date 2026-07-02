"""Small Threads Graph API wrapper used by the posting workflows."""
from __future__ import annotations

import time
from typing import Any

import requests


class ThreadsAPI:
    BASE_URL = "https://graph.threads.net/v1.0"
    MAX_RETRIES = 3
    RETRY_BASE_WAIT = 3

    def __init__(self, access_token: str, user_id: str | None = None):
        self.access_token = access_token
        self.user_id = user_id

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.request(method, url, timeout=60, **kwargs)
                try:
                    data = response.json()
                except ValueError:
                    data = {"raw": response.text}

                if response.status_code >= 400:
                    error = data.get("error", data) if isinstance(data, dict) else data
                    code = error.get("code") if isinstance(error, dict) else None
                    message = error.get("message") if isinstance(error, dict) else str(error)
                    if code in (4, 10, 190, 200, 368):
                        return {"error": error, "status_code": response.status_code}
                    raise requests.exceptions.RequestException(
                        f"HTTP {response.status_code}: {message}"
                    )

                if isinstance(data, dict) and "error" in data:
                    return data
                return data if isinstance(data, dict) else {"data": data}
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES - 1:
                    wait = self.RETRY_BASE_WAIT * (2**attempt)
                    print(f"Retry {attempt + 1}/{self.MAX_RETRIES} after {wait}s")
                    time.sleep(wait)
        return {"error": str(last_error)}

    def _require_user_id(self) -> str:
        if not self.user_id:
            raise RuntimeError("Threads user_id is required for this operation.")
        return self.user_id

    def get_me(self) -> dict[str, Any]:
        url = f"{self.BASE_URL}/me"
        params = {
            "fields": "id,username,name,threads_profile_picture_url,threads_biography",
            "access_token": self.access_token,
        }
        return self._request_with_retry("GET", url, params=params)

    def create_text_container(self, text: str, reply_to_id: str = "") -> dict[str, Any]:
        url = f"{self.BASE_URL}/{self._require_user_id()}/threads"
        data = {
            "media_type": "TEXT",
            "text": text,
            "access_token": self.access_token,
        }
        if reply_to_id:
            data["reply_to_id"] = reply_to_id
        return self._request_with_retry("POST", url, data=data)

    def create_image_container(
        self,
        text: str,
        image_url: str,
        alt_text: str = "",
        reply_to_id: str = "",
    ) -> dict[str, Any]:
        url = f"{self.BASE_URL}/{self._require_user_id()}/threads"
        data = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": text,
            "access_token": self.access_token,
        }
        if alt_text:
            data["alt_text"] = alt_text
        if reply_to_id:
            data["reply_to_id"] = reply_to_id
        return self._request_with_retry("POST", url, data=data)

    def publish(self, creation_id: str) -> dict[str, Any]:
        url = f"{self.BASE_URL}/{self._require_user_id()}/threads_publish"
        data = {
            "creation_id": creation_id,
            "access_token": self.access_token,
        }
        return self._request_with_retry("POST", url, data=data)

    def post_text(
        self,
        text: str,
        wait_seconds: int = 2,
        reply_to_id: str = "",
    ) -> dict[str, Any]:
        container = self.create_text_container(text, reply_to_id=reply_to_id)
        if "error" in container:
            return container
        creation_id = container.get("id")
        if not creation_id:
            return {"error": "Container ID was not returned.", "container": container}
        time.sleep(wait_seconds)
        return self.publish(str(creation_id))

    def post_image(
        self,
        text: str,
        image_url: str,
        alt_text: str = "",
        wait_seconds: int = 2,
        reply_to_id: str = "",
    ) -> dict[str, Any]:
        container = self.create_image_container(
            text,
            image_url,
            alt_text,
            reply_to_id=reply_to_id,
        )
        if "error" in container:
            return container
        creation_id = container.get("id")
        if not creation_id:
            return {"error": "Container ID was not returned.", "container": container}
        time.sleep(wait_seconds)
        return self.publish(str(creation_id))
