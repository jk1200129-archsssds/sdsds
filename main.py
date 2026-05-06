"""
TikTok Bulk Downloader
======================
- Har user ki 10 fresh videos download karta hai
- FFmpeg se 1080x1920 vertical format mein convert karta hai
- Sab videos ko ek ZIP mein pack karta hai
- ZIP ko filebin.net pe upload karta hai
- Download link print karta hai
"""

import os
import sys
import subprocess
import zipfile
import hashlib
import datetime
import requests
import yt_dlp

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════

TARGET_USERNAMES = [
    ".smith58",
    "bullymovie1995",
    "ig.theshy6",
    "lee.movie.10",
    "lee.movie",
    "kyee_films",
    "billygardner",
    "utodio.hz",
    "yfuuet5",
    "oioi.movie1",
    "loong.movie",
    "milesmovies1",
    "aire.movie",
    "rushbolt42",
    "shadownarrator13",
    "lixchangysong",
    "hoang.ae",
    "1eesten",
    "eiei.edit"
]

VIDEOS_PER_USER  = 10       # Har user se kitni videos
MAX_DURATION     = 180      # 3 min se zyada skip
TARGET_W         = 1080     # Final width
TARGET_H         = 1920     # Final height

HISTORY_FILE     = "download_history.txt"
RAW_DIR          = "raw_videos"
FINAL_DIR        = "final_videos"
ZIP_DIR          = "zips"


# ══════════════════════════════════════════════════════════
#  HISTORY
# ══════════════════════════════════════════════════════════

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_history(video_id):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{video_id}\n")


# ══════════════════════════════════════════════════════════
#  FFMPEG
# ══════════════════════════════════════════════════════════

def check_ffmpeg():
    try:
        r = subprocess.run(["ffmpeg", "-version"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except FileNotFoundError:
        return False

def ffmpeg_process(input_path, output_path):
    """
    1080x1920 vertical format mein convert karta hai.
    Aspect ratio maintain hoti hai, baaki area black hota hai.
    """
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black"
    )
    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-r", "30", "-movflags", "+faststart",
        "-y", output_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"      ❌ FFmpeg error:\n{result.stderr[-300:]}")
        return False
    return True


# ══════════════════════════════════════════════════════════
#  PROGRESS HOOK
# ══════════════════════════════════════════════════════════

def _hook(d):
    if d["status"] == "downloading":
        pct   = d.get("_percent_str", "?").strip()
        speed = d.get("_speed_str", "?").strip()
        eta   = d.get("_eta_str", "?").strip()
        print(f"\r      📥 {pct}  {speed}  eta {eta}   ", end="", flush=True)
    elif d["status"] == "finished":
        print(f"\r      📥 Download done, merging...              ")


# ══════════════════════════════════════════════════════════
#  TIKTOK — FETCH VIDEO LIST
# ══════════════════════════════════════════════════════════

def fetch_videos(username, history, needed):
    """
    User ke latest 50 videos scan karo.
    'needed' kadar fresh (not in history, <= MAX_DURATION) videos return karo.
    """
    print(f"\n   🔍 @{username} scan kar raha hoon (chahiye: {needed})")

    opts = {
        "quiet":          True,
        "playlist_items": "1:50",
        "ignoreerrors":   True,
        "noplaylist":     True,
        "extract_flat":   False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"https://www.tiktok.com/@{username}", download=False)
    except Exception as e:
        print(f"      ⚠️  Fetch error: {e}")
        return []

    if not info or "entries" not in info:
        print(f"      ⚠️  Koi entries nahi.")
        return []

    found = []
    for v in info["entries"]:
        if not v:
            continue
        vid_id   = v.get("id", "")
        duration = v.get("duration", 0) or 0
        if vid_id in history:
            continue
        if duration > MAX_DURATION:
            continue
        found.append(v)
        if len(found) >= needed:
            break

    print(f"      ✅ {len(found)} fresh video(s) mili")
    return found


# ══════════════════════════════════════════════════════════
#  TIKTOK — DOWNLOAD + PROCESS ONE VIDEO
# ══════════════════════════════════════════════════════════

def download_and_process(video, username, num):
    """
    Ek video download karo aur FFmpeg se process karo.
    Returns: final output path ya None
    """
    os.makedirs(RAW_DIR,   exist_ok=True)
    os.makedirs(FINAL_DIR, exist_ok=True)

    vid_id   = video["id"]
    url      = video.get("webpage_url") or video.get("url")
    raw_path = os.path.join(RAW_DIR, f"{username}_{num}_{vid_id}.mp4")
    fin_path = os.path.join(FINAL_DIR, f"{username}_{num:02d}_{vid_id}.mp4")

    print(f"      ⬇️  [{num}] Downloading: {vid_id}")

    dl_opts = {
        "outtmpl":             raw_path,
        "quiet":               True,
        "no_warnings":         True,
        "format": (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=1080]+bestaudio"
            "/best[ext=mp4]/best"
        ),
        "merge_output_format": "mp4",
        "progress_hooks":      [_hook],
        "retries":             3,
        "fragment_retries":    3,
    }

    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"\n      ❌ Download failed: {e}")
        return None

    # File check (yt-dlp kabhi kabhi path thoda alag hota hai)
    if not os.path.exists(raw_path):
        for ext in ["mp4", "mkv", "webm"]:
            alt = os.path.join(RAW_DIR, f"{username}_{num}_{vid_id}.{ext}")
            if os.path.exists(alt):
                raw_path = alt
                break

    if not os.path.exists(raw_path):
        print(f"      ❌ Raw file nahi mili.")
        return None

    print(f"      🎬 FFmpeg processing...")
    ok = ffmpeg_process(raw_path, fin_path)

    # Raw delete karo
    if os.path.exists(raw_path):
        os.remove(raw_path)

    if not ok:
        if os.path.exists(fin_path):
            os.remove(fin_path)
        return None

    size_mb = os.path.getsize(fin_path) / (1024 * 1024)
    print(f"      ✅ Done: {os.path.basename(fin_path)} ({size_mb:.1f} MB)")
    return fin_path


# ══════════════════════════════════════════════════════════
#  ZIP CREATOR
# ══════════════════════════════════════════════════════════

def create_zip(video_paths, zip_path):
    """Saari final videos ko ek ZIP mein pack karo."""
    print(f"\n📦 ZIP bana raha hoon: {zip_path}")
    os.makedirs(ZIP_DIR, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for vp in video_paths:
            if vp and os.path.exists(vp):
                arcname = os.path.basename(vp)
                zf.write(vp, arcname)
                print(f"   + {arcname}")

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"✅ ZIP ready: {zip_path} ({size_mb:.1f} MB)")
    return zip_path


# ══════════════════════════════════════════════════════════
#  FILEBIN UPLOADER
# ══════════════════════════════════════════════════════════

def upload_to_filebin(zip_path):
    """
    ZIP file ko filebin.net pe upload karo.
    API: POST https://filebin.net/{bin}/{filename}
    Returns: (bin_url, download_url) ya (None, None)
    """
    filename = os.path.basename(zip_path)

    # Unique bin ID: date + short hash
    date_str  = datetime.datetime.utcnow().strftime("%Y%m%d%H%M")
    short_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    bin_id    = f"tiktok-{date_str}-{short_hash}"

    upload_url = f"https://filebin.net/{bin_id}/{filename}"
    bin_url    = f"https://filebin.net/{bin_id}"
    zip_url    = f"https://filebin.net/archive/{bin_id}/zip"

    print(f"\n🚀 Filebin pe upload ho raha hai...")
    print(f"   Bin ID   : {bin_id}")
    print(f"   File     : {filename}")
    print(f"   Upload URL: {upload_url}")

    file_size = os.path.getsize(zip_path)
    print(f"   Size     : {file_size / (1024*1024):.1f} MB")

    # SHA256 checksum for integrity
    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    checksum = sha256.hexdigest()

    headers = {
        "Content-SHA256": checksum,
        "Content-Type":   "application/octet-stream",
        "Content-Length": str(file_size),
    }

    try:
        with open(zip_path, "rb") as f:
            resp = requests.post(
                upload_url,
                data=f,
                headers=headers,
                timeout=300   # 5 min timeout for large files
            )

        if resp.status_code == 201:
            print(f"\n🎉 UPLOAD SUCCESS!")
            print(f"   📁 Bin URL      : {bin_url}")
            print(f"   📥 ZIP Download : {zip_url}")
            print(f"   ⚠️  Note         : Files 6 din baad delete ho jayenge")
            return bin_url, zip_url
        else:
            print(f"❌ Upload failed! Status: {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
            return None, None

    except requests.exceptions.Timeout:
        print("❌ Upload timeout! File bohat bari hai ya internet slow hai.")
        return None, None
    except Exception as e:
        print(f"❌ Upload exception: {e}")
        return None, None


# ══════════════════════════════════════════════════════════
#  CLEANUP
# ══════════════════════════════════════════════════════════

def cleanup_final_videos(video_paths):
    """Final videos delete karo (ZIP mein already hai)."""
    print("\n🗑️  Final videos cleanup...")
    for vp in video_paths:
        if vp and os.path.exists(vp):
            os.remove(vp)
    # Folder bhi hatao agar khali hai
    try:
        if os.path.exists(FINAL_DIR) and not os.listdir(FINAL_DIR):
            os.rmdir(FINAL_DIR)
    except:
        pass


# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════

def main():
    pkt_time = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    date_str = pkt_time.strftime("%Y-%m-%d_%H-%M")

    print("=" * 65)
    print("   TikTok Bulk Downloader → ZIP → Filebin")
    print(f"   Pakistan Time : {pkt_time.strftime('%Y-%m-%d %H:%M')} PKT")
    print("=" * 65)

    # FFmpeg check
    if not check_ffmpeg():
        print("\n❌ FFmpeg nahi mila!")
        print("   Linux:   sudo apt-get install -y ffmpeg")
        print("   Windows: https://ffmpeg.org/download.html")
        sys.exit(1)
    print("✅ FFmpeg ready\n")

    history     = load_history()
    all_finals  = []  # Successful final video paths
    total_dl    = 0
    total_fail  = 0

    # ── Har user ke liye loop ──
    for username in TARGET_USERNAMES:
        print(f"\n{'═' * 65}")
        print(f"  USER: @{username}")
        print(f"{'═' * 65}")

        videos = fetch_videos(username, history, VIDEOS_PER_USER)

        if not videos:
            print(f"   ⚠️  Koi valid video nahi mili, skip.")
            continue

        user_count = 0
        for i, video in enumerate(videos, start=1):
            fin = download_and_process(video, username, i)
            if fin:
                all_finals.append(fin)
                save_history(video["id"])
                history.add(video["id"])
                user_count += 1
                total_dl   += 1
            else:
                total_fail += 1

        print(f"\n   📊 @{username}: {user_count}/{len(videos)} videos download hue")

    # ── Summary ──
    print(f"\n{'═' * 65}")
    print(f"  DOWNLOAD SUMMARY")
    print(f"  ✅ Successful : {total_dl}")
    print(f"  ❌ Failed     : {total_fail}")
    print(f"  📁 Total files: {len(all_finals)}")
    print(f"{'═' * 65}")

    if not all_finals:
        print("\n😴 Koi video download nahi hui. Kuch nahi karna.")
        sys.exit(0)

    # ── ZIP banao ──
    zip_filename = f"tiktok_videos_{date_str}.zip"
    zip_path     = os.path.join(ZIP_DIR, zip_filename)
    create_zip(all_finals, zip_path)

    # ── Final videos cleanup (ZIP mein hai, ab zaroorat nahi) ──
    cleanup_final_videos(all_finals)

    # ── Filebin pe upload ──
    bin_url, download_url = upload_to_filebin(zip_path)

    # ── ZIP bhi delete karo (upload ho gaya) ──
    if bin_url and os.path.exists(zip_path):
        os.remove(zip_path)
        print(f"🗑️  Local ZIP delete kiya (filebin pe hai)")

    # ── Final output ──
    print(f"\n{'=' * 65}")
    print("  🏁 ALL DONE!")
    if bin_url:
        print(f"  📁 Bin Page     : {bin_url}")
        print(f"  📥 ZIP Download : {download_url}")
        print(f"  ⏰ Expires in   : 6 din")
    else:
        print("  ⚠️  Upload fail hua. ZIP locally check karo.")
        print(f"  📦 Local ZIP    : {zip_path}")
    print("=" * 65)

    # GitHub Actions mein output set karo (optional)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as gh_out:
            gh_out.write(f"bin_url={bin_url or 'FAILED'}\n")
            gh_out.write(f"download_url={download_url or 'FAILED'}\n")
            gh_out.write(f"total_downloaded={total_dl}\n")


if __name__ == "__main__":
    main()
