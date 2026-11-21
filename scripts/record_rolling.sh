#!/usr/bin/env bash
# scripts/record_rolling.sh — Live Stream Rolling Buffer Recorder
# Part of GTA 6 Live & Long-Video Clipping Skill.
#
# Usage:
#   record_rolling.sh <twitch_channel | URL | file/udp/srt/rtmp source> [buffer_dir] [keep_minutes]
#
# Examples:
#   bash scripts/record_rolling.sh streamer_name buffer 45
#   bash scripts/record_rolling.sh "https://www.youtube.com/watch?v=..." buffer 60
#   bash scripts/record_rolling.sh "rtmp://localhost/live/stream" buffer 30

set -uo pipefail

SRC="${1:?Source required (channel name, stream URL, or RTMP/SRT input)}"
BUF="${2:-buffer}"
KEEP="${3:-45}"
SEG=10

mkdir -p "$BUF"

echo "=========================================================="
echo "🔴 Live Rolling Buffer Recorder Starting"
echo "   Source:       $SRC"
echo "   Buffer Dir:   $BUF"
echo "   Keep Window:  $KEEP minutes"
echo "   Segment Size: $SEG seconds (MPEG-TS, copy codec)"
echo "=========================================================="

# Background rolling cleaner: deletes segments older than KEEP minutes
(
  while true; do
    find "$BUF" -name 'seg_*.ts' -mmin "+$KEEP" -delete 2>/dev/null
    sleep 60
  done
) &
CLEAN_PID=$!

trap 'echo "[$(date +%T)] Stopping recorder and cleaning up..."; kill $CLEAN_PID 2>/dev/null; exit 0' SIGINT SIGTERM EXIT

OUTPAT="$BUF/seg_%Y%m%d_%H%M%S.ts"

while true; do
  if [[ "$SRC" =~ ^https?:// || "$SRC" =~ ^[A-Za-z0-9_]+$ ]]; then
    URL="$SRC"
    [[ "$SRC" =~ ^https?:// ]] || URL="https://twitch.tv/$SRC"
    
    echo "[$(date +%T)] Connecting to stream: $URL"
    if command -v streamlink >/dev/null 2>&1; then
      streamlink --stdout "$URL" best 2>>"$BUF/streamlink.log" | \
        ffmpeg -hide_banner -loglevel warning -i pipe:0 -c copy -f segment -segment_time "$SEG" \
          -segment_atclocktime 1 -reset_timestamps 1 -strftime 1 -segment_format mpegts "$OUTPAT"
    elif command -v yt-dlp >/dev/null 2>&1; then
      echo "[$(date +%T)] streamlink not found; falling back to yt-dlp..."
      yt-dlp -o - "$URL" 2>>"$BUF/ytdlp.log" | \
        ffmpeg -hide_banner -loglevel warning -i pipe:0 -c copy -f segment -segment_time "$SEG" \
          -segment_atclocktime 1 -reset_timestamps 1 -strftime 1 -segment_format mpegts "$OUTPAT"
    else
      echo "ERROR: Neither streamlink nor yt-dlp was found in PATH." >&2
      exit 1
    fi
  else
    # Direct capture or local RTMP/SRT feed
    echo "[$(date +%T)] Ingesting direct source: $SRC"
    ffmpeg -hide_banner -loglevel warning -i "$SRC" -c copy -f segment -segment_time "$SEG" \
      -segment_atclocktime 1 -reset_timestamps 1 -strftime 1 -segment_format mpegts "$OUTPAT"
  fi

  echo "[$(date +%T)] Stream source dropped or ended; retrying in 5s (Ctrl+C to stop)..." >&2
  sleep 5
done
