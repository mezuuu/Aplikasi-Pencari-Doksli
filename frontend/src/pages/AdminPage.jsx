import { useState, useEffect, useCallback } from 'react'
import ImageUpload from '../components/ImageUpload'
import { adminLogin, addOriginal, deleteOriginal, listOriginals } from '../api/client'

export default function AdminPage() {
    // Auth state
    const [isLoggedIn, setIsLoggedIn] = useState(false)
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [loginError, setLoginError] = useState(null)
    const [loginLoading, setLoginLoading] = useState(false)

    // Dashboard state
    const [documents, setDocuments] = useState([])
    const [loading, setLoading] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [uploadResult, setUploadResult] = useState(null)
    const [selectedFile, setSelectedFile] = useState(null)
    const [error, setError] = useState(null)
    const [deletingId, setDeletingId] = useState(null)
    const [page, setPage] = useState(1)
    const [pagination, setPagination] = useState({ next: null, previous: null, count: 0 })

    const adminAuth = `${username}:${password}`

    const fetchDocuments = useCallback(async (pageNum = 1) => {
        setLoading(true)
        try {
            const response = await listOriginals(pageNum)
            setDocuments(response.results || response.data || [])
            setPagination({
                next: response.next,
                previous: response.previous,
                count: response.count || 0,
            })
            setPage(pageNum)
        } catch (err) {
            setError('Gagal memuat dokumen.')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        if (isLoggedIn) {
            fetchDocuments()
        }
    }, [isLoggedIn, fetchDocuments])

    // --- Login ---
    const handleLogin = async (e) => {
        e.preventDefault()
        setLoginLoading(true)
        setLoginError(null)

        try {
            await adminLogin(username, password)
            setIsLoggedIn(true)
        } catch (err) {
            setLoginError(err.response?.data?.error || 'Login gagal.')
        } finally {
            setLoginLoading(false)
        }
    }

    const handleLogout = () => {
        setIsLoggedIn(false)
        setUsername('')
        setPassword('')
        setDocuments([])
    }

    // --- Upload ---
    const handleFileSelect = (file) => {
        setSelectedFile(file)
        setUploadResult(null)
        setError(null)
    }

    const handleUpload = async () => {
        if (!selectedFile) return

        setUploading(true)
        setUploadResult(null)
        setError(null)

        try {
            const data = await addOriginal(selectedFile)
            setUploadResult(data)
            setSelectedFile(null)
            fetchDocuments(1)
        } catch (err) {
            const errData = err.response?.data
            if (err.response?.status === 409) {
                setUploadResult(errData)
            } else {
                setError(errData?.error || 'Gagal mengunggah dokumen.')
            }
        } finally {
            setUploading(false)
        }
    }

    // --- Delete ---
    const handleDelete = async (docId) => {
        if (!window.confirm('Yakin ingin menghapus dokumen ini?')) return

        setDeletingId(docId)
        try {
            await deleteOriginal(docId, adminAuth)
            fetchDocuments(page)
        } catch (err) {
            setError(err.response?.data?.error || 'Gagal menghapus dokumen.')
        } finally {
            setDeletingId(null)
        }
    }

    // =================== LOGIN PAGE ===================
    if (!isLoggedIn) {
        return (
            <div className="flex items-center justify-center min-h-[70vh]">
                <div className="card w-full max-w-md">
                    <div className="text-center mb-6">
                        <h1 className="text-2xl font-extrabold">
                            <span className="gradient-text">Admin Login</span>
                        </h1>
                        <p className="text-slate-400 text-sm mt-2">
                            Masuk untuk mengelola database dokumen asli.
                        </p>
                    </div>

                    <form onSubmit={handleLogin} className="space-y-4">
                        <div>
                            <label className="block text-xs text-slate-400 font-medium mb-1.5 uppercase tracking-wider">
                                Username
                            </label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full px-4 py-3 rounded-xl bg-surface-800 border border-surface-600
                                           text-slate-200 placeholder-slate-500 text-sm
                                           focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/50
                                           transition-colors"
                                placeholder="Masukkan username"
                                required
                                autoFocus
                            />
                        </div>

                        <div>
                            <label className="block text-xs text-slate-400 font-medium mb-1.5 uppercase tracking-wider">
                                Password
                            </label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-4 py-3 rounded-xl bg-surface-800 border border-surface-600
                                           text-slate-200 placeholder-slate-500 text-sm
                                           focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/50
                                           transition-colors"
                                placeholder="Masukkan password"
                                required
                            />
                        </div>

                        {loginError && (
                            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20">
                                <p className="text-sm text-red-300">{loginError}</p>
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={loginLoading || !username || !password}
                            className="btn-primary w-full flex items-center justify-center gap-2"
                        >
                            {loginLoading ? (
                                <>
                                    <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }}></div>
                                    <span>Memproses...</span>
                                </>
                            ) : (
                                <span>Masuk</span>
                            )}
                        </button>
                    </form>
                </div>
            </div>
        )
    }

    // =================== ADMIN DASHBOARD ===================
    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-extrabold">
                        <span className="gradient-text">Admin Panel</span>
                    </h1>
                    <p className="text-slate-400 text-sm mt-1">
                        Kelola database dokumen asli
                    </p>
                </div>
                <button onClick={handleLogout} className="btn-secondary text-sm">
                    Logout
                </button>
            </div>

            {/* Upload Section */}
            <div className="card">
                <h2 className="text-lg font-semibold text-slate-200 mb-4">Tambah Dokumen</h2>
                <div className="space-y-4">
                    <ImageUpload
                        onUpload={handleFileSelect}
                        loading={uploading}
                        label="Upload Gambar Dokumen Asli"
                    />

                    <button
                        onClick={handleUpload}
                        disabled={!selectedFile || uploading}
                        className="btn-primary w-full flex items-center justify-center gap-2"
                    >
                        {uploading ? (
                            <>
                                <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }}></div>
                                <span>Mengunggah...</span>
                            </>
                        ) : (
                            <span>Tambahkan ke Database</span>
                        )}
                    </button>

                    {uploadResult && (
                        <div className={`p-3 rounded-xl border text-sm ${uploadResult.status === 'success'
                            ? 'bg-green-500/10 border-green-500/20 text-green-300'
                            : uploadResult.status === 'duplicate'
                                ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-300'
                                : 'bg-red-500/10 border-red-500/20 text-red-300'
                            }`}>
                            {uploadResult.message}
                        </div>
                    )}
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                    <p className="text-sm text-red-300">{error}</p>
                </div>
            )}

            {/* Document Count */}
            <div className="flex items-center gap-4">
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-primary-500/30 to-transparent"></div>
                <span className="text-xs text-slate-500 font-medium">
                    {pagination.count} dokumen tersimpan
                </span>
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-primary-500/30 to-transparent"></div>
            </div>

            {/* Documents Table */}
            {loading ? (
                <div className="flex justify-center py-12">
                    <div className="spinner"></div>
                </div>
            ) : documents.length > 0 ? (
                <>
                    <div className="space-y-3">
                        {documents.map((doc) => (
                            <div key={doc.id} className="card flex items-center gap-4">
                                {/* Thumbnail */}
                                <div className="shrink-0 w-16 h-16 rounded-lg bg-surface-800 overflow-hidden">
                                    {doc.image_url ? (
                                        <img
                                            src={doc.image_url}
                                            alt="Dokumen"
                                            className="w-full h-full object-cover"
                                        />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-slate-600 text-xs">
                                            No img
                                        </div>
                                    )}
                                </div>

                                {/* Info */}
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-slate-200 font-mono truncate">
                                        {doc.file_hash?.slice(0, 24)}...
                                    </p>
                                    <p className="text-xs text-slate-500 mt-0.5">
                                        ID: {doc.id?.slice(0, 8)}... | {new Date(doc.created_at).toLocaleDateString('id-ID')}
                                    </p>
                                </div>

                                {/* Delete Button */}
                                <button
                                    onClick={() => handleDelete(doc.id)}
                                    disabled={deletingId === doc.id}
                                    className="shrink-0 px-4 py-2 rounded-lg text-xs font-semibold
                                               bg-red-500/10 text-red-300 border border-red-500/30
                                               hover:bg-red-500/20 transition-colors
                                               disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {deletingId === doc.id ? (
                                        <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div>
                                    ) : (
                                        'Hapus'
                                    )}
                                </button>
                            </div>
                        ))}
                    </div>

                    {/* Pagination */}
                    {(pagination.next || pagination.previous) && (
                        <div className="flex justify-center gap-3">
                            <button
                                onClick={() => fetchDocuments(page - 1)}
                                disabled={!pagination.previous}
                                className="btn-secondary text-sm disabled:opacity-30"
                            >
                                Sebelumnya
                            </button>
                            <span className="flex items-center text-xs text-slate-500">
                                Halaman {page}
                            </span>
                            <button
                                onClick={() => fetchDocuments(page + 1)}
                                disabled={!pagination.next}
                                className="btn-secondary text-sm disabled:opacity-30"
                            >
                                Selanjutnya
                            </button>
                        </div>
                    )}
                </>
            ) : (
                <div className="card text-center py-12">
                    <p className="text-slate-300 font-medium mb-1">Belum ada dokumen</p>
                    <p className="text-xs text-slate-500">
                        Upload dokumen asli pertama melalui form di atas.
                    </p>
                </div>
            )}
        </div>
    )
}
