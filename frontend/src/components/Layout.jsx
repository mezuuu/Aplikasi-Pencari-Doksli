import Navbar from './Navbar'

export default function Layout({ children }) {
    return (
        <div className="min-h-screen flex flex-col">
            <Navbar />
            <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {children}
            </main>
            <footer className="py-4 mt-auto border-t" style={{ background: 'rgba(30, 41, 59, 0.5)', borderColor: 'rgba(99, 102, 241, 0.1)' }}>
                <div className="max-w-7xl mx-auto px-4 text-center">
                    <p className="text-xs text-slate-500">
                        © 2026 Pencari Doksli — Sistem Deteksi Manipulasi Gambar.
                        <span className="hidden sm:inline"> Didukung oleh AI & Google Cloud Vision.</span>
                    </p>
                </div>
            </footer>
        </div>
    )
}
