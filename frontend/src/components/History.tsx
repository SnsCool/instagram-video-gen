"use client";

import { useEffect, useState } from "react";

interface HistoryItem {
  run_id: string;
  created_at: string;
  theme: string;
  title: string;
  thumbnail: string | null;
  videoUrl: string | null;
  scene_count: number;
}

interface Props {
  onRestore: (runId: string) => void;
  onClose: () => void;
}

export default function History({ onRestore, onClose }: Props) {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/history");
      if (!res.ok) throw new Error("Failed to fetch history");
      const data = await res.json();
      setHistory(data.history);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (runId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("この履歴を削除しますか？")) return;

    try {
      const res = await fetch(`/api/history/${runId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete");
      setHistory((prev) => prev.filter((h) => h.run_id !== runId));
    } catch (err: any) {
      alert("削除に失敗しました: " + err.message);
    }
  };

  const formatDate = (dateStr: string) => {
    // run_id format: 20250209_153045
    if (dateStr.length === 15 && dateStr.includes("_")) {
      const year = dateStr.slice(0, 4);
      const month = dateStr.slice(4, 6);
      const day = dateStr.slice(6, 8);
      const hour = dateStr.slice(9, 11);
      const min = dateStr.slice(11, 13);
      return `${year}/${month}/${day} ${hour}:${min}`;
    }
    return dateStr;
  };

  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="animate-spin h-8 w-8 border-2 border-indigo-500 border-t-transparent rounded-full mx-auto" />
        <p className="mt-2 text-sm text-gray-400">読み込み中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-400 text-sm">{error}</p>
        <button
          onClick={onClose}
          className="mt-4 rounded-lg bg-gray-800 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
        >
          閉じる
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">履歴</h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-300 text-sm"
        >
          閉じる
        </button>
      </div>

      {history.length === 0 ? (
        <p className="text-center py-8 text-gray-500 text-sm">
          履歴がありません
        </p>
      ) : (
        <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
          {history.map((item) => (
            <div
              key={item.run_id}
              onClick={() => onRestore(item.run_id)}
              className="flex gap-3 p-3 rounded-lg bg-gray-800 hover:bg-gray-750 cursor-pointer transition group"
            >
              {/* Thumbnail */}
              <div className="w-16 h-28 flex-shrink-0 rounded overflow-hidden bg-gray-700">
                {item.thumbnail ? (
                  <img
                    src={item.thumbnail}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-500 text-xs">
                    No Image
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {item.title || item.theme || "無題"}
                </p>
                <p className="text-xs text-gray-400 truncate mt-0.5">
                  {item.theme}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {formatDate(item.created_at)}
                </p>
                <p className="text-xs text-gray-500">
                  {item.scene_count}シーン
                </p>

                <div className="flex gap-2 mt-2">
                  {item.videoUrl && (
                    <a
                      href={item.videoUrl}
                      download
                      onClick={(e) => e.stopPropagation()}
                      className="text-xs text-indigo-400 hover:text-indigo-300"
                    >
                      ダウンロード
                    </a>
                  )}
                  <button
                    onClick={(e) => handleDelete(item.run_id, e)}
                    className="text-xs text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    削除
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
