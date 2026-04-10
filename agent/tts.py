import asyncio
import subprocess
import edge_tts

# Text-to-speech for Ava using Microsoft Edge's neural voices, no API key needed


async def _speak(text: str):
    # Generate audio and play it back using ffplay
    communicate = edge_tts.Communicate(text, voice="en-US-JennyNeural")
    await communicate.save("ava_output.mp3")
    subprocess.run(["ffplay", "-nodisp", "-autoexit", "ava_output.mp3"], capture_output=True)


def speak(text: str):
    asyncio.run(_speak(text))
