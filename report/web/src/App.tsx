import { HashRouter, Routes, Route } from "react-router-dom";
import NavPage from "@/pages/NavPage";
import RunPage from "@/pages/RunPage";
import OptunaPage from "@/pages/OptunaPage";
import Layout from "@/components/Layout";

export default function App() {
  return (
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<NavPage />} />
          <Route path="/run/:id" element={<RunPage />} />
          <Route path="/run/:id/optuna" element={<OptunaPage />} />
        </Routes>
      </Layout>
    </HashRouter>
  );
}