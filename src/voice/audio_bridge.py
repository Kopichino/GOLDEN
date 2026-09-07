import numpy as np
from scipy import signal

class AudioBridge:
    """
    Bridges Exotel Telephony (8kHz PCM 16-bit mono) and Gemini Live (16kHz / 24kHz PCM 16-bit mono).
    """

    @staticmethod
    def pcm16_to_float32(pcm_bytes: bytes) -> np.ndarray:
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        return audio / 32768.0

    @staticmethod
    def float32_to_pcm16(audio: np.ndarray) -> bytes:
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)
        return pcm.tobytes()

    @classmethod
    def resample_8k_to_16k(cls, pcm8k_bytes: bytes) -> bytes:
        if not pcm8k_bytes:
            return b""
        audio = cls.pcm16_to_float32(pcm8k_bytes)
        # upsample 8000 -> 16000 (ratio 2/1)
        resampled = signal.resample_poly(audio, up=2, down=1)
        return cls.float32_to_pcm16(resampled)

    @classmethod
    def resample_8k_to_24k(cls, pcm8k_bytes: bytes) -> bytes:
        if not pcm8k_bytes:
            return b""
        audio = cls.pcm16_to_float32(pcm8k_bytes)
        # upsample 8000 -> 24000 (ratio 3/1)
        resampled = signal.resample_poly(audio, up=3, down=1)
        return cls.float32_to_pcm16(resampled)

    @classmethod
    def resample_to_8k(cls, pcm_bytes: bytes, source_rate: int = 16000) -> bytes:
        if not pcm_bytes:
            return b""
        audio = cls.pcm16_to_float32(pcm_bytes)
        if source_rate == 16000:
            # downsample 16000 -> 8000 (ratio 1/2)
            resampled = signal.resample_poly(audio, up=1, down=2)
        elif source_rate == 24000:
            # downsample 24000 -> 8000 (ratio 1/3)
            resampled = signal.resample_poly(audio, up=1, down=3)
        else:
            raise ValueError(f"Unsupported source rate: {source_rate}")
        return cls.float32_to_pcm16(resampled)
