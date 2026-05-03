/**
 * Multimodal / vision API — placeholder until FastAPI exposes a route.
 *
 * Intended shape when implemented:
 * - `POST ${apiOrigin}${VISION_ANALYZE_GROUNDED_PATH}` with Bearer auth (`apiFetch` + FormData).
 */

import { apiOrigin } from '../lib/api'

export const VISION_ANALYZE_GROUNDED_PATH = '/vision/analyze-grounded'

export async function analyzePhoto(_file: File, _context: string): Promise<never> {
  const base = apiOrigin() || '(same origin)'
  throw new Error(
    `Vision is not wired to this backend yet. Planned: POST ${base}${VISION_ANALYZE_GROUNDED_PATH}`,
  )
}
