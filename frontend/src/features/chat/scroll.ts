export function isNearBottom(
  element: Pick<HTMLElement, "scrollHeight" | "scrollTop" | "clientHeight">,
  threshold = 96,
): boolean {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= threshold;
}

export function preservedScrollTop(
  previousTop: number,
  previousHeight: number,
  nextHeight: number,
): number {
  return previousTop + Math.max(0, nextHeight - previousHeight);
}
