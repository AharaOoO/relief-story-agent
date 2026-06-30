import { useState, useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Hls from 'hls.js';
import { ArrowUpRight, Play, Database, Command } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { DesktopTitlebar } from '../shared/components/DesktopTitlebar';
import { Magnetic } from '../shared/components/ui/Magnetic';
import { SpotlightCard } from '../shared/components/ui/SpotlightCard';
import { TextReveal } from '../shared/components/ui/TextReveal';
import { PixelCursorGlow } from '../shared/components/ui/PixelCursorGlow';

gsap.registerPlugin(ScrollTrigger);

// --- Section 1: Loading Screen ---
function LoadingScreen({ onComplete }: { onComplete: () => void }) {
  const [count, setCount] = useState(0);
  const [wordIndex, setWordIndex] = useState(0);
  const words = ["Generate", "Direct", "Render"];
  const isDesktop = typeof window !== 'undefined' && !!window.reliefDesktop;

  useEffect(() => {
    let start: number;
    const duration = 2700;
    
    const animate = (time: number) => {
      if (!start) start = time;
      const progress = Math.min((time - start) / duration, 1);
      setCount(Math.floor(progress * 100));
      
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setTimeout(onComplete, 400);
      }
    };
    requestAnimationFrame(animate);

    const wordInterval = setInterval(() => {
      setWordIndex((prev) => (prev + 1) % words.length);
    }, 900);

    return () => clearInterval(wordInterval);
  }, [onComplete]);

  return (
    <motion.div
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.8, ease: "easeInOut" }}
      className="fixed inset-0 z-[9999] bg-bg flex flex-col justify-between p-6 md:p-12"
      style={{
        paddingTop: isDesktop ? '52px' : undefined
      }}
    >
      <motion.div
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="text-xs text-muted uppercase tracking-[0.3em]"
      >
        LTX 2.3 核心引擎 (ENGINE)
      </motion.div>

      <div className="flex-1 flex items-center justify-center overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={wordIndex}
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -20, opacity: 0 }}
            transition={{ duration: 0.4 }}
            className="text-4xl md:text-6xl lg:text-7xl font-display italic text-text-primary/80"
          >
            {words[wordIndex]}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="flex flex-col items-end gap-4">
        <div className="text-6xl md:text-8xl lg:text-9xl font-display text-text-primary tabular-nums">
          {String(count).padStart(3, "0")}
        </div>
        <div className="w-full max-w-md h-[3px] bg-stroke/50 relative overflow-hidden rounded-full">
          <div
            className="absolute inset-y-0 left-0 w-full bg-gradient-to-r from-[#89AACC] to-[#4E85BF] origin-left"
            style={{ 
              transform: `scaleX(${count / 100})`, 
              boxShadow: "0 0 8px rgba(137, 170, 204, 0.35)" 
            }}
          />
        </div>
      </div>
    </motion.div>
  );
}

// --- Section 2: Hero & Navbar ---
function Navbar() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const isDesktop = typeof window !== 'undefined' && !!window.reliefDesktop;

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 100);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav 
      className="fixed left-0 right-0 z-50 flex justify-center px-4"
      style={{
        top: isDesktop ? '36px' : '0px',
        paddingTop: isDesktop ? '12px' : '16px'
      }}
    >
      <div className={`inline-flex items-center rounded-full backdrop-blur-md border border-white/10 bg-surface px-2 py-2 transition-shadow duration-300 ${scrolled ? 'shadow-md shadow-black/10' : ''}`}>
        
        <Magnetic intensity={0.2}>
          <div onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="w-9 h-9 rounded-full bg-gradient-to-r from-[#89AACC] to-[#4E85BF] p-[1.5px] cursor-pointer group">
            <div className="w-full h-full rounded-full bg-bg flex items-center justify-center">
              <span className="font-display italic text-[13px] text-text-primary">LTX</span>
            </div>
          </div>
        </Magnetic>

        <div className="hidden md:block w-px h-5 bg-stroke mx-3" />

        <div className="flex items-center gap-1">
          {[
            { label: '控制台', en: 'Dashboard', path: '/' },
            { label: '任务流', en: 'Batches', path: '/batches' },
            { label: '资产库', en: 'Artifacts', path: '/artifacts' }
          ].map((link, i) => {
            return (
              <Magnetic intensity={0.1} key={link.en}>
                <button 
                  onClick={() => {
                    if (link.en === "Dashboard") window.scrollTo({ top: 0, behavior: 'smooth' });
                    else navigate(link.path);
                  }}
                  className={`text-xs sm:text-sm rounded-full px-3 sm:px-4 py-1.5 sm:py-2 transition-colors cursor-pointer ${i === 0 ? 'text-text-primary bg-stroke/50' : 'text-muted hover:text-text-primary hover:bg-stroke/50'}`}
                >
                  {link.label}
                </button>
              </Magnetic>
            );
          })}
        </div>

        <div className="w-px h-5 bg-stroke mx-3" />

        <Magnetic intensity={0.15}>
          <button onClick={() => navigate('/create-run')} className="group relative text-xs sm:text-sm rounded-full px-3 sm:px-4 py-1.5 sm:py-2 text-text-primary cursor-pointer">
            <span className="absolute inset-[-2px] rounded-full bg-gradient-to-r from-[#89AACC] to-[#4E85BF] opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative flex items-center gap-2 bg-surface rounded-full backdrop-blur-md px-3 py-1.5 h-full w-full">
              新建流 <Play size={14} className="fill-current" />
            </div>
          </button>
        </Magnetic>
      </div>
    </nav>
  );
}

function HeroSection() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [roleIndex, setRoleIndex] = useState(0);
  const rolesEN = ["Director", "Pipeline", "Generator", "Studio"];
  const rolesCN = ["执导", "管线", "生成", "工作室"];

  useEffect(() => {
    if (videoRef.current) {
      const videoSrc = "https://stream.mux.com/Aa02T7oM1wH5Mk5EEVDYhbZ1ChcdhRsS2m1NYyx4Ua1g.m3u8";
      if (Hls.isSupported()) {
        const hls = new Hls();
        hls.loadSource(videoSrc);
        hls.attachMedia(videoRef.current);
      } else if (videoRef.current.canPlayType("application/vnd.apple.mpegurl")) {
        videoRef.current.src = videoSrc;
      }
    }

    const interval = setInterval(() => {
      setRoleIndex(prev => (prev + 1) % rolesEN.length);
    }, 2000);

    gsap.to(".blur-in", { opacity: 1, filter: "blur(0px)", y: 0, duration: 1, stagger: 0.1, delay: 0.8, ease: "power3.out" });

    return () => clearInterval(interval);
  }, []);

  return (
    <section className="relative w-full h-screen flex flex-col items-center justify-center overflow-hidden">
      <div className="absolute inset-0 z-0">
        <video 
          ref={videoRef}
          autoPlay muted loop playsInline
          className="absolute top-1/2 left-1/2 min-w-full min-h-full object-cover -translate-x-1/2 -translate-y-1/2 opacity-60"
        />
        <div className="absolute inset-0 bg-black/30" />
        <div className="absolute bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-bg to-transparent" />
      </div>

      <div className="relative z-10 flex flex-col items-center text-center px-4 mt-16">
        <div className="blur-in opacity-0 translate-y-5 filter blur-[10px] text-xs text-muted uppercase tracking-[0.3em] mb-8">
          SYSTEM CORE '26
        </div>
        
        <TextReveal 
          text="LTX 2.3" 
          delay={0.2}
          className="text-6xl md:text-8xl lg:text-[10rem] font-display italic leading-[0.9] tracking-tight text-text-primary mb-6" 
        />

        <div className="blur-in opacity-0 translate-y-5 filter blur-[10px] text-xl md:text-2xl text-text-primary mb-4 flex items-center gap-2">
            <div className="flex items-center whitespace-nowrap">
              高度自动化的 AI&nbsp;
              <div className="relative inline-grid place-items-center">
                <AnimatePresence mode="popLayout">
                  <motion.span 
                    key={roleIndex}
                    initial={{ y: 20, opacity: 0, filter: "blur(4px)" }}
                    animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
                    exit={{ y: -20, opacity: 0, filter: "blur(4px)" }}
                    transition={{ duration: 0.4, ease: "easeInOut" }}
                    className="font-display italic text-text-primary text-center px-1"
                  >
                    {rolesCN[roleIndex]}
                  </motion.span>
                </AnimatePresence>
              </div>
              &nbsp;中枢 (Automated&nbsp;
              <div className="relative inline-grid place-items-center">
                <AnimatePresence mode="popLayout">
                  <motion.span 
                    key={roleIndex}
                    initial={{ y: 20, opacity: 0, filter: "blur(4px)" }}
                    animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
                    exit={{ y: -20, opacity: 0, filter: "blur(4px)" }}
                    transition={{ duration: 0.4, ease: "easeInOut" }}
                    className="font-display italic text-text-primary text-center px-1"
                  >
                    {rolesEN[roleIndex]}
                  </motion.span>
                </AnimatePresence>
              </div>
              &nbsp;Node).
            </div>
        </div>

        <p className="blur-in opacity-0 translate-y-5 filter blur-[10px] text-sm md:text-base text-muted max-w-md mb-12">
            专注于 AI 视频管线的毫厘之差，为您重塑无缝数字叙事 (Orchestrating seamless digital cinematography).
        </p>

        <div className="blur-in opacity-0 translate-y-5 filter blur-[10px] inline-flex flex-col sm:flex-row gap-6">
          <Magnetic intensity={0.3}>
            <button onClick={() => navigate('/create-run')} className="relative group rounded-full text-sm px-8 py-4 hover:scale-105 transition-transform overflow-hidden bg-text-primary text-bg hover:text-text-primary cursor-pointer">
              <span className="absolute inset-0 bg-bg opacity-0 group-hover:opacity-100 transition-opacity z-0" />
              <span className="absolute inset-0 rounded-full bg-gradient-to-r from-[#89AACC] to-[#4E85BF] p-[2px] opacity-0 group-hover:opacity-100 z-10 mask-border" />
              <span className="relative z-20 font-medium">初始化流 (Initialize)</span>
            </button>
          </Magnetic>

          <Magnetic intensity={0.3}>
            <button onClick={() => navigate('/model-config')} className="relative group rounded-full text-sm px-8 py-4 hover:scale-105 transition-transform border-2 border-stroke bg-bg/50 backdrop-blur-sm text-text-primary hover:border-transparent cursor-pointer">
              <span className="absolute inset-0 rounded-full bg-gradient-to-r from-[#89AACC] to-[#4E85BF] opacity-0 group-hover:opacity-100 transition-opacity z-0" />
              <span className="absolute inset-[2px] rounded-full bg-bg z-10" />
              <span className="relative z-20 font-medium flex items-center gap-2"><Command size={14} /> 配置模型 (Config)</span>
            </button>
          </Magnetic>
        </div>
      </div>

      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
        <span className="text-[10px] text-muted uppercase tracking-[0.2em]">Scroll</span>
        <div className="w-px h-10 bg-stroke relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1/3 bg-text-primary animate-scroll-down" />
        </div>
      </div>
    </section>
  );
}

// --- Section 3: Selected Works ---
function SelectedWorks() {
  const navigate = useNavigate();
  const projects = [
    { title: "Run: Ocean Cinematic", cnTitle: "运行: 海洋电影", col: "md:col-span-7" },
    { title: "Batch: Urban Architecture", cnTitle: "批次: 城市建筑", col: "md:col-span-5" },
    { title: "Log: Resource Optimization", cnTitle: "日志: 资源优化", col: "md:col-span-5" },
    { title: "Run: Cyberpunk Abyss", cnTitle: "运行: 赛博朋克深渊", col: "md:col-span-7" },
  ];

  return (
    <section className="bg-bg py-16 md:py-24">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10 lg:px-16">
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: [0.25, 0.1, 0.25, 1] }}
          viewport={{ once: true, margin: "-100px" }}
          className="flex flex-col md:flex-row md:items-end justify-between mb-12"
        >
          <div>
            <div className="flex items-center gap-4 mb-4">
              <div className="w-8 h-px bg-stroke" />
              <span className="text-xs text-muted uppercase tracking-[0.3em]">Recent Batches</span>
            </div>
            <h2 className="text-4xl md:text-5xl font-medium tracking-tight mb-2">
              生成的数字分镜 <span className="font-display italic text-muted">(Generated Storyboards)</span>
            </h2>
            <p className="text-muted text-sm md:text-base">精选近期 AI 视频生成任务，从概念到最终渲染 (A selection of recent AI video runs, from concept to render).</p>
          </div>
          <Magnetic intensity={0.1}>
            <button onClick={() => navigate('/batches')} className="hidden md:inline-flex items-center gap-2 group text-sm text-text-primary rounded-full border border-stroke px-5 py-2 hover:border-transparent relative cursor-pointer">
              <span className="absolute inset-[-1px] rounded-full bg-gradient-to-r from-[#89AACC] to-[#4E85BF] opacity-0 group-hover:opacity-100 transition-opacity z-0" />
              <span className="absolute inset-[1px] rounded-full bg-bg z-10" />
              <span className="relative z-20 flex items-center gap-2">查看所有任务流 (View all batches) <ArrowUpRight size={14} /></span>
            </button>
          </Magnetic>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-5 md:gap-6">
          {projects.map((p, i) => (
            <SpotlightCard key={i} className={`${p.col} aspect-[4/3] md:aspect-auto md:min-h-[400px]`}>
              <div className="absolute inset-0 bg-gradient-to-br from-surface to-bg opacity-50 transition-transform duration-700" />
              {/* Halftone Overlay */}
              <div 
                className="absolute inset-0 opacity-20 mix-blend-multiply pointer-events-none" 
                style={{ backgroundImage: 'radial-gradient(circle, #000 1px, transparent 1px)', backgroundSize: '4px 4px' }}
              />
              
              <div className="absolute inset-0 bg-bg/60 opacity-0 group-hover:opacity-100 backdrop-blur-md transition-opacity duration-500 flex items-center justify-center">
                <div className="relative rounded-full px-6 py-3 bg-white text-black font-medium text-sm flex items-center gap-2 transform translate-y-4 group-hover:translate-y-0 transition-all duration-500">
                  查看 (Inspect) — <span className="font-display italic text-base">{p.cnTitle}</span>
                </div>
              </div>
            </SpotlightCard>
          ))}
        </div>
      </div>
    </section>
  );
}

// --- Section 4: Journal ---
function JournalSection() {
  const journals = [
    { title: "节点初始化 (Node initialized): local-sdxl-01", date: "System", time: "0ms 延迟" },
    { title: "资产编译完成 (Artifact compilation finished)", date: "Render", time: "4.2s 运行时间" },
    { title: "获取外部依赖 (Fetching external dependencies)", date: "Network", time: "20ms 延迟" },
    { title: "任务终止 (Run #4092 aborted by user)", date: "User", time: "已终止 (Terminated)" },
  ];

  return (
    <section className="bg-bg py-16 md:py-24">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10 lg:px-16">
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: [0.25, 0.1, 0.25, 1] }}
          viewport={{ once: true, margin: "-100px" }}
          className="mb-12"
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="w-8 h-px bg-stroke" />
            <span className="text-xs text-muted uppercase tracking-[0.3em]">Telemetry</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-medium tracking-tight mb-2">
            系统遥测日志 <span className="font-display italic text-muted">(System Logs)</span>
          </h2>
        </motion.div>

        <div className="flex flex-col gap-4">
          {journals.map((j, i) => (
            <div key={i} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 sm:p-6 bg-surface/30 hover:bg-surface border border-stroke rounded-[32px] sm:rounded-full cursor-pointer transition-colors group">
              <div className="flex items-center gap-4 sm:gap-6">
                <div className="w-12 h-12 rounded-full bg-stroke/50 group-hover:scale-105 transition-transform flex items-center justify-center">
                  <Database size={16} className="text-muted" />
                </div>
                <span className="text-base md:text-lg font-medium">{j.title}</span>
              </div>
              <div className="flex items-center gap-6 text-sm text-muted px-2 sm:px-4">
                <span>{j.time}</span>
                <span>{j.date}</span>
                <ArrowUpRight size={16} className="group-hover:text-text-primary transition-colors" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}


// --- Section 5: Stats ---
function StatsSection() {
  const stats = [
    { value: "10+", label: "模型节点 (Model Nodes)" },
    { value: "400+", label: "生成帧数 (Generated Frames)" },
    { value: "99%", label: "管线运行时间 (Pipeline Uptime)" },
  ];

  return (
    <section className="bg-bg py-16 md:py-24 border-t border-stroke">
      <div className="max-w-[1200px] mx-auto px-6 grid grid-cols-1 md:grid-cols-3 gap-12 text-center divide-y md:divide-y-0 md:divide-x divide-stroke">
        {stats.map((s, i) => (
          <div key={i} className="pt-8 md:pt-0">
            <div className="text-6xl md:text-7xl font-display italic text-text-primary mb-2">{s.value}</div>
            <div className="text-sm text-muted uppercase tracking-widest">{s.label}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

// --- Section 6: Footer ---
function FooterSection() {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current) {
      const videoSrc = "https://stream.mux.com/Aa02T7oM1wH5Mk5EEVDYhbZ1ChcdhRsS2m1NYyx4Ua1g.m3u8";
      if (Hls.isSupported()) {
        const hls = new Hls();
        hls.loadSource(videoSrc);
        hls.attachMedia(videoRef.current);
      } else if (videoRef.current.canPlayType("application/vnd.apple.mpegurl")) {
        videoRef.current.src = videoSrc;
      }
    }

    gsap.to(".marquee-inner", {
      xPercent: -50,
      duration: 40,
      ease: "none",
      repeat: -1
    });
  }, []);

  return (
    <footer className="relative bg-bg pt-16 md:pt-20 pb-8 md:pb-12 overflow-hidden border-t border-stroke">
      <div className="absolute inset-0 z-0">
        <video 
          ref={videoRef}
          autoPlay muted loop playsInline
          className="absolute top-1/2 left-1/2 min-w-full min-h-full object-cover -translate-x-1/2 -translate-y-1/2 scale-y-[-1] opacity-30"
        />
        <div className="absolute inset-0 bg-black/60" />
      </div>

      <div className="relative z-10">
        <div className="flex justify-center mb-16 px-4">
          <Magnetic intensity={0.2}>
            <button className="relative group rounded-full text-base md:text-lg px-8 py-4 border border-stroke bg-surface/50 backdrop-blur-md text-text-primary cursor-pointer">
              <span className="absolute inset-[-1px] rounded-full bg-gradient-to-r from-[#89AACC] to-[#4E85BF] opacity-0 group-hover:opacity-100 transition-opacity z-0" />
              <span className="absolute inset-[1px] rounded-full bg-bg z-10" />
              <span className="relative z-20 font-medium tracking-wide">admin@ltxstudio.local</span>
            </button>
          </Magnetic>
        </div>

        <div className="overflow-hidden w-full border-y border-stroke/50 py-4 mb-12 bg-bg/40 backdrop-blur-sm">
          <div className="marquee-inner whitespace-nowrap flex w-[200%]">
            <div className="text-4xl md:text-6xl font-display italic text-text-primary/50 tracking-widest flex-1 flex justify-around">
              {Array(5).fill("生成未来 (GENERATING THE FUTURE) • ").map((text, i) => <span key={i}>{text}</span>)}
            </div>
            <div className="text-4xl md:text-6xl font-display italic text-text-primary/50 tracking-widest flex-1 flex justify-around">
              {Array(5).fill("生成未来 (GENERATING THE FUTURE) • ").map((text, i) => <span key={i}>{text}</span>)}
            </div>
          </div>
        </div>

        <div className="max-w-[1200px] mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex gap-6 text-sm text-muted">
            <a href="#" className="hover:text-text-primary transition-colors">文档 (Documentation)</a>
            <a href="#" className="hover:text-text-primary transition-colors">接口 (API)</a>
            <a href="#" className="hover:text-text-primary transition-colors">状态 (Status)</a>
          </div>
          <div className="flex items-center gap-3 text-sm text-muted bg-surface/50 rounded-full px-4 py-2 border border-stroke">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            系统在线 (System Online)
          </div>
        </div>
      </div>
    </footer>
  );
}

// --- Main Page Assembly ---
const initialHasPlayed = typeof window !== 'undefined' ? sessionStorage.getItem('hasPlayedLoading') === 'true' : false;

export default function LandingPage() {
  const [isLoading, setIsLoading] = useState(!initialHasPlayed);

  return (
    <div className="bg-bg text-text-primary min-h-screen overflow-x-hidden selection:bg-text-primary selection:text-bg">
      <PixelCursorGlow />
      <DesktopTitlebar />
      <AnimatePresence mode="wait">
        {isLoading ? (
          <LoadingScreen 
            key="loading" 
            onComplete={() => {
              if (typeof window !== 'undefined') sessionStorage.setItem('hasPlayedLoading', 'true');
              setIsLoading(false);
            }} 
          />
        ) : (
          <motion.div
            key="content"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1 }}
          >
            <Navbar />
            <HeroSection />
            <SelectedWorks />
            <JournalSection />
            <StatsSection />
            <FooterSection />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
