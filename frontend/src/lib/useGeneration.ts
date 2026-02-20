"use client";

import { useCallback, useRef, useState } from "react";

export type Phase =
  | "idle"
  | "script_review"
  | "running"
  | "cuts_review"
  | "composing"
  | "videos_review"
  | "voices_review"
  | "transition_edit"
  | "finalizing"
  | "complete"
  | "error";

export interface TransitionSetting {
  audioGap: number; // 音声間の空白秒数 (0 = なし)
}

export interface ScriptScene {
  scene_id: number;
  text: string;
  image_prompt: string;
  duration_sec: number;
}

export interface Script {
  title: string;
  scenes: ScriptScene[];
}

export interface CutImage {
  scene_id: number;
  imageUrl: string;
}

export interface VideoClip {
  scene_id: number;
  videoUrl: string;
}

export interface VoiceClip {
  scene_id: number;
  text: string;
  voiceUrl: string;
}

export interface ProgressEvent {
  step: number;
  stepName: string;
  totalSteps: number;
  status: string;
  detail: string;
  scene?: number;
  totalScenes?: number;
  videoUrl?: string;
}

export interface GenerationState {
  phase: Phase;
  runId: string | null;
  script: Script | null;
  originalScript: Script | null;  // 画像生成後の台本を保持（部分再生成の比較用）
  images: CutImage[] | null;
  videos: VideoClip[] | null;
  voices: VoiceClip[] | null;
  transitions: TransitionSetting[] | null;
  progress: ProgressEvent | null;
  videoUrl: string | null;
  error: string | null;
}

const INITIAL_STATE: GenerationState = {
  phase: "idle",
  runId: null,
  script: null,
  originalScript: null,
  images: null,
  videos: null,
  voices: null,
  transitions: null,
  progress: null,
  videoUrl: null,
  error: null,
};

export function useGeneration() {
  const [state, setState] = useState<GenerationState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  /** SSE接続して進捗を受信する */
  const connectSSE = useCallback(
    async (
      runId: string,
      opts?: {
        onImagesReady?: (images: CutImage[]) => void;
        onVideosReady?: (videos: VideoClip[]) => void;
        onVoicesReady?: (voices: VoiceClip[]) => void;
      },
    ) => {
      const abort = new AbortController();
      abortRef.current = abort;

      const eventSource = await fetch(
        `/api/generate/${runId}/progress`,
        { signal: abort.signal },
      );

      if (!eventSource.ok || !eventSource.body) {
        throw new Error("Failed to connect to progress stream");
      }

      const reader = eventSource.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const jsonStr = line.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const data = JSON.parse(jsonStr);

            if (data.status === "complete" && data.videoUrl) {
              setState((s) => ({
                ...s,
                phase: "complete",
                videoUrl: data.videoUrl,
                progress: null,
              }));
              return;
            }

            if (data.status === "images_ready" && opts?.onImagesReady) {
              opts.onImagesReady(data.images);
              return;
            }

            if (data.status === "videos_ready" && opts?.onVideosReady) {
              opts.onVideosReady(data.videos);
              return;
            }

            if (data.status === "voices_ready" && opts?.onVoicesReady) {
              opts.onVoicesReady(data.voices);
              return;
            }

            if (data.status === "error") {
              setState((s) => ({
                ...s,
                phase: "error",
                error: data.detail || "Unknown error",
              }));
              return;
            }

            setState((s) => ({ ...s, progress: data as ProgressEvent }));
          } catch {
            // Skip non-JSON lines (comments, keepalives)
          }
        }
      }
    },
    [],
  );

  /** テーマ送信 → 台本だけ生成して script_review へ */
  const start = useCallback(
    async (params: {
      theme: string;
      voice_id?: string;
      duration?: number;
      mock?: boolean;
      tone?: string;
      first_person?: string;
      second_person?: string;
      referenceImages?: File[];
      reference_script?: string;
    }) => {
      abortRef.current?.abort();
      setState({ ...INITIAL_STATE, phase: "running" });

      try {
        const { referenceImages, ...jsonParams } = params;
        let res: Response;

        if (referenceImages && referenceImages.length > 0) {
          const formData = new FormData();
          formData.append("params", JSON.stringify(jsonParams));
          for (const file of referenceImages) {
            formData.append("reference_images", file);
          }
          res = await fetch("/api/generate", {
            method: "POST",
            body: formData,
          });
        } else {
          res = await fetch("/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(jsonParams),
          });
        }

        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }

        const { run_id, script } = await res.json();
        setState((s) => ({
          ...s,
          phase: "script_review",
          runId: run_id,
          script,
        }));
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setState((s) => ({
          ...s,
          phase: "error",
          error: err.message || "Unknown error",
        }));
      }
    },
    [],
  );

  /** 台本確認後 → continue（STEP2: 画像生成）→ cuts_review */
  const confirm = useCallback(
    async (editedScript: Script) => {
      const runId = state.runId;
      if (!runId) return;

      setState((s) => ({ ...s, phase: "running", progress: null }));

      try {
        // 元の台本がある場合、変更されたシーンを検出
        let changedSceneIds: number[] | undefined;
        if (state.originalScript && state.images) {
          // 画像が既に生成されている場合のみ部分再生成を行う
          changedSceneIds = [];
          const originalScenes = state.originalScript.scenes;
          const editedScenes = editedScript.scenes;

          for (let i = 0; i < editedScenes.length; i++) {
            const edited = editedScenes[i];
            const original = originalScenes.find(s => s.scene_id === edited.scene_id);

            // 新規シーン、または image_prompt が変更されたシーンを検出
            if (!original || original.image_prompt !== edited.image_prompt) {
              changedSceneIds.push(edited.scene_id);
            }
          }

          // 変更がない場合は再生成をスキップ
          if (changedSceneIds.length === 0) {
            setState((s) => ({
              ...s,
              phase: "cuts_review",
              script: editedScript,
              progress: null,
            }));
            return;
          }
        }

        const body: { script: Script; changed_scene_ids?: number[] } = {
          script: editedScript,
        };
        if (changedSceneIds && changedSceneIds.length > 0) {
          body.changed_scene_ids = changedSceneIds;
        }

        const res = await fetch(`/api/generate/${runId}/continue`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }

        await connectSSE(runId, {
          onImagesReady: (images) => {
            setState((s) => ({
              ...s,
              phase: "cuts_review",
              script: editedScript,
              originalScript: editedScript,  // 新しい台本を保存
              images,
              progress: null,
            }));
          },
        });
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setState((s) => ({
          ...s,
          phase: "error",
          error: err.message || "Unknown error",
        }));
      }
    },
    [state.runId, state.originalScript, state.images, connectSSE],
  );

  /** カット確認後 → compose（STEP3: 動画生成）→ videos_review */
  const compose = useCallback(
    async (sceneOrder: number[]) => {
      const runId = state.runId;
      if (!runId) return;

      setState((s) => ({ ...s, phase: "composing", progress: null }));

      try {
        const res = await fetch(`/api/generate/${runId}/compose`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scene_order: sceneOrder }),
        });

        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }

        await connectSSE(runId, {
          onVideosReady: (videos: VideoClip[]) => {
            setState((s) => ({
              ...s,
              phase: "videos_review",
              videos,
              progress: null,
            }));
          },
        });
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setState((s) => ({
          ...s,
          phase: "error",
          error: err.message || "Unknown error",
        }));
      }
    },
    [state.runId, connectSSE],
  );

  /** 動画確認後 → 音声生成 → voices_review */
  const generateVoices = useCallback(async () => {
    const runId = state.runId;
    if (!runId) return;

    setState((s) => ({ ...s, phase: "composing", progress: null }));

    try {
      const res = await fetch(`/api/generate/${runId}/generate-voices`, {
        method: "POST",
      });

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      await connectSSE(runId, {
        onVoicesReady: (voices) => {
          setState((s) => ({
            ...s,
            phase: "voices_review",
            voices,
            progress: null,
          }));
        },
      });
    } catch (err: any) {
      if (err.name === "AbortError") return;
      setState((s) => ({
        ...s,
        phase: "error",
        error: err.message || "Unknown error",
      }));
    }
  }, [state.runId, connectSSE]);

  /** 特定シーンの画像を再生成（複数対応・シーンごとの指示） */
  const regenerateImage = useCallback(
    async (sceneInstructions: Record<number, string>) => {
      const runId = state.runId;
      if (!runId) return;

      setState((s) => ({ ...s, phase: "running", progress: null }));

      try {
        const res = await fetch(`/api/generate/${runId}/regenerate-images`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scene_instructions: sceneInstructions }),
        });

        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }

        await connectSSE(runId, {
          onImagesReady: (images: CutImage[]) => {
            setState((s) => ({
              ...s,
              phase: "cuts_review",
              images,
              progress: null,
            }));
          },
        });
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setState((s) => ({
          ...s,
          phase: "error",
          error: err.message || "Unknown error",
        }));
      }
    },
    [state.runId, connectSSE],
  );

  /** 特定シーンの動画を再生成（複数対応・シーンごとの指示） */
  const regenerateVideo = useCallback(
    async (sceneInstructions: Record<number, string>) => {
      const runId = state.runId;
      if (!runId) return;

      setState((s) => ({ ...s, phase: "composing", progress: null }));

      try {
        const res = await fetch(`/api/generate/${runId}/regenerate-videos`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scene_instructions: sceneInstructions }),
        });

        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }

        await connectSSE(runId, {
          onVideosReady: (videos: VideoClip[]) => {
            setState((s) => ({
              ...s,
              phase: "videos_review",
              videos,
              progress: null,
            }));
          },
        });
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setState((s) => ({
          ...s,
          phase: "error",
          error: err.message || "Unknown error",
        }));
      }
    },
    [state.runId, connectSSE],
  );

  /** 音声確認後 → トランジション編集画面へ */
  const goToTransitionEdit = useCallback(() => {
    setState((s) => ({ ...s, phase: "transition_edit" }));
  }, []);

  /** トランジション設定後 → finalize（STEP5: 合成）→ complete */
  const finalize = useCallback(async (
    transitions?: TransitionSetting[],
    telop?: {
      enabled: boolean;
      font_size: number;
      font_style: string;
      font_color: string;
      shadow_color: string;
      shadow_opacity: number;
      shadow_distance: number;
      shadow_angle: number;
    }
  ) => {
    const runId = state.runId;
    if (!runId) return;

    setState((s) => ({
      ...s,
      phase: "finalizing",
      progress: null,
      transitions: transitions || s.transitions,
    }));

    try {
      const res = await fetch(`/api/generate/${runId}/finalize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transitions: transitions || state.transitions,
          telop: telop,
        }),
      });

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      await connectSSE(runId);
    } catch (err: any) {
      if (err.name === "AbortError") return;
      setState((s) => ({
        ...s,
        phase: "error",
        error: err.message || "Unknown error",
      }));
    }
  }, [state.runId, state.transitions, connectSSE]);

  /** テキスト・感情・設定を反映して音声を再生成 → voices_review に戻る */
  const regenerateVoices = useCallback(
    async (data: {
      texts: Record<string, string>;
      emotions?: Record<string, string>;
      speed?: number;
      volume?: number;
    }) => {
      const runId = state.runId;
      if (!runId) return;

      setState((s) => ({ ...s, phase: "composing", progress: null }));

      try {
        const res = await fetch(
          `/api/generate/${runId}/regenerate-voices`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              texts: data.texts,
              emotions: data.emotions,
              speed: data.speed,
              volume: data.volume,
            }),
          },
        );

        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }

        await connectSSE(runId, {
          onVoicesReady: (voices) => {
            setState((s) => ({
              ...s,
              phase: "voices_review",
              voices,
              progress: null,
            }));
          },
        });
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setState((s) => ({
          ...s,
          phase: "error",
          error: err.message || "Unknown error",
        }));
      }
    },
    [state.runId, connectSSE],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  /** 台本編集画面に戻る */
  const goToScriptReview = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({
      ...s,
      phase: "script_review",
      progress: null,
      // 画像が生成済みなら現在の台本を originalScript として保持（部分再生成用）
      originalScript: s.images ? (s.originalScript || s.script) : null,
    }));
  }, []);

  /** カット確認画面に戻る */
  const goToCutsReview = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({
      ...s,
      phase: "cuts_review",
      progress: null,
    }));
  }, []);

  /** 音声確認画面に戻る */
  const goToVoicesReview = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({
      ...s,
      phase: "voices_review",
      progress: null,
    }));
  }, []);

  /** 動画確認画面に戻る */
  const goToVideosReview = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({
      ...s,
      phase: "videos_review",
      progress: null,
    }));
  }, []);

  /** 履歴からセッションを復元 */
  const restoreFromHistory = useCallback(async (runId: string) => {
    try {
      setState({ ...INITIAL_STATE, phase: "running" });

      const res = await fetch(`/api/history/${runId}/restore`, {
        method: "POST",
      });

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      const data = await res.json();

      // 復元されたデータに基づいて適切なフェーズに遷移
      const newState: GenerationState = {
        ...INITIAL_STATE,
        runId: data.run_id,
        script: data.script,
        originalScript: data.images ? data.script : null,  // 画像がある場合は部分再生成用に保持
        images: data.images,
        videos: data.videos,
        voices: data.voices,
        videoUrl: data.videoUrl,
        phase: "complete", // デフォルトは完了画面
      };

      // 利用可能なデータに基づいてフェーズを決定
      if (data.videoUrl) {
        newState.phase = "complete";
      } else if (data.voices && data.voices.length > 0) {
        newState.phase = "voices_review";
      } else if (data.videos && data.videos.length > 0) {
        newState.phase = "videos_review";
      } else if (data.images && data.images.length > 0) {
        newState.phase = "cuts_review";
      } else if (data.script) {
        newState.phase = "script_review";
      }

      setState(newState);
    } catch (err: any) {
      setState((s) => ({
        ...s,
        phase: "error",
        error: err.message || "復元に失敗しました",
      }));
    }
  }, []);

  return {
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
  };
}
