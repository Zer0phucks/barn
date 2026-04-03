import { useState, useEffect, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Play, Square } from "lucide-react";
import {
  getWorkerStatus,
  resumeScan,
  vptStopScan,
  type VPTWorkerState,
} from "@/services/vptApi";

interface WorkerStatusProps {
  onAction?: () => void;
}

function deriveLabel(state: VPTWorkerState): string {
  if (!state.worker || state.worker.status === "offline") {
    return "Worker offline";
  }
  if (state.active_job) {
    const { job_type, current_city, current_apn } = state.active_job;
    const parts = [job_type];
    if (current_city) parts.push(`– ${current_city}`);
    if (current_apn) parts.push(current_apn);
    return `Worker online · running ${parts.join(" ")}`;
  }
  if (state.last_interrupted_job) {
    return "Worker online · interrupted job available";
  }
  return "Worker online · idle";
}

export default function WorkerStatus({ onAction }: WorkerStatusProps) {
  const [state, setState] = useState<VPTWorkerState | null>(null);
  const [isActing, setIsActing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const result = await getWorkerStatus();
      setState(result);
    } catch {
      setState({ worker: null, active_job: null, last_interrupted_job: null });
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 15000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const handleResume = async () => {
    setIsActing(true);
    try {
      await resumeScan();
      await refresh();
      onAction?.();
    } finally {
      setIsActing(false);
    }
  };

  const handleStop = async () => {
    setIsActing(true);
    try {
      await vptStopScan();
      await refresh();
      onAction?.();
    } finally {
      setIsActing(false);
    }
  };

  if (!state) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="h-2.5 w-2.5 rounded-full bg-gray-300 animate-pulse" />
        Connecting…
      </div>
    );
  }

  const isOffline = !state.worker || state.worker.status === "offline";
  const hasActiveJob = Boolean(state.active_job);
  const hasInterrupted = Boolean(state.last_interrupted_job) && !hasActiveJob;
  const label = deriveLabel(state);

  const dotColor = isOffline
    ? "bg-gray-400"
    : hasActiveJob
    ? "bg-green-500"
    : hasInterrupted
    ? "bg-yellow-500"
    : "bg-green-500";

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="flex items-center gap-2 rounded-full border px-3 py-1 text-sm">
        <span className={`h-2.5 w-2.5 rounded-full ${dotColor}`} />
        <span
          className={
            isOffline
              ? "text-muted-foreground"
              : hasActiveJob
              ? "text-green-700"
              : hasInterrupted
              ? "text-yellow-700"
              : "text-green-700"
          }
        >
          {label}
        </span>
      </span>

      {hasActiveJob && state.active_job && (
        <span className="text-sm text-muted-foreground">
          {state.active_job.processed_count.toLocaleString()} processed /{" "}
          {state.active_job.hit_count.toLocaleString()} hits
        </span>
      )}

      {hasActiveJob && (
        <Button
          size="sm"
          variant="destructive"
          onClick={handleStop}
          disabled={isActing}
          data-testid="stop-btn"
        >
          <Square className="h-3.5 w-3.5 mr-1" />
          Stop
        </Button>
      )}

      {hasInterrupted && (
        <Button
          size="sm"
          variant="outline"
          onClick={handleResume}
          disabled={isActing}
          data-testid="resume-btn"
        >
          <Play className="h-3.5 w-3.5 mr-1" />
          Resume last scan
        </Button>
      )}

      {state.last_interrupted_job && !hasActiveJob && (
        <Badge variant="secondary" className="text-xs">
          interrupted: {state.last_interrupted_job.job_type}
          {state.last_interrupted_job.current_city
            ? ` / ${state.last_interrupted_job.current_city}`
            : ""}
        </Badge>
      )}
    </div>
  );
}
