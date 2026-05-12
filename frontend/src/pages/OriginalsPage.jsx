import { useState, useEffect, useCallback } from 'react'
import { listOriginals } from '../api/client'

export default function OriginalsPage() {
    const [docCount, setDocCount] = useState(0)

    // Fetch only the count of documents
    const fetchCount = useCallback(async () => {
        try {
            const response = await listOriginals(1)
            setDocCount(response.count || 0)
        } catch (err) {
            // Silently ignore count fetch errors
        }
    }, [])

    useEffect(() => {
        fetchCount()
    }, [fetchCount])

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="text-center space-y-3 py-4">
                <h1 className="text-3xl sm:text-4xl font-extrabold">
                    <span className="gradient-text">Dokumen Asli</span>
                </h1>
                <p className="text-slate-400 text-sm max-w-xl mx-auto">
                    Koleksi dokumen asli yang tersimpan di database untuk perbandingan kemiripan.
                    Pengelolaan dokumen dilakukan melalui Admin Panel.
                </p>
            </div>

            {/* Info Card */}
            <div className="max-w-xl mx-auto">
                <div className="card text-center py-8">
                    <div className="text-4xl mb-3"></div>
                    <p className="text-lg font-semibold text-slate-200 mb-1">
                        {docCount} dokumen tersimpan
                    </p>
                    <p className="text-xs text-slate-500">
                        Untuk menambah atau menghapus dokumen, silakan masuk melalui Admin Panel.
                    </p>
                </div>
            </div>

            {/* Document Count Divider */}
            <div className="flex items-center gap-4">
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-primary-500/30 to-transparent"></div>
                <span className="text-xs text-slate-500 font-medium">
                    Database Dokumen Asli
                </span>
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-primary-500/30 to-transparent"></div>
            </div>
        </div>
    )
}
