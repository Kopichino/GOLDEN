import numpy as np
from src.voice.audio_bridge import AudioBridge

def test_audio_resampling_ratios():
    # 1 second of 8kHz 16-bit mono audio is 8000 samples * 2 bytes = 16000 bytes
    t = np.linspace(0, 1.0, 8000, endpoint=False)
    sine_wave = (np.sin(2 * np.pi * 440 * t) * 30000).astype(np.int16)
    pcm_8k = sine_wave.tobytes()

    # 1. 8k -> 16k
    pcm_16k = AudioBridge.resample_8k_to_16k(pcm_8k)
    assert len(pcm_16k) == len(pcm_8k) * 2

    # 2. 8k -> 24k
    pcm_24k = AudioBridge.resample_8k_to_24k(pcm_8k)
    assert len(pcm_24k) == len(pcm_8k) * 3

    # 3. 16k -> 8k
    pcm_8k_back = AudioBridge.resample_to_8k(pcm_16k, source_rate=16000)
    assert len(pcm_8k_back) == len(pcm_8k)
