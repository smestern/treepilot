import { useCallback, useEffect, useState } from 'react';

interface ResizableDividerProps {
  onResize: (rightWidth: number) => void;
  minLeftWidth?: number;
  maxLeftWidth?: number;
  containerRef: React.RefObject<HTMLDivElement>;
}

export default function ResizableDivider({
  onResize,
  minLeftWidth = 400,
  maxLeftWidth = 1200,
  containerRef,
}: ResizableDividerProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      // Calculate the right panel width (distance from mouse to right edge)
      const rightWidth = containerRect.right - e.clientX;
      
      // Clamp between min and max (these are for the right panel)
      const minRightWidth = 300;
      const maxRightWidth = 700;
      const clampedWidth = Math.max(minRightWidth, Math.min(maxRightWidth, rightWidth));
      onResize(clampedWidth);
    },
    [isDragging, onResize, containerRef]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  return (
    <div
      onMouseDown={handleMouseDown}
      className={`resizable-divider flex-shrink-0 w-1 bg-slate-700 hover:bg-emerald-500 cursor-col-resize transition-colors ${
        isDragging ? 'bg-emerald-500' : ''
      }`}
      title="Drag to resize"
    />
  );
}
