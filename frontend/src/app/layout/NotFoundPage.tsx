import { Link } from 'react-router-dom'
import { Button } from '@heroui/react'
import { PageHeader } from '../../shared/components/PageHeader'

export function NotFoundPage() {
  return (
    <div className="stack">
      <PageHeader
        title="页面不存在"
        description="这个入口还没有绑定到 Relief Story Agent 的操作流。"
      />
      <Link to="/local-setup">
        <Button className="hero-button">回到本地环境检查</Button>
      </Link>
    </div>
  )
}
