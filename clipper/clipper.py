#!/usr/bin/env python3
"""Clip-Cutter: findet Highlights in langen Videos (Stream-VODs) und
schneidet sie zu fertigen Hochformat-Clips (9:16) fuer Shorts/TikTok/Reels.

Nur ffmpeg ist Pflicht. Optional: yt-dlp (fetch), faster-whisper (transcribe).

Ablauf:
  python3 clipper.py fetch     URL -o vod.mp4            # optional, braucht yt-dlp
  python3 clipper.py transcribe vod.mp4 -o vod.srt       # optional, braucht faster-whisper
  python3 clipper.py analyze   vod.mp4 [--srt vod.srt] [--chat chat.csv] -n 5 -o clips.json
  #   -> clips.json bearbeiten: pro Clip "hook" eintragen (macht Claude)
  python3 clipper.py render    vod.mp4 clips.json [--srt vod.srt] -d out/
  python3 clipper.py auto      vod.mp4 -n 5 -d out/       # analyze + render ohne Hooks
"""
import argparse
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
from array import array

RATE = 4000  # Hz fuer die Lautstaerke-Analyse, reicht voellig
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
HYPE_WORDS = [
    "oh mein gott", "oh my god", "omg", "was", "what", "alter", "digga", "nein",
    "no way", "krass", "wtf", "lol", "haha", "let's go", "lets go", "boah", "junge",
    "bro", "insane", "unglaublich", "wie", "hä", "clip", "clip it",
]


# ---------------------------------------------------------------- helpers
def die(msg):
    print(f"Fehler: {msg}", file=sys.stderr)
    sys.exit(1)


def need(tool):
    if not shutil.which(tool):
        die(f"'{tool}' ist nicht installiert.")


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def fmt_ts(sec):
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def srt_time(t):
    ms = int(round((t - int(t)) * 1000))
    return f"{fmt_ts(t)},{ms:03d}"


def parse_srt(path):
    """-> Liste von (start, end, text)."""
    if not path:
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        blocks = re.split(r"\n\s*\n", f.read().strip())
    ts = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
    cues = []
    for b in blocks:
        lines = b.strip().splitlines()
        for i, line in enumerate(lines):
            m = ts.search(line)
            if m:
                g = list(map(int, m.groups()))
                s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
                e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
                cues.append((s, e, " ".join(lines[i + 1:]).strip()))
                break
    return cues


def write_srt(cues, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, (s, e, t) in enumerate(cues, 1):
            f.write(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{t}\n\n")


def load_chat(path):
    """CSV/TXT mit Sekunden-Zeitstempel (oder hh:mm:ss) in der ersten Spalte."""
    if not path:
        return []
    times = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            first = re.split(r"[,;\t ]", line.strip(), maxsplit=1)[0]
            try:
                if ":" in first:
                    parts = [float(p) for p in first.split(":")]
                    while len(parts) < 3:
                        parts.insert(0, 0.0)
                    times.append(parts[0] * 3600 + parts[1] * 60 + parts[2])
                else:
                    times.append(float(first))
            except ValueError:
                continue  # Kopfzeile o.ae.
    return times


# ---------------------------------------------------------------- analyse
def loudness_per_second(path):
    """RMS-Lautstaerke (dB) pro Sekunde, gestreamt -> auch fuer stundenlange VODs."""
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(RATE),
         "-f", "s16le", "-"], stdout=subprocess.PIPE)
    db = []
    chunk = RATE * 2
    buf = b""
    while True:
        data = proc.stdout.read(chunk * 16)
        if not data:
            break
        buf += data
        while len(buf) >= chunk:
            a = array("h", buf[:chunk])
            buf = buf[chunk:]
            rms = math.sqrt(sum(x * x for x in a) / len(a)) or 1.0
            db.append(20 * math.log10(rms / 32768))
    proc.wait()
    if proc.returncode != 0 and not db:
        die("Konnte keine Tonspur lesen (hat das Video Audio?).")
    return db


def zscores(values, window=90):
    """Abweichung vom gleitenden Median -> 'ploetzlich lauter als sonst'."""
    out = []
    n = len(values)
    spread = statistics.pstdev(values) or 1.0
    for i in range(n):
        lo, hi = max(0, i - window), min(n, i + window)
        base = statistics.median(values[lo:hi])
        out.append((values[i] - base) / spread)
    return out


def smooth(values, k=3):
    out = []
    for i in range(len(values)):
        seg = values[max(0, i - k):i + k + 1]
        out.append(sum(seg) / len(seg))
    return out


def score_timeline(n_sec, loud, chat, cues):
    score = smooth(zscores(loud), 2) if loud else [0.0] * n_sec
    score = (score + [0.0] * n_sec)[:n_sec]
    if chat:
        rate = [0] * n_sec
        for t in chat:
            if 0 <= t < n_sec:
                rate[int(t)] += 1
        cz = smooth(zscores([float(r) for r in rate], 120), 3)
        score = [s + 1.5 * c for s, c in zip(score, cz)]
    for s, e, text in cues:
        low = text.lower()
        hits = sum(1 for w in HYPE_WORDS if re.search(rf"\b{re.escape(w)}\b", low))
        hits += low.count("!")
        for t in range(int(s), min(n_sec, int(e) + 1)):
            score[t] += 0.6 * hits
    return score


def pick_clips(score, n, length, lead, total):
    """Top-n nicht ueberlappende Fenster; Start etwas vor dem Peak (Aufbau)."""
    win = max(1, int(length))
    # Fensterscore = Mittel ueber das Clip-Fenster, Peak zaehlt doppelt
    cands = []
    for peak in range(len(score)):
        start = max(0.0, min(peak - lead, total - length))
        a, b = int(start), int(start) + win
        seg = score[a:b] or [0.0]
        cands.append((sum(seg) / len(seg) + max(seg), start, peak))
    cands.sort(reverse=True)
    chosen = []
    for sc, start, peak in cands:
        if all(abs(start - c["start"]) >= length for c in chosen):
            chosen.append({"start": round(start, 2), "end": round(min(total, start + length), 2),
                           "peak": peak, "score": round(sc, 2)})
        if len(chosen) >= n:
            break
    chosen.sort(key=lambda c: c["start"])
    return chosen


def cmd_analyze(args, quiet=False):
    total = duration(args.video)
    loud = loudness_per_second(args.video)
    cues = parse_srt(args.srt)
    chat = load_chat(args.chat)
    n_sec = max(1, int(math.ceil(total)))
    score = score_timeline(n_sec, loud, chat, cues)
    clips = pick_clips(score, args.n, args.length, args.lead, total)
    for i, c in enumerate(clips, 1):
        c["id"] = i
        c["timestamp"] = fmt_ts(c["start"])
        c["transcript"] = " ".join(t for s, e, t in cues if e > c["start"] and s < c["end"])
        c["hook"] = ""
        c["title"] = ""
    result = {"video": os.path.abspath(args.video), "duration": round(total, 2),
              "signals": {"audio": bool(loud), "chat": bool(chat), "transcript": bool(cues)},
              "clips": clips}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if not quiet:
        print(f"{len(clips)} Highlights gefunden -> {args.out}")
        for c in clips:
            print(f"  #{c['id']}  {c['timestamp']}  ({c['end'] - c['start']:.0f}s)  score {c['score']}")
        print("Naechster Schritt: 'hook' (und optional 'title') pro Clip eintragen, dann 'render'.")
    return result


# ---------------------------------------------------------------- render
def esc_drawtext(text):
    return (text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")
            .replace("%", "\\%"))


EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def wrap(text, width=22):
    # Emojis kann die Video-Schrift nicht -> im Bild weglassen (im Titel bleiben sie)
    words, lines, cur = EMOJI.sub("", text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines[:4])


def font_path():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def render_clip(video, clip, out_path, cues, hook_secs, workdir):
    start, end = clip["start"], clip["end"]
    length = end - start
    W, H = 1080, 1920
    # Hintergrund: Bild gefuellt + unscharf; Vordergrund: volle Breite, mittig
    vf = (f"[0:v]split=2[bg][fg];"
          f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"boxblur=20:2,eq=brightness=-0.08[bgb];"
          f"[fg]scale={W}:-2[fgs];"
          f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2[v0]")
    last = "v0"
    font = font_path()
    hook = (clip.get("hook") or "").strip()
    if hook and font:
        txtfile = os.path.join(workdir, f"hook_{clip['id']}.txt")
        with open(txtfile, "w", encoding="utf-8") as f:
            f.write(wrap(hook))
        dur = f":enable='lte(t,{hook_secs})'" if hook_secs > 0 else ""
        vf += (f";[{last}]drawtext=fontfile='{font}':textfile='{txtfile}':"
               f"fontsize=68:fontcolor=white:line_spacing=12:"
               f"box=1:boxcolor=black@0.65:boxborderw=28:"
               f"x=(w-text_w)/2:y=h*0.13{dur}[v1]")
        last = "v1"
    if cues:
        local = [(max(0, s - start), min(length, e - start), t)
                 for s, e, t in cues if e > start and s < end]
        if local:
            srt = os.path.join(workdir, f"subs_{clip['id']}.srt")
            write_srt(local, srt)
            style = ("FontName=DejaVu Sans,Bold=1,FontSize=13,PrimaryColour=&H00FFFFFF,"
                     "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
                     "Alignment=2,MarginV=70")
            vf += (f";[{last}]subtitles='{srt}':original_size={W}x{H}:"
                   f"force_style='{style}'[v2]")
            last = "v2"
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start}", "-t", f"{length}", "-i", video,
           "-filter_complex", vf, "-map", f"[{last}]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
           "-r", "30", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True)


def slug(text, fallback):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40]
    return s or fallback


def cmd_render(args, data=None):
    if data is None:
        with open(args.clips, encoding="utf-8") as f:
            data = json.load(f)
    video = args.video or data["video"]
    cues = parse_srt(args.srt)
    os.makedirs(args.dir, exist_ok=True)
    workdir = os.path.join(args.dir, ".work")
    os.makedirs(workdir, exist_ok=True)
    only = set(args.only or [])
    lines = ["# Clips\n"]
    for c in data["clips"]:
        if only and c["id"] not in only:
            continue
        name = f"clip{c['id']:02d}-{slug(c.get('title') or c.get('hook'), c['timestamp'].replace(':', ''))}.mp4"
        out = os.path.join(args.dir, name)
        print(f"Rendere #{c['id']} ({c['timestamp']}) -> {out}")
        render_clip(video, c, out, cues, args.hook_secs, workdir)
        lines.append(f"## {name}\n- Quelle: {c['timestamp']} ({c['end'] - c['start']:.0f}s)\n"
                     f"- Hook: {c.get('hook') or '-'}\n- Titel: {c.get('title') or '-'}\n"
                     f"- Beschreibung: {c.get('caption') or '-'}\n")
    with open(os.path.join(args.dir, "CLIPS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    shutil.rmtree(workdir, ignore_errors=True)
    print(f"Fertig. Uebersicht: {os.path.join(args.dir, 'CLIPS.md')}")


# ---------------------------------------------------------------- extras
def cmd_fetch(args):
    need("yt-dlp")
    subprocess.run(["yt-dlp", "-f", "bv*[height<=1080]+ba/b[height<=1080]",
                    "--merge-output-format", "mp4", "-o", args.out]
                   + (["--download-sections", f"*{args.section}"] if args.section else [])
                   + [args.url], check=True)


def cmd_transcribe(args):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die("faster-whisper fehlt: pip install faster-whisper")
    model = WhisperModel(args.model, device="auto", compute_type="int8")
    segments, info = model.transcribe(args.video, language=args.lang, vad_filter=True)
    cues = []
    for seg in segments:
        cues.append((seg.start, seg.end, seg.text.strip()))
        print(f"\r{fmt_ts(seg.end)}", end="", flush=True)
    write_srt(cues, args.out)
    print(f"\nTranskript ({info.language}) -> {args.out}")


def main():
    need("ffmpeg")
    need("ffprobe")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Video/VOD laden (yt-dlp)")
    f.add_argument("url")
    f.add_argument("-o", "--out", default="vod.mp4")
    f.add_argument("--section", help="nur Ausschnitt, z.B. 1:20:00-1:50:00")

    t = sub.add_parser("transcribe", help="Untertitel erzeugen (faster-whisper)")
    t.add_argument("video")
    t.add_argument("-o", "--out", default="transcript.srt")
    t.add_argument("--model", default="small")
    t.add_argument("--lang", default=None, help="z.B. de oder en (sonst automatisch)")

    def common(sp):
        sp.add_argument("--srt", help="Transkript (.srt) fuer Untertitel + Hype-Woerter")
    for name in ("analyze", "auto"):
        a = sub.add_parser(name, help="Highlights finden" + (" + rendern" if name == "auto" else ""))
        a.add_argument("video")
        common(a)
        a.add_argument("--chat", help="Chat-Log: eine Zeile pro Nachricht, Zeit in Spalte 1")
        a.add_argument("-n", type=int, default=5, help="Anzahl Clips")
        a.add_argument("--length", type=float, default=30, help="Clip-Laenge in s")
        a.add_argument("--lead", type=float, default=12, help="Sekunden vor dem Peak starten")
        a.add_argument("-o", "--out", default="clips.json")
        if name == "auto":
            a.add_argument("-d", "--dir", default="out")
            a.add_argument("--hook-secs", type=float, default=0)
            a.set_defaults(only=None)

    r = sub.add_parser("render", help="Clips aus clips.json rendern")
    r.add_argument("video", nargs="?", help="sonst Pfad aus clips.json")
    r.add_argument("clips")
    common(r)
    r.add_argument("-d", "--dir", default="out")
    r.add_argument("--hook-secs", type=float, default=0,
                   help="Hook nur die ersten N s zeigen (0 = ganzer Clip)")
    r.add_argument("--only", type=int, nargs="*", help="nur diese Clip-IDs")

    args = p.parse_args()
    if args.cmd == "fetch":
        cmd_fetch(args)
    elif args.cmd == "transcribe":
        cmd_transcribe(args)
    elif args.cmd == "analyze":
        cmd_analyze(args)
    elif args.cmd == "render":
        cmd_render(args)
    elif args.cmd == "auto":
        data = cmd_analyze(args)
        cmd_render(args, data)


if __name__ == "__main__":
    main()
