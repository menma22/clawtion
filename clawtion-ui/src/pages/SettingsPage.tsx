import { useSettingsStore } from '@/stores/settingsStore'
import { useUIStore } from '@/stores/uiStore'

export default function SettingsPage() {
  const s = useSettingsStore()
  const addToast = useUIStore((sm) => sm.addToast)

  const radioBtn = (active: boolean) =>
    `px-3 py-1 text-[12px] font-medium rounded-md cursor-pointer transition-colors ${active ? 'bg-text text-app' : 'text-text-secondary hover:bg-hover'}`

  return (
    <div className="mx-auto max-w-xl px-8 py-8">
      <h1 className="text-[22px] font-bold text-text tracking-tight mb-6">Settings</h1>

      <div className="space-y-6">
        {/* Vault */}
        <section>
          <h2 className="text-[13px] font-semibold text-text mb-2">Vault</h2>
          <input value={s.vaultPath} onChange={(e) => s.setVaultPath(e.target.value)}
            className="h-9 w-full rounded-md border border-border bg-input px-2.5 text-[13px] text-text outline-none focus:border-accent/40 focus:ring-2 focus:ring-accent/10 transition-all" />
        </section>

        {/* Provider */}
        <section>
          <h2 className="text-[13px] font-semibold text-text mb-2">Embedding Provider</h2>
          <div className="flex rounded-lg border border-border p-0.5 w-fit">
            {(['gemini', 'openai', 'ollama'] as const).map((p) => (
              <label key={p} className={radioBtn(s.embeddingProvider === p)}>
                <input type="radio" name="provider" checked={s.embeddingProvider === p} onChange={() => s.setProvider(p)} className="sr-only" />
                {p === 'gemini' ? 'Gemini' : p === 'openai' ? 'OpenAI' : 'Ollama'}
              </label>
            ))}
          </div>
        </section>

        {/* Theme */}
        <section>
          <h2 className="text-[13px] font-semibold text-text mb-2">Theme</h2>
          <div className="flex rounded-lg border border-border p-0.5 w-fit">
            {(['light', 'dark', 'system'] as const).map((t) => (
              <label key={t} className={radioBtn(s.theme === t)}>
                <input type="radio" name="theme" checked={s.theme === t} onChange={() => s.setTheme(t)} className="sr-only" />
                {t === 'light' ? 'Light' : t === 'dark' ? 'Dark' : 'System'}
              </label>
            ))}
          </div>
        </section>

        {/* Language */}
        <section>
          <h2 className="text-[13px] font-semibold text-text mb-2">Language</h2>
          <div className="flex rounded-lg border border-border p-0.5 w-fit">
            {(['ja', 'en'] as const).map((l) => (
              <label key={l} className={radioBtn(s.language === l)}>
                <input type="radio" name="language" checked={s.language === l} onChange={() => s.setLanguage(l)} className="sr-only" />
                {l === 'ja' ? '日本語' : 'English'}
              </label>
            ))}
          </div>
        </section>

        {/* Chunking */}
        <section>
          <h2 className="text-[13px] font-semibold text-text mb-2">Chunking</h2>
          <label className="flex items-center gap-2 mb-2 cursor-pointer">
            <input type="checkbox" checked={s.multiResolution} onChange={(e) => s.setMultiResolution(e.target.checked)} className="rounded" />
            <span className="text-[13px] text-text">マルチレゾリューション</span>
          </label>
          {s.multiResolution && (
            <div className="space-y-1.5 ml-6">
              {(['file', 'coarse', 'fine'] as const).map((level) => (
                <label key={level} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={s.enabledLevels[level]} onChange={(e) => s.setLevel(level, e.target.checked)} className="rounded" />
                  <span className="text-[12px] text-text-secondary">{level}粒度</span>
                </label>
              ))}
            </div>
          )}
        </section>

        <button onClick={() => addToast({ type: 'success', title: '設定を保存しました' })}
          className="rounded-lg bg-text px-4 py-1.5 text-[13px] font-medium text-app hover:bg-text/85 transition-colors cursor-pointer">
          保存
        </button>
      </div>
    </div>
  )
}
