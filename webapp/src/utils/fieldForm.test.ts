import { describe, expect, it } from 'vitest'
import { translate, type MessageKey, type Params } from '../i18n'
import { EMPTY_FORM, formFromField, validateFieldForm, type FieldFormValues } from './fieldForm'

const tUz = (k: MessageKey, p?: Params) => translate('uz', k, p)
const tRu = (k: MessageKey, p?: Params) => translate('ru', k, p)
const tEn = (k: MessageKey, p?: Params) => translate('en', k, p)
const TODAY = '2026-11-15'

const valid: FieldFormValues = {
  name: "  Bug'doy dalasi ",
  crop: 'wheat_winter',
  area: '76,23',
  plantingDate: '2026-10-12',
  soil: 'loam',
  irrigation: 'furrow',
  water: 'canal',
  location: { lat: 40.02612345, lon: 67.90114999 },
}

describe('add / edit field form', () => {
  it('builds the v2 POST /fields payload (decimal comma accepted)', () => {
    const { errors, input } = validateFieldForm(valid, tUz, TODAY)
    expect(errors).toEqual({})
    expect(input).toEqual({
      name: "Bug'doy dalasi",
      crop: 'wheat_winter',
      area_ha: 76.23,
      planting_date: '2026-10-12',
      soil_texture: 'loam',
      irrigation_type: 'furrow',
      water_source: 'canal',
      location: { lat: 40.026123, lon: 67.90115 },
    })
  })

  it('reports every missing item with a clear message', () => {
    const { errors, input } = validateFieldForm(EMPTY_FORM, tUz, TODAY)
    expect(input).toBeNull()
    expect(errors).toEqual({
      name: 'Dala nomini kiriting',
      crop: 'Ekin turini tanlang',
      area: 'Maydonni kiriting',
      plantingDate: 'Ekilgan sanani tanlang',
      soil: 'Tuproq turini tanlang',
      irrigation: "Sug'orish turini tanlang",
      water: 'Suv manbaini tanlang',
      location: 'Xaritada dala joylashuvini belgilang',
    })
  })

  it('validates the area', () => {
    expect(validateFieldForm({ ...valid, area: 'besh' }, tUz, TODAY).errors.area).toBe('Maydonni raqam bilan kiriting, masalan: 2,5')
    expect(validateFieldForm({ ...valid, area: '0,01' }, tUz, TODAY, 'uz').errors.area).toBe("Maydon 0,05 – 5 000 ga oralig'ida bo'lishi kerak")
    expect(validateFieldForm({ ...valid, area: '6000' }, tRu, TODAY, 'ru').errors.area).toBe('Площадь должна быть от 0,05 до 5 000 га')
    expect(validateFieldForm({ ...valid, area: '0.05' }, tUz, TODAY).errors.area).toBeUndefined()
    expect(validateFieldForm({ ...valid, area: '0' }, tEn, TODAY, 'en').errors.area).toBe('The area must be between 0.05 and 5,000 ha')
    expect(validateFieldForm({ ...valid, area: 'five' }, tEn, TODAY, 'en').errors.area).toBe('Enter the area as a number, e.g. 2.5')
  })

  it('validates name length and the planting date', () => {
    expect(validateFieldForm({ ...valid, name: 'x'.repeat(129) }, tUz, TODAY).errors.name).toMatch(/128/)
    expect(validateFieldForm({ ...valid, plantingDate: '2026-02-30' }, tUz, TODAY).errors.plantingDate).toBe('Ekilgan sanani tanlang')
    expect(validateFieldForm({ ...valid, plantingDate: '2028-01-01' }, tUz, TODAY).errors.plantingDate).toBe('Sana juda uzoq kelajakda')
    expect(validateFieldForm({ ...valid, plantingDate: '2027-03-01' }, tUz, TODAY).errors.plantingDate).toBeUndefined()
  })

  it('messages follow the language', () => {
    expect(validateFieldForm(EMPTY_FORM, tRu, TODAY).errors.crop).toBe('Выберите культуру')
    expect(validateFieldForm(EMPTY_FORM, tEn, TODAY).errors).toEqual({
      name: 'Enter a field name',
      crop: 'Choose a crop type',
      area: 'Enter the area',
      plantingDate: 'Choose a planting date',
      soil: 'Choose a soil type',
      irrigation: 'Choose an irrigation type',
      water: 'Choose a water source',
      location: 'Tap the map to set the field location',
    })
  })

  it('pre-fills from an existing field (edit)', () => {
    const v = formFromField(
      {
        id: 7,
        name: "Bug'doy dalasi",
        geometry: null,
        area_ha: 76.23,
        crop: 'wheat_winter',
        planting_date: '2026-10-12',
        soil_texture: 'loam',
        irrigation_type: 'furrow',
        water_source: 'canal',
        location: { lat: 40.0261, lon: 67.9011 },
      },
      'uz',
    )
    expect(v).toEqual({ ...valid, name: "Bug'doy dalasi", location: { lat: 40.0261, lon: 67.9011 } })
  })
})
