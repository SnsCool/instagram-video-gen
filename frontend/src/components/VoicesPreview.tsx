"use client";

import { useState } from "react";
import type { VoiceClip } from "@/lib/useGeneration";

const EMOTION_OPTIONS = [
  { value: "", label: "なし" },
  { value: "happy", label: "嬉しい" },
  { value: "excited", label: "興奮" },
  { value: "calm", label: "落ち着いた" },
  { value: "serious", label: "真剣" },
  { value: "sad", label: "悲しい" },
  { value: "angry", label: "怒り" },
  { value: "surprised", label: "驚き" },
  { value: "nervous", label: "緊張" },
];

interface Props {
  voices: VoiceClip[];
  onFinalize: () => void;
  onRegenerateVoices: (data: {
    texts: Record<string, string>;
    emotions: Record<string, string>;
    speed: number;
    volume: number;
  }) => void;
  onReset: () => void;
}

export default function VoicesPreview({
  voices,
  onFinalize,
  onRegenerateVoices,
  onReset,
}: Props) {
  const [texts, setTexts] = useState<Record<string, string>>(() =>
    Object.fromEntries(voices.map((v) => [String(v.scene_id), v.text])),
  );
  const [emotions, setEmotions] = useState<Record<string, string>>(() =>
    Object.fromEntries(voices.map((v) => [String(v.scene_id), (v as any).emotion || ""])),
  );
  const [speed, setSpeed] = useState(1.0);
  const [volume, setVolume] = useState(0.0);
  const [showSettings, setShowSettings] = useState(false);

  const hasChanges = voices.some(
    (v) => texts[String(v.scene_id)] !== v.text || emotions[String(v.scene_id)] !== ((v as any).emotion || ""),
  );

  const updateText = (sceneId: number, value: string) => {
    setTexts((prev) => ({ ...prev, [String(sceneId)]: value }));
  };

  const updateEmotion = (sceneId: number, value: string) => {
    setEmotions((prev) => ({ ...prev, [String(sceneId)]: value }));
  };

  const handleRegenerate = () => {
    onRegenerateVoices({ texts, emotions, speed, volume });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <p className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
          音声確認
        </p>
        <p className="text-sm text-gray-400">
          テキスト・感情・設定を調整して再生成できます
        </p>
      </div>

      {/* Voice Settings */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-3">
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="w-full flex items-center justify-between text-xs font-medium text-gray-400"
        >
          <span>音声設定</span>
          <span>{showSettings ? "▲" : "▼"}</span>
        </button>
        {showSettings && (
          <div className="mt-3 space-y-3">
            <div>
              <label className="text-xs text-gray-500">
                スピード: {speed.toFixed(1)}x
              </label>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-600">
                <span>0.5x</span>
                <span>1.0x</span>
                <span>2.0x</span>
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500">
                音量: {volume > 0 ? "+" : ""}{volume.toFixed(0)}dB
              </label>
              <input
                type="range"
                min="-20"
                max="20"
                step="1"
                value={volume}
                onChange={(e) => setVolume(parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-600">
                <span>-20dB</span>
                <span>0dB</span>
                <span>+20dB</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Voice clips */}
      <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
        {voices.map((clip, index) => {
          const textEdited = texts[String(clip.scene_id)] !== clip.text;
          const emotionEdited = emotions[String(clip.scene_id)] !== ((clip as any).emotion || "");
          const edited = textEdited || emotionEdited;
          return (
            <div
              key={clip.scene_id}
              className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-indigo-400">
                  シーン {index + 1}
                </span>
                <div className="flex items-center gap-2">
                  {edited && (
                    <span className="text-xs text-amber-400">変更あり</span>
                  )}
                  <select
                    value={emotions[String(clip.scene_id)] || ""}
                    onChange={(e) => updateEmotion(clip.scene_id, e.target.value)}
                    className="rounded bg-gray-700 border border-gray-600 px-2 py-1 text-xs text-gray-200 focus:border-indigo-500 outline-none"
                  >
                    {EMOTION_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <textarea
                value={texts[String(clip.scene_id)]}
                onChange={(e) => updateText(clip.scene_id, e.target.value)}
                rows={2}
                className="w-full text-sm text-gray-200 leading-relaxed bg-transparent border border-gray-700 rounded px-2 py-1 focus:border-indigo-500 outline-none resize-none"
              />
              <audio
                src={clip.voiceUrl}
                controls
                className="w-full h-8"
                preload="metadata"
              />
            </div>
          );
        })}
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2">
        {hasChanges && (
          <button
            onClick={handleRegenerate}
            className="w-full rounded-lg bg-amber-600 py-3 text-sm font-semibold text-white hover:bg-amber-500 transition"
          >
            変更を適用して音声を再生成
          </button>
        )}
        <button
          onClick={handleRegenerate}
          className="w-full rounded-lg bg-gray-700 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-600 transition"
        >
          全シーンの音声を再生成（トーン統一）
        </button>
        <div className="flex gap-3">
          <button
            onClick={onReset}
            className="flex-1 rounded-lg bg-gray-800 py-3 text-sm font-medium text-gray-300 hover:bg-gray-700 transition"
          >
            やり直す
          </button>
          <button
            onClick={onFinalize}
            className="flex-1 rounded-lg bg-indigo-600 py-3 text-sm font-semibold text-white hover:bg-indigo-500 transition"
          >
            この音声で合成する
          </button>
        </div>
      </div>
    </div>
  );
}
