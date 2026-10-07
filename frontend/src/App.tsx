import { NavLink, Route, Routes } from 'react-router-dom';
import Admissions from './pages/Admissions';
import Detail from './pages/Detail';
import Import from './pages/Import';
import Landing from './pages/Landing';
import Methodology from './pages/Methodology';
import Profile from './pages/Profile';

export default function App() {
  return (
    <>
      <nav className="glass-nav" aria-label="Primary">
        <NavLink className="brand" to="/"><span className="brand-mark" aria-hidden="true" />Aletheia</NavLink>
        <div className="nav-links">
          <NavLink to="/">Home</NavLink>
          <NavLink to="/admissions">Admissions</NavLink>
          <NavLink to="/profile">Testing &amp; Profile</NavLink>
          <NavLink to="/import">Import</NavLink>
          <NavLink to="/methodology">Methodology</NavLink>
        </div>
        <NavLink className="btn" to="/admissions">Compare</NavLink>
      </nav>
      <main className="page">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/admissions" element={<Admissions />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/u/:id" element={<Detail />} />
          <Route path="/import" element={<Import />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="*" element={<Landing />} />
        </Routes>
        <footer className="meta-strip" style={{ marginTop: 48 }}>
          Aletheia · Common Data Set comparison · C7 + C8–C11 · sources cited · missing ≠ zero
        </footer>
      </main>
    </>
  );
}
