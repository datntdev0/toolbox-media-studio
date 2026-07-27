import type { TranslationLanguageOption } from '~/types/translation-workspace'

export const SUPPORTED_LANGUAGES: TranslationLanguageOption[] = [
  { code: 'zh', label: 'Chinese', nativeLabel: '中文' },
  { code: 'en', label: 'English', nativeLabel: 'English' },
  { code: 'vi', label: 'Vietnamese', nativeLabel: 'Tiếng Việt' },
  { code: 'ja', label: 'Japanese', nativeLabel: '日本語' },
  { code: 'ko', label: 'Korean', nativeLabel: '한국어' },
  { code: 'fr', label: 'French', nativeLabel: 'Français' },
  { code: 'es', label: 'Spanish', nativeLabel: 'Español' }
]

export function resolveLanguage(value?: string | null): TranslationLanguageOption {
  const code = String(value || '').trim().toLowerCase()
  return SUPPORTED_LANGUAGES.find(language => language.code === code) || {
    code: code || 'und',
    label: code ? code.toUpperCase() : 'Unknown',
    nativeLabel: code ? code.toUpperCase() : 'Unknown'
  }
}
