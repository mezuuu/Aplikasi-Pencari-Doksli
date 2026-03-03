import Navbar from './Navbar'

export default function Layout({ children }) {
    return (
        <div className="min-h-screen flex flex-col">
            <Navbar />
            <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {children}
            </main>
            <footer className="glass-light py-4 mt-auto">
                <div className="max-w-7xl mx-auto px-4 text-center">
                    <p className="text-xs text-slate-500">
                        © 2026 ImageGuard — Sistem Deteksi Manipulasi Gambar.
                        <span className="hidden sm:inline"> Didukung oleh AI & Google Cloud Vision.</span>
                    </p>
                </div>
            </footer>
        </div>
    )
}
