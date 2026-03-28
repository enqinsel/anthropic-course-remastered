# Content Agent

Anthropic'in açık kaynak [courses](https://github.com/anthropics/courses) reposundaki Jupyter Notebook dosyalarını çekip `anthropic-tr/src/content/courses/*.json` dosyalarına aktaran Python scripti.

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

1. `_repo_cache/` klasörüne `--depth=1` ile repo klonlanır (ilk çalıştırma) ya da `git pull` yapılır
2. Her kurs için ilgili klasördeki `.ipynb` dosyaları sıralanır
3. Her notebook'tan markdown ve kod hücreleri `content_blocks` dizisine aktarılır
4. `src/content/courses/[slug].json` dosyasındaki `chapters` ve `last_synced_at` güncellenir; `title_tr`, `description_tr` gibi çeviri alanlarına dokunulmaz

## Notlar

- `_repo_cache/` git'e eklenmez (`.gitignore`)
- İçerik şimdilik İngilizce aktarılır; Türkçe çeviri sonraki fazda eklenecek
- Senkronizasyon sonrası `npm run build` ile site yeniden derlenmeli
