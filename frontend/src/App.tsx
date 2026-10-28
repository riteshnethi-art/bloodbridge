import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import Landing from "./pages/Landing";
import Join from "./pages/Join";
import Login from "./pages/Login";
import DonorRegister from "./pages/DonorRegister";
import BloodRequest from "./pages/BloodRequest";
import MatchResults from "./pages/MatchResults";
import RequesterDashboard from "./pages/RequesterDashboard";
import DonorDashboard from "./pages/DonorDashboard";
import Rewards from "./pages/Rewards";
import Referrals from "./pages/Referrals";
import Admin from "./pages/Admin";
import Assistant from "./pages/Assistant";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/join" element={<Join />} />
        <Route path="/login" element={<Login />} />
        <Route path="/donors/register" element={<DonorRegister />} />
        <Route path="/requests/new" element={<BloodRequest />} />
        <Route path="/requests/:publicId" element={<MatchResults />} />
        <Route path="/requests/:publicId/matches" element={<MatchResults />} />
        <Route
          path="/dashboard/requester"
          element={
            <RequireAuth>
              <RequesterDashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/dashboard/donor"
          element={
            <RequireAuth>
              <DonorDashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/rewards"
          element={
            <RequireAuth>
              <Rewards />
            </RequireAuth>
          }
        />
        <Route
          path="/referrals"
          element={
            <RequireAuth>
              <Referrals />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAuth roles={["admin"]}>
              <Admin />
            </RequireAuth>
          }
        />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="*" element={<Landing />} />
      </Route>
    </Routes>
  );
}
