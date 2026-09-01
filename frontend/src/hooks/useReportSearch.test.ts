import { renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useReportSearch } from './useReportSearch'

/** Build a 200 streaming Response that emits each frame as its own chunk. */
function sseResponse(frames: string[]): Response {
  const enc = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(enc.encode(f))
      controller.close()
    },
  })
  return new Response(body, { status: 200 })
}

function mockFetch(value: Response) {
  const fn = vi.fn().mockResolvedValue(value)
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('useReportSearch', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('accumulates tokens and sources from the stream (happy path)', async () => {
    mockFetch(
      sseResponse([
        'event: sources\ndata: {"sources": [{"filename": "report.pdf"}], "chunks_used": 1}\n\n',
        'event: token\ndata: {"token": "Wind "}\n\n',
        'event: token\ndata: {"token": "damage."}\n\n',
      ]),
    )

    const { result } = renderHook(() => useReportSearch())
    await act(async () => {
      await result.current.search('wind damage')
    })

    const r = result.current.results[0]
    expect(r.answer).toBe('Wind damage.')
    expect(r.sources).toHaveLength(1)
    expect(r.chunksUsed).toBe(1)
    expect(r.streaming).toBe(false)
  })

  it('surfaces a readable message when the server emits an SSE error frame', async () => {
    // This is the regression: the backend signals failure with `event: error`
    // and the parser must not silently drop it (which produced a blank result).
    mockFetch(sseResponse(['event: error\ndata: {"detail": "retrieval_failed"}\n\n']))

    const { result } = renderHook(() => useReportSearch())
    await act(async () => {
      await result.current.search('wind damage')
    })

    const r = result.current.results[0]
    expect(r.streaming).toBe(false)
    expect(r.answer).toMatch(/retriev/i)
    expect(r.answer).not.toBe('Error:')
  })

  it('shows the status code instead of a blank "Error:" on an empty HTTP/2 failure', async () => {
    // statusText is empty over HTTP/2; with an empty body the old code threw
    // `new Error('')`, rendering a bare "Error:". Status code must fill the gap.
    mockFetch(new Response(null, { status: 502, statusText: '' }))

    const { result } = renderHook(() => useReportSearch())
    await act(async () => {
      await result.current.search('wind damage')
    })

    const r = result.current.results[0]
    expect(r.answer).toBe('Error: HTTP 502')
  })

  it('parses retrieval_debug from the sources event', async () => {
    mockFetch(
      sseResponse([
        'event: sources\ndata: {"sources": [], "chunks_used": 0, "retrieval_debug": {"retried": true, "original_query": "q1", "rewritten_query": "intact roof tiles"}}\n\n',
        'event: token\ndata: {"token": "ok"}\n\n',
      ]),
    )

    const { result } = renderHook(() => useReportSearch())
    await act(async () => {
      await result.current.search('q1')
    })

    const r = result.current.results[0]
    expect(r.retrievalDebug?.retried).toBe(true)
    expect(r.retrievalDebug?.rewritten_query).toBe('intact roof tiles')
  })

  it('does not carry guest results into a signed-in cache', async () => {
    window.localStorage.setItem(
      'verbiage-search-results:guest',
      JSON.stringify([
        {
          id: 'guest-1',
          query: 'harbor example',
          answer: 'sample hail damage',
          sources: [],
          chunksUsed: 0,
          streaming: false,
        },
      ]),
    )

    const { result, rerender } = renderHook(
      ({ userId }: { userId: string | null }) => useReportSearch(3, 'auto', userId),
      { initialProps: { userId: null } },
    )
    expect(result.current.results).toHaveLength(1)
    expect(result.current.results[0].query).toBe('harbor example')

    act(() => {
      rerender({ userId: 'user-123' })
    })
    expect(result.current.results).toHaveLength(0)
  })

  it('records corpus from the sources event', async () => {
    mockFetch(
      sseResponse([
        'event: sources\ndata: {"sources": [], "chunks_used": 0, "corpus": "live"}\n\n',
        'event: token\ndata: {"token": "ok"}\n\n',
      ]),
    )

    const { result } = renderHook(() => useReportSearch(3, 'auto', 'user-123'))
    await act(async () => {
      await result.current.search('q1')
    })

    expect(result.current.results[0].corpus).toBe('live')
  })

  it('parses an event whose type and data arrive in separate network reads', async () => {
    // currentEvent must persist across read() chunks, not reset per chunk.
    mockFetch(sseResponse(['event: token\n', 'data: {"token": "split"}\n\n']))

    const { result } = renderHook(() => useReportSearch())
    await act(async () => {
      await result.current.search('wind damage')
    })

    expect(result.current.results[0].answer).toBe('split')
  })
})
