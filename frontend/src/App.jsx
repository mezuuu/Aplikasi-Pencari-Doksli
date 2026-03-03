import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import SearchPage from './pages/SearchPage'
import ResultDetailPage from './pages/ResultDetailPage'
import OriginalsPage from './pages/OriginalsPage'
import AdminPage from './pages/AdminPage'

function App() {
    return (
        <Router>
            <Layout>
                <Routes>
                    <Route path="/" element={<SearchPage />} />
                    <Route path="/results/:searchId" element={<ResultDetailPage />} />
                    <Route path="/originals" element={<OriginalsPage />} />
                    <Route path="/admin" element={<AdminPage />} />
                </Routes>
            </Layout>
        </Router>
    )
}

export default App
