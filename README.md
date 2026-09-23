# opus-orchestration-3dprint

3D yazıcı için model tasarlatıp bastırmaya yönelik bir [Claude Code](https://claude.com/claude-code) skill seti. Claude istediğin parçayı araştırıyor, kodla modelliyor, kontrol ediyor, diliyor ve Bambu Studio üzerinden Bambu Lab yazıcına gönderiyor. Baskıya basmadan önce her zaman senden onay alıyor.

Arka planda **Claude Pro + ChatGPT Plus** ikilisini verimli kullanan bir orkestrasyon var: Opus yönetiyor, işin büyük kısmını daha ucuz modeller yapıyor.

> **Sadece Claude Code'da çalışır.** Codex, Cursor, Antigravity gibi başka ajanlarda çalışmaz. Ayrıntı için [Uyumluluk](#uyumluluk) bölümüne bak.

## Kurulum

### 1. Yol: Claude kursun (önerilen)

Claude Code'u aç ve şu mesajı sohbete yapıştır:

```text
Şu skill'i benim için kur: https://github.com/alisencerefeturk/opus-orchestration-3dprint
Repoyu ~/opus-orchestration-3dprint klasörüne klonla ve README'deki "Kurulum adımları (Claude için)" bölümünü sırayla uygula.
```

Claude repoyu indirir, skill'leri kurar, eksik programları kontrol eder ve senin elle yapman gerekenleri söyler. Bitince Claude Code'u kapatıp yeniden aç.

### 2. Yol: Claude kuramazsa (elle kurulum)

Terminalde:

```bash
git clone https://github.com/alisencerefeturk/opus-orchestration-3dprint.git ~/opus-orchestration-3dprint
cd ~/opus-orchestration-3dprint
./install.sh
```

Sonra `~/.claude/settings.json` dosyasına şu satırı ekle. Dosyada başka ayarlar varsa onlara dokunma, bunu yanlarına ekle:

```json
"statusLine": { "type": "command", "command": "~/.claude/statusline.sh" }
```

Eksik programlar varsa [Gereksinimler](#gereksinimler) bölümündeki komutlarla kur, sonra Claude Code'u yeniden başlat.

### Kurulum adımları (Claude için)

> Bu bölüm, 1. yoldaki mesajla kurulumu yapan Claude içindir.

1. Repoyu `~/opus-orchestration-3dprint` klasörüne klonla. Klasör zaten varsa ve bu repoysa, içinde `git pull` çalıştır.
2. Repo klasöründe `./install.sh` çalıştır. Script iki skill'i, ajan ayarlarını ve `statusline.sh` dosyasını `~/.claude` altına bağlar. Önceden var olan dosyaları önce yedekler.
3. `~/.claude/settings.json` dosyasına `"statusLine": {"type": "command", "command": "~/.claude/statusline.sh"}` ekle. Mevcut ayarları koru, sadece bunu ekle. Başka bir statusLine zaten tanımlıysa kullanıcıya göster ve değiştirmeden önce sor.
4. Gereksinimleri tek tek kontrol et ve her birinin sonucunu bildir:
   - `python3 --version`
   - `codex --version` ve `codex login status`
   - OpenSCAD: `openscad --version` ya da `/Applications/OpenSCAD.app`
   - Bambu Studio: `/Applications/BambuStudio.app`
   - `python3 -c "import trimesh, scipy, PIL"`

   Eksik olan varsa nasıl kurulacağını söyle, ama kendin kurma.
5. Skill'lerin global kurulduğunu doğrula: `ls -l ~/.claude/skills/3dprint ~/.claude/skills/opus-orchestration`.
6. Kullanıcıya iki şeyi hatırlat:
   - Computer use ayarı proje başına saklanır. Claude'un Bambu Studio'yu kullanacağı her klasörde bir kez `/mcp` → `computer-use` → **Enable** yapılmalı. İlk seferde macOS, Erişilebilirlik (Accessibility) ve Ekran Kaydı (Screen Recording) izni ister.
   - Claude Code yeniden başlatılmalı.
7. Neyin kurulduğunu ve kullanıcının elle yapması gereken her şeyi Türkçe olarak kısaca özetle.

## Nasıl kullanılır

Kurulumdan sonra **herhangi bir klasörde** Claude Code'u açıp şunu yazman yeterli:

```text
/3dprint
```

Claude ne yapmak istediğini sorarak başlar. İsteğini doğrudan komutla birlikte de yazabilirsin:

```text
/3dprint 12 mm havlu çubuğuna takılan bir duvar askısı, PETG
/3dprint Aula F75 Max klavyem için 1-5 tuşlarına CS2 temalı keycap
/3dprint masadaki kulaklık için alta vidalanan bir askı, ölçüleri aşağıda
```

Komutu yazmadan bir baskı işi anlatırsan da Claude skill'i kendisi yükler.

### Claude bir iş gelince ne yapar?

1. **İşi anlar.** Yeni parça mı, dekoratif obje mi, kutu mu, var olan bir dosya mı, başarısız bir baskı mı?
2. **Yazıcını öğrenir.** İlk seferde yazıcı modelini, nozulu, AMS'de hangi yuvada hangi filament olduğunu sorar ve `~/.claude/3d-printer-profile.md` dosyasına kaydeder. Sonraki işlerde sadece "Bu iş şu yazıcı için mi?" diye onaylatır.
3. **Önce araştırır.** Mesajında adı geçen her şey için paralel araştırma ajanları çalıştırır (Luna canlı web aramasıyla, gerekirse Sonnet):
   - parçanın takılacağı cihazın ölçüleri ve standartları (örneğin bir klavyenin tuş profili, sıra yükseklikleri, stem tipi);
   - yazıcının özellikleri;
   - logo veya görseller için resmi vektör kaynakları;
   - vida, mıknatıs gibi standart parçaların ölçüleri;
   - o tür parçaları basarken bilinen sorunlar.

   Her ajan kaynaklarıyla birlikte bir bilgi tablosu getirir.
4. **Sadece gerekeni sorar.** Araştırmanın netleştiremediği şeyleri sorar, örneğin senin kumpasla ölçmen gereken bir ölçüyü.
5. **Özet çıkarır.** Her ölçünün kaynağını gösteren kısa bir `brief.md` yazar: resmi, senin ölçtüğün ya da varsayım. Senden onay alınca modellemeye başlar.
6. **Modeller ve kontrol eder.** Model OpenSCAD koduyla yazılır. Sonra mesh kontrolü yapılır (sızdırmazlık, ölçü, kopuk parça, tablanın altına taşma) ve model birkaç açıdan render edilip gerçek nesneyle karşılaştırılır.
7. **Dilimler ve basar.** Bambu Studio'yu kullanır. **Baskıya basmadan önce** yazıcıyı, plakayı, filamenti, süreyi ve gramajı özetleyip senden onay ister. Yazıcının ağ ve güvenlik ayarlarına asla dokunmaz.

Tüm dosyalar proje klasöründe toplanır (varsayılan `~/3d-prints/<proje-adı>/`): araştırma notları, model kodu, STL/3MF dosyaları, render'lar ve dilimlenmiş dosya.

## Gereksinimler

- Claude Code, **Pro veya Max** planla. Computer use ve kota takibi bunu gerektiriyor.
- **macOS**. Claude Code'da computer use sadece macOS'ta var.
- [Codex CLI](https://github.com/openai/codex), ChatGPT hesabıyla giriş yapılmış. Codex yoksa da çalışır, o zaman işi Claude tarafı yapar.
- Python 3 ve şu paketler: `pip3 install trimesh scipy pillow`
- [OpenSCAD](https://openscad.org): `brew install --cask openscad`
- [Bambu Studio](https://bambulab.com/en/download/studio), yazıcına bağlı ve giriş yapılmış.

## Hangi işi hangi model yapar?

| Model | Nerede | Görevi |
|---|---|---|
| **Opus** | ana Claude Code oturumu | Yönetir, soruları sorar, **3D modeli kendisi yazar**, render'ları kontrol eder, ekranı kullanır. İş dağıtan tek model. |
| **Luna** (`gpt-6-luna`, high) | Codex CLI | Araştırma, toplu işler, varyant üretme. Varsayılan olarak yüksek akıl yürütme ayarında çalışır. |
| **Sol** (`gpt-6-sol`) | Codex CLI | Net bir spesifikasyona göre hassas iş. Opus kotası dolmaya yaklaşınca modellemeyi o devralır. |
| **Astra** (`gpt-6-astra`) | Codex CLI | Sadece çok zor geometri ve akıl yürütme işleri. Kotayı en hızlı o tüketir. |
| **Sonnet** | `sonnet-worker` | Codex'in erişemediği siteler, ikinci görüş, GPT çalışmazsa yedek. CAD'de kullanılmaz. |
| **Haiku** | `haiku-worker` | Sadece yedek. |

Bu dağılımın gerekçeleri ve dayandığı benchmark verileri `skills/opus-orchestration/SKILL.md` dosyasında. Opus'un parçayı kendisi modellemesinin sebebi şu: parçayı devretmek için yazılacak ayrıntılı spesifikasyon işin çoğu demek, ve CAD testlerinde en yüksek skoru Opus alıyor. Görsel maliyeti de hesaba katıldı. `render_sheet.py` dört açıyı tek bir görselde topluyor ve kaliteyi düşürmeden token harcamasını azaltıyor.

## Klasör yapısı

```
skills/3dprint/SKILL.md              3D iş akışı: araştırma → model → kontrol → dilimleme → baskı
skills/3dprint/render_sheet.py       4 açılı önizleme görseli
skills/opus-orchestration/SKILL.md   model yönlendirme kuralları
agents/sonnet-worker.md              Sonnet ajan ayarı
agents/haiku-worker.md               Haiku yedek ajan ayarı
statusline/statusline.sh             Claude kota kullanımını kaydeden status line
install.sh                           her şeyi ~/.claude altına bağlar
```

## Bilinmesi gerekenler

- **Kurulum global.** Skill'ler `~/.claude/skills/` altına bağlanır, `/3dprint` her klasörde çalışır.
- **Klonlanan klasörü silme ya da taşıma.** Kurulan skill'ler o klasöre bağlı. Güncellemek için klasörde `git pull` yapman yeterli.
- **Computer use proje başına açılır.** Claude'un Bambu Studio'yu kullanacağı her yeni klasörde bir kez `/mcp` → `computer-use` → Enable yap. Modelleme, kontroller ve CLI ile dilimleme bu ayar olmadan da çalışır.
- **Orijinal repoyla birlikte kurma.** Bu repo [opus-orchestration](https://github.com/alisencerefeturk/opus-orchestration)'ın 3D baskı sürümü. İkisi aynı skill adını kullanıyor, sadece birini kur.
- Skill dosyalarının içi İngilizce; Claude seninle yine Türkçe konuşur. Zorluk seviyeleri Türkçe: **basit**, **orta**, **zor**.

## Uyumluluk

| Ortam | Çalışır mı? | Neden |
|---|---|---|
| **Claude Code** (CLI, masaüstü, IDE eklentileri) | ✅ | Bunun için yapıldı. |
| **Codex CLI / ChatGPT** | ❌ | Bu yapıda Codex, Claude Code'un çağırdığı bir işçi; ana ortam değil. |
| **Antigravity, Cursor, diğer ajanlar** | ❌ | Gereken Claude Code özellikleri (Agent aracı, skill yükleyici, statusLine, computer use) onlarda yok. |

Model adları, kota eşikleri ve benchmark sayıları Eylül 2026 itibarıyla. Kendi hesabındaki model adlarını `codex` → `/model` ile kontrol edebilirsin.

## Lisans

MIT, [LICENSE](LICENSE) dosyasına bak.
