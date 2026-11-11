<div align="center">

# Quran Subtitle Generator

**Kur’an tilavetinden Arapça, Türkçe ve İngilizce SRT altyazılar oluşturun.**

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)
![Version](https://img.shields.io/badge/Version-3.0-248B57)
![Status](https://img.shields.io/badge/Status-Development-orange)

**🇹🇷 Türkçe** · [🇬🇧 English](README_EN.md)

</div>

---

## 📖 Proje hakkında

**Quran Subtitle Generator**, Kur’an-ı Kerim tilaveti için hazırlanmış bir **MP3 → SRT altyazı oluşturma** uygulamasıdır. Ayetin ses kaydını ve kendi seçtiğiniz Arapça metni, Türkçe meali ve İngilizce çeviriyi kullanır.

- **Arapça:** Verilen metnin kelimeleri ses kaydıyla otomatik eşleştirilmeye çalışılır (*forced alignment*). Harekeli metin korunarak zamanlanmış altyazılar hazırlanır.
- **Türkçe ve İngilizce:** Verdiğiniz çeviriler seçtiğiniz yönteme göre parçalara ayrılır. Her parça, ses kaydının **toplam süresinden eşit pay** alır.
- **Çıktı:** Her dil için ayrı `.srt` dosyası; ayrıca kontrol amaçlı `.json` raporu.

Bu uygulama çeviri **yapmaz** ve ayet metnini **üretmez**: metinleri siz sağlarsınız.

## ✨ Özellikler

| Özellik | Açıklama |
|---|---|
| 🔊 Ses dosyaları | MP3, WAV, M4A, FLAC, OGG |
| 🕌 Arapça hizalama | `stable-ts` / Whisper tabanlı ses–metin hizalaması |
| 📝 Arapça bölme | 3 kelime, 4 kelime veya 3–4 kelime |
| 🇹🇷 Türkçe altyazı | Ayrı metin alanı ve bağımsız bölme ayarı |
| 🇬🇧 İngilizce altyazı | Ayrı metin alanı ve bağımsız bölme ayarı |
| ⏱️ Çeviri zamanlaması | Sesin toplam süresine eşit dağıtım |
| 📂 Toplu işlem | Aynı klasördeki MP3 ve ilgili TXT dosyalarını eşleştirme |
| 🎬 Video düzenleme | CapCut'a aktarılabilen standart SRT çıktısı |
| 🔍 Kontrol raporu | Bölümler, ayarlar ve Arapça kelime zamanlarını içeren JSON |

## 🧰 Gereksinimler

- **Windows 10/11**
- **Python 3.11 veya 3.12** (önerilen)
- **FFmpeg + FFprobe** (komut satırında erişilebilir olmalı)
- İlk model indirme ve Python paketlerini kurma için internet bağlantısı

Modelin indirilmesi ve Arapça hizalama işlemi bilgisayarın donanımına bağlı olarak zaman alabilir.

## 🚀 Kurulum (Windows)

Depoyu indirin veya CMD üzerinden klonlayın:

```cmd
git clone https://github.com/KULLANICI_ADIN/quran-subtitle-generator.git
cd quran-subtitle-generator
```

> `KULLANICI_ADIN` kısmını kendi GitHub kullanıcı adınızla değiştirin. Depo gizliyse erişim izniniz ve GitHub kimlik doğrulamanız olmalıdır.

1. `01_KURULUM.bat` dosyasını çalıştırın.
2. FFmpeg/FFprobe yok uyarısı alırsanız `03_FFMPEG_KUR.bat` dosyasını çalıştırın. Ardından terminali kapatıp yeniden açın.
3. Kurulum tamamlanınca `02_BASLAT.bat` dosyasını çalıştırın.

FFmpeg'i CMD üzerinden kurmak için alternatif:

```cmd
winget install --id Gyan.FFmpeg -e
```

`ffmpeg -version` ve `ffprobe -version` komutlarıyla kurulumu kontrol edebilirsiniz.

## 🎛️ Kullanım

### Tek ayet

1. MP3 ses dosyasını seçin.
2. **Arapça ayeti** kendi metin alanına yapıştırın.
3. **Türkçe meal** ve **İngilizce çeviri** metinlerini ilgili alanlara yapıştırın.
4. Arapça için 3, 4 veya 3–4 kelimelik gösterimi seçin.
5. Türkçe ve İngilizce için farklı bölme yöntemleri belirleyin.
6. **SRT Oluştur** işlemini başlatın.
7. Çıktıları CapCut'a ayrı altyazı dosyaları olarak aktarın.

Yalnızca Türkçe/İngilizce altyazı gerekiyorsa **Arapça SRT oluştur** seçeneğini kapatabilirsiniz. Arapça metin boş bırakıldığında bu seçenek kapalı olmalıdır.

### Çeviri bölme seçenekleri

- Metnin tamamı (1 bölüm)
- 2, 3, 4, 5, 6, 8 veya 10 eşit bölüm
- Yaklaşık 3–4, 5–6, 7–8, 9–12 veya 13–16 kelimelik parçalar
- Noktalama işaretlerine göre **cümle cümle**

**Örnek:** 60 saniyelik bir MP3 için **4 eşit bölüm** seçilirse her çeviri altyazısı **15 saniye** gösterilir. Kelimeye veya cümleye göre bölmede de ortaya çıkan blok sayısına göre süreler eşit paylaşılır.

> **Not:** Türkçe ve İngilizce altyazılar, Arapça tilavetin belirli kelimelerine/anlamlarına göre senkronlanmaz. Sadece toplam ses süresine eşit dağıtılır. Bu nedenle videoyu yayınlamadan önce okunabilirliği ve anlam bütünlüğünü kontrol edin.

## 📦 Çıktı dosyaları

`002061.mp3` için örnek:

```text
002061_AR.srt          # Arapça altyazı (sesle hizalanmış)
002061_TR.srt          # Türkçe altyazı (eşit süreli)
002061_EN.srt          # İngilizce altyazı (eşit süreli)
002061_kontrol.json    # İşlem raporu ve zamanlamalar
```

Metni verilmeyen dilin SRT dosyası oluşturulmaz. Aynı adlı çıktı dosyaları yeniden işlemde **üzerine yazılabilir**.

## 📁 Toplu işlem

Dosyaları şu şekilde adlandırın:

```text
ayetler/
├── 002061.mp3
├── 002061.txt        # Arapça ayet
├── 002061.tr.txt     # Türkçe meal
├── 002061.en.txt     # İngilizce çeviri
├── 002062.mp3
├── 002062.txt
├── 002062.tr.txt
└── 002062.en.txt
```

Programdaki **Toplu İşlem** seçeneğinden bu klasörü seçin. Varsayılan çıktı klasörü `SRT_CIKTILAR` olur. Arapça üretimi açıksa her ses dosyası için aynı adlı `.txt` dosyası gereklidir; çeviri dosyaları isteğe bağlıdır.

## 💻 CMD ile kullanım

Sanal ortam kurulduysa:

```cmd
.venv\Scripts\python.exe kuran_mp3_srt.py --mp3 "002061.mp3" --text-file "002061.txt" --tr-file "002061.tr.txt" --en-file "002061.en.txt"
```

Yalnızca Türkçe ve İngilizce, her biri 4 eşit bölüm:

```cmd
.venv\Scripts\python.exe kuran_mp3_srt.py --mp3 "002061.mp3" --no-ar --tr-file "002061.tr.txt" --tr-mode parts:4 --en-file "002061.en.txt" --en-mode parts:4
```

Toplu işlem:

```cmd
.venv\Scripts\python.exe kuran_mp3_srt.py --batch "ayetler"
```

Diğer parametreler için:

```cmd
.venv\Scripts\python.exe kuran_mp3_srt.py --help
```

## ⚠️ Önemli notlar

- **Kur’an metninin doğruluğu:** Arapça ayetleri güvenilir bir kaynaktan alın. Yazım, hareke ve ayet sınırlarını kontrol edin.
- **Hizalama hataları:** Tecvid uzatmaları, duraklamalar ve tekrarlı okumalar nedeniyle Arapça kelime zamanları hatalı olabilir. Yayından önce sesle karşılaştırın.
- **Çeviri bütünlüğü:** Otomatik eşit bölme, cümleleri veya anlam birimlerini uygun olmayan yerlerden ayırabilir. Bölme ayarını buna göre seçin.
- **Gizlilik:** Kişisel MP3/TXT dosyalarını, sanal ortamı, model ağırlıklarını ve üretilen büyük dosyaları depoya eklemeyin. İlk kullanımda model dosyaları dış kaynaktan indirilebilir.
- **Kullanım amacı:** Oluşturulan altyazılar otomatik bir taslaktır; yayın öncesi insan kontrolü önerilir.

## 🔧 Kullanılan teknolojiler

- **Python** — uygulama ve arayüz
- **stable-ts / Whisper** — Arapça ses–metin hizalama
- **FFmpeg / FFprobe** — ses işleme ve süre tespiti
- **SRT** — CapCut ve diğer video editörleri için altyazı biçimi

---

<div align="center">

**Kur’an-ı Kerim'i Arapça tilavet, Türkçe ve İngilizce anlamlarla daha erişilebilir sunmak için geliştirilmiştir.**

[English documentation →](README_EN.md)

</div>
