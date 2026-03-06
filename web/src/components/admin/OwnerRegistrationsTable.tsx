import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MoreHorizontal, Eye, Trash2, Mail, Phone, MapPin, FileText, ExternalLink } from "lucide-react";
import { format } from "date-fns";
import type { Tables } from "@/integrations/supabase/types";
import { useState } from "react";

type OwnerRegistration = Tables<"owner_registrations">;

interface OwnerRegistrationsTableProps {
  registrations: OwnerRegistration[];
  isLoading: boolean;
  onUpdateStatus: (id: string, status: string) => void;
  onDelete: (id: string) => void;
}

const statusColors: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800 hover:bg-amber-100",
  reviewing: "bg-blue-100 text-blue-800 hover:bg-blue-100",
  approved: "bg-green-100 text-green-800 hover:bg-green-100",
  rejected: "bg-red-100 text-red-800 hover:bg-red-100",
};

const OwnerRegistrationsTable = ({
  registrations,
  isLoading,
  onUpdateStatus,
  onDelete,
}: OwnerRegistrationsTableProps) => {
  const [selectedRegistration, setSelectedRegistration] = useState<OwnerRegistration | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading registrations...</p>
      </div>
    );
  }

  if (registrations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground mb-2">No owner registrations yet</p>
        <p className="text-sm text-muted-foreground">
          Property owner registrations will appear here.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Owner</TableHead>
              <TableHead>Property Address</TableHead>
              <TableHead>City</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Submitted</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {registrations.map((registration) => (
              <TableRow key={registration.id}>
                <TableCell className="font-medium">{registration.owner_name}</TableCell>
                <TableCell>{registration.property_address}</TableCell>
                <TableCell>{registration.property_city}, {registration.property_state}</TableCell>
                <TableCell>
                  <Badge className={statusColors[registration.status] || ""}>
                    {registration.status.charAt(0).toUpperCase() + registration.status.slice(1)}
                  </Badge>
                </TableCell>
                <TableCell>
                  {format(new Date(registration.created_at), "MMM d, yyyy")}
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuLabel>Actions</DropdownMenuLabel>
                      <DropdownMenuItem onClick={() => setSelectedRegistration(registration)}>
                        <Eye className="h-4 w-4 mr-2" />
                        View Details
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuLabel className="text-xs text-muted-foreground">
                        Update Status
                      </DropdownMenuLabel>
                      <DropdownMenuItem onClick={() => onUpdateStatus(registration.id, "pending")}>
                        Pending
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(registration.id, "reviewing")}>
                        Reviewing
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(registration.id, "approved")}>
                        Approved
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(registration.id, "rejected")}>
                        Rejected
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <DropdownMenuItem
                            onSelect={(e) => e.preventDefault()}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete Registration</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete this owner registration? This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => onDelete(registration.id)}
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Registration Details Dialog */}
      <Dialog open={!!selectedRegistration} onOpenChange={() => setSelectedRegistration(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Owner Registration Details</DialogTitle>
            <DialogDescription>
              Submitted {selectedRegistration && format(new Date(selectedRegistration.created_at), "MMMM d, yyyy")}
            </DialogDescription>
          </DialogHeader>
          {selectedRegistration && (
            <div className="space-y-4">
              <div>
                <h4 className="font-medium mb-1">Owner Name</h4>
                <p className="text-muted-foreground">{selectedRegistration.owner_name}</p>
              </div>
              
              <div className="flex gap-4">
                <div className="flex-1">
                  <h4 className="font-medium mb-1 flex items-center gap-1">
                    <Mail className="h-4 w-4" /> Email
                  </h4>
                  <a href={`mailto:${selectedRegistration.owner_email}`} className="text-primary hover:underline">
                    {selectedRegistration.owner_email}
                  </a>
                </div>
                {selectedRegistration.owner_phone && (
                  <div className="flex-1">
                    <h4 className="font-medium mb-1 flex items-center gap-1">
                      <Phone className="h-4 w-4" /> Phone
                    </h4>
                    <a href={`tel:${selectedRegistration.owner_phone}`} className="text-primary hover:underline">
                      {selectedRegistration.owner_phone}
                    </a>
                  </div>
                )}
              </div>

              <div>
                <h4 className="font-medium mb-1 flex items-center gap-1">
                  <MapPin className="h-4 w-4" /> Property Address
                </h4>
                <p className="text-muted-foreground">
                  {selectedRegistration.property_address}<br />
                  {selectedRegistration.property_city}, {selectedRegistration.property_state} {selectedRegistration.property_zip}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium mb-1">Authorization Agreed</h4>
                  <Badge variant={selectedRegistration.authorization_agreed ? "default" : "secondary"}>
                    {selectedRegistration.authorization_agreed ? "Yes" : "No"}
                  </Badge>
                </div>
                <div>
                  <h4 className="font-medium mb-1">Authorization Date</h4>
                  <p className="text-muted-foreground">
                    {format(new Date(selectedRegistration.authorization_date), "MMM d, yyyy")}
                  </p>
                </div>
              </div>

              <div>
                <h4 className="font-medium mb-1">Digital Signature</h4>
                <p className="text-muted-foreground italic">{selectedRegistration.authorization_signature}</p>
              </div>

              {selectedRegistration.document_url && (
                <div>
                  <h4 className="font-medium mb-1 flex items-center gap-1">
                    <FileText className="h-4 w-4" /> Supporting Document
                  </h4>
                  <a 
                    href={selectedRegistration.document_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    View Document <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}

              {selectedRegistration.admin_notes && (
                <div>
                  <h4 className="font-medium mb-1">Admin Notes</h4>
                  <p className="text-muted-foreground text-sm whitespace-pre-wrap bg-muted p-2 rounded">
                    {selectedRegistration.admin_notes}
                  </p>
                </div>
              )}

              <div>
                <h4 className="font-medium mb-1">Status</h4>
                <Badge className={statusColors[selectedRegistration.status] || ""}>
                  {selectedRegistration.status.charAt(0).toUpperCase() + selectedRegistration.status.slice(1)}
                </Badge>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default OwnerRegistrationsTable;
