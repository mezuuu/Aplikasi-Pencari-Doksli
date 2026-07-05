import { getImageUrl } from '../api/client'

export default function ResultCard({ result, onClick }) {
    if (!result) return null

    const isLocal = result.source_type === 'local'
    const scorePercent = (result.similarity_score * 100).toFixed(1)

    // Any result with a displayable image can be clicked for comparison
    const hasImage = !!(result.matched_image_url || result.matched_document?.image_url)
    const isClickable = hasImage && onClick

    // Color based on similarity score
    const getScoreColor = (score) => {
        if (score >= 0.9) return 'text-red-400'
        if (score >= 0.7) return 'text-yellow-400'
        return 'text-green-400'
    }

    const getScoreBg = (score) => {
        if (score >= 0.9) return 'bg-red-500/10 border-red-500/30'
        if (score >= 0.7) return 'bg-yellow-500/10 border-yellow-500/30'
        return 'bg-green-500/10 border-green-500/30'
    }

    // Source label
    const sourceLabel = isLocal ? 'Lokal' : result.source_type === 'bing' ? 'Bing' : 'Google'

    // Image URL to display (works for both local and web results)
    const imageUrl = getImageUrl(result.matched_image_url || result.matched_document?.image_url)

    return (
        <div 
            onClick={isClickable ? onClick : undefined}
            className={`card group ${isClickable ? 'cursor-pointer hover:border-primary-400 hover:shadow-[0_0_15px_rgba(59,130,246,0.2)]' : ''}`}
        >
            <div className="flex items-start gap-4">
                {/* Thumbnail */}
                {imageUrl && (
                    <div className="shrink-0 w-16 h-16 rounded-lg bg-black/5 dark:bg-white/5 overflow-hidden border border-white/10">
                        <img
                            src={imageUrl}
                            alt="Hasil pencarian"
                            className="w-full h-full object-cover"
                            loading="lazy"
                        />
                    </div>
                )}

                {/* Source badge */}
                <div className={`shrink-0 px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider ${isLocal
                    ? 'bg-primary-500/15 text-primary-300 border border-primary-500/30'
                    : 'bg-accent-500/15 text-accent-300 border border-accent-500/30'
                    }`}>
                    {sourceLabel}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    {isLocal && result.matched_document ? (
                        <div>
                            <p className="text-sm font-medium text-navy truncate">
                                Dokumen: {result.matched_document.file_hash?.slice(0, 16)}...
                            </p>
                            <p className="text-xs text-navy/50 mt-1">
                                ID: {result.matched_document.id?.slice(0, 8)}...
                            </p>
                        </div>
                    ) : hasImage ? (
                        <div>
                            <p className="text-sm font-medium text-navy truncate">
                                Kandidat dari web ({sourceLabel})
                            </p>
                            <p className="text-xs text-navy/50 mt-1">
                                Klik untuk membandingkan gambar
                            </p>
                        </div>
                    ) : (
                        <div>
                            <a
                                href={result.external_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm font-medium text-primary-300 hover:text-primary-200 
                           underline underline-offset-2 truncate block transition-colors"
                                onClick={(e) => e.stopPropagation()}
                            >
                                {result.external_url}
                            </a>
                            <p className="text-xs text-navy/50 mt-1">Sumber eksternal</p>
                        </div>
                    )}
                </div>

                {/* Score */}
                <div className={`shrink-0 px-3 py-2 rounded-xl border text-center ${getScoreBg(result.similarity_score)}`}>
                    <p className={`text-lg font-bold ${getScoreColor(result.similarity_score)}`}>
                        {scorePercent}%
                    </p>
                    <p className="text-[10px] text-navy/50 uppercase tracking-wide">Similarity</p>
                </div>
            </div>

            {/* Similarity bar */}
            <div className="mt-3 h-1.5 rounded-full bg-black/5 dark:bg-white/5 overflow-hidden">
                <div
                    className="h-full rounded-full transition-all duration-700 ease-out"
                    style={{
                        width: `${scorePercent}%`,
                        background: result.similarity_score >= 0.9
                            ? 'linear-gradient(90deg, #ef4444, #f87171)'
                            : result.similarity_score >= 0.7
                                ? 'linear-gradient(90deg, #eab308, #fde047)'
                                : 'linear-gradient(90deg, #22c55e, #86efac)',
                    }}
                />
            </div>
        </div>
    )
}
