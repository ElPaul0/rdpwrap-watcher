"""ntfy notification helpers."""

from __future__ import annotations

import requests


class NtfyClient:
    PRIORITY_OK = "3"
    PRIORITY_UPDATED = "4"
    PRIORITY_ERROR = "5"

    def __init__(self, url: str, user: str, password: str, timeout: float = 15.0):
        self.url = url.rstrip("/")
        self.auth = (user, password)
        self.timeout = timeout

    def send(self, message: str, title: str, priority: str) -> None:
        headers = {
            "Title": title,
            "Priority": priority,
        }
        response = requests.post(
            self.url,
            data=message.encode("utf-8"),
            headers=headers,
            auth=self.auth,
            timeout=self.timeout,
        )
        response.raise_for_status()

    def ok(self, message: str, title: str = "RDPWrap Watcher") -> None:
        self.send(message, title, self.PRIORITY_OK)

    def updated(self, message: str, title: str = "RDPWrap Watcher") -> None:
        self.send(message, title, self.PRIORITY_UPDATED)

    def error(self, message: str, title: str = "RDPWrap Watcher") -> None:
        self.send(message, title, self.PRIORITY_ERROR)
