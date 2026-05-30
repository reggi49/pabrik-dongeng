const { bundle } = require("@remotion/bundler");
const { renderMedia, selectComposition } = require("@remotion/renderer");
const path = require("path");
const fs = require("fs");
const http = require("http");

const PROJECT_NAME = process.argv[2] || 'dongeng';
const CONFIG_PATH = path.resolve(process.cwd(), `public/${PROJECT_NAME}/config.json`);
const ASSET_SERVER_PORT = 3002;
const assetBaseUrl = `http://localhost:${ASSET_SERVER_PORT}`;

// Default configuration
const defaultProps = {
  title: "Video Percobaan",
  audioNarrationUrl: "",
  scenes: [
    {
      id: "scene-1",
      type: "video",
      assetUrl: "./public/test-assets/video1.mp4",
      durationInSeconds: 5,
    },
  ],
};

async function main() {
  console.log("\n==============================================");
  console.log(`🚀 [CLI] MEMULAI RENDER VIDEO... (Proyek: ${PROJECT_NAME})`);
  console.log("==============================================\n");

  let inputProps = defaultProps;

  if (fs.existsSync(CONFIG_PATH)) {
    try {
      inputProps = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
      console.log(`✅ Konfigurasi berhasil dibaca dari public/${PROJECT_NAME}/config.json`);
    } catch (err) {
      console.error(`❌ Gagal membaca public/${PROJECT_NAME}/config.json, menggunakan template bawaan.`);
    }
  } else {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(defaultProps, null, 2));
    console.log(`📝 Membuat file config.json baru di public/${PROJECT_NAME}/`);
  }

  // 1. Start lightweight HTTP server to serve the public directory
  let server;
  try {
    server = http.createServer((req, res) => {
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "*");

      if (req.method === "OPTIONS") {
        res.writeHead(204);
        res.end();
        return;
      }

      const decodedPath = decodeURIComponent(req.url || "");
      const safePath = path.normalize(decodedPath).replace(/^(\.\.[\/\\])+/, "");
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

    await new Promise((resolve, reject) => {
      server.listen(ASSET_SERVER_PORT, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
    console.log(`📡 [Asset Server] Running on ${assetBaseUrl} serving public/`);
  } catch (err) {
    console.error("❌ Gagal memulai server asset lokal:", err);
    process.exit(1);
  }

  // 2. Resolve relative paths to port 3002 URLs
  const resolveLocalAsset = (url) => {
    if (!url) return url;
    if (url.startsWith("/")) {
      return `${assetBaseUrl}${url}`;
    }
    if (url.startsWith(".")) {
      const relativePart = url.replace(/^\.+/, "").replace(/^[\/\\]/, "");
      // If it starts with public/, remove it because our server root is the public/ directory
      const cleanRelative = relativePart.startsWith("public/")
        ? relativePart.substring(7)
        : relativePart;
      return `${assetBaseUrl}/${cleanRelative}`;
    }
    // Map localhost:3000 to port 3002
    return url
      .replace(/http:\/\/localhost:3000/g, assetBaseUrl)
      .replace(/http:\/\/127.0.0.1:3000/g, assetBaseUrl);
  };

  if (inputProps.scenes) {
    inputProps.scenes = inputProps.scenes.map((scene) => ({
      ...scene,
      assetUrl: resolveLocalAsset(scene.assetUrl),
    }));
  }
  if (inputProps.audioNarrationUrl) {
    inputProps.audioNarrationUrl = resolveLocalAsset(inputProps.audioNarrationUrl);
  }

  const outDir = path.resolve(process.cwd(), "public/out");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const entryPoint = path.resolve(process.cwd(), "remotion/index.ts");
  console.log(`⚙️  Entry Point: ${entryPoint}`);

  try {
    console.log("⏳ [PHASE 1] Memulai bundling remotion (Webpack)...");
    const bundleLocation = await bundle({
      entryPoint,
      webpackOverride: (config) => config,
    });
    console.log(`✅ [PHASE 1] Bundling Selesai! Lokasi: ${bundleLocation}`);

    console.log("⏳ [PHASE 2] Mencari Composition 'YouTubeVideo'...");
    const composition = await selectComposition({
      serveUrl: bundleLocation,
      id: "YouTubeVideo",
      inputProps,
    });
    console.log(`✅ [PHASE 2] Composition ditemukan! Total Frame: ${composition.durationInFrames}`);

    const outputLocation = path.join(outDir, `video-${Date.now()}.mp4`);
    console.log(`⏳ [PHASE 3] Memulai rendering video ke -> ${outputLocation}\n`);

    await renderMedia({
      composition,
      serveUrl: bundleLocation,
      codec: "h264",
      outputLocation,
      inputProps,
      concurrency: 4,
      onProgress: ({ renderedFrames, progress }) => {
        const percent = Math.round(progress * 100);
        const filledWidth = Math.round(progress * 20);
        const emptyWidth = 20 - filledWidth;
        const bar = "#".repeat(filledWidth) + "-".repeat(emptyWidth);
        process.stdout.write(`🎥 Rendering: [${bar}] ${percent}% (${renderedFrames}/${composition.durationInFrames} frames)\r`);
      },
    });

    console.log("\n\n🎉 RENDER SELESAI!");
    console.log(`📁 Video disimpan ke: ${outputLocation}`);
    console.log("==============================================\n");

  } catch (error) {
    console.error("\n❌ ERROR FATAL:", error);
  } finally {
    if (server) {
      server.close();
      console.log("📡 [Asset Server] Stopped.");
    }
  }
}

main();
