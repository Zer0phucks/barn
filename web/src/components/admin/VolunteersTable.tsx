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
import { MoreHorizontal, Eye, Trash2, Mail, Phone } from "lucide-react";
import { format } from "date-fns";
import type { Tables } from "@/integrations/supabase/types";
import { useState } from "react";

type Volunteer = Tables<"volunteers">;

interface VolunteersTableProps {
  volunteers: Volunteer[];
  isLoading: boolean;
  onUpdateStatus: (id: string, status: string) => void;
  onDelete: (id: string) => void;
}

const statusColors: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800 hover:bg-amber-100",
  approved: "bg-green-100 text-green-800 hover:bg-green-100",
  active: "bg-blue-100 text-blue-800 hover:bg-blue-100",
  inactive: "bg-muted text-muted-foreground hover:bg-muted",
  rejected: "bg-red-100 text-red-800 hover:bg-red-100",
};

const VolunteersTable = ({
  volunteers,
  isLoading,
  onUpdateStatus,
  onDelete,
}: VolunteersTableProps) => {
  const [selectedVolunteer, setSelectedVolunteer] = useState<Volunteer | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading volunteers...</p>
      </div>
    );
  }

  if (volunteers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground mb-2">No volunteer applications yet</p>
        <p className="text-sm text-muted-foreground">
          Volunteer signups will appear here.
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
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Skills</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Applied</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {volunteers.map((volunteer) => (
              <TableRow key={volunteer.id}>
                <TableCell className="font-medium">{volunteer.name}</TableCell>
                <TableCell>{volunteer.email}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1 max-w-[200px]">
                    {volunteer.skills?.slice(0, 2).map((skill) => (
                      <Badge key={skill} variant="secondary" className="text-xs">
                        {skill}
                      </Badge>
                    ))}
                    {volunteer.skills && volunteer.skills.length > 2 && (
                      <Badge variant="outline" className="text-xs">
                        +{volunteer.skills.length - 2}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge className={statusColors[volunteer.status] || ""}>
                    {volunteer.status.charAt(0).toUpperCase() + volunteer.status.slice(1)}
                  </Badge>
                </TableCell>
                <TableCell>
                  {format(new Date(volunteer.created_at), "MMM d, yyyy")}
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
                      <DropdownMenuItem onClick={() => setSelectedVolunteer(volunteer)}>
                        <Eye className="h-4 w-4 mr-2" />
                        View Details
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuLabel className="text-xs text-muted-foreground">
                        Update Status
                      </DropdownMenuLabel>
                      <DropdownMenuItem onClick={() => onUpdateStatus(volunteer.id, "pending")}>
                        Pending
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(volunteer.id, "approved")}>
                        Approved
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(volunteer.id, "active")}>
                        Active
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(volunteer.id, "inactive")}>
                        Inactive
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onUpdateStatus(volunteer.id, "rejected")}>
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
                            <AlertDialogTitle>Delete Volunteer</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete this volunteer application? This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => onDelete(volunteer.id)}
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

      {/* Volunteer Details Dialog */}
      <Dialog open={!!selectedVolunteer} onOpenChange={() => setSelectedVolunteer(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Volunteer Details</DialogTitle>
            <DialogDescription>
              Application submitted {selectedVolunteer && format(new Date(selectedVolunteer.created_at), "MMMM d, yyyy")}
            </DialogDescription>
          </DialogHeader>
          {selectedVolunteer && (
            <div className="space-y-4">
              <div>
                <h4 className="font-medium mb-1">Name</h4>
                <p className="text-muted-foreground">{selectedVolunteer.name}</p>
              </div>
              
              <div className="flex gap-4">
                <div className="flex-1">
                  <h4 className="font-medium mb-1 flex items-center gap-1">
                    <Mail className="h-4 w-4" /> Email
                  </h4>
                  <a href={`mailto:${selectedVolunteer.email}`} className="text-primary hover:underline">
                    {selectedVolunteer.email}
                  </a>
                </div>
                {selectedVolunteer.phone && (
                  <div className="flex-1">
                    <h4 className="font-medium mb-1 flex items-center gap-1">
                      <Phone className="h-4 w-4" /> Phone
                    </h4>
                    <a href={`tel:${selectedVolunteer.phone}`} className="text-primary hover:underline">
                      {selectedVolunteer.phone}
                    </a>
                  </div>
                )}
              </div>

              <div>
                <h4 className="font-medium mb-2">Skills</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedVolunteer.skills?.length ? (
                    selectedVolunteer.skills.map((skill) => (
                      <Badge key={skill} variant="secondary">
                        {skill}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-muted-foreground text-sm">No skills listed</span>
                  )}
                </div>
              </div>

              <div>
                <h4 className="font-medium mb-2">Availability</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedVolunteer.availability?.length ? (
                    selectedVolunteer.availability.map((time) => (
                      <Badge key={time} variant="outline">
                        {time}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-muted-foreground text-sm">No availability listed</span>
                  )}
                </div>
              </div>

              {selectedVolunteer.notes && (
                <div>
                  <h4 className="font-medium mb-1">Additional Notes</h4>
                  <p className="text-muted-foreground text-sm whitespace-pre-wrap">
                    {selectedVolunteer.notes}
                  </p>
                </div>
              )}

              <div>
                <h4 className="font-medium mb-1">Status</h4>
                <Badge className={statusColors[selectedVolunteer.status] || ""}>
                  {selectedVolunteer.status.charAt(0).toUpperCase() + selectedVolunteer.status.slice(1)}
                </Badge>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default VolunteersTable;
