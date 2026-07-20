import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import EquipmentDetail from "./pages/EquipmentDetail";
import ReviewQueue from "./pages/ReviewQueue";
import Notifications from "./pages/Notifications";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/review", label: "Review Queue" },
  { to: "/notifications", label: "Alerts" },
];

function NavItem({ to, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `rounded-lg px-3 py-2 text-sm font-semibold transition ${
          isActive ? "bg-white text-slate-900 shadow" : "text-slate-200 hover:bg-slate-700"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="bg-slate-900 text-white">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🛠️</span>
            <span className="text-lg font-bold tracking-tight">
              Equipment Intelligence
            </span>
          </div>
          <nav className="flex gap-1">
            {NAV.map((n) => (
              <NavItem key={n.to} {...n} />
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/equipment/:id" element={<EquipmentDetail />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/notifications" element={<Notifications />} />
        </Routes>
      </main>
    </div>
  );
}
