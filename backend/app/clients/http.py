import hashlib
import json
import time

import httpx

from ..config import settings


class ApiError(Exception):
    pass


class ApiClient:

    def __init__(self, memory, investigation_id=None):
        self.memory = memory
        self.inv = investigation_id

        self.http = httpx.Client(
            timeout=settings.http_timeout,
            headers={
                "User-Agent": (
                    "ProofTrace/0.1 (mailto:"
                    + settings.contact_email
                    + ")"
                )
            },
        )

    def get_json(
        self,
        source,
        url,
        params=None,
        retries=3,
        ttl_hours=None,
    ):
        key = hashlib.sha256(
            (
                url
                + json.dumps(params or {}, sort_keys=True)
            ).encode()
        ).hexdigest()

        # Retraction data changes over time and can be cached for less
        # than ordinary metadata; callers pass a shorter ttl for it.
        ttl = (
            settings.cache_ttl_hours
            if ttl_hours is None
            else ttl_hours
        )

        hit = self.memory.cache_get(key, ttl)

        if hit is not None:
            self.memory.log_api(
                self.inv,
                source,
                url,
                200,
                0,
                True,
            )
            return hit

        last = ""

        for attempt in range(retries):
            start = time.time()

            try:
                response = self.http.get(
                    url,
                    params=params,
                )

                ms = int((time.time() - start) * 1000)

                self.memory.log_api(
                    self.inv,
                    source,
                    url,
                    response.status_code,
                    ms,
                    False,
                )

                if response.status_code == 404:
                    return None

                if response.status_code == 200:
                    body = response.json()

                    self.memory.cache_set(key, body)

                    return body

                last = "HTTP " + str(response.status_code)

                if response.status_code not in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    break

            except (httpx.HTTPError, ValueError) as error:
                last = str(error)

            time.sleep(2 ** attempt)

        raise ApiError(
            source + " request failed: " + last
        )

    def get_text(
        self,
        source,
        url,
        params=None,
        retries=3,
        ttl_hours=None,
    ):
        """Like get_json but for a plain-text body (e.g. full-text XML).

        The text is cached the same way as JSON so a repeated lookup is
        not refetched.
        """

        key = hashlib.sha256(
            (
                url
                + json.dumps(params or {}, sort_keys=True)
            ).encode()
        ).hexdigest()

        ttl = (
            settings.cache_ttl_hours
            if ttl_hours is None
            else ttl_hours
        )

        hit = self.memory.cache_get(key, ttl)

        if hit is not None:
            self.memory.log_api(self.inv, source, url, 200, 0, True)

            if isinstance(hit, dict):
                return hit.get("__text__")

            return hit

        last = ""

        for attempt in range(retries):
            start = time.time()

            try:
                response = self.http.get(url, params=params)

                ms = int((time.time() - start) * 1000)

                self.memory.log_api(
                    self.inv,
                    source,
                    url,
                    response.status_code,
                    ms,
                    False,
                )

                if response.status_code == 404:
                    return None

                if response.status_code == 200:
                    self.memory.cache_set(
                        key,
                        {"__text__": response.text},
                    )

                    return response.text

                last = "HTTP " + str(response.status_code)

                if response.status_code not in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    break

            except (httpx.HTTPError, ValueError) as error:
                last = str(error)

            time.sleep(2 ** attempt)

        raise ApiError(
            source + " request failed: " + last
        )

    def get_bytes(
        self,
        source,
        url,
        params=None,
        retries=2,
        max_bytes=None,
    ):
        """Fetch a binary body (an open-access PDF) with a size cap.

        Not cached: PDFs are large and are only fetched for a matched
        paper with no XML full text available.
        """

        last = ""

        for attempt in range(retries):
            start = time.time()

            try:
                response = self.http.get(url, params=params)

                ms = int((time.time() - start) * 1000)

                self.memory.log_api(
                    self.inv,
                    source,
                    url,
                    response.status_code,
                    ms,
                    False,
                )

                if response.status_code == 404:
                    return None

                if response.status_code == 200:
                    content = response.content

                    if max_bytes and len(content) > max_bytes:
                        return None

                    return content

                last = "HTTP " + str(response.status_code)

                if response.status_code not in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    break

            except (httpx.HTTPError, ValueError) as error:
                last = str(error)

            time.sleep(2 ** attempt)

        raise ApiError(
            source + " request failed: " + last
        )