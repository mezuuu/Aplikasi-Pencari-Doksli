import { useState, useRef, useCallback } from 'react'

export default function ImageUpload({ onUpload, loading = false, label = 'Upload Gambar' }) {
    const [preview, setPreview] = useState(null)
    const [dragActive, setDragActive] = useState(false)
    const [fileName, setFileName] = useState('')
    const inputRef = useRef(null)

    const handleFile = useCallback((file) => {
        if (!file) return
        if (!file.type.startsWith('image/')) {
            alert('Hanya file gambar yang diizinkan (JPG, PNG, WEBP)')
            return
        }
        setFileName(file.name)
        const reader = new FileReader()
        reader.onload = (e) => setPreview(e.target.result)
        reader.readAsDataURL(file)
        onUpload?.(file)
    }, [onUpload])

    const handleDrop = useCallback((e) => {
        e.preventDefault()
        e.stopPropagation()
        setDragActive(false)
        if (e.dataTransfer.files?.[0]) {
            handleFile(e.dataTransfer.files[0])
        }
    }, [handleFile])

    const handleDrag = useCallback((e) => {
        e.preventDefault()
        e.stopPropagation()
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true)
        } else if (e.type === 'dragleave') {
            setDragActive(false)
        }
    }, [])

    const handleChange = (e) => {
        if (e.target.files?.[0]) {
            handleFile(e.target.files[0])
        }
    }

    const clearPreview = () => {
        setPreview(null)
        setFileName('')
        if (inputRef.current) inputRef.current.value = ''
    }

    return (
        <div className="w-full">
            <label className="block text-sm font-medium text-slate-300 mb-2">
                {label}
            </label>

            <div
                className={`relative rounded-2xl border-2 border-dashed transition-all duration-300 cursor-pointer overflow-hidden ${dragActive
                    ? 'border-primary-400 bg-primary-500/10 scale-[1.02]'
                    : preview
                        ? 'border-primary-500/30 bg-surface-800/50'
                        : 'border-slate-600 hover:border-primary-500/50 bg-surface-800/30 hover:bg-primary-500/5'
                    } ${loading ? 'pointer-events-none opacity-60' : ''}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => !preview && inputRef.current?.click()}
            >
                <input
                    ref={inputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleChange}
                    className="hidden"
                />

                {preview ? (
                    <div className="p-4">
                        <div className="relative group">
                            <img
                                src={preview}
                                alt="Preview"
                                className="w-full max-h-72 object-contain rounded-xl mx-auto"
                            />
                            {/* Overlay on hover */}
                            <div className="absolute inset-0 bg-black/50 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center">
                                <button
                                    onClick={(e) => { e.stopPropagation(); clearPreview(); }}
                                    className="btn-secondary text-sm"
                                >
                                    Hapus
                                </button>
                            </div>
                        </div>
                        <p className="text-xs text-slate-400 text-center mt-3 truncate">
                            {fileName}
                        </p>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-12 px-6">
                        <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4 text-3xl"
                            style={{ background: 'var(--gradient-card)' }}>
                        </div>
                        <p className="text-base font-medium text-slate-300 mb-1">
                            {dragActive ? 'Lepas gambar di sini...' : 'Seret & lepas gambar'}
                        </p>
                        <p className="text-sm text-slate-500">
                            atau <span className="text-primary-400 underline">pilih file</span>
                        </p>
                        <p className="text-xs text-slate-600 mt-2">
                            JPG, PNG, WEBP — Maks 10MB
                        </p>
                    </div>
                )}

                {/* Loading overlay */}
                {loading && (
                    <div className="absolute inset-0 bg-surface-900/80 backdrop-blur-sm flex flex-col items-center justify-center rounded-2xl">
                        <div className="spinner mb-3"></div>
                        <p className="text-sm text-primary-300 font-medium animate-pulse">
                            Menganalisis gambar...
                        </p>
                    </div>
                )}
            </div>
        </div>
    )
}
