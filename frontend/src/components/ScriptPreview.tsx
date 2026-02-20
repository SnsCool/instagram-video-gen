"use client";

import { useState } from "react";
import type { Script, ScriptScene } from "@/lib/useGeneration";

interface Props {
  script: Script;
  onConfirm: (editedScript: Script) => void;
  onReset: () => void;
}

export default function ScriptPreview({ script, onConfirm, onReset }: Props) {
  const [title, setTitle] = useState(script.title);
  const [scenes, setScenes] = useState<ScriptScene[]>(script.scenes);

  const totalDuration = scenes.reduce((sum, s) => sum + s.duration_sec, 0);

  const updateScene = (index: number, patch: Partial<ScriptScene>) => {
    setScenes((prev) =>
      prev.map((s, i) => (i === index ? { ...s, ...patch } : s)),
    );
  };

  const moveScene = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= scenes.length) return;
    setScenes((prev) => {
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next.map((s, i) => ({ ...s, scene_id: i + 1 }));
    });
  };

  const handleConfirm = () => {
    onConfirm({ title, scenes });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <p className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
          台本プレビュー
        </p>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full text-center text-lg font-bold text-gray-100 bg-transparent border-b border-gray-700 focus:border-indigo-500 outline-none pb-1"
        />
        <p className="text-xs text-gray-500">
          {scenes.length}シーン / 合計{totalDuration}秒
        </p>
      </div>

      {/* Scenes */}
      <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
        {scenes.map((scene, index) => (
          <div
            key={index}
            className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 space-y-2"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <div className="flex flex-col">
                  <button
                    type="button"
                    disabled={index === 0}
                    onClick={() => moveScene(index, -1)}
                    className="text-gray-500 hover:text-gray-200 disabled:opacity-20 disabled:cursor-not-allowed transition leading-none"
                    aria-label="上に移動"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    disabled={index === scenes.length - 1}
                    onClick={() => moveScene(index, 1)}
                    className="text-gray-500 hover:text-gray-200 disabled:opacity-20 disabled:cursor-not-allowed transition leading-none"
                    aria-label="下に移動"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                </div>
                <span className="text-xs font-semibold text-indigo-400">
                  シーン {scene.scene_id}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={scene.duration_sec}
                  onChange={(e) =>
                    updateScene(index, {
                      duration_sec: Math.max(1, Number(e.target.value) || 1),
                    })
                  }
                  className="w-12 text-right text-xs text-gray-300 bg-gray-800 border border-gray-700 rounded px-1 py-0.5 focus:border-indigo-500 outline-none"
                />
                <span className="text-xs text-gray-500">秒</span>
              </div>
            </div>
            <textarea
              value={scene.text}
              onChange={(e) => updateScene(index, { text: e.target.value })}
              rows={2}
              className="w-full text-sm text-gray-200 leading-relaxed bg-transparent border border-gray-700 rounded px-2 py-1 focus:border-indigo-500 outline-none resize-none"
            />
            <textarea
              value={scene.image_prompt}
              onChange={(e) =>
                updateScene(index, { image_prompt: e.target.value })
              }
              rows={2}
              className="w-full text-xs text-gray-500 italic bg-transparent border border-gray-700 rounded px-2 py-1 focus:border-indigo-500 outline-none resize-none"
            />
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={onReset}
          className="flex-1 rounded-lg bg-gray-800 py-3 text-sm font-medium text-gray-300 hover:bg-gray-700 transition"
        >
          やり直す
        </button>
        <button
          onClick={handleConfirm}
          className="flex-1 rounded-lg bg-indigo-600 py-3 text-sm font-semibold text-white hover:bg-indigo-500 transition"
        >
          この台本で生成する
        </button>
      </div>
    </div>
  );
}
