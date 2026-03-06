-- Create volunteers table
CREATE TABLE public.volunteers (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  skills TEXT[] DEFAULT '{}',
  availability TEXT[] DEFAULT '{}',
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.volunteers ENABLE ROW LEVEL SECURITY;

-- Anyone can submit volunteer applications (public form)
CREATE POLICY "Anyone can submit volunteer applications"
ON public.volunteers
FOR INSERT
WITH CHECK (true);

-- Only admins can view volunteer applications
CREATE POLICY "Admins can view volunteers"
ON public.volunteers
FOR SELECT
USING (is_admin());

-- Only admins can update volunteer applications
CREATE POLICY "Admins can update volunteers"
ON public.volunteers
FOR UPDATE
USING (is_admin());

-- Only admins can delete volunteer applications
CREATE POLICY "Admins can delete volunteers"
ON public.volunteers
FOR DELETE
USING (is_admin());

-- Create trigger for automatic timestamp updates
CREATE TRIGGER update_volunteers_updated_at
BEFORE UPDATE ON public.volunteers
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();