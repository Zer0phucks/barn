-- Create owner registrations table
CREATE TABLE public.owner_registrations (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  
  -- Owner info
  owner_name TEXT NOT NULL,
  owner_email TEXT NOT NULL,
  owner_phone TEXT,
  
  -- Property info
  property_address TEXT NOT NULL,
  property_city TEXT NOT NULL DEFAULT 'Oakland',
  property_state TEXT NOT NULL DEFAULT 'CA',
  property_zip TEXT,
  
  -- Authorization
  authorization_agreed BOOLEAN NOT NULL DEFAULT false,
  authorization_signature TEXT NOT NULL,
  authorization_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  
  -- Optional document
  document_url TEXT,
  
  -- Status
  status TEXT NOT NULL DEFAULT 'pending',
  admin_notes TEXT
);

-- Enable RLS
ALTER TABLE public.owner_registrations ENABLE ROW LEVEL SECURITY;

-- Anyone can submit registrations
CREATE POLICY "Anyone can submit owner registrations"
ON public.owner_registrations
FOR INSERT
WITH CHECK (true);

-- Admins can view all registrations
CREATE POLICY "Admins can view owner registrations"
ON public.owner_registrations
FOR SELECT
USING (is_admin());

-- Admins can update registrations
CREATE POLICY "Admins can update owner registrations"
ON public.owner_registrations
FOR UPDATE
USING (is_admin());

-- Admins can delete registrations
CREATE POLICY "Admins can delete owner registrations"
ON public.owner_registrations
FOR DELETE
USING (is_admin());

-- Trigger for updated_at
CREATE TRIGGER update_owner_registrations_updated_at
BEFORE UPDATE ON public.owner_registrations
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- Create storage bucket for owner documents
INSERT INTO storage.buckets (id, name, public) 
VALUES ('owner-documents', 'owner-documents', false);

-- Storage policies for owner documents
CREATE POLICY "Anyone can upload owner documents"
ON storage.objects
FOR INSERT
WITH CHECK (bucket_id = 'owner-documents');

-- Admins can view owner documents
CREATE POLICY "Admins can view owner documents"
ON storage.objects
FOR SELECT
USING (bucket_id = 'owner-documents' AND is_admin());

-- Admins can delete owner documents
CREATE POLICY "Admins can delete owner documents"
ON storage.objects
FOR DELETE
USING (bucket_id = 'owner-documents' AND is_admin());