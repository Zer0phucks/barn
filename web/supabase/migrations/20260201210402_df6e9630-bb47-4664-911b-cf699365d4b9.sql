-- Create housing_applications table for families applying for housing
CREATE TABLE public.housing_applications (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  
  -- Applicant information
  applicant_name TEXT NOT NULL,
  applicant_email TEXT NOT NULL,
  applicant_phone TEXT,
  
  -- Family information
  family_size INTEGER NOT NULL DEFAULT 1,
  has_children BOOLEAN NOT NULL DEFAULT false,
  children_ages TEXT,
  
  -- Current situation
  current_situation TEXT NOT NULL,
  employment_status TEXT,
  monthly_income TEXT,
  
  -- Housing needs
  special_needs TEXT,
  preferred_location TEXT,
  
  -- Agreement
  maintenance_agreement BOOLEAN NOT NULL DEFAULT false,
  background_check_consent BOOLEAN NOT NULL DEFAULT false,
  
  -- Admin fields
  status TEXT NOT NULL DEFAULT 'pending',
  admin_notes TEXT
);

-- Enable Row Level Security
ALTER TABLE public.housing_applications ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
-- Anyone can submit housing applications (public form)
CREATE POLICY "Anyone can submit housing applications"
ON public.housing_applications
FOR INSERT
TO public
WITH CHECK (true);

-- Only admins can view housing applications
CREATE POLICY "Admins can view housing applications"
ON public.housing_applications
FOR SELECT
USING (is_admin());

-- Only admins can update housing applications
CREATE POLICY "Admins can update housing applications"
ON public.housing_applications
FOR UPDATE
USING (is_admin());

-- Only admins can delete housing applications
CREATE POLICY "Admins can delete housing applications"
ON public.housing_applications
FOR DELETE
USING (is_admin());

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_housing_applications_updated_at
BEFORE UPDATE ON public.housing_applications
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();