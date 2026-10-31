import clsx from "clsx";
import { VideoOff } from "lucide-react";
import { useEffect, useState } from "react";
import { streamUrl } from "../lib/api";
import type { Camera } from "../lib/types";
import { StatusBadge } from "./ui";

/** MJPEG stream of annotated frames produced by the vision worker. Reconnects automatically. */
export default function CameraFeed({ camera, className, compact }: { camera: Camera; className?: string; compact?: boolean }) {
  const [nonce, setNonce] = useState(0);
  const [failed, setFailed] = useState(false);
  const running = camera.enabled && camera.status !== "stopped";

  useEffect(() => {
    if (!running) return;
    setFailed(false);
    const id = window.setInterval(() => setNonce((n) => n + 1), failed ? 4000 : 60000);
    return () => window.clearInterval(id);
  }, [running, failed, camera.status]);

  return (
    <div className={clsx("relative overflow-hidden rounded-2xl bg-[#e7eef3]", className)}>
      <div className="aspect-video w-full">
        {running && !failed ? (
          <img key={nonce} src={`${streamUrl(camera.code)}&n=${nonce}`} alt={`Live view from ${camera.name}`}
            className="h-full w-full object-cover" onError={() => setFailed(true)} />
        ) : (
          <div className="grid h-full place-items-center text-center text-ink-faint">
            <div>
              <VideoOff className="mx-auto mb-2" size={compact ? 20 : 28} />
              <p className="text-sm font-medium">{running ? "Waiting for frames from the vision worker" : "Camera stopped"}</p>
              {!compact && running && <p className="mt-1 text-xs">Start it with: python run.py dev (or python worker.py)</p>}
            </div>
          </div>
        )}
      </div>
      <div className="absolute left-3 top-3 flex items-center gap-2">
        <span className="rounded-full bg-white/85 px-2.5 py-0.5 text-xs font-semibold text-ink backdrop-blur">{camera.code}</span>
        <StatusBadge status={camera.status} />
      </div>
      {!compact && camera.status === "online" && (
        <span className="absolute right-3 top-3 rounded-full bg-white/85 px-2.5 py-0.5 text-xs font-semibold text-ink-soft backdrop-blur num">{camera.fps.toFixed(1)} fps</span>
      )}
    </div>
  );
}
