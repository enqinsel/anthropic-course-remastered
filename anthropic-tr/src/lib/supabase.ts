import { createClient } from '@supabase/supabase-js';

// Supabase sadece blog yazıları (posts tablosu) için kullanılır.
// Kurs içerikleri → src/content/courses/*.json
// SSS içerikleri  → src/content/faqs.json

const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Supabase environment değişkenleri eksik!');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
