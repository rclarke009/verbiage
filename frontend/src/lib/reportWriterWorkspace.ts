export type ReportWriterWorkspace = 'intake' | 'photos' | 'report'

export function claimHasGeneratedContent(
  sections: Record<string, { content?: string }> | undefined,
): boolean {
  return Object.values(sections ?? {}).some(s => (s.content ?? '').trim().length > 0)
}

export function defaultReportWriterWorkspace(opts: {
  hasGeneratedContent: boolean
  generating: boolean
}): ReportWriterWorkspace {
  if (opts.generating || opts.hasGeneratedContent) return 'report'
  return 'intake'
}
