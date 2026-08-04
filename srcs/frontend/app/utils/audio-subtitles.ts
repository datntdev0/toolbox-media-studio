import type { AudioSubtitleCue } from '~/types/audio-workspace'

const TIMESTAMP_PATTERN
  = /^(\d{2,}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2,}):(\d{2}):(\d{2}),(\d{3})$/

function normalizeSentence(value: string): string {
  return value.replace(/\s+/gu, ' ').trim()
}

function parseTimestamp(parts: RegExpMatchArray, offset: number): number {
  const hours = Number(parts[offset])
  const minutes = Number(parts[offset + 1])
  const seconds = Number(parts[offset + 2])
  const milliseconds = Number(parts[offset + 3])
  if (minutes > 59 || seconds > 59) throw new Error('Invalid subtitle timestamp')
  return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
}

export function parseChapterSrt(srt: string, sentences: string[]): AudioSubtitleCue[] {
  const normalizedSrt = srt.replace(/^\uFEFF/u, '').replace(/\r\n?/gu, '\n').trim()
  if (!normalizedSrt) throw new Error('Subtitle file is empty')

  const blocks = normalizedSrt.split(/\n{2,}/gu)
  if (blocks.length !== sentences.length) {
    throw new Error('Subtitle cue count does not match the chapter')
  }

  let previousEnd = 0
  return blocks.map((block, cueIndex) => {
    const lines = block.split('\n')
    if (lines.length < 3 || lines[0] !== String(cueIndex + 1)) {
      throw new Error('Subtitle cues are not in 1-based sequential order')
    }

    const timestamp = lines[1]?.match(TIMESTAMP_PATTERN)
    if (!timestamp) throw new Error('Subtitle cue has an invalid timestamp')
    const startSeconds = parseTimestamp(timestamp, 1)
    const endSeconds = parseTimestamp(timestamp, 5)
    if (endSeconds <= startSeconds || startSeconds < previousEnd) {
      throw new Error('Subtitle cue timings are invalid or overlap')
    }

    const text = normalizeSentence(lines.slice(2).join(' '))
    const sourceText = normalizeSentence(sentences[cueIndex] || '')
    if (!sourceText || text !== sourceText) {
      throw new Error(`Subtitle cue ${cueIndex + 1} does not match the chapter text`)
    }

    previousEnd = endSeconds
    return {
      index: cueIndex,
      startSeconds,
      endSeconds,
      text
    }
  })
}
