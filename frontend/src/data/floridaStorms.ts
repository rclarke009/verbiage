export type StormType = 'hurricane' | 'tropical_storm'

export interface FloridaStorm {
  id: string
  name: string
  year: number
  landfall_date: string
  landfall_display: string
  storm_type: StormType
  category: string
  landfall_region: string
}

export const FLORIDA_STORMS: FloridaStorm[] = [
  {
    id: 'milton-2024',
    name: 'Milton',
    year: 2024,
    landfall_date: '2024-10-09',
    landfall_display: 'October 9, 2024',
    storm_type: 'hurricane',
    category: 'Cat 3',
    landfall_region: 'Siesta Key, FL',
  },
  {
    id: 'helene-2024',
    name: 'Helene',
    year: 2024,
    landfall_date: '2024-09-26',
    landfall_display: 'September 26, 2024',
    storm_type: 'hurricane',
    category: 'Cat 4',
    landfall_region: 'Near Perry, FL',
  },
  {
    id: 'debby-2024',
    name: 'Debby',
    year: 2024,
    landfall_date: '2024-08-05',
    landfall_display: 'August 5, 2024',
    storm_type: 'hurricane',
    category: 'Cat 1',
    landfall_region: 'Steinhatchee, FL',
  },
  {
    id: 'idalia-2023',
    name: 'Idalia',
    year: 2023,
    landfall_date: '2023-08-30',
    landfall_display: 'August 30, 2023',
    storm_type: 'hurricane',
    category: 'Cat 3',
    landfall_region: 'Keaton Beach, FL',
  },
  {
    id: 'ian-2022',
    name: 'Ian',
    year: 2022,
    landfall_date: '2022-09-28',
    landfall_display: 'September 28, 2022',
    storm_type: 'hurricane',
    category: 'Cat 4',
    landfall_region: 'Cayo Costa, FL',
  },
  {
    id: 'nicole-2022',
    name: 'Nicole',
    year: 2022,
    landfall_date: '2022-11-10',
    landfall_display: 'November 10, 2022',
    storm_type: 'hurricane',
    category: 'Cat 1',
    landfall_region: 'Vero Beach, FL',
  },
  {
    id: 'elsa-2021',
    name: 'Elsa',
    year: 2021,
    landfall_date: '2021-07-07',
    landfall_display: 'July 7, 2021',
    storm_type: 'tropical_storm',
    category: 'Tropical Storm',
    landfall_region: 'Taylor County, FL',
  },
  {
    id: 'fred-2021',
    name: 'Fred',
    year: 2021,
    landfall_date: '2021-08-16',
    landfall_display: 'August 16, 2021',
    storm_type: 'tropical_storm',
    category: 'Tropical Storm',
    landfall_region: 'Cape San Blas, FL',
  },
  {
    id: 'mindy-2021',
    name: 'Mindy',
    year: 2021,
    landfall_date: '2021-09-08',
    landfall_display: 'September 8, 2021',
    storm_type: 'tropical_storm',
    category: 'Tropical Storm',
    landfall_region: 'St. Vincent Island, FL',
  },
]

export const STORM_METADATA_KEYS = [
  'storm_id',
  'storm_name',
  'storm_date',
  'storm_type',
  'storm_category',
  'landfall_region',
] as const

export function getStormById(id: string): FloridaStorm | undefined {
  return FLORIDA_STORMS.find(s => s.id === id)
}

export function stormsByYear(): Map<number, FloridaStorm[]> {
  const grouped = new Map<number, FloridaStorm[]>()
  for (const storm of FLORIDA_STORMS) {
    const list = grouped.get(storm.year) ?? []
    list.push(storm)
    grouped.set(storm.year, list)
  }
  return grouped
}

export function stormOptionLabel(storm: FloridaStorm): string {
  const shortDate = storm.landfall_display.replace(/, \d{4}$/, '')
  return `${storm.name} (${shortDate}) — ${storm.category}, ${storm.landfall_region}`
}

export function stormMetadataFromSelection(storm: FloridaStorm): Record<string, string> {
  return {
    storm_id: storm.id,
    storm_name: storm.name,
    storm_date: storm.landfall_display,
    storm_type: storm.storm_type,
    storm_category: storm.category,
    landfall_region: storm.landfall_region,
  }
}

export function clearStormMetadata(meta: Record<string, string>): Record<string, string> {
  const next = { ...meta }
  for (const key of STORM_METADATA_KEYS) {
    delete next[key]
  }
  return next
}
