"use client";

import { useState } from "react";

interface Props {
  onSubmit: (params: {
    theme: string;
    voice_id?: string;
    duration?: number;
    mock?: boolean;
    tone?: string;
    first_person?: string;
    second_person?: string;
    referenceImages?: File[];
    reference_script?: string;
  }) => void;
}

const VOICES = [
  { id: "9c51d76d1bfa4a3a864bee5c56c4e096", label: "ボイス1" },
  { id: "71bf4cb71cd44df6aa603d51db8f92ff", label: "ななみん" },
];

const TONES = [
  { id: "desu_masu", label: "ですます調" },
  { id: "da_dearu", label: "だ・である調" },
];

const FIRST_PERSONS = [
  { id: "watashi", label: "私" },
  { id: "ore", label: "俺" },
];

const SECOND_PERSONS = [
  { id: "anata", label: "あなた" },
];

export default function GenerationForm({ onSubmit }: Props) {
  const [theme, setTheme] = useState("");
  const [voiceId, setVoiceId] = useState(VOICES[0].id);
  const [duration, setDuration] = useState(45);
  const [mock, setMock] = useState(true);
  const [tone, setTone] = useState(TONES[0].id);
  const [firstPerson, setFirstPerson] = useState(FIRST_PERSONS[0].id);
  const [secondPerson, setSecondPerson] = useState(SECOND_PERSONS[0].id);
  const [referenceImages, setReferenceImages] = useState<File[]>([]);
  const [referenceScript, setReferenceScript] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!theme.trim()) return;
    onSubmit({
      theme: theme.trim(),
      voice_id: voiceId,
      duration,
      mock,
      tone,
      first_person: firstPerson,
      second_person: secondPerson,
      referenceImages: referenceImages.length > 0 ? referenceImages : undefined,
      reference_script: referenceScript.trim() || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* テーマ */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          テーマ
        </label>
        <input
          type="text"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          placeholder="例: 30代 転職 失敗"
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
        />
      </div>

      {/* 参考画像 */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          参考画像（任意）
        </label>
        <input
          type="file"
          multiple
          accept="image/*"
          onChange={(e) => {
            const files = e.target.files;
            if (files) setReferenceImages(Array.from(files));
          }}
          className="w-full text-sm text-gray-400 file:mr-3 file:rounded-lg file:border-0 file:bg-gray-800 file:px-4 file:py-2 file:text-sm file:font-medium file:text-gray-300 hover:file:bg-gray-700 file:cursor-pointer file:transition"
        />
        {referenceImages.length > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-gray-400">
              {referenceImages.length}枚選択中
            </span>
            <button
              type="button"
              onClick={() => {
                setReferenceImages([]);
                // file inputもリセット
                const input = document.querySelector<HTMLInputElement>(
                  'input[type="file"]'
                );
                if (input) input.value = "";
              }}
              className="text-xs text-red-400 hover:text-red-300 transition"
            >
              クリア
            </button>
          </div>
        )}
      </div>

      {/* 参考台本 */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          参考台本（任意）
        </label>
        <textarea
          value={referenceScript}
          onChange={(e) => setReferenceScript(e.target.value)}
          placeholder="参考にしたい台本や文字起こしを貼り付けてください。この内容を元に新しい台本を生成します。"
          rows={4}
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none resize-none text-sm"
        />
        {referenceScript.trim() && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-gray-400">
              {referenceScript.length}文字
            </span>
            <button
              type="button"
              onClick={() => setReferenceScript("")}
              className="text-xs text-red-400 hover:text-red-300 transition"
            >
              クリア
            </button>
          </div>
        )}
      </div>

      {/* 口調 */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          口調
        </label>
        <div className="flex flex-wrap gap-3">
          {TONES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTone(t.id)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                tone === t.id
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* 一人称・二人称 */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            一人称
          </label>
          <div className="flex flex-wrap gap-3">
            {FIRST_PERSONS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setFirstPerson(p.id)}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                  firstPerson === p.id
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            二人称
          </label>
          <div className="flex flex-wrap gap-3">
            {SECOND_PERSONS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setSecondPerson(p.id)}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                  secondPerson === p.id
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 音声 */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          音声
        </label>
        <div className="flex flex-wrap gap-3">
          {VOICES.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => setVoiceId(v.id)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                voiceId === v.id
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* 秒数 */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          動画秒数: {duration}秒
        </label>
        <input
          type="range"
          min={30}
          max={60}
          step={5}
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
          className="w-full accent-indigo-500"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>30秒</span>
          <span>60秒</span>
        </div>
      </div>

      {/* モックモード */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={mock}
          onClick={() => setMock(!mock)}
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors ${
            mock ? "bg-indigo-600" : "bg-gray-700"
          }`}
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform mt-0.5 ${
              mock ? "translate-x-5.5 ml-0.5" : "translate-x-0.5"
            }`}
          />
        </button>
        <span className="text-sm text-gray-300">
          モックモード（APIを呼ばずダミーで実行）
        </span>
      </div>

      {/* 生成ボタン */}
      <button
        type="submit"
        disabled={!theme.trim()}
        className="w-full rounded-lg bg-indigo-600 py-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition"
      >
        動画を生成する
      </button>
    </form>
  );
}
