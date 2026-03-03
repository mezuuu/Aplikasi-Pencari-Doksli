export default function DocumentCard({ document }) {
    if (!document) return null

    const dateStr = new Date(document.created_at).toLocaleDateString('id-ID', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    })

    return (
        <div className="card group cursor-default">
            {/* Hash badge */}
            <div className="flex items-center justify-between mb-3">
                <span className="px-2 py-1 rounded-lg bg-primary-500/10 border border-primary-500/20 
                         text-xs font-mono text-primary-300">
                    #{document.file_hash?.slice(0, 12)}
                </span>
                {document.label_count > 0 && (
                    <span className="badge-warning">
                        {document.label_count} label
                    </span>
                )}
            </div>

            {/* Thumbnail */}
            <div className="rounded-xl overflow-hidden bg-surface-800 mb-3 aspect-video flex items-center justify-center">
                {document.image_path ? (
                    <img
                        src={`/media/${document.image_path.split('/media/').pop() || ''}`}
                        alt="Document"
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                        onError={(e) => {
                            e.target.style.display = 'none'
                            e.target.nextSibling.style.display = 'flex'
                        }}
                    />
                ) : null}
                <div className="hidden items-center justify-center text-4xl text-slate-600"
                    style={document.image_path ? { display: 'none' } : { display: 'flex' }}>
                </div>
            </div>

            {/* Meta info */}
            <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="flex items-center gap-1">
                    {dateStr}
                </span>
                <span className="text-primary-400/60 font-mono">
                    {document.id?.slice(0, 8)}
                </span>
            </div>
        </div>
    )
}
