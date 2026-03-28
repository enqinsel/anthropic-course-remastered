# Content Agent

Anthropic'in açık kaynak [courses](https://github.com/anthropics/courses) reposundaki Jupyter Notebook dosyalarını senkronize edip `anthropic-tr/src/content/courses/*.json` ve `anthropic-tr/public/course-media/` altına yayına hazır içerik üreten Python scripti.

## Kurulum

```bash
cd scripts/
pip install -r requirements.txt
```

## Kullanım

```bash
# Tüm kursları senkronize et
python content_agent.py

# Tek kurs
python content_agent.py --course api-temelleri

# Önce ne yapacağını göster (dosya değişikliği yok)
python content_agent.py --dry-run

# Repo önbelleğini silip yeniden klonla
python content_agent.py --clean
```

## Kurs Listesi

| `--course` değeri | GitHub klasörü |
|---|---|
| `api-temelleri` | `anthropic_api_fundamentals` |
| `prompt-muhendisligi` | `prompt_engineering_interactive_tutorial` |
| `gercek-dunya-prompting` | `real_world_prompting` |
| `prompt-degerlendirme` | `prompt_evaluations` |
| `arac-kullanimi` | `tool_use` |

## Nasıl Çalışır

1. `_repo_cache/` klasörüne repo klonlanır ya da mevcut önbellek güncellenir
2. Her kurs için doğru notebook kökü seçilir; provider kopyaları ve tekrar eden varyantlar ayıklanır
3. Notebook markdown ve kod hücreleri güvenli biçimde ayrıştırılır; `h1`, code block, inline code ve HTML yapısı korunur
4. Notebook içi görseller ve attachment dosyaları `anthropic-tr/public/course-media/` altına taşınır
5. Mevcut Türkçe JSON yalnızca güvenli seed ve cleanup kaynağı olarak kullanılır; bozuk placeholder ve çevrilmiş HTML etiketleri temizlenir
6. `src/content/courses/[slug].json` dosyaları chapter-level metadata (`source_url`, `summary_tr`, `summary_en`) ile yeniden yazılır

## Notlar

- `_repo_cache/` git'e eklenmez (`.gitignore`)
- Çeviri serbest paket çevirisiyle değil, mevcut Türkçe içerik seed'i + terminoloji cleanup katmanıyla üretilir
- İlk görünür `h1` içerikten çıkarılır; başlık site chrome'unda render edilir
- Görseller artık relative notebook path yerine yerel `/course-media/...` URL'leriyle servis edilir
- Senkronizasyon sonrası `npm run build` ile site yeniden derlenmeli
