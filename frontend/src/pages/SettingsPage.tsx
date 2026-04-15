import { useState, useEffect } from 'react'
import { Save, Server, Globe, Cpu, Timer, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { Button } from '../components/ui/Button'
import { Input, Select } from '../components/ui/FormFields'
import { settingsApi } from '../services/api'

export function SettingsPage() {
  const [settings, setSettings] = useState({
    apiUrl: 'http://127.0.0.1:8000',
    llmModel: '',
    llmTemperature: '',
    defaultBrowser: 'chromium',
    stepTimeout: '',
    navigationTimeout: '',
    executionTimeout: '',
    maxRetries: '',
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    settingsApi.get()
      .then(data => {
        setSettings(prev => ({
          ...prev,
          llmModel: data.ollama_model,
          llmTemperature: String(data.llm_temperature),
          stepTimeout: String(data.step_timeout_ms),
          navigationTimeout: String(data.navigation_timeout_ms),
          executionTimeout: String(data.execution_timeout_s),
          maxRetries: String(data.max_reverification_attempts),
        }))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const update = (key: string, val: string) => {
    setSettings(prev => ({ ...prev, [key]: val }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="animate-fade-in max-w-3xl">
      <PageHeader
        title="Settings"
        description="Configure your test automation platform"
      />

      {/* API Connection */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-surface-400" />
            <h3 className="text-sm font-semibold text-surface-200">API Connection</h3>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            id="api-url"
            label="Backend API URL"
            value={settings.apiUrl}
            onChange={e => update('apiUrl', e.target.value)}
          />
        </CardContent>
      </Card>

      {/* AI Configuration */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-surface-400" />
            <h3 className="text-sm font-semibold text-surface-200">AI Configuration</h3>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              id="llm-model"
              label="LLM Model"
              value={settings.llmModel}
              onChange={e => update('llmModel', e.target.value)}
            />
            <Input
              id="llm-temp"
              label="Temperature"
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={settings.llmTemperature}
              onChange={e => update('llmTemperature', e.target.value)}
            />
          </div>
          <Input
            id="max-retries"
            label="Max Reverification Attempts"
            type="number"
            min="1"
            max="10"
            value={settings.maxRetries}
            onChange={e => update('maxRetries', e.target.value)}
          />
        </CardContent>
      </Card>

      {/* Execution Settings */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Timer className="w-4 h-4 text-surface-400" />
            <h3 className="text-sm font-semibold text-surface-200">Execution Settings</h3>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select
            id="default-browser"
            label="Default Browser"
            options={[
              { value: 'chromium', label: 'Chromium' },
              { value: 'firefox', label: 'Firefox' },
              { value: 'webkit', label: 'WebKit (Safari)' },
            ]}
            value={settings.defaultBrowser}
            onChange={e => update('defaultBrowser', e.target.value)}
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Input
              id="step-timeout"
              label="Step Timeout (ms)"
              type="number"
              value={settings.stepTimeout}
              onChange={e => update('stepTimeout', e.target.value)}
            />
            <Input
              id="nav-timeout"
              label="Navigation Timeout (ms)"
              type="number"
              value={settings.navigationTimeout}
              onChange={e => update('navigationTimeout', e.target.value)}
            />
            <Input
              id="exec-timeout"
              label="Execution Timeout (s)"
              type="number"
              value={settings.executionTimeout}
              onChange={e => update('executionTimeout', e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button>
          <Save className="w-4 h-4" />
          Save Settings
        </Button>
      </div>
    </div>
  )
}
