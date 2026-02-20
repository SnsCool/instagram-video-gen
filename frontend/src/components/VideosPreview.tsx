"use client";

import { useState } from "react";
import type { VideoClip } from "@/lib/useGeneration";

interface Props {
  videos: VideoClip[];
  onConfirm: () => void;
  onRegenerateVideo: (sceneInstructions: Record<number, string>) => void;
  onReset: () => void;
  isRegenerating?: boolean;
}

export default function VideosPreview({
  videos,
  onConfirm,
  onRegenerateVideo,
  onReset,
  isRegenerating,
}: Props) {
  const [selectedScenes, setSelectedScenes] = useState<Set<number>>(new Set());
  const [scenePrompts, setScenePrompts] = useState<Record<number, string>>({});

  const toggleSceneSelection = (sceneId: number) => {
    setSelectedScenes((prev) => {
      const next = new Set(prev);
      if (next.has(sceneId)) {
        next.delete(sceneId);
        setScenePrompts((p) => {
          const newPrompts = { ...p };
          delete newPrompts[sceneId];
          return newPrompts;
        });
      } else {
        next.add(sceneId);
      }
      return next;
    });
  };

  const updateScenePrompt = (sceneId: number, prompt: string) => {
    setScenePrompts((prev) => ({ ...prev, [sceneId]: prompt }));
  };

  const handleRegenerateSelected = () => {
    if (selectedScenes.size > 0) {
      const sceneInstructions: Record<number, string> = {};
      selectedScenes.forEach((id) => {
        sceneInstructions[id] = scenePrompts[id] || "";
      });
      onRegenerateVideo(sceneInstructions);
      setSelectedScenes(new Set());
      setScenePrompts({});
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <p className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
          動画確認
        </p>
        <p className="text-sm text-gray-400">
          各シーンの動画を確認してください
        </p>
      </div>

      {/* Video clips */}
      <div className="space-y-4 max-h-[420px] overflow-y-auto pr-1">
        {videos.map((clip, index) => (
          <div
            key={clip.scene_id}
            className={`rounded-lg border bg-gray-800/50 p-4 space-y-3 ${
              selectedScenes.has(clip.scene_id)
                ? "border-amber-500"
                : "border-gray-700"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-indigo-400">
                シーン {index + 1}
              </span>
              <label className="flex items-center gap-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedScenes.has(clip.scene_id)}
                  onChange={() => toggleSceneSelection(clip.scene_id)}
                  disabled={isRegenerating}
                  className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-amber-500 focus:ring-amber-500 focus:ring-offset-0"
                />
                <span className="text-xs text-gray-400">再生成</span>
              </label>
            </div>
            <div className="aspect-[9/16] max-h-[200px] rounded-lg overflow-hidden bg-black">
              <video
                src={clip.videoUrl}
                controls
                playsInline
                className="w-full h-full object-contain"
                preload="metadata"
              />
            </div>
            {/* シーン個別のプロンプト入力 */}
            {selectedScenes.has(clip.scene_id) && (
              <textarea
                value={scenePrompts[clip.scene_id] || ""}
                onChange={(e) => updateScenePrompt(clip.scene_id, e.target.value)}
                placeholder="このシーンへの指示（例: もっとゆっくり動かして...）"
                className="w-full rounded bg-gray-700 border border-amber-500/50 px-2 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:border-amber-500 outline-none resize-none"
                rows={2}
              />
            )}
          </div>
        ))}
      </div>

      {/* 再生成ボタン（選択シーンがある場合） */}
      {selectedScenes.size > 0 && (
        <button
          onClick={handleRegenerateSelected}
          disabled={isRegenerating}
          className="w-full rounded-lg bg-amber-600 py-3 text-sm font-semibold text-white hover:bg-amber-500 disabled:opacity-50 transition"
        >
          {isRegenerating ? "生成中..." : `選択した${selectedScenes.size}シーンの動画を再生成`}
        </button>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={onReset}
          className="flex-1 rounded-lg bg-gray-800 py-3 text-sm font-medium text-gray-300 hover:bg-gray-700 transition"
        >
          やり直す
        </button>
        <button
          onClick={onConfirm}
          className="flex-1 rounded-lg bg-indigo-600 py-3 text-sm font-semibold text-white hover:bg-indigo-500 transition"
        >
          この動画で音声生成へ
        </button>
      </div>
    </div>
  );
}
