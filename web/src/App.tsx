import { useEffect } from "react";
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
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const ExternalRedirect = ({ to }: { to: string }) => {
  useEffect(() => { window.location.href = to; }, [to]);
  return <div style={{padding:'40px',textAlign:'center',color:'#666'}}>Redirecting…</div>;
};

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
          <Route path="/admin" element={<ExternalRedirect to="https://app.barnhousing.org" />} />
          <Route path="/admin/dashboard" element={<ExternalRedirect to="https://app.barnhousing.org" />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
