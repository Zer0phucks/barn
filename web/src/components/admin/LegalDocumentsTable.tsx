import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Eye, Copy, Download, FileSignature, ClipboardCheck, Home, Mail, Send } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import LegalDocumentViewer from "./LegalDocumentViewer";

// Document templates
const DOCUMENTS = [
    {
        id: "inspection-authorization",
        title: "Authorization to Enter and Inspect Property",
        description: "Owner permission for BARN to enter and inspect property for 30 days.",
        icon: ClipboardCheck,
        category: "Owner",
        content: `AUTHORIZATION TO ENTER AND INSPECT PROPERTY

This Authorization Agreement ("Agreement") is entered into as of the date signed below by and between the undersigned property owner ("Owner") and Bay Area Renovating Neighbors ("BARN"), a California nonprofit organization.

## Property Owner Information

Owner Name: ________________________________________

Mailing Address: ________________________________________

City, State, ZIP: ________________________________________

Phone: _____________________ Email: _____________________

## Property to be Inspected

Property Address: ________________________________________

City, State, ZIP: ________________________________________

APN (if known): _____________________

## Authorization Grant

I, the undersigned property owner, hereby grant Bay Area Renovating Neighbors (BARN), its authorized agents, representatives, contractors, and volunteers, permission to enter and inspect the above-referenced property for the following purposes:

1. Conducting a comprehensive assessment of the property's current condition
2. Documenting any existing damage, deferred maintenance, or code compliance issues
3. Taking photographs, video recordings, and measurements for evaluation and planning purposes
4. Evaluating the property's suitability for participation in the BARN Caretaker Program
5. Preparing cost estimates for any necessary repairs or renovations

## Term of Authorization

This authorization shall be valid for a period of THIRTY (30) DAYS from the date of execution, unless earlier revoked in writing by the Owner.

## BARN's Obligations

During the authorization period, BARN agrees to:

• Provide reasonable advance notice (minimum 24 hours) before each property visit
• Conduct all inspections during reasonable hours (8:00 AM - 6:00 PM, Monday-Saturday)
• Take reasonable care to secure the property upon departure from each visit
• Carry comprehensive general liability insurance during all property visits
• Provide Owner with a written summary of findings within ten (10) business days of the final inspection

## Owner Acknowledgments

By signing below, Owner acknowledges and agrees that:

• This authorization does not constitute a commitment by either party to enter into any further agreement
• No renovation, repair, or construction work will be performed during the inspection period
• Owner may revoke this authorization at any time by providing written notice to BARN
• BARN is not responsible for any pre-existing conditions discovered during the inspection
• Owner will ensure BARN has safe access to all areas of the property to be inspected

## Limitation of Liability

Owner agrees to hold harmless BARN and its agents from any claims arising from pre-existing property conditions. BARN shall be liable only for damage directly caused by the negligent acts of its agents during the inspection.

## Contact Information

BARN Representative: ________________________________________

Phone: _____________________ Email: _____________________

## Signatures

____________________________________ Property Owner Signature

____________________________________ Printed Name

____________________________________ Date

____________________________________ BARN Representative Signature

____________________________________ Printed Name

____________________________________ Date`,
    },
    {
        id: "master-lease",
        title: "Master Lease Agreement",
        description: "Use Agreement between BARN and property owner for the Caretaker Program.",
        icon: Home,
        category: "Owner",
        content: `MASTER LEASE / USE AGREEMENT

This Master Lease and Use Agreement ("Agreement") is entered into between the Property Owner ("Owner") and Bay Area Renovating Neighbors ("BARN"), a California nonprofit organization.

## 1. Property Information

Property Address: ________________________________________

City, State, ZIP: ________________________________________

Property Type: ________________________________________

## 2. Term of Agreement

This Agreement shall commence on _____________ and continue for a period of _________ year(s), with automatic renewal unless terminated by either party with 60 days written notice.

## 3. Consideration

In consideration for the use of the Property, BARN shall pay Owner the sum of One Dollar ($1.00) per year, with the first payment due upon execution of this Agreement.

## 4. BARN's Responsibilities

BARN agrees to:

a) Maintain the Property in good condition and repair
b) Ensure compliance with all applicable building codes and ordinances
c) Carry comprehensive general liability insurance naming Owner as additional insured
d) Place qualified Caretakers under BARN's Caretaker License Agreement
e) Handle all maintenance, repairs, and code compliance at BARN's expense
f) Provide Owner with quarterly property condition reports
g) Respond to any emergency situations within 24 hours

## 5. Caretaker Program

Owner acknowledges and agrees that:

a) BARN will place Caretakers at the Property under a revocable license agreement
b) Caretakers are NOT tenants and do not have tenant rights
c) BARN retains full authority over Caretaker placement and removal
d) No landlord-tenant relationship exists between Owner and Caretakers
e) BARN handles all Caretaker screening, placement, and management

## 6. Owner's Responsibilities

Owner agrees to:

a) Maintain property ownership and pay all property taxes
b) Maintain hazard insurance on the Property
c) Notify BARN of any claims or liens against the Property
d) Not interfere with BARN's use or Caretaker occupancy
e) Provide BARN with emergency contact information

## 7. Property Condition

Owner represents that the Property is structurally sound and that all major systems (electrical, plumbing, HVAC) are functional or will be made functional by BARN.

## 8. Termination

Either party may terminate this Agreement with 60 days written notice. Upon termination:

a) BARN shall relocate any Caretakers within 30 days
b) BARN shall return the Property in equal or better condition
c) Owner shall not be responsible for any Caretaker relocation costs

## 9. Indemnification

BARN shall indemnify and hold harmless Owner from any claims, damages, or liabilities arising from BARN's use of the Property or actions of Caretakers placed by BARN.

## 10. Dispute Resolution

Any disputes shall be resolved through mediation before any legal action is initiated.

## Signatures

____________________________________ Property Owner Signature

____________________________________ Printed Name

____________________________________ Date

____________________________________ BARN Authorized Representative

____________________________________ Printed Name

____________________________________ Date`,
    },
    {
        id: "caretaker-license",
        title: "Caretaker License & Service Agreement",
        description: "Agreement between BARN and Caretaker for property occupancy and maintenance duties.",
        icon: FileSignature,
        category: "Caretaker",
        content: `CARETAKER LICENSE & SERVICE AGREEMENT

This Caretaker License and Service Agreement ("Agreement") is entered into between Bay Area Renovating Neighbors ("BARN") and the Caretaker identified below.

## Caretaker Information

Name: ________________________________________

Phone: _____________________ Email: _____________________

Emergency Contact: ________________________________________

Emergency Phone: _____________________

## Property Assignment

Property Address: ________________________________________

City, State, ZIP: ________________________________________

Move-In Date: _____________________

## 1. Nature of Agreement

Caretaker acknowledges and agrees that:

a) This is a LICENSE agreement, NOT a lease or rental agreement
b) Caretaker is NOT a tenant and does not have tenant rights
c) This license is revocable at BARN's discretion
d) No landlord-tenant relationship exists between Caretaker and the property owner
e) Caretaker's right to occupy is contingent on compliance with this Agreement

## 2. Caretaker Responsibilities

Caretaker agrees to:

a) Maintain the Property in clean, orderly condition
b) Perform light maintenance duties including:
   - Lawn care and basic landscaping
   - Regular cleaning of common areas
   - Reporting any maintenance issues to BARN within 24 hours
   - Basic upkeep of property systems
c) Allow BARN access for inspections with 24-hour notice
d) Not make any alterations to the Property without written approval
e) Not sublet or allow unauthorized occupants
f) Comply with all applicable laws and ordinances
g) Maintain peaceful relations with neighbors

## 3. Prohibited Activities

Caretaker shall NOT:

a) Use the Property for any illegal purpose
b) Keep pets without prior written approval
c) Smoke inside the Property
d) Make excessive noise or create disturbances
e) Store hazardous materials on the Property
f) Conduct business operations from the Property without approval

## 4. Utilities

Caretaker is responsible for:
- Electric: [ ] Yes [ ] No
- Gas: [ ] Yes [ ] No
- Water: [ ] Yes [ ] No
- Internet: [ ] Yes [ ] No

## 5. Financial Contribution

Caretaker agrees to contribute $___________ monthly toward utility costs, due on the 1st of each month.

## 6. Insurance

Caretaker is encouraged to obtain renter's insurance for personal belongings. BARN's insurance does not cover Caretaker's personal property.

## 7. Termination

a) BARN may terminate this license with 30 days written notice
b) BARN may terminate immediately for violation of this Agreement
c) Caretaker may terminate with 14 days written notice
d) Upon termination, Caretaker shall vacate and remove all personal property

## 8. Move-Out Condition

Upon termination, Caretaker shall leave the Property in the same or better condition as at move-in, ordinary wear and tear excepted.

## 9. Acknowledgments

Caretaker acknowledges that:

a) BARN is a nonprofit organization providing housing assistance
b) Participation in this program is voluntary
c) This license does not create any employment relationship
d) Caretaker has read and understands all terms of this Agreement

## Signatures

____________________________________ Caretaker Signature

____________________________________ Printed Name

____________________________________ Date

____________________________________ BARN Representative Signature

____________________________________ Printed Name

____________________________________ Date

## Property Condition Checklist (Complete at Move-In)

Kitchen: ________________________________________

Bathroom(s): ________________________________________

Bedrooms: ________________________________________

Living Areas: ________________________________________

Exterior: ________________________________________

Notes: ________________________________________`,
    },
    {
        id: "first-contact-email",
        title: "First Contact Email Template",
        description: "Email template for initial outreach to vacant property owners.",
        icon: Send,
        category: "Outreach",
        content: `FIRST CONTACT EMAIL TEMPLATE

Subject: Partnership Opportunity for Your Property at [PROPERTY ADDRESS]

---

Dear [PROPERTY OWNER NAME],

I hope this message finds you well. My name is [YOUR NAME], and I'm reaching out on behalf of Bay Area Renovating Neighbors (BARN), a California nonprofit organization dedicated to addressing housing instability while helping property owners maintain their vacant properties.

## Why We're Contacting You

We noticed that your property at [PROPERTY ADDRESS] may currently be vacant or underutilized. We understand that maintaining a vacant property can be challenging—from ongoing maintenance costs to security concerns and potential code compliance issues.

## What BARN Offers

Our innovative Caretaker Program provides a unique solution that benefits both property owners and families in need:

**For You as the Property Owner:**
• Zero maintenance costs — BARN handles all upkeep and repairs
• No tenant complications — Caretakers hold a revocable license, not a lease
• Property protection — Occupied properties deter vandalism and deterioration
• Code compliance — We ensure your property meets all local requirements
• Quarterly property condition reports
• Comprehensive liability insurance coverage

**How It Works:**
1. You grant BARN a simple Use Agreement for $1/year
2. We assess and renovate the property as needed (at no cost to you)
3. We place vetted caretakers who maintain the property in exchange for housing
4. You retain full ownership and can reclaim the property with 60 days notice

## No Obligations

We'd love the opportunity to discuss how this program might work for your specific situation. There's absolutely no obligation—just a chance to explore whether BARN could be a good fit for your property.

## Next Steps

Would you be available for a brief 15-minute call this week? I'm happy to answer any questions and provide more details about our program.

You can reach me at:
• Phone: [YOUR PHONE]
• Email: [YOUR EMAIL]

Alternatively, you can learn more about our program at [WEBSITE URL] or register your property directly at [REGISTRATION URL].

Thank you for considering this opportunity. We look forward to the possibility of working together to make a positive impact in our community.

Warm regards,

[YOUR NAME]
[YOUR TITLE]
Bay Area Renovating Neighbors (BARN)
[PHONE NUMBER]
[EMAIL ADDRESS]

---

P.S. BARN has helped [X] property owners and housed [Y] families since [YEAR]. We'd be honored to add your property to our network of community partners.`,
    },
    {
        id: "snail-mail-letter",
        title: "Snail Mail Letter Template",
        description: "Physical mail template for property owner outreach.",
        icon: Mail,
        category: "Outreach",
        content: `PHYSICAL MAIL LETTER TEMPLATE

[BARN LETTERHEAD]

Bay Area Renovating Neighbors
[BARN ADDRESS LINE 1]
[BARN ADDRESS LINE 2]
[PHONE] | [EMAIL] | [WEBSITE]

---

[DATE]

[PROPERTY OWNER NAME]
[OWNER ADDRESS LINE 1]
[OWNER ADDRESS LINE 2]
[CITY, STATE ZIP]

RE: Partnership Opportunity for Your Property at [PROPERTY ADDRESS]

Dear [PROPERTY OWNER NAME],

I am writing to introduce you to Bay Area Renovating Neighbors (BARN), a California nonprofit organization, and to share an opportunity that may benefit both you and families in our community who need housing assistance.

## About Your Property

Our records indicate that your property located at:

    [PROPERTY ADDRESS]
    [PROPERTY CITY, STATE ZIP]

may currently be vacant or underutilized. We understand that maintaining an unoccupied property presents unique challenges, including:

    • Ongoing maintenance and upkeep costs
    • Security and vandalism concerns
    • Potential code compliance issues
    • Property deterioration from lack of occupancy

## Our Innovative Solution

BARN's Caretaker Program offers a proven solution that addresses these challenges while creating positive community impact. Here's how it works:

**THE BARN ADVANTAGE FOR PROPERTY OWNERS:**

    ✓ ZERO Maintenance Costs
      BARN assumes full responsibility for all property maintenance,
      repairs, and code compliance—at absolutely no cost to you.

    ✓ NO Tenant Complications
      Unlike traditional rentals, our caretakers hold a revocable
      license agreement. This means no eviction proceedings or
      tenant rights issues if you need your property back.

    ✓ Property Protection
      An occupied property is a protected property. Our caretakers
      provide 24/7 presence, deterring vandalism and preventing
      the deterioration that plagues vacant homes.

    ✓ Complete Peace of Mind
      We provide comprehensive liability insurance, quarterly
      condition reports, and responsive property management.

## Simple Agreement Terms

    • Minimal paperwork — just a simple Use Agreement
    • Nominal consideration — $1.00 per year
    • Flexible terms — reclaim your property with 60 days notice
    • You retain full ownership at all times

## Who Are Our Caretakers?

BARN carefully vets all caretaker families. They agree to:

    • Maintain the property in clean, orderly condition
    • Perform light maintenance duties
    • Allow periodic inspections
    • Contribute modestly toward utilities

In exchange, they receive stable housing while they work toward permanent solutions.

## What Others Are Saying

"BARN took a property that was becoming a liability and turned it into an asset. I don't worry about vandalism anymore, and I know a family is benefiting." — Property Owner, [CITY]

## No Obligation — Let's Talk

I would welcome the opportunity to discuss your property and answer any questions you may have. There is absolutely no obligation.

Please contact me at your convenience:

    Phone:  [YOUR PHONE]
    Email:  [YOUR EMAIL]
    Web:    [WEBSITE URL]

You may also register your property online at [REGISTRATION URL] to schedule a free property assessment.

Thank you for taking the time to consider this opportunity. Together, we can protect your property while making a meaningful difference in someone's life.

Sincerely,



____________________________________
[YOUR NAME]
[YOUR TITLE]
Bay Area Renovating Neighbors

---

Enclosures:
[ ] BARN Program Brochure
[ ] Property Owner FAQ Sheet
[ ] Postage-Paid Response Card

---

BAY AREA RENOVATING NEIGHBORS is a 501(c)(3) nonprofit organization.
Tax ID: [EIN NUMBER]`,
    },
];

const LegalDocumentsTable = () => {
    const [selectedDocument, setSelectedDocument] = useState<typeof DOCUMENTS[0] | null>(null);
    const { toast } = useToast();

    const handleQuickCopy = async (doc: typeof DOCUMENTS[0]) => {
        try {
            await navigator.clipboard.writeText(doc.content);
            toast({
                title: "Copied to Clipboard",
                description: `"${doc.title}" has been copied.`,
            });
        } catch {
            toast({
                title: "Copy Failed",
                description: "Unable to copy text to clipboard.",
                variant: "destructive",
            });
        }
    };

    return (
        <>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {DOCUMENTS.map((doc) => (
                    <Card key={doc.id} className="flex flex-col">
                        <CardHeader className="pb-3">
                            <div className="flex items-start justify-between">
                                <div className="p-2 bg-primary/10 rounded-lg">
                                    <doc.icon className="h-6 w-6 text-primary" />
                                </div>
                                <Badge variant="secondary" className="text-xs">
                                    {doc.category}
                                </Badge>
                            </div>
                            <CardTitle className="text-lg mt-3">{doc.title}</CardTitle>
                            <CardDescription className="text-sm">
                                {doc.description}
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="pt-0 mt-auto">
                            <div className="flex flex-wrap gap-2">
                                <Button
                                    variant="default"
                                    size="sm"
                                    onClick={() => setSelectedDocument(doc)}
                                    className="gap-1.5"
                                >
                                    <Eye className="h-4 w-4" />
                                    View
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleQuickCopy(doc)}
                                    className="gap-1.5"
                                >
                                    <Copy className="h-4 w-4" />
                                    Copy
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setSelectedDocument(doc)}
                                    className="gap-1.5"
                                >
                                    <Download className="h-4 w-4" />
                                    PDF
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {selectedDocument && (
                <LegalDocumentViewer
                    open={!!selectedDocument}
                    onOpenChange={() => setSelectedDocument(null)}
                    title={selectedDocument.title}
                    content={selectedDocument.content}
                />
            )}
        </>
    );
};

export default LegalDocumentsTable;
