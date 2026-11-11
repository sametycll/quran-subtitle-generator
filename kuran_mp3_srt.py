#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kur'an tilaveti MP3/WAV + kullanıcı tarafından verilen Arapça ayet -> zamanlanmış SRT.

Sesi gerçek bir Whisper / stable-ts forced alignment modeliyle eşleştirir.
Orijinal harekeli Arapça metin ekranda değişmeden kalır.
Python 3.11 / 3.12 önerilir. İlk kullanımda model dosyası indirilir.
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import subprocess
from pathlib import Path
import queue
import re
import shutil
import sys
import threading
import traceback
import unicodedata
from dataclasses import asdict, dataclass
from typing import Callable, Optional

APP_NAME = "Kur’an MP3 → Arapça / Türkçe / İngilizce SRT v3"
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg")
ARABIC_ALEF_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا", "ى": "ي"})


@dataclass
class WordTime:
    display: str
    start: float
    end: float
    aligned: str


@dataclass
class Caption:
    start: float
    end: float
    text: str
    word_count: int


def clean_for_alignment(word: str) -> str:
    """Harekeleri kaldırır; kaynak metne *asla* dokunmaz.

    Kur'ânî küçük işaretler, harekeler ve durak sembolleri yalnızca model
    girdisinden çıkartılır. Boşlukla ayrılmış kelime sayısı korunur.
    """
    chars = []
    for ch in unicodedata.normalize("NFKD", word):
        # Osmanlı/Uthmânî imlâdaki küçük elif bazı sözcüklerde güncel
        # yazımda açık elife karşılık gelir: وَٰحِد -> واحد, يَٰمُوسَى -> ياموسى.
        # Diğer küçük elifler atılır (هَٰذَا -> هذا gibi).
        if ch == "\u0670":
            if chars and chars[-1] in ("و", "ي"):
                chars.append("ا")
            continue
        category = unicodedata.category(ch)
        if category.startswith("M") or category.startswith("P") or category in ("Cf", "Sk"):
            continue
        if ch == "ـ" or ch.isspace():
            continue
        # Aynı kelimeye bağlı ayet/durak işaretleri (harf değil) atılır.
        if category.startswith("L") or category.startswith("N"):
            chars.append(ch)
    return "".join(chars).translate(ARABIC_ALEF_MAP)


def parse_verse_words(text: str) -> tuple[list[str], list[str]]:
    # BOM / yönlendirme işaretleri temizlenir; ayet metni ekranda aynen korunur.
    text = text.replace("\ufeff", "").replace("\u200e", "").replace("\u200f", "")
    words = text.split()
    if not words:
        raise ValueError("Arapça ayet metni boş.")
    normalized = [clean_for_alignment(w) for w in words]
    empty = [str(i + 1) for i, w in enumerate(normalized) if not w]
    if empty:
        raise ValueError("Yalnızca işaret içeren kelime(ler) tespit edildi: " + ", ".join(empty) + ". Metindeki bağımsız ayet/durak simgelerini kaldırın.")
    # Doğru model dilini desteklemeyen yanlış metinleri erkenden reddet.
    if not any("\u0600" <= c <= "\u06ff" for w in normalized for c in w):
        raise ValueError("Metinde Arapça harf bulunamadı.")
    return words, normalized


def _timestamp(sec: float) -> str:
    ms = max(0, int(round(sec * 1000)))
    hour, ms = divmod(ms, 3_600_000)
    minute, ms = divmod(ms, 60_000)
    second, ms = divmod(ms, 1000)
    return f"{hour:02d}:{minute:02d}:{second:02d},{ms:03d}"


def render_srt(captions: list[Caption]) -> str:
    blocks = []
    for i, cap in enumerate(captions, 1):
        if cap.end <= cap.start:
            raise ValueError(f"{i}. altyazı için geçersiz süre: {cap.start} -> {cap.end}")
        blocks.append(f"{i}\n{_timestamp(cap.start)} --> {_timestamp(cap.end)}\n{cap.text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def extract_aligned(result, expected: list[str]) -> tuple[list[tuple[float, float, str]], list[str]]:
    """Stable-ts kelimelerini kaynak kelimelerle güvenli biçimde eşleştirir.

    Sayıları aynı değilse yalnızca tüm normalleştirilmiş harf dizisi *bire bir*
    eşleşiyorsa kelime zamanlarını aktarır; rastgele/eşit süre dağıtmaz.
    """
    source_words = []
    for seg in result.segments:
        for item in (getattr(seg, "words", None) or []):
            text = str(getattr(item, "word", ""))
            normalized = clean_for_alignment(text)
            if not normalized:
                continue
            start = float(getattr(item, "start"))
            end = float(getattr(item, "end"))
            source_words.append((start, end, normalized))
    if not source_words:
        raise ValueError("Model sesle eşleşmiş kelime zamanları üretmedi. MP3 ve ayet metnini kontrol edin.")

    warnings = []
    target_joined = "".join(expected)
    actual_joined = "".join(word[2] for word in source_words)
    # Daha küçük sözcük eşleşmeleri de kabul edilir, ancak metin aynı olmalıdır.
    if target_joined != actual_joined:
        score = difflib.SequenceMatcher(None, target_joined, actual_joined).ratio()
        raise ValueError(
            "Modelin hizaladığı Arapça metin verilen ayetle uyuşmadı "
            f"(benzerlik %{score * 100:.1f}; model kelime sayısı {len(source_words)}, "
            f"metin kelime sayısı {len(expected)}). Yanlış MP3, fazladan okunan "
            "besmele/istiâze veya eksik kelime olabilir. Güvenilir zamanlar "
            "olmadığı için tahminî SRT oluşturulmadı."
        )

    # Harf pozisyonlarına göre kaynak word-timing aralıklarının hangi orijinal
    # kelimeye ait olduğunu çözer; model bir sözcüğü bölerse de çalışır.
    timed_spans = []
    pos = 0
    for start, end, tok in source_words:
        timed_spans.append((pos, pos + len(tok), start, end))
        pos += len(tok)

    mapped = []
    pos = 0
    overlaps_detected = False
    for tok in expected:
        lo, hi = pos, pos + len(tok)
        hits = [s for s in timed_spans if s[0] < hi and s[1] > lo]
        if not hits:
            raise ValueError("Bir kelime için ses zamanlaması bulunamadı.")
        mapped.append((min(s[2] for s in hits), max(s[3] for s in hits), tok))
        if any(s[0] < lo or s[1] > hi for s in hits):
            overlaps_detected = True
        pos = hi

    if overlaps_detected:
        warnings.append("Model bazı kelimeleri birleştirmiş/bölmüş olabilir; ilgili kelimelerin sınırlarını dinleyerek kontrol edin.")

    bad = []
    for i, (start, end, _) in enumerate(mapped):
        if not (math.isfinite(start) and math.isfinite(end)) or end <= start + 0.005 or start < -0.01:
            bad.append(i + 1)
        if i and start < mapped[i - 1][0] - 0.3:
            bad.append(i + 1)
    if bad:
        raise ValueError("Model geçersiz/geriye giden kelime zamanlamaları verdi (kelime no: " + ", ".join(map(str, sorted(set(bad)))) + "). Ses ve metin eşleştirmesini kontrol edin.")
    for i, (start, end, _) in enumerate(mapped):
        if end - start > 7:
            warnings.append(f"{i + 1}. kelime çok uzun ({end-start:.1f} sn); uzun tecvid/uzatma veya hizalama hatası olabilir.")
        if i and start < mapped[i-1][1] - 0.18:
            warnings.append(f"{i + 1}. kelime bir öncekiyle örtüşüyor; zamanlamayı dinleyerek kontrol edin.")
    return mapped, warnings


def choose_groups(mapped: list[tuple[float, float, str]], mode: str) -> list[tuple[int, int]]:
    """3 veya 4 kelimelik bölümler seçer. 5 ve altı için istisna olabilir.

    Bölüm sınırında belirgin ses boşluğu varsa onu tercih eder.
    """
    n = len(mapped)
    if n <= 4:
        return [(0, n)]
    if n == 5:
        return [(0, 3), (3, 5)]
    sizes = {3} if mode == "3" else ({4} if mode == "4" else {3, 4})
    # Sabit 3 veya 4 seçildiğinde kalan 1/2 sözcüğü son parçaya bırakmak yerine
    # son iki bloğu gerektiğinde 3–4 arası dengele.
    if mode != "3-4":
        desired = int(mode)
        if n % desired:
            sizes = {3, 4}
    dp = [(float("inf"), None)] * (n + 1)
    dp[n] = (0.0, n)
    for i in range(n - 1, -1, -1):
        best = (float("inf"), None)
        for size in sizes:
            j = i + size
            if j > n or not math.isfinite(dp[j][0]):
                continue
            duration = mapped[j - 1][1] - mapped[i][0]
            if duration < 0:
                continue
            gap = 0.0 if j == n else max(0.0, mapped[j][0] - mapped[j-1][1])
            cost = (0.09 if size == 3 else 0.0) + (abs(duration - 5.7) * 0.04)
            cost -= min(0.75, gap) * 0.36
            cost += dp[j][0]
            if cost < best[0]:
                best = (cost, j)
        dp[i] = best
    if dp[0][1] is None:
        # Çok kısa, sabit 4 kelime modunda istisna gerekebilir.
        for mid in range(3, min(n, 4) + 1):
            if n - mid <= 4:
                return [(0, mid), (mid, n)]
        raise ValueError("Metin 3–4 kelimelik gruplara ayrılamadı.")
    chunks = []
    i = 0
    while i < n:
        j = dp[i][1]
        if j is None or j <= i:
            raise ValueError("Grup oluşturma sırasında beklenmeyen durum.")
        chunks.append((i, j))
        i = j
    return chunks


def make_captions(words: list[str], mapped: list[tuple[float, float, str]], mode: str) -> tuple[list[Caption], list[str]]:
    groups = choose_groups(mapped, mode)
    warnings = []
    caps: list[Caption] = []
    for k, (a, b) in enumerate(groups):
        start = max(0.0, mapped[a][0] - 0.04)
        if caps:
            start = max(start, caps[-1].end)
        last_end = mapped[b - 1][1]
        if k + 1 < len(groups):
            next_start = max(start, mapped[groups[k + 1][0]][0] - 0.02)
            end = min(next_start, last_end + 0.17)
        else:
            end = last_end + 0.15
        if end - start < 0.08:
            raise ValueError(f"{k + 1}. bölüm için süre çok kısa veya çakışıyor. SRT oluşturulmadı.")
        if end - start > 14:
            warnings.append(f"{k + 1}. altyazı {end - start:.1f} saniye sürecek; kulakla kontrol edin.")
        caps.append(Caption(start=round(start, 3), end=round(end, 3),
                            text=" ".join(words[a:b]), word_count=b-a))
    return caps, warnings


def check_prerequisites() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg bulunamadı. Windows Terminal/CMD'de 'winget install --id Gyan.FFmpeg -e' komutuyla yükleyin ve programı yeniden açın.")


def load_alignment_model(name: str, log: Callable[[str], None]):
    try:
        import torch
        import stable_whisper
    except ImportError as e:
        raise RuntimeError("Gerekli Python paketleri kurulu değil. Önce '01_KURULUM.bat' dosyasını çalıştırın. Teknik ayrıntı: " + str(e)) from e
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"Ses hizalama modeli: {name} | İşlemci: {device.upper()}")
    log("İlk kullanımda model dosyası internetten indirilebilir. CPU'da işlem yavaş olabilir.")
    return stable_whisper.load_model(name, device=device)



# --- v3: Türkçe ve İngilizce için eşit zamanlı altyazılar ---
# Arapça bölüm v2'deki gerçek ses/metin zorunlu hizalamasını kullanmaya devam eder.
TRANSLATION_MODES = {
    "Metnin tamamı (1 bölüm)": "parts:1",
    "2 eşit bölüm": "parts:2",
    "3 eşit bölüm": "parts:3",
    "4 eşit bölüm": "parts:4",
    "5 eşit bölüm": "parts:5",
    "6 eşit bölüm": "parts:6",
    "8 eşit bölüm": "parts:8",
    "10 eşit bölüm": "parts:10",
    "3–4 kelimelik": "words:4",
    "5–6 kelimelik": "words:6",
    "7–8 kelimelik": "words:8",
    "9–12 kelimelik": "words:12",
    "13–16 kelimelik": "words:16",
    "Cümle cümle": "sentences",
}
DEFAULT_TRANSLATION_MODE = "7–8 kelimelik"


def probe_audio_duration(audio: Path) -> float:
    """FFprobe ile dosyanın gerçek oynatma süresini öğren; tahmini uzunluk kullanma."""
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError(
            "FFprobe bulunamadı. FFmpeg paketini (03_FFMPEG_KUR.bat) kurup "
            "komut pencerelerini kapatıp yeniden açın."
        )
    try:
        cp = subprocess.run(
            [executable, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
            text=True, capture_output=True, timeout=40, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Ses dosyası süresi okunamadı: {exc}") from exc
    if cp.returncode != 0:
        raise RuntimeError(f"Ses süresi FFprobe ile okunamadı: {cp.stderr.strip()}")
    try:
        duration = float(cp.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("FFprobe geçerli bir süre döndürmedi.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("MP3 dosyası boş veya süresi geçersiz.")
    return duration


def _balanced_word_chunks(words: list[str], number: int) -> list[str]:
    """Kelimelerin sırasını bozmadan olabildiğince dengeli gruplar hazırla."""
    if not words:
        return []
    number = max(1, min(number, len(words)))
    base, extra = divmod(len(words), number)
    lengths = [base + (1 if i < extra else 0) for i in range(number)]
    result = []
    pos = 0
    for length in lengths:
        result.append(" ".join(words[pos:pos + length]))
        pos += length
    assert pos == len(words)
    return result


def split_translation(text: str, selected_mode: str) -> list[str]:
    """Çeviriyi yalnızca metin sınırlarından böl; orijinal içeriği değiştirme."""
    text = text.replace("\ufeff", "").replace("\u200e", "").replace("\u200f", "").strip()
    if not text:
        return []
    mode = TRANSLATION_MODES.get(selected_mode, selected_mode)
    words = text.split()
    if mode.startswith("parts:"):
        count = int(mode.split(":", 1)[1])
        if count <= 0:
            raise ValueError("Bölüm sayısı pozitif olmalıdır.")
        return _balanced_word_chunks(words, count)
    if mode.startswith("words:"):
        max_words = int(mode.split(":", 1)[1])
        if max_words <= 0:
            raise ValueError("Kelime sayısı pozitif olmalıdır.")
        return _balanced_word_chunks(words, math.ceil(len(words) / max_words))
    if mode == "sentences":
        flat = " ".join(words)
        chunks = re.split(r"(?<=[.!?؟])\s+", flat)
        return [c.strip() for c in chunks if c.strip()]
    raise ValueError(f"Desteklenmeyen çeviri bölme yöntemi: {selected_mode}")


def build_translation_captions(text: str, mode: str, duration: float) -> tuple[list[Caption], list[str]]:
    """MP3'ün 00:00–son zaman aralığını tam eşit süreli çeviri bloklarına böl."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Çeviri altyazısı için geçersiz MP3 süresi.")
    chunks = split_translation(text, mode)
    if not chunks:
        return [], []
    n = len(chunks)
    if duration / n < 0.08:
        raise ValueError("MP3 çok kısa veya çok fazla altyazı bölümü var; bölme ayarını küçültün.")
    captions = []
    for i, chunk in enumerate(chunks):
        start = round(i * duration / n, 3)
        end = round((i + 1) * duration / n, 3)
        captions.append(Caption(start, end, chunk, len(chunk.split())))
    warnings = []
    if duration / n < 1.5:
        warnings.append(f"Çeviri bölümleri ortalama {duration/n:.2f} saniye; okumak zor olabilir.")
    if duration / n > 15:
        warnings.append(f"Çeviri bölümleri ortalama {duration/n:.1f} saniye; ekranda uzun kalabilir.")
    return captions, warnings


def process_one(
    audio: Path, arabic: str, turkish: str, english: str, output_dir: Path,
    get_model: Callable[[], object], arabic_mode: str, tr_mode: str, en_mode: str,
    include_arabic: bool, log: Callable[[str], None]
) -> tuple[dict[str, Path], Path, list[str]]:
    """Üç bağımsız SRT ve bir JSON raporu oluştur (metin boşsa o dil atlanır)."""
    if not audio.is_file() or audio.suffix.lower() not in AUDIO_EXTS:
        raise ValueError("Geçerli bir MP3 / WAV / M4A / FLAC / OGG dosyası seçin.")
    arabic, turkish, english = arabic.strip(), turkish.strip(), english.strip()
    if include_arabic and not arabic:
        raise ValueError("Arapça SRT seçildi ancak Arapça ayet alanı boş.")
    if not include_arabic and not turkish and not english:
        raise ValueError("En az bir dilin metnini girin.")

    duration = probe_audio_duration(audio)
    log(f"Ses: {audio.name} | Süre: {duration:.3f} sn")
    captions: dict[str, list[Caption]] = {}
    warnings: list[str] = []
    word_times: list[dict] = []

    if include_arabic:
        check_prerequisites()
        words, normalized = parse_verse_words(arabic)
        log(f"Arapça: {len(words)} kelime; MP3 ile ses/metin hizalaması başlıyor...")
        model = get_model()  # Yalnızca Arapça çıktıda ağır model yüklenir.
        result = model.align(
            str(audio), " ".join(normalized), language="ar", verbose=False,
            max_word_dur=10.0, word_dur_factor=5.0,
        )
        if result is None:
            raise RuntimeError("Arapça MP3 ile ayet hizalaması başarısız.")
        mapped, ar_warnings = extract_aligned(result, normalized)
        ar_captions, ar_cap_warnings = make_captions(words, mapped, arabic_mode)
        # Bazı modeller son sözcüğün sonunu dosya süresinin dışına taşıyabilir.
        if any(c.end > duration + 0.5 for c in ar_captions):
            raise ValueError("Arapça kelime zamanları MP3 süresinin dışına taşıyor. Model sonucunu kontrol edin.")
        captions["AR"] = ar_captions
        word_times = [asdict(WordTime(words[i], st, en, norm)) for i, (st, en, norm) in enumerate(mapped)]
        warnings.extend(["AR: " + item for item in ar_warnings + ar_cap_warnings])
        log(f"Arapça: {len(ar_captions)} bölüm hazır (gerçek ses hizalaması).")

    for code, text_value, mode in (("TR", turkish, tr_mode), ("EN", english, en_mode)):
        if text_value:
            created, warnings_local = build_translation_captions(text_value, mode, duration)
            captions[code] = created
            warnings.extend([f"{code}: " + item for item in warnings_local])
            log(f"{code}: {len(created)} bölüm hazır (MP3 süresine eşit aralıklar).")
        else:
            log(f"{code}: metin boş, SRT oluşturulmayacak.")

    # Başarısız model hizalaması halinde kısmi/yanlış çıktılar üretmemek için
    # yazma işlemleri ancak tüm diller üretildikten sonra başlar.
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for code, parts in captions.items():
        target = output_dir / f"{audio.stem}_{code}.srt"
        target.write_text(render_srt(parts), encoding="utf-8-sig")
        files[code] = target
        log(f"Kaydedildi: {target.name}")

    report = output_dir / f"{audio.stem}_kontrol.json"
    report.write_text(json.dumps({
        "ses_dosyasi": str(audio),
        "toplam_sure_saniye": round(duration, 3),
        "arapca_model": "stable-ts / Whisper forced alignment" if include_arabic else "kullanılmadı",
        "ceviri_zamanlama": "MP3 süresi / altyazı bölüm sayısı (her blok eşit süre)",
        "bolme_ayarlari": {"AR": arabic_mode, "TR": tr_mode, "EN": en_mode},
        "cikti_dosyalari": {k: str(v) for k, v in files.items()},
        "uyarilar": warnings,
        "arapca_kelime_zamanlari": word_times,
        "altyazilar": {k: [asdict(c) for c in parts] for k, parts in captions.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return files, report, warnings


def process_batch(
    folder: Path, output_dir: Path, get_model: Callable[[], object],
    arabic_mode: str, tr_mode: str, en_mode: str, include_arabic: bool,
    log: Callable[[str], None],
) -> tuple[int, list[str]]:
    audios = [p for p in sorted(folder.iterdir()) if p.is_file() and p.suffix.lower() in AUDIO_EXTS]
    if not audios:
        raise ValueError("Seçilen klasörde MP3 / WAV / M4A / FLAC / OGG dosyası yok.")
    succeeded, errors = 0, []
    for i, audio in enumerate(audios, 1):
        log(f"[{i}/{len(audios)}] {audio.name}")
        try:
            ar_path = audio.with_suffix(".txt")
            tr_path = audio.with_name(audio.stem + ".tr.txt")
            en_path = audio.with_name(audio.stem + ".en.txt")
            ar = ar_path.read_text(encoding="utf-8-sig") if ar_path.is_file() else ""
            tr = tr_path.read_text(encoding="utf-8-sig") if tr_path.is_file() else ""
            en = en_path.read_text(encoding="utf-8-sig") if en_path.is_file() else ""
            files, _report, _warnings = process_one(
                audio, ar, tr, en, output_dir, get_model, arabic_mode, tr_mode,
                en_mode, include_arabic, log,
            )
            succeeded += 1
            log("Tamam: " + ", ".join(f.name for f in files.values()))
        except Exception as exc:
            message = f"{audio.name}: {exc}"
            errors.append(message)
            log("HATA: " + message)
    return succeeded, errors


class QuranApp:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("990x920")
        self.root.minsize(810, 740)
        self.audio_var = tk.StringVar()
        self.model_var = tk.StringVar(value="small")
        self.group_var = tk.StringVar(value="3-4")
        self.tr_mode_var = tk.StringVar(value=DEFAULT_TRANSLATION_MODE)
        self.en_mode_var = tk.StringVar(value=DEFAULT_TRANSLATION_MODE)
        self.include_arabic = tk.BooleanVar(value=True)
        self.output_var = tk.StringVar()
        self.status = tk.StringVar(value="Hazır. MP3 ve metinleri seçin.")
        self.events = queue.Queue()
        self.working = False
        self._build()
        self.root.after(150, self._poll)

    def _build(self):
        tk, ttk = self.tk, self.ttk
        outer = ttk.Frame(self.root, padding=15)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Kur'an MP3 → 3 dil için otomatik SRT", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Arapça: sesle hizalı | Türkçe ve İngilizce: MP3 süresi eşit altyazı bölümlerine ayrılır.",
        ).pack(anchor="w", pady=(2, 10))

        audio_frame = ttk.LabelFrame(outer, text="1 · Ses dosyası", padding=9)
        audio_frame.pack(fill="x", pady=(0, 7))
        row = ttk.Frame(audio_frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.audio_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="MP3 seç", command=self._choose_mp3).pack(side="left", padx=(8, 0))

        languages = ttk.LabelFrame(outer, text="2 · Arapça ayet ve çevirileri", padding=9)
        languages.pack(fill="both", expand=True)
        self.ar_text = self._text_section(
            languages, "Arapça ayet (orijinal harekeler korunur)", "ar", 4, ("Traditional Arabic", 17),
            self.group_var, ["3-4", "3", "4"],
        )
        self.tr_text = self._text_section(
            languages, "Türkçe anlam (boş bırakılırsa oluşturulmaz)", "tr", 4,
            ("Segoe UI", 11), self.tr_mode_var, list(TRANSLATION_MODES),
        )
        self.en_text = self._text_section(
            languages, "İngilizce anlam (boş bırakılırsa oluşturulmaz)", "en", 4,
            ("Segoe UI", 11), self.en_mode_var, list(TRANSLATION_MODES),
        )

        opts = ttk.Frame(outer)
        opts.pack(fill="x", pady=(10, 7))
        ttk.Checkbutton(opts, text="Arapça SRT oluştur", variable=self.include_arabic).pack(side="left")
        ttk.Label(opts, text="  Model:").pack(side="left", padx=(12, 1))
        ttk.Combobox(opts, textvariable=self.model_var, state="readonly", width=9,
                     values=("base", "small", "medium")).pack(side="left")
        ttk.Label(opts, text="  (yalnızca Arapça için; small önerilir)").pack(side="left")

        out_frame = ttk.Frame(outer)
        out_frame.pack(fill="x", pady=(3, 8))
        ttk.Label(out_frame, text="Çıktı klasörü:").pack(side="left")
        ttk.Entry(out_frame, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=(8, 6))
        ttk.Button(out_frame, text="Seç", command=self._choose_output).pack(side="left")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(5, 6))
        self.start_btn = ttk.Button(actions, text="MP3 + METİNLER → 3 SRT OLUŞTUR", command=self._start_single)
        self.start_btn.pack(side="left")
        self.batch_btn = ttk.Button(actions, text="TOPLU İŞLEM", command=self._start_batch)
        self.batch_btn.pack(side="left", padx=(9, 0))
        ttk.Label(outer, textvariable=self.status, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.log_box = tk.Text(outer, height=5, wrap="word", font=("Consolas", 9), state="disabled")
        self.log_box.pack(fill="x", pady=(5, 0))
        ttk.Label(
            outer,
            text="Çeviriler eşit aralıklarla gösterilir; Arapça telaffuzuna kelime kelime eşleşmez. "
                 "Özellikle Kur'an yazısını ve zamanlamayı CapCut'ta kontrol edin.",
            wraplength=900,
        ).pack(anchor="w", pady=(7, 0))

    def _text_section(self, parent, title: str, lang: str, height: int, font,
                      group_var, choices):
        tk, ttk = self.tk, self.ttk
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(4, 2))
        ttk.Label(header, text=title, font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(header, text="TXT yükle", command=lambda: self._choose_txt(lang)).pack(side="right")
        ttk.Combobox(header, textvariable=group_var, state="readonly", width=24 if lang != "ar" else 8,
                     values=choices).pack(side="right", padx=(5, 12))
        ttk.Label(header, text="Bölme:").pack(side="right")
        box = tk.Text(parent, height=height, wrap="word", font=font, undo=True,
                      padx=6, pady=5, relief="solid", borderwidth=1)
        box.pack(fill="both", expand=True, pady=(0, 7))
        return box

    def _text_box(self, lang: str):
        return {"ar": self.ar_text, "tr": self.tr_text, "en": self.en_text}[lang]

    def _get_text(self, lang: str) -> str:
        return self._text_box(lang).get("1.0", "end").strip()

    def _load_txt(self, lang: str, filename: Path):
        content = filename.read_text(encoding="utf-8-sig")
        box = self._text_box(lang)
        box.delete("1.0", "end")
        box.insert("1.0", content)

    def _choose_mp3(self):
        from tkinter import filedialog, messagebox
        filename = filedialog.askopenfilename(
            title="Ayet sesini seç", filetypes=[("Ses dosyaları", "*.mp3 *.wav *.m4a *.flac *.ogg"), ("Tüm", "*.*")],
        )
        if not filename:
            return
        audio = Path(filename)
        if self.audio_var.get() and self.audio_var.get() != filename:
            # Eski ayetin çevirileri yanlış ayete karışmasın.
            for lang in ("ar", "tr", "en"):
                self._text_box(lang).delete("1.0", "end")
        self.audio_var.set(filename)
        for lang, txt in (
            ("ar", audio.with_suffix(".txt")),
            ("tr", audio.with_name(audio.stem + ".tr.txt")),
            ("en", audio.with_name(audio.stem + ".en.txt")),
        ):
            if txt.is_file():
                try:
                    self._load_txt(lang, txt)
                except Exception as exc:
                    messagebox.showerror("Metin dosyası okunamadı", f"{txt.name}: {exc}")

    def _choose_txt(self, lang: str):
        from tkinter import filedialog, messagebox
        filename = filedialog.askopenfilename(
            title=f"{lang.upper()} metnini seç", filetypes=[("Metin", "*.txt"), ("Tüm dosyalar", "*.*")],
        )
        if filename:
            try:
                self._load_txt(lang, Path(filename))
            except Exception as exc:
                messagebox.showerror("Metin okunamadı", str(exc))

    def _choose_output(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="SRT dosyalarının kaydedileceği klasör")
        if folder:
            self.output_var.set(folder)

    def _begin(self, job):
        from tkinter import messagebox
        if self.working:
            return
        try:
            # Çeviri SRT'leri için Whisper'a gerek yok, yalnızca FFprobe gerekir.
            if not shutil.which("ffprobe"):
                raise RuntimeError("FFprobe bulunamadı. Önce 03_FFMPEG_KUR.bat dosyasını çalıştırın.")
            if job["include_arabic"]:
                check_prerequisites()
        except Exception as exc:
            messagebox.showerror("Eksik kurulum", str(exc))
            return
        self.working = True
        self.start_btn.configure(state="disabled")
        self.batch_btn.configure(state="disabled")
        self.status.set("İşleniyor...")
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()

    def _base_settings(self):
        return {
            "include_arabic": self.include_arabic.get(),
            "arabic_mode": self.group_var.get(),
            "tr_mode": self.tr_mode_var.get(),
            "en_mode": self.en_mode_var.get(),
            "model": self.model_var.get(),
        }

    def _start_single(self):
        from tkinter import messagebox
        audio = Path(self.audio_var.get().strip())
        ar, tr, en = (self._get_text(lang) for lang in ("ar", "tr", "en"))
        if not audio.is_file():
            messagebox.showwarning("Eksik bilgi", "Önce bir MP3 dosyası seçin.")
            return
        if self.include_arabic.get():
            try:
                parse_verse_words(ar)
            except Exception as exc:
                messagebox.showerror("Arapça ayet hatası", str(exc))
                return
        if not self.include_arabic.get() and not tr and not en:
            messagebox.showwarning("Eksik bilgi", "Türkçe veya İngilizce metin girin, ya da Arapça'yı etkinleştirin.")
            return
        folder = Path(self.output_var.get().strip()) if self.output_var.get().strip() else audio.parent
        self._begin({"kind": "single", "audio": audio, "ar": ar, "tr": tr, "en": en,
                     "out_dir": folder, **self._base_settings()})

    def _start_batch(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="MP3 ve aynı adlı TXT dosyalarının bulunduğu klasör")
        if not folder:
            return
        input_dir = Path(folder)
        output_dir = Path(self.output_var.get().strip()) if self.output_var.get().strip() else input_dir / "SRT_CIKTILAR"
        self._begin({"kind": "batch", "folder": input_dir, "out_dir": output_dir,
                     **self._base_settings()})

    def _run_job(self, job):
        def log(msg):
            self.events.put(("log", str(msg)))
        model_cache = [None]
        def get_model():
            if model_cache[0] is None:
                model_cache[0] = load_alignment_model(job["model"], log)
            return model_cache[0]
        try:
            if job["kind"] == "single":
                files, report, warnings = process_one(
                    job["audio"], job["ar"], job["tr"], job["en"], job["out_dir"],
                    get_model, job["arabic_mode"], job["tr_mode"], job["en_mode"],
                    job["include_arabic"], log,
                )
                result = "Oluşturulan SRT dosyaları:\n" + "\n".join(str(p) for p in files.values())
                result += f"\n\nZamanlama raporu:\n{report}"
                if warnings:
                    result += f"\n\n{len(warnings)} uyarı bulunuyor, rapordan kontrol edin."
            else:
                count, errors = process_batch(
                    job["folder"], job["out_dir"], get_model,
                    job["arabic_mode"], job["tr_mode"], job["en_mode"],
                    job["include_arabic"], log,
                )
                result = f"{count} ayet dosyası işlendi.\nÇıktılar: {job['out_dir']}"
                if errors:
                    result += "\n\nHatalar:\n" + "\n".join(errors[:8])
            self.events.put(("done", result))
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))
            self.events.put(("log", traceback.format_exc()))

    def _poll(self):
        from tkinter import messagebox
        try:
            while True:
                kind, val = self.events.get_nowait()
                if kind == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", val + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif kind in ("done", "error"):
                    self.working = False
                    self.start_btn.configure(state="normal")
                    self.batch_btn.configure(state="normal")
                    self.status.set("Tamamlandı." if kind == "done" else "Hata oluştu.")
                    if kind == "done":
                        messagebox.showinfo("İşlem tamamlandı", val)
                    else:
                        messagebox.showerror("Hata", val)
        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--mp3", type=Path, help="Tek MP3/WAV/M4A/FLAC/OGG")
    parser.add_argument("--batch", type=Path, help="Toplu işlem klasörü")
    parser.add_argument("--text", help="Arapça ayet")
    parser.add_argument("--text-file", type=Path, help="Arapça TXT")
    parser.add_argument("--tr-text", help="Türkçe çeviri")
    parser.add_argument("--tr-file", type=Path, help="Türkçe TXT")
    parser.add_argument("--en-text", help="İngilizce çeviri")
    parser.add_argument("--en-file", type=Path, help="İngilizce TXT")
    parser.add_argument("--no-ar", action="store_true", help="Arapça SRT üretme (model yüklenmez)")
    parser.add_argument("--output", type=Path, help="SRT çıktı klasörü")
    parser.add_argument("--model", choices=("base", "small", "medium"), default="small")
    parser.add_argument("--words", choices=("3", "4", "3-4"), default="3-4", help="Arapça gruplama")
    parser.add_argument("--tr-mode", choices=tuple(TRANSLATION_MODES.values()), default="words:8")
    parser.add_argument("--en-mode", choices=tuple(TRANSLATION_MODES.values()), default="words:8")
    args = parser.parse_args()
    if not args.mp3 and not args.batch:
        if any((args.text, args.text_file, args.tr_text, args.tr_file,
                args.en_text, args.en_file, args.output, args.no_ar)):
            parser.error("--mp3 veya --batch gerekiyor.")
        QuranApp().run()
        return
    if bool(args.mp3) == bool(args.batch):
        parser.error("--mp3 ve --batch birlikte kullanılamaz.")
    if args.text is not None and args.text_file:
        parser.error("--text ve --text-file birlikte kullanılamaz.")
    if args.tr_text is not None and args.tr_file:
        parser.error("--tr-text ve --tr-file birlikte kullanılamaz.")
    if args.en_text is not None and args.en_file:
        parser.error("--en-text ve --en-file birlikte kullanılamaz.")

    def get_text(text_value, filepath):
        return text_value if text_value is not None else (filepath.read_text(encoding="utf-8-sig") if filepath else "")

    if not shutil.which("ffprobe"):
        parser.error("FFprobe bulunamadı; FFmpeg kurun.")
    model_cache = [None]
    def get_model():
        if model_cache[0] is None:
            model_cache[0] = load_alignment_model(args.model, print)
        return model_cache[0]
    folder = args.output
    if folder and folder.suffix.lower() == ".srt":
        # V2'de --output bir .srt dosyasıydı; v3 artık her dil için ayrı dosya üretir.
        folder = folder.parent
    if args.batch:
        if not args.batch.is_dir():
            parser.error(f"Klasör bulunamadı: {args.batch}")
        target = folder or args.batch / "SRT_CIKTILAR"
        count, errors = process_batch(
            args.batch, target, get_model, args.words, args.tr_mode, args.en_mode,
            not args.no_ar, print,
        )
        print(f"\n{count} başarılı ayet, {len(errors)} hatalı. Çıktı: {target}")
        if errors:
            sys.exit(1)
    else:
        ar = get_text(args.text, args.text_file)
        tr = get_text(args.tr_text, args.tr_file)
        en = get_text(args.en_text, args.en_file)
        include_ar = bool(ar.strip()) and not args.no_ar
        if not include_ar and not tr.strip() and not en.strip():
            parser.error("Arapça, Türkçe veya İngilizce metin verin.")
        target = folder or args.mp3.parent
        files, report, warnings = process_one(
            args.mp3, ar, tr, en, target, get_model, args.words, args.tr_mode,
            args.en_mode, include_ar, print,
        )
        print("\nHazır:\n" + "\n".join(str(p) for p in files.values()))
        print("Kontrol dosyası:", report)


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print("HATA:", err, file=sys.stderr)
        sys.exit(1)
