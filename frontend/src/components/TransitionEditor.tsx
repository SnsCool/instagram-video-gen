"use client";

import { useState } from "react";

export interface TransitionSetting {
  audioGap: number; // 音声間の空白秒数 (0 = なし)
}

export interface TelopSetting {
  enabled: boolean;
  font_size: number;
  font_style: "gothic" | "mincho";
  font_color: string;
  shadow_color: string;
  shadow_opacity: number;
  shadow_distance: number;
  shadow_angle: number;
}

interface Props {
  sceneCount: number;
  onFinalize: (transitions: TransitionSetting[], telop?: TelopSetting) => void;
  onBack: () => void;
  onReset: () => void;
}

const GAP_OPTIONS = [
  { value: 0, label: "なし" },
  { value: 0.3, label: "0.3秒" },
  { value: 0.5, label: "0.5秒" },
  { value: 0.8, label: "0.8秒" },
  { value: 1.0, label: "1.0秒" },
];

export default function TransitionEditor({
  sceneCount,
  onFinalize,
  onBack,
  onReset,
}: Props) {
  // シーン間の設定 (シーン数 - 1)
  const transitionCount = sceneCount - 1;

  const [transitions, setTransitions] = useState<TransitionSetting[]>(() =>
    Array(transitionCount).fill({ audioGap: 0.3 })
  );

  // CapCut風の固定設定（明朝体、シャドウ付き）
  const [telop, setTelop] = useState<TelopSetting>({
    enabled: false,
    font_size: 48,
    font_style: "mincho",
    font_color: "white",
    shadow_color: "black",
    shadow_opacity: 0.4,  // 不鮮明さ 40%
    shadow_distance: 5,
    shadow_angle: -45,
  });

  const updateTransition = (index: number, value: number) => {
    setTransitions((prev) =>
      prev.map((t, i) => (i === index ? { audioGap: value } : t))
    );
  };

  const applyToAll = (value: number) => {
    setTransitions(Array(transitionCount).fill({ audioGap: value }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <p className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
          音声つなぎ設定
        </p>
        <p className="text-sm text-gray-400">
          シーン間の空白（間）を調整できます
        </p>
      </div>

      {/* 一括設定 */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 space-y-3">
        <p className="text-xs font-medium text-gray-400">一括設定</p>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => applyToAll(0)}
            className="rounded px-3 py-1.5 text-xs bg-gray-700 text-gray-300 hover:bg-gray-600 transition"
          >
            全て間なし
          </button>
          <button
            onClick={() => applyToAll(0.3)}
            className="rounded px-3 py-1.5 text-xs bg-gray-700 text-gray-300 hover:bg-gray-600 transition"
          >
            全て0.3秒
          </button>
          <button
            onClick={() => applyToAll(0.5)}
            className="rounded px-3 py-1.5 text-xs bg-gray-700 text-gray-300 hover:bg-gray-600 transition"
          >
            全て0.5秒
          </button>
        </div>
      </div>

      {/* 個別設定 */}
      <div className="space-y-3 max-h-[200px] overflow-y-auto pr-1">
        {transitions.map((t, index) => (
          <div
            key={index}
            className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
          >
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-indigo-400">
                シーン {index + 1} → {index + 2}
              </p>
              <select
                value={t.audioGap}
                onChange={(e) =>
                  updateTransition(index, parseFloat(e.target.value))
                }
                className="rounded bg-gray-700 border border-gray-600 px-3 py-1.5 text-sm text-gray-200 focus:border-indigo-500 outline-none"
              >
                {GAP_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>

      {/* テロップ設定 */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
              テロップ
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              明朝体・中央・シャドウ付き
            </p>
          </div>
          <button
            onClick={() => setTelop((prev) => ({ ...prev, enabled: !prev.enabled }))}
            className={`relative w-12 h-6 rounded-full transition-colors ${
              telop.enabled ? "bg-indigo-600" : "bg-gray-600"
            }`}
          >
            <span
              className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                telop.enabled ? "left-7" : "left-1"
              }`}
            />
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2">
        <div className="flex gap-3">
          <button
            onClick={onBack}
            className="flex-1 rounded-lg bg-gray-800 py-3 text-sm font-medium text-gray-300 hover:bg-gray-700 transition"
          >
            戻る
          </button>
          <button
            onClick={() => onFinalize(transitions, telop.enabled ? telop : undefined)}
            className="flex-1 rounded-lg bg-indigo-600 py-3 text-sm font-semibold text-white hover:bg-indigo-500 transition"
          >
            この設定で合成する
          </button>
        </div>
        <button
          onClick={onReset}
          className="w-full rounded-lg bg-gray-800/50 py-2 text-xs font-medium text-gray-500 hover:bg-gray-700 hover:text-gray-300 transition"
        >
          最初からやり直す
        </button>
      </div>
    </div>
  );
}
