-- Create function to update timestamps
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public;

-- Create user roles enum and table for admin access
CREATE TYPE public.app_role AS ENUM ('admin', 'moderator', 'user');

CREATE TABLE public.user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  role app_role NOT NULL,
  UNIQUE (user_id, role)
);

ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

-- Create security definer function to check roles
CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role app_role)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_roles
    WHERE user_id = _user_id
      AND role = _role
  )
$$;

-- Create helper function to check if current user is admin
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_roles
    WHERE user_id = auth.uid()
      AND role = 'admin'
  )
$$;

-- Create property_reports table for abandoned property submissions
CREATE TABLE public.property_reports (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  address TEXT NOT NULL,
  city TEXT NOT NULL DEFAULT 'Oakland',
  state TEXT NOT NULL DEFAULT 'CA',
  zip_code TEXT,
  description TEXT,
  reporter_name TEXT,
  reporter_email TEXT,
  reporter_phone TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.property_reports ENABLE ROW LEVEL SECURITY;

-- RLS Policies for property_reports
-- Anyone can insert (public submission)
CREATE POLICY "Anyone can submit property reports"
ON public.property_reports
FOR INSERT
TO anon, authenticated
WITH CHECK (true);

-- Only admins can view reports
CREATE POLICY "Admins can view all property reports"
ON public.property_reports
FOR SELECT
TO authenticated
USING (public.is_admin());

-- Only admins can update reports
CREATE POLICY "Admins can update property reports"
ON public.property_reports
FOR UPDATE
TO authenticated
USING (public.is_admin());

-- Only admins can delete reports
CREATE POLICY "Admins can delete property reports"
ON public.property_reports
FOR DELETE
TO authenticated
USING (public.is_admin());

-- RLS Policies for user_roles (only admins can manage)
CREATE POLICY "Admins can view user roles"
ON public.user_roles
FOR SELECT
TO authenticated
USING (public.is_admin());

CREATE POLICY "Admins can manage user roles"
ON public.user_roles
FOR ALL
TO authenticated
USING (public.is_admin());

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_property_reports_updated_at
BEFORE UPDATE ON public.property_reports
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();