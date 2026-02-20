"""音声生成（Fish Audio API）"""

import logging
import os
import struct
import math
import subprocess

import config

logger = logging.getLogger(__name__)


def _get_audio_duration(path: str) -> float:
    """音声ファイルの長さを取得（秒）"""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def _adjust_audio_tempo(input_path: str, output_path: str, target_duration: float) -> str:
    """音声を目標の長さに収まるようにテンポ調整"""
    current_duration = _get_audio_duration(input_path)

    if current_duration <= target_duration:
        # 既に目標以下なら何もしない
        if input_path != output_path:
            os.rename(input_path, output_path)
        return output_path

    # テンポ係数を計算（1.0より大きいと速くなる）
    # 少し余裕を持たせて0.5秒短くする
    tempo = current_duration / (target_duration - 0.3)

    # atempoは0.5〜2.0の範囲なので、それを超える場合は複数回適用
    atempo_filters = []
    remaining_tempo = tempo
    while remaining_tempo > 2.0:
        atempo_filters.append("atempo=2.0")
        remaining_tempo /= 2.0
    if remaining_tempo > 0.5:
        atempo_filters.append(f"atempo={remaining_tempo:.4f}")

    if not atempo_filters:
        if input_path != output_path:
            os.rename(input_path, output_path)
        return output_path

    filter_str = ",".join(atempo_filters)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-af", filter_str,
        output_path,
    ]

    subprocess.run(cmd, capture_output=True, check=True)

    # 元ファイルを削除（異なる場合）
    if input_path != output_path and os.path.exists(input_path):
        os.remove(input_path)

    new_duration = _get_audio_duration(output_path)
    logger.info("音声テンポ調整: %.2f秒 → %.2f秒 (tempo=%.2f)", current_duration, new_duration, tempo)

    return output_path


def _create_silent_wav(path: str, duration_sec: int, sample_rate: int = 24000) -> None:
    """無音WAVファイルを生成（モック用）"""
    num_samples = sample_rate * duration_sec
    data_size = num_samples * 2  # 16-bit mono

    with open(path, "wb") as f:
        # WAV header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", 1))   # PCM
        f.write(struct.pack("<H", 1))   # mono
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * 2))  # byte rate
        f.write(struct.pack("<H", 2))   # block align
        f.write(struct.pack("<H", 16))  # bits per sample
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        # 短いビープ音を入れる（デバッグ確認用）
        freq = 440
        for i in range(num_samples):
            t = i / sample_rate
            # 最初の0.1秒だけビープ、残りは無音
            if t < 0.1:
                val = int(3000 * math.sin(2 * math.pi * freq * t))
            else:
                val = 0
            f.write(struct.pack("<h", val))


def generate_voice(
    scene: dict,
    output_dir: str,
    voice_id: str = None,
    mock: bool = False,
    speed: float = 1.0,
    volume: float = 0.0,
) -> str:
    scene_id = scene["scene_id"]
    duration_sec = scene["duration_sec"]
    output_path = os.path.join(output_dir, f"voice_{scene_id}.wav")

    if mock:
        _create_silent_wav(output_path, duration_sec)
        logger.info("[MOCK] 音声生成: scene_%d「%s」→ %s", scene_id, scene["text"][:20], output_path)
        return output_path

    # --- 本番実装 ---
    import httpx

    # 一時ファイルに生成
    temp_path = os.path.join(output_dir, f"voice_{scene_id}_raw.wav")

    # テキストに感情マーカーがあればそのまま使用
    text = scene["text"]
    # シーンに emotion フィールドがあれば先頭に追加
    emotion = scene.get("emotion")
    if emotion and not text.startswith("("):
        text = f"({emotion}) {text}"

    # prosody設定を構築
    prosody = {}
    if speed != 1.0:
        prosody["speed"] = max(0.5, min(2.0, speed))
    if volume != 0.0:
        prosody["volume"] = max(-20.0, min(20.0, volume))

    request_body = {
        "text": text,
        "reference_id": voice_id or config.FISH_AUDIO_VOICE_ID,
        "format": "wav",
    }
    if prosody:
        request_body["prosody"] = prosody

    resp = httpx.post(
        "https://api.fish.audio/v1/tts",
        headers={
            "Authorization": f"Bearer {config.FISH_AUDIO_API_KEY}",
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=60,
    )
    resp.raise_for_status()

    with open(temp_path, "wb") as f:
        f.write(resp.content)

    # 動画の長さに収まるようにテンポ調整
    _adjust_audio_tempo(temp_path, output_path, duration_sec)

    logger.info("音声生成完了: scene_%d → %s (speed=%.1f, volume=%.1f)", scene_id, output_path, speed, volume)
    return output_path
