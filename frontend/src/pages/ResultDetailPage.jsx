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
                <p className="text-sm text-slate-400">Memuat detail...</p>
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
                <span className="text-xs text-slate-500">{dateStr}</span>
            </div>

            {/* Title */}
            <div>
                <h1 className="text-2xl font-bold gradient-text mb-1">Detail Pencarian</h1>
                <p className="text-xs text-slate-500 font-mono">ID: {data.id}</p>
            </div>

            {/* Meta Info */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="card py-3 px-4">
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Sumber</p>
                    <p className="text-sm font-semibold text-slate-200">
                        {data.search_source === 'local' ? 'Lokal' : data.search_source === 'google' ? 'Google' : 'Keduanya'}
                    </p>
                </div>
                <div className="card py-3 px-4">
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Hasil</p>
                    <p className="text-sm font-semibold text-slate-200">{results.length} kecocokan</p>
                </div>
                <div className="card py-3 px-4 col-span-2 sm:col-span-1">
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Hash</p>
                    <p className="text-sm font-mono text-primary-300 truncate">{data.query_hash?.slice(0, 20)}...</p>
                </div>
            </div>

            {/* Privacy Analysis */}
            <PrivacyBadge privacyData={data.privacy_analysis} />

            {/* Results */}
            {results.length > 0 ? (
                <div className="space-y-4">
                    <h2 className="text-lg font-semibold text-slate-200">
                        Hasil Kecocokan ({results.length})
                    </h2>
                    <div className="space-y-3">
                        {results.map((r) => (
                            <ResultCard key={r.id} result={r} />
                        ))}
                    </div>
                </div>
            ) : (
                <div className="card text-center py-8">
                    <p className="text-slate-300 font-medium">Tidak ada kecocokan ditemukan</p>
                </div>
            )}
        </div>
    )
}
