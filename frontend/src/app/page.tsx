"use client";

import { useState } from "react";
import CutsPreview from "@/components/CutsPreview";
import GenerationForm from "@/components/GenerationForm";
import History from "@/components/History";
import ProgressDisplay from "@/components/ProgressDisplay";
import ScriptPreview from "@/components/ScriptPreview";
import TransitionEditor from "@/components/TransitionEditor";
import VideoPreview from "@/components/VideoPreview";
import VideosPreview from "@/components/VideosPreview";
import VoicesPreview from "@/components/VoicesPreview";
import { useGeneration } from "@/lib/useGeneration";

export default function Home() {
  const [showHistory, setShowHistory] = useState(false);
  const {
    state,
    start,
    confirm,
    compose,
    generateVoices,
    regenerateImage,
    regenerateVideo,
    finalize,
    goToTransitionEdit,
    regenerateVoices,
    reset,
    goToScriptReview,
    goToCutsReview,
    goToVideosReview,
    goToVoicesReview,
    restoreFromHistory,
  } = useGeneration();

  const handleRestore = (runId: string) => {
    setShowHistory(false);
    restoreFromHistory(runId);
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight">
            Instagram Video Generator
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            テーマを入力して動画を自動生成
          </p>
        </div>

        <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
          {showHistory ? (
            <History
              onRestore={handleRestore}
              onClose={() => setShowHistory(false)}
            />
          ) : (
            <>
              {state.phase === "idle" && (
                <>
                  <GenerationForm onSubmit={start} />
                  <div className="mt-4 pt-4 border-t border-gray-700">
                    <button
                      onClick={() => setShowHistory(true)}
                      className="w-full rounded-lg bg-gray-800 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-700 transition"
                    >
                      履歴を見る
                    </button>
                  </div>
                </>
              )}

              {state.phase === "script_review" && state.script && (
                <ScriptPreview
                  script={state.script}
                  onConfirm={confirm}
                  onReset={reset}
                />
              )}

              {(state.phase === "running" || state.phase === "composing" || state.phase === "finalizing") && (
                <ProgressDisplay progress={state.progress} />
              )}

              {state.phase === "cuts_review" &&
                state.script &&
                state.images && (
                  <CutsPreview
                    script={state.script}
                    images={state.images}
                    onCompose={compose}
                    onReset={reset}
                    onRegenerateImage={regenerateImage}
                  />
                )}

              {state.phase === "videos_review" && state.videos && (
                <VideosPreview
                  videos={state.videos}
                  onConfirm={generateVoices}
                  onRegenerateVideo={regenerateVideo}
                  onReset={reset}
                  isRegenerating={false}
                />
              )}

              {state.phase === "voices_review" && state.voices && (
                <VoicesPreview
                  voices={state.voices}
                  onFinalize={goToTransitionEdit}
                  onRegenerateVoices={regenerateVoices}
                  onReset={reset}
                />
              )}

              {state.phase === "transition_edit" && state.script && (
                <TransitionEditor
                  sceneCount={state.script.scenes.length}
                  onFinalize={finalize}
                  onBack={goToVoicesReview}
                  onReset={reset}
                />
              )}

              {state.phase === "complete" && state.videoUrl && (
                <VideoPreview
                  videoUrl={state.videoUrl}
                  onReset={reset}
                  onGoToScript={state.script ? goToScriptReview : undefined}
                  onGoToCuts={state.images ? goToCutsReview : undefined}
                  onGoToVideos={state.videos ? goToVideosReview : undefined}
                  onGoToVoices={state.voices ? goToVoicesReview : undefined}
                  onGoToTransition={state.script ? goToTransitionEdit : undefined}
                />
              )}

              {state.phase === "error" && (
                <div className="space-y-4 text-center">
                  <p className="text-sm text-red-400">
                    エラーが発生しました: {state.error}
                  </p>
                  <button
                    onClick={reset}
                    className="rounded-lg bg-gray-800 px-5 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-700 transition"
                  >
                    やり直す
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
