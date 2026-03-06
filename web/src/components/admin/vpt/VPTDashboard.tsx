import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Database, List, Map, Settings } from "lucide-react";
import VPTPropertiesTable from "./VPTPropertiesTable";
import VPTMapView from "./VPTMapView";
import VPTScannerControl from "./VPTScannerControl";

export default function VPTDashboard() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge className="bg-green-100 text-green-800">Connected</Badge>
          <span className="text-sm text-muted-foreground">
            Scanner data source: Supabase
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Database className="h-3.5 w-3.5" />
          Unified project mode
        </div>
      </div>

      <Tabs defaultValue="properties" className="space-y-4">
        <TabsList>
          <TabsTrigger value="properties" className="gap-2">
            <List className="h-4 w-4" />
            Properties
          </TabsTrigger>
          <TabsTrigger value="map" className="gap-2">
            <Map className="h-4 w-4" />
            Map View
          </TabsTrigger>
          <TabsTrigger value="scanner" className="gap-2">
            <Settings className="h-4 w-4" />
            Scanner Admin
          </TabsTrigger>
        </TabsList>

        <TabsContent value="properties">
          <VPTPropertiesTable />
        </TabsContent>

        <TabsContent value="map">
          <VPTMapView />
        </TabsContent>

        <TabsContent value="scanner">
          <VPTScannerControl />
        </TabsContent>
      </Tabs>
    </div>
  );
}
