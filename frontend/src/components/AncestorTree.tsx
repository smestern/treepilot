import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { TreeNode, Individual } from '../types';

interface AncestorTreeProps {
  data: TreeNode;
  onNodeClick: (person: Individual) => void;
  selectedId?: string;
}

export default function AncestorTree({ data, onNodeClick, selectedId }: AncestorTreeProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

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
    const width = container.clientWidth;
    const height = container.clientHeight;
    const margin = { top: 40, right: 120, bottom: 40, left: 120 };

    console.log('[AncestorTree] Container dimensions:', { width, height });
    
    if (width === 0 || height === 0) {
      console.warn('[AncestorTree] Container has zero dimensions, tree cannot render');
      return;
    }

    // Create SVG with zoom behavior
    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${height / 2})`);

    // Add zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Initial transform to center the tree
    svg.call(zoom.transform, d3.zoomIdentity.translate(margin.left, height / 2));

    // Create tree layout - horizontal, going right for ancestors
    const treeLayout = d3.tree<TreeNode>()
      .size([height - margin.top - margin.bottom, width - margin.left - margin.right])
      .separation((a, b) => (a.parent === b.parent ? 1 : 1.5));

    // Create hierarchy
    const root = d3.hierarchy(data);
    console.log('[AncestorTree] Hierarchy created, descendants:', root.descendants().length);
    const treeData = treeLayout(root);
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

    // Create nodes
    const nodes = g.selectAll('.tree-node')
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
    nodes.append('circle')
      .attr('r', 20);

    // Add name labels
    nodes.append('text')
      .attr('dy', '0.35em')
      .attr('x', d => d.children ? -28 : 28)
      .attr('text-anchor', d => d.children ? 'end' : 'start')
      .text(d => {
        const name = d.data.fullName || 'Unknown';
        return name.length > 20 ? name.substring(0, 18) + '...' : name;
      });

    // Add year labels below name
    nodes.append('text')
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

    // Add tooltip behavior
    nodes
      .on('mouseenter', function(_, d) {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', 25);
      })
      .on('mouseleave', function() {
        d3.select(this).select('circle')
          .transition()
          .duration(200)
          .attr('r', 20);
      });

    console.log('[AncestorTree] Tree rendering complete');

  }, [data, selectedId, onNodeClick]);

  return (
    <div ref={containerRef} className="w-full h-full bg-slate-900">
      <svg ref={svgRef} className="w-full h-full" />
      
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
          Click a person to research • Scroll to zoom • Drag to pan
        </p>
      </div>
    </div>
  );
}
