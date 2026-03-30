export const prerender = false;

import type { APIRoute } from 'astro';
import { createClient } from '@supabase/supabase-js';

function getAdminClient() {
  return createClient(
    import.meta.env.PUBLIC_SUPABASE_URL,
    import.meta.env.SUPABASE_SERVICE_ROLE_KEY
  );
}

function normalizePostPayload(
  payload: Record<string, unknown>,
  existingPublishedAt: string | null = null
) {
  const normalized = { ...payload };

  if (normalized.status === 'published') {
    normalized.published_at = normalized.published_at ?? existingPublishedAt ?? new Date().toISOString();
  } else if (existingPublishedAt && normalized.published_at === undefined) {
    normalized.published_at = existingPublishedAt;
  }

  return normalized;
}

export const POST: APIRoute = async ({ request }) => {
  const supabase = getAdminClient();
  const body = await request.json();
  const { id: _id, ...payload } = body; // id alanını at (yeni kayıt)
  const normalizedPayload = normalizePostPayload(payload);
  const { data, error } = await supabase.from('posts').insert(normalizedPayload).select().single();
  if (error) return new Response(JSON.stringify({ error: error.message }), { status: 400 });
  return new Response(JSON.stringify(data), { status: 200 });
};

export const PUT: APIRoute = async ({ request }) => {
  const supabase = getAdminClient();
  const body = await request.json();
  const { id, ...rest } = body;
  if (!id) return new Response(JSON.stringify({ error: 'id zorunlu' }), { status: 400 });
  const { data: existing, error: existingError } = await supabase
    .from('posts')
    .select('published_at')
    .eq('id', id)
    .single();

  if (existingError) {
    return new Response(JSON.stringify({ error: existingError.message }), { status: 400 });
  }

  const normalizedPayload = normalizePostPayload(rest, existing?.published_at ?? null);
  const { data, error } = await supabase.from('posts').update(normalizedPayload).eq('id', id).select().single();
  if (error) return new Response(JSON.stringify({ error: error.message }), { status: 400 });
  return new Response(JSON.stringify(data), { status: 200 });
};

export const DELETE: APIRoute = async ({ request }) => {
  const supabase = getAdminClient();
  const body = await request.json();
  const { id } = body;
  if (!id) return new Response(JSON.stringify({ error: 'id zorunlu' }), { status: 400 });
  const { error } = await supabase.from('posts').delete().eq('id', id);
  if (error) return new Response(JSON.stringify({ error: error.message }), { status: 400 });
  return new Response(JSON.stringify({ success: true }), { status: 200 });
};
