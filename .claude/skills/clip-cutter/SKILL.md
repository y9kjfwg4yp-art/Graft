---
name: clip-cutter
description: Schneidet aus langen Videos oder Stream-VODs (z. B. GTA-Streams) die besten Momente zu fertigen Hochformat-Clips (9:16) fuer YouTube Shorts, TikTok und Instagram Reels, mit Hook-Text und Untertiteln. Verwenden, wenn der Nutzer ein Video, einen VOD-Link oder einen Stream nennt und daraus Clips, Shorts, Reels oder Highlights haben will, oder Hooks und Titel fuer Clips braucht.
---

# Clip-Cutter

Werkzeug: `clipper/clipper.py` (nur ffmpeg ist Pflicht). Arbeitsordner fuer
Videos und Ausgaben: ausserhalb des Repos oder in `clips-work/` (per
.gitignore ausgeschlossen). Videos werden nie committet.

## 0. Rechte pruefen, bevor du schneidest
Frage nach, wenn es unklar ist: Ist das eigenes Material, oder gibt es eine
Erlaubnis (Clipping-Kampagne bzw. Freigabe durch den Streamer)? Ohne Erlaubnis
fremdes Material nicht zum Hochladen vorbereiten. Weise auf Copyright-Strikes
und die YouTube-Regel zu "wiederverwendeten Inhalten" hin. Bei
Kampagnen-Regeln (Laenge, Wasserzeichen, Pflicht-Tags) diese uebernehmen.

## 1. Video besorgen
- Lokale Datei: direkt verwenden.
- Link: `python3 clipper/clipper.py fetch URL -o clips-work/vod.mp4`
  (braucht yt-dlp; bei langen VODs mit `--section 1:20:00-1:50:00` nur einen Teil laden).

## 2. Transkript (stark empfohlen)
`python3 clipper/clipper.py transcribe clips-work/vod.mp4 -o clips-work/vod.srt --lang de`
(braucht faster-whisper). Ohne Transkript gibt es keine Untertitel, und du
kannst die Hooks nur aus dem Bild ableiten. Sag das dem Nutzer.

## 3. Highlights finden
`python3 clipper/clipper.py analyze clips-work/vod.mp4 --srt clips-work/vod.srt -n 8 --length 30 -o clips-work/clips.json`
Signale: Lautstaerke-Spitzen (Schreien, Explosionen), Hype-Woerter im
Transkript und optional ein Chat-Log (`--chat chat.csv`, Zeit in Spalte 1).
Waehle lieber zu viele Kandidaten (`-n 8` bis `-n 12`) und filtere dann.

## 4. Kandidaten pruefen und Hooks schreiben (deine Aufgabe)
Lies `clips.json`. Pro Clip:
1. Nutze das `transcript`. Optional ein Standbild ansehen:
   `ffmpeg -ss <start+peak-offset> -i vod.mp4 -frames:v 1 f.png`
2. Langweilige Clips (nur Gerede ohne Pointe) aus der Liste loeschen.
3. `start` und `end` so anpassen, dass der Clip mit Spannung beginnt und
   direkt nach der Pointe endet. Optimal sind 15 bis 45 s.
4. Ausfuellen:
   - `hook`: max. ca. 8 Woerter, Neugier statt Spoiler, in der Sprache des
     Streams. Muster: "Er hat NICHT damit gerechnet", "Warte auf das Ende…",
     "Das ist der dummste Bankraub in GTA 6", "Wie hat er das ueberlebt?!".
     Keine falschen Versprechen (Clickbait, der nicht eingeloest wird,
     senkt die Watchtime).
   - `title`: Plattform-Titel, darf Emojis enthalten.
   - `caption`: 1 bis 2 Saetze plus 3 bis 5 Hashtags, inklusive Credit fuer
     den Streamer (@name), wenn es fremdes Material ist.

## 5. Rendern
`python3 clipper/clipper.py render clips-work/clips.json --srt clips-work/vod.srt -d clips-work/out --hook-secs 4`
Ergebnis: 1080x1920 MP4s plus `CLIPS.md` mit Hook, Titel und Beschreibung
pro Clip. Ein Standbild pro Clip ansehen und pruefen, dass der Text lesbar
ist. Dann dem Nutzer die Dateien schicken.

## Grenzen (ehrlich kommunizieren)
- Kein automatisches Hochladen und kein dauerhaftes Live-Ueberwachen von
  Streamern. Dafuer braucht es einen dauerhaft laufenden Rechner.
- Monetarisierung (AdSense, Kampagnen-Auszahlungen) entscheiden die
  Plattformen, nicht dieses Werkzeug.
