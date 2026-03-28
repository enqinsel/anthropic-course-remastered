export const prerender = false;

import type { APIRoute } from 'astro';
import { createClient } from '@supabase/supabase-js';

export const GET: APIRoute = async ({ params }) => {
  const supabase = createClient(
    import.meta.env.PUBLIC_SUPABASE_URL,
    import.meta.env.SUPABASE_SERVICE_ROLE_KEY
  );
  const { data, error } = await supabase.from('posts').select('*').eq('id', params.id).single();
  if (error || !data) return new Response('Not found', { status: 404 });
  return new Response(JSON.stringify(data), { status: 200 });
};
