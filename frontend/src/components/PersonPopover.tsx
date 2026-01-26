import { useEffect, useState } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { X, Pin, Briefcase, Calendar, User } from 'lucide-react';
import { PersonMetadata } from '../types';

interface PersonPopoverProps {
  personId: string | null;
  position: { x: number; y: number } | null;
  isPinned: boolean;
  onPin: () => void;
  onClose: () => void;
  containerRef: React.RefObject<HTMLDivElement>;
}

// Loading skeleton component
function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      <div className="h-5 bg-slate-600 rounded w-3/4"></div>
      <div className="space-y-2">
        <div className="h-3 bg-slate-600 rounded w-full"></div>
        <div className="h-3 bg-slate-600 rounded w-5/6"></div>
        <div className="h-3 bg-slate-600 rounded w-4/6"></div>
      </div>
    </div>
  );
}

// Cache for metadata to avoid re-fetching
const metadataCache = new Map<string, PersonMetadata>();

export default function PersonPopover({
  personId,
  position,
  isPinned,
  onPin,
  onClose,
  containerRef,
}: PersonPopoverProps) {
  const [metadata, setMetadata] = useState<PersonMetadata | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch metadata when personId changes
  useEffect(() => {
    if (!personId) {
      setMetadata(null);
      return;
    }

    // Check cache first
    const cached = metadataCache.get(personId);
    if (cached) {
      setMetadata(cached);
      setIsLoading(false);
      return;
    }

    // Fetch from API
    setIsLoading(true);
    setError(null);

    const cleanId = personId.replace(/@/g, '');
    fetch(`/api/person/${cleanId}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error('Failed to fetch person details');
        }
        return res.json();
      })
      .then((data: PersonMetadata) => {
        metadataCache.set(personId, data);
        setMetadata(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('[PersonPopover] Error fetching metadata:', err);
        setError(err.message);
        setIsLoading(false);
      });
  }, [personId]);

  const isOpen = Boolean(personId && position);

  if (!isOpen) return null;

  // Calculate position relative to container
  const containerRect = containerRef.current?.getBoundingClientRect();
  const popoverStyle: React.CSSProperties = {
    position: 'absolute',
    left: position!.x - (containerRect?.left ?? 0) + 30,
    top: position!.y - (containerRect?.top ?? 0) - 20,
    zIndex: 50,
    // Only enable pointer events when pinned, otherwise let events pass through to tree
    pointerEvents: isPinned ? 'auto' : 'none',
  };

  return (
    <div style={popoverStyle}>
      <Popover.Root open={isOpen}>
        <Popover.Anchor />
        <Popover.Content
          className="bg-slate-800/95 backdrop-blur-sm border border-slate-700 rounded-lg shadow-xl p-4 w-72 text-sm"
          sideOffset={5}
          style={{ pointerEvents: isPinned ? 'auto' : 'none' }}
          onPointerDownOutside={(e) => {
            // Don't close if pinned
            if (isPinned) {
              e.preventDefault();
            }
          }}
        >
            {/* Header with pin/close buttons */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                {isLoading ? (
                  <div className="h-5 bg-slate-600 rounded w-3/4 animate-pulse"></div>
                ) : metadata ? (
                  <h3 className="font-semibold text-white text-base">
                    {metadata.fullName}
                  </h3>
                ) : null}
              </div>
              <div className="flex items-center gap-1 ml-2">
                <button
                  onClick={onPin}
                  className={`p-1 rounded hover:bg-slate-700 transition-colors ${
                    isPinned ? 'text-emerald-400' : 'text-slate-400'
                  }`}
                  title={isPinned ? 'Unpin' : 'Pin popover'}
                >
                  <Pin className="w-4 h-4" />
                </button>
                <button
                  onClick={onClose}
                  className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                  title="Close"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Content */}
            {isLoading ? (
              <LoadingSkeleton />
            ) : error ? (
              <p className="text-red-400">{error}</p>
            ) : metadata ? (
              <div className="space-y-2 text-slate-300">
                {/* Gender & ID */}
                <div className="flex items-center gap-2 text-slate-400 text-xs">
                  <User className="w-3 h-3" />
                  <span>
                    {metadata.gender === 'M'
                      ? 'Male'
                      : metadata.gender === 'F'
                      ? 'Female'
                      : 'Unknown'}
                  </span>
                  <span className="text-slate-600">•</span>
                  <span className="font-mono">{metadata.id}</span>
                </div>

                {/* Birth */}
                {(metadata.birthYear || metadata.birthPlace) && (
                  <div className="flex items-start gap-2">
                    <Calendar className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <span className="text-slate-400 text-xs">Born:</span>
                      <p className="text-slate-200">
                        {metadata.birthYear && <span>{metadata.birthYear}</span>}
                        {metadata.birthYear && metadata.birthPlace && ' • '}
                        {metadata.birthPlace && <span>{metadata.birthPlace}</span>}
                      </p>
                    </div>
                  </div>
                )}

                {/* Death */}
                {(metadata.deathYear || metadata.deathPlace) && (
                  <div className="flex items-start gap-2">
                    <Calendar className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <span className="text-slate-400 text-xs">Died:</span>
                      <p className="text-slate-200">
                        {metadata.deathYear && <span>{metadata.deathYear}</span>}
                        {metadata.deathYear && metadata.deathPlace && ' • '}
                        {metadata.deathPlace && <span>{metadata.deathPlace}</span>}
                      </p>
                    </div>
                  </div>
                )}

                {/* Occupation */}
                {metadata.occupation && (
                  <div className="flex items-start gap-2">
                    <Briefcase className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <span className="text-slate-400 text-xs">Occupation:</span>
                      <p className="text-slate-200">{metadata.occupation}</p>
                    </div>
                  </div>
                )}

                {/* Notes */}
                {metadata.notes && metadata.notes.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-slate-700">
                    <span className="text-slate-400 text-xs">Notes:</span>
                    <div className="mt-1 space-y-1">
                      {metadata.notes.slice(0, 2).map((note, idx) => (
                        <p
                          key={idx}
                          className="text-slate-300 text-xs leading-relaxed line-clamp-2"
                        >
                          {note}
                        </p>
                      ))}
                      {metadata.notes.length > 2 && (
                        <p className="text-slate-500 text-xs">
                          +{metadata.notes.length - 2} more notes
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* No extra info message */}
                {!metadata.birthPlace &&
                  !metadata.deathPlace &&
                  !metadata.occupation &&
                  (!metadata.notes || metadata.notes.length === 0) && (
                    <p className="text-slate-500 text-xs italic">
                      No additional details available.
                    </p>
                  )}
              </div>
            ) : null}

            <Popover.Arrow className="fill-slate-800" />
          </Popover.Content>
      </Popover.Root>
    </div>
  );
}
