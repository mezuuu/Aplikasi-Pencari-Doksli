import Navbar from './Navbar'
import ParticleBackground from './ParticleBackground'

export default function Layout({ children }) {
    return (
        <div className="min-h-screen flex flex-col relative font-sans w-full" style={{ backgroundColor: 'var(--bg-color)' }}>
            {/* Particle Background — fixed to cover entire screen behind everything */}
            <div className="fixed inset-0 z-0 pointer-events-none">
                <ParticleBackground />
            </div>

            <Navbar />
            
            <main className="relative z-10 flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-12">
                {children}
            </main>
            
            <footer className="relative z-10 py-8 mt-auto border-t w-full" style={{ borderColor: 'var(--glass-border)', backgroundColor: 'var(--glass-bg)' }}>
                <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-4 text-xs font-medium" style={{ color: 'var(--text-color)', opacity: 0.5 }}>
                    <div className="flex items-center gap-2">
                        <span className="font-display font-bold">Pencari Doksli</span>
                        <span>© 2026</span>
                    </div>
                    <div className="flex gap-6">
                        <span className="cursor-pointer">Didukung oleh AI & Google Cloud Vision</span>
                    </div>
                </div>
            </footer>
        </div>
    )
}

