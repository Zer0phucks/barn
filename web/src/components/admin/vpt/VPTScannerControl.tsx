import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { RefreshCw, Play, Square, Zap, Search, Camera } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
    vptGetScanStatus,
    vptStartScan,
    vptStopScan,
    vptGetResearchStatus,
    vptStartResearch,
    vptGetConditionStatus,
    vptStartConditionScanAll,
    vptGetPgeStatus,
    vptStartPgeScanAll,
    vptStopPgeScan,
    vptGetFavorites,
    type VPTScanStatus,
    type VPTResearchStatus,
    type VPTConditionStatus,
    type VPTPgeStatus,
} from "@/services/vptApi";

interface LogEntry {
    message: string;
    type: "info" | "warn" | "error";
    time: string;
}

export default function VPTScannerControl() {
    const [scanStatus, setScanStatus] = useState<VPTScanStatus | null>(null);
    const [researchStatus, setResearchStatus] = useState<VPTResearchStatus | null>(null);
    const [conditionStatus, setConditionStatus] = useState<VPTConditionStatus | null>(null);
    const [pgeStatus, setPgeStatus] = useState<VPTPgeStatus | null>(null);
    const [selectedCity, setSelectedCity] = useState<string>("");
    const [logs, setLogs] = useState<LogEntry[]>([
        { message: "Scanner control panel loaded", type: "info", time: new Date().toLocaleTimeString() },
    ]);
    const { toast } = useToast();

    const addLog = useCallback((message: string, type: LogEntry["type"] = "info") => {
        setLogs((prev) => [
            { message, type, time: new Date().toLocaleTimeString() },
            ...prev.slice(0, 49),
        ]);
    }, []);

    const refreshAllStatus = useCallback(async () => {
        try {
            const [scan, research, condition, pge] = await Promise.all([
                vptGetScanStatus(),
                vptGetResearchStatus(),
                vptGetConditionStatus(),
                vptGetPgeStatus(),
            ]);
            setScanStatus(scan);
            setResearchStatus(research);
            setConditionStatus(condition);
            setPgeStatus(pge);
        } catch (error) {
            addLog("Error fetching status", "error");
        }
    }, [addLog]);

    useEffect(() => {
        refreshAllStatus();
        const interval = setInterval(refreshAllStatus, 5000);
        return () => clearInterval(interval);
    }, [refreshAllStatus]);

    const handleStartCityScan = async () => {
        if (!selectedCity) {
            toast({ title: "Select a city first", variant: "destructive" });
            return;
        }
        try {
            const result = await vptStartScan(selectedCity, false);
            addLog(result.message, result.status === "ok" ? "info" : "error");
            refreshAllStatus();
        } catch (error) {
            addLog("Failed to start scan", "error");
        }
    };

    const handleStartContinuousScan = async () => {
        try {
            const result = await vptStartScan(undefined, true);
            addLog(result.message, result.status === "ok" ? "info" : "error");
            refreshAllStatus();
        } catch (error) {
            addLog("Failed to start continuous scan", "error");
        }
    };

    const handleStopScan = async () => {
        try {
            const result = await vptStopScan();
            addLog(result.message, result.status === "ok" ? "info" : "warn");
            refreshAllStatus();
        } catch (error) {
            addLog("Failed to stop scan", "error");
        }
    };

    const handleResearchFavorites = async () => {
        try {
            const favorites = await vptGetFavorites();
            if (favorites.length === 0) {
                addLog("No favorites to research", "warn");
                return;
            }
            const result = await vptStartResearch(favorites);
            addLog(result.message, result.status === "ok" ? "info" : "error");
            refreshAllStatus();
        } catch (error) {
            addLog("Failed to start research", "error");
        }
    };

    const handleConditionScanAll = async () => {
        try {
            const result = await vptStartConditionScanAll();
            addLog(result.message, result.status === "ok" ? "info" : "error");
            refreshAllStatus();
        } catch (error) {
            addLog("Failed to start condition scan", "error");
        }
    };

    const handlePgeScanAll = async () => {
        try {
            const result = await vptStartPgeScanAll();
            addLog(result.message, result.status === "ok" ? "info" : "error");
            refreshAllStatus();
        } catch (error) {
            addLog("Failed to start PGE scan", "error");
        }
    };

    const handlePgeStop = async () => {
        try {
            const result = await vptStopPgeScan();
            addLog(result.message, result.status === "ok" ? "info" : "warn");
            refreshAllStatus();
        } catch (error) {
            addLog("Failed to stop PGE scan", "error");
        }
    };

    return (
        <div className="space-y-6">
            {/* Main Scan Status */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <div>
                        <CardTitle className="text-lg">Property Scanner Status</CardTitle>
                        <CardDescription>Control the main property scanning process</CardDescription>
                    </div>
                    <Button variant="ghost" size="sm" onClick={refreshAllStatus}>
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="text-center p-3 bg-muted rounded-lg">
                            <div className="text-2xl font-bold">
                                {scanStatus?.is_running ? (
                                    <Badge className="bg-green-100 text-green-800">
                                        {scanStatus.continuous_mode ? "CONTINUOUS" : "RUNNING"}
                                    </Badge>
                                ) : (
                                    <Badge variant="secondary">STOPPED</Badge>
                                )}
                            </div>
                            <div className="text-sm text-muted-foreground mt-1">Status</div>
                        </div>
                        <div className="text-center p-3 bg-muted rounded-lg">
                            <div className="text-2xl font-bold">{scanStatus?.current_city || "-"}</div>
                            <div className="text-sm text-muted-foreground mt-1">Current City</div>
                        </div>
                        <div className="text-center p-3 bg-muted rounded-lg">
                            <div className="text-2xl font-bold">{scanStatus?.total_bills?.toLocaleString() || 0}</div>
                            <div className="text-sm text-muted-foreground mt-1">Total Records</div>
                        </div>
                        <div className="text-center p-3 bg-muted rounded-lg">
                            <div className="text-2xl font-bold">{scanStatus?.vpt_count?.toLocaleString() || 0}</div>
                            <div className="text-sm text-muted-foreground mt-1">VPT Properties</div>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-3 items-center">
                        <Select value={selectedCity} onValueChange={setSelectedCity}>
                            <SelectTrigger className="w-48">
                                <SelectValue placeholder="Select a city..." />
                            </SelectTrigger>
                            <SelectContent>
                                {scanStatus?.available_cities?.map((city) => (
                                    <SelectItem key={city} value={city}>
                                        {city}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button onClick={handleStartCityScan} disabled={scanStatus?.is_running || !selectedCity}>
                            <Play className="h-4 w-4 mr-1" />
                            Scan City
                        </Button>
                        <Button onClick={handleStartContinuousScan} disabled={scanStatus?.is_running} variant="secondary">
                            <Play className="h-4 w-4 mr-1" />
                            Continuous Scan
                        </Button>
                        <Button
                            onClick={handleStopScan}
                            disabled={!scanStatus?.is_running || !scanStatus?.continuous_mode}
                            variant="destructive"
                        >
                            <Square className="h-4 w-4 mr-1" />
                            Stop
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Secondary Scanners */}
            <div className="grid md:grid-cols-3 gap-4">
                {/* Research Scanner */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Search className="h-4 w-4" />
                            Deep Research
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Status:</span>
                            {researchStatus?.is_running ? (
                                <Badge className="bg-green-100 text-green-800">Running</Badge>
                            ) : researchStatus?.api_configured ? (
                                <Badge variant="secondary">Idle</Badge>
                            ) : (
                                <Badge variant="destructive">No API Key</Badge>
                            )}
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Completed:</span>
                            <span>{researchStatus?.total_completed || 0}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Queue:</span>
                            <span>{researchStatus?.queue_length || 0}</span>
                        </div>
                        <Button
                            onClick={handleResearchFavorites}
                            className="w-full"
                            size="sm"
                            disabled={researchStatus?.is_running}
                        >
                            Research Favorites
                        </Button>
                    </CardContent>
                </Card>

                {/* Condition Scanner */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Camera className="h-4 w-4" />
                            Condition Scanner
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Status:</span>
                            {conditionStatus?.is_running ? (
                                <Badge className="bg-green-100 text-green-800">Scanning</Badge>
                            ) : (
                                <Badge variant="secondary">Idle</Badge>
                            )}
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Scanned:</span>
                            <span>{conditionStatus?.total_scanned || 0}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Avg Score:</span>
                            <span>{conditionStatus?.average_score?.toFixed(1) || "-"}/10</span>
                        </div>
                        <Button
                            onClick={handleConditionScanAll}
                            className="w-full"
                            size="sm"
                            disabled={conditionStatus?.is_running}
                        >
                            Scan All Unscanned
                        </Button>
                    </CardContent>
                </Card>

                {/* PGE Scanner */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Zap className="h-4 w-4" />
                            PGE Power Status
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Status:</span>
                            {pgeStatus?.is_running ? (
                                <Badge className="bg-green-100 text-green-800">Scanning</Badge>
                            ) : (
                                <Badge variant="secondary">Idle</Badge>
                            )}
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Power On:</span>
                            <span className="text-green-600">{pgeStatus?.total_power_on || 0}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Power Off:</span>
                            <span className="text-red-600">{pgeStatus?.total_power_off || 0}</span>
                        </div>
                        <div className="flex gap-2">
                            <Button
                                onClick={handlePgeScanAll}
                                className="flex-1"
                                size="sm"
                                disabled={pgeStatus?.is_running}
                            >
                                Scan All
                            </Button>
                            <Button
                                onClick={handlePgeStop}
                                variant="destructive"
                                size="sm"
                                disabled={!pgeStatus?.is_running}
                            >
                                Stop
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Activity Log */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-lg">Activity Log</CardTitle>
                </CardHeader>
                <CardContent>
                    <ScrollArea className="h-48 rounded border bg-slate-950 p-3">
                        {logs.map((log, i) => (
                            <div
                                key={i}
                                className={`text-sm font-mono ${log.type === "error"
                                        ? "text-red-400"
                                        : log.type === "warn"
                                            ? "text-yellow-400"
                                            : "text-green-400"
                                    }`}
                            >
                                [{log.time}] {log.message}
                            </div>
                        ))}
                    </ScrollArea>
                </CardContent>
            </Card>
        </div>
    );
}
