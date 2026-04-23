"""Command line entry point for early Neuzelaar milestones."""

from __future__ import annotations

import argparse

from neuzelaar.core.fetch.client import FetchClient
from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.origin import parse_url


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m neuzelaar")
    parser.add_argument("url", help="URL or local path to fetch")
    args = parser.parse_args()

    url = args.url
    if "://" not in url:
        url = parse_url(url).normalized

    url_record = parse_url(url)
    request = Request(
        url=url_record.normalized,
        method="GET",
        headers={},
        body=None,
        reason=FetchReason.TOP_LEVEL,
        initiator=None,
        origin=url_record.origin,
        context_origin=url_record.origin,
    )
    resource = FetchClient().fetch(request)
    print(f"{resource.status} {resource.final_url}")
    print(resource.body.decode(resource.encoding or "utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
