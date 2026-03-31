export const prerender = false;

import type { APIRoute } from 'astro';
import { createClient } from '@supabase/supabase-js';
import { sortPostsByRecency, type PostListItem } from '../../lib/posts';

export const GET: APIRoute = async () => {
  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'public, max-age=300, s-maxage=300',
  };

  if (!supabaseUrl || !supabaseAnonKey) {
    return new Response(JSON.stringify({ posts: [] }), { status: 200, headers });
  }

  const supabase = createClient(supabaseUrl, supabaseAnonKey);
  const { data, error } = await supabase
    .from('posts')
    .select('title, slug, excerpt, cover_image, tags, published_at, created_at')
    .eq('status', 'published')
    .limit(12);

  if (error) {
    return new Response(JSON.stringify({ posts: [] }), { status: 200, headers });
  }

  const posts = sortPostsByRecency((data ?? []) as PostListItem[]).slice(0, 3);

  return new Response(JSON.stringify({ posts }), { status: 200, headers });
};
