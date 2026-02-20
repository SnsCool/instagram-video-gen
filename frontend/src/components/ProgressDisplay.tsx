"use client";

import type { ProgressEvent } from "@/lib/useGeneration";

interface Props {
  progress: ProgressEvent | null;
}

const STEPS = [
  { name: "script", label: "台本生成" },
  { name: "image", label: "画像生成" },
  { name: "video", label: "動画生成" },
  { name: "voice", label: "音声生成" },
  { name: "compose", label: "合成" },
];

export default function ProgressDisplay({ progress }: Props) {
  const currentStep = progress?.step ?? 0;

  return (
    <div className="space-y-6">
      {/* Stepper */}
      <div className="flex items-center justify-between">
        {STEPS.map((step, i) => {
          const stepNum = i + 1;
          const isActive = stepNum === currentStep;
          const isDone =
            stepNum < currentStep ||
            (stepNum === currentStep && progress?.status === "done");

          return (
            <div key={step.name} className="flex flex-col items-center flex-1">
              <div className="flex items-center w-full">
                {i > 0 && (
                  <div
                    className={`h-0.5 flex-1 ${
                      stepNum <= currentStep ? "bg-indigo-500" : "bg-gray-700"
                    }`}
                  />
                )}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                    isDone
                      ? "bg-indigo-500 text-white"
                      : isActive
                        ? "bg-indigo-600 text-white ring-2 ring-indigo-400 ring-offset-2 ring-offset-gray-950"
                        : "bg-gray-800 text-gray-500"
                  }`}
                >
                  {isDone ? (
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={3}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  ) : (
                    stepNum
                  )}
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    className={`h-0.5 flex-1 ${
                      stepNum < currentStep ? "bg-indigo-500" : "bg-gray-700"
                    }`}
                  />
                )}
              </div>
              <span
                className={`mt-2 text-xs ${
                  isActive
                    ? "text-indigo-400 font-medium"
                    : isDone
                      ? "text-gray-400"
                      : "text-gray-600"
                }`}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Detail */}
      {progress && (
        <div className="text-center space-y-2">
          <p className="text-sm text-gray-300">{progress.detail}</p>
          {progress.scene && progress.totalScenes && (
            <div className="mx-auto w-64">
              <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                  style={{
                    width: `${(progress.scene / progress.totalScenes) * 100}%`,
                  }}
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                シーン {progress.scene} / {progress.totalScenes}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Spinner */}
      <div className="flex justify-center">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    </div>
  );
}
