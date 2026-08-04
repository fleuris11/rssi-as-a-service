import { Outlet } from 'react-router-dom'
import NavBar from './NavBar'

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
