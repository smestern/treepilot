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

// Count max depth of tree
function getTreeDepth(node: TreeNode, depth = 0): number {
  if (!node.children || node.children.length === 0) {
    return depth;
  }
  return Math.max(...node.children.map(child => getTreeDepth(child, depth + 1)));
}

export default function AncestorTree({ data, onNodeClick, selectedId }: AncestorTreeProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [maxGenerations, setMaxGenerations] = useState(5);
  const maxDepth = getTreeDepth(data);

  // Popover state
  const [hoveredNode, setHoveredNode] = useState<HoverState | null>(null);
  const [pinnedNode, setPinnedNode] = useState<HoverState | null>(null);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentZoomRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);
  
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

    console.log('[AncestorTree] Starting tree render...');

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();

    const container = containerRef.current;
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    const margin = { top: 40, right: 120, bottom: 40, left: 120 };

    console.log('[AncestorTree] Container dimensions:', { width: containerWidth, height: containerHeight });
    
    if (containerWidth === 0 || containerHeight === 0) {
      console.warn('[AncestorTree] Container has zero dimensions, tree cannot render');
      return;
    }

    // Count nodes to calculate appropriate tree dimensions
    const limitedData = limitTreeDepth(data, maxGenerations);
    const tempRoot = d3.hierarchy(limitedData);
    const nodeCount = tempRoot.descendants().length;
    const nodeSpacing = 50; // pixels between nodes vertically
    
    // Calculate tree dimensions - fit to viewport but ensure minimum spacing
    const minTreeHeight = nodeCount * nodeSpacing;
    const treeHeight = Math.max(containerHeight - margin.top - margin.bottom, minTreeHeight);
    const treeWidth = containerWidth - margin.left - margin.right;

    // Create tree layout - horizontal, going right for ancestors
    const treeLayout = d3.tree<TreeNode>()
      .size([treeHeight, treeWidth])
      .separation((a, b) => (a.parent === b.parent ? 1 : 1.5));

    // Create hierarchy and compute layout
    const root = d3.hierarchy(limitedData);
    const treeData = treeLayout(root);
    console.log('[AncestorTree] Hierarchy created, descendants:', root.descendants().length, 'maxGenerations:', maxGenerations);

    // Calculate bounds of the tree
    const nodes = treeData.descendants();
    const xExtent = d3.extent(nodes, d => d.y) as [number, number]; // d.y is horizontal position
    const yExtent = d3.extent(nodes, d => d.x) as [number, number]; // d.x is vertical position
    const treeBoundsWidth = xExtent[1] - xExtent[0];
    const treeBoundsHeight = yExtent[1] - yExtent[0];

    // Create SVG with zoom behavior
    const svg = d3.select(svgRef.current)
      .attr('width', containerWidth)
      .attr('height', containerHeight);

    const g = svg.append('g');

    // Add zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        currentZoomRef.current = event.transform;
        
        // Update pinned node position on zoom
        const currentPinned = pinnedNodeRef.current;
        if (currentPinned) {
          const nodeData = treeData.descendants().find(n => n.data.id === currentPinned.id);
          if (nodeData && containerRef.current) {
            const containerRect = containerRef.current.getBoundingClientRect();
            const screenX = event.transform.applyX(nodeData.y) + containerRect.left;
            const screenY = event.transform.applyY(nodeData.x) + containerRect.top;
            setPinnedNode({ id: currentPinned.id, x: screenX, y: screenY });
          }
        }
      });

    svg.call(zoom);

    // Calculate initial scale to fit tree in viewport with padding
    const padding = 100;
    const scaleX = (containerWidth - padding * 2) / (treeBoundsWidth || 1);
    const scaleY = (containerHeight - padding * 2) / (treeBoundsHeight || 1);
    const scale = Math.min(1, scaleX, scaleY);
    
    // Center the tree in the viewport
    const treeCenterX = (xExtent[0] + xExtent[1]) / 2;
    const treeCenterY = (yExtent[0] + yExtent[1]) / 2;
    const initialX = containerWidth / 2 - treeCenterX * scale;
    const initialY = containerHeight / 2 - treeCenterY * scale;
    svg.call(zoom.transform, d3.zoomIdentity.translate(initialX, initialY).scale(scale));
    console.log('[AncestorTree] Tree layout computed');

    // Create links (curved paths)
    const linkGenerator = d3.linkHorizontal<d3.HierarchyPointLink<TreeNode>, d3.HierarchyPointNode<TreeNode>>()
      .x(d => d.y)
      .y(d => d.x);

    g.selectAll('.tree-link')
      .data(treeData.links())
      .enter()
      .append('path')
      .attr('class', 'tree-link')
      .attr('d', linkGenerator as unknown as string);

    // Create node groups
    const nodeGroups = g.selectAll('.tree-node')
      .data(treeData.descendants())
      .enter()
      .append('g')
      .attr('class', d => {
        let classes = 'tree-node';
        const gender = d.data.gender;
        if (gender === 'M') classes += ' male';
        else if (gender === 'F') classes += ' female';
        if (d.data.id === selectedId) classes += ' selected';
        return classes;
      })
      .attr('transform', d => `translate(${d.y},${d.x})`)
      .style('cursor', 'pointer')
      .on('click', (_, d) => {
        onNodeClick(d.data);
      });

    // Add circles for nodes
    nodeGroups.append('circle')
      .attr('r', 20);

    // Add name labels
    nodeGroups.append('text')
      .attr('dy', '0.35em')
      .attr('x', d => d.children ? -28 : 28)
      .attr('text-anchor', d => d.children ? 'end' : 'start')
      .text(d => {
        const name = d.data.fullName || 'Unknown';
        return name.length > 20 ? name.substring(0, 18) + '...' : name;
      });

    // Add year labels below name
    nodeGroups.append('text')
      .attr('dy', '1.5em')
      .attr('x', d => d.children ? -28 : 28)
      .attr('text-anchor', d => d.children ? 'end' : 'start')
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
          .attr('r', 25);
        
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
            const screenX = transform.applyX(d.y) + containerRect.left;
            const screenY = transform.applyY(d.x) + containerRect.top;
            setHoveredNode({ id: d.data.id, x: screenX, y: screenY });
          }
        }, HOVER_DELAY);
      })
      .on('mouseleave', function() {
        // Scale down circle
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', 20);
        
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

    console.log('[AncestorTree] Tree rendering complete');

  }, [data, selectedId, onNodeClick, maxGenerations]);

  return (
    <div ref={containerRef} className="absolute inset-0 bg-slate-900">
      <svg ref={svgRef} className="w-full h-full" />
      
      {/* Generation Control */}
      <div className="absolute top-4 left-4 bg-slate-800/90 backdrop-blur rounded-lg p-3 text-sm">
        <div className="flex items-center gap-3">
          <span className="text-slate-300">Generations:</span>
          <button
            onClick={() => setMaxGenerations(g => Math.max(1, g - 1))}
            disabled={maxGenerations <= 1}
            className="w-8 h-8 rounded bg-slate-700 text-white hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            −
          </button>
          <span className="text-white font-medium w-6 text-center">{maxGenerations}</span>
          <button
            onClick={() => setMaxGenerations(g => Math.min(maxDepth, g + 1))}
            disabled={maxGenerations >= maxDepth}
            className="w-8 h-8 rounded bg-slate-700 text-white hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            +
          </button>
          <span className="text-slate-500 text-xs">of {maxDepth}</span>
        </div>
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
