import { VISION_ANALYZE_GROUNDED_PATH } from '../../api/vision'
import { apiOrigin } from '../../lib/api'

/**
 * Shown only when `VITE_FEATURE_VISION=true`. Backend route does not exist on Verbiage yet.
 */
export function VisionTab() {
  const base = apiOrigin() || 'same-origin as app'
  return (
    <div>
      <h2 style={{ marginTop: 0, color: '#0969da', fontSize: 18 }}>Photo analysis (preview)</h2>
      <p style={{ fontSize: 14, color: '#57606a', lineHeight: 1.55, maxWidth: 560 }}>
        This tab is a placeholder from the prototype. The production API does not implement{' '}
        <code style={{ fontSize: 12 }}>{VISION_ANALYZE_GROUNDED_PATH}</code> yet. When you add it,
        wire <code style={{ fontSize: 12 }}>frontend/src/api/vision.ts</code> to use{' '}
        <code style={{ fontSize: 12 }}>apiFetch</code> (Bearer token) and multipart form upload.
      </p>
      <p style={{ fontSize: 13, color: '#24292f' }}>
        API base (dev / split deploy): <code style={{ fontSize: 12 }}>{base}</code>
      </p>
    </div>
  )
}
