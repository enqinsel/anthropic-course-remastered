import type { Chapter, Course } from './types';

export interface CourseContent extends Course {
  chapters: Chapter[];
}

const ORDER = [
  'api-temelleri',
  'prompt-muhendisligi',
  'gercek-dunya-prompting',
  'prompt-degerlendirme',
  'arac-kullanimi',
];

const courseModules = import.meta.glob<{ default: CourseContent }>('../content/courses/*.json', { eager: true });

function decodeBasicEntities(value: string) {
  return value
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
}

export function stripHtml(value: string | null | undefined) {
  if (!value) return '';
  return decodeBasicEntities(value.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
}

export function getAllCourses() {
  const allCourses = Object.values(courseModules).map((module) => module.default);
  const ordered = ORDER
    .map((slug) => allCourses.find((course) => course.slug === slug))
    .filter(Boolean) as CourseContent[];
  const remaining = allCourses.filter((course) => !ORDER.includes(course.slug));
  return [...ordered, ...remaining];
}

export function getCourseBySlug(slug: string) {
  return getAllCourses().find((course) => course.slug === slug);
}

export function getCourseChapterHref(courseSlug: string, chapterSlug?: string | null) {
  return chapterSlug ? `/kurslar/${courseSlug}/${chapterSlug}` : `/kurslar/${courseSlug}`;
}

export function getCourseLandingHref(course: CourseContent) {
  return getCourseChapterHref(course.slug, course.chapters[0]?.slug);
}

export function getChapterDescription(chapter: Chapter, fallback = '') {
  const fallbackSummary = stripHtml(fallback);
  const summaryTr = stripHtml(chapter.summary_tr);
  const summaryEn = stripHtml(chapter.summary_en);
  const preferred = summaryTr && summaryTr !== summaryEn ? summaryTr : summaryEn || fallbackSummary;
  const summary = stripHtml(preferred);
  if (!summary) return fallbackSummary;
  if (summary === summaryEn && fallbackSummary) return fallbackSummary;
  if (summary.length <= 160) return summary;
  const shortened = summary.slice(0, 157);
  return `${shortened.replace(/\s+\S*$/, '')}...`;
}
