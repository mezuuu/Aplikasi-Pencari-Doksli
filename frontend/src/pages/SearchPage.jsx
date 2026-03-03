import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import ImageUpload from '../components/ImageUpload'
import PrivacyBadge from '../components/PrivacyBadge'
import ResultCard from '../components/ResultCard'
import { searchImage } from '../api/client'

export default function SearchPage() {
    const navigate = useNavigate()
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)
    const [selectedFile, setSelectedFile] = useState(null)

    // Create a preview URL from the selected file
    const queryPreviewUrl = useMemo(() => {
        if (selectedFile) return URL.createObjectURL(selectedFile)
        return null
    }, [selectedFile])

    const handleFileSelect = (file) => {
        setSelectedFile(file)
        setResult(null)
        setError(null)
    }

    const handleSearch = async () => {
        if (!selectedFile) return

        setLoading(true)
        setError(null)
        setResult(null)

        try {
            const data = await searchImage(selectedFile)
            setResult(data)
        } catch (err) {
            const errData = err.response?.data
            if (err.response?.status === 403 && errData?.status === 'blocked') {
                // Blocked by privacy filter — still show the result for UI
                setResult(errData)
            } else {
                setError(errData?.error || 'Terjadi kesalahan saat menganalisis gambar.')
            }
        } finally {
            setLoading(false)
        }
    }

    const searchData = result?.data
    const isBlocked = result?.status === 'blocked'
    const results = searchData?.results || []

    // Find the best local match for side-by-side comparison
    const bestLocalMatch = results.find(
        (r) => r.source_type === 'local' && r.matched_document?.image_url
    )

    return (
        <div className="space-y-8">
            {/* Hero Section */}
            <div className="text-center space-y-4 py-4">
                <h1 className="text-3xl sm:text-4xl font-extrabold">
                    <span className="gradient-text">Analisis Gambar</span>
                </h1>
                <p className="text-slate-400 text-sm sm:text-base max-w-2xl mx-auto">
                    Upload gambar untuk menganalisis keaslian dan mencari kemiripan
                    dengan dokumen yang tersimpan. Sistem akan memeriksa privasi
                    sebelum melakukan pencarian.
                </p>
            </div>

            {/* Upload Section */}
            <div className="max-w-2xl mx-auto space-y-4">
                <ImageUpload
                    onUpload={handleFileSelect}
                    loading={loading}
                    label="Upload Gambar untuk Dianalisis"
                />

                <button
                    onClick={handleSearch}
                    disabled={!selectedFile || loading}
                    className="btn-primary w-full flex items-center justify-center gap-2"
                >
                    {loading ? (
                        <>
                            <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }}></div>
                            <span>Memproses...</span>
                        </>
                    ) : (
                        <>
                            <span>Mulai Analisis</span>
                        </>
                    )}
                </button>
            </div>

            {/* Error */}
            {error && (
                <div className="max-w-2xl mx-auto p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                    <p className="text-sm text-red-300">{error}</p>
                </div>
            )}

            {/* Results */}
            {searchData && (
                <div className="max-w-4xl mx-auto space-y-6 animate-in">
                    {/* Privacy Analysis */}
                    <PrivacyBadge privacyData={searchData.privacy_analysis} />

                    {/* Side-by-Side Image Comparison */}
                    {!isBlocked && bestLocalMatch && queryPreviewUrl && (
                        <div className="card">
                            <h2 className="text-lg font-semibold text-slate-200 mb-4 text-center">
                                Perbandingan Gambar
                            </h2>
                            <div className="flex items-stretch gap-0 rounded-xl overflow-hidden">
                                {/* Left — Query Image */}
                                <div className="flex-1 flex flex-col items-center">
                                    <p className="text-xs text-slate-400 font-medium mb-2 uppercase tracking-wider">
                                        Gambar yang Dianalisis
                                    </p>
                                    <div className="w-full aspect-square bg-surface-800 rounded-xl overflow-hidden flex items-center justify-center">
                                        <img
                                            src={queryPreviewUrl}
                                            alt="Gambar yang dianalisis"
                                            className="w-full h-full object-contain"
                                        />
                                    </div>
                                </div>

                                {/* Separator */}
                                <div className="w-px bg-slate-600 mx-4 self-stretch"></div>

                                {/* Right — Matched Document Image */}
                                <div className="flex-1 flex flex-col items-center">
                                    <p className="text-xs text-slate-400 font-medium mb-2 uppercase tracking-wider">
                                        Gambar Doksli
                                    </p>
                                    <div className="w-full aspect-square bg-surface-800 rounded-xl overflow-hidden flex items-center justify-center">
                                        <img
                                            src={bestLocalMatch.matched_document.image_url}
                                            alt="Dokumen asli yang cocok"
                                            className="w-full h-full object-contain"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Search Results */}
                    {!isBlocked && results.length > 0 && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <h2 className="text-lg font-semibold text-slate-200">
                                    Hasil Pencarian
                                </h2>
                                <span className="text-xs text-slate-500">
                                    {results.length} hasil ditemukan
                                </span>
                            </div>
                            <div className="space-y-3">
                                {results.map((r) => (
                                    <ResultCard key={r.id} result={r} />
                                ))}
                            </div>
                        </div>
                    )}

                    {/* No results */}
                    {!isBlocked && results.length === 0 && (
                        <div className="card text-center py-8">
                            <p className="text-slate-300 font-medium">Tidak ditemukan kecocokan</p>
                            <p className="text-xs text-slate-500 mt-1">
                                Gambar ini tidak ditemukan di database lokal maupun web.
                            </p>
                        </div>
                    )}

                    {/* View Detail Link */}
                    {searchData.id && (
                        <div className="text-center">
                            <button
                                onClick={() => navigate(`/results/${searchData.id}`)}
                                className="btn-secondary text-sm"
                            >
                                Lihat Selengkapnya
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Feature Cards */}
            {!result && !loading && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-12">
                    {[
                        {
                            icon: '',
                            title: 'Analisis Privasi',
                            desc: 'Deteksi wajah, nama, umur, alamat, dan nomor telepon secara otomatis.',
                        },
                        {
                            icon: '',
                            title: 'AI Similarity',
                            desc: 'Bandingkan dengan database menggunakan CNN embedding & cosine similarity.',
                        },
                        {
                            icon: '',
                            title: 'Web Detection',
                            desc: 'Fallback ke Google Vision API untuk pencarian web yang lebih luas.',
                        },
                    ].map((feature, i) => (
                        <div key={i} className="card text-center">
                            <div className="text-3xl mb-3">{feature.icon}</div>
                            <h3 className="text-sm font-semibold text-slate-200 mb-1">{feature.title}</h3>
                            <p className="text-xs text-slate-500">{feature.desc}</p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
