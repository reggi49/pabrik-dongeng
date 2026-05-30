const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { getVideoDurationInSeconds } = require('get-video-duration');

const PROJECT_NAME = 'dongeng';
const BASE_DIR = path.join(__dirname, 'public', PROJECT_NAME);
const IMAGES_DIR = path.join(BASE_DIR, 'images');
const VIDEOS_DIR = path.join(BASE_DIR, 'videos');
const AUDIO_DIR = path.join(BASE_DIR, 'audio');
const CONFIG_PATH = path.join(BASE_DIR, 'config.json');

const IMAGE_DURATION_SEC = 2;
const CFR_FPS = 30;

function needsTranscoding(filePath) {
  try {
    const rFrameRate = execSync(
      `ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "${filePath}"`,
      { encoding: 'utf-8' }
    ).trim();
    const avgFrameRate = execSync(
      `ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate -of csv=p=0 "${filePath}"`,
      { encoding: 'utf-8' }
    ).trim();

    if (rFrameRate !== avgFrameRate) return true;

    const [num, den] = avgFrameRate.split('/').map(Number);
    if (den && num / den !== CFR_FPS) return true;

    const pictTypes = execSync(
      `ffprobe -v error -select_streams v:0 -show_entries frame=pict_type -of csv=p=0 "${filePath}"`,
      { encoding: 'utf-8' }
    ).trim().split('\n');

    const hasOnlyIframes = pictTypes.every(t => t.trim() === 'I');
    return !hasOnlyIframes;
  } catch {
    return true;
  }
}

function transcodeToCFR(inputPath, outputPath) {
  execSync(
    `ffmpeg -y -i "${inputPath}" -an -c:v libx264 -pix_fmt yuv420p -r 30 -g 1 -movflags +faststart "${outputPath}"`,
    { stdio: 'pipe' }
  );
}

function ensureVideoCFR(filePath) {
  const fileName = path.basename(filePath);
  const dirName = path.dirname(filePath);

  if (!needsTranscoding(filePath)) {
    console.log(`\n   ⏭️  ${fileName} is already CFR ${CFR_FPS}fps with all keyframes. Skipping.`);
    return;
  }

  console.log(`\n   🔄 Transcoding ${fileName} → CFR ${CFR_FPS}fps (GOP=1)...`);

  const tmpPath = path.join(dirName, `._tmp_cfr_${fileName}`);
  try {
    transcodeToCFR(filePath, tmpPath);
    fs.unlinkSync(filePath);
    fs.renameSync(tmpPath, filePath);
    console.log(`   ✅ ${fileName} transcoded successfully.`);
  } catch (err) {
    if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
    console.error(`   ❌ Failed to transcode ${fileName}:`, err.message);
  }
}

async function generateConfig() {
  console.log(`\n🔍 [GENERATE] Scanning project directory: public/${PROJECT_NAME}/...`);

  [BASE_DIR, IMAGES_DIR, VIDEOS_DIR, AUDIO_DIR].forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
      console.log(`📁 Created missing directory: ${dir}`);
    }
  });

  const audioFiles = fs.readdirSync(AUDIO_DIR).filter(f => f.endsWith('.mp3') || f.endsWith('.wav'));
  const mainAudio = audioFiles.length > 0 ? `./public/${PROJECT_NAME}/audio/${audioFiles[0]}` : "";
  if (mainAudio) console.log(`🎵 Found VoiceOver: ${audioFiles[0]}`);

  const videoScanResults = fs.readdirSync(VIDEOS_DIR).filter(f => f.endsWith('.mp4'));
  if (videoScanResults.length > 0) {
    console.log(`\n🎬 [CFR TRANSCODER] Checking ${videoScanResults.length} videos for VFR / missing keyframes...`);
    for (const f of videoScanResults) {
      ensureVideoCFR(path.join(VIDEOS_DIR, f));
    }
    console.log(`\n✅ [CFR TRANSCODER] All videos conditioned.\n`);
  }

  const imageFiles = fs.readdirSync(IMAGES_DIR)
    .filter(f => f.match(/\.(jpg|jpeg|png)$/i))
    .map(f => ({ name: f, type: 'image', path: path.join(IMAGES_DIR, f), url: `./public/${PROJECT_NAME}/images/${f}` }));

  const videoFiles = fs.readdirSync(VIDEOS_DIR)
    .filter(f => f.endsWith('.mp4'))
    .map(f => ({ name: f, type: 'video', path: path.join(VIDEOS_DIR, f), url: `./public/${PROJECT_NAME}/videos/${f}` }));

  const allVisuals = [...imageFiles, ...videoFiles].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
  );

  if (allVisuals.length === 0) {
    console.warn(`⚠️ [GENERATE] No visual assets found in images/ or videos/ directories.`);
    return;
  }

  console.log(`🎬 Found ${allVisuals.length} visual assets. Extracting metadata...`);

  const scenes = [];
  let totalDuration = 0;

  for (let i = 0; i < allVisuals.length; i++) {
    const asset = allVisuals[i];
    let duration = 0;

    if (asset.type === 'video') {
      try {
        duration = await getVideoDurationInSeconds(asset.path);
      } catch (err) {
        console.error(`\n❌ Failed to read duration for ${asset.name}. Defaulting to 10s.`, err.message);
        duration = 10;
      }
    } else {
      duration = IMAGE_DURATION_SEC;
    }

    totalDuration += duration;

    scenes.push({
      id: `scene-${i + 1}`,
      type: asset.type,
      assetUrl: asset.url,
      durationInSeconds: parseFloat(duration.toFixed(2))
    });

    process.stdout.write(`\r✅ Processed: ${i + 1}/${allVisuals.length} assets`);
  }

  const config = {
    title: `Proyek Video: ${PROJECT_NAME}`,
    audioNarrationUrl: mainAudio,
    scenes: scenes
  };

  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));

  console.log(`\n🎉 [GENERATE] SUCCESS!`);
  console.log(`📝 Configuration saved to: ${CONFIG_PATH}`);
  console.log(`⏱️  Total visual duration: ~${Math.floor(totalDuration / 60)}m ${Math.round(totalDuration % 60)}s`);
}

generateConfig();
