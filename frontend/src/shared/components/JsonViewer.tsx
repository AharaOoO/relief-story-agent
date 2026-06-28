import { safeJson } from '../utils/safeJson'

type JsonViewerProps = {
  value: unknown
}

export function JsonViewer({ value }: JsonViewerProps) {
  return <pre className="json-viewer">{safeJson(value)}</pre>
}
