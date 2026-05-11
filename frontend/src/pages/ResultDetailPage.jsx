import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import PrivacyBadge from '../components/PrivacyBadge'
import ResultCard from '../components/ResultCard'
import { getResultDetail } from '../api/client'

export default function ResultDetailPage() {
    const { searchId } = useParams()
    const navigate = useNavigate()
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [selectedMatch, setSelectedMatch] = useState(null)

    useEffect(() => {
        const fetchDetail = async () => {
            try {
                const response = await getResultDetail(searchId)
                setData(response.data)
            } catch (err) {
                setError(err.response?.data?.error || 'Gagal memuat detail pencarian.')
            } finally {
                setLoading(false)
            }
        }
        fetchDetail()
    }, [searchId])

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20">
                <div className="spinner mb-4"></div>
                <p className="text-sm text-navy/60">Memuat detail...</p>
            </div>
        )
    }

    if (error) {
        return (
            <div className="max-w-2xl mx-auto py-12">
                <div className="card text-center">
                    <p className="text-red-300 font-medium">{error}</p>
                    <button
                        onClick={() => navigate('/')}
                        className="btn-secondary text-sm mt-4"
                    >
                        ← Kembali
                    </button>
                </div>
            </div>
        )
    }

    if (!data) return null

    const results = data.results || []
    const dateStr = new Date(data.created_at).toLocaleDateString('id-ID', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    })

    return (
        <div className="max-w-3xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <button
                    onClick={() => navigate('/')}
                    className="btn-secondary text-sm"
                >
                    ← Kembali
                </button>
                <span className="text-xs text-navy/50">{dateStr}</span>
            </div>

            {/* Title */}
            <div>
                <h1 className="text-2xl font-bold gradient-text mb-1">Detail Pencarian</h1>
                <p className="text-xs text-navy/50 font-mono">ID: {data.id}</p>
            </div>

            {/* Meta Info */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="card py-3 px-4">
                    <p className="text-[10px] text-navy/50 uppercase tracking-wide mb-1">Sumber</p>
                    <p className="text-sm font-semibold text-navy">
                        {data.search_source === 'local' ? 'Lokal' : data.search_source === 'google' ? 'Google' : 'Keduanya'}
                    </p>
                </div>
                <div className="card py-3 px-4">
                    <p className="text-[10px] text-navy/50 uppercase tracking-wide mb-1">Hasil</p>
                    <p className="text-sm font-semibold text-navy">{results.length} kecocokan</p>
                </div>
                <div className="card py-3 px-4 col-span-2 sm:col-span-1">
                    <p className="text-[10px] text-navy/50 uppercase tracking-wide mb-1">Hash</p>
                    <p className="text-sm font-mono text-primary-300 truncate">{data.query_hash?.slice(0, 20)}...</p>
                </div>
            </div>

            {/* Privacy Analysis */}
            <PrivacyBadge privacyData={data.privacy_analysis} />

                {/* Results */}
            {results.length > 0 ? (
                <div className="space-y-4">
                    <h2 className="text-lg font-semibold text-navy">
                        Hasil Kecocokan ({results.length})
                    </h2>
                    <div className="space-y-3">
                        {results.map((r) => (
                            <ResultCard 
                                key={r.id} 
                                result={r} 
                                onClick={() => r.source_type === 'local' && setSelectedMatch(r)}
                            />
                        ))}
                    </div>
                </div>
            ) : (
                <div className="card text-center py-8">
                    <p className="text-navy/80 font-medium">Tidak ada kecocokan ditemukan</p>
                </div>
            )}

            {/* Comparison Modal */}
            {selectedMatch && selectedMatch.matched_document && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
                    {/* Backdrop */}
                    <div 
                        className="absolute inset-0 bg-black/80 backdrop-blur-sm" 
                        onClick={() => setSelectedMatch(null)}
                    ></div>
                    
                    {/* Modal Content */}
                    <div className="relative w-full max-w-6xl max-h-[90vh] bg-[#0f172a] rounded-2xl border border-blue-500/20 shadow-2xl overflow-hidden flex flex-col">
                        
                        {/* Modal Header */}
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h2 className="text-lg font-bold text-white flex items-center gap-2">
                                ⚖️ Perbandingan Gambar
                            </h2>
                            <button 
                                onClick={() => setSelectedMatch(null)}
                                className="w-8 h-8 flex items-center justify-center rounded-full bg-white/10 text-white hover:bg-red-500/80 transition-colors"
                            >
                                ✕
                            </button>
                        </div>

                        {/* Modal Body: Side by Side */}
                        <div className="flex-1 overflow-y-auto p-4 md:p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                            
                            {/* Left: Queried Image (Timpa) */}
                            <div className="flex flex-col gap-3">
                                <div className="flex items-center justify-between">
                                    <span className="px-3 py-1 bg-red-500/20 text-red-300 border border-red-500/30 rounded-lg text-sm font-bold">
                                        Gambar Timpa (Query)
                                    </span>
                                </div>
                                <div className="bg-black/50 rounded-xl border border-white/10 overflow-hidden flex items-center justify-center min-h-[300px]">
                                    <img 
                                        src={data.query_image_url} 
                                        alt="Query Image" 
                                        className="max-w-full max-h-[60vh] object-contain"
                                    />
                                </div>
                            </div>

                            {/* Right: Matched Doksli (Asli) */}
                            <div className="flex flex-col gap-3">
                                <div className="flex items-center justify-between">
                                    <span className="px-3 py-1 bg-green-500/20 text-green-300 border border-green-500/30 rounded-lg text-sm font-bold flex gap-2">
                                        <span>Doksli Tersedia</span>
                                        <span className="bg-green-500/30 px-1.5 rounded text-green-200">
                                            {(selectedMatch.similarity_score * 100).toFixed(1)}% Match
                                        </span>
                                    </span>
                                </div>
                                <div className="bg-black/50 rounded-xl border border-white/10 overflow-hidden flex items-center justify-center min-h-[300px]">
                                    <img 
                                        src={selectedMatch.matched_document.image_url} 
                                        alt="Original Document" 
                                        className="max-w-full max-h-[60vh] object-contain"
                                    />
                                </div>
                                <p className="text-xs text-white/50 font-mono break-all text-center">
                                    ID: {selectedMatch.matched_document.id}
                                </p>
                            </div>

                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
