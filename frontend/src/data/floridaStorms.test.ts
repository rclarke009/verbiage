import { describe, expect, it } from 'vitest'
import {
  FLORIDA_STORMS,
  getStormById,
  stormMetadataFromSelection,
  stormsByYear,
} from './floridaStorms'

describe('floridaStorms', () => {
  it('lists 9 notable Florida landfalls from 2021–2024', () => {
    expect(FLORIDA_STORMS).toHaveLength(9)
    expect(FLORIDA_STORMS.map(s => s.id)).toContain('ian-2022')
    expect(FLORIDA_STORMS.map(s => s.id)).toContain('milton-2024')
  })

  it('groups storms by year newest-first', () => {
    const grouped = stormsByYear()
    expect([...grouped.keys()].sort((a, b) => b - a)).toEqual([2024, 2023, 2022, 2021])
    expect(grouped.get(2024)).toHaveLength(3)
  })

  it('fills full storm metadata for Ian', () => {
    const ian = getStormById('ian-2022')
    expect(ian).toBeDefined()
    expect(stormMetadataFromSelection(ian!)).toEqual({
      storm_id: 'ian-2022',
      storm_name: 'Ian',
      storm_date: 'September 28, 2022',
      storm_date_iso: '2022-09-28',
      storm_type: 'hurricane',
      storm_category: 'Cat 4',
      landfall_region: 'Cayo Costa, FL',
    })
  })
})
