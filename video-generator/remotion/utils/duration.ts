export function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function calculateTotalDuration(
  scenes: { durationInSeconds: number }[],
): number {
  return scenes.reduce((sum, scene) => sum + scene.durationInSeconds, 0);
}
