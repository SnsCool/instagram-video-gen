"""動画生成（Google Veo 2 via Gemini API）"""

import logging
import os
import re
import subprocess
import time
from typing import Optional

import httpx

import config

logger = logging.getLogger(__name__)


def _create_dummy_video(image_path: str, output_path: str, duration_sec: int) -> None:
    """画像から無音ダミー動画を生成（モック用、FFmpeg使用）"""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration_sec),
        "-vf", f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},zoompan=z='min(zoom+0.001,1.05)':d={duration_sec * 25}:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "25",
        "-an",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def generate_video(scene: dict, image_path: str, output_dir: str, mock: bool = False, on_progress=None, instructions: str = None) -> str:
    scene_id = scene["scene_id"]
    duration_sec = scene["duration_sec"]
    output_path = os.path.join(output_dir, f"scene_{scene_id}.mp4")

    if mock:
        _create_dummy_video(image_path, output_path, duration_sec)
        logger.info("[MOCK] 動画生成: scene_%d (%d秒) → %s", scene_id, duration_sec, output_path)
        return output_path

    # --- 本番実装（Google Veo 2）---
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # 画像を読み込み
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # MIMEタイプを判定
    if image_bytes[:3] == b"\xff\xd8\xff":
        mime_type = "image/jpeg"
    elif image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        mime_type = "image/png"
    else:
        mime_type = "image/jpeg"

    # Veo 2でimage-to-video生成
    # duration_secをVeo2のサポート範囲にマッピング（5-8秒）
    # Veo2は5秒か8秒をサポート
    veo_duration = 8 if duration_sec >= 6 else 5

    # プロンプトを構築（カスタム指示があれば追加）
    base_prompt = scene.get("image_prompt", "cinematic camera movement, smooth motion")
    if instructions:
        video_prompt = f"{base_prompt}. Additional instructions: {instructions}"
        logger.info("Veo2動画生成開始: scene_%d (duration=%ds) - カスタム指示あり", scene_id, veo_duration)
    else:
        video_prompt = base_prompt
        logger.info("Veo2動画生成開始: scene_%d (duration=%ds)", scene_id, veo_duration)

    operation = client.models.generate_videos(
        model="veo-2.0-generate-001",
        prompt=video_prompt,
        image=types.Image(image_bytes=image_bytes, mime_type=mime_type),
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            duration_seconds=veo_duration,
            number_of_videos=1,
        ),
    )

    # ポーリングして完了を待つ
    max_wait = 600  # 最大10分
    poll_interval = 10
    elapsed = 0

    while elapsed < max_wait:
        operation = client.operations.get(operation)

        if operation.done:
            break

        logger.info("Veo2生成中: scene_%d (経過: %ds)", scene_id, elapsed)
        if on_progress:
            on_progress(elapsed)
        time.sleep(poll_interval)
        elapsed += poll_interval

    if not operation.done:
        raise TimeoutError(f"Veo2動画生成タイムアウト: scene_{scene_id}")

    # 結果を取得
    if not operation.response or not operation.response.generated_videos:
        raise RuntimeError(f"Veo2動画生成失敗: scene_{scene_id} - 動画が生成されませんでした")

    generated_video = operation.response.generated_videos[0]

    # 動画をダウンロード（認証付きAPIを使用）
    video_file = generated_video.video

    # ファイル名を取得してダウンロード
    file_name = None
    if hasattr(video_file, 'name') and video_file.name:
        file_name = video_file.name
    elif hasattr(video_file, 'uri') and video_file.uri:
        # URIからファイル名を抽出 (例: files/xxxxx)
        import re
        match = re.search(r'files/([^/:]+)', video_file.uri)
        if match:
            file_name = f"files/{match.group(1)}"

    if file_name:
        # 認証付きでダウンロード
        import httpx
        download_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}:download?alt=media&key={config.GEMINI_API_KEY}"
        resp = httpx.get(download_url, timeout=120, follow_redirects=True)
        resp.raise_for_status()
        video_bytes = resp.content
    else:
        raise RuntimeError(f"Veo2動画生成失敗: scene_{scene_id} - ダウンロードURLが取得できませんでした")

    with open(output_path, "wb") as f:
        f.write(video_bytes)

    logger.info("Veo2動画生成完了: scene_%d → %s", scene_id, output_path)
    return output_path


def generate_videos_parallel(
    scenes: list[dict],
    image_paths: list[str],
    output_dir: str,
    mock: bool = False,
    on_progress=None,
) -> list[str]:
    """複数の動画を並列生成（全て同時に開始し、並列でポーリング）

    Args:
        scenes: シーン情報のリスト
        image_paths: 各シーンの画像パスのリスト
        output_dir: 出力ディレクトリ
        mock: モックモード
        on_progress: 進捗コールバック(completed_count, total_count)

    Returns:
        生成された動画パスのリスト（シーン順）
    """
    num_scenes = len(scenes)

    if mock:
        # モックモードは順次処理
        results = []
        for scene, img_path in zip(scenes, image_paths):
            path = generate_video(scene, img_path, output_dir, mock=True)
            results.append(path)
            if on_progress:
                on_progress(len(results), num_scenes)
        return results

    # --- 本番実装：全て同時に開始 ---
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # 全シーンの生成を同時に開始
    operations = []
    output_paths = []

    for scene, img_path in zip(scenes, image_paths):
        scene_id = scene["scene_id"]
        duration_sec = scene["duration_sec"]
        output_path = os.path.join(output_dir, f"scene_{scene_id}.mp4")
        output_paths.append(output_path)

        # 画像を読み込み
        with open(img_path, "rb") as f:
            image_bytes = f.read()

        # MIMEタイプを判定
        if image_bytes[:3] == b"\xff\xd8\xff":
            mime_type = "image/jpeg"
        elif image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"

        # Veo2のduration
        veo_duration = 8 if duration_sec >= 6 else 5

        video_prompt = scene.get("image_prompt", "cinematic camera movement, smooth motion")

        logger.info("Veo2動画生成開始: scene_%d (duration=%ds)", scene_id, veo_duration)

        operation = client.models.generate_videos(
            model="veo-2.0-generate-001",
            prompt=video_prompt,
            image=types.Image(image_bytes=image_bytes, mime_type=mime_type),
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16",
                duration_seconds=veo_duration,
                number_of_videos=1,
            ),
        )
        operations.append({
            "operation": operation,
            "scene_id": scene_id,
            "output_path": output_path,
            "done": False,
        })

    logger.info("全%dシーンの動画生成を開始しました", num_scenes)

    # 並列でポーリング（全てのoperationを1ループでチェック）
    max_wait = 600  # 最大10分
    poll_interval = 5  # 5秒間隔（より頻繁にチェック）
    elapsed = 0
    completed_count = 0

    while elapsed < max_wait:
        all_done = True

        for op_info in operations:
            if op_info["done"]:
                continue

            # operationの状態を更新
            op_info["operation"] = client.operations.get(op_info["operation"])

            if op_info["operation"].done:
                op_info["done"] = True
                completed_count += 1
                logger.info("Veo2動画生成完了: scene_%d (%d/%d)",
                           op_info["scene_id"], completed_count, num_scenes)
                if on_progress:
                    on_progress(completed_count, num_scenes)
            else:
                all_done = False

        if all_done:
            break

        logger.info("Veo2生成中: %d/%d 完了 (経過: %ds)", completed_count, num_scenes, elapsed)
        time.sleep(poll_interval)
        elapsed += poll_interval

    # 結果を取得してダウンロード
    for op_info in operations:
        operation = op_info["operation"]
        scene_id = op_info["scene_id"]
        output_path = op_info["output_path"]

        if not operation.done:
            raise TimeoutError(f"Veo2動画生成タイムアウト: scene_{scene_id}")

        if not operation.response or not operation.response.generated_videos:
            raise RuntimeError(f"Veo2動画生成失敗: scene_{scene_id} - 動画が生成されませんでした")

        generated_video = operation.response.generated_videos[0]
        video_file = generated_video.video

        # ファイル名を取得
        file_name = None
        if hasattr(video_file, 'name') and video_file.name:
            file_name = video_file.name
        elif hasattr(video_file, 'uri') and video_file.uri:
            match = re.search(r'files/([^/:]+)', video_file.uri)
            if match:
                file_name = f"files/{match.group(1)}"

        if not file_name:
            raise RuntimeError(f"Veo2動画生成失敗: scene_{scene_id} - ダウンロードURLが取得できませんでした")

        # ダウンロード
        download_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}:download?alt=media&key={config.GEMINI_API_KEY}"
        resp = httpx.get(download_url, timeout=120, follow_redirects=True)
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(resp.content)

        logger.info("Veo2動画ダウンロード完了: scene_%d → %s", scene_id, output_path)

    return output_paths
