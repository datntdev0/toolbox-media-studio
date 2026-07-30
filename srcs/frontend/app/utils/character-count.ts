export function countCharacters(content: string | string[]): number {
  const text = Array.isArray(content) ? content.join(' ') : content
  return Array.from(text).length
}

export function formatCharacterCount(content: string | string[]): string {
  return new Intl.NumberFormat().format(countCharacters(content))
}
