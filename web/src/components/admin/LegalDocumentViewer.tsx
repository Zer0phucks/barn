import { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { Copy, Download, CheckCircle } from "lucide-react";

interface LegalDocumentViewerProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    content: string;
}

const LegalDocumentViewer = ({
    open,
    onOpenChange,
    title,
    content,
}: LegalDocumentViewerProps) => {
    const [copied, setCopied] = useState(false);
    const { toast } = useToast();

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            toast({
                title: "Copied to Clipboard",
                description: "Document text has been copied successfully.",
            });
            setTimeout(() => setCopied(false), 2000);
        } catch {
            toast({
                title: "Copy Failed",
                description: "Unable to copy text to clipboard.",
                variant: "destructive",
            });
        }
    };

    const handleDownloadPDF = () => {
        // Create a printable HTML document
        const printWindow = window.open('', '_blank');
        if (!printWindow) {
            toast({
                title: "Download Failed",
                description: "Please allow pop-ups to download the PDF.",
                variant: "destructive",
            });
            return;
        }

        const htmlContent = `
      <!DOCTYPE html>
      <html>
        <head>
          <title>${title}</title>
          <style>
            @page { margin: 1in; }
            body {
              font-family: 'Times New Roman', Times, serif;
              font-size: 12pt;
              line-height: 1.6;
              color: #000;
              max-width: 8.5in;
              margin: 0 auto;
              padding: 0.5in;
            }
            h1 {
              font-size: 18pt;
              font-weight: bold;
              text-align: center;
              margin-bottom: 24pt;
              text-transform: uppercase;
            }
            h2 {
              font-size: 14pt;
              font-weight: bold;
              margin-top: 18pt;
              margin-bottom: 12pt;
            }
            p {
              margin-bottom: 12pt;
              text-align: justify;
            }
            .signature-block {
              margin-top: 36pt;
              page-break-inside: avoid;
            }
            .signature-line {
              border-bottom: 1px solid #000;
              width: 300px;
              height: 24pt;
              margin-bottom: 6pt;
            }
            .signature-label {
              font-size: 10pt;
              color: #666;
            }
            @media print {
              body { print-color-adjust: exact; }
            }
          </style>
        </head>
        <body>
          <h1>${title}</h1>
          ${content.split('\n\n').map(para => {
            if (para.startsWith('##')) {
                return `<h2>${para.replace('## ', '')}</h2>`;
            }
            if (para.includes('____')) {
                return `
                <div class="signature-block">
                  <div class="signature-line"></div>
                  <div class="signature-label">${para.replace(/_{4,}/g, '').trim()}</div>
                </div>
              `;
            }
            return `<p>${para}</p>`;
        }).join('')}
        </body>
      </html>
    `;

        printWindow.document.write(htmlContent);
        printWindow.document.close();

        // Wait for content to load, then trigger print dialog (Save as PDF)
        printWindow.onload = () => {
            setTimeout(() => {
                printWindow.print();
            }, 250);
        };

        toast({
            title: "PDF Ready",
            description: "Use 'Save as PDF' in the print dialog to download.",
        });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle className="text-xl">{title}</DialogTitle>
                    <DialogDescription>
                        Review, copy, or download this document as PDF
                    </DialogDescription>
                </DialogHeader>

                <div className="flex gap-2 mb-4">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopy}
                        className="gap-2"
                    >
                        {copied ? (
                            <>
                                <CheckCircle className="h-4 w-4 text-green-600" />
                                Copied!
                            </>
                        ) : (
                            <>
                                <Copy className="h-4 w-4" />
                                Copy Text
                            </>
                        )}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleDownloadPDF}
                        className="gap-2"
                    >
                        <Download className="h-4 w-4" />
                        Download PDF
                    </Button>
                </div>

                <ScrollArea className="flex-1 border rounded-lg p-6 bg-white">
                    <div className="prose prose-sm max-w-none text-foreground">
                        {content.split('\n\n').map((paragraph, index) => {
                            if (paragraph.startsWith('## ')) {
                                return (
                                    <h2 key={index} className="text-lg font-semibold mt-6 mb-3 text-foreground">
                                        {paragraph.replace('## ', '')}
                                    </h2>
                                );
                            }
                            if (paragraph.includes('____')) {
                                const label = paragraph.replace(/_{4,}/g, '').trim();
                                return (
                                    <div key={index} className="mt-8 mb-4">
                                        <div className="border-b-2 border-gray-400 w-80 h-8" />
                                        <p className="text-sm text-muted-foreground mt-1">{label}</p>
                                    </div>
                                );
                            }
                            return (
                                <p key={index} className="mb-4 text-sm leading-relaxed">
                                    {paragraph}
                                </p>
                            );
                        })}
                    </div>
                </ScrollArea>
            </DialogContent>
        </Dialog>
    );
};

export default LegalDocumentViewer;
