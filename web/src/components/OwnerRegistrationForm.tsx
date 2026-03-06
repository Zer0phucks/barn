import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { FileText, CheckCircle } from "lucide-react";

const formSchema = z.object({
  ownerName: z.string().trim().min(2, "Name must be at least 2 characters").max(100),
  ownerEmail: z.string().trim().email("Please enter a valid email").max(255),
  ownerPhone: z.string().trim().optional(),
  propertyAddress: z.string().trim().min(5, "Please enter a valid address").max(200),
  propertyCity: z.string().trim().min(2, "City is required").max(100),
  propertyState: z.string().trim().length(2, "Please use 2-letter state code"),
  propertyZip: z.string().trim().optional(),
  authorizationAgreed: z.boolean().refine(val => val === true, {
    message: "You must agree to the authorization terms"
  }),
  authorizationSignature: z.string().trim().min(2, "Please type your full legal name as signature").max(100),
});

type FormData = z.infer<typeof formSchema>;

interface OwnerRegistrationFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const OwnerRegistrationForm = ({ open, onOpenChange }: OwnerRegistrationFormProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const { toast } = useToast();

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      ownerName: "",
      ownerEmail: "",
      ownerPhone: "",
      propertyAddress: "",
      propertyCity: "Oakland",
      propertyState: "CA",
      propertyZip: "",
      authorizationAgreed: false,
      authorizationSignature: "",
    },
  });

  const onSubmit = async (data: FormData) => {
    setIsSubmitting(true);

    try {
      // Insert registration
      const { error } = await supabase
        .from("owner_registrations")
        .insert({
          owner_name: data.ownerName,
          owner_email: data.ownerEmail,
          owner_phone: data.ownerPhone || null,
          property_address: data.propertyAddress,
          property_city: data.propertyCity,
          property_state: data.propertyState,
          property_zip: data.propertyZip || null,
          authorization_agreed: data.authorizationAgreed,
          authorization_signature: data.authorizationSignature,
          authorization_date: new Date().toISOString(),
          document_url: null,
        });

      if (error) throw error;

      setIsSuccess(true);
      form.reset();
    } catch (error) {
      toast({
        title: "Submission Failed",
        description: "There was an error submitting your registration. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setIsSuccess(false);
    form.reset();
    onOpenChange(false);
  };

  if (isSuccess) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-md">
          <div className="flex flex-col items-center text-center py-6">
            <div className="rounded-full bg-primary/10 p-4 mb-4">
              <CheckCircle className="h-10 w-10 text-primary" />
            </div>
            <DialogTitle className="text-xl mb-2">Registration Submitted!</DialogTitle>
            <DialogDescription className="mb-6">
              Thank you for registering your property with BARN. We have received your
              authorization and will contact you within 3-5 business days to discuss next steps.
            </DialogDescription>
            <Button onClick={handleClose}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] p-0">
        <ScrollArea className="max-h-[90vh]">
          <div className="p-6">
            <DialogHeader>
              <DialogTitle className="text-xl font-display">Property Owner Registration</DialogTitle>
              <DialogDescription>
                Register your property and authorize BARN to enter and inspect for rehabilitation purposes.
              </DialogDescription>
            </DialogHeader>

            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6 mt-6">
                {/* Owner Information */}
                <div>
                  <h3 className="font-semibold mb-4">Owner Information</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="ownerName"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Full Legal Name *</FormLabel>
                          <FormControl>
                            <Input placeholder="John Smith" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="ownerEmail"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Email Address *</FormLabel>
                          <FormControl>
                            <Input type="email" placeholder="john@example.com" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="ownerPhone"
                      render={({ field }) => (
                        <FormItem className="md:col-span-2">
                          <FormLabel>Phone Number</FormLabel>
                          <FormControl>
                            <Input type="tel" placeholder="(510) 555-0123" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>

                <Separator />

                {/* Property Information */}
                <div>
                  <h3 className="font-semibold mb-4">Property Information</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="propertyAddress"
                      render={({ field }) => (
                        <FormItem className="md:col-span-2">
                          <FormLabel>Property Address *</FormLabel>
                          <FormControl>
                            <Input placeholder="123 Main Street" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="propertyCity"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>City *</FormLabel>
                          <FormControl>
                            <Input placeholder="Oakland" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="propertyState"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>State *</FormLabel>
                            <FormControl>
                              <Input placeholder="CA" maxLength={2} {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="propertyZip"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>ZIP Code</FormLabel>
                            <FormControl>
                              <Input placeholder="94601" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Authorization Document */}
                <div>
                  <h3 className="font-semibold mb-4 flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Authorization to Enter & Inspect
                  </h3>

                  <div className="bg-muted/50 rounded-lg p-4 mb-4 text-sm space-y-3 max-h-48 overflow-y-auto border">
                    <p className="font-semibold">AUTHORIZATION TO ENTER AND INSPECT PROPERTY</p>

                    <p>
                      I, the undersigned property owner, hereby grant Bay Area Renovating Neighbors
                      ("BARN"), its authorized agents, representatives, contractors, and volunteers,
                      permission to enter and inspect the property located at the address specified
                      above for the purposes of assessment and evaluation for the BARN Caretaker Program.
                    </p>

                    <p className="font-medium">By signing this authorization, I acknowledge and agree that:</p>

                    <ol className="list-decimal list-inside space-y-2 pl-2">
                      <li>
                        BARN and its representatives may enter the property during reasonable hours
                        (8:00 AM - 6:00 PM, Monday-Saturday) with at least 24 hours advance notice.
                      </li>
                      <li>
                        This authorization is valid for a period of <strong>thirty (30) days</strong> from the
                        date of signature unless earlier revoked in writing.
                      </li>
                      <li>
                        I am the legal owner of the property or am legally authorized to grant this
                        permission on behalf of the owner.
                      </li>
                      <li>
                        BARN will take reasonable precautions to secure the property after each visit
                        and will provide a written summary of findings within ten (10) business days.
                      </li>
                      <li>
                        BARN may document the property's condition through photographs, video recordings,
                        and written reports for evaluation and planning purposes.
                      </li>
                      <li>
                        No renovation, repair, or construction work will be performed during this
                        inspection period. Any such work will require a separate written agreement.
                      </li>
                      <li>
                        I release BARN from claims arising from pre-existing property conditions. BARN
                        shall be liable only for damage directly caused by the negligent acts of its agents.
                      </li>
                    </ol>

                    <p className="text-muted-foreground text-xs mt-4">
                      This authorization is governed by the laws of the State of California.
                    </p>
                  </div>

                  <FormField
                    control={form.control}
                    name="authorizationAgreed"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-start space-x-3 space-y-0 mb-4">
                        <FormControl>
                          <Checkbox
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                        <div className="space-y-1 leading-none">
                          <FormLabel className="font-normal">
                            I have read, understand, and agree to the Authorization to Enter & Inspect
                            terms above. *
                          </FormLabel>
                          <FormMessage />
                        </div>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="authorizationSignature"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Electronic Signature (Type your full legal name) *</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="John Smith"
                            className="font-serif italic text-lg"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          By typing your name above, you are providing a legally binding electronic signature.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleClose}
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button type="submit" className="flex-1" disabled={isSubmitting}>
                    {isSubmitting ? "Submitting..." : "Submit Registration"}
                  </Button>
                </div>
              </form>
            </Form>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};

export default OwnerRegistrationForm;
