import os, cv2
from services.similarity_service import phash_similarity, orb_similarity, histogram_similarity, cosine_similarity
from services.embedding_service import extract_embedding
from services.online_search_service import _download_candidate_images

query = r'D:\Coding\Capstone Project\backend\media\queries\c3c1efcce51843da8976fdea74b1a924.jpg'

urls = [
    'https://cdn5.telesco.pe/file/BufsMBlxwmEhL0RN_4UsfVqqj2fcmdZ344bCYyMBg5VHbZiBzuBL4_bMudqoo_XjI-Fr58wrKfTIXlSO_q1z3KBZO50WfNWa5XssaAVM1e7ASwIaOOpBUOoyFgRNdvcACOiNOAt8GdKzCEuJm4_d357MjbAAubB7-uGg6o4ImrlQGk5jpKzbZoffie76bem6ZJf_W_7sjn47jx66PPsWtA8XVFQpzLhfJTlql0j7zUfgQhzzmMxaOB3TPEcWTUJti6m9FvDqxzGR3espnsQDRvNfefTE7grIkKdWVaxckmzAtkmG4QK0aMPvGVZ9I8f1R8Sr44IMXRaDtJQir_Ekow.jpg',
    'https://www.balipost.com/wp-content/uploads/2025/03/balipostcom_bgn-butuh-tambahan-rp25-triliunbulan-layani-penerima-mbg_01.jpg',
    'https://cdn.antaranews.com/cache/1200x800/2025/03/03/20250303_143712_1.jpg',
    'https://i.ytimg.com/vi/LaG6kf-ss88/maxresdefault.jpg'
]

print("Downloading candidates...")
candidates = _download_candidate_images(urls, 4)

print("\nScoring candidates against query:")
q_emb = extract_embedding(query)

for c in candidates:
    path = c['path']
    if not path or not os.path.exists(path):
        continue
    
    ph = phash_similarity(query, path)
    orb = orb_similarity(query, path)
    hist = histogram_similarity(query, path)
    
    c_emb = extract_embedding(path)
    emb = cosine_similarity(q_emb, c_emb)
    
    total = 0.3 * ph + 0.3 * orb + 0.2 * hist + 0.2 * emb
    
    print(f"\nURL: {c['url']}")
    print(f"Total: {total:.4f} | pHash: {ph:.4f} | ORB: {orb:.4f} | Hist: {hist:.4f} | Emb: {emb:.4f}")
