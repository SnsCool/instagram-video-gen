"""画像生成（Gemini 2.5 Flash Image）"""

import logging
import os
import struct
import time
import zlib

import config

logger = logging.getLogger(__name__)


def _create_dummy_png(path: str, width: int, height: int, color: tuple[int, int, int]) -> None:
    """最小限のPNGファイルを生成（モック用）"""

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw_row = b"\x00" + bytes(color) * width
    raw_data = raw_row * height
    idat = chunk(b"IDAT", zlib.compress(raw_data))
    iend = chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(header + ihdr + idat + iend)


def _enhance_image_prompt(prompt: str) -> str:
    """画像プロンプトに品質指示を補強する。"""
    additions = []
    lower = prompt.lower()
    if "realistic photograph" not in lower:
        additions.append("realistic photograph")
    if "high resolution" not in lower and "high-resolution" not in lower:
        additions.append("high resolution")
    if "detailed" not in lower:
        additions.append("highly detailed")
    if "no text" not in lower:
        additions.append("no text, no letters, no watermarks")

    if additions:
        return prompt.rstrip(" ,.\n") + ", " + ", ".join(additions)
    return prompt


def _simplify_prompt_for_retry(prompt: str) -> str:
    """安全フィルターでブロックされた場合にプロンプトを簡略化する。"""
    simplified = prompt
    for term in ["Japanese ", "Asian ", "Caucasian ", "African "]:
        simplified = simplified.replace(term, "")
    for term in ["man ", "woman ", "person "]:
        simplified = simplified.replace(term, "professional ")
    return simplified


def generate_image(scene: dict, output_dir: str, mock: bool = False, instructions: str = None) -> str:
    scene_id = scene["scene_id"]
    output_path = os.path.join(output_dir, f"scene_{scene_id}.png")

    if mock:
        colors = [(70, 130, 180), (60, 179, 113), (218, 165, 32), (205, 92, 92), (147, 112, 219)]
        color = colors[(scene_id - 1) % len(colors)]
        _create_dummy_png(output_path, config.VIDEO_WIDTH, config.VIDEO_HEIGHT, color)
        logger.info("[MOCK] 画像生成: scene_%d → %s", scene_id, output_path)
        return output_path

    # --- 本番実装（Gemini 2.5 Flash Image）---
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    base_prompt = _enhance_image_prompt(scene["image_prompt"])
    # 追加指示がある場合はプロンプトに追加
    if instructions:
        base_prompt = base_prompt + ". Additional instructions: " + instructions

    max_retries = 3
    for attempt in range(max_retries):
        prompt = base_prompt if attempt == 0 else _simplify_prompt_for_retry(base_prompt)

        try:
            logger.info(
                "画像生成リクエスト: scene_%d (attempt %d/%d)",
                scene_id, attempt + 1, max_retries,
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="9:16",
                    ),
                ),
            )

            # レスポンスのpartsから画像を探す
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image = part.as_image()
                        image.save(output_path)
                        logger.info("画像生成完了: scene_%d → %s", scene_id, output_path)
                        return output_path

            # 画像が返されなかった（安全フィルターによるブロック等）
            logger.warning(
                "画像生成: scene_%d — 画像が返されませんでした (attempt %d/%d)",
                scene_id, attempt + 1, max_retries,
            )

        except Exception as e:
            logger.warning(
                "画像生成エラー: scene_%d (attempt %d/%d): %s",
                scene_id, attempt + 1, max_retries, e,
            )

        if attempt < max_retries - 1:
            wait = 2 ** (attempt + 1)  # 2, 4 秒
            logger.info("リトライまで %d秒待機...", wait)
            time.sleep(wait)

    raise RuntimeError(f"画像生成失敗: scene_{scene_id} — 全リトライ失敗")
