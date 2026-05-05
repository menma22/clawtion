import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type EmbeddingProvider = 'gemini' | 'openai' | 'ollama'
type Theme = 'light' | 'dark' | 'system'
type Language = 'ja' | 'en'

interface SettingsStore {
  vaultPath: string
  embeddingProvider: EmbeddingProvider
  language: Language
  theme: Theme
  multiResolution: boolean
  enabledLevels: { file: boolean; coarse: boolean; fine: boolean }
  setVaultPath: (p: string) => void
  setProvider: (p: EmbeddingProvider) => void
  setTheme: (t: Theme) => void
  setLanguage: (l: Language) => void
  setMultiResolution: (v: boolean) => void
  setLevel: (level: 'file' | 'coarse' | 'fine', v: boolean) => void
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      vaultPath: '~/Documents/clawtion-vault',
      embeddingProvider: 'gemini',
      language: 'ja',
      theme: 'system',
      multiResolution: true,
      enabledLevels: { file: true, coarse: true, fine: true },

      setVaultPath: (vaultPath) => set({ vaultPath }),
      setProvider: (embeddingProvider) => set({ embeddingProvider }),
      setTheme: (theme) => {
        set({ theme })
        applyTheme(theme)
      },
      setLanguage: (language) => set({ language }),
      setMultiResolution: (multiResolution) => set({ multiResolution }),
      setLevel: (level, v) =>
        set((s) => ({
          enabledLevels: { ...s.enabledLevels, [level]: v },
        })),
    }),
    { name: 'clawtion-settings' },
  ),
)

function applyTheme(theme: Theme) {
  const root = document.documentElement
  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    root.setAttribute('data-theme', prefersDark ? 'dark' : 'light')
  } else {
    root.setAttribute('data-theme', theme)
  }
}

// Apply theme on load
const savedTheme = (useSettingsStore.getState().theme) as Theme
applyTheme(savedTheme)
