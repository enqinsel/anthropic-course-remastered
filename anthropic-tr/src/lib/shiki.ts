import { createHighlighter, type HighlighterGeneric } from 'shiki';

const SUPPORTED_LANGUAGES = ['python', 'bash', 'text', 'javascript', 'typescript', 'json', 'html'] as const;

type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

let highlighterPromise: Promise<HighlighterGeneric<SupportedLanguage, 'github-dark' | 'github-light'>> | null = null;

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizeLanguage(language?: string | null): SupportedLanguage {
  const normalized = (language ?? 'text').trim().toLowerCase();

  if (normalized === 'shell' || normalized === 'sh') return 'bash';
  if (normalized === 'ts' || normalized === 'tsx') return 'typescript';
  if (normalized === 'js' || normalized === 'jsx') return 'javascript';

  return (SUPPORTED_LANGUAGES as readonly string[]).includes(normalized) ? (normalized as SupportedLanguage) : 'text';
}

async function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ['github-dark', 'github-light'],
      langs: [...SUPPORTED_LANGUAGES],
    });
  }

  return highlighterPromise;
}

export async function highlightCode(code: string, language?: string | null) {
  const source = code.replace(/\s+$/, '');

  try {
    const highlighter = await getHighlighter();
    return highlighter.codeToHtml(source, {
      lang: normalizeLanguage(language),
      themes: {
        dark: 'github-dark',
        light: 'github-light',
      },
      defaultColor: false,
    });
  } catch {
    return `<pre class="shiki fallback-code"><code>${escapeHtml(source)}</code></pre>`;
  }
}
