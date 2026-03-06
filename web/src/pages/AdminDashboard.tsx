import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { Home, LogOut, FileText, Clock, CheckCircle, XCircle, Users, Building2, KeyRound, FileSignature, Search } from "lucide-react";
import { Link } from "react-router-dom";
import PropertyReportsTable from "@/components/admin/PropertyReportsTable";
import VolunteersTable from "@/components/admin/VolunteersTable";
import HousingApplicationsTable from "@/components/admin/HousingApplicationsTable";
import OwnerRegistrationsTable from "@/components/admin/OwnerRegistrationsTable";
import LegalDocumentsTable from "@/components/admin/LegalDocumentsTable";
import VPTDashboard from "@/components/admin/vpt/VPTDashboard";
import type { Tables } from "@/integrations/supabase/types";

type PropertyReport = Tables<"property_reports">;
type Volunteer = Tables<"volunteers">;
type HousingApplication = Tables<"housing_applications">;
type OwnerRegistration = Tables<"owner_registrations">;

const AdminDashboard = () => {
  const [reports, setReports] = useState<PropertyReport[]>([]);
  const [volunteers, setVolunteers] = useState<Volunteer[]>([]);
  const [housingApplications, setHousingApplications] = useState<HousingApplication[]>([]);
  const [ownerRegistrations, setOwnerRegistrations] = useState<OwnerRegistration[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [volunteersLoading, setVolunteersLoading] = useState(true);
  const [housingLoading, setHousingLoading] = useState(true);
  const [ownersLoading, setOwnersLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const { data: { session } } = await supabase.auth.getSession();

    if (!session) {
      navigate("/admin");
      return;
    }

    // Verify admin role
    const { data: isAdmin, error } = await supabase.rpc('is_admin');

    if (error || !isAdmin) {
      await supabase.auth.signOut();
      navigate("/admin");
      toast({
        title: "Access Denied",
        description: "You do not have admin privileges.",
        variant: "destructive",
      });
      return;
    }

    setIsAuthenticated(true);
    fetchReports();
    fetchVolunteers();
    fetchHousingApplications();
    fetchOwnerRegistrations();
  };

  const fetchOwnerRegistrations = async () => {
    setOwnersLoading(true);
    const { data, error } = await supabase
      .from("owner_registrations")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      toast({
        title: "Error",
        description: "Failed to fetch owner registrations.",
        variant: "destructive",
      });
    } else {
      setOwnerRegistrations(data || []);
    }
    setOwnersLoading(false);
  };

  const fetchVolunteers = async () => {
    setVolunteersLoading(true);
    const { data, error } = await supabase
      .from("volunteers")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      toast({
        title: "Error",
        description: "Failed to fetch volunteers.",
        variant: "destructive",
      });
    } else {
      setVolunteers(data || []);
    }
    setVolunteersLoading(false);
  };

  const fetchHousingApplications = async () => {
    setHousingLoading(true);
    const { data, error } = await supabase
      .from("housing_applications")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      toast({
        title: "Error",
        description: "Failed to fetch housing applications.",
        variant: "destructive",
      });
    } else {
      setHousingApplications(data || []);
    }
    setHousingLoading(false);
  };

  const fetchReports = async () => {
    setIsLoading(true);
    const { data, error } = await supabase
      .from("property_reports")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) {
      toast({
        title: "Error",
        description: "Failed to fetch property reports.",
        variant: "destructive",
      });
    } else {
      setReports(data || []);
    }
    setIsLoading(false);
  };

  const updateStatus = async (id: string, status: string) => {
    const { error } = await supabase
      .from("property_reports")
      .update({ status })
      .eq("id", id);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to update status.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Status Updated",
        description: `Report status changed to ${status}.`,
      });
      fetchReports();
    }
  };

  const deleteReport = async (id: string) => {
    const { error } = await supabase
      .from("property_reports")
      .delete()
      .eq("id", id);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to delete report.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Report Deleted",
        description: "The property report has been removed.",
      });
      fetchReports();
    }
  };

  const updateVolunteerStatus = async (id: string, status: string) => {
    const { error } = await supabase
      .from("volunteers")
      .update({ status })
      .eq("id", id);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to update volunteer status.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Status Updated",
        description: `Volunteer status changed to ${status}.`,
      });
      fetchVolunteers();
    }
  };

  const deleteVolunteer = async (id: string) => {
    const { error } = await supabase
      .from("volunteers")
      .delete()
      .eq("id", id);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to delete volunteer.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Volunteer Deleted",
        description: "The volunteer application has been removed.",
      });
      fetchVolunteers();
    }
  };

  const updateHousingStatus = async (id: string, status: string) => {
    const { error } = await supabase
      .from("housing_applications")
      .update({ status })
      .eq("id", id);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to update application status.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Status Updated",
        description: `Application status changed to ${status}.`,
      });
      fetchHousingApplications();
    }
  };

  const deleteHousingApplication = async (id: string) => {
    const { error } = await supabase
      .from("housing_applications")
      .delete()
      .eq("id", id);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to delete application.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Application Deleted",
        description: "The housing application has been removed.",
      });
      fetchHousingApplications();
    }
  };

  const updateOwnerStatus = async (id: string, status: string) => {
    const { error } = await supabase
      .from("owner_registrations")
      .update({ status })
      .eq("id", id);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to update registration status.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Status Updated",
        description: `Registration status changed to ${status}.`,
      });
      fetchOwnerRegistrations();
    }
  };

  const deleteOwnerRegistration = async (id: string) => {
    const { error } = await supabase
      .from("owner_registrations")
      .delete()
      .eq("id", id);

    if (error) {
      toast({
        title: "Error",
        description: "Failed to delete registration.",
        variant: "destructive",
      });
    } else {
      toast({
        title: "Registration Deleted",
        description: "The owner registration has been removed.",
      });
      fetchOwnerRegistrations();
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate("/admin");
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Verifying access...</p>
      </div>
    );
  }

  const reportStats = {
    total: reports.length,
    pending: reports.filter(r => r.status === "pending").length,
    reviewing: reports.filter(r => r.status === "reviewing").length,
    approved: reports.filter(r => r.status === "approved").length,
    rejected: reports.filter(r => r.status === "rejected").length,
  };

  const volunteerStats = {
    total: volunteers.length,
    pending: volunteers.filter(v => v.status === "pending").length,
    approved: volunteers.filter(v => v.status === "approved").length,
    active: volunteers.filter(v => v.status === "active").length,
  };

  const housingStats = {
    total: housingApplications.length,
    pending: housingApplications.filter(a => a.status === "pending").length,
    reviewing: housingApplications.filter(a => a.status === "reviewing").length,
    approved: housingApplications.filter(a => a.status === "approved").length,
    waitlisted: housingApplications.filter(a => a.status === "waitlisted").length,
  };

  const ownerStats = {
    total: ownerRegistrations.length,
    pending: ownerRegistrations.filter(o => o.status === "pending").length,
    reviewing: ownerRegistrations.filter(o => o.status === "reviewing").length,
    approved: ownerRegistrations.filter(o => o.status === "approved").length,
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container-wide px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <Home className="h-4 w-4" />
              Home
            </Link>
            <span className="text-border">|</span>
            <h1 className="font-display text-xl font-semibold">Admin Dashboard</h1>
          </div>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4 mr-2" />
            Sign Out
          </Button>
        </div>
      </header>

      <main className="container-wide px-6 py-8">
        <Tabs defaultValue="reports" className="space-y-6">
          <TabsList className="grid w-full max-w-5xl grid-cols-6">
            <TabsTrigger value="reports" className="gap-2">
              <FileText className="h-4 w-4" />
              Reports
            </TabsTrigger>
            <TabsTrigger value="volunteers" className="gap-2">
              <Users className="h-4 w-4" />
              Volunteers
            </TabsTrigger>
            <TabsTrigger value="housing" className="gap-2">
              <Building2 className="h-4 w-4" />
              Housing
            </TabsTrigger>
            <TabsTrigger value="owners" className="gap-2">
              <KeyRound className="h-4 w-4" />
              Owners
            </TabsTrigger>
            <TabsTrigger value="documents" className="gap-2">
              <FileSignature className="h-4 w-4" />
              Documents
            </TabsTrigger>
            <TabsTrigger value="vpt" className="gap-2">
              <Search className="h-4 w-4" />
              VPT Scanner
            </TabsTrigger>
          </TabsList>

          <TabsContent value="reports" className="space-y-6">
            {/* Property Reports Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <FileText className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{reportStats.total}</p>
                    <p className="text-sm text-muted-foreground">Total</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-accent rounded-lg">
                    <Clock className="h-5 w-5 text-accent-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{reportStats.pending}</p>
                    <p className="text-sm text-muted-foreground">Pending</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-secondary rounded-lg">
                    <FileText className="h-5 w-5 text-secondary-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{reportStats.reviewing}</p>
                    <p className="text-sm text-muted-foreground">Reviewing</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/20 rounded-lg">
                    <CheckCircle className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{reportStats.approved}</p>
                    <p className="text-sm text-muted-foreground">Approved</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-destructive/10 rounded-lg">
                    <XCircle className="h-5 w-5 text-destructive" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{reportStats.rejected}</p>
                    <p className="text-sm text-muted-foreground">Rejected</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Reports Table */}
            <Card>
              <CardHeader>
                <CardTitle>Property Reports</CardTitle>
                <CardDescription>
                  Manage submitted property reports from community members
                </CardDescription>
              </CardHeader>
              <CardContent>
                <PropertyReportsTable
                  reports={reports}
                  isLoading={isLoading}
                  onUpdateStatus={updateStatus}
                  onDelete={deleteReport}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="volunteers" className="space-y-6">
            {/* Volunteer Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Users className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{volunteerStats.total}</p>
                    <p className="text-sm text-muted-foreground">Total</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-accent rounded-lg">
                    <Clock className="h-5 w-5 text-accent-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{volunteerStats.pending}</p>
                    <p className="text-sm text-muted-foreground">Pending</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/20 rounded-lg">
                    <CheckCircle className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{volunteerStats.approved}</p>
                    <p className="text-sm text-muted-foreground">Approved</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-secondary rounded-lg">
                    <Users className="h-5 w-5 text-secondary-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{volunteerStats.active}</p>
                    <p className="text-sm text-muted-foreground">Active</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Volunteers Table */}
            <Card>
              <CardHeader>
                <CardTitle>Volunteer Applications</CardTitle>
                <CardDescription>
                  Review and manage volunteer signups
                </CardDescription>
              </CardHeader>
              <CardContent>
                <VolunteersTable
                  volunteers={volunteers}
                  isLoading={volunteersLoading}
                  onUpdateStatus={updateVolunteerStatus}
                  onDelete={deleteVolunteer}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="housing" className="space-y-6">
            {/* Housing Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Building2 className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{housingStats.total}</p>
                    <p className="text-sm text-muted-foreground">Total</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-accent rounded-lg">
                    <Clock className="h-5 w-5 text-accent-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{housingStats.pending}</p>
                    <p className="text-sm text-muted-foreground">Pending</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-secondary rounded-lg">
                    <FileText className="h-5 w-5 text-secondary-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{housingStats.reviewing}</p>
                    <p className="text-sm text-muted-foreground">Reviewing</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/20 rounded-lg">
                    <CheckCircle className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{housingStats.approved}</p>
                    <p className="text-sm text-muted-foreground">Approved</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-purple-100 rounded-lg">
                    <Users className="h-5 w-5 text-purple-800" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{housingStats.waitlisted}</p>
                    <p className="text-sm text-muted-foreground">Waitlisted</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Housing Applications Table */}
            <Card>
              <CardHeader>
                <CardTitle>Housing Applications</CardTitle>
                <CardDescription>
                  Review and manage family housing applications
                </CardDescription>
              </CardHeader>
              <CardContent>
                <HousingApplicationsTable
                  applications={housingApplications}
                  isLoading={housingLoading}
                  onUpdateStatus={updateHousingStatus}
                  onDelete={deleteHousingApplication}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="owners" className="space-y-6">
            {/* Owner Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <KeyRound className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{ownerStats.total}</p>
                    <p className="text-sm text-muted-foreground">Total</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-accent rounded-lg">
                    <Clock className="h-5 w-5 text-accent-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{ownerStats.pending}</p>
                    <p className="text-sm text-muted-foreground">Pending</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-secondary rounded-lg">
                    <FileText className="h-5 w-5 text-secondary-foreground" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{ownerStats.reviewing}</p>
                    <p className="text-sm text-muted-foreground">Reviewing</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/20 rounded-lg">
                    <CheckCircle className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{ownerStats.approved}</p>
                    <p className="text-sm text-muted-foreground">Approved</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Owner Registrations Table */}
            <Card>
              <CardHeader>
                <CardTitle>Owner Registrations</CardTitle>
                <CardDescription>
                  Review property owner authorization submissions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <OwnerRegistrationsTable
                  registrations={ownerRegistrations}
                  isLoading={ownersLoading}
                  onUpdateStatus={updateOwnerStatus}
                  onDelete={deleteOwnerRegistration}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="documents" className="space-y-6">
            {/* Documents Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <FileSignature className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">5</p>
                    <p className="text-sm text-muted-foreground">Templates</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-amber-100 rounded-lg">
                    <KeyRound className="h-5 w-5 text-amber-800" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">2</p>
                    <p className="text-sm text-muted-foreground">Owner Docs</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Users className="h-5 w-5 text-blue-800" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">1</p>
                    <p className="text-sm text-muted-foreground">Caretaker Docs</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <FileText className="h-5 w-5 text-green-800" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">2</p>
                    <p className="text-sm text-muted-foreground">Outreach</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Legal Documents */}
            <Card>
              <CardHeader>
                <CardTitle>Legal Document Templates</CardTitle>
                <CardDescription>
                  View, copy, or download legal documents for the BARN program
                </CardDescription>
              </CardHeader>
              <CardContent>
                <LegalDocumentsTable />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="vpt" className="space-y-6">
            {/* VPT Scanner Dashboard */}
            <Card>
              <CardHeader>
                <CardTitle>VPT Property Scanner</CardTitle>
                <CardDescription>
                  View properties from the VPT scanner database, manage scans, and perform research
                </CardDescription>
              </CardHeader>
              <CardContent>
                <VPTDashboard />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default AdminDashboard;
