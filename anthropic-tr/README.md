# Anthropic TR — Claude Eğitim Platformu

Anthropic'in resmi kurs materyallerinin Türkçe versiyonu.

## Teknoloji
- **Frontend:** Astro 6 + Tailwind CSS v4
- **Veritabanı:** Supabase (PostgreSQL) — yalnızca blog yazıları
- **İçerik:** `src/content/courses/*.json` (kurslar) ve `src/content/faqs.json` (SSS)
- **Hosting:** Netlify

## Yerel Geliştirme

### Gereksinimler
- Node.js 22+
- Python 3.10+

### Kurulum

```bash
# Bağımlılıkları yükle
npm install

# .env dosyasını oluştur
cp .env.example .env
# .env dosyasını Supabase bilgileriyle doldur

# Supabase şemasını kur
# schema.sql dosyasını Supabase SQL Editor'da çalıştır

# Geliştirme sunucusunu başlat
npm run dev
```

### İçerik Senkronizasyonu (Content Agent)

```bash
# Ne yapacağını göster (değişiklik yok)
npm run sync:dry

# Tüm kursları çek
npm run sync

# Sadece bir kursu güncelle
cd ..
python scripts/content_agent.py --course prompt-muhendisligi
```

## Deployment

Netlify'a bağla:
1. GitHub reposunu Netlify'a bağla
2. Build command: `npm run build`
3. Publish directory: `dist`
4. Environment variables'ı Netlify panelinden ekle

## Environment Variables

```
PUBLIC_SUPABASE_URL         = https://xxxxx.supabase.co
PUBLIC_SUPABASE_ANON_KEY    = eyJ...
SUPABASE_SERVICE_ROLE_KEY   = eyJ...
ADSENSE_CLIENT_ID           = ca-pub-...
```

## Klasör Yapısı

```
anthropic-tr/
├── src/
│   ├── components/
│   │   ├── layout/      # Header, Footer, BaseLayout
│   │   ├── ui/          # Card
│   │   └── ads/         # AdBanner
│   ├── content/
│   │   ├── courses/     # *.json (content_agent ile doldurulur)
│   │   └── faqs.json
│   ├── pages/
│   │   ├── index.astro
│   │   ├── kurslar/
│   │   ├── blog/
│   │   ├── sss.astro
│   │   └── admin/
│   ├── lib/
│   │   ├── supabase.ts
│   │   └── types.ts
│   └── styles/global.css
├── public/
│   ├── robots.txt
│   └── favicon.svg
├── netlify.toml
├── schema.sql
└── .env.example

scripts/                   # Proje kökünde (anthropic-tr dışında)
├── content_agent.py
└── requirements.txt
```
