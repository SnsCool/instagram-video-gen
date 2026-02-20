"""FastAPI server with SSE progress streaming."""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

import config
from main import generate_script_only, generate_images_only, generate_videos_only, generate_voices_only, regenerate_voices_only, compose_only

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Instagram Video Generator")

# CORS設定：環境変数またはデフォルト
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store progress queues keyed by run_id
_progress_queues: dict = {}
_run_results: dict = {}
_run_meta: dict = {}  # run_id -> {script, output_dir, mock}

# History file path
HISTORY_FILE = os.path.join(config.OUTPUT_DIR, "history.json")


def _load_history() -> list[dict]:
    """履歴をファイルから読み込む"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_history(history: list[dict]) -> None:
    """履歴をファイルに保存"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _add_to_history(run_id: str, meta: dict) -> None:
    """履歴に追加"""
    history = _load_history()

    # 画像・動画・音声のURLを構築
    images = []
    if meta.get("image_paths"):
        for i, path in enumerate(meta["image_paths"]):
            rel = os.path.relpath(path, config.OUTPUT_DIR)
            images.append({"scene_id": i + 1, "imageUrl": f"/output/{rel}"})

    videos = []
    if meta.get("video_paths"):
        for i, path in enumerate(meta["video_paths"]):
            rel = os.path.relpath(path, config.OUTPUT_DIR)
            videos.append({"scene_id": i + 1, "videoUrl": f"/output/{rel}"})

    voices = []
    if meta.get("voice_paths"):
        for i, path in enumerate(meta["voice_paths"]):
            rel = os.path.relpath(path, config.OUTPUT_DIR)
            scene = meta["script"]["scenes"][i] if meta.get("script") else {}
            voices.append({
                "scene_id": i + 1,
                "text": scene.get("text", ""),
                "voiceUrl": f"/output/{rel}",
            })

    final_video = None
    final_path = os.path.join(meta["output_dir"], "final.mp4")
    if os.path.exists(final_path):
        rel = os.path.relpath(final_path, config.OUTPUT_DIR)
        final_video = f"/output/{rel}"

    entry = {
        "run_id": run_id,
        "created_at": run_id,  # run_id is timestamp format
        "theme": meta.get("theme", ""),
        "script": meta.get("script"),
        "images": images,
        "videos": videos,
        "voices": voices,
        "videoUrl": final_video,
        "output_dir": meta["output_dir"],
    }

    # 既存のエントリを更新するか追加
    existing_idx = next((i for i, h in enumerate(history) if h["run_id"] == run_id), None)
    if existing_idx is not None:
        history[existing_idx] = entry
    else:
        history.insert(0, entry)  # 最新を先頭に

    # 最大100件に制限
    history = history[:100]

    _save_history(history)


@app.get("/api/history")
def get_history():
    """履歴一覧を取得"""
    history = _load_history()
    # サムネイル用に最初の画像だけ返す
    return {
        "history": [
            {
                "run_id": h["run_id"],
                "created_at": h.get("created_at", h["run_id"]),
                "theme": h.get("theme", ""),
                "title": h.get("script", {}).get("title", "") if h.get("script") else "",
                "thumbnail": h["images"][0]["imageUrl"] if h.get("images") else None,
                "videoUrl": h.get("videoUrl"),
                "scene_count": len(h.get("images", [])),
            }
            for h in history
        ]
    }


@app.get("/api/history/{run_id}")
def get_history_detail(run_id: str):
    """特定の履歴の詳細を取得"""
    history = _load_history()
    entry = next((h for h in history if h["run_id"] == run_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="History not found")
    return entry


@app.post("/api/history/{run_id}/restore")
def restore_from_history(run_id: str):
    """履歴からセッションを復元"""
    history = _load_history()
    entry = next((h for h in history if h["run_id"] == run_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="History not found")

    # 出力ディレクトリが存在するか確認
    output_dir = entry.get("output_dir")
    if not output_dir or not os.path.exists(output_dir):
        raise HTTPException(status_code=400, detail="Output directory not found")

    # パスを復元
    image_paths = []
    if entry.get("images"):
        for img in entry["images"]:
            # /output/xxx/scene_1.png -> full path
            rel_path = img["imageUrl"].replace("/output/", "")
            full_path = os.path.join(config.OUTPUT_DIR, rel_path)
            if os.path.exists(full_path):
                image_paths.append(full_path)

    video_paths = []
    if entry.get("videos"):
        for vid in entry["videos"]:
            rel_path = vid["videoUrl"].replace("/output/", "")
            full_path = os.path.join(config.OUTPUT_DIR, rel_path)
            if os.path.exists(full_path):
                video_paths.append(full_path)

    voice_paths = []
    if entry.get("voices"):
        for voice in entry["voices"]:
            rel_path = voice["voiceUrl"].replace("/output/", "")
            full_path = os.path.join(config.OUTPUT_DIR, rel_path)
            if os.path.exists(full_path):
                voice_paths.append(full_path)

    # メタデータを復元
    _run_meta[run_id] = {
        "script": entry.get("script"),
        "output_dir": output_dir,
        "theme": entry.get("theme", ""),
        "voice_id": None,
        "mock": False,
        "image_paths": image_paths if image_paths else None,
        "video_paths": video_paths if video_paths else None,
        "voice_paths": voice_paths if voice_paths else None,
    }

    return {
        "run_id": run_id,
        "script": entry.get("script"),
        "images": entry.get("images"),
        "videos": entry.get("videos"),
        "voices": entry.get("voices"),
        "videoUrl": entry.get("videoUrl"),
    }


@app.delete("/api/history/{run_id}")
def delete_history(run_id: str):
    """履歴を削除"""
    history = _load_history()
    new_history = [h for h in history if h["run_id"] != run_id]
    if len(new_history) == len(history):
        raise HTTPException(status_code=404, detail="History not found")
    _save_history(new_history)
    return {"ok": True}


class GenerateRequest(BaseModel):
    theme: str
    voice_id: Optional[str] = None
    duration: Optional[int] = None
    mock: bool = False
    tone: Optional[str] = None
    first_person: Optional[str] = None
    second_person: Optional[str] = None
    reference_script: Optional[str] = None


@app.get("/api/voices")
def list_voices():
    """利用可能なボイス一覧を返す。"""
    return {"voices": config.VOICES}


@app.post("/api/generate")
async def start_generation(request: Request):
    """STEP1: 台本だけ同期的に生成して返す。JSON / multipart 両対応。"""
    import time as _time

    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        params_json = form.get("params")
        if params_json is None:
            raise HTTPException(status_code=400, detail="params field is required")
        params = json.loads(params_json)
        ref_images_bytes: list[bytes] = []
        for key, value in form.multi_items():
            if key == "reference_images":
                ref_images_bytes.append(await value.read())
        await form.close()
    else:
        params = await request.json()
        ref_images_bytes = []

    req = GenerateRequest(**params)

    run_id = _time.strftime("%Y%m%d_%H%M%S")

    # Patch strftime so generate_script_only uses our run_id
    _original_strftime = _time.strftime

    def _patched_strftime(fmt, *args):
        if fmt == "%Y%m%d_%H%M%S" and not args:
            _time.strftime = _original_strftime
            return run_id
        return _original_strftime(fmt, *args)

    _time.strftime = _patched_strftime

    try:
        script, output_dir = generate_script_only(
            theme=req.theme,
            duration_sec=req.duration,
            mock=req.mock,
            tone=req.tone,
            first_person=req.first_person,
            second_person=req.second_person,
            reference_images=ref_images_bytes if ref_images_bytes else None,
            reference_script=req.reference_script,
        )
    except Exception as e:
        logger.exception("Script generation failed")
        raise HTTPException(status_code=500, detail=str(e))

    _run_meta[run_id] = {
        "script": script,
        "output_dir": output_dir,
        "voice_id": req.voice_id,
        "mock": req.mock,
        "theme": req.theme,
    }

    return {"run_id": run_id, "script": script}


class ContinueRequest(BaseModel):
    script: Optional[dict] = None
    changed_scene_ids: Optional[list[int]] = None  # 変更されたシーンのIDリスト（指定時はそのシーンのみ再生成）


@app.post("/api/generate/{run_id}/continue")
def continue_generation(run_id: str, req: ContinueRequest = ContinueRequest()):
    """STEP2のみ: 台本確認後、画像生成をバックグラウンド実行。完了時に images_ready を送信。

    changed_scene_ids が指定された場合、既存の画像を保持し、変更されたシーンのみ再生成する。
    """
    meta = _run_meta.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    # 編集済み台本が送られてきた場合は上書き
    if req.script is not None:
        meta["script"] = req.script
        script_path = os.path.join(meta["output_dir"], "script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(req.script, f, ensure_ascii=False, indent=2)

    q: queue.Queue = queue.Queue()
    _progress_queues[run_id] = q

    def on_progress(data: dict):
        q.put(data)

    # 部分再生成モード: 既存の画像があり、変更されたシーンのみ指定された場合
    existing_images = meta.get("image_paths")
    partial_mode = (
        req.changed_scene_ids is not None
        and len(req.changed_scene_ids) > 0
        and existing_images is not None
    )

    def worker():
        try:
            if partial_mode:
                # 部分再生成: 変更されたシーンのみ再生成
                from concurrent.futures import ThreadPoolExecutor, as_completed
                from pipeline.image_generator import generate_image

                scenes = meta["script"]["scenes"]
                changed_ids = set(req.changed_scene_ids)
                total_changed = len(changed_ids)

                on_progress({
                    "step": 2, "stepName": "image", "totalSteps": 5,
                    "status": "running",
                    "detail": f"変更されたシーンの画像を再生成中 (0/{total_changed})"
                })

                # 変更されたシーンのデータを準備
                scene_data = []
                for i, scene in enumerate(scenes):
                    if scene["scene_id"] in changed_ids:
                        scene_data.append({
                            "scene_index": i,
                            "scene": scene,
                        })

                def generate_one(data):
                    path = generate_image(data["scene"], meta["output_dir"], mock=meta["mock"])
                    return data["scene_index"], path

                # 並列で画像再生成
                completed_count = 0
                with ThreadPoolExecutor(max_workers=min(total_changed, 5)) as executor:
                    futures = {executor.submit(generate_one, data): data for data in scene_data}
                    for future in as_completed(futures):
                        scene_index, path = future.result()
                        existing_images[scene_index] = path
                        completed_count += 1
                        on_progress({
                            "step": 2, "stepName": "image", "totalSteps": 5,
                            "status": "running",
                            "detail": f"変更されたシーンの画像を再生成中 ({completed_count}/{total_changed})"
                        })

                image_paths = existing_images
            else:
                # 全シーン生成
                image_paths = generate_images_only(
                    script=meta["script"],
                    output_dir=meta["output_dir"],
                    mock=meta["mock"],
                    on_progress=on_progress,
                )

            meta["image_paths"] = image_paths

            # 各シーンの画像URLを組み立てて返す（キャッシュバスティング用タイムスタンプ付き）
            import time as _time
            cache_bust = int(_time.time() * 1000)
            images = []
            for scene, img_path in zip(meta["script"]["scenes"], image_paths):
                rel = os.path.relpath(img_path, config.OUTPUT_DIR)
                images.append({
                    "scene_id": scene["scene_id"],
                    "imageUrl": f"/output/{rel}?t={cache_bust}",
                })
            q.put({"status": "images_ready", "images": images})
        except Exception as e:
            logger.exception("Image generation failed for run_id=%s", run_id)
            q.put({"status": "error", "detail": str(e)})
            _run_results[run_id] = {"status": "error", "detail": str(e)}

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return {"ok": True}


class ComposeRequest(BaseModel):
    scene_order: Optional[list[int]] = None
    changed_scene_ids: Optional[list[int]] = None  # 変更されたシーンのIDリスト（指定時はそのシーンのみ再生成）


@app.post("/api/generate/{run_id}/compose")
def compose_generation(run_id: str, req: ComposeRequest = ComposeRequest()):
    """STEP3: カット確認後、動画のみ生成。完了時に videos_ready を送信。

    changed_scene_ids が指定された場合、既存の動画を保持し、変更されたシーンのみ再生成する。
    """
    meta = _run_meta.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    image_paths = meta.get("image_paths")
    if image_paths is None:
        raise HTTPException(status_code=400, detail="images not generated yet")

    script = meta["script"]

    # カットの並べ替えが指定された場合、image_paths のみを並べ替え（台本は変更しない）
    if req.scene_order is not None:
        order = req.scene_order  # scene_id のリスト
        path_map = {s["scene_id"]: p for s, p in zip(script["scenes"], image_paths)}
        # 画像パスのみを並べ替え（台本の順番に合わせて画像を再配置）
        # order[i] は「i番目のシーンにはどの画像を使うか」を示す
        image_paths = [path_map[order[i]] for i in range(len(order))]
        meta["image_paths"] = image_paths
        # 注: script["scenes"] は変更しない（台本のテキストは元の順番のまま）

    q: queue.Queue = queue.Queue()
    _progress_queues[run_id] = q

    def on_progress(data: dict):
        q.put(data)

    # 部分再生成モード: 既存の動画があり、変更されたシーンのみ指定された場合
    existing_videos = meta.get("video_paths")
    partial_mode = (
        req.changed_scene_ids is not None
        and len(req.changed_scene_ids) > 0
        and existing_videos is not None
    )

    def worker():
        try:
            if partial_mode:
                # 部分再生成: 変更されたシーンのみ再生成
                from concurrent.futures import ThreadPoolExecutor, as_completed
                from pipeline.video_generator import generate_video

                scenes = meta["script"]["scenes"]
                changed_ids = set(req.changed_scene_ids)
                total_changed = len(changed_ids)

                on_progress({
                    "step": 3, "stepName": "video", "totalSteps": 5,
                    "status": "running",
                    "detail": f"変更されたシーンの動画を再生成中 (0/{total_changed})"
                })

                # 変更されたシーンのデータを準備
                scene_data = []
                for i, scene in enumerate(scenes):
                    if scene["scene_id"] in changed_ids:
                        scene_data.append({
                            "scene_index": i,
                            "scene": scene,
                            "image_path": meta["image_paths"][i],
                        })

                def generate_one(data):
                    path = generate_video(
                        data["scene"], data["image_path"],
                        meta["output_dir"], mock=meta["mock"]
                    )
                    return data["scene_index"], path

                # 並列で動画再生成（Veo2のAPI負荷を考慮してmax_workers制限）
                completed_count = 0
                with ThreadPoolExecutor(max_workers=min(total_changed, 3)) as executor:
                    futures = {executor.submit(generate_one, data): data for data in scene_data}
                    for future in as_completed(futures):
                        scene_index, path = future.result()
                        existing_videos[scene_index] = path
                        completed_count += 1
                        on_progress({
                            "step": 3, "stepName": "video", "totalSteps": 5,
                            "status": "running",
                            "detail": f"変更されたシーンの動画を再生成中 ({completed_count}/{total_changed})"
                        })

                video_paths = existing_videos
            else:
                # 全シーン生成
                video_paths = generate_videos_only(
                    script=meta["script"],
                    image_paths=meta["image_paths"],
                    output_dir=meta["output_dir"],
                    mock=meta["mock"],
                    on_progress=on_progress,
                )

            meta["video_paths"] = video_paths

            # 各シーンの動画URLを組み立てて返す（キャッシュバスティング用タイムスタンプ付き）
            import time as _time
            cache_bust = int(_time.time() * 1000)
            videos = []
            for scene, vp in zip(meta["script"]["scenes"], video_paths):
                rel = os.path.relpath(vp, config.OUTPUT_DIR)
                videos.append({
                    "scene_id": scene["scene_id"],
                    "videoUrl": f"/output/{rel}?t={cache_bust}",
                })
            q.put({"status": "videos_ready", "videos": videos})
        except Exception as e:
            logger.exception("Video/voice generation failed for run_id=%s", run_id)
            q.put({"status": "error", "detail": str(e)})
            _run_results[run_id] = {"status": "error", "detail": str(e)}

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return {"ok": True}


class GenerateVoicesRequest(BaseModel):
    speed: Optional[float] = 1.0
    volume: Optional[float] = 0.0
    changed_scene_ids: Optional[list[int]] = None  # 変更されたシーンのIDリスト（指定時はそのシーンのみ再生成）


@app.post("/api/generate/{run_id}/generate-voices")
def generate_voices(run_id: str, req: GenerateVoicesRequest = GenerateVoicesRequest()):
    """STEP4: 動画確認後、音声を生成。完了時に voices_ready を送信。

    changed_scene_ids が指定された場合、既存の音声を保持し、変更されたシーンのみ再生成する。
    """
    meta = _run_meta.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    if meta.get("video_paths") is None:
        raise HTTPException(status_code=400, detail="videos not generated yet")

    # 音声設定を保存
    meta["voice_speed"] = req.speed
    meta["voice_volume"] = req.volume

    q: queue.Queue = queue.Queue()
    _progress_queues[run_id] = q

    def on_progress(data: dict):
        q.put(data)

    # 部分再生成モード: 既存の音声があり、変更されたシーンのみ指定された場合
    existing_voices = meta.get("voice_paths")
    partial_mode = (
        req.changed_scene_ids is not None
        and len(req.changed_scene_ids) > 0
        and existing_voices is not None
    )

    def worker():
        try:
            if partial_mode:
                # 部分再生成: 変更されたシーンのみ再生成
                from pipeline.voice_generator import generate_voice

                scenes = meta["script"]["scenes"]
                changed_ids = set(req.changed_scene_ids)
                total_changed = len(changed_ids)

                on_progress({
                    "step": 4, "stepName": "voice", "totalSteps": 5,
                    "status": "running",
                    "detail": f"変更されたシーンの音声を再生成中 (0/{total_changed})"
                })

                # 変更されたシーンの音声を順次生成
                completed_count = 0
                for i, scene in enumerate(scenes):
                    if scene["scene_id"] in changed_ids:
                        path = generate_voice(
                            scene, meta["output_dir"],
                            voice_id=meta.get("voice_id"),
                            mock=meta["mock"],
                            speed=req.speed,
                            volume=req.volume,
                        )
                        existing_voices[i] = path
                        completed_count += 1
                        on_progress({
                            "step": 4, "stepName": "voice", "totalSteps": 5,
                            "status": "running",
                            "detail": f"変更されたシーンの音声を再生成中 ({completed_count}/{total_changed})"
                        })

                voice_paths = existing_voices
            else:
                # 全シーン生成
                voice_paths = generate_voices_only(
                    script=meta["script"],
                    output_dir=meta["output_dir"],
                    voice_id=meta.get("voice_id"),
                    mock=meta["mock"],
                    on_progress=on_progress,
                    speed=req.speed,
                    volume=req.volume,
                )

            meta["voice_paths"] = voice_paths
            voices = []
            for scene, vp in zip(meta["script"]["scenes"], voice_paths):
                rel = os.path.relpath(vp, config.OUTPUT_DIR)
                voices.append({
                    "scene_id": scene["scene_id"],
                    "text": scene["text"],
                    "emotion": scene.get("emotion", ""),
                    "voiceUrl": f"/output/{rel}",
                })
            q.put({"status": "voices_ready", "voices": voices})
        except Exception as e:
            logger.exception("Voice generation failed for run_id=%s", run_id)
            q.put({"status": "error", "detail": str(e)})
            _run_results[run_id] = {"status": "error", "detail": str(e)}

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return {"ok": True}


class RegenerateImagesRequest(BaseModel):
    scene_instructions: dict[str, str]  # scene_id(str) -> instructions


@app.post("/api/generate/{run_id}/regenerate-images")
def regenerate_images(run_id: str, req: RegenerateImagesRequest):
    """複数シーンの画像を再生成（シーンごとの指示対応）。完了時に images_ready を送信。"""
    meta = _run_meta.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    if meta.get("image_paths") is None:
        raise HTTPException(status_code=400, detail="images not generated yet")

    q: queue.Queue = queue.Queue()
    _progress_queues[run_id] = q

    def on_progress(data: dict):
        q.put(data)

    def worker():
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from pipeline.image_generator import generate_image

            scene_ids = [int(k) for k in req.scene_instructions.keys()]
            total_scenes = len(scene_ids)

            # シーン情報を事前に構築
            scene_data = []
            for scene_id in scene_ids:
                scene_index = None
                for i, scene in enumerate(meta["script"]["scenes"]):
                    if scene["scene_id"] == scene_id:
                        scene_index = i
                        break
                if scene_index is None:
                    raise ValueError(f"scene_id {scene_id} not found")
                scene_data.append({
                    "scene_id": scene_id,
                    "scene_index": scene_index,
                    "scene": meta["script"]["scenes"][scene_index],
                    "instructions": req.scene_instructions.get(str(scene_id), ""),
                })

            on_progress({
                "step": 2, "stepName": "image", "totalSteps": 5,
                "status": "running",
                "detail": f"画像を再生成中... (0/{total_scenes})"
            })

            def regenerate_one(data):
                new_path = generate_image(
                    data["scene"], meta["output_dir"],
                    mock=meta["mock"],
                    instructions=data["instructions"] if data["instructions"] else None
                )
                return data["scene_index"], new_path

            # 並列で画像再生成
            completed_count = 0
            with ThreadPoolExecutor(max_workers=min(total_scenes, 5)) as executor:
                futures = {executor.submit(regenerate_one, data): data for data in scene_data}
                for future in as_completed(futures):
                    scene_index, new_path = future.result()
                    meta["image_paths"][scene_index] = new_path
                    completed_count += 1
                    on_progress({
                        "step": 2, "stepName": "image", "totalSteps": 5,
                        "status": "running",
                        "detail": f"画像を再生成中... ({completed_count}/{total_scenes})"
                    })

            # 全シーンの画像URLを返す（キャッシュバスティング用タイムスタンプ付き）
            import time as _time
            cache_bust = int(_time.time() * 1000)
            images = []
            for s, ip in zip(meta["script"]["scenes"], meta["image_paths"]):
                rel = os.path.relpath(ip, config.OUTPUT_DIR)
                images.append({
                    "scene_id": s["scene_id"],
                    "imageUrl": f"/output/{rel}?t={cache_bust}",
                })
            q.put({"status": "images_ready", "images": images})
        except Exception as e:
            logger.exception("Image regeneration failed for run_id=%s", run_id)
            q.put({"status": "error", "detail": str(e)})
            _run_results[run_id] = {"status": "error", "detail": str(e)}

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return {"ok": True}


class RegenerateVideosRequest(BaseModel):
    scene_instructions: dict[str, str]  # scene_id(str) -> instructions


@app.post("/api/generate/{run_id}/regenerate-videos")
def regenerate_videos(run_id: str, req: RegenerateVideosRequest):
    """複数シーンの動画を再生成（シーンごとの指示対応）。完了時に videos_ready を送信。"""
    meta = _run_meta.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    if meta.get("video_paths") is None:
        raise HTTPException(status_code=400, detail="videos not generated yet")

    q: queue.Queue = queue.Queue()
    _progress_queues[run_id] = q

    def on_progress(data: dict):
        q.put(data)

    def worker():
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from pipeline.video_generator import generate_video

            scene_ids = [int(k) for k in req.scene_instructions.keys()]
            total_scenes = len(scene_ids)

            # シーン情報を事前に構築
            scene_data = []
            for scene_id in scene_ids:
                scene_index = None
                for i, scene in enumerate(meta["script"]["scenes"]):
                    if scene["scene_id"] == scene_id:
                        scene_index = i
                        break
                if scene_index is None:
                    raise ValueError(f"scene_id {scene_id} not found")
                scene_data.append({
                    "scene_id": scene_id,
                    "scene_index": scene_index,
                    "scene": meta["script"]["scenes"][scene_index],
                    "image_path": meta["image_paths"][scene_index],
                    "instructions": req.scene_instructions.get(str(scene_id), ""),
                })

            on_progress({
                "step": 3, "stepName": "video", "totalSteps": 5,
                "status": "running",
                "detail": f"動画を再生成中... (0/{total_scenes})"
            })

            def regenerate_one(data):
                new_path = generate_video(
                    data["scene"], data["image_path"], meta["output_dir"],
                    mock=meta["mock"],
                    instructions=data["instructions"] if data["instructions"] else None
                )
                return data["scene_index"], new_path

            # 並列で動画再生成（Veo2のAPI負荷を考慮してmax_workers制限）
            completed_count = 0
            with ThreadPoolExecutor(max_workers=min(total_scenes, 3)) as executor:
                futures = {executor.submit(regenerate_one, data): data for data in scene_data}
                for future in as_completed(futures):
                    scene_index, new_path = future.result()
                    meta["video_paths"][scene_index] = new_path
                    completed_count += 1
                    on_progress({
                        "step": 3, "stepName": "video", "totalSteps": 5,
                        "status": "running",
                        "detail": f"動画を再生成中... ({completed_count}/{total_scenes})"
                    })

            # 全シーンの動画URLを返す（キャッシュバスティング用タイムスタンプ付き）
            import time as _time
            cache_bust = int(_time.time() * 1000)
            videos = []
            for s, vp in zip(meta["script"]["scenes"], meta["video_paths"]):
                rel = os.path.relpath(vp, config.OUTPUT_DIR)
                videos.append({
                    "scene_id": s["scene_id"],
                    "videoUrl": f"/output/{rel}?t={cache_bust}",
                })
            q.put({"status": "videos_ready", "videos": videos})
        except Exception as e:
            logger.exception("Video regeneration failed for run_id=%s", run_id)
            q.put({"status": "error", "detail": str(e)})
            _run_results[run_id] = {"status": "error", "detail": str(e)}

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return {"ok": True}


class RegenerateVoicesRequest(BaseModel):
    texts: Optional[dict[str, str]] = None  # scene_id(str) -> new text
    emotions: Optional[dict[str, str]] = None  # scene_id(str) -> emotion
    speed: Optional[float] = None
    volume: Optional[float] = None


@app.post("/api/generate/{run_id}/regenerate-voices")
def regenerate_voices(run_id: str, req: RegenerateVoicesRequest = RegenerateVoicesRequest()):
    """STEP4のみ再実行: テキスト修正後に音声を再生成。完了時に voices_ready を送信。"""
    meta = _run_meta.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    if meta.get("video_paths") is None:
        raise HTTPException(status_code=400, detail="videos not generated yet")

    # テキストの更新
    if req.texts:
        for scene in meta["script"]["scenes"]:
            sid = str(scene["scene_id"])
            if sid in req.texts:
                scene["text"] = req.texts[sid]

    # 感情マーカーの更新
    if req.emotions:
        for scene in meta["script"]["scenes"]:
            sid = str(scene["scene_id"])
            if sid in req.emotions:
                scene["emotion"] = req.emotions[sid]

    # スクリプトを保存
    if req.texts or req.emotions:
        script_path = os.path.join(meta["output_dir"], "script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(meta["script"], f, ensure_ascii=False, indent=2)

    # 音声設定の更新（指定があれば）
    speed = req.speed if req.speed is not None else meta.get("voice_speed", 1.0)
    volume = req.volume if req.volume is not None else meta.get("voice_volume", 0.0)
    meta["voice_speed"] = speed
    meta["voice_volume"] = volume

    q: queue.Queue = queue.Queue()
    _progress_queues[run_id] = q

    def on_progress(data: dict):
        q.put(data)

    def worker():
        try:
            voice_paths = regenerate_voices_only(
                script=meta["script"],
                output_dir=meta["output_dir"],
                voice_id=meta.get("voice_id"),
                mock=meta["mock"],
                on_progress=on_progress,
                speed=speed,
                volume=volume,
            )
            meta["voice_paths"] = voice_paths
            voices = []
            for scene, vp in zip(meta["script"]["scenes"], voice_paths):
                rel = os.path.relpath(vp, config.OUTPUT_DIR)
                voices.append({
                    "scene_id": scene["scene_id"],
                    "text": scene["text"],
                    "emotion": scene.get("emotion", ""),
                    "voiceUrl": f"/output/{rel}",
                })
            q.put({"status": "voices_ready", "voices": voices})
        except Exception as e:
            logger.exception("Voice regeneration failed for run_id=%s", run_id)
            q.put({"status": "error", "detail": str(e)})
            _run_results[run_id] = {"status": "error", "detail": str(e)}

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return {"ok": True}


class TelopSettings(BaseModel):
    enabled: bool = False
    font_size: int = 48
    font_style: str = "mincho"  # "gothic" | "mincho"
    font_color: str = "white"
    shadow_color: str = "black"
    shadow_opacity: float = 0.4  # 不鮮明さ 40%
    shadow_distance: int = 5
    shadow_angle: int = -45


class FinalizeRequest(BaseModel):
    transitions: Optional[list[dict]] = None
    telop: Optional[TelopSettings] = None


@app.post("/api/generate/{run_id}/finalize")
def finalize_generation(run_id: str, req: FinalizeRequest = FinalizeRequest()):
    """STEP5: 音声確認後、最終合成をバックグラウンド実行。"""
    meta = _run_meta.get(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    video_paths = meta.get("video_paths")
    voice_paths = meta.get("voice_paths")
    if video_paths is None or voice_paths is None:
        raise HTTPException(status_code=400, detail="videos/voices not generated yet")

    transitions = req.transitions

    # テロップ設定
    telop_texts = None
    telop_settings = None
    if req.telop and req.telop.enabled:
        # 台本のテキストをテロップとして使用
        telop_texts = [scene["text"] for scene in meta["script"]["scenes"]]
        telop_settings = {
            "font_size": req.telop.font_size,
            "font_style": req.telop.font_style,
            "font_color": req.telop.font_color,
            "shadow_color": req.telop.shadow_color,
            "shadow_opacity": req.telop.shadow_opacity,
            "shadow_distance": req.telop.shadow_distance,
            "shadow_angle": req.telop.shadow_angle,
        }

    q: queue.Queue = queue.Queue()
    _progress_queues[run_id] = q

    def on_progress(data: dict):
        q.put(data)

    def worker():
        try:
            final_path = compose_only(
                video_paths=meta["video_paths"],
                voice_paths=meta["voice_paths"],
                output_dir=meta["output_dir"],
                on_progress=on_progress,
                transitions=transitions,
                telop_texts=telop_texts,
                telop_settings=telop_settings,
            )
            rel = os.path.relpath(final_path, config.OUTPUT_DIR)
            video_url = f"/output/{rel}"

            # 履歴に保存
            _add_to_history(run_id, meta)

            q.put({"status": "complete", "videoUrl": video_url})
            _run_results[run_id] = {"status": "complete", "videoUrl": video_url}
        except Exception as e:
            logger.exception("Compose failed for run_id=%s", run_id)
            q.put({"status": "error", "detail": str(e)})
            _run_results[run_id] = {"status": "error", "detail": str(e)}
        # Note: _run_meta is intentionally NOT deleted here
        # to allow users to go back and edit videos/voices after finalize

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return {"ok": True}


@app.get("/api/generate/{run_id}/progress")
async def progress_stream(run_id: str):
    q = _progress_queues.get(run_id)
    if q is None:
        raise HTTPException(status_code=404, detail="run_id not found")

    async def event_generator():
        while True:
            try:
                data = q.get(timeout=30)
            except queue.Empty:
                # Send keepalive comment
                yield {"comment": "keepalive"}
                continue

            yield {"data": json.dumps(data, ensure_ascii=False)}

            if data.get("status") in ("complete", "error", "images_ready", "videos_ready", "voices_ready"):
                break

        # Cleanup
        _progress_queues.pop(run_id, None)

    return EventSourceResponse(event_generator())


# Serve output files (videos, images, etc.)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)
app.mount("/output", StaticFiles(directory=config.OUTPUT_DIR), name="output")
