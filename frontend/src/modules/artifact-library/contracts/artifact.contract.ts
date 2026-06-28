export type ArtifactItem = {
  artifact_id: string
  kind: string
  name: string
  path: string
  exists: boolean
  size_bytes?: number
  publish_ready?: boolean
}
