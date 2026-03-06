import { useState } from "react";
import { Calculator, DollarSign, Building, Shield, FileText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

const vacantTaxRates: Record<string, { min: number; max: number; name: string }> = {
  "san-francisco": { min: 2500, max: 5000, name: "San Francisco (Prop M)" },
  "oakland": { min: 6000, max: 6000, name: "Oakland (Measure W)" },
  "berkeley": { min: 3000, max: 6000, name: "Berkeley (Measure M)" },
  "other": { min: 0, max: 0, name: "Other Bay Area City" },
};

const SavingsCalculator = () => {
  const [city, setCity] = useState<string>("");
  const [monthlyRent, setMonthlyRent] = useState<string>("");
  const [hasCodeViolations, setHasCodeViolations] = useState(false);
  const [violationDays, setViolationDays] = useState<string>("30");
  const [hasInsuranceIssues, setHasInsuranceIssues] = useState(false);

  const calculateSavings = () => {
    const rent = parseFloat(monthlyRent) || 0;
    const days = parseInt(violationDays) || 0;

    // Vacant property tax savings
    const taxInfo = city ? vacantTaxRates[city] : null;
    const vacantTaxSavings = taxInfo ? (taxInfo.min + taxInfo.max) / 2 : 0;

    // Code violation savings ($100-$1000/day, using $250 average)
    const codeViolationSavings = hasCodeViolations ? days * 250 : 0;

    // Insurance savings (estimate $2,000-$5,000/year for vacancy premium)
    const insuranceSavings = hasInsuranceIssues ? 3500 : 0;

    // Tax deduction value (assuming 30% effective tax rate)
    const annualRentValue = rent * 12;
    const taxDeductionValue = annualRentValue * 0.3;

    return {
      vacantTaxSavings,
      codeViolationSavings,
      insuranceSavings,
      taxDeductionValue,
      total: vacantTaxSavings + codeViolationSavings + insuranceSavings + taxDeductionValue,
    };
  };

  const savings = calculateSavings();
  const hasInputs = city || monthlyRent || hasCodeViolations || hasInsuranceIssues;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <Card className="border-2 border-primary/20 bg-gradient-to-br from-card to-primary/5">
      <CardHeader className="text-center pb-4">
        <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
          <Calculator size={28} className="text-primary" />
        </div>
        <CardTitle className="font-display text-2xl md:text-3xl">Owner's Savings Calculator</CardTitle>
        <CardDescription className="text-base">
          See how much you could save by partnering with BARN
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Inputs */}
        <div className="grid md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label htmlFor="city">Property Location</Label>
            <Select value={city} onValueChange={setCity}>
              <SelectTrigger id="city">
                <SelectValue placeholder="Select city" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(vacantTaxRates).map(([key, value]) => (
                  <SelectItem key={key} value={key}>
                    {value.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {city && city !== "other" && (
              <p className="text-xs text-muted-foreground">
                Vacant property tax: {formatCurrency(vacantTaxRates[city].min)}
                {vacantTaxRates[city].min !== vacantTaxRates[city].max && 
                  ` – ${formatCurrency(vacantTaxRates[city].max)}`}/year
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="rent">Estimated Monthly Rent Value</Label>
            <div className="relative">
              <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="rent"
                type="number"
                placeholder="3000"
                value={monthlyRent}
                onChange={(e) => setMonthlyRent(e.target.value)}
                className="pl-9"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Used to calculate potential tax deduction value
            </p>
          </div>
        </div>

        <div className="space-y-4 pt-2">
          <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
            <div className="space-y-0.5">
              <Label htmlFor="violations" className="text-base cursor-pointer">
                Active Code Violations?
              </Label>
              <p className="text-sm text-muted-foreground">
                Overgrown weeds, graffiti, boarded windows, etc.
              </p>
            </div>
            <Switch
              id="violations"
              checked={hasCodeViolations}
              onCheckedChange={setHasCodeViolations}
            />
          </div>

          {hasCodeViolations && (
            <div className="space-y-2 pl-4 border-l-2 border-primary/20">
              <Label htmlFor="days">Days with unresolved violations</Label>
              <Input
                id="days"
                type="number"
                value={violationDays}
                onChange={(e) => setViolationDays(e.target.value)}
                className="max-w-[120px]"
              />
              <p className="text-xs text-muted-foreground">
                Bay Area cities charge $100–$1,000 per day in fines
              </p>
            </div>
          )}

          <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
            <div className="space-y-0.5">
              <Label htmlFor="insurance" className="text-base cursor-pointer">
                Vacancy Insurance Concerns?
              </Label>
              <p className="text-sm text-muted-foreground">
                Standard policies often void after 30–60 days vacant
              </p>
            </div>
            <Switch
              id="insurance"
              checked={hasInsuranceIssues}
              onCheckedChange={setHasInsuranceIssues}
            />
          </div>
        </div>

        {/* Results */}
        {hasInputs && (
          <div className="pt-6 border-t space-y-4">
            <h3 className="font-display font-semibold text-lg text-center">
              Your Estimated Annual Savings
            </h3>

            <div className="space-y-3">
              {savings.vacantTaxSavings > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-background">
                  <div className="flex items-center gap-3">
                    <Building className="h-5 w-5 text-primary" />
                    <span className="text-sm font-medium">Vacant Property Tax Exemption</span>
                  </div>
                  <span className="font-semibold text-primary">
                    {formatCurrency(savings.vacantTaxSavings)}
                  </span>
                </div>
              )}

              {savings.codeViolationSavings > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-background">
                  <div className="flex items-center gap-3">
                    <FileText className="h-5 w-5 text-primary" />
                    <span className="text-sm font-medium">Code Violation Fines Avoided</span>
                  </div>
                  <span className="font-semibold text-primary">
                    {formatCurrency(savings.codeViolationSavings)}
                  </span>
                </div>
              )}

              {savings.insuranceSavings > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-background">
                  <div className="flex items-center gap-3">
                    <Shield className="h-5 w-5 text-primary" />
                    <span className="text-sm font-medium">Insurance Premium Savings</span>
                  </div>
                  <span className="font-semibold text-primary">
                    {formatCurrency(savings.insuranceSavings)}
                  </span>
                </div>
              )}

              {savings.taxDeductionValue > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-background">
                  <div className="flex items-center gap-3">
                    <DollarSign className="h-5 w-5 text-primary" />
                    <span className="text-sm font-medium">Tax Deduction Value*</span>
                  </div>
                  <span className="font-semibold text-primary">
                    {formatCurrency(savings.taxDeductionValue)}
                  </span>
                </div>
              )}
            </div>

            {savings.total > 0 && (
              <div className="mt-4 p-4 rounded-xl bg-primary text-primary-foreground">
                <div className="flex items-center justify-between">
                  <span className="font-display font-semibold text-lg">Total Annual Benefit</span>
                  <span className="font-display font-bold text-2xl">
                    {formatCurrency(savings.total)}
                  </span>
                </div>
              </div>
            )}

            {savings.taxDeductionValue > 0 && (
              <p className="text-xs text-muted-foreground text-center">
                *Tax deduction estimate assumes 30% effective tax rate based on potential charitable contribution 
                of the difference between $1/year rent and fair market value. Consult your CPA for exact figures.
              </p>
            )}
          </div>
        )}

        {!hasInputs && (
          <div className="text-center py-6 text-muted-foreground">
            <p>Enter your property details above to see potential savings</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default SavingsCalculator;
