"""スナップショット方式のファイル読み込み。

ファイル編集中にindexingが走っても編集体験をブロックしないよう、
ファイル内容をスナップショットとしてメモリにコピーしてから処理する。
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from clawtion.utils.exceptions import ClawtionError
from clawtion.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FileSnapshot:
    """ファイルのスナップショット。

    Attributes:
        file_path: ファイルの絶対パス
        content: ファイル内容（バイト列）
        content_hash: SHA-256 ハッシュ
        taken_at: スナップショット取得時刻（Unix タイムスタンプ）
    """

    file_path: str
    content: bytes
    content_hash: str
    taken_at: float


def compute_content_hash(content: bytes) -> str:
    """バイト列の SHA-256 ハッシュを計算する。"""
    return hashlib.sha256(content).hexdigest()


def take_snapshot(file_path: str) -> FileSnapshot:
    """ファイルのスナップショットを取得する。

    指定されたファイルを読み込み、バッファリングした内容と
    ハッシュ・タイムスタンプを返す。

    Args:
        file_path: 読み込むファイルの絶対パス

    Returns:
        ファイルのスナップショット

    Raises:
        ClawtionError: ファイルの読み込みに失敗した場合
    """
    try:
        with open(file_path, "rb") as f:
            content = f.read()
    except (OSError, PermissionError) as e:
        logger.error("Failed to read file for snapshot", file_path=file_path, error=str(e))
        raise ClawtionError(
    code="FILE_READ_ERROR",
    message=f"Failed to read file: {file_path}",
) from e

    content_hash = compute_content_hash(content)
    taken_at = time.time()

    return FileSnapshot(
        file_path=file_path,
        content=content,
        content_hash=content_hash,
        taken_at=taken_at,
    )


def has_changed(file_path: str, snapshot: FileSnapshot) -> bool:
    """現在のファイルがスナップショットから変更されたかどうかを判定する。

    現在のファイルのハッシュとスナップショットのハッシュを比較する。
    ファイルが存在しない場合も変更ありとみなす。

    Args:
        file_path: チェックするファイルの絶対パス
        snapshot: 比較対象のスナップショット

    Returns:
        変更されている場合は True
    """
    try:
        with open(file_path, "rb") as f:
            current_content = f.read()
    except (OSError, FileNotFoundError):
        # ファイルが削除された、または読み込めない
        return True

    current_hash = compute_content_hash(current_content)
    return current_hash != snapshot.content_hash
