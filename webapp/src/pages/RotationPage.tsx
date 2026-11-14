/** Almashlab ekish — GET /fields/{id}/rotation-plan (ROT-2, ROT-3, ROT-4). */
import { useParams } from 'react-router'
import { getCrops, getRotationPlan } from '../api/endpoints'
import type { RotationCandidate } from '../api/types'
import { Badge, BulletList, Card, ConfidenceBadge, Empty, ErrorBox, KeyValue, Loading, Meter, NoData, Page, RangeBar } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { fmtNum, fmtSigned } from '../utils/format'
import { formatDateTime } from '../utils/time'

function CandidateCard({ c, rank, yieldScale }: { c: RotationCandidate; rank: number; yieldScale: number }) {
  return (
    <article className="candidate">
      <header className="candidate__head">
        <span className="candidate__rank">{rank}</span>
        <div className="candidate__title">
          <strong>{c.crop_name_uz}</strong>
          <ConfidenceBadge value={c.confidence} />
        </div>
        <div className="candidate__score">
          {fmtNum(c.score, 0)}
          <span className="muted small">/100</span>
        </div>
      </header>
      <Meter value={c.score} tone={c.score >= 70 ? 'success' : c.score >= 50 ? 'warning' : 'danger'} />

      <KeyValue
        items={[
          {
            label: 'Taxminiy hosil',
            value: c.yield ? (
              <span>
                {fmtNum(c.yield.min_t_ha, 1)} – <strong>{fmtNum(c.yield.likely_t_ha, 1)}</strong> – {fmtNum(c.yield.max_t_ha, 1)} t/ga
              </span>
            ) : (
              <NoData />
            ),
          },
          { label: 'Suv talabi', value: c.water_need_m3_ha !== null ? `${fmtNum(c.water_need_m3_ha, 0)} m³/ga` : <NoData /> },
          {
            label: 'Suv unumdorligi',
            value: c.water_productivity_kg_m3 !== null ? `${fmtNum(c.water_productivity_kg_m3, 2)} kg/m³` : <NoData />,
          },
        ]}
      />
      {c.yield && <RangeBar min={c.yield.min_t_ha} likely={c.yield.likely_t_ha} max={c.yield.max_t_ha} scaleMax={yieldScale} />}

      {c.rationale_uz && <p>{c.rationale_uz}</p>}

      <details className="candidate__details">
        <summary>Ball tarkibi ({c.score_breakdown.length} omil)</summary>
        <ul className="breakdown">
          {c.score_breakdown.map((b, i) => (
            <li key={i}>
              <span className={`breakdown__pts ${b.points < 0 ? 'is-negative' : ''}`}>{fmtSigned(b.points, 0)}</span>
              <div>
                <div>{b.factor_uz}</div>
                {b.reason_uz && <div className="muted small">{b.reason_uz}</div>}
              </div>
            </li>
          ))}
        </ul>
      </details>

      <div className="rec__lists">
        <div>
          <div className="rec__list-title">Taxminlar</div>
          <BulletList items={c.assumptions} empty="—" />
        </div>
        <div>
          <div className="rec__list-title">Xavflar</div>
          <BulletList items={c.risks} empty="—" />
        </div>
      </div>
    </article>
  )
}

export function RotationPage() {
  const { id } = useParams()
  const fieldId = Number(id)
  const plan = useAsync(() => getRotationPlan(fieldId), [fieldId])
  const crops = useAsync(getCrops, [])
  const cropName = (key: string) => crops.data?.find((c) => c.key === key)?.name_uz ?? key

  const p = plan.data
  const included = (p?.candidates ?? []).filter((c) => !c.excluded).sort((a, b) => b.score - a.score)
  const excluded = (p?.candidates ?? []).filter((c) => c.excluded)
  const yieldScale = Math.max(1, ...included.map((c) => (c.yield ? c.yield.max_t_ha * 1.15 : 0)))

  return (
    <Page title="Almashlab ekish" subtitle="Keyingi mavsum uchun nomzod ekinlar" back={`/fields/${fieldId}`}>
      {plan.loading && !p && <Loading />}
      {plan.error && <ErrorBox error={plan.error} onRetry={plan.reload} />}
      {p && (
        <>
          <Card title="Asos">
            <KeyValue
              items={[
                { label: 'Oldingi ekinlar', value: p.previous_crops.length ? p.previous_crops.map(cropName).join(', ') : <NoData /> },
                { label: 'Hisoblangan', value: formatDateTime(p.generated_at) },
              ]}
            />
            {p.method_uz && <p className="muted small">Usul: {p.method_uz}</p>}
          </Card>

          {!included.length && <Empty>Mos nomzod topilmadi</Empty>}
          {included.map((c, i) => (
            <CandidateCard key={c.crop} c={c} rank={i + 1} yieldScale={yieldScale} />
          ))}

          {excluded.length > 0 && (
            <Card title="Chiqarib tashlangan ekinlar">
              <ul className="excluded">
                {excluded.map((c) => (
                  <li key={c.crop}>
                    <Badge tone="neutral">{c.crop_name_uz}</Badge>
                    <span>{c.exclusion_reason ?? 'Sabab ko\'rsatilmagan'}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </Page>
  )
}
