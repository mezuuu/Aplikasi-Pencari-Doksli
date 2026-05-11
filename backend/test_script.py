
text = ''
ADDRESS_KEYWORDS = [
    'jl', 'jl.', 'jalan',
    'rt', 'rt.', 'rw', 'rw.',
    'rt/', 'rw/',
    'no', 'no.',
    'kecamatan', 'kec', 'kec.',
    'kelurahan', 'kel', 'kel.',
    'kabupaten', 'kab', 'kab.',
    'kota', 'provinsi', 'prov',
    'desa', 'dusun',
    'gang', 'gg', 'gg.',
    'blok', 'gedung',
    'perumahan', 'perum',
    'komplek', 'kompleks',
]

text_lower = text.lower()
matches = [kw for kw in ADDRESS_KEYWORDS if kw in text_lower]
print('Address Matches:', matches)

import re
name_indicators = re.compile(
        r'(?:nama|name|an\.|a\.n\.?|narna|hama|noma|nam\w|\wama)\s*[:.\-]?\s*([A-Za-z\s\.]{3,40})',
        re.IGNORECASE
    )
print('Name Matches:', name_indicators.findall(text))
