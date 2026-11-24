"""起動: `python -m app`（backend ディレクトリで実行）"""

from __future__ import annotations

import logging
import sys

import uvicorn
from pydantic import ValidationError

from .config import MIN_TOKEN_LENGTH, Settings
from .main import create_app

# 比較用の定数（ここで bind するわけではない）
WILDCARD_HOSTS = frozenset({"0.0.0.0", "::"})  # noqa: S104  # nosec B104


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("desk")
    try:
        settings = Settings()
    except ValidationError as exc:
        print("設定エラーのため起動しません:", file=sys.stderr)
        # 値（input）は表示しない。トークンなどの秘密情報が含まれ得るため
        for e in exc.errors():
            where = ".".join(str(p) for p in e["loc"])
            msg = str(e["msg"]).removeprefix("Value error, ")
            print(f"  - {where + ': ' if where else ''}{msg}", file=sys.stderr)
        if any(e["loc"] and e["loc"][0] == "token" for e in exc.errors()):
            print(
                f"DESK_TOKEN（{MIN_TOKEN_LENGTH}文字以上）を .env に設定してください。作り方:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(32))"',
                file=sys.stderr,
            )
        return 2

    if not settings.is_loopback():
        log.warning(
            "DESK_ALLOW_REMOTE=true のため、DESK_HOST=%s で待ち受けます（ネットワークに公開）。"
            " HTTPS のリバースプロキシ経由でのみアクセスし、ファイアウォールで接続元を絞ってください。",
            settings.host,
        )
    if settings.host not in settings.allowed_hosts and settings.host not in WILDCARD_HOSTS:
        log.warning("DESK_HOST が DESK_ALLOWED_HOSTS に含まれていません。Host チェックで拒否されます。")

    print(f"IP TEST DESK: http://{settings.host}:{settings.port}/", flush=True)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        proxy_headers=False,
        server_header=False,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
