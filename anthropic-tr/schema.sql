-- Blog yazıları (TEK TABLO — kurslar ve SSS dosya tabanlıdır)
create table if not exists posts (
  id uuid default gen_random_uuid() primary key,
  title text not null,
  slug text unique not null,
  excerpt text,
  content jsonb not null default '[]',
  cover_image text,
  tags text[] default '{}',
  status text default 'draft' check (status in ('draft', 'published')),
  seo_title text,
  seo_description text,
  created_at timestamptz default now(),
  published_at timestamptz
);

alter table posts enable row level security;

-- Herkes yayınlanmış yazıları okuyabilir
create policy "public_read_posts" on posts
  for select using (status = 'published');

-- Admin yazabilir
create policy "admin_write_posts" on posts
  for all using (auth.role() = 'authenticated');

-- Eski tabloları temizlemek için (varsa):
-- drop table if exists courses cascade;
-- drop table if exists faqs cascade;
