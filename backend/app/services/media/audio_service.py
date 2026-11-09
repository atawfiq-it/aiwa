import json
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.database.models import GeneratedFile, Task
from app.services.tasks.queue import register_task_handler

logger = logging.getLogger(__name__)


class AudioService:
    @staticmethod
    def is_stt_available() -> bool:
        try:
            import faster_whisper  # noqa: F401

            return True
        except ImportError:
            return False

    @staticmethod
    def is_tts_available() -> bool:
        try:
            import kokoro  # noqa: F401
            import soundfile  # noqa: F401

            return True
        except ImportError:
            return False

    def transcribe_audio(self, audio_path: Path, model_size: str = "base") -> dict[str, Any]:
        if not self.is_stt_available():
            raise RuntimeError(
                "faster-whisper is not installed. Install with: uv sync --extra audio"
            )
        from faster_whisper import WhisperModel

        # Run on CPU with INT8 compute to prevent VRAM competition with LLM
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio_path), beam_size=5)

        transcript_segments = []
        full_text = []

        for seg in segments:
            full_text.append(seg.text)
            transcript_segments.append(
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                }
            )

        return {
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
            "text": " ".join(full_text).strip(),
            "segments": transcript_segments,
        }

    def generate_speech(self, text: str, voice: str = "af_heart") -> Path:
        if not self.is_tts_available():
            raise RuntimeError(
                "kokoro/soundfile is not installed. Install with: uv sync --extra audio"
            )
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline

        logger.info(f"Synthesizing full speech ({len(text)} chars) with voice '{voice}'...")
        pipeline = KPipeline(lang_code="a")
        generator = pipeline(text, voice=voice, speed=1.0)

        out_filename = f"tts_{uuid.uuid4().hex[:8]}.wav"
        out_path = settings.GENERATED_DIR / out_filename

        # Concatenate ALL audio chunks so full multi-paragraph text is synthesized
        audio_chunks = []
        for _, _, audio in generator:
            if audio is not None and len(audio) > 0:
                audio_chunks.append(audio)

        if not audio_chunks:
            raise RuntimeError("Kokoro generated no audio output.")

        full_audio = np.concatenate(audio_chunks)
        sf.write(str(out_path), full_audio, 24000)

        logger.info(
            f"✅ Full audio synthesized ({round(len(full_audio) / 24000, 1)}s): {out_path.name}"
        )
        return out_path


audio_service = AudioService()


@register_task_handler("audio_transcription")
async def handle_audio_transcription(task: Task, db: Session) -> dict[str, Any]:
    params = json.loads(task.parameters)
    file_path = Path(params["file_path"])
    model_size = params.get("model_size", "base")
    return audio_service.transcribe_audio(file_path, model_size=model_size)


@register_task_handler("text_to_speech")
async def handle_tts(task: Task, db: Session) -> dict[str, Any]:
    params = json.loads(task.parameters)
    text = params["text"]
    voice = params.get("voice", "af_heart")

    saved_path = audio_service.generate_speech(text, voice=voice)

    gen_file = GeneratedFile(
        task_id=task.id,
        file_type="audio",
        file_name=saved_path.name,
        file_path=str(saved_path),
        mime_type="audio/wav",
        file_size_bytes=saved_path.stat().st_size,
        prompt=text[:100],
    )
    db.add(gen_file)
    db.commit()

    return {
        "file_id": gen_file.id,
        "file_name": saved_path.name,
        "file_path": str(saved_path),
    }
