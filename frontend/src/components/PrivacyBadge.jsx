const flagLabels = {
    face_detected: { label: 'Wajah' },
    name_detected: { label: 'Nama' },
    age_detected: { label: 'Umur' },
    address_detected: { label: 'Alamat' },
    phone_detected: { label: 'Telepon' },
}

export default function PrivacyBadge({ privacyData }) {
    if (!privacyData) return null

    const flags = Object.entries(flagLabels)
    const isBlocked = privacyData.is_blocked

    return (
        <div className="card">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                    🔒 Analisis Privasi
                </h3>
                <span className={isBlocked ? 'badge-danger' : 'badge-safe'}>
                    {isBlocked
                        ? `Diblokir (${privacyData.total_flags} flag)`
                        : `Aman (${privacyData.total_flags} flag)`}
                </span>
            </div>

            {/* Flag Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                {flags.map(([key, { label }]) => {
                    const detected = privacyData[key]
                    return (
                        <div
                            key={key}
                            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-300 ${detected
                                ? 'bg-red-500/10 border border-red-500/30 text-red-300'
                                : 'bg-green-500/5 border border-green-500/10 text-green-400/60'
                                }`}
                        >
                            <div>
                                <p>{label}</p>
                                <p className={`text-[10px] ${detected ? 'text-red-400' : 'text-green-500/40'}`}>
                                    {detected ? 'Terdeteksi' : 'Tidak'}
                                </p>
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* Blocked Warning */}
            {isBlocked && (
                <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20">
                    <p className="text-xs text-red-300">
                        Pencarian diblokir karena terdeteksi {privacyData.total_flags} kategori
                        informasi pribadi. Gambar yang mengandung terlalu banyak data personal
                        tidak dapat diproses untuk melindungi privasi.
                    </p>
                </div>
            )}
        </div>
    )
}
