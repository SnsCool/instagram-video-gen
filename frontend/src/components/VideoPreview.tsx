"use client";

interface Props {
  videoUrl: string;
  onReset: () => void;
  onGoToScript?: () => void;
  onGoToCuts?: () => void;
  onGoToVideos?: () => void;
  onGoToVoices?: () => void;
  onGoToTransition?: () => void;
}

export default function VideoPreview({
  videoUrl,
  onReset,
  onGoToScript,
  onGoToCuts,
  onGoToVideos,
  onGoToVoices,
  onGoToTransition,
}: Props) {
  return (
    <div className="space-y-6 flex flex-col items-center">
      <p className="text-sm font-medium text-indigo-400">生成完了</p>

      {/* 9:16 video player */}
      <div className="w-[270px] h-[480px] rounded-xl overflow-hidden bg-black shadow-xl shadow-indigo-500/10">
        <video
          src={videoUrl}
          controls
          autoPlay
          playsInline
          className="w-full h-full object-contain"
        />
      </div>

      <div className="flex gap-3">
        <a
          href={videoUrl}
          download
          className="rounded-lg bg-gray-800 px-5 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-700 transition"
        >
          ダウンロード
        </a>
        <button
          onClick={onReset}
          className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 transition"
        >
          もう一度生成
        </button>
      </div>

      {/* 編集に戻るボタン */}
      <div className="w-full border-t border-gray-700 pt-4">
        <p className="text-xs text-gray-500 text-center mb-3">編集に戻る</p>
        <div className="flex flex-wrap gap-2 justify-center">
          {onGoToScript && (
            <button
              onClick={onGoToScript}
              className="rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-gray-300 hover:bg-gray-700 transition"
            >
              台本を編集
            </button>
          )}
          {onGoToCuts && (
            <button
              onClick={onGoToCuts}
              className="rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-gray-300 hover:bg-gray-700 transition"
            >
              カットを編集
            </button>
          )}
          {onGoToVideos && (
            <button
              onClick={onGoToVideos}
              className="rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-gray-300 hover:bg-gray-700 transition"
            >
              動画を編集
            </button>
          )}
          {onGoToVoices && (
            <button
              onClick={onGoToVoices}
              className="rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-gray-300 hover:bg-gray-700 transition"
            >
              音声を編集
            </button>
          )}
          {onGoToTransition && (
            <button
              onClick={onGoToTransition}
              className="rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-gray-300 hover:bg-gray-700 transition"
            >
              トランジションを編集
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
