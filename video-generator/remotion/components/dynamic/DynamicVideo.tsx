import { OffthreadVideo, useVideoConfig, random } from "remotion";
import React, { useMemo } from "react";

export const DynamicVideo: React.FC<{ src: string; id: string; requiredDurationInFrames: number }> = ({ src, id, requiredDurationInFrames }) => {
  const { fps } = useVideoConfig();
  const sourceDurationInSeconds = 10; 
  const sourceDurationInFrames = sourceDurationInSeconds * fps;

  // Deterministic color grading
  const filter = useMemo(() => {
    const brightness = 0.95 + random(`${id}-vb`) * 0.15; 
    const contrast = 0.95 + random(`${id}-vc`) * 0.15;
    return `brightness(${brightness}) contrast(${contrast})`;
  }, [id]);

  // Random Slice (Trim) Logic
  const maxStartFrame = Math.max(0, sourceDurationInFrames - requiredDurationInFrames);
  const startFrom = Math.floor(random(`${id}-start`) * maxStartFrame);

  return (
    <OffthreadVideo 
      src={src} 
      startFrom={startFrom}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
        filter
      }}
    />
  );
};
