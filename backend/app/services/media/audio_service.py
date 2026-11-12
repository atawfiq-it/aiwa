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

    def generate_speech(self, text: str, voice: str = "af_heart", speed: float = 1.0) -> Path:
        if not self.is_tts_available():
            raise RuntimeError(
                "kokoro/soundfile is not installed. Install with: uv sync --extra audio"
            )
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline

        logger.info(
            f"Synthesizing speech ({len(text)} chars, speed {speed}x) with voice '{voice}'..."
        )
        pipeline = KPipeline(lang_code="a")
        generator = pipeline(text, voice=voice, speed=speed)

        out_filename = f"tts_{uuid.uuid4().hex[:8]}.wav"
        out_path = settings.GENERATED_DIR / out_filename

        audio_chunks = []
        for _, _, audio in generator:
            if audio is not None and len(audio) > 0:
                audio_chunks.append(audio)

        if not audio_chunks:
            raise RuntimeError("Kokoro generated no audio output.")

        full_audio = np.concatenate(audio_chunks)
        sf.write(str(out_path), full_audio, 24000)
        return out_path

    def generate_podcast_dialogue(
        self,
        script: list[dict[str, str]],
        silence_ms: int = 350,
        speed: float = 1.0,
    ) -> Path:
        """Synthesizes alternating multi-speaker lines and merges them into a single podcast episode."""
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline

        pipeline = KPipeline(lang_code="a")
        sample_rate = 24000
        silence_samples = int(sample_rate * (silence_ms / 1000.0))
        silence_buffer = np.zeros(silence_samples, dtype=np.float32)

        master_track = []

        for turn in script:
            speaker_voice = turn.get("voice", "am_adam")
            speaker_text = turn.get("text", "").strip()
            if not speaker_text:
                continue

            generator = pipeline(speaker_text, voice=speaker_voice, speed=speed)
            turn_chunks = [
                audio for _, _, audio in generator if audio is not None and len(audio) > 0
            ]

            if turn_chunks:
                turn_audio = np.concatenate(turn_chunks)
                master_track.append(turn_audio)
                master_track.append(silence_buffer)

        if not master_track:
            raise RuntimeError("Podcast script contained no speakable dialogue.")

        final_episode = np.concatenate(master_track)
        out_filename = f"podcast_{uuid.uuid4().hex[:8]}.wav"
        out_path = settings.GENERATED_DIR / out_filename
        sf.write(str(out_path), final_episode, sample_rate)

        logger.info(
            f"🎙️ Podcast generated ({round(len(final_episode) / sample_rate, 1)}s): {out_path.name}"
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
