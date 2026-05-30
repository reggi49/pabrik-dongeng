"use client";

import { useState } from "react";

export default function Dashboard() {
  const [jsonInput, setJsonInput] = useState(
    JSON.stringify(
      {
        title: "Video Percobaan",
        audioNarrationUrl: "",
        scenes: [
          {
            id: "scene-1",
            type: "video",
            assetUrl: "/test-assets/video1.mp4",
            durationInSeconds: 5,
          },
        ],
      },
      null,
      2
    )
  );
  const [isRendering, setIsRendering] = useState(false);
  const [progressLogs, setProgressLogs] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [finalVideoUrl, setFinalVideoUrl] = useState<string | null>(null);

  const handleRender = async () => {
    setIsRendering(true);
    setProgress(0);
    setProgressLogs(["Mengirim permintaan ke server..."]);
    setFinalVideoUrl(null);
    
    try {
      const parsedData = JSON.parse(jsonInput);
      const res = await fetch("/api/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsedData),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || "Gagal memulai render");
      }

      const jobId = data.jobId;
      setProgressLogs((prev) => [...prev, `Pekerjaan terdaftar: ID ${jobId}`, "Memulai pemantauan progress..."]);

      // Polling function
      const pollProgress = async () => {
        try {
          const pollRes = await fetch(`/api/render?jobId=${jobId}`);
          const pollData = await pollRes.json();
          if (pollRes.ok && pollData.success) {
            setProgress(pollData.progress);
            if (pollData.logs) {
              setProgressLogs(pollData.logs);
            }

            if (pollData.status === "completed") {
              setProgressLogs((prev) => [...prev, "Render selesai secara sukses!"]);
              setFinalVideoUrl(pollData.url);
              setIsRendering(false);
              clearInterval(pollInterval);
            } else if (pollData.status === "failed") {
              setProgressLogs((prev) => [...prev, `Gagal: ${pollData.error}`]);
              setIsRendering(false);
              clearInterval(pollInterval);
              alert("Render gagal: " + pollData.error);
            }
          }
        } catch (pollError) {
          console.error("Error polling progress:", pollError);
        }
      };

      // Poll every 1 second
      const pollInterval = setInterval(pollProgress, 1000);

    } catch (error) {
      setProgressLogs((prev) => [...prev, `Error: ${String(error)}`]);
      alert("Error: " + String(error));
      setIsRendering(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Pabrik Video Dashboard</h1>
          <p className="text-gray-600">Configure and render your automated video pipeline.</p>
        </header>

        <div className="bg-white rounded-xl shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Video Configuration</h2>
          <textarea
            className="w-full h-64 p-4 bg-gray-900 text-green-400 font-mono text-sm rounded-lg mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
          />
          <button
            onClick={handleRender}
            disabled={isRendering}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors disabled:opacity-50"
          >
            {isRendering ? "Submitting Render Job..." : "Render Video"}
          </button>

          {/* Progress Bar */}
          {isRendering && (
            <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-semibold text-gray-700">Proses Render</span>
                <span className="text-sm font-bold text-blue-600">{progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden shadow-inner">
                <div
                  className="bg-gradient-to-r from-blue-500 to-indigo-600 h-full rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Rendering Progress Logs */}
          {progressLogs.length > 0 && (
            <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg max-h-48 overflow-y-auto">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Live Progress:</h3>
              <ul className="space-y-1">
                {progressLogs.map((log, idx) => (
                  <li key={idx} className="text-xs font-mono text-gray-600 flex items-start">
                    <span className="text-blue-500 mr-2">➜</span> {log}
                  </li>
                ))}
              </ul>
              {finalVideoUrl && (
                <div className="mt-3 p-2 bg-green-100 text-green-800 text-sm font-semibold rounded text-center">
                  <a href={finalVideoUrl} target="_blank" rel="noreferrer" className="underline hover:text-green-900">
                    Lihat Hasil Video
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
