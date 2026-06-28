import { useRouteError } from 'react-router-dom'
import { ErrorState } from '../../shared/components/ErrorState'

export function RouteErrorBoundary() {
  const error = useRouteError()
  return <ErrorState error={error} title="页面渲染失败" />
}
