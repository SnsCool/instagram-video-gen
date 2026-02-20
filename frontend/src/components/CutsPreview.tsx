"use client";

import { useState } from "react";
import type { CutImage, Script } from "@/lib/useGeneration";

interface Props {
  script: Script;
  images: CutImage[];
  onCompose: (sceneOrder: number[]) => void;
  onReset: () => void;
  onRegenerateImage?: (sceneInstructions: Record<number, string>) => void;
  isRegenerating?: boolean;
}

export default function CutsPreview({
  script,
  images,
  onCompose,
  onReset,
  onRegenerateImage,
  isRegenerating,
}: Props) {
  // 各シーン位置に対応する画像のscene_idを管理
  // imageOrder[i] = 「シーンi+1の位置にどの画像(scene_id)を表示するか」
  const [imageOrder, setImageOrder] = useState<number[]>(
    images.map((img) => img.scene_id),
  );

  // 再生成用のUI状態（シーンごとのプロンプト）
  const [selectedScenes, setSelectedScenes] = useState<Set<number>>(new Set());
  const [scenePrompts, setScenePrompts] = useState<Record<number, string>>({});

  const toggleSceneSelection = (sceneId: number) => {
    setSelectedScenes((prev) => {
      const next = new Set(prev);
      if (next.has(sceneId)) {
        next.delete(sceneId);
        // プロンプトもクリア
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
    if (selectedScenes.size > 0 && onRegenerateImage) {
      // シーンIDとプロンプトのマップを作成
      const sceneInstructions: Record<number, string> = {};
      selectedScenes.forEach((id) => {
        sceneInstructions[id] = scenePrompts[id] || "";
      });
      onRegenerateImage(sceneInstructions);
      setSelectedScenes(new Set());
      setScenePrompts({});
    }
  };

  const imageMap = Object.fromEntries(
    images.map((img) => [img.scene_id, img.imageUrl]),
  );

  // 画像を上下に入れ替え（台本テキストは固定、画像のみ入れ替え）
  const swapImages = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= imageOrder.length) return;
    setImageOrder((prev) => {
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <p className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
          カット確認
        </p>
        <h2 className="text-lg font-bold text-gray-100">{script.title}</h2>
        <p className="text-xs text-gray-500">
          {script.scenes.length}カット — 画像のみ入れ替え可能
        </p>
      </div>

      {/* Cuts */}
      <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
        {script.scenes.map((scene, index) => {
          // このシーン位置に表示する画像のscene_id
          const imageSceneId = imageOrder[index];
          const imageUrl = imageMap[imageSceneId];
          const isImageSwapped = imageSceneId !== scene.scene_id;

          return (
            <div
              key={scene.scene_id}
              className="rounded-lg border border-gray-700 bg-gray-800/50 p-3 flex gap-3 items-start"
            >
              {/* Move buttons for image */}
              <div className="flex flex-col pt-4 shrink-0">
                <button
                  type="button"
                  disabled={index === 0}
                  onClick={() => swapImages(index, -1)}
                  className="text-gray-500 hover:text-gray-200 disabled:opacity-20 disabled:cursor-not-allowed transition leading-none"
                  aria-label="画像を上に移動"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 15l7-7 7 7"
                    />
                  </svg>
                </button>
                <button
                  type="button"
                  disabled={index === script.scenes.length - 1}
                  onClick={() => swapImages(index, 1)}
                  className="text-gray-500 hover:text-gray-200 disabled:opacity-20 disabled:cursor-not-allowed transition leading-none"
                  aria-label="画像を下に移動"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>
              </div>

              {/* Thumbnail */}
              <div className={`relative w-16 h-28 rounded overflow-hidden bg-gray-900 shrink-0 ${isImageSwapped ? "ring-2 ring-amber-500" : ""}`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imageUrl}
                  alt={`シーン ${index + 1}`}
                  className="w-full h-full object-cover"
                />
                {isImageSwapped && (
                  <div className="absolute top-0 right-0 bg-amber-500 text-[10px] text-black font-bold px-1 rounded-bl">
                    入替
                  </div>
                )}
              </div>

              {/* Info - 台本テキスト（固定） */}
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-indigo-400">
                    シーン {index + 1}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">
                      {scene.duration_sec}秒
                    </span>
                    {onRegenerateImage && (
                      <label className="flex items-center gap-1 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedScenes.has(scene.scene_id)}
                          onChange={() => toggleSceneSelection(scene.scene_id)}
                          disabled={isRegenerating}
                          className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-amber-500 focus:ring-amber-500 focus:ring-offset-0"
                        />
                        <span className="text-xs text-gray-400">再生成</span>
                      </label>
                    )}
                  </div>
                </div>
                <p className="text-sm text-gray-200 leading-snug line-clamp-2">
                  {scene.text}
                </p>
                {/* シーン個別のプロンプト入力 */}
                {selectedScenes.has(scene.scene_id) && onRegenerateImage && (
                  <textarea
                    value={scenePrompts[scene.scene_id] || ""}
                    onChange={(e) => updateScenePrompt(scene.scene_id, e.target.value)}
                    placeholder="このシーンへの指示（例: もっと明るく...）"
                    className="w-full mt-2 rounded bg-gray-700 border border-amber-500/50 px-2 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:border-amber-500 outline-none resize-none"
                    rows={2}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 再生成ボタン（選択シーンがある場合） */}
      {selectedScenes.size > 0 && onRegenerateImage && (
        <button
          onClick={handleRegenerateSelected}
          disabled={isRegenerating}
          className="w-full rounded-lg bg-amber-600 py-3 text-sm font-semibold text-white hover:bg-amber-500 disabled:opacity-50 transition"
        >
          {isRegenerating ? "生成中..." : `選択した${selectedScenes.size}シーンの画像を再生成`}
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
          onClick={() => onCompose(imageOrder)}
          className="flex-1 rounded-lg bg-indigo-600 py-3 text-sm font-semibold text-white hover:bg-indigo-500 transition"
        >
          この組み合わせで動画を生成
        </button>
      </div>
    </div>
  );
}
