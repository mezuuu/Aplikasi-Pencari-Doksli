import { useState, useEffect, useCallback } from 'react'
import ImageUpload from '../components/ImageUpload'
import { addOriginal, listOriginals } from '../api/client'

export default function OriginalsPage() {
    const [uploading, setUploading] = useState(false)
    const [uploadResult, setUploadResult] = useState(null)
    const [error, setError] = useState(null)
    const [selectedFile, setSelectedFile] = useState(null)
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
            // Refresh count
            fetchCount()
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

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="text-center space-y-3 py-4">
                <h1 className="text-3xl sm:text-4xl font-extrabold">
                    <span className="gradient-text">Dokumen Asli</span>
                </h1>
                <p className="text-slate-400 text-sm max-w-xl mx-auto">
                    Kelola koleksi dokumen asli untuk perbandingan kemiripan.
                    Upload dokumen baru untuk ditambahkan ke database lokal.
                </p>
            </div>

            {/* Upload Section */}
            <div className="max-w-xl mx-auto space-y-4">
                <ImageUpload
                    onUpload={handleFileSelect}
                    loading={uploading}
                    label="Upload Dokumen Asli"
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
                        <>
                            <span>Tambahkan ke Database</span>
                        </>
                    )}
                </button>

                {/* Upload Result */}
                {uploadResult && (
                    <div className={`p-4 rounded-xl border text-sm ${uploadResult.status === 'success'
                        ? 'bg-green-500/10 border-green-500/20 text-green-300'
                        : uploadResult.status === 'duplicate'
                            ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-300'
                            : 'bg-red-500/10 border-red-500/20 text-red-300'
                        }`}>
                        {uploadResult.message}
                    </div>
                )}

                {/* Error */}
                {error && (
                    <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                        <p className="text-sm text-red-300">{error}</p>
                    </div>
                )}
            </div>

            {/* Document Count */}
            <div className="flex items-center gap-4">
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-primary-500/30 to-transparent"></div>
                <span className="text-xs text-slate-500 font-medium">
                    {docCount} dokumen tersimpan
                </span>
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-primary-500/30 to-transparent"></div>
            </div>
        </div>
    )
}
