# Anthropic TR — 6 Yeni Ozellik Plani

## Context
Proje prod'da calisiyor (Netlify), 5 kurs icerigi cevirildi, blog/SSS/admin calisiyor. Simdi UX ve icerik kalitesini artirmak icin 6 ozellik eklenecek. Siralama bagimliliklara gore: tema toggle > Shiki (cift tema gerektirir) > diger ozellikler > analytics (tum event'leri yakalar).

---

## Faz 1: Dark/Light Tema Toggle

**Degisecek dosyalar:**
- `src/styles/global.css`
- `src/components/layout/BaseLayout.astro`
- `src/components/layout/Header.astro`

**Yaklasim:**
1. `global.css` — `@layer base` icinde `html.light` sektor ekle, tum `--color-*` degiskenlerini light karsiliklariyla override et:
   - site: `#f8f8f6`, surface: `#ffffff`, surface2: `#f0efe8`, border: `#d8d8d0`
   - accent: `#c96442` (ayni), accent-light: `#b8522f` (kontrast icin koyu)
   - base: `#1a1a1a`, muted: `#6b6b65`
2. `global.css` — `body` renglerini hardcoded hex yerine `var(--color-site)` / `var(--color-base)` yap. `code` ve `pre` stillerini de degisken bazli yap.
3. `BaseLayout.astro` — `<head>` icine `is:inline` senkron script ekle (FOWT onlemi):
   - localStorage'dan `theme` oku, yoksa `prefers-color-scheme` kullan
   - `document.documentElement.className = theme` ata
4. `Header.astro` — Gunes/Ay SVG icon toggle butonu ekle (GitHub linkinin yanina). Click handler: class toggle + localStorage kayit.

---

## Faz 2: Kod Kopyala Butonu + Shiki Syntax Highlighting

**Yeni dosya:** `src/lib/shiki.ts`
**Degisecek dosyalar:**
- `src/styles/global.css`
- `src/pages/kurslar/[course]/[chapter].astro`
- `src/pages/blog/[slug].astro`
- `src/components/layout/BaseLayout.astro`

**Yaklasim:**
1. `src/lib/shiki.ts` — Singleton highlighter olustur:
   - `createHighlighter({ themes: ['github-dark','github-light'], langs: ['python','bash','text'] })`
   - `highlightCode(code, lang)` fonksiyonu — `codeToHtml()` cift tema modu (`defaultColor: false`)
   - Shiki zaten Astro'nun transitive dependency'si olarak yuklu (v4.0.2)
2. `global.css` — Shiki cift tema CSS ekle:
   - `html.dark .shiki span { color: var(--shiki-dark) }`
   - `html.light .shiki span { color: var(--shiki-light) }`
   - `pre.shiki` icin border/padding/font stili
3. `[chapter].astro` — Frontmatter'da tum code block'lari `highlightCode()` ile isle, template'de `set:html` kullan. Her code block'u `relative group` wrapper'a sar, icine "Kopyala" butonu ekle.
4. `blog/[slug].astro` — Ayni pattern: code block'lari SSR sirasinda Shiki ile isle.
5. `BaseLayout.astro` — Event delegation ile `.copy-btn` click handler ekle (clipboard API + 1.6s reset). Tum sayfalarda calisir.

**Not:** 1,026 code block (hepsi Python). Build time ~1-5sn ek.

---

## Faz 3: Okuma Suresi + Begen Butonu

**Yeni dosya:** `src/lib/readingTime.ts`
**Degisecek dosyalar:**
- `src/pages/kurslar/[course]/[chapter].astro`
- `src/pages/blog/[slug].astro`

**Yaklasim:**
1. `readingTime.ts` — `calculateReadingTime(blocks: ChapterBlock[])` fonksiyonu. HTML block'lardan `stripHtml()` ile text cikar (mevcut `courseData.ts`'deki fonksiyon), kelime say, 200'e bol.
2. `[chapter].astro` — Baslik alanina "{X} dk okuma" badge'i ekle. Ayrica kalp ikonlu "Begen" butonu ekle.
3. `blog/[slug].astro` — Mevcut okuma suresi zaten var. Sadece "Begen" butonu ekle (paylas butonlarinin yanina).
4. localStorage key: `likes` = slug dizisi (Set olarak). Toggle mantigi: click → has(slug) ? delete : add → icon degistir (bos kalp ♡ / dolu kalp ♥).

---

## Faz 4: Homepage Prerender

**Yeni dosya:** `src/pages/api/recent-posts.ts`
**Degisecek dosyalar:**
- `src/pages/index.astro`

**Yaklasim:**
1. `api/recent-posts.ts` — SSR API endpoint. Supabase'den son 3 yaziyi cek, JSON don. `Cache-Control: max-age=300` header'i ekle.
2. `index.astro` — `prerender: false` → `prerender: true`. Supabase import'larini kaldir. Blog section'i client-side `fetch('/api/recent-posts')` ile yukle. Hero + ogrenme yolu + SSS tamamen statik kalir.
3. Blog yoksa section gizli kalir (graceful degradation).

---

## Faz 5: Sozluk (Glossary) Sayfasi

**Yeni dosyalar:**
- `src/content/glossary.json` (50-100 terim)
- `src/pages/sozluk.astro`

**Degisecek dosyalar:**
- `src/components/layout/Header.astro` (nav'a "Sozluk" ekle)
- `src/components/layout/Footer.astro` (footer'a link ekle)
- `astro.config.mjs` (sitemap priority)

**Yaklasim:**
1. `glossary.json` — Her terim: `{ id, term_en, term_tr, definition_tr, category, related_terms[] }`. Kategoriler: genel-ai, nlp, prompt, mimari, api.
2. `sozluk.astro` — Prerender, alfabe bazli gruplama, arama input'u, kategori filtre butonlari. SSS sayfasiyla ayni UX pattern'i.
3. Header/Footer'a "Sozluk" linki ekle.
4. 50-100 AI/ML terimi doldur: LLM, Transformer, Token, Embedding, Attention, Fine-tuning, RLHF, Constitutional AI, Prompt, System Prompt, Few-shot, CoT, Temperature, Top-k, Top-p, Context Window, Hallucination, RAG, Function Calling, Tool Use, Streaming, vb.

---

## Faz 6: Umami/Plausible Analytics

**Degisecek dosyalar:**
- `src/components/layout/BaseLayout.astro`
- `.env.example`

**Yaklasim:**
1. Env degiskenleri: `ANALYTICS_URL`, `ANALYTICS_SITE_ID`
2. `BaseLayout.astro` — `<head>` icine conditional analytics script. Umami ve Plausible'i otomatik ayirt et.
3. `BaseLayout.astro` — `window.trackEvent(name, data)` global fonksiyon (Umami/Plausible abstraction).
4. Diger sayfalardaki event'lere `trackEvent()` cagrilari ekle:
   - `theme_toggle` (Header.astro)
   - `chapter_complete` ([chapter].astro)
   - `lang_toggle` ([chapter].astro)
   - `like` ([chapter].astro + blog/[slug].astro)
   - `code_copy` (BaseLayout.astro)

---

## Dogrulama

Her faz sonunda:
1. `npm run build` — hatasiz build
2. Sayfada gorsel kontrol (tema, highlight, butonlar)
3. localStorage degerlerinin dogru kaydedildigini kontrol
4. Faz 6 sonunda: `git commit` + `git push`
