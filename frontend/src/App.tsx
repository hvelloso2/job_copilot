import { BriefcaseBusiness } from 'lucide-react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'

import { Toaster } from '@/components/ui/sonner'
import { cn } from '@/lib/utils'
import BoardPage from '@/pages/BoardPage'
import JobPage from '@/pages/JobPage'
import ProfilePage from '@/pages/ProfilePage'

function NavItem({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
          isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        )
      }
    >
      {children}
    </NavLink>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-muted/30">
        <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
            <div className="flex items-center gap-2 font-semibold">
              <BriefcaseBusiness className="size-5" />
              job-copilot
            </div>
            <nav className="flex gap-1">
              <NavItem to="/">Candidaturas</NavItem>
              <NavItem to="/perfil">Perfil</NavItem>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">
          <Routes>
            <Route path="/" element={<BoardPage />} />
            <Route path="/vagas/:id" element={<JobPage />} />
            <Route path="/perfil" element={<ProfilePage />} />
            <Route path="*" element={<p className="text-muted-foreground">Página não encontrada.</p>} />
          </Routes>
        </main>
      </div>
      <Toaster richColors position="top-right" />
    </BrowserRouter>
  )
}
