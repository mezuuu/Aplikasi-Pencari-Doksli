import { useEffect, useRef } from 'react'

/**
 * Animated particle background inspired by antigravity.google
 * Renders colorful floating particles that drift organically,
 * dodge the mouse cursor (antigravity), and connect to form constellations.
 */
export default function ParticleBackground() {
    const canvasRef = useRef(null)

    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        let animationId
        let particles = []
        let mouse = { x: -1000, y: -1000 }

        // Google-inspired color palette
        const COLORS_LIGHT = [
            '#1D59AD', '#4285F4', '#EA4335', '#FBBC04', '#34A853', '#9b72cb', '#d96570'
        ]

        const COLORS_DARK = [
            '#60a5fa', '#818cf8', '#f87171', '#fbbf24', '#34d399', '#c084fc', '#fb7185'
        ]

        const PARTICLE_COUNT = 90
        const MAX_SIZE = 5
        const MIN_SIZE = 1.5
        const CONNECTION_DISTANCE = 110
        const MOUSE_RADIUS = 180

        function getColors() {
            return document.documentElement.classList.contains('dark')
                ? COLORS_DARK
                : COLORS_LIGHT
        }

        function resize() {
            const dpr = window.devicePixelRatio || 1
            const rect = canvas.parentElement.getBoundingClientRect()
            canvas.width = rect.width * dpr
            canvas.height = rect.height * dpr
            canvas.style.width = rect.width + 'px'
            canvas.style.height = rect.height + 'px'
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
        }

        function createParticle() {
            const rect = canvas.parentElement.getBoundingClientRect()
            const colors = getColors()
            const size = MIN_SIZE + Math.random() * (MAX_SIZE - MIN_SIZE)
            
            // Base velocities
            const vxBase = (Math.random() - 0.5) * 0.6
            const vyBase = (Math.random() - 0.5) * 0.6

            return {
                x: Math.random() * rect.width,
                y: Math.random() * rect.height,
                size,
                color: colors[Math.floor(Math.random() * colors.length)],
                vxBase,
                vyBase,
                vx: vxBase,
                vy: vyBase,
                phaseX: Math.random() * Math.PI * 2,
                phaseY: Math.random() * Math.PI * 2,
                freqX: 0.001 + Math.random() * 0.002,
                freqY: 0.001 + Math.random() * 0.002,
                ampX: 0.4 + Math.random() * 0.6,
                ampY: 0.4 + Math.random() * 0.6,
                alpha: 0.4 + Math.random() * 0.6,
                alphaPhase: Math.random() * Math.PI * 2,
                alphaFreq: 0.003 + Math.random() * 0.008,
            }
        }

        function init() {
            resize()
            particles = []
            for (let i = 0; i < PARTICLE_COUNT; i++) {
                particles.push(createParticle())
            }
        }

        function draw(time) {
            const rect = canvas.parentElement.getBoundingClientRect()
            ctx.clearRect(0, 0, rect.width, rect.height)

            // 1. Draw glowing mouse aura
            if (mouse.x > -1000 && mouse.x <= rect.width && mouse.y <= rect.height) {
                const gradient = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, MOUSE_RADIUS * 2)
                const isDark = document.documentElement.classList.contains('dark')
                gradient.addColorStop(0, isDark ? 'rgba(59, 130, 246, 0.08)' : 'rgba(29, 89, 173, 0.05)')
                gradient.addColorStop(1, 'rgba(0, 0, 0, 0)')
                
                ctx.globalAlpha = 1
                ctx.fillStyle = gradient
                ctx.fillRect(0, 0, rect.width, rect.height)
            }

            // 2. Update and draw particles
            for (let i = 0; i < particles.length; i++) {
                const p = particles[i]

                // Antigravity mouse repulsion
                let targetVx = p.vxBase
                let targetVy = p.vyBase
                
                const dx = p.x - mouse.x
                const dy = p.y - mouse.y
                const dist = Math.sqrt(dx * dx + dy * dy)

                if (dist < MOUSE_RADIUS) {
                    const force = (MOUSE_RADIUS - dist) / MOUSE_RADIUS
                    // Push away from mouse
                    targetVx += (dx / dist) * force * 3
                    targetVy += (dy / dist) * force * 3
                }

                // Smooth velocity interpolation
                p.vx += (targetVx - p.vx) * 0.05
                p.vy += (targetVy - p.vy) * 0.05

                // Apply movement with organic sine waves
                p.x += p.vx + Math.sin(p.phaseX + time * p.freqX) * p.ampX
                p.y += p.vy + Math.cos(p.phaseY + time * p.freqY) * p.ampY

                // Wrap around edges smoothly
                if (p.x < -50) p.x = rect.width + 50
                if (p.x > rect.width + 50) p.x = -50
                if (p.y < -50) p.y = rect.height + 50
                if (p.y > rect.height + 50) p.y = -50

                // Draw connections to nearby particles (Constellation effect)
                for (let j = i + 1; j < particles.length; j++) {
                    const p2 = particles[j]
                    const dx2 = p.x - p2.x
                    const dy2 = p.y - p2.y
                    const dist2 = Math.sqrt(dx2*dx2 + dy2*dy2)
                    
                    if (dist2 < CONNECTION_DISTANCE) {
                        ctx.beginPath()
                        ctx.strokeStyle = p.color
                        // Opacity based on distance
                        ctx.globalAlpha = (1 - dist2 / CONNECTION_DISTANCE) * 0.25
                        ctx.lineWidth = 0.8
                        ctx.moveTo(p.x, p.y)
                        ctx.lineTo(p2.x, p2.y)
                        ctx.stroke()
                    }
                }

                // Draw particle (stroke style)
                const alpha = p.alpha + Math.sin(p.alphaPhase + time * p.alphaFreq) * 0.2
                const angle = Math.atan2(p.vy, p.vx)
                const len = p.size * 2.5

                ctx.save()
                ctx.globalAlpha = Math.max(0.1, Math.min(0.9, alpha))
                
                // Add soft glow to particles
                ctx.shadowBlur = p.size * 2
                ctx.shadowColor = p.color
                
                ctx.strokeStyle = p.color
                ctx.lineWidth = p.size * 0.7
                ctx.lineCap = 'round'
                ctx.beginPath()
                ctx.moveTo(
                    p.x - Math.cos(angle) * len / 2,
                    p.y - Math.sin(angle) * len / 2
                )
                ctx.lineTo(
                    p.x + Math.cos(angle) * len / 2,
                    p.y + Math.sin(angle) * len / 2
                )
                ctx.stroke()
                ctx.restore()
            }

            animationId = requestAnimationFrame(draw)
        }

        // Global mouse tracking
        const handleMouseMove = (e) => {
            mouse.x = e.clientX
            mouse.y = e.clientY
        }
        
        const handleMouseLeave = () => {
            mouse.x = -1000
            mouse.y = -1000
        }

        window.addEventListener('mousemove', handleMouseMove)
        document.body.addEventListener('mouseleave', handleMouseLeave)

        // Listen for theme changes
        const observer = new MutationObserver(() => {
            const colors = getColors()
            particles.forEach(p => {
                p.color = colors[Math.floor(Math.random() * colors.length)]
            })
        })
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['class'],
        })

        init()
        animationId = requestAnimationFrame(draw)

        const handleResize = () => {
            resize()
        }
        window.addEventListener('resize', handleResize)

        return () => {
            cancelAnimationFrame(animationId)
            window.removeEventListener('resize', handleResize)
            window.removeEventListener('mousemove', handleMouseMove)
            document.body.removeEventListener('mouseleave', handleMouseLeave)
            observer.disconnect()
        }
    }, [])

    return (
        <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
        />
    )
}
