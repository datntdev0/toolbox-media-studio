import type {
  TranslationChapter,
  TranslationLanguageOption,
  TranslationNovelOption,
  TranslationProviderOption,
  TranslationWorkspace
} from '~/types/translation-workspace'
import { SUPPORTED_LANGUAGES } from '~/constants/supported-languages'

export const translationLanguages: TranslationLanguageOption[] = SUPPORTED_LANGUAGES

const chinese = translationLanguages[0]!
const english = translationLanguages[1]!
const vietnamese = translationLanguages[2]!
const japanese = translationLanguages[3]!
const korean = translationLanguages[4]!
const french = translationLanguages[5]!

export const translationNovels: TranslationNovelOption[] = [
  {
    id: 'novel-clockwork',
    title: 'The Clockwork Ascendant',
    sourceLanguage: chinese,
    chapterCount: 7,
    coverImageUrl: '/workspace-covers/clockwork-ascendant.svg'
  },
  {
    id: 'novel-lantern-city',
    title: 'Lantern City at the Edge of Dawn',
    sourceLanguage: english,
    chapterCount: 6,
    coverImageUrl: '/workspace-covers/lantern-city.svg'
  },
  {
    id: 'novel-iron-orchard',
    title: 'The Iron Orchard',
    sourceLanguage: chinese,
    chapterCount: 6,
    coverImageUrl: null
  },
  {
    id: 'novel-moonlit',
    title: 'Moonlit Swordmaster',
    sourceLanguage: chinese,
    chapterCount: 6,
    coverImageUrl: null
  }
]

export const translationProviders: TranslationProviderOption[] = [
  {
    id: 'openai',
    label: 'OpenAI',
    icon: 'simple-icons:openai',
    models: [
      {
        id: 'gpt-5-mini',
        label: 'GPT-5 mini',
        description: 'Balanced quality and throughput for chapter translation.'
      },
      {
        id: 'gpt-5',
        label: 'GPT-5',
        description: 'Higher-quality literary translation for nuanced prose.'
      }
    ]
  },
  {
    id: 'anthropic',
    label: 'Anthropic',
    icon: 'simple-icons:anthropic',
    models: [
      {
        id: 'claude-sonnet',
        label: 'Claude Sonnet',
        description: 'Strong long-context translation and style consistency.'
      }
    ]
  },
  {
    id: 'google',
    label: 'Google',
    icon: 'simple-icons:google',
    models: [
      {
        id: 'gemini-pro',
        label: 'Gemini Pro',
        description: 'General-purpose multilingual preview model.'
      }
    ]
  }
]

const originalParagraphs = [
  'When the seventh bell rang, Jian opened his eyes beneath a ceiling of brass gears. Every wheel turned in perfect silence, though the tower around him trembled with the storm.',
  'On the desk lay a letter bearing his own seal. The ink was still wet. “Do not let the city remember you,” it warned.',
  'He folded the letter into his coat and stepped toward the only door. Beyond it, footsteps climbed the spiral stair.'
]

const vietnameseParagraphs = [
  'Khi tiếng chuông thứ bảy vang lên, Jian mở mắt dưới trần nhà phủ kín những bánh răng bằng đồng. Mọi bánh xe đều xoay trong im lặng tuyệt đối, dù tòa tháp quanh anh đang rung chuyển giữa cơn bão.',
  'Trên bàn là một lá thư mang chính con dấu của anh. Mực vẫn còn ướt. “Đừng để thành phố nhớ đến ngươi,” dòng cảnh báo viết.',
  'Anh gấp lá thư vào áo khoác rồi bước về phía cánh cửa duy nhất. Phía bên kia, tiếng chân đang đi lên cầu thang xoắn ốc.'
]

const englishParagraphs = [
  'When the seventh bell sounded, Jian awoke beneath a ceiling crowded with brass gears. Each wheel moved in absolute silence even as the tower shuddered in the storm.',
  'A letter marked with his own seal waited on the desk. Its ink had not yet dried. “Do not let the city remember you,” it read.',
  'He slipped the letter into his coat and approached the room’s only door. On the other side, footsteps were ascending the spiral stairs.'
]

function makeChapters(
  translated: string[],
  statuses: TranslationChapter['status'][]
): TranslationChapter[] {
  const titles = [
    'The Seventh Bell',
    'A Map Without Streets',
    'The Brass Archivist',
    'Rain Over the Lower City',
    'Names Written in Smoke',
    'The Unwound Hour',
    'A Door Beneath the River'
  ]
  return titles.map((title, index) => ({
    id: `chapter-${index + 1}`,
    number: index + 1,
    title,
    status: statuses[index] || 'not_started',
    originalParagraphs: index === 6
      ? []
      : originalParagraphs.map((text, paragraph) =>
          paragraph === 0 ? text.replace('seventh', String(index + 7)) : text
        ),
    translatedParagraphs: ['translated', 'manually_edited'].includes(statuses[index] || '')
      ? translated
      : []
  }))
}

const defaultPrompt = `You are a professional literary translator. Translate faithfully while preserving names, dialogue, tone, paragraph breaks, and narrative intent. Return only the translated chapter text.`

export const translationWorkspaces: TranslationWorkspace[] = [
  {
    id: 'clockwork-vietnamese',
    name: 'Vietnamese translation',
    novelId: 'novel-clockwork',
    novelTitle: 'The Clockwork Ascendant',
    coverImageUrl: '/workspace-covers/clockwork-ascendant.svg',
    sourceLanguage: chinese,
    targetLanguage: vietnamese,
    status: 'running',
    progress: { total: 7, translated: 2, queued: 1, running: 1, failed: 1 },
    configuration: {
      providerId: 'openai',
      providerName: 'OpenAI',
      modelId: 'gpt-5-mini',
      modelName: 'GPT-5 mini',
      globalPrompt: defaultPrompt,
      previewChapterId: 'chapter-1',
      previewParagraphs: vietnameseParagraphs,
      previewGeneratedAt: '2026-07-27T08:30:00Z'
    },
    chapters: makeChapters(vietnameseParagraphs, [
      'translated',
      'manually_edited',
      'translating',
      'queued',
      'failed',
      'not_started',
      'unavailable'
    ]),
    updatedAt: '2026-07-27T09:14:00Z',
    etag: null
  },
  {
    id: 'clockwork-english',
    name: 'English translation',
    novelId: 'novel-clockwork',
    novelTitle: 'The Clockwork Ascendant',
    coverImageUrl: '/workspace-covers/clockwork-ascendant.svg',
    sourceLanguage: chinese,
    targetLanguage: english,
    status: 'completed',
    progress: { total: 7, translated: 7, queued: 0, running: 0, failed: 0 },
    configuration: {
      providerId: 'anthropic',
      providerName: 'Anthropic',
      modelId: 'claude-sonnet',
      modelName: 'Claude Sonnet',
      globalPrompt: defaultPrompt,
      previewChapterId: 'chapter-1',
      previewParagraphs: englishParagraphs,
      previewGeneratedAt: '2026-07-24T11:00:00Z'
    },
    chapters: makeChapters(englishParagraphs, [
      'translated',
      'translated',
      'translated',
      'manually_edited',
      'translated',
      'translated',
      'translated'
    ]),
    updatedAt: '2026-07-24T12:40:00Z',
    etag: null
  },
  {
    id: 'lantern-french',
    name: 'French translation',
    novelId: 'novel-lantern-city',
    novelTitle: 'Lantern City at the Edge of Dawn',
    coverImageUrl: '/workspace-covers/lantern-city.svg',
    sourceLanguage: english,
    targetLanguage: french,
    status: 'ready',
    progress: { total: 6, translated: 0, queued: 0, running: 0, failed: 0 },
    configuration: {
      providerId: 'google',
      providerName: 'Google',
      modelId: 'gemini-pro',
      modelName: 'Gemini Pro',
      globalPrompt: defaultPrompt,
      previewChapterId: 'chapter-1',
      previewParagraphs: [
        'Lorsque la septième cloche sonna, Jian ouvrit les yeux sous un plafond d’engrenages de laiton.',
        'Une lettre portant son propre sceau reposait sur le bureau. L’encre était encore humide.'
      ],
      previewGeneratedAt: '2026-07-26T07:15:00Z'
    },
    chapters: makeChapters([], [
      'not_started',
      'not_started',
      'not_started',
      'not_started',
      'not_started',
      'unavailable'
    ]).slice(0, 6),
    updatedAt: '2026-07-26T07:18:00Z',
    etag: null
  },
  {
    id: 'orchard-korean',
    name: 'Korean translation',
    novelId: 'novel-iron-orchard',
    novelTitle: 'The Iron Orchard',
    coverImageUrl: null,
    sourceLanguage: chinese,
    targetLanguage: korean,
    status: 'failed',
    progress: { total: 6, translated: 2, queued: 0, running: 0, failed: 2 },
    configuration: {
      providerId: 'openai',
      providerName: 'OpenAI',
      modelId: 'gpt-5-mini',
      modelName: 'GPT-5 mini',
      globalPrompt: defaultPrompt,
      previewChapterId: 'chapter-1',
      previewParagraphs: ['일곱 번째 종이 울리자 지안은 황동 톱니바퀴로 뒤덮인 천장 아래에서 눈을 떴다.'],
      previewGeneratedAt: '2026-07-22T08:00:00Z'
    },
    chapters: makeChapters(['번역된 예시 단락입니다.'], [
      'translated',
      'translated',
      'failed',
      'failed',
      'not_started',
      'not_started'
    ]).slice(0, 6),
    updatedAt: '2026-07-22T08:42:00Z',
    etag: null
  },
  {
    id: 'moonlit-japanese',
    name: 'Japanese translation',
    novelId: 'novel-moonlit',
    novelTitle: 'Moonlit Swordmaster',
    coverImageUrl: null,
    sourceLanguage: chinese,
    targetLanguage: japanese,
    status: 'needs_setup',
    progress: { total: 6, translated: 0, queued: 0, running: 0, failed: 0 },
    configuration: null,
    chapters: makeChapters([], [
      'not_started',
      'not_started',
      'not_started',
      'not_started',
      'not_started',
      'unavailable'
    ]).slice(0, 6),
    updatedAt: '2026-07-20T06:30:00Z',
    etag: null
  }
]

export function findTranslationWorkspace(id: string) {
  return translationWorkspaces.find(workspace => workspace.id === id) || null
}
