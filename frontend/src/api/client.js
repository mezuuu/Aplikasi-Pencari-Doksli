import axios from 'axios'

const client = axios.create({
    baseURL: '/api',
    timeout: 120000, // 2 min timeout for ML processing
})

/**
 * Upload image for search (privacy analysis + similarity search)
 */
export const searchImage = async (imageFile) => {
    const formData = new FormData()
    formData.append('image', imageFile)
    const response = await client.post('/search/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
}

/**
 * Upload original document to the database
 */
export const addOriginal = async (imageFile) => {
    const formData = new FormData()
    formData.append('image', imageFile)
    const response = await client.post('/add-original/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
}

/**
 * Get search result detail
 */
export const getResultDetail = async (searchId) => {
    const response = await client.get(`/results/${searchId}/`)
    return response.data
}

/**
 * List stored original documents
 */
export const listOriginals = async (page = 1) => {
    const response = await client.get('/originals/', { params: { page } })
    return response.data
}

// --- Admin API ---

/**
 * Admin login
 */
export const adminLogin = async (username, password) => {
    const response = await client.post('/admin/login/', { username, password })
    return response.data
}

/**
 * Delete an original document (admin only)
 */
export const deleteOriginal = async (documentId, adminAuth) => {
    const response = await client.delete(`/admin/originals/${documentId}/`, {
        headers: { 'X-Admin-Auth': adminAuth },
    })
    return response.data
}

export default client
