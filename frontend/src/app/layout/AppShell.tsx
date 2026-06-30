import { useEffect, useState, useMemo } from 'react'
import { useLocation, useParams, useNavigate } from 'react-router-dom'
import { Sparkles, Activity, Command, ArrowLeft, ArrowUpRight } from 'lucide-react'

// Import components
import { DesktopTitlebar } from '../../shared/components/DesktopTitlebar'
import { SpotlightCard } from '../../shared/components/ui/SpotlightCard'
import { Magnetic } from '../../shared/components/ui/Magnetic'

import { PixelCursorGlow } from '../../shared/components/ui/PixelCursorGlow'

// Import pages
import { LocalSetupPage } from '../../modules/local-setup/pages/LocalSetupPage'
import { ModelConfigPage } from '../../modules/model-config/pages/ModelConfigPage'
import { CreateRunPage } from '../../modules/run-creation/pages/CreateRunPage'
import { BatchQueuePage, BatchDetailPage } from '../../modules/batch-queue/pages/BatchQueuePage'
import { StoryboardReviewPage } from '../../modules/storyboard-review/pages/StoryboardReviewPage'
import { ArtifactLibraryPage } from '../../modules/artifact-library/pages/ArtifactLibraryPage'
import { RecoveryDiagnosticsPage } from '../../modules/recovery-diagnostics/pages/RecoveryDiagnosticsPage'

interface NavItem {
  id: string;
  label: string;
}

const navItems: NavItem[] = [
  { id: 'overview', label: 'System Overview' },
  { id: 'setup', label: 'Environment' },
  { id: 'config', label: 'Model Config' },
  { id: 'create', label: 'Initialize Run' },
  { id: 'batches', label: 'Batch Queue' },
  { id: 'storyboard', label: 'Review' },
  { id: 'artifacts', label: 'Artifacts' },
  { id: 'recovery', label: 'Diagnostics' },
]

const pathMap: Record<string, string> = {
  '/overview': 'overview',
  '/local-setup': 'setup',
  '/model-config': 'config',
  '/create-run': 'create',
  '/batches': 'batches',
  '/artifacts': 'artifacts',
  '/recovery': 'recovery',
}

export function AppShell() {
  const [activeId, setActiveId] = useState('overview')
  const location = useLocation()
  const params = useParams()
  const navigate = useNavigate()

  // Handle route changes
  useEffect(() => {
    const targetSectionId = pathMap[location.pathname]
    if (targetSectionId) {
      setActiveId(targetSectionId)
      document.getElementById(targetSectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } else if (location.pathname.startsWith('/runs/')) {
      setActiveId('storyboard')
      document.getElementById('storyboard')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } else if (location.pathname.startsWith('/batches/')) {
      setActiveId('batches')
      document.getElementById('batches')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [location.pathname])

  // Scroll Spy Observer
  useEffect(() => {
    const container = document.querySelector('.overflow-y-auto.flex-1')
    if (!container) return

    const observer = new IntersectionObserver((entries) => {
      // Find the most visible section
      let maxRatio = 0;
      let targetId = '';
      entries.forEach(entry => {
        if (entry.isIntersecting && entry.intersectionRatio > maxRatio) {
          maxRatio = entry.intersectionRatio;
          targetId = entry.target.id;
        }
      });
      if (targetId) setActiveId(targetId);
    }, {
      root: container,
      threshold: [0.1, 0.3, 0.5, 0.7, 0.9], // Trigger multiple times to find best ratio
      rootMargin: '-10% 0px -40% 0px'
    })

    // Setup a small timeout to let the DOM render before observing
    const timer = setTimeout(() => {
      navItems.forEach(item => {
        const el = document.getElementById(item.id)
        if (el) observer.observe(el)
      })
    }, 100);

    return () => {
      clearTimeout(timer)
      observer.disconnect()
    }
  }, [])

  const handleNavClick = (id: string) => {
    setActiveId(id)
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      
      // Update URL to match section (optional but good for direct links)
      const entry = Object.entries(pathMap).find(([_, value]) => value === id)
      if (entry) navigate(entry[0], { replace: true })
    }
  }

  const stats = useMemo(
    () => [
      { label: 'Environment Probe', value: 'Ready', status: 'ready' as const },
      { label: 'Prompt Engine', value: 'Optimized', status: 'ready' as const },
      { label: 'ComfyUI Handshake', value: 'Connected', status: 'ready' as const },
      { label: 'Cloud RunningHub', value: 'Standby', status: 'idle' as const },
    ],
    []
  )

  const isDesktop = typeof window !== 'undefined' && !!window.reliefDesktop;
  const isBatchDetailActive = location.pathname.startsWith('/batches/') && params.batchId

  return (
    <div 
      className="bg-bg text-text-primary min-h-screen flex h-screen overflow-hidden selection:bg-text-primary selection:text-bg"
      style={{ paddingTop: isDesktop ? '36px' : '0px' }}
    >
      <PixelCursorGlow />
      <DesktopTitlebar />
      {/* Dark Sidebar Navigation */}
      <div className="w-[280px] shrink-0 border-r border-stroke bg-surface p-6 flex flex-col justify-between overflow-y-auto">
        <div>
          <button onClick={() => navigate('/')} className="flex items-center gap-2 text-xs text-muted hover:text-text-primary uppercase tracking-[0.2em] mb-8 transition-colors cursor-pointer">
            <ArrowLeft size={14} /> Back to Landing
          </button>
          
          <div className="flex items-center gap-3 mb-8">
            <div className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-[#89AACC] to-[#4E85BF] p-[1.5px]">
              <div className="w-full h-full rounded-2xl bg-bg flex items-center justify-center">
                <Sparkles size={18} className="text-text-primary" />
              </div>
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight">LTX 2.3 Studio</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted font-bold">AUTOMATION</div>
            </div>
          </div>

          <div className="flex flex-col gap-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => handleNavClick(item.id)}
                className={`flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-xl transition duration-300 cursor-pointer ${
                  activeId === item.id
                    ? 'bg-stroke/50 text-text-primary'
                    : 'text-muted hover:bg-stroke/30 hover:text-text-primary'
                }`}
              >
                <span className={`h-2 w-2 rounded-full ${activeId === item.id ? 'bg-[#89AACC]' : 'bg-transparent'}`} />
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="mt-8 pt-4 border-t border-stroke flex items-center justify-center gap-2 text-[10px] text-muted font-bold uppercase tracking-[0.1em]">
            <Activity size={10} className="text-[#89AACC] animate-pulse" />
            Active Runtime: OK
          </div>
        </div>
      </div>

      {/* Main Workspace Scrolling Panel */}
      <div className="flex-1 overflow-y-auto p-8 md:p-12 pb-32">
        <div className="max-w-[1200px] mx-auto">
          {/* SECTION 1: Overview */}
          <section id="overview" className="scroll-mt-12 mb-12">
            <div className="mb-12">
              <h1 className="font-display italic text-5xl md:text-6xl font-semibold tracking-tight mb-4">
                Dashboard
              </h1>
              <p className="text-muted text-sm md:text-base uppercase tracking-[0.2em]">
                Ai Video Production Console #01
              </p>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
              <SpotlightCard className="min-h-[380px] p-8 flex flex-col justify-between">
                <div>
                  <div className="mb-6 flex flex-wrap items-center gap-3">
                    <span className="px-3 py-1 rounded-full bg-[#89AACC]/10 text-[#89AACC] border border-[#89AACC]/20 text-xs font-medium">LTX2.3 Core Active</span>
                    <span className="px-3 py-1 rounded-full bg-stroke/50 text-text-primary border border-stroke text-xs font-medium">Workflow Configured</span>
                  </div>

                  <p className="mb-4 text-xs uppercase tracking-[0.32em] text-muted font-bold">
                    PRODUCER CABINET / PIPELINE
                  </p>

                  <p className="mt-4 text-sm leading-8 text-muted">
                    Automated director workspace running on the LTX 2.3 framework. Supports full lifecycle generation from script drafting and pre-flight checks, to model orchestration and final artifact delivery.
                  </p>
                </div>

                <div className="mt-8 flex flex-wrap gap-4">
                  <Magnetic intensity={0.2}>
                    <button onClick={() => navigate('/create-run')} className="relative group rounded-full text-sm px-6 py-3 bg-text-primary text-bg font-medium cursor-pointer">
                      Initialize Run <ArrowUpRight className="inline ml-1" size={14} />
                    </button>
                  </Magnetic>
                  <Magnetic intensity={0.2}>
                    <button onClick={() => navigate('/local-setup')} className="relative group rounded-full text-sm px-6 py-3 border border-stroke text-text-primary hover:bg-stroke/50 transition-colors cursor-pointer">
                      System Checks
                    </button>
                  </Magnetic>
                </div>
              </SpotlightCard>

              <SpotlightCard className="p-8 flex flex-col justify-between">
                <div>
                  <div className="mb-6 flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.22em] text-muted font-bold">TELEMETRY</p>
                      <h2 className="mt-2 text-2xl font-medium">System Status</h2>
                    </div>
                    <div className="grid h-10 w-10 place-items-center rounded-xl bg-stroke/50">
                      <Command size={18} className="text-muted" />
                    </div>
                  </div>

                  <div className="grid gap-2">
                    {stats.map((item) => (
                      <div key={item.label} className="flex items-center justify-between px-4 py-3 rounded-lg bg-bg/50 border border-stroke/50">
                        <span className="text-sm text-muted">{item.label}</span>
                        <span className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full ${item.status === 'ready' ? 'bg-[#89AACC]' : 'bg-stroke'}`} />
                          <span className="text-sm font-medium">{item.value}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-stroke flex justify-between text-xs text-muted">
                  <span>Console: v2.3-LTX</span>
                  <span>Env: System Stable</span>
                </div>
              </SpotlightCard>
            </div>
          </section>

          {/* SECTION 2: Environment Setup */}
          <section id="setup" className="scroll-mt-12 mb-12">
            <SpotlightCard className="p-6 md:p-8">
              <LocalSetupPage />
            </SpotlightCard>
          </section>

          {/* SECTION 3: Model Config */}
          <section id="config" className="scroll-mt-12 mb-12">
            <SpotlightCard className="p-6 md:p-8">
              <ModelConfigPage />
            </SpotlightCard>
          </section>

          {/* SECTION 4: Creative Run */}
          <section id="create" className="scroll-mt-12 mb-12">
            <SpotlightCard className="p-6 md:p-8">
              <CreateRunPage />
            </SpotlightCard>
          </section>

          {/* SECTION 5: Batch Queue */}
          <section id="batches" className="scroll-mt-12 mb-12">
            <SpotlightCard className="p-6 md:p-8">
              <BatchQueuePage />
            </SpotlightCard>
          </section>

          {/* SECTION 6: Storyboard Review */}
          <section id="storyboard" className="scroll-mt-12 mb-12">
            <SpotlightCard className="p-6 md:p-8">
              <StoryboardReviewPage />
            </SpotlightCard>
          </section>

          {/* SECTION 7: Artifact Library */}
          <section id="artifacts" className="scroll-mt-12 mb-12">
            <SpotlightCard className="p-6 md:p-8">
              <ArtifactLibraryPage />
            </SpotlightCard>
          </section>

          {/* SECTION 8: Recovery Diagnostics */}
          <section id="recovery" className="scroll-mt-12">
            <SpotlightCard className="p-6 md:p-8">
              <RecoveryDiagnosticsPage />
            </SpotlightCard>
          </section>
        </div>
      </div>

      {/* Pop-out Glass Modal for Batch Details */}
      {isBatchDetailActive && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-bg/80 backdrop-blur-sm">
          <SpotlightCard className="w-full max-w-4xl max-h-[85vh] overflow-y-auto p-6 md:p-8 relative border-stroke/50 shadow-2xl">
            <button
              onClick={() => navigate('/batches')}
              className="absolute top-4 right-4 h-8 w-8 rounded-full bg-stroke hover:bg-stroke/80 flex items-center justify-center text-text-primary cursor-pointer transition-colors"
            >
              ✕
            </button>
            <BatchDetailPage />
          </SpotlightCard>
        </div>
      )}
    </div>
  )
}
