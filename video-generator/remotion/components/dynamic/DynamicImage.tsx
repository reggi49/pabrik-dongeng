import { Img, useCurrentFrame, useVideoConfig, random, prefetch } from "remotion";
import React, { useMemo, useEffect } from "react";

export const DynamicImage: React.FC<{ src: string; id: string }> = ({ src, id }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  useEffect(() => {
    prefetch(src, { contentType: "image" });
  }, [src]);

  const { filter, scaleStart, scaleEnd, dirX, dirY } = useMemo(() => {
    const brightness = 0.9 + random(`${id}-b`) * 0.2;
    const contrast = 0.95 + random(`${id}-c`) * 0.15;
    const sepia = random(`${id}-s`) * 0.2;
    const sStart = 1.05 + random(`${id}-scale`) * 0.1;
    const sEnd = sStart + (random(`${id}-dir`) > 0.5 ? 0.1 : -0.1);
    const dx = random(`${id}-x`) > 0.5 ? 1 : -1;
    const dy = random(`${id}-y`) > 0.5 ? 1 : -1;
    return {
      filter: `brightness(${brightness}) contrast(${contrast}) sepia(${sepia})`,
      scaleStart: sStart,
      scaleEnd: sEnd,
      dirX: dx,
      dirY: dy,
    };
  }, [id]);

  const progress = frame / durationInFrames;
  const currentScale = scaleStart + (scaleEnd - scaleStart) * progress;
  const translateX = dirX * (progress * 20);
  const translateY = dirY * (progress * 20);

  return (
    <Img
      src={src}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
        filter,
        transform: `scale(${currentScale}) translate(${translateX}px, ${translateY}px)`,
        transformOrigin: "center center",
      }}
    />
  );
};
