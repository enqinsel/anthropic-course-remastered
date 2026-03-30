export type PostListItem = {
  title: string;
  slug: string;
  excerpt: string | null;
  cover_image: string | null;
  tags: string[] | null;
  published_at: string | null;
  created_at: string;
};

function toTimestamp(value: string | null | undefined) {
  if (!value) return 0;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

export function getPostDisplayDate(post: Pick<PostListItem, 'published_at' | 'created_at'>) {
  return post.published_at ?? post.created_at;
}

export function sortPostsByRecency<T extends Pick<PostListItem, 'published_at' | 'created_at'>>(posts: T[]) {
  return [...posts].sort((a, b) => toTimestamp(getPostDisplayDate(b)) - toTimestamp(getPostDisplayDate(a)));
}
