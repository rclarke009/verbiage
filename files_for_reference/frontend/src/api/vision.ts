import type { RagGroundedVisionResponse } from '../types'

export async function analyzePhoto(file: File, context: string): Promise<RagGroundedVisionResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('context', context)
  const res = await fetch('/api/vision/analyze-grounded', { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
