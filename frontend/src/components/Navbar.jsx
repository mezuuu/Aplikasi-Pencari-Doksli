import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'

const navItems = [
    { path: '/', label: 'Analisis Gambar' },
]

export default function Navbar() {
    const [isDark, setIsDark] = useState(false)

    useEffect(() => {
        // Init theme
        const storedTheme = localStorage.getItem('theme')
        if (storedTheme === 'dark' || (!storedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            setIsDark(true)
            document.documentElement.classList.add('dark')
        } else {
            setIsDark(false)
            document.documentElement.classList.remove('dark')
        }
    }, [])

    const toggleTheme = () => {
        if (isDark) {
            document.documentElement.classList.remove('dark')
            localStorage.setItem('theme', 'light')
            setIsDark(false)
        } else {
            document.documentElement.classList.add('dark')
            localStorage.setItem('theme', 'dark')
            setIsDark(true)
        }
    }

    return (
        <nav className="sticky top-0 z-50 glass border-b-0 rounded-none shadow-md">
            <div className="w-full px-4 sm:px-8 lg:px-12">
                <div className="flex items-center justify-between h-16">
                    {/* Logo */}
                    <NavLink to="/" className="flex items-center gap-3 group">
                        <div>
                            <h1 className="text-xl sm:text-2xl font-bold text-royal leading-tight">
                                Pencari Doksli
                            </h1>
                            <p className="text-xs text-navy/60 leading-tight hidden sm:block">
                                Deteksi Manipulasi Gambar
                            </p>
                        </div>
                    </NavLink>

                    {/* Navigation Links & Actions */}
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1">
                            {navItems.map(({ path, label }) => (
                                <NavLink
                                    key={path}
                                    to={path}
                                    end={path === '/'}
                                    className={({ isActive }) =>
                                        `flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-300 ${isActive
                                            ? 'bg-royal/10 text-royal'
                                            : 'text-navy/60 hover:text-navy hover:bg-black/5 dark:hover:bg-white/5'
                                        }`
                                    }
                                >
                                    <span>{label}</span>
                                </NavLink>
                            ))}
                        </div>
                        
                        {/* Theme Toggle Button */}
                        <button 
                            onClick={toggleTheme}
                            className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-navy flex items-center justify-center"
                            aria-label="Toggle Dark Mode"
                        >
                            {isDark ? (
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>
                            ) : (
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </nav>
    )
}
