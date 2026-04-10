import threading
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel

# Speech-to-text using faster-whisper, runs locally with no API key needed

SAMPLE_RATE = 16000

# Load the base Whisper model on CPU, int8 is more efficient on CPU than float16
model = WhisperModel("base", device="cpu", compute_type="int8")


def record_until_enter() -> str:
    # Press Enter to start recording, press Enter again to stop.
    # Audio is saved to karen_input.wav and transcribed by Whisper.
    print("[ Press ENTER to start speaking ]")
    input()
    print("[ Recording... press ENTER to stop ]")

    frames = []
    stop_flag = threading.Event()

    def callback(indata, _frame_count, _time_info, _status):
        if not stop_flag.is_set():
            frames.append(indata.copy())

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback)
    stream.start()
    input()
    stop_flag.set()
    stream.stop()
    stream.close()

    audio = np.concatenate(frames, axis=0)
    wav.write("lead_input.wav", SAMPLE_RATE, audio)

    segments, _ = model.transcribe("lead_input.wav")
    text = " ".join(s.text for s in segments).strip()
    print(f"YOU: {text}\n")
    return text
