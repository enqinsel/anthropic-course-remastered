// Course ve FAQ tipleri src/content/ klasöründeki JSON dosyalarından okunur.
// Supabase sadece Post tipi için kullanılır.

// Blog yazısı içerik blokları
export type ContentBlockType =
  | 'paragraph'
  | 'heading'
  | 'image'
  | 'code'
  | 'callout'
  | 'quote'
  | 'video'
  | 'link_card'
  | 'divider';

export interface ContentBlock {
  id: string;
  type: ContentBlockType;
  // paragraph
  text?: string;
  // heading
  level?: 2 | 3;
  // image
  url?: string;
  alt?: string;
  caption?: string;
  // code
  code?: string;
  language?: string;
  // callout
  variant?: 'info' | 'warn' | 'success';
  // quote
  source?: string;
  // video
  videoId?: string;
  // link_card
  href?: string;
  linkTitle?: string;
  linkDescription?: string;
}

export interface Post {
  id: string;
  title: string;
  slug: string;
  excerpt: string | null;
  content: ContentBlock[];
  cover_image: string | null;
  tags: string[];
  status: 'draft' | 'published';
  seo_title: string | null;
  seo_description: string | null;
  created_at: string;
  published_at: string | null;
}

export interface FAQ {
  id: string;
  question: string;
  answer: string;
  category: string;
  order_index: number;
  created_at: string;
}

export interface ChapterBlock {
  type: 'html' | 'code';
  content: string;
}

export interface Chapter {
  slug: string;
  order_index: number;
  title: string;         // İngilizce orijinal
  title_tr: string;      // Türkçe çeviri
  blocks_en: ChapterBlock[];
  blocks_tr: ChapterBlock[];
}

export interface Course {
  id: string;
  course_id: string;
  title_tr: string;
  slug: string;
  description_tr: string | null;
  chapters: Chapter[];
  source_url: string | null;
  last_synced_at: string | null;
  created_at: string;
}
