import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import DonationSuccess from "./pages/DonationSuccess";
import ReportProperty from "./pages/ReportProperty";
import RegisterProperty from "./pages/RegisterProperty";
import Volunteer from "./pages/Volunteer";
import ApplyHousing from "./pages/ApplyHousing";
import AdminLogin from "./pages/AdminLogin";
import AdminDashboard from "./pages/AdminDashboard";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/donation-success" element={<DonationSuccess />} />
          <Route path="/report-property" element={<ReportProperty />} />
          <Route path="/register-property" element={<RegisterProperty />} />
          <Route path="/volunteer" element={<Volunteer />} />
          <Route path="/apply-housing" element={<ApplyHousing />} />
          <Route path="/admin" element={<AdminLogin />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
