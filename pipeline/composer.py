"""動画＋音声合成（FFmpeg）"""

import logging
import math
import os
import platform
import subprocess
from typing import Optional

import config

logger = logging.getLogger(__name__)


def _get_system_font(style: str = "gothic") -> str:
    """システムに適した日本語フォントパスを取得

    Args:
        style: "gothic"（ゴシック体）または "mincho"（明朝体）
    """
    system = platform.system()
    if system == "Darwin":  # macOS
        if style == "mincho":
            # 明朝体
            candidates = [
                "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
                "/System/Library/Fonts/ヒラギノ明朝 ProN W6.ttc",
                "/Library/Fonts/Yu Mincho.ttc",
            ]
        else:
            # ゴシック体
            candidates = [
                "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
            ]
    elif system == "Windows":
        if style == "mincho":
            candidates = [
                "C:/Windows/Fonts/msmincho.ttc",
                "C:/Windows/Fonts/YuMincho.ttf",
            ]
        else:
            candidates = [
                "C:/Windows/Fonts/msgothic.ttc",
                "C:/Windows/Fonts/meiryo.ttc",
            ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        ]

    for font in candidates:
        if os.path.exists(font):
            return font

    # フォールバック
    return ""


def _escape_text_for_ffmpeg(text: str) -> str:
    """FFmpegのdrawtextフィルター用にテキストをエスケープ"""
    # FFmpegのdrawtext特有のエスケープ
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def compose_scene(
    video_path: str,
    voice_path: str,
    output_path: str,
    telop_text: Optional[str] = None,
    telop_settings: Optional[dict] = None,
) -> str:
    """1シーン分の動画と音声を合成（オプションでテロップ追加）

    Args:
        video_path: 動画ファイルパス
        voice_path: 音声ファイルパス
        output_path: 出力ファイルパス
        telop_text: テロップテキスト（Noneの場合はテロップなし）
        telop_settings: テロップ設定 {
            "font_size": int,
            "font_style": "gothic" | "mincho",
            "font_color": str,
            "shadow_color": str,
            "shadow_opacity": float,
            "shadow_distance": int,
            "shadow_angle": int,
        }
    """
    if telop_text and telop_text.strip():
        # テロップあり：drawtextフィルターを使用
        settings = telop_settings or {}
        font_size = settings.get("font_size", 48)
        font_style = settings.get("font_style", "mincho")
        font_color = settings.get("font_color", "white")
        shadow_color = settings.get("shadow_color", "black")
        shadow_opacity = settings.get("shadow_opacity", 0.4)
        shadow_distance = settings.get("shadow_distance", 5)
        shadow_angle = settings.get("shadow_angle", -45)

        font_path = _get_system_font(style=font_style)
        escaped_text = _escape_text_for_ffmpeg(telop_text)

        # シャドウのオフセットを計算（アングルと距離から）
        angle_rad = math.radians(shadow_angle)
        shadow_x = int(shadow_distance * math.cos(angle_rad))
        shadow_y = int(-shadow_distance * math.sin(angle_rad))  # 画面座標系

        # 位置は中央固定
        y_pos = "(h-th)/2"

        # drawtextフィルター構築（シャドウ付き、背景ボックスなし）
        drawtext_filter = (
            f"drawtext=text='{escaped_text}'"
            f":x=(w-tw)/2:y={y_pos}"
            f":fontsize={font_size}"
            f":fontcolor={font_color}"
            f":shadowcolor={shadow_color}@{shadow_opacity}"
            f":shadowx={shadow_x}:shadowy={shadow_y}"
        )
        if font_path:
            drawtext_filter += f":fontfile='{font_path}'"

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", voice_path,
            "-filter_complex", f"[0:v]{drawtext_filter}[v]",
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_path,
        ]
    else:
        # テロップなし：従来の処理
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", voice_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("FFmpeg error: %s", result.stderr)
        raise RuntimeError(f"シーン合成失敗: {result.stderr}")

    logger.info("シーン合成: %s", output_path)
    return output_path


def concat_scenes_simple(scene_paths: list[str], output_path: str) -> str:
    """全シーンを単純結合して最終動画を出力（トランジションなし）"""
    concat_list_path = os.path.join(os.path.dirname(output_path), "concat_list.txt")

    with open(concat_list_path, "w") as f:
        for path in scene_paths:
            f.write(f"file '{path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    os.remove(concat_list_path)
    logger.info("最終動画出力: %s", output_path)
    return output_path


def concat_scenes_with_gap(
    scene_paths: list[str],
    output_path: str,
    transitions: list[dict],
) -> str:
    """シーン間に空白（動画フリーズ＋無音）を挿入して全シーンを結合"""
    if len(scene_paths) < 2:
        return concat_scenes_simple(scene_paths, output_path)

    # 空白があるかチェック
    has_gap = any(t.get("audioGap", 0) > 0 for t in transitions)

    if not has_gap:
        # 空白なしの場合は単純結合
        return concat_scenes_simple(scene_paths, output_path)

    # 入力ファイル引数
    inputs = []
    for path in scene_paths:
        inputs.extend(["-i", path])

    # フィルタ複合体を構築
    # 動画: 最後のフレームをフリーズして延長
    # 音声: 無音を追加
    filter_parts = []
    video_streams = []
    audio_streams = []

    for i in range(len(scene_paths)):
        # 最後のシーン以外は、動画と音声の両方に空白を追加
        if i < len(transitions):
            gap_duration = transitions[i].get("audioGap", 0)
            if gap_duration > 0:
                # 動画: tpadで最後のフレームをフリーズして延長
                filter_parts.append(
                    f"[{i}:v]tpad=stop_mode=clone:stop_duration={gap_duration}[v{i}]"
                )
                video_streams.append(f"[v{i}]")

                # 音声: apadで無音を追加
                filter_parts.append(
                    f"[{i}:a]apad=pad_dur={gap_duration}[a{i}]"
                )
                audio_streams.append(f"[a{i}]")
            else:
                video_streams.append(f"[{i}:v]")
                audio_streams.append(f"[{i}:a]")
        else:
            video_streams.append(f"[{i}:v]")
            audio_streams.append(f"[{i}:a]")

    # 動画をconcat
    video_concat = "".join(video_streams) + f"concat=n={len(scene_paths)}:v=1:a=0[vout]"
    filter_parts.append(video_concat)

    # 音声をconcat
    audio_concat = "".join(audio_streams) + f"concat=n={len(scene_paths)}:v=0:a=1[aout]"
    filter_parts.append(audio_concat)

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info("空白付き合成コマンド: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("FFmpeg error: %s", result.stderr)
        # フォールバック：単純結合
        logger.warning("空白適用に失敗、単純結合にフォールバック")
        return concat_scenes_simple(scene_paths, output_path)

    logger.info("空白付き最終動画出力: %s", output_path)
    return output_path


def compose_final(
    video_paths: list[str],
    voice_paths: list[str],
    output_dir: str,
    transitions: Optional[list[dict]] = None,
    telop_texts: Optional[list[str]] = None,
    telop_settings: Optional[dict] = None,
) -> str:
    """全シーンの動画+音声合成→結合→final.mp4

    Args:
        video_paths: 動画ファイルパスのリスト
        voice_paths: 音声ファイルパスのリスト
        output_dir: 出力ディレクトリ
        transitions: トランジション設定のリスト
        telop_texts: 各シーンのテロップテキストのリスト（Noneの場合はテロップなし）
        telop_settings: テロップ設定（全シーン共通）
    """
    composed_paths = []

    for i, (vid, voice) in enumerate(zip(video_paths, voice_paths)):
        composed_path = os.path.join(output_dir, f"composed_{i + 1}.mp4")
        telop_text = telop_texts[i] if telop_texts and i < len(telop_texts) else None
        compose_scene(vid, voice, composed_path, telop_text=telop_text, telop_settings=telop_settings)
        composed_paths.append(composed_path)

    final_path = os.path.join(output_dir, "final.mp4")

    # 空白設定がある場合は空白付き結合（動画フリーズ＋無音）
    if transitions and any(t.get("audioGap", 0) > 0 for t in transitions):
        concat_scenes_with_gap(composed_paths, final_path, transitions)
    else:
        concat_scenes_simple(composed_paths, final_path)

    # 中間ファイル削除
    for p in composed_paths:
        os.remove(p)

    return final_path
