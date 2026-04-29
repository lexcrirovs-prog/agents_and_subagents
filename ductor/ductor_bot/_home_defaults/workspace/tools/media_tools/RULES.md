# Media File Tools

Scripts for processing files received via any transport (Telegram, Matrix, API).

## Common Commands

```bash
python3 tools/media_tools/list_files.py --limit 20
python3 tools/media_tools/list_files.py --type image
python3 tools/media_tools/list_files.py --date 2026-01-15
python3 tools/media_tools/file_info.py --file /absolute/path/to/file
python3 tools/media_tools/read_document.py --file /absolute/path/to/doc.pdf
python3 tools/media_tools/transcribe_audio.py --file /absolute/path/to/audio.ogg
python3 tools/media_tools/process_video.py --file /absolute/path/to/video.mp4
```

## File-Type Routing

- image/photo: inspect directly
- audio/voice: use cached ingress transcript when attached; otherwise transcribe first
- document/PDF: extract text
- video: frames + transcript
- sticker: acknowledge naturally

## Dependencies

- always available: `file_info.py`, `list_files.py`
- PDF parsing: `pypdf`
- YAML listing: `pyyaml`
- audio transcription: local Whisper contour by default, OpenAI only as fallback
- video processing: `ffmpeg`

## Audio Transcription Order

Telegram voice notes may already arrive with a cached fast transcript attached in the prompt.
Prefer that text first; only run `transcribe_audio.py` again if the transcript is missing,
looks wrong, or the user asks for a more exact pass.

For voice and audio files, use this contour in order:

1. local whisper.cpp server on `127.0.0.1:8090`
2. project bridge script `scripts/transcribe-local-whisper.sh`
3. local `whisper` CLI
4. local `whisper-cli`
5. OpenAI Whisper API fallback

## Response UX

After processing, offer concise next actions (optional buttons) when helpful.
