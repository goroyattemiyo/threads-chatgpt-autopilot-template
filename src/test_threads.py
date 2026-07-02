"""Test the Threads API connection and optionally publish a short test."""
from __future__ import annotations

import argparse
import json

from .threads_api import ThreadsAPI
from .utils import require_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-text", default="")
    args = parser.parse_args()

    api = ThreadsAPI(
        access_token=require_env("THREADS_ACCESS_TOKEN"),
        user_id=require_env("THREADS_USER_ID"),
    )
    print(json.dumps(api.get_me(), ensure_ascii=False, indent=2))

    if args.post_text:
        result = api.post_text(args.post_text)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
