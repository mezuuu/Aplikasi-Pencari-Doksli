import { NavLink } from 'react-router-dom'

const navItems = [
    { path: '/', label: 'Analisis Gambar', icon: '' },
    { path: '/originals', label: 'Dokumen Asli', icon: '' },
]

export default function Navbar() {
    return (
        <nav className="glass sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                    {/* Logo */}
                    <NavLink to="/" className="flex items-center gap-3 group">
                        <div>
                            <h1 className="text-sm sm:text-base font-bold gradient-text leading-tight">
                                Pencari Doksli
                            </h1>
                            <p className="text-[10px] text-slate-500 leading-tight hidden sm:block">
                                Deteksi Manipulasi Gambar
                            </p>
                        </div>
                    </NavLink>

                    {/* Navigation Links */}
                    <div className="flex items-center gap-1">
                        {navItems.map(({ path, label, icon }) => (
                            <NavLink
                                key={path}
                                to={path}
                                end={path === '/'}
                                className={({ isActive }) =>
                                    `flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 ${isActive
                                        ? 'bg-primary-600/20 text-primary-300 border border-primary-500/30'
                                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                                    }`
                                }
                            >
                                <span>{label}</span>
                            </NavLink>
                        ))}
                    </div>
                </div>
            </div>
        </nav>
    )
}
