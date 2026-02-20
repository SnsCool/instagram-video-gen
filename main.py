#!/usr/bin/env python3
"""Instagram動画自動生成 MVP"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from pipeline.script_generator import generate_script
from pipeline.image_generator import generate_image
from pipeline.video_generator import generate_video, generate_videos_parallel
from pipeline.voice_generator import generate_voice
from pipeline.composer import compose_final

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def generate_script_only(
    theme: str,
    duration_sec: int = None,
    mock: bool = False,
    tone: str = None,
    first_person: str = None,
    second_person: str = None,
    reference_images: list[bytes] = None,
    reference_script: str = None,
) -> tuple[dict, str]:
    """STEP1のみ: テーマから台本を生成して返す。(script, output_dir)を返す。"""
    run_id = time.strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(config.OUTPUT_DIR, run_id)
    os.makedirs(output_dir, exist_ok=True)

    logger.info("=== 台本生成開始: テーマ「%s」 (mock=%s) ===", theme, mock)

    script = generate_script(
        theme, duration_sec=duration_sec, mock=mock,
        tone=tone, first_person=first_person, second_person=second_person,
        reference_images=reference_images,
        reference_script=reference_script,
    )

    script_path = os.path.join(output_dir, "script.json")
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    logger.info("台本保存: %s", script_path)

    return script, output_dir


def generate_images_only(
    script: dict,
    output_dir: str,
    mock: bool = False,
    on_progress=None,
) -> list[str]:
    """STEP2のみ: 台本からシーン画像を並列生成して返す。"""
    def emit(step, step_name, status, detail, **extra):
        if on_progress:
            on_progress({"step": step, "stepName": step_name, "totalSteps": 5,
                         "status": status, "detail": detail, **extra})

    scenes = script["scenes"]
    num_scenes = len(scenes)

    logger.info("--- STEP 2/5: 画像生成 (%d枚, 並列処理) ---", num_scenes)
    emit(2, "image", "running", f"画像生成中 (0/{num_scenes})",
         scene=0, totalScenes=num_scenes)

    # シーンIDをキーとした結果格納用
    results: dict[int, str] = {}
    completed_count = 0

    def generate_one(scene):
        return scene["scene_id"], generate_image(scene, output_dir, mock=mock)

    # 並列で画像生成
    with ThreadPoolExecutor(max_workers=min(num_scenes, 5)) as executor:
        futures = {executor.submit(generate_one, scene): scene for scene in scenes}

        for future in as_completed(futures):
            scene_id, path = future.result()
            results[scene_id] = path
            completed_count += 1
            emit(2, "image", "running", f"画像生成中 ({completed_count}/{num_scenes})",
                 scene=completed_count, totalScenes=num_scenes)

    # シーン順に並び替えて返す
    image_paths = [results[scene["scene_id"]] for scene in scenes]
    emit(2, "image", "done", "画像生成完了")

    return image_paths


def generate_videos_only(
    script: dict,
    image_paths: list[str],
    output_dir: str,
    mock: bool = False,
    on_progress=None,
) -> list[str]:
    """STEP3のみ: 動画を全て同時に開始して並列生成。"""
    def emit(step, step_name, status, detail, **extra):
        if on_progress:
            on_progress({"step": step, "stepName": step_name, "totalSteps": 5,
                         "status": status, "detail": detail, **extra})

    scenes = script["scenes"]
    num_scenes = len(scenes)

    logger.info("--- STEP 3/5: 動画生成 (%d本, 全並列) (mock=%s) ---", num_scenes, mock)
    emit(3, "video", "running", f"動画生成中 (0/{num_scenes})",
         scene=0, totalScenes=num_scenes)

    def video_progress(completed, total):
        emit(3, "video", "running", f"動画生成中 ({completed}/{total})",
             scene=completed, totalScenes=total)

    # 全シーンを同時に開始して並列でポーリング
    video_paths = generate_videos_parallel(
        scenes=scenes,
        image_paths=image_paths,
        output_dir=output_dir,
        mock=mock,
        on_progress=video_progress,
    )

    emit(3, "video", "done", "動画生成完了")
    return video_paths


def generate_voices_only(
    script: dict,
    output_dir: str,
    voice_id: str = None,
    mock: bool = False,
    on_progress=None,
    speed: float = 1.0,
    volume: float = 0.0,
) -> list[str]:
    """STEP4のみ: 音声生成を行い voice_paths を返す。"""
    def emit(step, step_name, status, detail, **extra):
        if on_progress:
            on_progress({"step": step, "stepName": step_name, "totalSteps": 5,
                         "status": status, "detail": detail, **extra})

    scenes = script["scenes"]

    logger.info("--- STEP 4/5: 音声生成 (%d本) (mock=%s, speed=%.1f, volume=%.1f) ---", len(scenes), mock, speed, volume)
    voice_paths = []
    for i, scene in enumerate(scenes, 1):
        emit(4, "voice", "running", f"音声生成中 ({i}/{len(scenes)})",
             scene=i, totalScenes=len(scenes))
        path = generate_voice(scene, output_dir, voice_id=voice_id, mock=mock, speed=speed, volume=volume)
        voice_paths.append(path)
    emit(4, "voice", "done", "音声生成完了")

    return voice_paths


def generate_videos_and_voices(
    script: dict,
    image_paths: list[str],
    output_dir: str,
    voice_id: str = None,
    mock: bool = False,
    on_progress=None,
) -> tuple[list[str], list[str]]:
    """STEP3+4: 動画生成と音声生成を行い (video_paths, voice_paths) を返す。"""
    video_paths = generate_videos_only(script, image_paths, output_dir, mock=mock, on_progress=on_progress)
    voice_paths = generate_voices_only(script, output_dir, voice_id=voice_id, mock=mock, on_progress=on_progress)
    return video_paths, voice_paths


def regenerate_voices_only(
    script: dict,
    output_dir: str,
    voice_id: str = None,
    mock: bool = False,
    on_progress=None,
    speed: float = 1.0,
    volume: float = 0.0,
) -> list[str]:
    """STEP4のみ再実行: 台本のテキストから音声を再生成して返す。"""
    def emit(step, step_name, status, detail, **extra):
        if on_progress:
            on_progress({"step": step, "stepName": step_name, "totalSteps": 5,
                         "status": status, "detail": detail, **extra})

    scenes = script["scenes"]

    logger.info("--- STEP 4/5: 音声再生成 (%d本) (speed=%.1f, volume=%.1f) ---", len(scenes), speed, volume)
    voice_paths = []
    for i, scene in enumerate(scenes, 1):
        emit(4, "voice", "running", f"音声再生成中 ({i}/{len(scenes)})",
             scene=i, totalScenes=len(scenes))
        path = generate_voice(scene, output_dir, voice_id=voice_id, mock=mock, speed=speed, volume=volume)
        voice_paths.append(path)
    emit(4, "voice", "done", "音声再生成完了")

    return voice_paths


def compose_only(
    video_paths: list[str],
    voice_paths: list[str],
    output_dir: str,
    on_progress=None,
    transitions: list[dict] = None,
    telop_texts: list[str] = None,
    telop_settings: dict = None,
) -> str:
    """STEP5のみ: 動画＋音声を合成して最終ファイルを返す。

    Args:
        telop_texts: 各シーンのテロップテキストのリスト
        telop_settings: テロップ設定（position, font_size, font_color等）
    """
    def emit(step, step_name, status, detail, **extra):
        if on_progress:
            on_progress({"step": step, "stepName": step_name, "totalSteps": 5,
                         "status": status, "detail": detail, **extra})

    logger.info("--- STEP 5/5: 動画＋音声合成 ---")
    emit(5, "compose", "running", "動画＋音声合成中...")
    final_path = compose_final(
        video_paths, voice_paths, output_dir,
        transitions=transitions,
        telop_texts=telop_texts,
        telop_settings=telop_settings,
    )
    emit(5, "compose", "done", "合成完了")

    logger.info("=== 完了: %s ===", final_path)
    return final_path


def run_from_images(
    script: dict,
    image_paths: list[str],
    output_dir: str,
    voice_id: str = None,
    mock: bool = False,
    on_progress=None,
) -> str:
    """STEP3〜5: 生成済み画像からパイプラインの残りを実行する。"""
    video_paths, voice_paths = generate_videos_and_voices(
        script, image_paths, output_dir, voice_id=voice_id, mock=mock, on_progress=on_progress,
    )
    return compose_only(
        video_paths, voice_paths, output_dir, on_progress=on_progress,
    )


def run_from_script(
    script: dict,
    output_dir: str,
    voice_id: str = None,
    mock: bool = False,
    on_progress=None,
) -> str:
    """STEP2〜5: 生成済み台本からパイプラインの残りを実行する。"""
    image_paths = generate_images_only(
        script, output_dir, mock=mock, on_progress=on_progress,
    )
    return run_from_images(
        script, image_paths, output_dir, voice_id=voice_id, mock=mock, on_progress=on_progress,
    )


def run(
    theme: str,
    duration_sec: int = None,
    voice_id: str = None,
    mock: bool = False,
    on_progress=None,
) -> str:
    def emit(step, step_name, status, detail, **extra):
        if on_progress:
            on_progress({"step": step, "stepName": step_name, "totalSteps": 5,
                         "status": status, "detail": detail, **extra})

    emit(1, "script", "running", "台本生成中...")
    script, output_dir = generate_script_only(
        theme, duration_sec=duration_sec, mock=mock,
    )
    emit(1, "script", "done", "台本生成完了")

    return run_from_script(
        script, output_dir, voice_id=voice_id, mock=mock, on_progress=on_progress,
    )


def main():
    parser = argparse.ArgumentParser(description="Instagram動画自動生成 MVP")
    parser.add_argument("--theme", required=True, help="投稿テーマ（例: '30代 転職 失敗'）")
    parser.add_argument("--voice-id", default=None, help="Fish Audio ボイスID")
    parser.add_argument("--duration", type=int, default=None, help="動画秒数（例: 45）")
    parser.add_argument("--mock", action="store_true", help="モックモード（APIを呼ばずダミーで実行）")

    args = parser.parse_args()

    final_path = run(
        theme=args.theme,
        voice_id=args.voice_id,
        duration_sec=args.duration,
        mock=args.mock,
    )

    print(f"\n出力: {final_path}")


if __name__ == "__main__":
    main()
