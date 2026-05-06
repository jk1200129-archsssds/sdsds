"""
TikTok Downloader - Fast Mode
==============================
- Max 60 second videos only
- 5 videos per user
- ultrafast FFmpeg preset
- ID-based history (no duplicates)
- ZIP → filebin.net upload
"""

import os, sys, subprocess, zipfile, hashlib, datetime, requests, yt_dlp

# ════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════

TARGET_USERNAMES = [
    ".smith58", "bullymovie1995", "ig.theshy6", "lee.movie.10",
    "lee.movie", "kyee_films", "billygardner", "utodio.hz",
    "yfuuet5", "oioi.movie1", "loong.movie", "milesmovies1",
    "aire.movie", "rushbolt42", "shadownarrator13", "lixchangysong",
    "hoang.ae", "1eesten", "eiei.edit"
]

VIDEOS_PER_USER = 5          # Har user se kitni videos
MAX_DURATION    = 60         # Max 60 seconds (1 minute)
TARGET_W        = 1080
TARGET_H        = 1920

HISTORY_FILE    = "download_history.txt"
FINAL_DIR       = "final_videos"
ZIP_DIR         = "zips"


# ════════════════════════════════════════
#  HISTORY  (ID-based)
# ════════════════════════════════════════

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE) as f:
        return set(l.strip() for l in f if l.strip())

def add_history(vid_id):
    with open(HISTORY_FILE, "a") as f:
        f.write(vid_id + "\n")


# ════════════════════════════════════════
#  FFMPEG  (ultrafast — speed priority)
# ════════════════════════════════════════

def ffmpeg_convert(src, dst):
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black"
    )
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "ultrafast",   # ← fastest encoding
        "-crf", "28",             # ← slightly lower quality = much faster
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30",
        dst
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        print(f"      ❌ ffmpeg error: {r.stderr[-200:]}")
        return False
    return True


# ════════════════════════════════════════
#  DOWNLOAD ONE VIDEO  (no intermediate file)
# ════════════════════════════════════════

def download_one(video, username, num):
    """Download + convert one video. Returns final path or None."""
    os.makedirs(FINAL_DIR, exist_ok=True)

    vid_id  = video["id"]
    url     = video.get("webpage_url") or video.get("url", "")
    # raw temp file (will be deleted after ffmpeg)
    raw     = os.path.join(FINAL_DIR, f"_raw_{username}_{num}.mp4")
    final   = os.path.join(FINAL_DIR, f"{username}_{num:02d}_{vid_id}.mp4")

    print(f"    [{num}] ⬇  {vid_id}  ({video.get('duration',0)}s)")

    opts = {
        "outtmpl":             raw,
        "quiet":               True,
        "no_warnings":         True,
        "format":              "best[ext=mp4]/best",   # single file, no merge needed
        "merge_output_format": "mp4",
        "retries":             2,
        "fragment_retries":    2,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"         ❌ download error: {e}")
        if os.path.exists(raw): os.remove(raw)
        return None

    # find actual downloaded file (yt-dlp may add extension)
    if not os.path.exists(raw):
        for ext in ("mp4","mkv","webm"):
            alt = raw.replace(".mp4", f".{ext}")
            if os.path.exists(alt):
                raw = alt; break

    if not os.path.exists(raw):
        print(f"         ❌ raw file not found after download")
        return None

    print(f"         🎬 ffmpeg convert...")
    ok = ffmpeg_convert(raw, final)
    os.remove(raw)

    if not ok:
        if os.path.exists(final): os.remove(final)
        return None

    mb = os.path.getsize(final) / 1048576
    print(f"         ✅ saved  {os.path.basename(final)}  ({mb:.1f} MB)")
    return final


# ════════════════════════════════════════
#  FETCH FRESH VIDEOS FOR ONE USER
# ════════════════════════════════════════

def fetch_fresh(username, history, needed):
    print(f"\n  🔍 @{username}  (need {needed} fresh ≤{MAX_DURATION}s videos)")

    opts = {
        "quiet":          True,
        "playlist_items": "1:40",   # scan latest 40
        "ignoreerrors":   True,
        "noplaylist":     True,
        "extract_flat":   False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.tiktok.com/@{username}", download=False)
    except Exception as e:
        print(f"     ⚠ fetch error: {e}")
        return []

    if not info or "entries" not in info:
        print(f"     ⚠ no entries found")
        return []

    fresh = []
    for v in info["entries"]:
        if not v: continue
        vid_id   = v.get("id","")
        duration = v.get("duration", 0) or 0

        if vid_id in history:
            print(f"     ⏭  skip (already downloaded): {vid_id}")
            continue
        if duration > MAX_DURATION:
            print(f"     ⏭  skip (too long {duration}s): {vid_id}")
            continue

        fresh.append(v)
        if len(fresh) >= needed:
            break

    print(f"     ✅ {len(fresh)} usable video(s) found")
    return fresh


# ════════════════════════════════════════
#  ZIP
# ════════════════════════════════════════

def make_zip(paths, zip_path):
    os.makedirs(ZIP_DIR, exist_ok=True)
    print(f"\n📦 Creating ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:  # STORED = no extra compression on video
        for p in paths:
            if p and os.path.exists(p):
                zf.write(p, os.path.basename(p))
                print(f"   + {os.path.basename(p)}")
    mb = os.path.getsize(zip_path) / 1048576
    print(f"✅ ZIP ready  {mb:.1f} MB")
    return zip_path


# ════════════════════════════════════════
#  FILEBIN UPLOAD
# ════════════════════════════════════════

def upload_filebin(zip_path):
    fname    = os.path.basename(zip_path)
    ts       = datetime.datetime.utcnow().strftime("%Y%m%d%H%M")
    h8       = hashlib.md5(fname.encode()).hexdigest()[:8]
    bin_id   = f"tt-{ts}-{h8}"
    up_url   = f"https://filebin.net/{bin_id}/{fname}"
    bin_url  = f"https://filebin.net/{bin_id}"
    zip_url  = f"https://filebin.net/archive/{bin_id}/zip"

    fsize = os.path.getsize(zip_path)
    sha   = hashlib.sha256(open(zip_path,"rb").read()).hexdigest()

    print(f"\n🚀 Uploading to filebin.net ...")
    print(f"   bin  : {bin_id}")
    print(f"   file : {fname}  ({fsize/1048576:.1f} MB)")

    try:
        with open(zip_path, "rb") as f:
            resp = requests.post(
                up_url,
                data=f,
                headers={
                    "Content-SHA256": sha,
                    "Content-Type":   "application/octet-stream",
                    "Content-Length": str(fsize),
                },
                timeout=600
            )
        if resp.status_code == 201:
            print(f"✅ Upload SUCCESS")
            print(f"\n{'='*55}")
            print(f"  📁 Bin Page     : {bin_url}")
            print(f"  📥 ZIP Download : {zip_url}")
            print(f"  ⏰ Expires      : 6 din baad")
            print(f"{'='*55}")
            return bin_url, zip_url
        else:
            print(f"❌ Upload failed  HTTP {resp.status_code}: {resp.text[:200]}")
            return None, None
    except Exception as e:
        print(f"❌ Upload exception: {e}")
        return None, None


# ════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════

def main():
    pkt = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    print("=" * 55)
    print("  TikTok Downloader  —  Fast Mode")
    print(f"  PKT  : {pkt.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Config: {VIDEOS_PER_USER} videos/user  |  max {MAX_DURATION}s each")
    print("=" * 55)

    # ffmpeg check
    if subprocess.run(["ffmpeg","-version"], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode != 0:
        print("❌ ffmpeg not found!"); sys.exit(1)
    print("✅ ffmpeg ready\n")

    history    = load_history()
    all_finals = []
    ok_count   = 0
    fail_count = 0

    for username in TARGET_USERNAMES:
        print(f"\n{'─'*55}")
        print(f"  USER: @{username}")
        print(f"{'─'*55}")

        videos = fetch_fresh(username, history, VIDEOS_PER_USER)
        if not videos:
            print(f"  ⚠  No fresh videos — skip")
            continue

        user_ok = 0
        for i, v in enumerate(videos, 1):
            path = download_one(v, username, i)
            if path:
                all_finals.append(path)
                add_history(v["id"])
                history.add(v["id"])
                ok_count  += 1
                user_ok   += 1
            else:
                fail_count += 1

        print(f"  📊 @{username}: {user_ok}/{len(videos)} downloaded")

    # ── Summary ──
    print(f"\n{'='*55}")
    print(f"  ✅ Downloaded : {ok_count}")
    print(f"  ❌ Failed     : {fail_count}")
    print(f"{'='*55}")

    if not all_finals:
        print("😴 Nothing to upload."); sys.exit(0)

    # ── ZIP ──
    date_tag  = pkt.strftime("%Y-%m-%d_%H-%M")
    zip_path  = os.path.join(ZIP_DIR, f"tiktok_{date_tag}.zip")
    make_zip(all_finals, zip_path)

    # cleanup final videos (already in zip)
    for p in all_finals:
        if os.path.exists(p): os.remove(p)
    try:
        if not os.listdir(FINAL_DIR): os.rmdir(FINAL_DIR)
    except: pass

    # ── Upload ──
    bin_url, dl_url = upload_filebin(zip_path)

    if bin_url and os.path.exists(zip_path):
        os.remove(zip_path)

    # ── GitHub output ──
    gho = os.environ.get("GITHUB_OUTPUT","")
    if gho:
        with open(gho,"a") as f:
            f.write(f"bin_url={bin_url or 'FAILED'}\n")
            f.write(f"download_url={dl_url or 'FAILED'}\n")
            f.write(f"total_downloaded={ok_count}\n")

    print("\n🏁 Done!")

if __name__ == "__main__":
    main()
