// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import react from '@astrojs/react';
import sitemap from '@astrojs/sitemap';
import netlify from '@astrojs/netlify';

export default defineConfig({
  site: 'https://anthropic-tr.com',
  output: 'server',
  adapter: netlify(),
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [
    react(),
    sitemap({
      filter: (page) => !page.includes('/admin') && !page.includes('/api/'),
      changefreq: 'weekly',
      lastmod: new Date(),
      serialize(item) {
        if (item.url === 'https://anthropic-tr.com/') {
          item.priority = 1.0;
          item.changefreq = 'daily';
        } else if (item.url.includes('/kurslar/')) {
          item.priority = 0.9;
        } else if (item.url.includes('/blog/')) {
          item.priority = 0.8;
        } else if (item.url.includes('/sozluk')) {
          item.priority = 0.75;
        } else if (item.url.includes('/sss')) {
          item.priority = 0.7;
        }
        return item;
      },
    }),
  ],
});
