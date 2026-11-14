import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { DEFAULT_LANG, setLang, toLang } from './i18n'
import './styles/theme.css'
import './styles/app.css'
import { getTelegramLanguageCode, initTelegram } from './telegram'

initTelegram()
// Until the farmer's saved language is known: Telegram's language_code (en / uz / ru), else English.
const initialLang = toLang(getTelegramLanguageCode()) ?? DEFAULT_LANG
setLang(initialLang)
document.documentElement.lang = initialLang

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
