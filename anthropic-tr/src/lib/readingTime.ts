import { stripHtml } from './courseData';
import type { ChapterBlock, ContentBlock } from './types';

function countWords(text: string) {
  return text
    .split(/\s+/)
    .map((word) => word.trim())
    .filter(Boolean).length;
}

function minutesFromWordCount(words: number) {
  return Math.max(1, Math.round(words / 200) || 1);
}

export function calculateReadingTime(blocks: ChapterBlock[]) {
  const words = blocks
    .filter((block) => block.type === 'html')
    .reduce((total, block) => total + countWords(stripHtml(block.content)), 0);

  return minutesFromWordCount(words);
}

export function calculateContentReadingTime(blocks: ContentBlock[]) {
  const words = blocks.reduce((total, block) => {
    if (block.type === 'paragraph' || block.type === 'heading' || block.type === 'callout' || block.type === 'quote') {
      return total + countWords(block.text ?? '');
    }

    if (block.type === 'link_card') {
      return total + countWords(`${block.linkTitle ?? ''} ${block.linkDescription ?? ''}`);
    }

    return total;
  }, 0);

  return minutesFromWordCount(words);
}
