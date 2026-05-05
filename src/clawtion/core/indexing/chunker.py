"""チャンキングモジュール

3粒度（file / coarse / fine）のチャンク分割を提供する。
構造ベースの分割を原則とし、トークン数は安全上限としてのみ使用する。
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

# ---- 型エイリアス ----

ChunkLevel = Literal["file", "coarse", "fine"]

# ---- データクラス ----


@dataclass(frozen=True)
class Chunk:
    """イミュータブルなチャンクデータオブジェクト。"""

    level: ChunkLevel
    content: str
    content_with_context: str
    content_hash: str
    chunk_index: int
    chunk_total: int
    heading_path: str | None = None
    token_count: int = 0
    char_count: int = 0


# ---- ユーティリティ関数 ----


def compute_content_hash(content: bytes) -> str:
    """SHA-256でコンテンツのハッシュ値を計算する。"""
    return hashlib.sha256(content).hexdigest()


def is_code_block(text: str) -> bool:
    """テキストがコードブロック内かどうかを判定する。"""
    stripped = text.strip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def is_table(text: str) -> bool:
    """テキストがMarkdownテーブルかどうかを判定する。

    条件:
    - 全行が `|` で始まっている
    - 1行目と2行目があり、2行目がセパレータ行（`|---|`）ならテーブル
    """
    lines = text.strip().split("\n")
    if len(lines) < 2:
        return False
    pipe_count = sum(1 for line in lines if line.strip().startswith("|"))
    if pipe_count != len(lines):
        return False
    # 2行目がセパレータ行かチェック（`| --- |` or `|:---|` 等）
    separator_pattern = re.compile(r"^\|[\s:-]+\|$")
    return bool(separator_pattern.match(lines[1].strip()))


def split_by_markdown_headings(content: str) -> list[dict[str, str]]:
    """MarkdownをH1/H2/H3見出しで分割する。

    Returns:
        list[dict]: ``{"heading_path": str | None, "content": str}`` のリスト。
    """
    lines = content.split("\n")
    sections: list[dict[str, str]] = []
    current_lines: list[str] = []
    current_heading_path: str | None = None
    heading_stack: list[str] = []

    for line in lines:
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            # 現在のセクションを保存
            section_content = "\n".join(current_lines).strip()
            if section_content or current_heading_path is not None:
                sections.append({
                    "heading_path": current_heading_path,
                    "content": section_content,
                })
            current_lines = []

            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            # 見出しスタックを更新
            while heading_stack and len(heading_stack) >= level:
                heading_stack.pop()
            heading_stack.append(heading_text)
            current_heading_path = " > ".join(heading_stack)

            # 見出し行自体もコンテンツに含める
            current_lines.append(line)
        else:
            current_lines.append(line)

    # 最後のセクション
    section_content = "\n".join(current_lines).strip()
    sections.append({
        "heading_path": current_heading_path,
        "content": section_content,
    })

    return sections


def split_by_paragraphs(content: str) -> list[str]:
    """テキストを段落境界（空行）で分割する。"""
    paragraphs = re.split(r"\n\s*\n", content)
    return [p.strip() for p in paragraphs if p.strip()]


def merge_short_adjacent(chunks: list[Chunk], target_min: int = 200) -> list[Chunk]:
    """短すぎる隣接チャンクを結合する。"""
    if not chunks:
        return []

    merged: list[Chunk] = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        # コードブロックやテーブルは単独で保持
        if is_code_block(current.content) or is_table(current.content):
            merged.append(current)
            i += 1
            continue

        # 短すぎる場合、次のチャンクと結合を試みる
        if (
            current.token_count < target_min
            and i + 1 < len(chunks)
            and not is_code_block(chunks[i + 1].content)
            and not is_table(chunks[i + 1].content)
        ):
            next_chunk = chunks[i + 1]
            merged_content = current.content + "\n\n" + next_chunk.content
            merged_heading = (
                current.heading_path
                if current.heading_path == next_chunk.heading_path
                else current.heading_path or next_chunk.heading_path
            )
            merged_tokens = current.token_count + next_chunk.token_count
            merged_chars = current.char_count + next_chunk.char_count + 2
            merged_hash = compute_content_hash(merged_content.encode("utf-8"))
            joined = Chunk(
                level=current.level,
                content=merged_content,
                content_with_context=merged_content,
                content_hash=merged_hash,
                chunk_index=current.chunk_index,
                chunk_total=current.chunk_total,  # 後で補正
                heading_path=merged_heading,
                token_count=merged_tokens,
                char_count=merged_chars,
            )
            merged.append(joined)
            i += 2
        else:
            merged.append(current)
            i += 1

    # index / total を補正
    total = len(merged)
    return [
        Chunk(
            level=c.level,
            content=c.content,
            content_with_context=c.content_with_context,
            content_hash=c.content_hash,
            chunk_index=idx,
            chunk_total=total,
            heading_path=c.heading_path,
            token_count=c.token_count,
            char_count=c.char_count,
        )
        for idx, c in enumerate(merged)
    ]


# ---- 文分割 ----


def _detect_language(content: str) -> str:
    """コンテンツの言語を判定する。失敗時は 'ja' を返す。"""
    try:
        from clawtion.utils.language import detect_language

        return detect_language(content)
    except Exception:
        return "ja"


def _split_sentences(text: str, language: str = "ja") -> list[str]:
    """pysbd を使って文単位に分割する。"""
    try:
        import pysbd

        segmenter = pysbd.Segmenter(language=language, clean=False)
        return segmenter.segment(text)
    except ImportError:
        # pysbd がない場合は句点・改行で簡易分割
        return _simple_split_sentences(text, language)


def _simple_split_sentences(text: str, language: str = "ja") -> list[str]:
    """pysbd フォールバック用の簡易文分割。

    日本語: 句点（。）で分割
    英語:  ピリオド（.）＋スペース＋大文字 のパターンで分割
    それ以外: 改行で分割
    """
    if language == "ja":
        parts = re.split(r"(?<=。)\s*", text)
    elif language == "en":
        # ピリオド + スペース + 大文字 で分割（略語対策は簡易的に）
        parts = re.split(r"(?<=\.)\s+(?=[A-Z\"'(])", text)
    else:
        parts = text.split("\n")
    return [p.strip() for p in parts if p.strip()]


# ---- 低レベルチャンキング関数 ----


def chunk_file_level(content: str, max_tokens: int = 1500) -> list[Chunk]:
    """ファイルレベルチャンキング。

    ファイル全体を1チャンクとして扱う。
    上限トークン超過時は空リストを返す。
    """
    from clawtion.utils.tokens import count_tokens

    token_count = count_tokens(content)
    if token_count > max_tokens:
        return []

    content_hash = compute_content_hash(content.encode("utf-8"))
    return [
        Chunk(
            level="file",
            content=content,
            content_with_context=content,
            content_hash=content_hash,
            chunk_index=0,
            chunk_total=1,
            token_count=token_count,
            char_count=len(content),
        )
    ]


def chunk_coarse_level(
    content: str, target: int = 800, max_tokens: int = 1500
) -> list[Chunk]:
    """Coarse粒度チャンキング。

    見出しベースで分割する。見出しセクションが上限トークンを超える場合は、
    段落で再分割する。短すぎる隣接セクションは結合する。
    """
    from clawtion.utils.tokens import count_tokens

    sections = split_by_markdown_headings(content)
    raw_chunks: list[Chunk] = []

    for section in sections:
        section_content = section["content"]
        heading_path = section["heading_path"]
        section_tokens = count_tokens(section_content)

        if section_tokens <= max_tokens:
            # 見出しセクションをそのままチャンクに
            section_hash = compute_content_hash(section_content.encode("utf-8"))
            raw_chunks.append(
                Chunk(
                    level="coarse",
                    content=section_content,
                    content_with_context=section_content,
                    content_hash=section_hash,
                    chunk_index=0,
                    chunk_total=0,
                    heading_path=heading_path,
                    token_count=section_tokens,
                    char_count=len(section_content),
                )
            )
        else:
            # 上限超過: 段落で再分割
            paragraphs = split_by_paragraphs(section_content)
            para_chunks = _merge_paragraphs_to_target(
                paragraphs, heading_path, target, max_tokens
            )
            raw_chunks.extend(para_chunks)

    # 短すぎる隣接チャンクを結合
    raw_chunks = merge_short_adjacent(raw_chunks, target_min=200)

    total = len(raw_chunks)
    return [
        Chunk(
            level=c.level,
            content=c.content,
            content_with_context=c.content_with_context,
            content_hash=c.content_hash,
            chunk_index=idx,
            chunk_total=total,
            heading_path=c.heading_path,
            token_count=c.token_count,
            char_count=c.char_count,
        )
        for idx, c in enumerate(raw_chunks)
    ]


def _merge_paragraphs_to_target(
    paragraphs: list[str],
    heading_path: str | None,
    target: int,
    max_tokens: int,
) -> list[Chunk]:
    """段落を結合して target トークンに近づける。上限を超えない範囲で結合する。"""
    from clawtion.utils.tokens import count_tokens

    result: list[Chunk] = []
    current_parts: list[str] = []

    for para in paragraphs:
        # コードブロックやテーブルは単独チャンクにする
        if is_code_block(para) or is_table(para):
            if current_parts:
                joined = "\n\n".join(current_parts)
                joined_tokens = count_tokens(joined)
                joined_hash = compute_content_hash(joined.encode("utf-8"))
                result.append(
                    Chunk(
                        level="coarse",
                        content=joined,
                        content_with_context=joined,
                        content_hash=joined_hash,
                        chunk_index=0,
                        chunk_total=0,
                        heading_path=heading_path,
                        token_count=joined_tokens,
                        char_count=len(joined),
                    )
                )
                current_parts = []
            para_hash = compute_content_hash(para.encode("utf-8"))
            para_tokens = count_tokens(para)
            result.append(
                Chunk(
                    level="coarse",
                    content=para,
                    content_with_context=para,
                    content_hash=para_hash,
                    chunk_index=0,
                    chunk_total=0,
                    heading_path=heading_path,
                    token_count=para_tokens,
                    char_count=len(para),
                )
            )
            continue

        tentative = "\n\n".join([*current_parts, para])
        tentative_tokens = count_tokens(tentative)

        if tentative_tokens <= max_tokens:
            current_parts.append(para)
        else:
            if current_parts:
                joined = "\n\n".join(current_parts)
                joined_tokens = count_tokens(joined)
                joined_hash = compute_content_hash(joined.encode("utf-8"))
                result.append(
                    Chunk(
                        level="coarse",
                        content=joined,
                        content_with_context=joined,
                        content_hash=joined_hash,
                        chunk_index=0,
                        chunk_total=0,
                        heading_path=heading_path,
                        token_count=joined_tokens,
                        char_count=len(joined),
                    )
                )
            current_parts = [para]

    # 残り
    if current_parts:
        joined = "\n\n".join(current_parts)
        joined_tokens = count_tokens(joined)
        joined_hash = compute_content_hash(joined.encode("utf-8"))
        result.append(
            Chunk(
                level="coarse",
                content=joined,
                content_with_context=joined,
                content_hash=joined_hash,
                chunk_index=0,
                chunk_total=0,
                heading_path=heading_path,
                token_count=joined_tokens,
                char_count=len(joined),
            )
        )

    return result


def chunk_fine_level(content: str, target: int = 100) -> list[Chunk]:
    """Fine粒度チャンキング。

    文単位で分割する。pysbd による多言語文境界検出を使用する。
    コードブロック・テーブルは単一チャンクとして保持する。
    """
    from clawtion.utils.tokens import count_tokens

    language = _detect_language(content)
    paragraphs = split_by_paragraphs(content)
    raw_chunks: list[Chunk] = []

    for paragraph in paragraphs:
        # 構造保護: コードブロックやテーブルは分割しない
        if is_code_block(paragraph) or is_table(paragraph):
            para_hash = compute_content_hash(paragraph.encode("utf-8"))
            para_tokens = count_tokens(paragraph)
            raw_chunks.append(
                Chunk(
                    level="fine",
                    content=paragraph,
                    content_with_context=paragraph,
                    content_hash=para_hash,
                    chunk_index=0,
                    chunk_total=0,
                    token_count=para_tokens,
                    char_count=len(paragraph),
                )
            )
            continue

        # 文単位に分割
        sentences = _split_sentences(paragraph, language=language)

        # 隣接文を target に近づけるよう結合
        current_parts: list[str] = []
        for sentence in sentences:
            tentative = "".join([*current_parts, sentence])
            tentative_tokens = count_tokens(tentative)

            if tentative_tokens <= int(target * 1.5):
                current_parts.append(sentence)
            else:
                if current_parts:
                    joined = "".join(current_parts)
                    joined_hash = compute_content_hash(joined.encode("utf-8"))
                    joined_tokens = count_tokens(joined)
                    raw_chunks.append(
                        Chunk(
                            level="fine",
                            content=joined,
                            content_with_context=joined,
                            content_hash=joined_hash,
                            chunk_index=0,
                            chunk_total=0,
                            token_count=joined_tokens,
                            char_count=len(joined),
                        )
                    )
                current_parts = [sentence]

        if current_parts:
            joined = "".join(current_parts)
            joined_hash = compute_content_hash(joined.encode("utf-8"))
            joined_tokens = count_tokens(joined)
            raw_chunks.append(
                Chunk(
                    level="fine",
                    content=joined,
                    content_with_context=joined,
                    content_hash=joined_hash,
                    chunk_index=0,
                    chunk_total=0,
                    token_count=joined_tokens,
                    char_count=len(joined),
                )
            )

    total = len(raw_chunks)
    return [
        Chunk(
            level=c.level,
            content=c.content,
            content_with_context=c.content_with_context,
            content_hash=c.content_hash,
            chunk_index=idx,
            chunk_total=total,
            heading_path=c.heading_path,
            token_count=c.token_count,
            char_count=c.char_count,
        )
        for idx, c in enumerate(raw_chunks)
    ]


# ---- コンテキスト注入 ----


def build_context(
    folder_path: str,
    title: str,
    heading_path: str | None,
    content: str,
) -> str:
    """Embedding入力用のコンテキスト注入テキストを構築する。

    Format:
        ``folder: {folder_path} | file: {title} | section: {heading_path} | text: {content}``
    """
    parts: list[str] = []
    if folder_path:
        parts.append(f"folder: {folder_path}")
    if title:
        parts.append(f"file: {title}")
    if heading_path:
        parts.append(f"section: {heading_path}")
    parts.append(f"text: {content}")
    return " | ".join(parts)


# ---- メインエントリポイント ----


def _try_file_level(
    content: str, max_tokens: int = 1500
) -> list[dict[str, Any]]:
    """ファイルレベルを試行する。失敗時は空リスト。"""
    chunks = chunk_file_level(content, max_tokens=max_tokens)
    if not chunks:
        return []
    return [
        {
            "level": c.level,
            "content": c.content,
            "heading_path": c.heading_path,
            "token_count": c.token_count,
            "char_count": c.char_count,
        }
        for c in chunks
    ]


def _try_coarse_level(
    content: str, target: int = 800, max_tokens: int = 1500
) -> list[dict[str, Any]]:
    """Coarseレベルを試行する。"""
    chunks = chunk_coarse_level(content, target=target, max_tokens=max_tokens)
    return [
        {
            "level": c.level,
            "content": c.content,
            "heading_path": c.heading_path,
            "token_count": c.token_count,
            "char_count": c.char_count,
        }
        for c in chunks
    ]


def chunk_file(
    file_path: str, content: str, folder_path: str = ""
) -> list[Chunk]:
    """メインエントリポイント。

    Phase 1 デフォルト戦略:
        1. ファイルレベルを試行
        2. ファイルが1500トークンを超える場合、coarseレベルにフォールバック

    各チャンクに ``build_context()`` を適用して ``content_with_context`` を設定する。
    """
    from clawtion.utils.tokens import count_tokens

    title = os.path.splitext(os.path.basename(file_path))[0]
    token_count = count_tokens(content)

    raw_data = _try_file_level(content) if token_count <= 1500 else _try_coarse_level(content)

    if not raw_data:
        return []

    chunks: list[Chunk] = []
    total = len(raw_data)

    for i, r in enumerate(raw_data):
        chunk_content: str = r["content"]
        heading_path: str | None = r.get("heading_path")
        c_hash = compute_content_hash(chunk_content.encode("utf-8"))
        c_tokens: int = count_tokens(chunk_content)
        c_chars: int = len(chunk_content)
        context = build_context(folder_path, title, heading_path, chunk_content)

        chunks.append(
            Chunk(
                level=r["level"],
                content=chunk_content,
                content_with_context=context,
                content_hash=c_hash,
                chunk_index=i,
                chunk_total=total,
                heading_path=heading_path,
                token_count=c_tokens,
                char_count=c_chars,
            )
        )

    return chunks
