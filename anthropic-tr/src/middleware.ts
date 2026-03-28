import { defineMiddleware } from 'astro:middleware';
import { createClient } from '@supabase/supabase-js';

export const onRequest = defineMiddleware(async ({ url, cookies, redirect }, next) => {
  if (!url.pathname.startsWith('/admin')) return next();
  if (url.pathname === '/admin/login') return next();

  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const supabaseKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseKey) return redirect('/admin/login');

  const supabase = createClient(supabaseUrl, supabaseKey);

  const accessToken = cookies.get('sb-access-token')?.value;
  const refreshToken = cookies.get('sb-refresh-token')?.value;

  if (!accessToken || !refreshToken) return redirect('/admin/login');

  const { error } = await supabase.auth.setSession({
    access_token: accessToken,
    refresh_token: refreshToken,
  });

  if (error) return redirect('/admin/login');

  return next();
});
