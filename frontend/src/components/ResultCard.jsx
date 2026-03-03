export default function ResultCard({ result }) {
    if (!result) return null

    const isLocal = result.source_type === 'local'
    const scorePercent = (result.similarity_score * 100).toFixed(1)

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

    return (
        <div className="card group">
            <div className="flex items-start gap-4">
                {/* Source badge */}
                <div className={`shrink-0 px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider ${isLocal
                    ? 'bg-primary-500/15 text-primary-300 border border-primary-500/30'
                    : 'bg-accent-500/15 text-accent-300 border border-accent-500/30'
                    }`}>
                    {isLocal ? 'Lokal' : 'Google'}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    {isLocal && result.matched_document ? (
                        <div>
                            <p className="text-sm font-medium text-slate-200 truncate">
                                Dokumen: {result.matched_document.file_hash?.slice(0, 16)}...
                            </p>
                            <p className="text-xs text-slate-500 mt-1">
                                ID: {result.matched_document.id?.slice(0, 8)}...
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
                            >
                                {result.external_url}
                            </a>
                            <p className="text-xs text-slate-500 mt-1">Sumber eksternal</p>
                        </div>
                    )}
                </div>

                {/* Score */}
                <div className={`shrink-0 px-3 py-2 rounded-xl border text-center ${getScoreBg(result.similarity_score)}`}>
                    <p className={`text-lg font-bold ${getScoreColor(result.similarity_score)}`}>
                        {scorePercent}%
                    </p>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide">Similarity</p>
                </div>
            </div>

            {/* Similarity bar */}
            <div className="mt-3 h-1.5 rounded-full bg-surface-800 overflow-hidden">
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
