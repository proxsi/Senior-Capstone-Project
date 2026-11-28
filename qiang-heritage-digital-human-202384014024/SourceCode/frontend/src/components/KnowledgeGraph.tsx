/* Construct a browser graph from chunk metadata, with sample-data fallback.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Loader2, ZoomIn, ZoomOut, Maximize2, RotateCcw } from 'lucide-react';

interface KnowledgeGraphProps {
  /** Entity highlighted on the canvas; changing it recentres the view. */
  entity: string;
}

/** A vertex. `x`/`y` are injected and mutated by the force simulation at runtime. */
interface GraphNode {
  id: string;
  label: string;
  type: string;
  x?: number;
  y?: number;
}

/** A directed edge. react-force-graph rewrites the string endpoints into node objects. */
interface GraphLink {
  source: string;
  target: string;
  label: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({ entity }) => {
  /** Measured host element; the canvas is sized from its bounding box. */
  const containerRef = useRef<HTMLDivElement>(null);
  /** Imperative handle to ForceGraph2D, used for centreAt/zoom/zoomToFit. */
  const graphRef = useRef<any>(null);
  /** Current nodes and edges; replaced wholesale on every fetch. */
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  /** True while the chunk request is outstanding; swaps the canvas for a spinner. */
  const [loading, setLoading] = useState(true);
  /** Node id temporarily drawn in gold after an entity mention or a manual click. */
  const [highlightNode, setHighlightNode] = useState<string | null>(null);
  /** Mirror of the last zoom factor, because ForceGraph2D does not report it back. */
  const [zoomLevel, setZoomLevel] = useState(1);
  /** Canvas pixel size, kept in state so the force graph can be resized on window changes. */
  const [dimensions, setDimensions] = useState({ width: 300, height: 200 });

  // Initial data load only; the graph is fetched once per mount.
  useEffect(() => {
    fetchGraphData();
  }, []);

  /**
   * Track the container size.
   * The panel is laid out with flexbox and is often 0x0 on the first paint, so measurement
   * runs immediately, again after a 100 ms delay (layout settled), and on every window resize.
   * The listener and the timer are both torn down on cleanup to avoid leaks and double updates.
   */
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    };
    
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    
    const timer = setTimeout(updateDimensions, 100);
    
    return () => {
      window.removeEventListener('resize', updateDimensions);
      clearTimeout(timer);
    };
  }, [loading]);

  /**
   * Focus the node that matches the entity mentioned in the latest answer.
   * Matching is bidirectional: a short mention may be a substring of a longer node label and
   * vice versa, so either direction resolves to the same vertex. The 3 s reset keeps the
   * highlight temporary; its timer is not cleared because the component lives with the page.
   */
  useEffect(() => {
    if (entity && graphData.nodes.length > 0) {
      const targetNode = graphData.nodes.find(n => 
        n.label.includes(entity) || entity.includes(n.label)
      );
      if (targetNode && graphRef.current) {
        graphRef.current.centerAt(targetNode.x, targetNode.y, 1000);
        graphRef.current.zoom(2, 1000);
        setHighlightNode(targetNode.id);
        setTimeout(() => setHighlightNode(null), 3000);
      }
    }
  }, [entity, graphData]);

  /**
   * Load chunk metadata and derive a graph from it.
   * A capped limit keeps the simulation responsive; if the backend returns nothing (or fails)
   * a hard-coded sample graph is shown so the panel is never blank during a demo.
   */
  const fetchGraphData = async () => {
    setLoading(true);
    try {
      const response = await fetch('/knowledge-base/chunks?limit=100');
      const data = await response.json();
      
      if (data.items && data.items.length > 0) {
        const graphData = buildGraphFromChunks(data.items);
        setGraphData(graphData);
      } else {
        setGraphData(getDefaultGraphData());
      }
    } catch (error) {
      console.error('获取知识图谱数据失败:', error);
      setGraphData(getDefaultGraphData());
    } finally {
      setLoading(false);
    }
  };

  /**
   * Map chunks to nodes and edges.
   *
   * Each chunk contributes its `source_entity` as a node. If `relation_desc` contains the
   * related-item field, the value after the separator becomes a second node and an edge is
   * drawn between the two. A Map keyed by entity name de-duplicates nodes, so many chunks
   * about the same entity collapse into one vertex with several edges.
   *
   * The regex below matches that field name in both the full-width and ASCII colon variants
   * used in the source data.
   */
  const buildGraphFromChunks = (chunks: any[]): GraphData => {
    const nodesMap = new Map<string, GraphNode>();
    const links: GraphLink[] = [];
    
    chunks.forEach(chunk => {
      const entityId = chunk.source_entity;
      if (!entityId) return;
      
      // Create the primary node once; its label is the entity name shown on the canvas.
      if (!nodesMap.has(entityId)) {
        nodesMap.set(entityId, {
          id: entityId,
          label: entityId,
          type: chunk.entity_type || '其他'
        });
      }
      
      if (chunk.relation_desc) {
        const match = chunk.relation_desc.match(/关联项目[：:]\s*(.+)/);
        if (match) {
          const relatedEntity = match[1].trim();
          // Skip self-loops, which the force layout cannot render meaningfully.
          if (relatedEntity && relatedEntity !== entityId) {
            if (!nodesMap.has(relatedEntity)) {
              nodesMap.set(relatedEntity, {
                id: relatedEntity,
                label: relatedEntity,
                // The relation text does not carry a type, so assume a heritage item.
                type: '非遗项目'
              });
            }
            links.push({
              source: entityId,
              target: relatedEntity,
              label: '关联'
            });
          }
        }
      }
    });
    
    return {
      nodes: Array.from(nodesMap.values()),
      links: links
    };
  };

  /** Static demonstration graph used when the knowledge base is empty or unreachable. */
  const getDefaultGraphData = (): GraphData => {
    return {
      nodes: [
        { id: '羌族刺绣', label: '羌族刺绣', type: '非遗项目' },
        { id: '羌笛', label: '羌笛', type: '非遗项目' },
        { id: '羌年', label: '羌年', type: '节日' },
        { id: '羌族碉楼', label: '羌族碉楼', type: '非遗项目' },
        { id: '李兴秀', label: '李兴秀', type: '传承人' },
        { id: '阿坝州', label: '阿坝州', type: '地点' },
        { id: '挑花', label: '挑花', type: '技艺' },
        { id: '纳花', label: '纳花', type: '技艺' },
        { id: '瓦尔俄足节', label: '瓦尔俄足节', type: '节日' },
        { id: '羊皮鼓舞', label: '羊皮鼓舞', type: '非遗项目' },
      ],
      links: [
        { source: '羌族刺绣', target: '李兴秀', label: '传承人' },
        { source: '羌族刺绣', target: '阿坝州', label: '地区' },
        { source: '羌族刺绣', target: '挑花', label: '技法' },
        { source: '羌族刺绣', target: '纳花', label: '技法' },
        { source: '羌笛', target: '阿坝州', label: '地区' },
        { source: '羌年', target: '阿坝州', label: '地区' },
        { source: '羌年', target: '羌族刺绣', label: '展示' },
        { source: '羌年', target: '羌笛', label: '演奏' },
        { source: '羌族碉楼', target: '阿坝州', label: '地区' },
        { source: '瓦尔俄足节', target: '阿坝州', label: '地区' },
        { source: '羊皮鼓舞', target: '阿坝州', label: '地区' },
      ]
    };
  };

  /**
   * Node colour by entity type, with gold reserved for the transient highlight.
   * `highlightNode` is a dependency because the callback must be recreated when focus moves.
   */
  const getNodeColor = useCallback((node: GraphNode) => {
    if (highlightNode === node.id) {
      return '#FFD700';
    }
    switch (node.type) {
      case '非遗项目': return '#D72638';
      case '传承人': return '#F59E0B';
      case '节日': return '#8B5CF6';
      case '地点': return '#10B981';
      case '技艺': return '#3B82F6';
      default: return '#6B7280';
    }
  }, [highlightNode]);

  /**
   * Radius of each node in canvas units.
   * Heritage items are the focus of the graph, so they are drawn larger; the highlighted
   * node is temporarily enlarged to stand out against its neighbours.
   */
  const getNodeSize = useCallback((node: GraphNode) => {
    if (highlightNode === node.id) return 12;
    switch (node.type) {
      case '非遗项目': return 10;
      case '传承人': return 8;
      case '节日': return 8;
      default: return 6;
    }
  }, [highlightNode]);

  /** Clicking a node centres it and zooms in, mirroring the automatic entity focus. */
  const handleNodeClick = useCallback((node: any) => {
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 1000);
      graphRef.current.zoom(2, 1000);
      setHighlightNode(node.id);
      setTimeout(() => setHighlightNode(null), 2000);
    }
  }, []);

  /** Zoom in by 1.5x, clamped to 5x so labels stay legible. */
  const handleZoomIn = () => {
    if (graphRef.current) {
      const newZoom = Math.min(zoomLevel * 1.5, 5);
      graphRef.current.zoom(newZoom, 500);
      setZoomLevel(newZoom);
    }
  };

  /** Zoom out by 1.5x, clamped to 0.3x so the graph cannot collapse to nothing. */
  const handleZoomOut = () => {
    if (graphRef.current) {
      const newZoom = Math.max(zoomLevel / 1.5, 0.3);
      graphRef.current.zoom(newZoom, 500);
      setZoomLevel(newZoom);
    }
  };

  /** Fit all nodes in view with a 50 px margin; the internal scale is unknown, so reset to 1. */
  const handleFitView = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(500, 50);
      setZoomLevel(1);
    }
  };

  /** Return to the origin at 1x zoom. */
  const handleReset = () => {
    if (graphRef.current) {
      graphRef.current.centerAt(0, 0, 500);
      graphRef.current.zoom(1, 500);
      setZoomLevel(1);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg shadow-lg overflow-hidden border border-gray-800">
      {/* Graph title. */}
      <div className="flex items-center justify-between p-2 border-b border-gray-800 bg-gradient-to-r from-gray-800 to-gray-900">
        <h3 className="text-xs font-semibold text-gray-100">
          知识图谱 {entity ? `- ${entity}` : ''}
        </h3>
        <div className="flex items-center gap-1">
          {loading && <Loader2 className="w-3 h-3 animate-spin text-gray-400" />}
          <button onClick={handleZoomIn} className="p-1 hover:bg-gray-700 rounded" title="放大">
            <ZoomIn className="w-3 h-3 text-gray-400" />
          </button>
          <button onClick={handleZoomOut} className="p-1 hover:bg-gray-700 rounded" title="缩小">
            <ZoomOut className="w-3 h-3 text-gray-400" />
          </button>
          <button onClick={handleFitView} className="p-1 hover:bg-gray-700 rounded" title="适应视图">
            <Maximize2 className="w-3 h-3 text-gray-400" />
          </button>
          <button onClick={handleReset} className="p-1 hover:bg-gray-700 rounded" title="重置">
            <RotateCcw className="w-3 h-3 text-gray-400" />
          </button>
        </div>
      </div>

      {/* Graph canvas. The host div is flex-sized; the inner canvas follows `dimensions`. */}
      <div ref={containerRef} className="flex-1 relative" style={{ minHeight: '150px' }}>
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <Loader2 className="w-6 h-6 animate-spin mr-2" />
            <span className="text-xs">加载中...</span>
          </div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            width={dimensions.width}
            height={dimensions.height}
            nodeLabel={(node: any) => `${node.label}\n类型: ${node.type}`}
            nodeColor={getNodeColor as any}
            nodeVal={getNodeSize as any}
            /**
             * Custom label painting.
             * The canvas is redrawn every frame, so the label is drawn manually: font size is
             * divided by `globalScale` to keep text readable at any zoom, and a translucent
             * rectangle behind the text keeps it legible over edges and other nodes.
             */
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const label = node.label || node.id;
              const fontSize = Math.max(6, 10 / globalScale);
              ctx.font = `${fontSize}px Sans-Serif`;
              const textWidth = ctx.measureText(label).width;
              const padding = fontSize * 0.4;
              
              // Background plate centred on the node, sized from the measured text width.
              ctx.fillStyle = 'rgba(17, 24, 39, 0.9)';
              ctx.fillRect(
                node.x - textWidth / 2 - padding,
                node.y - fontSize / 2 - padding / 2,
                textWidth + padding * 2,
                fontSize + padding
              );
              
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = getNodeColor(node);
              ctx.fillText(label, node.x, node.y);
            }}
            linkLabel={(link: any) => link.label}
            linkColor={() => 'rgba(156, 163, 175, 0.4)'}
            linkWidth={1}
            onNodeClick={handleNodeClick}
            // Pinning a dragged node (`fx`/`fy`) stops the simulation from pulling it back,
            // so the user can lay the graph out by hand.
            onNodeDragEnd={(node: any) => {
              node.fx = node.x;
              node.fy = node.y;
            }}
            cooldownTicks={50}
            // Once the layout settles, frame the whole graph automatically.
            onEngineStop={() => {
              if (graphRef.current) {
                graphRef.current.zoomToFit(400, 30);
              }
            }}
          />
        )}
      </div>

      {/* Graph legend. Swatches must stay in sync with getNodeColor above. */}
      <div className="p-1 border-t border-gray-800 bg-gray-900">
        <div className="flex flex-wrap gap-2 text-xs justify-center">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#D72638' }}></span>
            <span className="text-gray-400">非遗项目</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#F59E0B' }}></span>
            <span className="text-gray-400">传承人</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#8B5CF6' }}></span>
            <span className="text-gray-400">节日</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#10B981' }}></span>
            <span className="text-gray-400">地点</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeGraph;
