import React from "react";
import { createRoot } from "react-dom/client";
import { HashRouter, Link, NavLink, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { Home } from "./pages/Home";
import { SpeciesPage } from "./pages/SpeciesPage";
import { api } from "./api";
import "./styles.css";

const NAV = [
  { label: "EPG", path: "/species/drosophila", c: "hemibrain_epg_v0.1" },
  { label: "Optic", path: "/species/drosophila", c: "optic_lobe_t4_v0.1" },
  { label: "MANC", path: "/species/drosophila", c: "manc_sample_v0.1" },
  { label: "Bombus", path: "/species/bumblebee", c: "bombus_terrestris_cx_projectome_v0.1" },
];

function PackNavLink({ label, path, c }: { label: string; path: string; c: string }) {
  const [params] = useSearchParams();
  const loc = useLocation();
  const on =
    loc.pathname.startsWith(path) &&
    (params.get("c") === c || (path.includes("bumblebee") && !params.get("c")));
  return (
    <Link
      to={`${path}?c=${encodeURIComponent(c)}`}
      className={on ? "active" : undefined}
      aria-current={on ? "page" : undefined}
    >
      {label}
    </Link>
  );
}

function Shell() {
  return (
    <div className="app-shell">
      <header className="topbar studio-bar">
        <NavLink to="/" className="brand" end>
          Insectome
        </NavLink>
        <nav className="nav">
          {NAV.map((n) => (
            <PackNavLink key={n.c} label={n.label} path={n.path} c={n.c} />
          ))}
        </nav>
        <span className="top-meta">{api.mode === "static" ? "GitHub Pages" : "local studio"}</span>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/species/:speciesKey" element={<SpeciesPage />} />
        </Routes>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <HashRouter>
    <Shell />
  </HashRouter>,
);
