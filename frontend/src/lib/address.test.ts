import { describe, expect, it } from 'vitest'

import { composeFullAddress, normalizeAddressMeta, splitLegacyAddress } from './address'

describe('composeFullAddress', () => {
  it('composes structured fields', () => {
    expect(
      composeFullAddress({
        address: '412 Gulfview Drive',
        address2: 'Apt 2',
        city: 'Tampa',
        state: 'FL',
        zip: '33609',
      }),
    ).toBe('412 Gulfview Drive, Apt 2, Tampa, FL 33609')
  })

  it('parses legacy full address when structured fields are missing', () => {
    expect(composeFullAddress({ address: '412 Gulfview Drive, Tampa, FL 33609' })).toBe(
      '412 Gulfview Drive, Tampa, FL 33609',
    )
  })
})

describe('splitLegacyAddress', () => {
  it('splits city state zip', () => {
    expect(splitLegacyAddress('412 Gulfview Drive, Tampa, FL 33609')).toEqual({
      address: '412 Gulfview Drive',
      address2: '',
      city: 'Tampa',
      state: 'FL',
      zip: '33609',
    })
  })
})

describe('normalizeAddressMeta', () => {
  it('returns structured fields from legacy address', () => {
    expect(normalizeAddressMeta({ address: '100 Main Street, Springfield, IL' })).toEqual({
      address: '100 Main Street',
      address2: '',
      city: 'Springfield',
      state: 'IL',
      zip: '',
    })
  })
})
