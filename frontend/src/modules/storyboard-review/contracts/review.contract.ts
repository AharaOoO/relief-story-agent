export type ReviewDecision = 'approve' | 'retry' | 'cancel' | 'manual_review'

export type ReviewEvent = {
  at: string
  title: string
  detail: string
}
