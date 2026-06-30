import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import { WorkbenchShell } from './workbench/WorkbenchShell'
import DashboardPage from '../pages/DashboardPage'
import AutopilotPage from '../pages/AutopilotPage'
import TasksPage from '../pages/TasksPage'
import AssetsPage from '../pages/AssetsPage'
import { NotFoundPage } from './layout/NotFoundPage'
import { RouteErrorBoundary } from './layout/RouteErrorBoundary'

export const routes: RouteObject[] = [
  {
    element: <WorkbenchShell />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/autopilot', element: <AutopilotPage /> },
      { path: '/run/:runId', element: <AutopilotPage /> },
      { path: '/tasks', element: <TasksPage /> },
      { path: '/assets', element: <AssetsPage /> },
      { path: '/create-run', element: <Navigate to="/" replace /> },
      { path: '/batches', element: <Navigate to="/tasks" replace /> },
      { path: '/artifacts', element: <Navigate to="/assets" replace /> },
      { path: '/model-config', element: <Navigate to="/" replace /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]

export const router = createBrowserRouter(routes)
