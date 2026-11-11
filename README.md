<div align="center">

# Quran Subtitle Generator

**Create Arabic, Turkish, and English SRT subtitles for Qur'an recitation audio.**

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)
![Version](https://img.shields.io/badge/Version-3.0-248B57)
![Status](https://img.shields.io/badge/Status-Development-orange)

[🇹🇷 Türkçe](README.md) · **🇬🇧 English**

</div>

---

## 📖 About the project

**Quran Subtitle Generator** is an **audio-to-SRT subtitle creation tool** designed for Qur'an recitations. It works with an audio recording and the Arabic verse text, Turkish translation, and English translation **provided by the user**.

- **Arabic:** Attempts to align the supplied Arabic words with the recitation audio using *forced alignment*, while preserving the user's original vocalized text.
- **Turkish and English:** Splits the supplied translations according to independent settings and allocates an **equal share of the total audio duration** to each subtitle block.
- **Outputs:** Separate `.srt` files per language, plus a `.json` report for inspection.

The application does **not** translate or generate the Qur'anic text. You provide the text yourself.

## ✨ Features

| Feature | Description |
|---|---|
| 🔊 Audio support | MP3, WAV, M4A, FLAC, OGG |
| 🕌 Arabic alignment | `stable-ts` / Whisper-based forced alignment |
| 📝 Arabic grouping | 3 words, 4 words, or alternating 3–4 word groups |
| 🇹🇷 Turkish subtitles | Dedicated text input and independent splitting options |
| 🇬🇧 English subtitles | Dedicated text input and independent splitting options |
| ⏱️ Translation timing | Equal-duration blocks across the full audio length |
| 📂 Batch processing | Match audio with corresponding TXT files by filename |
| 🎬 Video editing | Standard SRT output that can be imported into CapCut |
| 🔍 Review report | JSON with settings, subtitle blocks, and Arabic word timing |

## 🧰 Requirements

- **Windows 10/11**
- **Python 3.11 or 3.12** (recommended)
- **FFmpeg + FFprobe** available on the command line
- An internet connection for installing dependencies and downloading the alignment model on first use

Model downloads and Arabic alignment time depend on your hardware.

## 🚀 Installation (Windows)

Download the project or clone it in Command Prompt:

```cmd
git clone https://github.com/YOUR_USERNAME/quran-subtitle-generator.git
cd quran-subtitle-generator
```

> Replace `YOUR_USERNAME` with your GitHub username. If the repository is private, you must authenticate with an account that has access.

1. Run `01_KURULUM.bat` to create the Python environment and install dependencies.
2. If FFmpeg or FFprobe is missing, run `03_FFMPEG_KUR.bat` and restart your terminal.
3. Launch the application with `02_BASLAT.bat`.

Alternatively, install FFmpeg via Command Prompt:

```cmd
winget install --id Gyan.FFmpeg -e
```

Verify installation with `ffmpeg -version` and `ffprobe -version`.

## 🎛️ How to use

### Single verse

1. Select your recitation MP3 file.
2. Paste the **Arabic verse** into its input field.
3. Paste the **Turkish** and **English** translations into their respective fields.
4. Choose 3, 4, or 3–4 words per Arabic subtitle.
5. Select independent splitting modes for Turkish and English.
6. Start subtitle generation.
7. Import the resulting SRT files into CapCut as separate subtitle tracks or assets.

To generate only Turkish and/or English subtitles, disable **Generate Arabic SRT**. This should be disabled if you have not supplied Arabic text.

### Translation splitting modes

- Full text (1 block)
- 2, 3, 4, 5, 6, 8, or 10 equally sized sections
- Approximately 3–4, 5–6, 7–8, 9–12, or 13–16 words per section
- **Sentence-based** splitting using punctuation

**Example:** With a 60-second recording and **4 equal sections**, each translation subtitle remains on screen for **15 seconds**. Word-based and sentence-based modes also distribute the total duration evenly across the blocks they create.

> **Important:** Turkish and English subtitles are **not aligned to specific Arabic words or meanings** in the recitation. They only divide the full recording time equally. Review readability and meaning before publishing.

## 📦 Output files

Example for `002061.mp3`:

```text
002061_AR.srt          # Arabic subtitles (aligned to audio)
002061_TR.srt          # Turkish subtitles (equal timing)
002061_EN.srt          # English subtitles (equal timing)
002061_kontrol.json    # Timing and processing report
```

If a language's text is missing, its SRT file will not be created. Existing output files with the same name **may be overwritten** on subsequent runs.

## 📁 Batch processing

Organize files using matching names:

```text
verses/
├── 002061.mp3
├── 002061.txt        # Arabic verse
├── 002061.tr.txt     # Turkish translation
├── 002061.en.txt     # English translation
├── 002062.mp3
├── 002062.txt
├── 002062.tr.txt
└── 002062.en.txt
```

Choose **Batch Processing** in the application and select this folder. The default output folder is `SRT_CIKTILAR`. If Arabic output is enabled, each recording needs its matching `.txt` file; translation files are optional.

## 💻 Command-line usage

With the virtual environment installed:

```cmd
.venv\Scripts\python.exe kuran_mp3_srt.py --mp3 "002061.mp3" --text-file "002061.txt" --tr-file "002061.tr.txt" --en-file "002061.en.txt"
```

Turkish and English only, four equal sections each:

```cmd
.venv\Scripts\python.exe kuran_mp3_srt.py --mp3 "002061.mp3" --no-ar --tr-file "002061.tr.txt" --tr-mode parts:4 --en-file "002061.en.txt" --en-mode parts:4
```

Batch processing:

```cmd
.venv\Scripts\python.exe kuran_mp3_srt.py --batch "verses"
```

See all available options:

```cmd
.venv\Scripts\python.exe kuran_mp3_srt.py --help
```

## ⚠️ Important notes

- **Text accuracy:** Source Arabic verses from a reliable Qur'an text. Verify diacritics, spelling, and verse boundaries.
- **Alignment accuracy:** Tajweed elongations, pauses, and repeated phrases may lead to inaccurate Arabic word timestamps. Always review against the audio.
- **Translation readability:** Equal-duration splitting may divide sentences or ideas in awkward places. Choose an appropriate mode and review the result.
- **Privacy:** Avoid committing personal recordings, generated subtitles, virtual environments, downloaded models, or private configuration files. The alignment model may be downloaded from an external source on first use.
- **Human review:** Generated subtitles are an automated draft and should be checked before publication.

## 🔧 Technologies

- **Python** — application and desktop interface
- **stable-ts / Whisper** — Arabic forced alignment
- **FFmpeg / FFprobe** — audio processing and duration detection
- **SRT** — subtitle format for CapCut and other video editors

---

<div align="center">

**Built to help present Qur'an recitations alongside Arabic text and Turkish/English translations.**

[← Türkçe dokümantasyon](README.md)

</div>
