export type StructuredAddress = {
  address?: string
  address2?: string
  city?: string
  state?: string
  zip?: string
}

const ZIP_RE = /^(\d{5})(?:-(\d{4}))?$/

export function hasStructuredAddress(meta: StructuredAddress): boolean {
  return !!(
    meta.address2?.trim() ||
    meta.city?.trim() ||
    meta.state?.trim() ||
    meta.zip?.trim()
  )
}

export function splitLegacyAddress(raw: string): StructuredAddress {
  const trimmed = (raw || '').trim()
  if (!trimmed) {
    return { address: '', address2: '', city: '', state: '', zip: '' }
  }

  const parts = trimmed.split(',').map(p => p.trim())
  if (parts.length < 2) {
    return { address: trimmed, address2: '', city: '', state: '', zip: '' }
  }

  const line1 = parts[0]
  const remainder = parts.slice(1)

  if (remainder.length === 1) {
    const tokens = remainder[0].split(/\s+/)
    if (tokens.length >= 2 && tokens[tokens.length - 2].length === 2 && /^[A-Za-z]{2}$/.test(tokens[tokens.length - 2])) {
      const state = tokens[tokens.length - 2].toUpperCase()
      const zip = ZIP_RE.test(tokens[tokens.length - 1]) ? tokens[tokens.length - 1] : ''
      const city = tokens.length > 2 ? tokens.slice(0, -2).join(' ') : tokens[0]
      return { address: line1, address2: '', city, state, zip }
    }
    return { address: line1, address2: '', city: remainder[0], state: '', zip: '' }
  }

  const city = remainder[0]
  const stateZipTokens = remainder[remainder.length - 1].split(/\s+/)
  let state = ''
  let zip = ''
  if (
    stateZipTokens.length >= 2 &&
    stateZipTokens[stateZipTokens.length - 2].length === 2 &&
    /^[A-Za-z]{2}$/.test(stateZipTokens[stateZipTokens.length - 2])
  ) {
    state = stateZipTokens[stateZipTokens.length - 2].toUpperCase()
    if (ZIP_RE.test(stateZipTokens[stateZipTokens.length - 1])) {
      zip = stateZipTokens[stateZipTokens.length - 1]
    }
  } else if (stateZipTokens.length === 1 && /^[A-Za-z]{2}$/.test(stateZipTokens[0])) {
    state = stateZipTokens[0].toUpperCase()
  }

  const address2 = remainder.length > 2 ? remainder.slice(1, -1).join(', ') : ''
  return { address: line1, address2, city, state, zip }
}

export function normalizeAddressMeta(meta: StructuredAddress): StructuredAddress {
  const address = (meta.address ?? '').trim()
  if (!hasStructuredAddress(meta) && address.includes(',')) {
    return splitLegacyAddress(address)
  }
  return {
    address: meta.address ?? '',
    address2: meta.address2 ?? '',
    city: meta.city ?? '',
    state: meta.state ?? '',
    zip: meta.zip ?? '',
  }
}

export function composeFullAddress(meta: StructuredAddress): string {
  const normalized = normalizeAddressMeta(meta)
  const line1 = (normalized.address ?? '').trim()
  const line2 = (normalized.address2 ?? '').trim()
  const city = (normalized.city ?? '').trim()
  const state = (normalized.state ?? '').trim().toUpperCase()
  const zip = (normalized.zip ?? '').trim()

  if (!line1 && !city && !state) {
    return line1
  }

  if (city || state || zip) {
    const localityParts: string[] = []
    if (city) localityParts.push(city)
    const stateZip = [state, zip].filter(Boolean).join(' ')
    if (stateZip) localityParts.push(stateZip)
    const locality = localityParts.join(', ')

    const streetParts = [line1, line2].filter(Boolean)
    if (streetParts.length && locality) {
      return `${streetParts.join(', ')}, ${locality}`
    }
    if (streetParts.length) return streetParts.join(', ')
    return locality
  }

  if (line2) return line1 ? `${line1}, ${line2}` : line2
  return line1
}
