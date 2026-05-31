import os
import json
import requests
import re
from datetime import datetime
import time
from dotenv import load_dotenv

# ==========================================
# 0. LOAD ENVIRONMENT VARIABLES
# ==========================================
load_dotenv()

# ==========================================
# 1. KONFIGURASI INTEGRASI KREDENSIAL API
# ==========================================
MIMO_MODEL = "mimo-v2.5-pro"
MIMO_URL = "https://api.xiaomimimo.com/v1/chat/completions"
MIMO_KEY = os.environ.get("MIMO_API_KEY")

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_KEY = os.environ.get("BRAVE_API_KEY")

PROGRESS_FILE = "progress.json"
MAX_RETRIES = 3
OUTPUT_DIR = "output_generator"
DEBUG_LOG_DIR = "debug_logs"
MAX_BRAVE_CHARS_PER_RESULT = 1200

# ==========================================
# 2. SISTEM MONITORING UTILITY LOGGING
# ==========================================
def log_status(status_type, message):
    symbols = {
        "INFO": "[💡 INFO]",
        "SUCCESS": "[✅ BERHASIL]",
        "WARN": "[⚠️ PERINGATAN]",
        "ERROR": "[❌ EROR]"
    }
    print(f"{symbols.get(status_type, '[•]')} {message}")

def load_progress_db():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            log_status("WARN", "Berkas progress.json korup. Membuat ulang database baru.")
            return {}
    return {}

def save_progress_db(data):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ensure_debug_log_dir():
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)

def clean_debug_name(value):
    cleaned = value.strip().lower().replace(" ", "_")
    return re.sub(r'[\\/*?:"<>|]', "", cleaned)

def text_len(value):
    return len(value or "")

def dump_debug_artifact(judul, attempt, phase, suffix, data, is_json=True):
    ensure_debug_log_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = clean_debug_name(judul)
    ext = "json" if is_json else "txt"
    path = os.path.join(DEBUG_LOG_DIR, f"{timestamp}_{safe_title}_attempt{attempt}_{phase}_{suffix}.{ext}")
    with open(path, 'w', encoding='utf-8') as f:
        if is_json:
            json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            f.write(data)
    return path

def compact_text(value, max_chars):
    value = re.sub(r'\s+', ' ', value or '').strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rsplit(" ", 1)[0].strip() + "..."

def extract_required_block(text, start_tag, end_tag):
    if start_tag in text and end_tag in text:
        return text.split(start_tag)[1].split(end_tag)[0].strip()
    log_status("WARN", f"Tag pembatas {start_tag} atau {end_tag} tidak ditemukan. Menggunakan seluruh teks.")
    return text.strip()

def build_scene_map(story_content, max_chars_per_scene=220):
    matches = list(re.finditer(r'\[Scene\s+(\d+)\]', story_content))
    if len(matches) != 40:
        log_status("WARN", f"Jumlah scene marker terdeteksi {len(matches)}, bukan 40. Scene map tetap dibuat dari marker yang tersedia.")

    scene_lines = []
    for index, match in enumerate(matches):
        scene_number = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(story_content)
        scene_text = compact_text(story_content[start:end], max_chars_per_scene)
        scene_lines.append(f"[Scene {scene_number}] {scene_text}")
    return "\n".join(scene_lines)

def build_compact_phase_context(metadata_json_block, scene_map):
    return f"{metadata_json_block.strip()}\n\n===SCENE_MAP_RINGKAS===\n{scene_map}\n===SELESAI_SCENE_MAP_RINGKAS==="

def filter_scene_map(scene_map, start_scene, end_scene):
    lines = []
    for line in scene_map.splitlines():
        match = re.match(r'\[Scene\s+(\d+)\]', line.strip())
        if match and start_scene <= int(match.group(1)) <= end_scene:
            lines.append(line)
    return "\n".join(lines)

def get_artifact_paths(output_dir, filename_base):
    return {
        "metadata": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase1_metadata.txt"),
        "story_part_1": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase1b_cerita_part1.txt"),
        "story_part_2": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase1c_cerita_part2.txt"),
        "story_full": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_cerita_full.txt"),
        "scene_map": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_scene_map.txt"),
        "compact_context": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_compact_context.txt"),
        "image_prompts_part_1": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase2a_image_prompts_1_20.txt"),
        "image_prompts_part_2": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase2b_image_prompts_21_40.txt"),
        "image_prompts_raw": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase2_image_prompts_raw.txt"),
        "video_part_1": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase3a_video_prompts_1_20.txt"),
        "video_part_2": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase3b_video_prompts_21_40.txt"),
        "video_prompts_raw": os.path.join(DEBUG_LOG_DIR, f"{filename_base}_fase3_video_prompts_raw.txt"),
    }

def read_text_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_text_artifact(path, content, label):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    log_status("SUCCESS", f"Artifact {label} tersimpan -> {path}")

def load_or_none(path):
    if os.path.exists(path):
        content = read_text_file(path)
        log_status("SUCCESS", f"Artifact ditemukan, fase dilewati -> {path}")
        return content
    return None

def summarize_payload_chars(payload):
    messages = payload.get("messages", [])
    message_chars = sum(text_len(message.get("content", "")) for message in messages)
    return {
        "message_count": len(messages),
        "message_chars": message_chars,
        "max_completion_tokens": payload.get("max_completion_tokens"),
        "temperature": payload.get("temperature")
    }

def post_mimo_with_debug(phase, judul, attempt, headers, payload, timeout):
    request_path = dump_debug_artifact(judul, attempt, phase, "request", payload, is_json=True)
    summary = summarize_payload_chars(payload)
    log_status(
        "INFO",
        f"[DEBUG {phase}] Request tersimpan -> {request_path} | messages={summary['message_count']} chars={summary['message_chars']} max_tokens={summary['max_completion_tokens']}"
    )

    started_at = time.time()
    try:
        response = requests.post(MIMO_URL, headers=headers, json=payload, timeout=timeout)
    except Exception as exc:
        error_path = dump_debug_artifact(
            judul,
            attempt,
            phase,
            "exception",
            f"{type(exc).__name__}: {exc}",
            is_json=False
        )
        log_status("WARN", f"[DEBUG {phase}] Exception tersimpan -> {error_path}")
        raise

    elapsed = time.time() - started_at
    response_text = response.text
    response_path = dump_debug_artifact(judul, attempt, phase, "response", response_text, is_json=False)
    log_status(
        "INFO",
        f"[DEBUG {phase}] Response tersimpan -> {response_path} | status={response.status_code} chars={len(response_text)} durasi={elapsed:.1f}s"
    )
    return response

def validasi_kualitas_llm(fase, teks_hasil):
    """
    Fungsi Quality Assurance (QA) Handler:
    Memastikan keluaran LLM memiliki tanda format yang valid serta isi struktur yang benar,
    terdiri dari jumlah item yang pas dan key data yang diperlukan sebelum di-save.
    """
    if "fase1_metadata" in fase:
        if "===MULAI_JSON===" not in teks_hasil or "===SELESAI_JSON===" not in teks_hasil:
            return False, "Kehilangan tag ===MULAI_JSON=== atau ===SELESAI_JSON==="
        
        # Ekstrak dan parse JSON untuk cek isinya
        try:
            json_meta_raw = teks_hasil.split("===MULAI_JSON===")[1].split("===SELESAI_JSON===")[0].strip()
            json_meta_raw = re.sub(r'^```json\s*|```$', '', json_meta_raw, flags=re.MULTILINE).strip()
            meta_json = json.loads(json_meta_raw)
            metadata = meta_json.get("metadata", {})
            
            # Cek field wajib
            required_keys = ["story_title", "character_sheets", "matched_visual_tags", "factual_plot_map"]
            for rk in required_keys:
                if rk not in metadata:
                    return False, f"Struktur metadata tidak lengkap (komponen '{rk}' missing)"
        except Exception as e:
            return False, f"Malformed JSON Metadata: {str(e)}"

    elif "fase1b_cerita" in fase:
        if "===MULAI_CERITA_PART_1===" not in teks_hasil or "===SELESAI_CERITA_PART_1===" not in teks_hasil:
            return False, "Kehilangan tag ===MULAI_CERITA_PART_1=== atau ===SELESAI_CERITA_PART_1==="
    elif "fase1c_cerita" in fase:
        if "===MULAI_CERITA_PART_2===" not in teks_hasil or "===SELESAI_CERITA_PART_2===" not in teks_hasil:
            return False, "Kehilangan tag ===MULAI_CERITA_PART_2=== atau ===SELESAI_CERITA_PART_2==="

    elif "fase2a_image_prompts" in fase or "fase2b_image_prompts" in fase:
        tag_mulai = "===MULAI_IMAGE_PART_1===" if "2a" in fase else "===MULAI_IMAGE_PART_2==="
        tag_selesai = "===SELESAI_IMAGE_PART_1===" if "2a" in fase else "===SELESAI_IMAGE_PART_2==="
        
        # Ekstrak data dan cek apakah ada "##" sejumlah yang tepat
        try:
            if tag_mulai in teks_hasil and tag_selesai in teks_hasil:
                img_block = teks_hasil.split(tag_mulai)[1].split(tag_selesai)[0].strip()
            else:
                # Fallback jika tag hilang tapi format list ## ada
                img_block = teks_hasil.strip()
                
            # Harus pakai split "##"
            parts = [p.strip() for p in img_block.split("##") if p.strip()]
            if len(parts) == 20:
                 return True, "Lolos QA (Fallback: Tags missing but structure is intact)"
            
            if tag_mulai not in teks_hasil or tag_selesai not in teks_hasil:
                return False, f"Kehilangan tag {tag_mulai} atau {tag_selesai}"
                
            if len(parts) != 20:
                return False, f"Jumlah prompt tidak valid! Ditemukan {len(parts)} prompt (dipisah '##'), namun seharusnya tepat 20."
        except Exception as e:
            return False, f"Gagal memvalidasi block image prompts: {str(e)}"

    elif "fase3" in fase:
        tag_mulai = "===MULAI_JSON_VIDEO_PART_1===" if "3a" in fase else "===MULAI_JSON_VIDEO_PART_2==="
        tag_selesai = "===SELESAI_JSON_VIDEO_PART_1===" if "3a" in fase else "===SELESAI_JSON_VIDEO_PART_2==="
        
        if tag_mulai not in teks_hasil and "```json" not in teks_hasil:
            return False, f"Tidak terdeteksi penanda awal list array JSON Video Prompts ({tag_mulai})"
        
        # Ekstrak dan parse JSON untuk cek kelengkapan schema dan jumlah scene
        try:
            if tag_mulai in teks_hasil:
                video_json_raw = teks_hasil.split(tag_mulai)[1].split(tag_selesai)[0].strip()
            else:
                video_json_raw = teks_hasil.split("```json")[1].split("```")[0].strip()

            video_json_raw = re.sub(r'^```json\s*|```$', '', video_json_raw, flags=re.MULTILINE).strip()
            parsed_video_json = json.loads(video_json_raw)
            
            prompts = parsed_video_json.get("video_generation_prompts", [])
            if len(prompts) != 20:
                return False, f"Jumlah video prompt tidak valid! Ditemukan {len(prompts)}, seharusnya tepat 20."
            
            required_keys = ["scene_number", "start_image", "end_image", "description"]
            for idx, p in enumerate(prompts):
                for rk in required_keys:
                    if rk not in p:
                        return False, f"Elemen ke-{idx+1} kehilangan key wajib '{rk}'"
        except Exception as e:
             return False, f"Malformed JSON Video Output: {str(e)}"

    return True, "Lolos QA"

# ==========================================
# 3. ENGINE CRAWLER BRAVE SEARCH API
# ==========================================
def pencarian_fakta_brave_api(judul):
    log_status("INFO", f"Melakukan crawling data valid untuk '{judul}' via Brave API...")
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_KEY
    }
    params = {
        "q": f"cerita rakyat asli kisah legenda dongeng {judul} tokoh utama sinopsis alur asli urutan kejadian",
        "count": 5,
        "extra_snippets": True
    }
    try:
        response = requests.get(BRAVE_URL, headers=headers, params=params, timeout=25)
        if response.status_code == 200:
            search_data = response.json()
            konteks_fakta = ""
            for index, item in enumerate(search_data.get("web", {}).get("results", [])):
                description = compact_text(item.get('description'), 800)
                snippets = compact_text(' '.join(item.get('extra_snippets', [])), 1000)
                source_line = f"REFERENSI {index+1} (Source: {item.get('url')}):\nDescription: {description}\nDetails: {snippets}"
                konteks_fakta += f"\n{source_line}\n---"
            konteks_fakta = konteks_fakta.strip()
            log_status("SUCCESS", f"Data referensi internet untuk '{judul}' berhasil dikumpulkan ({len(konteks_fakta)} karakter).")
            return konteks_fakta.strip()
        else:
            log_status("WARN", f"Brave Search mengembalikan HTTP {response.status_code}.")
            return "Fakta internet tidak ditemukan."
    except Exception as e:
        log_status("WARN", f"Gagal menghubungi server pencari: {e}")
        return "Koneksi pencarian terganggu."

# ==========================================
# 4. ENGINE SELEKSI ART STYLE LOKAL
# ==========================================
def alokasi_style_lokal(tags_ai, database_path="art_styles.json"):
    if not os.path.exists(database_path):
        return "Cute modern 2D vector illustration style, children book design aesthetic.", "Default Vector"
    with open(database_path, 'r', encoding='utf-8') as db_file:
        db_data = json.load(db_file)
    style_terpilih = db_data["art_styles_database"][0]
    skor_tertinggi = -1
    for style in db_data["art_styles_database"]:
        kesamaan = set(tags_ai).intersection(set(style["tags"]))
        skor = len(kesamaan)
        if skor > skor_tertinggi:
            skor_tertinggi = skor
            style_terpilih = style
    return style_terpilih["core_tokens"], style_terpilih["name"]


# =========================================================================
# 5. STRUKTUR MASTER PROMPT BERANTAI (FASE 1, FASE 2, FASE 3)
# =========================================================================

PROMPT_FASE_1_SYSTEM = """You are "Dongeng", an expert Creative Director and Folklore Historian for children's YouTube animation channels.
Your output will be parsed programmatically. Output ONLY the requested data blocks bounded by the tags (===). No preamble or side chat.

CRITICAL INSTRUCTION FOR STORY FIDELITY:
- You must prioritize the "REFERENSI FAKTA INTERNET ASLI" provided below. 
- Stick to the traditional names, locations, and key plot points of the Indonesian legend. 
- Do not invent modern plot twists that contradict the original essence of the folklore.
- Ensure the tone is culturally appropriate for Indonesian children.

YOUR TASK IN THIS PHASE:
1. Read the provided internet reference context, extract real traditional facts.
2. Choose a maximum of 10 visual tags from this pool: ["moral", "fabel", "hewan", "ceria", "modern", "kerajaan", "putri", "magis", "peri", "klasik", "mistis", "hantu", "sungai", "malam", "hutan", "rakyat", "pahlawan", "komedi", "legenda", "aksi", "raksasa", "kutukan", "petualangan", "alam", "pedesaan", "tenang", "emosional", "lucu", "balita", "sejarah", "serius", "kota", "misteri", "laut", "hitam-putih", "sederhana", "game", "daerah", "seram", "fantasi", "dramatis", "pulau"].
   - IMPORTANT: Sort these tags based on their priority and order of appearance in the story.
3. Identify and generate detailed character design sheet prompts for up to 5 most important characters found in the research.
4. Create a "Factual Plot Map" (Poin Alur Asli) which is a list of exactly 10 mandatory chronological events that MUST happen in the story to stay 100% faithful to the folklore.
5. Do NOT write the full story yet.

===MULAI_JSON===
{
  "metadata": {
    "story_title": "[Insert Clean Story Title Here]",
    "matched_visual_tags": ["tag_priority_1", "tag_priority_2", "...max_10_tags"],
    "factual_plot_map": [
        "1. [Mandatory Event 1]",
        "2. [Mandatory Event 2]",
        "...up_to_10_events"
    ],
    "character_sheets": {
      "Character_Name_1": "Character design sheet layout of [Name], full body front view, back view, and a close-up portrait showing three expressive emotional states, pure solid white background, isolated on white, highly detailed turnaround",
      "Character_Name_2": "...",
      "...up_to_5_characters": "..."
    }
  }
}
===SELESAI_JSON===
"""

PROMPT_FASE_1B_USER = """Excellent. Now generate PART 1 of the story script using the metadata and folklore reference context from the previous turn.

STRICT FIDELITY RULES:
- Use the traditional names and plot points provided in the research context.
- Maintain the original moral values and cultural nuances of the legend.
- Do not deviate from the core sequence of the traditional story.

YOUR TASK IN THIS PHASE:
1. Write only the first half of the story in INDONESIAN, slow-paced and descriptive.
2. You MUST weave exactly 20 chronological scene markers formatted precisely as [Scene 1] through [Scene 20].
3. Stop exactly after [Scene 20]. Do not write Scene 21 yet.
4. Output ONLY the part block bounded by the tags.

===MULAI_CERITA_PART_1===
# [Insert Story Title]
[Extended narrative text in INDONESIAN containing [Scene 1] to [Scene 20]]
===SELESAI_CERITA_PART_1==="""

PROMPT_FASE_1C_USER = """Continue the same story directly from Scene 20. Ensure part 2 stays consistent with the provided research facts.

YOUR TASK IN THIS PHASE:
1. Write only the second half of the story in INDONESIAN, slow-paced and descriptive.
2. You MUST weave exactly 20 chronological scene markers formatted precisely as [Scene 21] through [Scene 40].
3. Create a wholesome child-friendly happy ending by [Scene 40] while respecting the original legend's conclusion.
4. Do not repeat the title heading.
5. Output ONLY the part block bounded by the tags.

===MULAI_CERITA_PART_2===
[Extended narrative text in INDONESIAN containing [Scene 21] to [Scene 40]]
===SELESAI_CERITA_PART_2==="""

PROMPT_FASE_2_USER = """Generate exactly 20 chronological text-to-image prompts in ENGLISH based strictly on the provided compact scene map.

YOUR TASK IN THIS PHASE:
Use the metadata and ===SCENE_MAP_RINGKAS=== as the only source of truth. Generate prompts only for Scene 1 through Scene 20.

STRICT SYNTAX LAWS:
1. Do NOT prepend any prompt with text like "Scene X:" or "1.". Start the text immediately with subject description adjectives.
2. Every scene prompt must be separated cleanly by the double-hashtag " ## " delimiter.
3. Output exactly 20 image prompts. Absolutely no character sheets or extra texts are allowed inside this block. Output ONLY the block bounded by the tags.

===MULAI_IMAGE_PART_1===
[Direct composition prompt for scene 1 in English. No numbering label!] ##
[Direct composition prompt for scene 2 in English] ##
...
[Direct composition prompt for scene 20 in English]
===SELESAI_IMAGE_PART_1==="""

PROMPT_FASE_2B_USER = """Generate exactly 20 chronological text-to-image prompts in ENGLISH based strictly on the provided compact scene map.

YOUR TASK IN THIS PHASE:
Use the metadata and ===SCENE_MAP_RINGKAS=== as the only source of truth. Generate prompts only for Scene 21 through Scene 40.

STRICT SYNTAX LAWS:
1. Do NOT prepend any prompt with text like "Scene X:" or "1.". Start the text immediately with subject description adjectives.
2. Every scene prompt must be separated cleanly by the double-hashtag " ## " delimiter.
3. Output exactly 20 image prompts. Absolutely no character sheets or extra texts are allowed inside this block. Output ONLY the block bounded by the tags.

===MULAI_IMAGE_PART_2===
[Direct composition prompt for scene 21 in English. No numbering label!] ##
[Direct composition prompt for scene 22 in English] ##
...
[Direct composition prompt for scene 40 in English]
===SELESAI_IMAGE_PART_2==="""

PROMPT_FASE_3A_USER = """Generate exactly 20 cinematic image-to-video instructions mapped directly from Scene 1 to Scene 20.

YOUR TASK IN THIS PHASE:
Generate exactly 20 cinematic image-to-video instructions using the provided compact scene map and image prompts. Every description must contain a professional mix of camera movement and character movement to bring the artwork to life beautifully.

STRICT SYNTAX LAWS:
1. You MUST strictly use the exact original JSON schema required by the engine. Do not alter or simplify any keys.
2. Output exactly 20 valid JSON objects inside the "video_generation_prompts" array, sequentially from scene_number 1 to 20.
3. NEVER use inner double quotes (") inside JSON text values; use single quotes (') instead to prevent breaking the script syntax compiler.
4. Output ONLY the block bounded by the tags.

===MULAI_JSON_VIDEO_PART_1===
{
  "video_generation_prompts": [
    {
      "scene_number": 1,
      "start_image": "generated_image_1",
      "end_image": "generated_image_2",
      "description": "Slow cinematic tracking shot gliding through the environment. The main character moves smoothly while background elements warp gently."
    }
  ]
}
===SELESAI_JSON_VIDEO_PART_1==="""

PROMPT_FASE_3B_USER = """Generate exactly 20 cinematic image-to-video instructions mapped directly from Scene 21 to Scene 40.

YOUR TASK IN THIS PHASE:
Generate exactly 20 cinematic image-to-video instructions using the provided compact scene map and image prompts. Every description must contain a professional mix of camera movement and character movement to bring the artwork to life beautifully.

STRICT SYNTAX LAWS:
1. You MUST strictly use the exact original JSON schema required by the engine. Do not alter or simplify any keys.
2. Output exactly 20 valid JSON objects inside the "video_generation_prompts" array, sequentially from scene_number 21 to 40.
3. NEVER use inner double quotes (") inside JSON text values; use single quotes (') instead to prevent breaking the script syntax compiler.
4. Output ONLY the block bounded by the tags.

===MULAI_JSON_VIDEO_PART_2===
{
  "video_generation_prompts": [
    {
      "scene_number": 21,
      "start_image": "generated_image_21",
      "end_image": "generated_image_22",
      "description": "Slow cinematic tracking shot gliding through the environment. The main character moves smoothly while background elements warp gently."
    }
  ]
}
===SELESAI_JSON_VIDEO_PART_2==="""


# =========================================================================
# 6. ENGINE EKSTRAKSI HASIL (DIPISAH PER FASE AGAR AMAN RESUME)
# =========================================================================
def ekstrak_dan_simpan_fase1(out_fase1, filename_base, output_dir="output_generator"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    md_path = os.path.join(output_dir, f"{filename_base}.md")
    metadata = {}
    
    # 1. Parsing Metadata JSON & Character Sheets
    if "===MULAI_JSON===" in out_fase1:
        json_meta_raw = out_fase1.split("===MULAI_JSON===")[1].split("===SELESAI_JSON===")[0].strip()
        json_meta_raw = re.sub(r'^```json\s*|```$', '', json_meta_raw, flags=re.MULTILINE).strip()
        try:
            meta_json = json.loads(json_meta_raw)
            metadata = meta_json.get("metadata", {})
        except json.JSONDecodeError:
            log_status("WARN", "JSON Metadata fail to parse, fallback to raw extraction.")
        
        meta_txt_path = os.path.join(output_dir, f"{filename_base}_meta_data.txt")
        if not os.path.exists(meta_txt_path):
            with open(meta_txt_path, 'w', encoding='utf-8') as f_meta:
                json.dump(metadata, f_meta, indent=2, ensure_ascii=False)
            log_status("SUCCESS", f"File Metadata berhasil disimpan -> {meta_txt_path}")
    else:
        raise ValueError("Blok JSON metadata dari Fase 1 tidak ditemukan.")

    # 2. Ekstrak Cerita & Simpan ke .md dan stories.txt
    if not os.path.exists(md_path):
        if "===MULAI_CERITA===" in out_fase1:
            story_content = out_fase1.split("===MULAI_CERITA===")[1].split("===SELESAI_CERITA===")[0].strip()
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(story_content)
            log_status("SUCCESS", f"File Markdown berhasil ditulis -> {md_path}")
            
            stories_txt_path = os.path.join(DEBUG_LOG_DIR, "stories.txt")
            with open(stories_txt_path, 'a', encoding='utf-8') as f_stories:
                f_stories.write(f"\n\n==================== LOG CERITA: {filename_base.upper()} ====================\n")
                f_stories.write(story_content)
            log_status("SUCCESS", f"Arsip naskah berhasil ditambahkan ke {stories_txt_path}")
        else:
            raise ValueError("Blok teks cerita dari Fase 1 mengalami kerusakan struktur.")

    return metadata

def ekstrak_dan_simpan_fase2(out_fase2, visual_tags, filename_base, output_dir="output_generator"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    txt_path = os.path.join(output_dir, f"{filename_base}_text_to_image.txt")
    core_tokens, style_name = alokasi_style_lokal(visual_tags)
    
    if not os.path.exists(txt_path):
        log_status("INFO", f"Tags terpilih: {visual_tags} -> Terpilih Style Lokal: '{style_name}'")
        if "===MULAI_IMAGE===" in out_fase2:
            img_block = out_fase2.split("===MULAI_IMAGE===")[1].split("===SELESAI_IMAGE===")[0].strip()
            # Pisahkan menggunakan split "##" maupun "\n" untuk mengantisipasi LLM yang lupa separator
            img_block = img_block.replace("##", "\n")
            raw_prompts = [p for p in img_block.split("\n") if p.strip()]
            
            final_prompts_list = []
            for p in raw_prompts:
                clean_p = p.strip()
                if clean_p:
                    clean_p = re.sub(r'^scene\s*\d+\s*[:\-]\s*', '', clean_p, flags=re.IGNORECASE).strip()
                    final_prompts_list.append(f"{core_tokens} {clean_p}")
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(" ##\n".join(final_prompts_list))
            log_status("SUCCESS", f"File Prompt Gambar terintegrasi berhasil ditulis -> {txt_path}")
        else:
            raise ValueError("Blok prompt gambar dari Fase 2 tidak ditemukan.")
            
    return style_name

def ekstrak_dan_simpan_fase3(out_fase3, filename_base, output_dir="output_generator"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    json_path = os.path.join(output_dir, f"{filename_base}_image_to_video.json")
    if not os.path.exists(json_path):
        video_json_raw = None
        if "===MULAI_JSON_VIDEO===" in out_fase3:
            video_json_raw = out_fase3.split("===MULAI_JSON_VIDEO===")[1].split("===SELESAI_JSON_VIDEO===")[0].strip()
        elif "```json" in out_fase3:
            video_json_raw = out_fase3.split("```json")[1].split("```")[0].strip()
        else:
            video_json_raw = out_fase3.strip()

        if video_json_raw:
            video_json_raw = re.sub(r'^```json\s*|```$', '', video_json_raw, flags=re.MULTILINE).strip()
            try:
                parsed_video_json = json.loads(video_json_raw)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(parsed_video_json, f, indent=2, ensure_ascii=False)
                log_status("SUCCESS", f"File JSON Video Prompts berhasil ditulis -> {json_path}")
            except Exception as e:
                raise ValueError(f"Gagal melakukan parsing JSON video dari Fase 3: {str(e)}")
        else:
            raise ValueError("Blok JSON video dari Fase 3 tidak ditemukan.")

# ==========================================
# 7. MAIN AUTOMATION CONTROLLER LOOP
# ==========================================
def jalankan_pipeline_utama(input_queue_file="daftar_dongeng.json"):
    output_dir = OUTPUT_DIR

    if not os.path.exists(input_queue_file):
        log_status("ERROR", f"Berkas antrean input '{input_queue_file}' tidak ditemukan!")
        return

    with open(input_queue_file, 'r', encoding='utf-8') as f:
        queue_data = json.load(f)
    
    daftar_antrean = queue_data.get("queue", [])
    progress_db = load_progress_db()

    log_status("INFO", f"Sistem Utama Aktif. Menghitung antrean pipa: {len(daftar_antrean)} target judul.")

    for judul in daftar_antrean:
        key_name = judul.strip().lower().replace(" ", "_")
        key_name = re.sub(r'[\\/*?:"<>|]', "", key_name)

        if key_name in progress_db and progress_db[key_name].get("status") == "done":
            log_status("SUCCESS", f"Judul '{judul}' dilewati otomatis karena status sudah 'done' di progress.json.")
            continue

        print("\n" + "="*85)
        log_status("INFO", f"MEMPROSES SEKUENSIAL PIPELINE: '{judul.upper()}'")
        print("="*85)

        os.makedirs(output_dir, exist_ok=True)
        artifact_paths = get_artifact_paths(output_dir, key_name)

        if key_name not in progress_db:
            progress_db[key_name] = {
                "status": "pending",
                "attempts": 0,
                "tokoh_utama": [],
                "poin_wajib": [],
                "selected_art_style": "",
                "error": None,
                "timestamp": None
            }
        
        save_progress_db(progress_db)

        # Max retries dalam satu sesi (agar tidak looping selamanya jika API error terus-menerus)
        percobaan_sesi = 0
        while percobaan_sesi < 2:  # Maksimal 2 kali coba per judul dalam satu kali running script
            percobaan_sesi += 1
            progress_db[key_name]["attempts"] += 1
            current_total_attempts = progress_db[key_name]["attempts"]
            progress_db[key_name]["timestamp"] = datetime.now().isoformat()
            save_progress_db(progress_db)

            log_status("INFO", f"Memulai Percobaan ke-{percobaan_sesi} (Total: {current_total_attempts}) untuk '{judul}'...")
            
            konteks_fakta = pencarian_fakta_brave_api(judul)
            
            headers = {
                "api-key": MIMO_KEY,
                "Content-Type": "application/json"
            }
            
            try:
                # ------------------------------------------------------------------
                # [TEMBAKAN 1]: REQUEST FASE FONDASI & METADATA
                # ------------------------------------------------------------------
                output_fase_1_meta = load_or_none(artifact_paths["metadata"])
                if output_fase_1_meta is None:
                    log_status("INFO", "[TEMBAKAN 1] Meminta Metadata & Character Sheets...")
                    messages_fase1 = [
                        {"role": "system", "content": PROMPT_FASE_1_SYSTEM},
                        {"role": "user", "content": f"JUDUL DONGENG: {judul}\n\nREFERENSI FAKTA INTERNET ASLI:\n{konteks_fakta}"}
                    ]
                    payload_fase1 = {
                        "model": MIMO_MODEL, "messages": messages_fase1, "max_completion_tokens": 4096, "temperature": 0.45
                    }
                    
                    res1 = post_mimo_with_debug("fase1_metadata", judul, current_total_attempts, headers, payload_fase1, timeout=180)
                    if res1.status_code == 429:
                        log_status("WARN", "Rate limited (429) pada Tembakan 1. Mengulang loop...")
                        time.sleep(20)
                        continue
                    if res1.status_code != 200:
                        raise ConnectionError(f"HTTP Error {res1.status_code} pada Tembakan 1: {res1.text}")
                    if 'choices' not in res1.json():
                        raise ConnectionError(f"Malformed Response Server pada Tembakan 1: {res1.text}")
                        
                    output_fase_1_meta = res1.json()['choices'][0]['message']['content'].strip()
                    lolos_qa, alasan_qa = validasi_kualitas_llm("fase1_metadata", output_fase_1_meta)
                    if not lolos_qa:
                        raise ValueError(f"QA Failed (Tembakan 1 - Metadata): {alasan_qa}")
                    write_text_artifact(artifact_paths["metadata"], output_fase_1_meta, "Tembakan 1 Metadata")
                    log_status("SUCCESS", "Tembakan 1 Berhasil diunduh lolos QA.")

                # ------------------------------------------------------------------
                # [JALUR BYPASS CERITA]: GUNAKAN .MD BILA SUDAH ADA
                # ------------------------------------------------------------------
                md_path = os.path.join(output_dir, f"{key_name}.md")
                if os.path.exists(md_path):
                    log_status("INFO", f"Naskah {md_path} sudah ada. BYPASS Tembakan 1B & 1C.")
                    full_story_content = read_text_file(md_path)
                    
                    # Bangun ulang scene map & compact context dari MD yang sudah jadi
                    scene_map = load_or_none(artifact_paths["scene_map"])
                    if scene_map is None:
                        scene_map = build_scene_map(full_story_content)
                        write_text_artifact(artifact_paths["scene_map"], scene_map, "Scene Map Ringkas")
                        
                    compact_phase_context = load_or_none(artifact_paths["compact_context"])
                    if compact_phase_context is None:
                        compact_phase_context = build_compact_phase_context(output_fase_1_meta, scene_map)
                        write_text_artifact(artifact_paths["compact_context"], compact_phase_context, "Compact Context")
                        
                    # Ekstraksi Metadata Fase 1
                    metadata = ekstrak_dan_simpan_fase1(f"{output_fase_1_meta}\n\n===MULAI_CERITA===\n{full_story_content}\n===SELESAI_CERITA===", key_name, output_dir)
                else:
                    # ------------------------------------------------------------------
                    # [TEMBAKAN 1B]: REQUEST NASKAH CERITA BAGIAN 1
                    # ------------------------------------------------------------------
                    output_fase_1_story = load_or_none(artifact_paths["story_part_1"])
                    if output_fase_1_story is None:
                        log_status("INFO", "[TEMBAKAN 1B] Meminta Naskah Cerita Scene 1-20...")
                        messages_fase1b = [
                            {"role": "system", "content": "You are Dongeng, a strict structured-output story writer. Your story MUST align 100% with the provided RESEARCH FACTS and the FACTUAL PLOT MAP in the metadata. Do not contradict or omit any primary historical or legendary plot points."},
                            {"role": "user", "content": f"REFERENSI FAKTA ASLI:\n{konteks_fakta}\n\nMETADATA:\n{output_fase_1_meta}\n\n{PROMPT_FASE_1B_USER}"}
                        ]
                        payload_fase1b = {
                            "model": MIMO_MODEL, "messages": messages_fase1b, "max_completion_tokens": 8192, "temperature": 0.35
                        }

                        res1b = post_mimo_with_debug("fase1b_cerita", judul, current_total_attempts, headers, payload_fase1b, timeout=550)
                        if res1b.status_code == 429:
                            log_status("WARN", "Rate limited (429) pada Tembakan 1B. Mengulang loop...")
                            time.sleep(20)
                            continue
                        if res1b.status_code != 200:
                            raise ConnectionError(f"HTTP Error {res1b.status_code} pada Tembakan 1B: {res1b.text}")
                        if 'choices' not in res1b.json():
                            raise ConnectionError(f"Malformed Response Server pada Tembakan 1B: {res1b.text}")

                        output_fase_1_story = res1b.json()['choices'][0]['message']['content'].strip()
                        lolos_qa, alasan_qa = validasi_kualitas_llm("fase1b_cerita", output_fase_1_story)
                        if not lolos_qa:
                            raise ValueError(f"QA Failed (Tembakan 1B - Cerita Part 1): {alasan_qa}")
                        write_text_artifact(artifact_paths["story_part_1"], output_fase_1_story, "Tembakan 1B Cerita Part 1")
                        log_status("SUCCESS", "Tembakan 1B Berhasil diunduh lolos QA.")

                    # ------------------------------------------------------------------
                    # [TEMBAKAN 1C]: REQUEST NASKAH CERITA BAGIAN 2
                    # ------------------------------------------------------------------
                    output_fase_1_story_part_2 = load_or_none(artifact_paths["story_part_2"])
                    if output_fase_1_story_part_2 is None:
                        log_status("INFO", "[TEMBAKAN 1C] Meminta Naskah Cerita Scene 21-40...")
                        messages_fase1c = [
                            {"role": "system", "content": "You are Dongeng, a strict structured-output story writer. Continue only using the provided RESEARCH FACTS, metadata, and Part 1 artifact. Maintain 100% consistency with the traditional resolution of the folklore."},
                            {"role": "user", "content": f"REFERENSI FAKTA ASLI:\n{konteks_fakta}\n\nMETADATA:\n{output_fase_1_meta}\n\nPART 1:\n{output_fase_1_story}\n\n{PROMPT_FASE_1C_USER}"}
                        ]
                        payload_fase1c = {
                            "model": MIMO_MODEL, "messages": messages_fase1c, "max_completion_tokens": 8192, "temperature": 0.35
                        }

                        res1c = post_mimo_with_debug("fase1c_cerita", judul, current_total_attempts, headers, payload_fase1c, timeout=550)
                        if res1c.status_code == 429:
                            log_status("WARN", "Rate limited (429) pada Tembakan 1C. Mengulang loop...")
                            time.sleep(20)
                            continue
                        if res1c.status_code != 200:
                            raise ConnectionError(f"HTTP Error {res1c.status_code} pada Tembakan 1C: {res1c.text}")
                        if 'choices' not in res1c.json():
                            raise ConnectionError(f"Malformed Response Server pada Tembakan 1C: {res1c.text}")

                        output_fase_1_story_part_2 = res1c.json()['choices'][0]['message']['content'].strip()
                        lolos_qa, alasan_qa = validasi_kualitas_llm("fase1c_cerita", output_fase_1_story_part_2)
                        if not lolos_qa:
                            raise ValueError(f"QA Failed (Tembakan 1C - Cerita Part 2): {alasan_qa}")
                        write_text_artifact(artifact_paths["story_part_2"], output_fase_1_story_part_2, "Tembakan 1C Cerita Part 2")

                        story_part_1 = extract_required_block(output_fase_1_story, "===MULAI_CERITA_PART_1===", "===SELESAI_CERITA_PART_1===")
                        story_part_2 = extract_required_block(output_fase_1_story_part_2, "===MULAI_CERITA_PART_2===", "===SELESAI_CERITA_PART_2===")
                        output_fase_1_story_full = f"===MULAI_CERITA===\n{story_part_1}\n\n{story_part_2}\n===SELESAI_CERITA==="
                        output_fase_1 = f"{output_fase_1_meta}\n\n{output_fase_1_story_full}"
                        full_story_content = f"{story_part_1}\n\n{story_part_2}"
                        write_text_artifact(artifact_paths["story_full"], output_fase_1_story_full, "Cerita Full 40 Scene")

                        scene_map = load_or_none(artifact_paths["scene_map"])
                        if scene_map is None:
                            scene_map = build_scene_map(full_story_content)
                            write_text_artifact(artifact_paths["scene_map"], scene_map, "Scene Map Ringkas")
                        compact_phase_context = load_or_none(artifact_paths["compact_context"])
                        if compact_phase_context is None:
                            compact_phase_context = build_compact_phase_context(output_fase_1_meta, scene_map)
                            write_text_artifact(artifact_paths["compact_context"], compact_phase_context, "Compact Context")
                        log_status("SUCCESS", f"Tembakan 1C Berhasil diunduh dan naskah digabung menjadi 40 scene. Scene map ringkas: {len(scene_map)} karakter.")

                        # EKSTRAKSI HASIL FASE 1 SEGERA AGAR AMAN RESUME
                        metadata = ekstrak_dan_simpan_fase1(output_fase_1, key_name, output_dir)

                # ------------------------------------------------------------------
                # [TEMBAKAN 2]: REQUEST 40 BARIS TEXT TO IMAGE PROMPTS MURNI
                # ------------------------------------------------------------------
                output_fase_2 = load_or_none(artifact_paths["image_prompts_raw"])
                if output_fase_2 is None:
                    scene_map_1_20 = filter_scene_map(scene_map, 1, 20)
                    scene_map_21_40 = filter_scene_map(scene_map, 21, 40)
                    compact_context_1_20 = build_compact_phase_context(output_fase_1_meta, scene_map_1_20)
                    compact_context_21_40 = build_compact_phase_context(output_fase_1_meta, scene_map_21_40)

                    output_fase_2_part_1 = load_or_none(artifact_paths["image_prompts_part_1"])
                    if output_fase_2_part_1 is None:
                        log_status("INFO", "[TEMBAKAN 2A] Meminta Image Prompts Scene 1-20 dengan Artifact Fase 1...")
                        messages_fase2a = [
                            {"role": "system", "content": "You are Dongeng, a strict structured-output image prompt generator. Use only the provided compact context artifact."},
                            {"role": "user", "content": f"{compact_context_1_20}\n\n{PROMPT_FASE_2_USER}"}
                        ]
                        payload_fase2a = {
                            "model": MIMO_MODEL, "messages": messages_fase2a, "max_completion_tokens": 8192, "temperature": 0.65
                        }
                        
                        res2a = post_mimo_with_debug("fase2a_image_prompts", judul, current_total_attempts, headers, payload_fase2a, timeout=550)
                        if res2a.status_code != 200:
                            raise ConnectionError(f"HTTP Error {res2a.status_code} pada Tembakan 2A: {res2a.text}")
                        if 'choices' not in res2a.json():
                            raise ConnectionError(f"Malformed Response Server pada Tembakan 2A: {res2a.text}")
                            
                        output_fase_2_part_1 = res2a.json()['choices'][0]['message']['content'].strip()
                        lolos_qa, alasan_qa = validasi_kualitas_llm("fase2a_image_prompts", output_fase_2_part_1)
                        if not lolos_qa:
                            raise ValueError(f"QA Failed (Tembakan 2A - Image Prompts 1-20): {alasan_qa}")
                        write_text_artifact(artifact_paths["image_prompts_part_1"], output_fase_2_part_1, "Tembakan 2A Image Prompts 1-20")

                    output_fase_2_part_2 = load_or_none(artifact_paths["image_prompts_part_2"])
                    if output_fase_2_part_2 is None:
                        log_status("INFO", "[TEMBAKAN 2B] Meminta Image Prompts Scene 21-40 dengan Artifact Fase 1...")
                        messages_fase2b = [
                            {"role": "system", "content": "You are Dongeng, a strict structured-output image prompt generator. Use only the provided compact context artifact."},
                            {"role": "user", "content": f"{compact_context_21_40}\n\n{PROMPT_FASE_2B_USER}"}
                        ]
                        payload_fase2b = {
                            "model": MIMO_MODEL, "messages": messages_fase2b, "max_completion_tokens": 8192, "temperature": 0.65
                        }
                        
                        res2b = post_mimo_with_debug("fase2b_image_prompts", judul, current_total_attempts, headers, payload_fase2b, timeout=550)
                        if res2b.status_code != 200:
                            raise ConnectionError(f"HTTP Error {res2b.status_code} pada Tembakan 2B: {res2b.text}")
                        if 'choices' not in res2b.json():
                            raise ConnectionError(f"Malformed Response Server pada Tembakan 2B: {res2b.text}")
                            
                        output_fase_2_part_2 = res2b.json()['choices'][0]['message']['content'].strip()
                        lolos_qa, alasan_qa = validasi_kualitas_llm("fase2b_image_prompts", output_fase_2_part_2)
                        if not lolos_qa:
                            raise ValueError(f"QA Failed (Tembakan 2B - Image Prompts 21-40): {alasan_qa}")
                        write_text_artifact(artifact_paths["image_prompts_part_2"], output_fase_2_part_2, "Tembakan 2B Image Prompts 21-40")

                    image_prompts_1_20 = extract_required_block(output_fase_2_part_1, "===MULAI_IMAGE_PART_1===", "===SELESAI_IMAGE_PART_1===")
                    image_prompts_21_40 = extract_required_block(output_fase_2_part_2, "===MULAI_IMAGE_PART_2===", "===SELESAI_IMAGE_PART_2===")
                    output_fase_2 = f"===MULAI_IMAGE===\n{image_prompts_1_20} ##\n{image_prompts_21_40}\n===SELESAI_IMAGE==="
                    write_text_artifact(artifact_paths["image_prompts_raw"], output_fase_2, "Tembakan 2 Image Prompts Raw")
                    log_status("SUCCESS", "Tembakan 2 Berhasil diunduh.")

                # EKSTRAKSI HASIL FASE 2 SEGERA
                visual_tags = metadata.get("matched_visual_tags", [])
                style_name = ekstrak_dan_simpan_fase2(output_fase_2, visual_tags, key_name, output_dir)

                # ------------------------------------------------------------------
                # [TEMBAKAN 3]: REQUEST SKEMA GERAK VIDEO JSON ASLI (SPLIT FASE 3A & 3B)
                # ------------------------------------------------------------------
                output_fase_3 = load_or_none(artifact_paths["video_prompts_raw"])
                if output_fase_3 is None:
                    # Part 1 (Scene 1-20)
                    output_fase_3a = load_or_none(artifact_paths["video_part_1"])
                    if output_fase_3a is None:
                        log_status("INFO", "[TEMBAKAN 3A] Meminta Skema Gerak Video JSON Part 1 (1-20)...")
                        messages_fase3a = [
                            {"role": "system", "content": "You are Dongeng, a strict structured-output video prompt generator. Use only the provided compact scene map and image prompt artifacts."},
                            {"role": "user", "content": f"{compact_phase_context}\n\n{output_fase_2}\n\n{PROMPT_FASE_3A_USER}"}
                        ]
                        payload_fase3a = {
                            "model": MIMO_MODEL, "messages": messages_fase3a, "max_completion_tokens": 8192, "temperature": 0.5
                        }
                        res3a = post_mimo_with_debug("fase3a_video_prompts", judul, current_total_attempts, headers, payload_fase3a, timeout=550)
                        if res3a.status_code != 200:
                            raise ConnectionError(f"HTTP Error {res3a.status_code} pada Tembakan 3A: {res3a.text}")
                        output_fase_3a = res3a.json()['choices'][0]['message']['content'].strip()
                        lolos_qa, alasan_qa = validasi_kualitas_llm("fase3a_video", output_fase_3a)
                        if not lolos_qa:
                            raise ValueError(f"QA Failed (Tembakan 3A - Video JSON 1-20): {alasan_qa}")
                        write_text_artifact(artifact_paths["video_part_1"], output_fase_3a, "Tembakan 3A Video Part 1")

                    # Part 2 (Scene 21-40)
                    output_fase_3b = load_or_none(artifact_paths["video_part_2"])
                    if output_fase_3b is None:
                        log_status("INFO", "[TEMBAKAN 3B] Meminta Skema Gerak Video JSON Part 2 (21-40)...")
                        messages_fase3b = [
                            {"role": "system", "content": "You are Dongeng, a strict structured-output video prompt generator. Use only the provided compact scene map and image prompt artifacts."},
                            {"role": "user", "content": f"{compact_phase_context}\n\n{output_fase_2}\n\n{PROMPT_FASE_3B_USER}"}
                        ]
                        payload_fase3b = {
                            "model": MIMO_MODEL, "messages": messages_fase3b, "max_completion_tokens": 8192, "temperature": 0.5
                        }
                        res3b = post_mimo_with_debug("fase3b_video_prompts", judul, current_total_attempts, headers, payload_fase3b, timeout=550)
                        if res3b.status_code != 200:
                            raise ConnectionError(f"HTTP Error {res3b.status_code} pada Tembakan 3B: {res3b.text}")
                        output_fase_3b = res3b.json()['choices'][0]['message']['content'].strip()
                        lolos_qa, alasan_qa = validasi_kualitas_llm("fase3b_video", output_fase_3b)
                        if not lolos_qa:
                            raise ValueError(f"QA Failed (Tembakan 3B - Video JSON 21-40): {alasan_qa}")
                        write_text_artifact(artifact_paths["video_part_2"], output_fase_3b, "Tembakan 3B Video Part 2")

                    # Merge Results
                    try:
                        v1_raw = extract_required_block(output_fase_3a, "===MULAI_JSON_VIDEO_PART_1===", "===SELESAI_JSON_VIDEO_PART_1===")
                        v2_raw = extract_required_block(output_fase_3b, "===MULAI_JSON_VIDEO_PART_2===", "===SELESAI_JSON_VIDEO_PART_2===")
                        v1_json = json.loads(v1_raw)
                        v2_json = json.loads(v2_raw)
                        combined_prompts = v1_json.get("video_generation_prompts", []) + v2_json.get("video_generation_prompts", [])
                        output_fase_3 = json.dumps({"video_generation_prompts": combined_prompts}, indent=2)
                        write_text_artifact(artifact_paths["video_prompts_raw"], output_fase_3, "Tembakan 3 Video Prompts Combined Raw")
                        log_status("SUCCESS", "Tembakan 3A & 3B Berhasil diunduh dan digabung.")
                    except Exception as e:
                        raise ValueError(f"Gagal menggabungkan JSON Video 3A & 3B: {str(e)}")

                # EKSTRAKSI HASIL FASE 3 SEGERA
                ekstrak_dan_simpan_fase3(output_fase_3, key_name, output_dir)

                # Update Laporan Sukses ke progress.json
                progress_db[key_name]["tokoh_utama"] = list(metadata.get("character_sheets", {}).keys())
                progress_db[key_name]["poin_wajib"] = metadata.get("matched_visual_tags", [])
                progress_db[key_name]["selected_art_style"] = style_name
                progress_db[key_name]["status"] = "done"
                progress_db[key_name]["error"] = None
                save_progress_db(progress_db)
                
                log_status("SUCCESS", f"Selesai! Dongeng '{judul}' sukses diproduksi utuh lewat 3-Fase Berantai.")
                break

            except Exception as error_internal:
                error_msg = str(error_internal)
                log_status("WARN", f"Kegagalan pada percobaan sesi {percobaan_sesi} (Total: {progress_db[key_name]['attempts']}): {error_msg}")
                progress_db[key_name]["status"] = "failed"
                progress_db[key_name]["error"] = error_msg
                save_progress_db(progress_db)
                
                # Jika LLM 'lelah' atau error, kita pindah ke judul selanjutnya
                # Kita tidak berhenti permanen, tapi memberi kesempatan judul lain
                log_status("INFO", f"LLM lelah dengan '{judul}', pindah ke antrean berikutnya...")
                break

    print("\n" + "="*85 + "\n[🎉 PIPELINE COMPLETE] Semua antrean sekuensial diproses. Status aman di progress.json!\n")

if __name__ == "__main__":
    jalankan_pipeline_utama()
