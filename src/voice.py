"""Vector Home Voice Pipeline — STT → router → parser → HA → TTS.

Offline-capable voice commands for smart home.
STT: Whisper tiny (faster-whisper, ~75MB)
TTS: edge-tts (online) or piper (offline, ~20MB per voice)
"""
import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
sys.path.insert(0, str(Path(__file__).resolve().parent))

from router import HomeRouter
from parser import HomeParser
from ha_bridge import HABridge, call_ha_sync
from pipeline import process

# ── Piper TTS config ────────────────────────────────────────────────
PIPER_VOICES_DIR = Path(__file__).resolve().parent.parent / "models" / "voices"


def _check_stt_available() -> bool:
    """Check if faster-whisper is available."""
    try:
        from faster_whisper import WhisperModel
        return True
    except ImportError:
        return False


def _check_tts_available() -> bool:
    """Check if edge-tts or piper is available."""
    try:
        import edge_tts
        return True
    except ImportError:
        pass
    # Check piper binary
    try:
        result = subprocess.run(["piper", "--help"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class VoicePipeline:
    """STT → Router → Parser → HA → TTS pipeline."""

    def __init__(self, stt_model: str = "tiny", stt_device: str = "cpu",
                 stt_compute: str = "int8",
                 tts_engine: str = "edge-tts",
                 tts_voice: str = "en-US-AriaNeural",
                 ha_url: str = None, ha_token: str = "", ha_dry_run: bool = True):
        self.stt_model_name = stt_model
        self.stt_device = stt_device
        self.stt_compute = stt_compute
        self.tts_engine = tts_engine
        self.tts_voice = tts_voice
        self._stt_model = None
        self._router = HomeRouter()
        self._parser = HomeParser(verbose=False)
        self._ha = HABridge(
            url=ha_url or os.environ.get("HA_URL", "http://homeassistant.local:8123"),
            token=ha_token or os.environ.get("HA_TOKEN", ""),
            dry_run=ha_dry_run,
        )

    def _load_stt(self):
        """Lazy-load Whisper model."""
        if self._stt_model is None:
            try:
                from faster_whisper import WhisperModel
                self._stt_model = WhisperModel(
                    self.stt_model_name,
                    device=self.stt_device,
                    compute_type=self.stt_compute,
                )
            except ImportError:
                raise ImportError(
                    "faster-whisper not installed. "
                    "Install with: pip install faster-whisper"
                )
        return self._stt_model

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (wav, mp3, flac, etc.)

        Returns:
            Transcribed text (lowercased, stripped).
        """
        model = self._load_stt()
        segments, info = model.transcribe(audio_path, beam_size=1)
        text = " ".join(seg.text for seg in segments).strip()
        return text

    def _format_response(self, result: dict, lang: str = "auto") -> str:
        """Format HA result as natural language response.

        Args:
            result: Pipeline process() result dict.
            lang: Response language — "auto" (detect from args), "ru", "en".

        Returns:
            Human-readable response string.
        """
        tool = result.get("tool_name", "")
        args = result.get("arguments", {})
        ha_result = result.get("ha_result", {})

        if result.get("error"):
            return f"Не удалось обработать: {result['error']}" if lang == "ru" else f"Sorry, I couldn't process that: {result['error']}"

        # Auto-detect language from argument values
        if lang == "auto":
            has_cyrillic = any(
                any('\u0400' <= c <= '\u04FF' for c in str(v))
                for v in args.values()
            )
            lang = "ru" if has_cyrillic else "en"

        if lang == "ru":
            return self._format_response_ru(tool, args, ha_result)
        return self._format_response_en(tool, args, ha_result)

    @staticmethod
    def _format_response_ru(tool: str, args: dict, ha_result: dict) -> str:
        """Format response in Russian."""
        room = args.get("room", "комнате")
        door = args.get("door", "двери")
        scene = args.get("scene", "")
        song = args.get("song", "музыку")

        if tool == "turn_on_light":
            return f"Включаю свет в {room}."
        elif tool == "turn_off_light":
            return f"Выключаю свет в {room}."
        elif tool == "set_temperature":
            temp = args.get("temperature_c", "?")
            return f"Устанавливаю {temp}°C в {room}."
        elif tool == "query_temperature":
            state = ha_result.get("state") if ha_result else None
            if state:
                return f"Температура в {room}: {state}°C."
            return f"Проверяю температуру в {room}."
        elif tool == "lock_door":
            return f"Закрываю {door}."
        elif tool == "unlock_door":
            return f"Открываю {door}."
        elif tool == "play_music":
            return f"Включаю {song} в {room}."
        elif tool == "stop_music":
            return f"Останавливаю музыку в {room}."
        elif tool == "set_alarm":
            return f"Будильник установлен на {args.get('time', '?')}."
        elif tool == "cancel_alarm":
            return "Будильник отменён."
        elif tool == "activate_scene":
            return f"Активирую сцену «{scene}»."
        elif tool == "vacuum_start":
            return f"Запускаю пылесос в {room}."
        return "Готово."

    @staticmethod
    def _format_response_en(tool: str, args: dict, ha_result: dict) -> str:
        """Format response in English."""
        room = args.get("room", "the room")
        door = args.get("door", "the door")
        scene = args.get("scene", "the scene")
        song = args.get("song", "music")

        if tool == "turn_on_light":
            return f"Turning on the lights in {room}."
        elif tool == "turn_off_light":
            return f"Turning off the lights in {room}."
        elif tool == "set_temperature":
            temp = args.get("temperature_c", "?")
            return f"Setting {room} to {temp} degrees."
        elif tool == "query_temperature":
            state = ha_result.get("state") if ha_result else None
            if state:
                return f"The temperature in {room} is {state} degrees."
            return f"Checking the temperature in {room}."
        elif tool == "lock_door":
            return f"Locking {door}."
        elif tool == "unlock_door":
            return f"Unlocking {door}."
        elif tool == "play_music":
            return f"Playing {song} in {room}."
        elif tool == "stop_music":
            return f"Stopping music in {room}."
        elif tool == "set_alarm":
            return f"Alarm set for {args.get('time', '?')}."
        elif tool == "cancel_alarm":
            return "Alarm cancelled."
        elif tool == "activate_scene":
            return f"Activating {scene} scene."
        elif tool == "vacuum_start":
            return f"Starting vacuum in {room}."
        return "Done."

    def _resolve_piper_model(self) -> str:
        """Resolve piper voice model path.

        If tts_voice is an absolute path containing '/', use it as-is.
        Otherwise resolve against PIPER_VOICES_DIR with auto language
        detection: ru-* → ru_RU-dmitri-medium, everything else → en_US-lessac-medium.
        """
        # If it looks like a full path, use directly
        if "/" in self.tts_voice or self.tts_voice.endswith(".onnx"):
            voice = self.tts_voice
        else:
            # Auto-select based on language prefix
            if self.tts_voice.startswith("ru-") or self.tts_voice.startswith("ru_"):
                voice = "ru_RU-dmitri-medium.onnx"
            else:
                voice = "en_US-lessac-medium.onnx"

        # Resolve against PIPER_VOICES_DIR if not absolute
        if not Path(voice).is_absolute():
            voice = str(PIPER_VOICES_DIR / voice)

        return voice

    def speak(self, text: str, output_path: str = None) -> Optional[str]:
        """Convert text to speech.

        Args:
            text: Text to speak.
            output_path: Optional output file path. If None, creates a temp file.

        Returns:
            Path to audio file, or None if played directly.
        """
        if self.tts_engine == "piper":
            # piper outputs WAV, use .wav extension
            if output_path is None:
                output_path = tempfile.mktemp(suffix=".wav")
            return self._speak_piper(text, output_path)
        elif self.tts_engine == "edge-tts":
            if output_path is None:
                output_path = tempfile.mktemp(suffix=".mp3")
            return self._speak_edge_tts(text, output_path)
        else:
            raise ValueError(f"Unknown TTS engine: {self.tts_engine}")

    def _speak_edge_tts(self, text: str, output_path: str) -> str:
        """Generate speech using edge-tts (online, Microsoft voices)."""
        import asyncio

        async def _generate():
            import edge_tts
            communicate = edge_tts.Communicate(text, self.tts_voice)
            await communicate.save(output_path)

        asyncio.run(_generate())

        # Try to play
        self._play_audio(output_path)
        return output_path

    def _speak_piper(self, text: str, output_path: str) -> str:
        """Generate speech using piper (offline, ~20MB per voice)."""
        model_path = self._resolve_piper_model()

        result = subprocess.run(
            ["piper", "--model", model_path, "--output_file", output_path],
            input=text.encode(),
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Piper failed: {result.stderr.decode()}")

        self._play_audio(output_path)
        return output_path

    @staticmethod
    def _play_audio(audio_path: str):
        """Play audio file using system player."""
        for player in ["paplay", "aplay", "ffplay", "mpv"]:
            try:
                subprocess.run(
                    [player, audio_path],
                    capture_output=True,
                    timeout=15,
                )
                return
            except FileNotFoundError:
                continue

    def process_voice(self, audio_path: str, speak_response: bool = True) -> dict:
        """Full voice pipeline: audio → STT → router → parser → HA → (TTS).

        Args:
            audio_path: Path to input audio file.
            speak_response: If True, speak the response aloud.

        Returns:
            Dict with transcription, result, and optional response audio path.
        """
        # STT
        transcription = self.transcribe(audio_path)

        if not transcription:
            return {"error": "Could not transcribe audio", "transcription": ""}

        # Process through pipeline
        result = process(transcription, self._router, self._parser, self._ha)

        # Format response
        response_text = self._format_response(result)

        # TTS (optional)
        response_audio = None
        if speak_response:
            try:
                response_audio = self.speak(response_text)
            except Exception as e:
                result["tts_error"] = str(e)

        result["transcription"] = transcription
        result["response_text"] = response_text
        if response_audio:
            result["response_audio"] = response_audio

        return result


# ── CLI ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Vector Home Voice Pipeline")
    p.add_argument("audio", help="Audio file to process (wav/mp3/flac)")
    p.add_argument("--stt-model", default="tiny", help="Whisper model (tiny/base/small)")
    p.add_argument("--tts", choices=["edge-tts", "piper"], default="edge-tts")
    p.add_argument("--tts-voice", default="en-US-AriaNeural", help="TTS voice name")
    p.add_argument("--no-speak", action="store_true", help="Don't speak response")
    p.add_argument("--dry-run", action="store_true", default=True, help="Don't call HA")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    voice = VoicePipeline(
        stt_model=args.stt_model,
        tts_engine=args.tts,
        tts_voice=args.tts_voice,
        ha_dry_run=args.dry_run,
    )

    print(f"[STT] Transcribing {args.audio}...")
    result = voice.process_voice(args.audio, speak_response=not args.no_speak)

    if result.get("error"):
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"\n  Transcription: {result['transcription']}")
    print(f"  Tool:          {result.get('tool_name', '?')}")
    print(f"  Arguments:     {result.get('arguments', {})}")
    print(f"  Response:      {result.get('response_text', '?')}")
    if result.get("response_audio"):
        print(f"  Audio:         {result['response_audio']}")
    if args.verbose:
        print(f"  Full result:   {json.dumps(result, indent=2, ensure_ascii=False)}")