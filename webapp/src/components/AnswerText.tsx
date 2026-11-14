/** Renders an AI Agronom reply simply: paragraphs with line breaks, numbered steps, bullets, "Batafsil". */
import { useMemo } from 'react'
import { useI18n } from '../i18n'
import { inlineSegments, parseAnswer, type Block } from '../utils/answer'

function Inline({ text }: { text: string }) {
  return (
    <>
      {inlineSegments(text).map((s, i) => (s.bold ? <strong key={i}>{s.text}</strong> : <span key={i}>{s.text}</span>))}
    </>
  )
}

function Blocks({ blocks }: { blocks: Block[] }) {
  return (
    <>
      {blocks.map((b, i) => {
        if (b.type === 'p')
          return (
            <p key={i} className="answer__p">
              <Inline text={b.text} />
            </p>
          )
        if (b.type === 'ol')
          return (
            <ol key={i} className="answer__steps">
              {b.items.map((it, j) => (
                <li key={j} className="answer__step">
                  <span className="answer__num">{it.num}</span>
                  <span className="answer__step-text">
                    <Inline text={it.text} />
                  </span>
                </li>
              ))}
            </ol>
          )
        return (
          <ul key={i} className="answer__bullets">
            {b.items.map((it, j) => (
              <li key={j}>
                <Inline text={it} />
              </li>
            ))}
          </ul>
        )
      })}
    </>
  )
}

export function AnswerText({ text }: { text: string }) {
  const { t } = useI18n()
  const parsed = useMemo(() => parseAnswer(text), [text])
  return (
    <div className="answer">
      <Blocks blocks={parsed.main} />
      {parsed.more.length > 0 && (
        <details className="answer__more">
          <summary>{t('agronom.more')}</summary>
          <Blocks blocks={parsed.more} />
        </details>
      )}
    </div>
  )
}
