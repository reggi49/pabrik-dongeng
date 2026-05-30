import { NextResponse } from "next/server";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "path";
import fs from "fs";
import crypto from "crypto";
import http from "http";

export const maxDuration = 300;
export const dynamic = "force-dynamic";

const ASSET_SERVER_PORT = 3002;
const assetBaseUrl = `http://localhost:${ASSET_SERVER_PORT}`;

// Global job store to persist state across API calls in next dev
const globalForJobs = global as unknown as {
  jobs?: Map<string, {
    status: "queued" | "bundling" | "rendering" | "completed" | "failed";
    progress: number;
    logs: string[];
    url?: string;
    error?: string;
  }>;
  assetServerStarted?: boolean;
};

if (!globalForJobs.jobs) {
  globalForJobs.jobs = new Map();
}
const jobs = globalForJobs.jobs;

// Start the lightweight asset server to serve local assets from port 3002 to avoid circular deadlock on port 3000
if (!globalForJobs.assetServerStarted) {
  try {
    const server = http.createServer((req, res) => {
      // Enable CORS
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "*");

      if (req.method === "OPTIONS") {
        res.writeHead(204);
        res.end();
        return;
      }

      const decodedPath = decodeURIComponent(req.url || "");
      const safePath = path.normalize(decodedPath).replace(/^(\.\.[/\\])+/, "");
      const filePath = path.join(process.cwd(), "public", safePath);

      if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        res.writeHead(404, { "Content-Type": "text/plain" });
        res.end("Not Found");
        return;
      }

      const stat = fs.statSync(filePath);
      const fileSize = stat.size;
      const range = req.headers.range;

      if (range) {
        const parts = range.replace(/bytes=/, "").split("-");
        const start = parseInt(parts[0], 10);
        const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
        const chunksize = (end - start) + 1;
        const file = fs.createReadStream(filePath, { start, end });
        const head = {
          "Content-Range": `bytes ${start}-${end}/${fileSize}`,
          "Accept-Ranges": "bytes",
          "Content-Length": chunksize,
          "Content-Type": filePath.endsWith(".mp4") ? "video/mp4" : "application/octet-stream",
        };
        res.writeHead(206, head);
        file.pipe(res);
      } else {
        const head = {
          "Content-Length": fileSize,
          "Content-Type": filePath.endsWith(".mp4") ? "video/mp4" : "application/octet-stream",
        };
        res.writeHead(200, head);
        fs.createReadStream(filePath).pipe(res);
      }
    });

    server.listen(ASSET_SERVER_PORT, () => {
      console.log(`📡 [Asset Server] Running on ${assetBaseUrl} serving public/`);
    });
    globalForJobs.assetServerStarted = true;
  } catch (err) {
    console.error("❌ Failed to start asset server:", err);
  }
}

// GET handler to poll job status
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const jobId = searchParams.get("jobId");

  if (!jobId) {
    return NextResponse.json({ success: false, error: "Missing jobId parameter" }, { status: 400 });
  }

  const job = jobs.get(jobId);
  if (!job) {
    return NextResponse.json({ success: false, error: "Job not found" }, { status: 404 });
  }

  return NextResponse.json({ success: true, ...job });
}

// POST handler to start render job
export async function POST(req: Request) {
  console.log("\n==============================================");
  console.log("🚨 [API] POST /api/render TERPANGGIL!");

  try {
    const body = await req.json();
    console.log("✅ [API] Payload JSON berhasil dibaca.");

    const resolveAssetUrl = (url: string) => {
      if (!url) return url;
      if (url.startsWith("/")) {
        return `${assetBaseUrl}${url}`;
      }
      return url
        .replace(/http:\/\/localhost:3000/g, assetBaseUrl)
        .replace(/http:\/\/127.0.0.1:3000/g, assetBaseUrl);
    };

    // Resolve relative paths in input props to assetBaseUrl (port 3002)
    const resolvedScenes = body.scenes?.map((scene: { assetUrl: string; [key: string]: unknown }) => ({
      ...scene,
      assetUrl: resolveAssetUrl(scene.assetUrl),
    })) || [];

    const resolvedAudio = resolveAssetUrl(body.audioNarrationUrl);

    const resolvedProps = {
      ...body,
      scenes: resolvedScenes,
      audioNarrationUrl: resolvedAudio,
    };

    const jobId = crypto.randomUUID();
    jobs.set(jobId, {
      status: "queued",
      progress: 0,
      logs: ["Permintaan diterima oleh server.", "Menyiapkan antrean render..."],
    });

    // Run render process in the background
    (async () => {
      const updateJob = (updates: Partial<{ status: "queued" | "bundling" | "rendering" | "completed" | "failed"; progress: number; url?: string; error?: string }>) => {
        const job = jobs.get(jobId);
        if (job) {
          jobs.set(jobId, { ...job, ...updates });
        }
      };

      const addLog = (log: string) => {
        const job = jobs.get(jobId);
        if (job) {
          console.log(`[Job ${jobId}] ${log}`);
          jobs.set(jobId, { ...job, logs: [...job.logs, log] });
        }
      };

      try {
        const outDir = path.resolve(process.cwd(), "public/out");
        if (!fs.existsSync(outDir)) {
          fs.mkdirSync(outDir, { recursive: true });
          addLog("Folder public/out dibuat.");
        }

        const entryPoint = path.resolve(process.cwd(), "remotion/index.ts");
        addLog(`Entry point disetel ke: ${entryPoint}`);

        // BUNDLING PHASE
        updateJob({ status: "bundling", progress: 5 });
        addLog("⏳ [PHASE 1] Memulai @remotion/bundler (Webpack)...");
        
        const bundleLocation = await bundle({
          entryPoint,
          webpackOverride: (config) => config,
        });

        updateJob({ progress: 20 });
        addLog(`✅ [PHASE 1] Bundling Selesai! Lokasi: ${bundleLocation}`);

        // COMPOSITION PHASE
        updateJob({ status: "rendering", progress: 25 });
        addLog("⏳ [PHASE 2] Mencari Composition 'YouTubeVideo'...");
        
        const composition = await selectComposition({
          serveUrl: bundleLocation,
          id: "YouTubeVideo",
          inputProps: resolvedProps,
        });
        
        updateJob({ progress: 30 });
        addLog(`✅ [PHASE 2] Composition ditemukan! Total Frame: ${composition.durationInFrames}`);

        // RENDERING PHASE
        const outputLocation = path.join(outDir, `video-${Date.now()}.mp4`);
        addLog(`⏳ [PHASE 3] Memulai renderMedia ke -> ${outputLocation}`);

        await renderMedia({
          composition,
          serveUrl: bundleLocation,
          codec: "h264",
          outputLocation,
          inputProps: resolvedProps,
          onProgress: ({ renderedFrames, progress }) => {
            const percent = Math.round(progress * 100);
            updateJob({
              progress: Math.min(99, 30 + Math.round(percent * 0.69)), // 30% to 99%
            });
            if (renderedFrames % 15 === 0 || percent === 100) {
              addLog(`🎥 Progress Render: ${percent}% (${renderedFrames}/${composition.durationInFrames} frames)`);
            }
          },
        });

        addLog("🎉 RENDER SELESAI!");
        updateJob({
          status: "completed",
          progress: 100,
          url: `/out/${path.basename(outputLocation)}`,
        });

      } catch (error) {
        console.error(`❌ [Job ${jobId}] ERROR FATAL:`, error);
        addLog(`❌ ERROR FATAL: ${String(error)}`);
        updateJob({ status: "failed", error: String(error) });
      }
    })();

    return NextResponse.json({
      success: true,
      jobId,
      message: "Proses rendering dimulai di server.",
    }, { status: 202 });

  } catch (error) {
    console.error("❌ [API] ERROR FATAL:", error);
    return NextResponse.json({ success: false, error: String(error) }, { status: 500 });
  }
}
