type LoadingStateProps = {
  title?: string
  message?: string
}

export function LoadingState({
  title = '正在读取状态',
  message = '本地后端响应中，请稍等。',
}: LoadingStateProps) {
  return (
    <div className="loading-state" role="status">
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  )
}
