import { motion } from 'framer-motion'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useSettingsStore } from '@/stores/settingsStore'
import { useUIStore } from '@/stores/uiStore'

export default function SettingsPage() {
  const settings = useSettingsStore()
  const addToast = useUIStore((s) => s.addToast)

  const handleSave = () => {
    addToast({ type: 'success', title: '設定を保存しました（ローカル）' })
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-2xl mx-auto p-6"
    >
      <h1 className="text-2xl font-bold text-text-primary mb-6">設定</h1>

      <div className="space-y-8">
        {/* Vault */}
        <section className="rounded-lg border border-border-default bg-surface-card p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Vault（ノート保存先）</h2>
          <Input
            value={settings.vaultPath}
            onChange={(e) => settings.setVaultPath(e.target.value)}
            placeholder="~/Documents/clawtion-vault"
          />
        </section>

        {/* Embedding Provider */}
        <section className="rounded-lg border border-border-default bg-surface-card p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Embedding プロバイダ</h2>
          <div className="flex gap-4">
            {(['gemini', 'openai', 'ollama'] as const).map((p) => (
              <label
                key={p}
                className={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
                  settings.embeddingProvider === p
                    ? 'bg-primary text-text-inverse'
                    : 'bg-surface-input text-text-secondary hover:bg-border-default'
                }`}
              >
                <input
                  type="radio"
                  name="provider"
                  checked={settings.embeddingProvider === p}
                  onChange={() => settings.setProvider(p)}
                  className="sr-only"
                />
                {p === 'gemini' ? 'Gemini' : p === 'openai' ? 'OpenAI' : 'Ollama (ローカル)'}
              </label>
            ))}
          </div>
        </section>

        {/* Theme */}
        <section className="rounded-lg border border-border-default bg-surface-card p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">テーマ</h2>
          <div className="flex gap-4">
            {(['light', 'dark', 'system'] as const).map((t) => (
              <label
                key={t}
                className={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
                  settings.theme === t
                    ? 'bg-primary text-text-inverse'
                    : 'bg-surface-input text-text-secondary hover:bg-border-default'
                }`}
              >
                <input
                  type="radio"
                  name="theme"
                  checked={settings.theme === t}
                  onChange={() => settings.setTheme(t)}
                  className="sr-only"
                />
                {t === 'light' ? 'ライト' : t === 'dark' ? 'ダーク' : 'システム'}
              </label>
            ))}
          </div>
        </section>

        {/* Language */}
        <section className="rounded-lg border border-border-default bg-surface-card p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">言語</h2>
          <div className="flex gap-4">
            {(['ja', 'en'] as const).map((l) => (
              <label
                key={l}
                className={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
                  settings.language === l
                    ? 'bg-primary text-text-inverse'
                    : 'bg-surface-input text-text-secondary hover:bg-border-default'
                }`}
              >
                <input
                  type="radio"
                  name="language"
                  checked={settings.language === l}
                  onChange={() => settings.setLanguage(l)}
                  className="sr-only"
                />
                {l === 'ja' ? '日本語' : 'English'}
              </label>
            ))}
          </div>
        </section>

        {/* Chunking */}
        <section className="rounded-lg border border-border-default bg-surface-card p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">チャンキング</h2>
          <label className="flex items-center gap-2 mb-3 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.multiResolution}
              onChange={(e) => settings.setMultiResolution(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-text-primary">マルチレゾリューション有効</span>
          </label>
          {settings.multiResolution && (
            <div className="space-y-2 ml-6">
              {(['file', 'coarse', 'fine'] as const).map((level) => (
                <label key={level} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.enabledLevels[level]}
                    onChange={(e) => settings.setLevel(level, e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm text-text-secondary">
                    {level === 'file' ? 'File 粒度' : level === 'coarse' ? 'Coarse 粒度' : 'Fine 粒度'}
                  </span>
                </label>
              ))}
            </div>
          )}
        </section>

        <Button onClick={handleSave}>保存</Button>
      </div>
    </motion.div>
  )
}
