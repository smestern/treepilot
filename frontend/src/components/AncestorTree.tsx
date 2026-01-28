import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { TreeNode, Individual } from '../types';
import PersonPopover from './PersonPopover';

interface AncestorTreeProps {
  data: TreeNode;
  onNodeClick: (person: Individual) => void;
  selectedId?: string;
}

// Hover state type
interface HoverState {
  id: string;
  x: number;
  y: number;
}

// Hover delay in milliseconds
const HOVER_DELAY = 300;
const CLOSE_DELAY = 100;

// Helper function to limit tree depth
function limitTreeDepth(node: TreeNode, maxDepth: number, currentDepth = 0): TreeNode {
  if (currentDepth >= maxDepth) {
    // Return node without children
    return { ...node, children: undefined };
  }
  
  if (!node.children || node.children.length === 0) {
    return node;
  }
  
  return {
    ...node,
    children: node.children.map(child => limitTreeDepth(child, maxDepth, currentDepth + 1))
  };
}

// Count max depth of tree (for ancestors)
function getTreeDepth(node: TreeNode, depth = 0): number {
  if (!node.children || node.children.length === 0) {
    // Also check ancestors array for bidirectional tree
    if (node.ancestors && node.ancestors.length > 0) {
      return Math.max(...node.ancestors.map(a => getTreeDepth({ ...a, children: a.children }, depth + 1)));
    }
    return depth;
  }
  return Math.max(...node.children.map(child => getTreeDepth(child, depth + 1)));
}

// Get max depth for descendants
function getDescendantDepth(node: TreeNode, depth = 0): number {
  if (!node.descendants && !node.children) {
    return depth;
  }
  const children = node.descendants || node.children || [];
  if (children.length === 0) return depth;
  return Math.max(...children.map(child => getDescendantDepth(child, depth + 1)));
}

// Prepare ancestor tree structure for D3
function prepareAncestorTree(rootData: TreeNode, maxGenerations: number): TreeNode | null {
  if (!rootData.ancestors || rootData.ancestors.length === 0) {
    return null;
  }
  
  // Create a virtual root with ancestors as children
  const ancestorRoot: TreeNode = {
    ...rootData,
    children: rootData.ancestors.map(a => limitTreeDepth(a, maxGenerations - 1, 0))
  };
  
  return ancestorRoot;
}

// Prepare descendant tree structure for D3
function prepareDescendantTree(rootData: TreeNode, maxGenerations: number): TreeNode | null {
  if (!rootData.descendants || rootData.descendants.length === 0) {
    return null;
  }
  
  // Create a virtual root with descendants as children
  const descendantRoot: TreeNode = {
    ...rootData,
    children: rootData.descendants.map(d => limitTreeDepth(d, maxGenerations - 1, 0))
  };
  
  return descendantRoot;
}

export default function AncestorTree({ data, onNodeClick, selectedId }: AncestorTreeProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [ancestorGenerations, setAncestorGenerations] = useState(5);
  const [descendantGenerations, setDescendantGenerations] = useState(5);
  
  // Calculate max depths for ancestors and descendants
  const maxAncestorDepth = data.ancestors ? Math.max(1, getTreeDepth({ ...data, children: data.ancestors })) : 0;
  const maxDescendantDepth = data.descendants ? Math.max(1, getDescendantDepth({ ...data, descendants: data.descendants })) : 0;
  
  const hasAncestors = Boolean(data.ancestors && data.ancestors.length > 0);
  const hasDescendants = Boolean(data.descendants && data.descendants.length > 0);

  // Popover state
  const [hoveredNode, setHoveredNode] = useState<HoverState | null>(null);
  const [pinnedNode, setPinnedNode] = useState<HoverState | null>(null);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentZoomRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);
  
  // Store all rendered nodes for popover lookup
  const allNodesRef = useRef<Array<{ id: string; x: number; y: number }>>([]);
  
  // Refs for D3 event handlers to access current state without re-rendering tree
  const pinnedNodeRef = useRef<HoverState | null>(null);
  const hoveredNodeRef = useRef<HoverState | null>(null);
  
  // Keep refs in sync with state
  useEffect(() => {
    pinnedNodeRef.current = pinnedNode;
  }, [pinnedNode]);
  
  useEffect(() => {
    hoveredNodeRef.current = hoveredNode;
  }, [hoveredNode]);

  // Clear timeouts on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
      if (closeTimeoutRef.current) {
        clearTimeout(closeTimeoutRef.current);
      }
    };
  }, []);

  // Handle pin toggle
  const handlePin = useCallback(() => {
    if (pinnedNode) {
      setPinnedNode(null);
    } else if (hoveredNode) {
      setPinnedNode(hoveredNode);
    }
  }, [hoveredNode, pinnedNode]);

  // Handle close
  const handleClose = useCallback(() => {
    setPinnedNode(null);
    setHoveredNode(null);
  }, []);

  // Get active popover node (pinned takes precedence)
  const activeNode = pinnedNode || hoveredNode;

  useEffect(() => {
    console.log('[AncestorTree] useEffect triggered');
    console.log('[AncestorTree] svgRef.current:', svgRef.current ? 'exists' : 'null');
    console.log('[AncestorTree] containerRef.current:', containerRef.current ? 'exists' : 'null');
    console.log('[AncestorTree] data:', data);
    
    if (!svgRef.current || !containerRef.current || !data) {
      console.warn('[AncestorTree] Early return - missing refs or data');
      return;
    }

    console.log('[AncestorTree] Starting bidirectional tree render...');

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();
    allNodesRef.current = [];

    const container = containerRef.current;
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;

    console.log('[AncestorTree] Container dimensions:', { width: containerWidth, height: containerHeight });
    
    if (containerWidth === 0 || containerHeight === 0) {
      console.warn('[AncestorTree] Container has zero dimensions, tree cannot render');
      return;
    }

    // Create SVG with zoom behavior
    const svg = d3.select(svgRef.current)
      .attr('width', containerWidth)
      .attr('height', containerHeight);

    const g = svg.append('g');

    // Prepare tree data structures
    const ancestorData = prepareAncestorTree(data, ancestorGenerations);
    const descendantData = prepareDescendantTree(data, descendantGenerations);
    
    // Center point for the root person
    const centerX = containerWidth / 2;
    const centerY = containerHeight / 2;
    
    // Calculate available space for each direction
    const halfWidth = (containerWidth / 2) - 100; // Leave margin
    const nodeSpacing = 60;
    
    // Track all nodes and links for rendering
    interface NodePosition { id: string; x: number; y: number; data: TreeNode }
    interface LinkData { source: NodePosition; target: NodePosition }
    const allNodePositions: NodePosition[] = [];
    const allLinks: LinkData[] = [];
    
    // Add root person at center
    const rootPosition: NodePosition = { id: data.id, x: centerX, y: centerY, data: data };
    allNodePositions.push(rootPosition);
    
    // Helper to render a tree in a specific direction
    function layoutTree(
      treeData: TreeNode | null, 
      direction: 'left' | 'right',
      maxWidth: number,
      startX: number
    ) {
      if (!treeData || !treeData.children || treeData.children.length === 0) return;
      
      const root = d3.hierarchy(treeData);
      const nodeCount = root.descendants().length - 1; // Exclude root (we already have it)
      const treeHeight = Math.max(containerHeight - 100, nodeCount * nodeSpacing);
      
      const treeLayout = d3.tree<TreeNode>()
        .size([treeHeight, maxWidth])
        .separation((a, b) => (a.parent === b.parent ? 1 : 1.5));
      
      const layoutData = treeLayout(root);
      
      // Process nodes (skip root node, we already added it)
      layoutData.descendants().forEach((node, index) => {
        if (index === 0) return; // Skip root
        
        // Calculate position
        // For horizontal trees: d.y is horizontal position, d.x is vertical
        let nodeX: number;
        if (direction === 'right') {
          // Ancestors go right from center
          nodeX = startX + node.y;
        } else {
          // Descendants go left from center
          nodeX = startX - node.y;
        }
        const nodeY = centerY - (treeHeight / 2) + node.x;
        
        const pos: NodePosition = { id: node.data.id, x: nodeX, y: nodeY, data: node.data };
        allNodePositions.push(pos);
      });
      
      // Process links
      layoutData.links().forEach(link => {
        let sourceX: number, targetX: number;
        
        if (link.source.depth === 0) {
          // Link from root
          sourceX = startX;
        } else if (direction === 'right') {
          sourceX = startX + link.source.y;
        } else {
          sourceX = startX - link.source.y;
        }
        
        if (direction === 'right') {
          targetX = startX + link.target.y;
        } else {
          targetX = startX - link.target.y;
        }
        
        const sourceY = link.source.depth === 0 ? centerY : centerY - (treeHeight / 2) + link.source.x;
        const targetY = centerY - (treeHeight / 2) + link.target.x;
        
        allLinks.push({
          source: { id: link.source.data.id, x: sourceX, y: sourceY, data: link.source.data },
          target: { id: link.target.data.id, x: targetX, y: targetY, data: link.target.data }
        });
      });
    }
    
    // Layout ancestors (going right)
    layoutTree(ancestorData, 'right', halfWidth, centerX);
    
    // Layout descendants (going left)
    layoutTree(descendantData, 'left', halfWidth, centerX);
    
    // Store for popover lookup
    allNodesRef.current = allNodePositions.map(n => ({ id: n.id, x: n.x, y: n.y }));
    
    // Calculate bounds for auto-fit
    const xExtent = d3.extent(allNodePositions, d => d.x) as [number, number];
    const yExtent = d3.extent(allNodePositions, d => d.y) as [number, number];
    const treeBoundsWidth = (xExtent[1] - xExtent[0]) || 1;
    const treeBoundsHeight = (yExtent[1] - yExtent[0]) || 1;

    // Add zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        currentZoomRef.current = event.transform;
        
        // Update pinned node position on zoom
        const currentPinned = pinnedNodeRef.current;
        if (currentPinned) {
          const nodeData = allNodesRef.current.find(n => n.id === currentPinned.id);
          if (nodeData && containerRef.current) {
            const containerRect = containerRef.current.getBoundingClientRect();
            const screenX = event.transform.applyX(nodeData.x) + containerRect.left;
            const screenY = event.transform.applyY(nodeData.y) + containerRect.top;
            setPinnedNode({ id: currentPinned.id, x: screenX, y: screenY });
          }
        }
      });

    svg.call(zoom);

    // Calculate initial scale to fit tree in viewport with padding
    const padding = 100;
    const scaleX = (containerWidth - padding * 2) / treeBoundsWidth;
    const scaleY = (containerHeight - padding * 2) / treeBoundsHeight;
    const scale = Math.min(1, scaleX, scaleY);
    
    // Center the tree in the viewport
    const treeCenterX = (xExtent[0] + xExtent[1]) / 2;
    const treeCenterY = (yExtent[0] + yExtent[1]) / 2;
    const initialX = containerWidth / 2 - treeCenterX * scale;
    const initialY = containerHeight / 2 - treeCenterY * scale;
    svg.call(zoom.transform, d3.zoomIdentity.translate(initialX, initialY).scale(scale));
    console.log('[AncestorTree] Bidirectional tree layout computed');

    // Draw links (curved paths)
    g.selectAll('.tree-link')
      .data(allLinks)
      .enter()
      .append('path')
      .attr('class', 'tree-link')
      .attr('d', d => {
        const sourceX = d.source.x;
        const sourceY = d.source.y;
        const targetX = d.target.x;
        const targetY = d.target.y;
        
        // Create curved path
        const midX = (sourceX + targetX) / 2;
        return `M${sourceX},${sourceY} C${midX},${sourceY} ${midX},${targetY} ${targetX},${targetY}`;
      });

    // Create node groups
    const nodeGroups = g.selectAll('.tree-node')
      .data(allNodePositions)
      .enter()
      .append('g')
      .attr('class', d => {
        let classes = 'tree-node';
        const gender = d.data.gender;
        if (gender === 'M') classes += ' male';
        else if (gender === 'F') classes += ' female';
        if (d.data.id === selectedId) classes += ' selected';
        if (d.data.direction === 'root') classes += ' root';
        return classes;
      })
      .attr('transform', d => `translate(${d.x},${d.y})`)
      .style('cursor', 'pointer')
      .on('click', (_, d) => {
        onNodeClick(d.data);
      });

    // Add circles for nodes (larger for root)
    nodeGroups.append('circle')
      .attr('r', d => d.data.direction === 'root' ? 25 : 20);

    // Add name labels
    nodeGroups.append('text')
      .attr('dy', '0.35em')
      .attr('x', d => {
        if (d.data.direction === 'root') return 0;
        // Ancestors (right side) get labels on the right, descendants (left side) get labels on the left
        return d.data.direction === 'ancestor' ? 28 : -28;
      })
      .attr('text-anchor', d => {
        if (d.data.direction === 'root') return 'middle';
        return d.data.direction === 'ancestor' ? 'start' : 'end';
      })
      .text(d => {
        const name = d.data.fullName || 'Unknown';
        return name.length > 20 ? name.substring(0, 18) + '...' : name;
      });

    // Add year labels below name
    nodeGroups.append('text')
      .attr('dy', d => d.data.direction === 'root' ? '2em' : '1.5em')
      .attr('x', d => {
        if (d.data.direction === 'root') return 0;
        return d.data.direction === 'ancestor' ? 28 : -28;
      })
      .attr('text-anchor', d => {
        if (d.data.direction === 'root') return 'middle';
        return d.data.direction === 'ancestor' ? 'start' : 'end';
      })
      .attr('class', 'text-xs fill-slate-400')
      .text(d => {
        const birth = d.data.birthYear;
        const death = d.data.deathYear;
        if (birth && death) return `${birth} - ${death}`;
        if (birth) return `b. ${birth}`;
        if (death) return `d. ${death}`;
        return '';
      });

    // Add hover/popover behavior
    nodeGroups
      .on('mouseenter', function(_, d) {
        // Scale up circle
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', d.data.direction === 'root' ? 30 : 25);
        
        // Cancel any pending close
        if (closeTimeoutRef.current) {
          clearTimeout(closeTimeoutRef.current);
          closeTimeoutRef.current = null;
        }
        
        // Set hover with delay (unless pinned to this node)
        if (pinnedNodeRef.current?.id === d.data.id) return;
        
        // Clear any existing hover timeout
        if (hoverTimeoutRef.current) {
          clearTimeout(hoverTimeoutRef.current);
        }
        
        // Start delay timer
        hoverTimeoutRef.current = setTimeout(() => {
          if (containerRef.current) {
            const containerRect = containerRef.current.getBoundingClientRect();
            const transform = currentZoomRef.current;
            const screenX = transform.applyX(d.x) + containerRect.left;
            const screenY = transform.applyY(d.y) + containerRect.top;
            setHoveredNode({ id: d.data.id, x: screenX, y: screenY });
          }
        }, HOVER_DELAY);
      })
      .on('mouseleave', function(_, d) {
        // Scale down circle
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', d.data.direction === 'root' ? 25 : 20);
        
        // Clear hover timeout
        if (hoverTimeoutRef.current) {
          clearTimeout(hoverTimeoutRef.current);
          hoverTimeoutRef.current = null;
        }
        
        // Clear hovered node with a small delay (but not if pinned)
        if (!pinnedNodeRef.current) {
          closeTimeoutRef.current = setTimeout(() => {
            setHoveredNode(null);
          }, CLOSE_DELAY);
        }
      });

    console.log('[AncestorTree] Bidirectional tree rendering complete');

  }, [data, selectedId, onNodeClick, ancestorGenerations, descendantGenerations]);

  return (
    <div ref={containerRef} className="absolute inset-0 bg-slate-900">
      <svg ref={svgRef} className="w-full h-full" />
      
      {/* Generation Controls */}
      <div className="absolute top-4 left-4 bg-slate-800/90 backdrop-blur rounded-lg p-3 text-sm space-y-2">
        {/* Ancestor generations control */}
        {hasAncestors && (
          <div className="flex items-center gap-3">
            <span className="text-slate-300 w-24">Ancestors:</span>
            <button
              onClick={() => setAncestorGenerations(g => Math.max(1, g - 1))}
              disabled={ancestorGenerations <= 1}
              className="w-8 h-8 rounded bg-slate-700 text-white hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              −
            </button>
            <span className="text-white font-medium w-6 text-center">{ancestorGenerations}</span>
            <button
              onClick={() => setAncestorGenerations(g => Math.min(maxAncestorDepth + 1, g + 1))}
              disabled={ancestorGenerations >= maxAncestorDepth + 1}
              className="w-8 h-8 rounded bg-slate-700 text-white hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              +
            </button>
          </div>
        )}
        
        {/* Descendant generations control */}
        {hasDescendants && (
          <div className="flex items-center gap-3">
            <span className="text-slate-300 w-24">Descendants:</span>
            <button
              onClick={() => setDescendantGenerations(g => Math.max(1, g - 1))}
              disabled={descendantGenerations <= 1}
              className="w-8 h-8 rounded bg-slate-700 text-white hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              −
            </button>
            <span className="text-white font-medium w-6 text-center">{descendantGenerations}</span>
            <button
              onClick={() => setDescendantGenerations(g => Math.min(maxDescendantDepth + 1, g + 1))}
              disabled={descendantGenerations >= maxDescendantDepth + 1}
              className="w-8 h-8 rounded bg-slate-700 text-white hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              +
            </button>
          </div>
        )}
        
        {!hasAncestors && !hasDescendants && (
          <div className="text-slate-400 text-xs">No ancestors or descendants found</div>
        )}
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-slate-800/90 backdrop-blur rounded-lg p-3 text-sm">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-blue-500"></div>
            <span className="text-slate-300">Male</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-pink-500"></div>
            <span className="text-slate-300">Female</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-emerald-500"></div>
            <span className="text-slate-300">Unknown</span>
          </div>
        </div>
        <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
          <span>← Children</span>
          <span className="text-slate-600">|</span>
          <span>Parents →</span>
        </div>
        <p className="text-slate-500 mt-2 text-xs">
          Hover for info • Click to research • Scroll to zoom • Drag to pan
        </p>
      </div>

      {/* Person Info Popover */}
      <PersonPopover
        personId={activeNode?.id ?? null}
        position={activeNode ? { x: activeNode.x, y: activeNode.y } : null}
        isPinned={Boolean(pinnedNode)}
        onPin={handlePin}
        onClose={handleClose}
        containerRef={containerRef as React.RefObject<HTMLDivElement>}
      />
    </div>
  );
}
