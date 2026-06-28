import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { NotFoundPage } from './layout/NotFoundPage'
import { RouteErrorBoundary } from './layout/RouteErrorBoundary'
import { ArtifactLibraryPage } from '../modules/artifact-library/pages/ArtifactLibraryPage'
import { BatchDetailPage, BatchQueuePage } from '../modules/batch-queue/pages/BatchQueuePage'
import { CreateRunPage } from '../modules/run-creation/pages/CreateRunPage'
import { LocalSetupPage } from '../modules/local-setup/pages/LocalSetupPage'
import { ModelConfigPage } from '../modules/model-config/pages/ModelConfigPage'
import { RecoveryDiagnosticsPage } from '../modules/recovery-diagnostics/pages/RecoveryDiagnosticsPage'
import { StoryboardReviewPage } from '../modules/storyboard-review/pages/StoryboardReviewPage'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: <Navigate to="/local-setup" replace /> },
      { path: 'local-setup', element: <LocalSetupPage /> },
      { path: 'model-config', element: <ModelConfigPage /> },
      { path: 'create-run', element: <CreateRunPage /> },
      { path: 'runs/:runId/review', element: <StoryboardReviewPage /> },
      { path: 'batches', element: <BatchQueuePage /> },
      { path: 'batches/:batchId', element: <BatchDetailPage /> },
      { path: 'artifacts', element: <ArtifactLibraryPage /> },
      { path: 'recovery', element: <RecoveryDiagnosticsPage /> },
      { path: 'recovery/run/:runId', element: <RecoveryDiagnosticsPage /> },
      { path: 'recovery/batch/:batchId', element: <RecoveryDiagnosticsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
