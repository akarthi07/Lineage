"""
Audio feature extractor — extracts a 36-dimensional feature vector
from a 30-second audio clip using librosa.

Features:
  - Tempo (1 dim)
  - MFCCs / timbre (13 dims)
  - Chroma / harmony (12 dims)
  - Spectral contrast (7 dims)
  - Spectral rolloff (1 dim)
  - Zero crossing rate (1 dim)
  - RMS energy (1 dim)
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import numpy as np
import requests

logger = logging.getLogger(__name__)

FEATURE_DIM = 36


def extract_features(
    source: str,
    duration: float = 30.0,
) -> Optional[np.ndarray]:
    """
    Extract a 36-dim audio feature vector from a file path or URL.

    Parameters
    ----------
    source : local file path or HTTP(S) URL to an audio file.
    duration : seconds of audio to analyze (default 30).

    Returns a normalized 36-dim float32 vector, or None on failure.
    """
    import librosa

    try:
        # Load audio — librosa handles URLs via urllib, but for reliability
        # we download URLs ourselves first
        if source.startswith("http://") or source.startswith("https://"):
            resp = requests.get(source, timeout=15)
            resp.raise_for_status()
            y, sr = librosa.load(io.BytesIO(resp.content), duration=duration, sr=22050)
        else:
            y, sr = librosa.load(source, duration=duration, sr=22050)

        if len(y) < sr * 1:  # less than 1 second of audio
            logger.warning(f"Audio too short: {len(y)} samples from {source[:60]}")
            return None

        features = []

        # 1. Tempo (1 dim)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # tempo can be an array in newer librosa versions
        tempo_val = float(tempo) if np.isscalar(tempo) else float(tempo[0]) if len(tempo) > 0 else 120.0
        features.append(tempo_val / 200.0)  # rough normalization

        # 2. MFCCs — timbre (13 dims)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        features.extend(np.mean(mfccs, axis=1).tolist())

        # 3. Chroma — harmony/key (12 dims)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        features.extend(np.mean(chroma, axis=1).tolist())

        # 4. Spectral contrast (7 dims)
        contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        features.extend(np.mean(contrast, axis=1).tolist())

        # 5. Spectral rolloff (1 dim)
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        features.append(float(np.mean(rolloff)) / sr)  # normalize by sample rate

        # 6. Zero crossing rate (1 dim)
        zcr = librosa.feature.zero_crossing_rate(y)
        features.append(float(np.mean(zcr)))

        # 7. RMS energy (1 dim)
        rms = librosa.feature.rms(y=y)
        features.append(float(np.mean(rms)))

        vec = np.array(features, dtype=np.float32)

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec = vec / norm

        if vec.shape[0] != FEATURE_DIM:
            logger.warning(f"Unexpected feature dim: {vec.shape[0]} (expected {FEATURE_DIM})")

        return vec

    except Exception as exc:
        logger.error(f"Feature extraction failed for {source[:80]}: {exc}")
        return None
