import { safeJson } from '../utils/safeJson'

type JsonViewerProps = {
  value: unknown
}

export function JsonViewer({ value }: JsonViewerProps) {
  return (
    <pre className="json-viewer max-h-[300px] overflow-auto bg-black/20 p-3 rounded-lg text-xs font-mono">
      {safeJson(value)}
    </pre>
  )
}
