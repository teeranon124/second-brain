import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Brain, MessageSquare, Plus, X, Share2, ArrowRight, Zap,
  Sparkles, Layers, Network, Send, Edit, Save, Trash2, Link as LinkIcon, MousePointerClick, Check, Eye, Search
} from 'lucide-react';
import api from './services/api';

// --- Gemini API Configuration (สำหรับ Local AI Extraction) ---
const apiKey = "AIzaSyCm7xrfPRAjCSQHJkKBuX3_sajLHxDOyIk";
const GEMINI_MODEL = "gemini-2.5-flash";

const App = () => {
  const [view, setView] = useState('graph');
  const [rightPanelMode, setRightPanelMode] = useState('none');
  const [rightPanelWidth, setRightPanelWidth] = useState(45); // % width
  const [isResizing, setIsResizing] = useState(false);

  const [selectedNodeData, setSelectedNodeData] = useState(null);
  const [isEditingMode, setIsEditingMode] = useState(false);
  const [editForm, setEditForm] = useState({ label: '', type: 'Concept', content: '' });
  const [newNodeForm, setNewNodeForm] = useState({ label: '', type: 'Concept', content: '', linkTarget: '', forwardLabel: '', backwardLabel: '' });

  // Removed isAddModalOpen - now using rightPanelMode === 'add'
  const [aiModalMode, setAiModalMode] = useState('manual'); // 'manual', 'text', 'document'
  const [aiInputText, setAiInputText] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [isAiThinking, setIsAiThinking] = useState(false);
  const [pendingAIData, setPendingAIData] = useState(null);
  const [suggestedConnections, setSuggestedConnections] = useState([]); // AI suggested similar nodes (while typing)
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [lastCreatedNode, setLastCreatedNode] = useState(null); // node just created manually
  const [postCreationSuggestions, setPostCreationSuggestions] = useState([]); // suggestions after save
  const [isConnectingSuggestion, setIsConnectingSuggestion] = useState(false);

  const [chatMessages, setChatMessages] = useState([
    { role: 'ai', text: 'ระบบ GraphRAG Engine ทำงาน! รองรับ Dense Retrieval, Bidirectional BFS และ Entity Matching' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [showMentionSuggestions, setShowMentionSuggestions] = useState(false);
  const [mentionSuggestions, setMentionSuggestions] = useState([]);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(0);

  // States สำหรับ Tracking การค้นหาเรียลไทม์
  const [activeChatFocus, setActiveChatFocus] = useState(null);
  const [bfsHighlightNodes, setBfsHighlightNodes] = useState([]);
  const [aiStatusMessage, setAiStatusMessage] = useState("");
  const [engineLogs, setEngineLogs] = useState([]);

  const [isEngineReady, setIsEngineReady] = useState(false);
  const [linkSetupModal, setLinkSetupModal] = useState(null);
  const [expandedNodeLinks, setExpandedNodeLinks] = useState(new Set()); // Track expanded nodes in notebook 
  const [graphDisplayMode, setGraphDisplayMode] = useState('nodes'); // 'nodes' | 'books'
  const [nodeRelatedBooks, setNodeRelatedBooks] = useState([]);

  // Search & Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [dateRangeFrom, setDateRangeFrom] = useState('');
  const [dateRangeTo, setDateRangeTo] = useState('');
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const [filterType, setFilterType] = useState('all'); // 'all' or specific type
  const [hideIsolated, setHideIsolated] = useState(false);

  // Quiz Mode States
  const [quizMode, setQuizMode] = useState(false);
  const [quizDashboardMode, setQuizDashboardMode] = useState('home'); // 'home', 'playing', 'history'
  const [currentQuiz, setCurrentQuiz] = useState(null);
  const [quizAnswer, setQuizAnswer] = useState('');
  const [quizResult, setQuizResult] = useState(null);
  const [isGeneratingQuiz, setIsGeneratingQuiz] = useState(false);
  const [quizHistory, setQuizHistory] = useState([]);
  const [quizStats, setQuizStats] = useState(null);
  const [selectedQuizCategory, setSelectedQuizCategory] = useState('all');
  const [quizCategories, setQuizCategories] = useState([]);
  const [quizBooks, setQuizBooks] = useState([]);
  const [selectedQuizBookId, setSelectedQuizBookId] = useState('');

  // Spaced Repetition States
  const [reviewQueue, setReviewQueue] = useState([]);
  const [showReviewPanel, setShowReviewPanel] = useState(false);
  const [books, setBooks] = useState([]);
  const [selectedBook, setSelectedBook] = useState(null);
  const [pendingBookDraft, setPendingBookDraft] = useState(null);
  const [isPersistingMemory, setIsPersistingMemory] = useState(false);
  const [bookClusters, setBookClusters] = useState({ nodes: [], edges: [] });
  const [isEditingBook, setIsEditingBook] = useState(false);
  const [bookEditForm, setBookEditForm] = useState({ title: '', full_text: '' });
  const [bfsPathLinks, setBfsPathLinks] = useState([]);
  const [activeCitationTerms, setActiveCitationTerms] = useState([]);

  const containerRef = useRef(null);
  const graphRef = useRef(null);
  const orbitInterval = useRef(null);
  const flyTimeout = useRef(null);

  // --- 1. โหลดข้อมูลจาก Backend ---
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [filteredGraphData, setFilteredGraphData] = useState({ nodes: [], links: [] });
  const [isLoadingGraph, setIsLoadingGraph] = useState(true);

  useEffect(() => {
    const loadGraph = async () => {
      try {
        setIsLoadingGraph(true);
        const data = await api.getFullGraph();

        // แปลง Backend format เป็น Frontend format
        const nodesWithVisuals = data.nodes.map(node => ({
          ...node,
          color: getNodeColor(node.type),
          baseVal: node.type === 'Hub' ? 20 : node.type === 'Animal' ? 18 : 12
        }));

        setGraphData({ nodes: nodesWithVisuals, links: data.links });
        setIsEngineReady(true);
      } catch (error) {
        console.error('Failed to load graph:', error);
        setChatMessages(prev => [...prev, {
          role: 'ai',
          text: `⚠️ ไม่สามารถเชื่อมต่อ Backend: ${error.message}`
        }]);
      } finally {
        setIsLoadingGraph(false);
      }
    };

    loadGraph();
  }, []);

  const loadBooks = useCallback(async () => {
    try {
      const items = await api.getBooks();
      setBooks(Array.isArray(items) ? items : []);

      const clusters = await api.getBookClusters();
      setBookClusters(clusters || { nodes: [], edges: [] });
    } catch (error) {
      console.error('Failed to load books:', error);
    }
  }, []);

  useEffect(() => {
    loadBooks();
  }, [loadBooks]);

  useEffect(() => {
    if (!selectedBook) return;
    setBookEditForm({
      title: selectedBook.title || '',
      full_text: selectedBook.full_text || '',
    });
    setIsEditingBook(false);
  }, [selectedBook]);

  const loadBooksForNode = useCallback(async (nodeId) => {
    if (!nodeId) return;
    try {
      const items = await api.getBooksByNode(nodeId);
      setNodeRelatedBooks(Array.isArray(items) ? items : []);
    } catch (error) {
      console.error('Failed to load books for node:', error);
      setNodeRelatedBooks([]);
    }
  }, []);

  const handleSaveBookEdit = useCallback(async () => {
    if (!selectedBook) return;
    try {
      setIsPersistingMemory(true);
      const response = await api.updateBook(selectedBook.id, {
        title: bookEditForm.title,
        full_text: bookEditForm.full_text,
        source_type: selectedBook.source_type || 'text',
        filename: selectedBook.filename || null,
      });

      if (response?.book) {
        setSelectedBook(response.book);
      }

      // refresh graph + books so node add/remove remains consistent everywhere
      const updatedGraph = await api.getFullGraph();
      const nodesWithVisuals = updatedGraph.nodes.map(node => ({
        ...node,
        color: getNodeColor(node.type),
        baseVal: node.type === 'Hub' ? 20 : node.type === 'Animal' ? 18 : 12
      }));
      setGraphData({ nodes: nodesWithVisuals, links: updatedGraph.links });

      await loadBooks();
      setIsEditingBook(false);
      alert('✅ แก้ไขหนังสือและซิงก์โหนดเรียบร้อย');
    } catch (error) {
      alert(`ไม่สามารถแก้ไขหนังสือได้: ${error.message}`);
    } finally {
      setIsPersistingMemory(false);
    }
  }, [selectedBook, bookEditForm, loadBooks]);

  const handleDeleteBook = useCallback(async () => {
    if (!selectedBook?.id) return;

    const ok = confirm(
      `ต้องการลบหนังสือ "${selectedBook.title || 'Untitled Book'}" หรือไม่?\n\nการลบนี้จะลบทั้งเล่ม รวมถึงโหนดและลิงก์ที่อยู่ในเล่มนี้`
    );
    if (!ok) return;

    try {
      setIsPersistingMemory(true);
      const result = await api.deleteBook(selectedBook.id);

      const updatedGraph = await api.getFullGraph();
      const nodesWithVisuals = updatedGraph.nodes.map(node => ({
        ...node,
        color: getNodeColor(node.type),
        baseVal: node.type === 'Hub' ? 20 : node.type === 'Animal' ? 18 : 12
      }));
      setGraphData({ nodes: nodesWithVisuals, links: updatedGraph.links });

      await loadBooks();
      setSelectedBook(null);
      setIsEditingBook(false);
      alert(`✅ ลบหนังสือเรียบร้อย (ลบโหนด ${result?.deleted_nodes ?? 0} รายการ)`);
    } catch (error) {
      alert(`ไม่สามารถลบหนังสือได้: ${error.message}`);
    } finally {
      setIsPersistingMemory(false);
    }
  }, [selectedBook, loadBooks]);

  const getNodeColor = (type) => {
    const colors = {
      'Hub': '#0ea5e9',
      'Entity': '#94a3b8',
      'Process': '#38bdf8',
      'Chemical': '#f8fafc',
      'Animal': '#ec4899',
      'Crisis': '#ffffff'
    };
    return colors[type] || '#64748b';
  };

  const renderHighlightedText = useCallback((text, refs = [], citationTerms = []) => {
    if (!text) return null;
    const labels = [...new Set([
      ...(refs || []).map(r => r?.label).filter(Boolean),
      ...(citationTerms || []).filter(Boolean),
    ])]
      .sort((a, b) => b.length - a.length)
      .slice(0, 80);

    if (labels.length === 0) return text;

    const escaped = labels.map(l => l.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const regex = new RegExp(`(${escaped.join('|')})`, 'gi');
    const parts = text.split(regex);

    return parts.map((part, idx) => {
      const isHit = labels.some(l => l.toLowerCase() === part.toLowerCase());
      if (!isHit) return <React.Fragment key={idx}>{part}</React.Fragment>;
      return (
        <mark
          key={idx}
          className="bg-yellow-300/40 text-yellow-100 px-1 rounded"
          title="Knowledge node"
        >
          {part}
        </mark>
      );
    });
  }, []);

  const stateRef = useRef({ selectedNodeData, activeChatFocus, graphData, bfsHighlightNodes, bfsPathLinks });
  useEffect(() => {
    stateRef.current = { selectedNodeData, activeChatFocus, graphData, bfsHighlightNodes, bfsPathLinks };
  }, [selectedNodeData, activeChatFocus, graphData, bfsHighlightNodes, bfsPathLinks]);

  // --- 2. API Engine (รองรับ Local & จัดการ Error) ---
  const callGemini = async (prompt, systemInstruction) => {
    // ใช้ตัวแปรโมเดลที่กำหนดไว้ด้านบน
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`;
    const payload = {
      contents: [{ parts: [{ text: prompt }] }],
    };
    if (systemInstruction) payload.systemInstruction = { parts: [{ text: systemInstruction }] };

    const runRequest = async (retries = 3, delay = 2000) => {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          const errBody = await response.text();
          throw new Error(`HTTP ${response.status}: ${errBody}`);
        }

        const data = await response.json();
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
        if (!text) throw new Error("Empty Response from AI");
        return text;
      } catch (error) {
        if (retries > 0 && !error.message.includes("404")) { // ถ้าเป็น 404 (Model not found) ไม่ต้อง Retry ให้เตะออกเลย
          await new Promise(r => setTimeout(r, delay));
          return runRequest(retries - 1, delay * 1.5);
        }
        throw error;
      }
    };
    return runRequest();
  };

  const safeJsonParse = (text) => {
    if (!text) return null;
    try {
      const match = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
      return match ? JSON.parse(match[0]) : JSON.parse(text);
    } catch (e) {
      console.error("Parse Error:", text);
      return null;
    }
  };

  const addLog = (msg) => setEngineLogs(prev => [...prev, msg].slice(-5));

  // ============================================================================
  // GraphRAG Query Engine - เชื่อมต่อกับ Backend
  // ============================================================================
  const handleQuery = async (directQuery = null) => {
    const userQuery = directQuery || chatInput;
    if (!userQuery.trim() || isAiThinking) return;

    setChatMessages(prev => [...prev, { role: 'user', text: userQuery }]);
    if (!directQuery) {
      setChatInput(''); // Clear input only if using the input field
    }
    setChatMessages(prev => [...prev, { role: 'ai', text: 'กำลังประมวลผล...', isThinking: true }]);
    setIsAiThinking(true);
    setBfsHighlightNodes([]);
    setBfsPathLinks([]);
    setEngineLogs([]);

    try {
      // ตรวจจับ Path Query Pattern: "@NodeA สัมพันธ์กับ @NodeB อย่างไร"
      const pathQueryRegex = /@([^@\s]+)[^@]*@([^@\s]+)/;
      const pathMatch = userQuery.match(pathQueryRegex);

      if (pathMatch && (userQuery.includes('สัมพันธ์') || userQuery.includes('เกี่ยวข้อง') || userQuery.includes('relation') || userQuery.includes('connect'))) {
        // Path Finding Query
        const sourceName = pathMatch[1].trim();
        const targetName = pathMatch[2].trim();

        // Find nodes by label
        const sourceNode = graphData.nodes.find(n => n.label.toLowerCase() === sourceName.toLowerCase());
        const targetNode = graphData.nodes.find(n => n.label.toLowerCase() === targetName.toLowerCase());

        if (!sourceNode || !targetNode) {
          setChatMessages(prev => {
            const next = [...prev];
            next[next.length - 1] = {
              role: 'ai',
              text: `❌ ไม่พบโหนด: ${!sourceNode ? sourceName : targetName}`,
              isThinking: false
            };
            return next;
          });
          setIsAiThinking(false); // Reset thinking state
          return;
        }

        setAiStatusMessage("กำลังค้นหาเส้นทางเชื่อมโยง...");
        addLog(`🔎 Finding path between ${sourceName} and ${targetName}...`);

        const pathResponse = await api.post(
          `/api/query/pathfind?source_id=${encodeURIComponent(sourceNode.id)}&target_id=${encodeURIComponent(targetNode.id)}&max_depth=5`,
          {}
        );

        if (pathResponse.found) {
          const pathText = `${pathResponse.explanation}\n\n📍 เส้นทาง (${pathResponse.distance} ${pathResponse.distance === 1 ? 'hop' : 'hops'}): ${pathResponse.path.map(n => n.label).join(' → ')}`;

          setChatMessages(prev => {
            const next = [...prev];
            next[next.length - 1] = {
              role: 'ai',
              text: pathText,
              sources: pathResponse.path.map(n => ({ id: n.id, label: n.label, content: n.content })),
              isThinking: false
            };
            return next;
          });
        } else {
          setChatMessages(prev => {
            const next = [...prev];
            next[next.length - 1] = {
              role: 'ai',
              text: `❌ ${pathResponse.explanation}`,
              isThinking: false
            };
            return next;
          });
        }

        setAiStatusMessage("");
        setIsAiThinking(false); // Reset thinking state
        return;
      }

      // Normal Query
      setAiStatusMessage("กำลังค้นหาข้อมูลในกราฟ...");
      addLog("🔎 Querying Backend GraphRAG Engine...");

      // ยิง Query ไปที่ Backend
      const response = await api.queryGraph(userQuery);

      // แสดง execution steps
      if (response.execution_steps) {
        for (const step of response.execution_steps) {
          addLog(`[Step ${step.step_number}] ${step.description}`);
          setAiStatusMessage(step.description);

          // บินไปยังโหนดที่เกี่ยวข้อง (แสดงสูงสุด 3 โหนด)
          if (step.nodes_involved && step.nodes_involved.length > 0) {
            const nodesToShow = step.nodes_involved.slice(0, 3);
            for (const nodeId of nodesToShow) {
              const node = graphData.nodes.find(n => String(n.id) === String(nodeId));
              if (node) {
                setActiveChatFocus(node);
                flyToNode(node);
                await new Promise(r => setTimeout(r, 1200));
              }
            }
          } else {
            // ถ้าไม่มีโหนด ให้รอเล็กน้อยเพื่อให้เห็น status
            await new Promise(r => setTimeout(r, 500));
          }
        }
      }

      // แสดง BFS Nodes บนกราฟ
      if (response.bfs_result?.visited_nodes) {
        setBfsHighlightNodes(response.bfs_result.visited_nodes);
        addLog(`⚡ Found ${response.bfs_result.visited_nodes.length} connected nodes`);
      }
      if (response.bfs_result?.paths) {
        const pathKeys = response.bfs_result.paths
          .filter(p => Array.isArray(p) && p.length >= 2)
          .map(p => makeLinkKey(p[0], p[1]));
        setBfsPathLinks(pathKeys);
      }

      // แสดงคำตอบ
      setChatMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = {
          role: 'ai',
          text: response.answer || "ไม่พบคำตอบในระบบ",
          sources: response.sources || [],
          isThinking: false
        };
        return next;
      });

      setActiveChatFocus(null);
      setAiStatusMessage("");
      flyToNode(null);

    } catch (error) {
      console.error("Query Error:", error);
      setActiveChatFocus(null);
      setAiStatusMessage("");

      setChatMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = {
          role: 'ai',
          text: `ระบบขัดข้อง: ${error.message}\n\n💡 ตรวจสอบว่า Backend รันอยู่ที่ http://localhost:8000`,
          isThinking: false
        };
        return next;
      });
      flyToNode(null);
    } finally {
      setIsAiThinking(false);
    }
  };

  // ============================================================================
  // @ Mention Autocomplete
  // ============================================================================
  const handleChatInputChange = (e) => {
    const value = e.target.value;
    setChatInput(value);

    // ตรวจจับ @ mention
    const cursorPosition = e.target.selectionStart;
    const textBeforeCursor = value.substring(0, cursorPosition);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');

    if (lastAtIndex !== -1) {
      const searchText = textBeforeCursor.substring(lastAtIndex + 1);

      // ถ้ามี space หลัง @ แสดงว่าจบการพิมพ์แล้ว
      if (searchText.includes(' ')) {
        setShowMentionSuggestions(false);
        return;
      }

      // กรองโหนดที่ตรงกับคำค้นหา
      const filtered = graphData.nodes.filter(node =>
        node.label.toLowerCase().includes(searchText.toLowerCase())
      ).slice(0, 20); // แสดงสูงสุด 20 รายการ

      if (filtered.length > 0) {
        setMentionSuggestions(filtered);
        setShowMentionSuggestions(true);
        setSelectedSuggestionIndex(0);
      } else {
        setShowMentionSuggestions(false);
      }
    } else {
      setShowMentionSuggestions(false);
    }
  };

  const selectMention = (node) => {
    const cursorPosition = document.querySelector('#chatInput')?.selectionStart || chatInput.length;
    const textBeforeCursor = chatInput.substring(0, cursorPosition);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');

    if (lastAtIndex !== -1) {
      const textAfterCursor = chatInput.substring(cursorPosition);
      const newValue = chatInput.substring(0, lastAtIndex) + `@${node.label} ` + textAfterCursor;
      setChatInput(newValue);
    }

    setShowMentionSuggestions(false);
    // Focus กลับไปที่ input
    setTimeout(() => document.querySelector('#chatInput')?.focus(), 10);
  };

  const handleMentionKeyDown = (e) => {
    if (!showMentionSuggestions) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedSuggestionIndex(prev =>
        prev < mentionSuggestions.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedSuggestionIndex(prev => prev > 0 ? prev - 1 : 0);
    } else if (e.key === 'Enter' && mentionSuggestions.length > 0) {
      e.preventDefault();
      selectMention(mentionSuggestions[selectedSuggestionIndex]);
    } else if (e.key === 'Escape') {
      setShowMentionSuggestions(false);
    }
  };


  // ============================================================================
  // อัลกอริทึม 3: GraphRAG Extraction (Knowledge Extractor)
  // ============================================================================
  const handleAIProcess = async () => {
    setPendingBookDraft(null);
    // Document mode validation
    if (aiModalMode === 'document' && !uploadedFile) {
      alert("กรุณาอัปโหลดไฟล์ก่อน");
      return;
    }

    // Text mode validation
    if (aiModalMode === 'text' && !aiInputText.trim()) {
      return;
    }

    if (isAiThinking) return;
    setIsAiThinking(true);

    try {
      let extractedData;

      // Document mode: Parse uploaded file
      if (aiModalMode === 'document') {
        const parseResult = await api.parseDocument(uploadedFile);
        extractedData = parseResult.entities; // entities มี {nodes: [...], links: [...]}
        setPendingBookDraft({
          title: parseResult.filename || `Document ${new Date().toLocaleString()}`,
          filename: parseResult.filename || null,
          source_type: 'document',
          full_text: parseResult.full_text || parseResult.extracted_text || ''
        });

        // แสดงข้อมูล preview ให้ผู้ใช้เห็น
        console.log(`📄 Parsed ${parseResult.filename} (${parseResult.text_length} characters)`);
        console.log(`Preview: ${parseResult.extracted_text}`);
      }
      // Text mode: Extract from text input
      else {
        extractedData = await api.extractEntities(aiInputText);
        setPendingBookDraft({
          title: `Text Note ${new Date().toLocaleString()}`,
          filename: null,
          source_type: 'text',
          full_text: aiInputText
        });
      }

      if (extractedData && extractedData.nodes && extractedData.nodes.length > 0) {
        // เตรียมข้อมูลสำหรับ Preview/Confirmation
        const previewNodes = extractedData.nodes.map((node, idx) => ({
          id: `preview_${Date.now()}_${idx}`,
          label: node.label,
          type: node.type || 'Concept',
          content: node.content || '',
          color: getNodeColor(node.type || 'Concept'),
          baseVal: 12
        }));

        const previewLinks = (extractedData.links || []).map((link, idx) => {
          const sourceLabel = link.source || link.source_label;
          const targetLabel = link.target || link.target_label;
          return {
            id: `preview_link_${Date.now()}_${idx}`,
            source_label: sourceLabel,
            target_label: targetLabel,
            label: link.label || 'เกี่ยวข้องกับ',
            labelReverse: link.label_reverse || link.labelReverse || 'เกี่ยวข้องกับ'
          };
        });

        setPendingAIData({ nodes: previewNodes, links: previewLinks });
        setRightPanelMode('none');
        setAiInputText('');
        setUploadedFile(null); // Clear uploaded file
      } else {
        alert("ไม่สามารถสกัดข้อมูลได้ กรุณาลองใหม่");
      }
    } catch (e) {
      alert(`การสกัดข้อมูลขัดข้อง: ${e.message}\n\n💡 ตรวจสอบว่า Backend รันอยู่ที่ http://localhost:8000`);
    } finally {
      setIsAiThinking(false);
    }
  };

  // --- 4. ฟังก์ชันจัดการโหนดและกล้อง ---
  const handleConfirmAIData = async () => {
    if (!pendingAIData) return;

    try {
      setIsPersistingMemory(true);
      // 🚀 Batch create with entity matching and deduplication (FAST!)
      const nodesPayload = pendingAIData.nodes.map(node => ({
        label: node.label,
        type: node.type || 'Concept',
        content: node.content || ''
      }));

      const linksPayload = (pendingAIData.links || []).map(link => ({
        source_label: link.source_label,
        target_label: link.target_label,
        label: link.label || 'เกี่ยวข้องกับ',
        labelReverse: link.labelReverse || 'เกี่ยวข้องกับ'
      }));

      const result = await api.batchCreate({
        nodes: nodesPayload,
        links: linksPayload,
        book: pendingBookDraft || undefined,
      });

      // รีโหลดกราฟ
      const updatedGraph = await api.getFullGraph();
      const nodesWithVisuals = updatedGraph.nodes.map(node => ({
        ...node,
        color: getNodeColor(node.type),
        baseVal: node.type === 'Hub' ? 20 : node.type === 'Animal' ? 18 : 12
      }));
      setGraphData({ nodes: nodesWithVisuals, links: updatedGraph.links });

      setPendingAIData(null);
      setPendingBookDraft(null);
      await loadBooks();

      // แสดงสถิติการบันทึก
      const stats = result.stats;
      const message = [
        `โหนดใหม่: ${stats.new_nodes}`,
        `โหนดเชื่อมเดิม: ${stats.merged_nodes}`,
        `ลิงก์ใหม่: ${stats.new_links}`,
        stats.skipped_links > 0 ? `ลิงก์ซ้ำ: ${stats.skipped_links}` : null
      ].filter(Boolean).join(' | ');

      alert(`✅ บันทึกสำเร็จ!\n\n${message}`);
    } catch (error) {
      alert(`ไม่สามารถบันทึกข้อมูลได้: ${error.message}`);
    } finally {
      setIsPersistingMemory(false);
    }
  };

  const handleAddNode = async () => {
    if (!newNodeForm.label.trim()) return;

    try {
      // Create node via backend
      const newNode = await api.createNode({
        label: newNodeForm.label,
        type: newNodeForm.type || 'Concept',
        content: newNodeForm.content || ''
      });

      const createdLinks = [];

      // Optional manual link
      if (newNodeForm.linkTarget && newNodeForm.forwardLabel && newNodeForm.backwardLabel) {
        const newLink = await api.createLink({
          source_id: newNode.id,
          target_id: newNodeForm.linkTarget,
          label: newNodeForm.forwardLabel,
          label_reverse: newNodeForm.backwardLabel
        });
        if (newLink) createdLinks.push(newLink);
      }

      // Append to graph locally — no full reload needed (faster UX)
      const newNodeWithVisuals = {
        ...newNode,
        color: getNodeColor(newNode.type),
        baseVal: newNode.type === 'Hub' ? 20 : newNode.type === 'Animal' ? 18 : 12
      };
      setGraphData(prev => ({
        nodes: [...prev.nodes, newNodeWithVisuals],
        links: [...prev.links, ...createdLinks]
      }));

      // Store for post-creation flow and reset form
      setLastCreatedNode(newNode);
      setSuggestedConnections([]);
      setNewNodeForm({ label: '', type: 'Concept', content: '', linkTarget: '', forwardLabel: '', backwardLabel: '' });

      // Fetch vector-similarity suggestions from the new endpoint
      try {
        const suggestions = await api.get(`/api/nodes/${newNode.id}/suggest-connections?top_k=5&threshold=0.5`);
        if (Array.isArray(suggestions) && suggestions.length > 0) {
          setPostCreationSuggestions(suggestions);
          // Panel stays open showing the suggestions section
        } else {
          setPostCreationSuggestions([]);
          setLastCreatedNode(null);
          setRightPanelMode('none');
        }
      } catch (_) {
        // Suggestions are optional — don't block the success flow
        setLastCreatedNode(null);
        setRightPanelMode('none');
      }
    } catch (error) {
      alert(`ไม่สามารถเพิ่มโหนดได้: ${error.message}`);
    }
  };

  const handleConnectSuggested = async (suggestion) => {
    if (!lastCreatedNode || isConnectingSuggestion) return;
    setIsConnectingSuggestion(true);
    try {
      const newLink = await api.createLink({
        source_id: lastCreatedNode.id,
        target_id: suggestion.id,
        label: suggestion.suggested_label || 'เกี่ยวข้องกับ',
        label_reverse: suggestion.suggested_label_reverse || 'เกี่ยวข้องกับ'
      });
      if (newLink) {
        setGraphData(prev => ({ nodes: prev.nodes, links: [...prev.links, newLink] }));
      }
      setPostCreationSuggestions(prev => prev.filter(s => s.id !== suggestion.id));
    } catch (err) {
      console.error('Failed to connect suggested node:', err);
    } finally {
      setIsConnectingSuggestion(false);
    }
  };

  const handleUpdateNode = async () => {
    if (!selectedNodeData || !editForm.label.trim()) return;

    try {
      await api.updateNode(selectedNodeData.id, {
        label: editForm.label,
        type: editForm.type || selectedNodeData.type,
        content: editForm.content || ''
      });

      // รีโหลดข้อมูลกราฟใหม่
      const updatedGraph = await api.getFullGraph();
      const nodesWithVisuals = updatedGraph.nodes.map(node => ({
        ...node,
        color: getNodeColor(node.type),
        baseVal: node.type === 'Hub' ? 20 : node.type === 'Animal' ? 18 : 12
      }));
      setGraphData({ nodes: nodesWithVisuals, links: updatedGraph.links });

      // อัปเดต selectedNodeData
      const updatedNode = nodesWithVisuals.find(n => String(n.id) === String(selectedNodeData.id));
      if (updatedNode) {
        setSelectedNodeData(updatedNode);
      }

      setIsEditingMode(false);
      alert('✅ อัปเดตโหนดสำเร็จ');
    } catch (error) {
      alert(`ไม่สามารถอัปเดตโหนดได้: ${error.message}`);
    }
  };

  const handleDeleteNode = async () => {
    if (!selectedNodeData) return;

    if (!confirm(`ต้องการลบโหนด "${selectedNodeData.label}" หรือไม่?`)) return;

    try {
      await api.deleteNode(selectedNodeData.id);

      // รีโหลดข้อมูลกราฟใหม่
      const updatedGraph = await api.getFullGraph();
      const nodesWithVisuals = updatedGraph.nodes.map(node => ({
        ...node,
        color: getNodeColor(node.type),
        baseVal: node.type === 'Hub' ? 20 : node.type === 'Animal' ? 18 : 12
      }));
      setGraphData({ nodes: nodesWithVisuals, links: updatedGraph.links });

      setRightPanelMode('none');
      setSelectedNodeData(null);
      alert('✅ ลบโหนดสำเร็จ');
    } catch (error) {
      alert(`ไม่สามารถลบโหนดได้: ${error.message}`);
    }
  };

  const flyToNode = useCallback((node) => {
    if (!graphRef.current) return;
    clearTimeout(flyTimeout.current);
    clearInterval(orbitInterval.current);
    if (node) {
      const distance = 150;
      const targetNode = graphRef.current.graphData().nodes.find(n => String(n.id) === String(node.id)) || node;
      if (targetNode.x === undefined) return;
      graphRef.current.cameraPosition({ x: targetNode.x, y: targetNode.y + 20, z: targetNode.z + distance }, targetNode, 1500);
      flyTimeout.current = setTimeout(() => {
        let angle = 0;
        orbitInterval.current = setInterval(() => {
          if (!graphRef.current) return;
          angle += 0.003;
          graphRef.current.cameraPosition({ x: targetNode.x + distance * Math.sin(angle), y: targetNode.y + 10 * Math.sin(angle * 2), z: targetNode.z + distance * Math.cos(angle) }, targetNode, 0);
        }, 16);
      }, 1500);
    } else {
      graphRef.current.cameraPosition({ x: 250, y: 250, z: 250 }, { x: 0, y: 0, z: 0 }, 1500);
    }
  }, []);

  const handleNodeClick = useCallback((node) => {
    if (graphDisplayMode === 'books' || node._bookRef) {
      const found = books.find(b => String(b.id) === String(node.id));
      if (!found) return;
      (async () => {
        try {
          const full = await api.getBook(found.id);
          setActiveCitationTerms([]);
          setSelectedBook(full);
          setView('notebook');
        } catch (e) {
          console.error('Failed to open book from graph:', e);
        }
      })();
      return;
    }

    setRightPanelMode('node');
    setSelectedNodeData(node);
    setEditForm({ label: node.label, content: node.content });
    setIsEditingMode(false);
    setActiveChatFocus(null);
    flyToNode(node);
    loadBooksForNode(node.id);
  }, [flyToNode, loadBooksForNode, graphDisplayMode, books]);

  const handleNodeClickRef = useRef(handleNodeClick);
  useEffect(() => { handleNodeClickRef.current = handleNodeClick; }, [handleNodeClick]);

  const toggleChatMode = () => {
    if (rightPanelMode === 'chat') {
      setRightPanelMode('none');
      setSelectedNodeData(null);
      setActiveChatFocus(null);
      setAiStatusMessage("");
      flyToNode(null);
      setBfsHighlightNodes([]);
    } else {
      setRightPanelMode('chat');
      setSelectedNodeData(null);
      flyToNode(null);
    }
  };

  const toggleAddMode = () => {
    if (rightPanelMode === 'add') {
      setRightPanelMode('none');
    } else {
      setAiModalMode('text');
      setRightPanelMode('add');
    }
  };

  const closeRightPanel = () => { setRightPanelMode('none'); setSelectedNodeData(null); setActiveChatFocus(null); setAiStatusMessage(""); setIsEditingMode(false); flyToNode(null); setBfsHighlightNodes([]); setLastCreatedNode(null); setPostCreationSuggestions([]); setPendingBookDraft(null); };

  // Search & Filter Functions
  const handleSearch = useCallback(async (query) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResults([]);
      setShowSearchDropdown(false);
      return;
    }

    try {
      // Use vector search API for semantic search
      const response = await api.get(`/api/nodes/search/?q=${encodeURIComponent(query)}&limit=10`);
      const results = Array.isArray(response) ? response : [];
      setSearchResults(results);
      setShowSearchDropdown(results.length > 0);
    } catch (error) {
      console.error('Search error:', error);
      // Fallback to local filter on error
      const results = graphData.nodes.filter(node =>
        node.label.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 10);
      setSearchResults(results);
      setShowSearchDropdown(results.length > 0);
    }
  }, [graphData.nodes]);

  const jumpToNode = useCallback((node) => {
    handleNodeClick(node);
    setSearchQuery('');
    setShowSearchDropdown(false);
    setView('graph'); // Switch to graph view
  }, [handleNodeClick]);

  // Apply filters to graphData
  useEffect(() => {
    let filtered = { nodes: [...graphData.nodes], links: [...graphData.links] };

    // Filter by type
    if (filterType !== 'all') {
      filtered.nodes = filtered.nodes.filter(n => n.type === filterType);
      const nodeIds = new Set(filtered.nodes.map(n => String(n.id)));
      filtered.links = filtered.links.filter(l =>
        nodeIds.has(String(typeof l.source === 'object' ? l.source.id : l.source)) &&
        nodeIds.has(String(typeof l.target === 'object' ? l.target.id : l.target))
      );
    }

    // Filter by date range
    if ((dateRangeFrom || dateRangeTo) && filtered.nodes.length > 0) {
      filtered.nodes = filtered.nodes.filter(n => {
        if (!n.created_at) return true; // Include nodes without dates
        const nodeDate = new Date(n.created_at).toISOString().split('T')[0]; // YYYY-MM-DD

        if (dateRangeFrom && nodeDate < dateRangeFrom) return false;
        if (dateRangeTo && nodeDate > dateRangeTo) return false;
        return true;
      });
      const nodeIds = new Set(filtered.nodes.map(n => String(n.id)));
      filtered.links = filtered.links.filter(l =>
        nodeIds.has(String(typeof l.source === 'object' ? l.source.id : l.source)) &&
        nodeIds.has(String(typeof l.target === 'object' ? l.target.id : l.target))
      );
    }

    // Hide isolated nodes
    if (hideIsolated) {
      const connectedNodes = new Set();
      filtered.links.forEach(link => {
        connectedNodes.add(String(typeof link.source === 'object' ? link.source.id : link.source));
        connectedNodes.add(String(typeof link.target === 'object' ? link.target.id : link.target));
      });
      filtered.nodes = filtered.nodes.filter(n => connectedNodes.has(String(n.id)));
    }

    setFilteredGraphData(filtered);
  }, [graphData, filterType, dateRangeFrom, dateRangeTo, hideIsolated]);

  const makeLinkKey = (a, b) => {
    const x = String(a);
    const y = String(b);
    return x < y ? `${x}::${y}` : `${y}::${x}`;
  };

  const activeGraphData = useMemo(() => {
    if (graphDisplayMode === 'nodes') return filteredGraphData;

    const bookNodes = (bookClusters.nodes || []).map((b, idx) => ({
      id: b.id,
      label: b.title,
      type: 'Book',
      content: `${b.node_count} nodes`,
      color: '#22d3ee',
      baseVal: Math.max(14, Math.min(30, 12 + (b.node_count || 0))),
      _bookRef: true,
      _bookIndex: idx,
    }));

    const bookLinks = (bookClusters.edges || []).map((e, idx) => ({
      id: `book_edge_${idx}`,
      source: e.source,
      target: e.target,
      label: `overlap_${e.shared_count}`,
      labelReverse: `overlap_${e.shared_count}`,
      curvature: 0,
      metadata: { shared_count: e.shared_count }
    }));

    return { nodes: bookNodes, links: bookLinks };
  }, [graphDisplayMode, filteredGraphData, bookClusters]);

  // AI Suggested Connections - Debounced search for similar nodes
  useEffect(() => {
    if (aiModalMode !== 'manual' || !newNodeForm.label.trim() || newNodeForm.label.length < 3) {
      setSuggestedConnections([]);
      return;
    }

    const timeoutId = setTimeout(async () => {
      setIsLoadingSuggestions(true);
      try {
        const searchText = `${newNodeForm.label} ${newNodeForm.content}`.trim();
        // api.get() returns the JSON array directly (no .data wrapper)
        const response = await api.get(`/api/nodes/search/?q=${encodeURIComponent(searchText)}&limit=5`);
        const suggestions = (Array.isArray(response) ? response : []).filter(node =>
          node.label.toLowerCase() !== newNodeForm.label.toLowerCase()
        );
        setSuggestedConnections(suggestions);
      } catch (error) {
        console.error('Failed to fetch suggestions:', error);
        setSuggestedConnections([]);
      } finally {
        setIsLoadingSuggestions(false);
      }
    }, 800); // Debounce 800ms

    return () => clearTimeout(timeoutId);
  }, [newNodeForm.label, newNodeForm.content, aiModalMode]);


  // Quiz Data Loading
  const loadQuizData = useCallback(async () => {
    try {
      console.log('Loading quiz data...');
      // Load quiz history
      const historyResponse = await api.get('/api/quiz/history?limit=20');
      console.log('Quiz history response:', historyResponse);
      setQuizHistory(historyResponse.recent_attempts || []);
      setQuizStats(historyResponse);
      
      // Load categories
      const categoriesResponse = await api.get('/api/quiz/categories');
      console.log('Quiz categories response:', categoriesResponse);
      setQuizCategories(categoriesResponse.categories || []);

      // Load books for book-based quiz mode
      const quizBooksResponse = await api.getQuizBooks();
      setQuizBooks(quizBooksResponse.books || []);
    } catch (error) {
      console.error('Failed to load quiz data:', error);
    }
  }, []);

  // Quiz Mode Functions
  const generateQuiz = useCallback(async () => {
    if (filteredGraphData.nodes.length === 0) return;

    setIsGeneratingQuiz(true);
    try {
      // Book-first quiz mode
      if (selectedQuizBookId) {
        const bookQuiz = await api.getQuizQuestionByBook(selectedQuizBookId, 'medium');
        setCurrentQuiz({
          question: bookQuiz.question,
          answer: bookQuiz.answer,
          hint: bookQuiz.hint,
          nodeId: '',
          nodeLabel: bookQuiz.book_title,
          bookId: bookQuiz.book_id,
          evidenceTerms: bookQuiz.evidence_terms || [],
        });
        setQuizAnswer('');
        setQuizResult(null);
        return;
      }

      // Select random node
      const randomNode = filteredGraphData.nodes[Math.floor(Math.random() * filteredGraphData.nodes.length)];

      // Generate quiz using Gemini
      const prompt = `สร้างคำถามทดสอบความรู้จากข้อมูลนี้:

โหนด: ${randomNode.label}
เนื้อหา: ${randomNode.content}

สร้างคำถามแบบเติมคำ (fill-in-the-blank) หรือแบบตอบสั้น ที่ทดสอบความเข้าใจในเนื้อหาหลัก

ตอบกลับในรูปแบบ JSON:
{
  "question": "คำถาม",
  "answer": "คำตอบที่ถูกต้อง",
  "hint": "คำใบ้ (ถ้ามี)"
}`;

      const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }]
        })
      });

      const data = await response.json();
      const quizData = JSON.parse(data.candidates[0].content.parts[0].text.replace(/```json\n?|```/g, ''));

      setCurrentQuiz({
        ...quizData,
        nodeId: randomNode.id,
        nodeLabel: randomNode.label,
        bookId: null,
        evidenceTerms: []
      });
      setQuizAnswer('');
      setQuizResult(null);
    } catch (error) {
      console.error('Quiz generation error:', error);
    } finally {
      setIsGeneratingQuiz(false);
    }
  }, [filteredGraphData.nodes]);

  const checkQuizAnswer = useCallback(async () => {
    if (!currentQuiz || !quizAnswer.trim()) return;

    try {
      // Use Gemini to check answer
      const prompt = `คำถาม: ${currentQuiz.question}
คำตอบที่ถูกต้อง: ${currentQuiz.answer}
คำตอบของผู้ใช้: ${quizAnswer}

ตรวจสอบว่าคำตอบถูกหรือผิด และให้คำอธิบาย

ตอบกลับในรูปแบบ JSON:
{
  "correct": true/false,
  "feedback": "คำอธิบาย"
}`;

      const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }]
        })
      });

      const data = await response.json();
      const result = JSON.parse(data.candidates[0].content.parts[0].text.replace(/```json\n?|```/g, ''));

      setQuizResult(result);
      
      // Save quiz attempt to backend
      try {
        const nodeData = filteredGraphData.nodes.find(n => n.id === currentQuiz.nodeId);
        const attemptData = {
          node_id: currentQuiz.nodeId,
          node_label: currentQuiz.nodeLabel,
          node_type: nodeData?.type || 'Concept',
          book_id: currentQuiz.bookId || null,
          book_title: currentQuiz.bookId ? currentQuiz.nodeLabel : null,
          question: currentQuiz.question,
          user_answer: quizAnswer,
          correct_answer: currentQuiz.answer,
          is_correct: result.correct,
          hint: currentQuiz.hint || null,
          relationships_tested: [],
        };
        
        console.log('Saving quiz attempt:', attemptData);
        const saveResponse = await api.post('/api/quiz/attempt', attemptData);
        console.log('Quiz saved successfully:', saveResponse);
        
        // Reload quiz data to update history
        await loadQuizData();
        console.log('Quiz history reloaded');
      } catch (error) {
        console.error('Failed to save quiz attempt:', error);
        alert('ไม่สามารถบันทึกคะแนนได้: ' + error.message);
      }

      // Add to review queue if incorrect
      if (!result.correct) {
        const nodeToReview = filteredGraphData.nodes.find(n => n.id === currentQuiz.nodeId);
        if (nodeToReview && !reviewQueue.find(n => n.id === nodeToReview.id)) {
          setReviewQueue([...reviewQueue, { ...nodeToReview, reviewDate: Date.now() + 24 * 60 * 60 * 1000 }]);
        }
      }
    } catch (error) {
      console.error('Answer check error:', error);
    }
  }, [currentQuiz, quizAnswer, filteredGraphData.nodes, reviewQueue, loadQuizData]);

  // Resize handlers for right panel
  const handleResizeStart = useCallback((e) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const handleResizeMove = useCallback((e) => {
    if (!isResizing) return;
    const containerWidth = window.innerWidth;
    const mouseX = e.clientX;
    const newWidth = ((containerWidth - mouseX) / containerWidth) * 100;
    // Clamp between 25% and 75%
    if (newWidth >= 25 && newWidth <= 75) {
      setRightPanelWidth(newWidth);
    }
  }, [isResizing]);

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false);
  }, []);

  useEffect(() => {
    if (isResizing) {
      window.addEventListener('mousemove', handleResizeMove);
      window.addEventListener('mouseup', handleResizeEnd);
      return () => {
        window.removeEventListener('mousemove', handleResizeMove);
        window.removeEventListener('mouseup', handleResizeEnd);
      };
    }
  }, [isResizing, handleResizeMove, handleResizeEnd]);

  const handleCreateManualLink = (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const targetId = String(fd.get('targetId'));
    if (!targetId || targetId === 'null') return;
    setGraphData(prev => ({
      ...prev,
      links: [...prev.links, { id: `l_${Date.now()}`, source: String(linkSetupModal.source.id), target: targetId, label: fd.get('forward'), labelReverse: fd.get('backward'), curvature: 0 }]
    }));
    setLinkSetupModal(null);
  };

  // --- 5. Initialize Graph Engine ---
  useEffect(() => {
    if (!containerRef.current || graphRef.current) return;
    const script = document.createElement('script');
    script.src = "https://unpkg.com/3d-force-graph";
    script.async = true;
    script.onload = () => {
      if (!window.ForceGraph3D) return;
      const Graph = window.ForceGraph3D()(containerRef.current)
        .graphData(activeGraphData)
        .backgroundColor('#00000000')
        .nodeLabel(node => `<div style="background:rgba(0,0,0,0.95);padding:12px;border-radius:12px;border:1px solid rgba(6,182,212,0.3);text-align:left;"><div style="font-size:10px;font-weight:900;color:#06b6d4;text-transform:uppercase;margin-bottom:2px;">${node.type || 'Concept'}</div><div style="font-size:15px;font-weight:bold;color:white;">${node.label}</div></div>`)
        .nodeColor(node => {
          const focusId = (stateRef.current.selectedNodeData || stateRef.current.activeChatFocus)?.id;
          const isHighlight = stateRef.current.bfsHighlightNodes.includes(String(node.id));
          if (node.id === focusId) return '#ffffff';
          if (isHighlight) return '#f472b6'; // สีชมพูสำหรับโหนดใน BFS Scope
          return node.color || '#a855f7';
        })
        .nodeRelSize(5)
        .nodeVal(node => {
          const focusId = (stateRef.current.selectedNodeData || stateRef.current.activeChatFocus)?.id;
          const isHighlight = stateRef.current.bfsHighlightNodes.includes(String(node.id));
          return node.id === focusId ? 22 : (isHighlight ? 16 : (node.baseVal || 10));
        })
        .linkCurvature(l => {
          const hasReverse = activeGraphData.links.some(link => link.source === l.target && link.target === l.source);
          return hasReverse ? 0.2 : 0;
        })
        .linkWidth(l => {
          const focusId = (stateRef.current.selectedNodeData || stateRef.current.activeChatFocus)?.id;
          const sId = String(typeof l.source === 'object' ? l.source.id : l.source);
          const tId = String(typeof l.target === 'object' ? l.target.id : l.target);
          const isExplored = stateRef.current.bfsHighlightNodes.includes(sId) && stateRef.current.bfsHighlightNodes.includes(tId);
          const isUsedPath = (stateRef.current.bfsPathLinks || []).includes(makeLinkKey(sId, tId));
          return (focusId && (sId === focusId || tId === focusId)) ? 4.5 : (isUsedPath ? 3.5 : (isExplored ? 2.5 : 1.5));
        })
        .linkColor(l => {
          const focusId = (stateRef.current.selectedNodeData || stateRef.current.activeChatFocus)?.id;
          const sId = String(typeof l.source === 'object' ? l.source.id : l.source);
          const tId = String(typeof l.target === 'object' ? l.target.id : l.target);
          const isExplored = stateRef.current.bfsHighlightNodes.includes(sId) && stateRef.current.bfsHighlightNodes.includes(tId);
          const isUsedPath = (stateRef.current.bfsPathLinks || []).includes(makeLinkKey(sId, tId));
          if (focusId && (sId === focusId || tId === focusId)) return '#06b6d4';
          if (isUsedPath) return '#f472b6'; // actual used path
          if (isExplored) return '#22d3ee'; // explored but not final path
          return 'rgba(255,255,255,0.2)';
        })
        .linkDirectionalArrowLength(3.5).linkDirectionalArrowRelPos(1)
        .linkDirectionalParticleWidth(3).linkDirectionalParticleSpeed(0.01)
        .linkDirectionalParticles(l => {
          const focusId = (stateRef.current.selectedNodeData || stateRef.current.activeChatFocus)?.id;
          const sId = String(typeof l.source === 'object' ? l.source.id : l.source);
          const tId = String(typeof l.target === 'object' ? l.target.id : l.target);
          const isHighlight = stateRef.current.bfsHighlightNodes.includes(sId) && stateRef.current.bfsHighlightNodes.includes(tId);
          const isUsedPath = (stateRef.current.bfsPathLinks || []).includes(makeLinkKey(sId, tId));
          if (focusId && (sId === focusId || tId === focusId)) return 5;
          if (isUsedPath) return 4;
          if (isHighlight) return 3;
          return 0;
        })
        .enableNodeDrag(false)
        .onNodeClick(node => handleNodeClickRef.current && handleNodeClickRef.current(node));

      Graph.d3Force('charge').strength(-150);
      graphRef.current = Graph;
      setIsEngineReady(true);

      const handleResize = () => {
        // แก้ไขบั๊ก TypeError null clientWidth
        if (graphRef.current && containerRef.current) {
          graphRef.current.width(containerRef.current.clientWidth).height(containerRef.current.clientHeight);
        }
      };

      window.addEventListener('resize', handleResize);

      const resizeObserver = new ResizeObserver(handleResize);
      if (containerRef.current) {
        resizeObserver.observe(containerRef.current);
      }

      // Cleanup
      return () => {
        window.removeEventListener('resize', handleResize);
        resizeObserver.disconnect();
      };
    };
    document.head.appendChild(script);
  }, []);

  useEffect(() => {
    if (graphRef.current && isEngineReady) {
      try {
        graphRef.current.graphData(activeGraphData);
        graphRef.current.nodeColor(graphRef.current.nodeColor());
        graphRef.current.nodeVal(graphRef.current.nodeVal());
        graphRef.current.linkWidth(graphRef.current.linkWidth());
        graphRef.current.linkColor(graphRef.current.linkColor());
        graphRef.current.linkDirectionalParticles(graphRef.current.linkDirectionalParticles());
      } catch (e) { }
    }
  }, [activeGraphData, selectedNodeData, activeChatFocus, bfsHighlightNodes, bfsPathLinks, isEngineReady]);

  return (
    <div className="flex flex-col h-screen w-screen bg-[#030305] text-slate-300 font-sans select-none text-left">
      <header className="w-full flex flex-col z-50 bg-gradient-to-b from-black/90 via-black/60 to-transparent backdrop-blur-md border-b border-white/5 shrink-0">
        {/* Row 1: Main Navigation */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-white/5">
          <div className="flex items-center gap-5 pointer-events-auto">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-cyan-400 to-blue-600 rounded-lg shadow-lg">
                <Brain size={18} className="text-white" />
              </div>
              <div className="text-left">
                <h1 className="text-[9px] font-black uppercase tracking-[0.25em] text-slate-500 leading-none">GraphRAG</h1>
                <p className="text-xs font-bold text-white tracking-tight">Knowledge Graph</p>
              </div>
            </div>
            <div className="flex gap-2 ml-6">
              <button onClick={() => setView('graph')} className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${view === 'graph' ? 'bg-cyan-500 text-black' : 'bg-white/5 text-slate-400 hover:bg-white/10'}`}>Graph</button>
              <button onClick={() => setView('notebook')} className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${view === 'notebook' ? 'bg-cyan-500 text-black' : 'bg-white/5 text-slate-400 hover:bg-white/10'}`}>Notebook</button>
              {view === 'graph' && (
                <>
                  <button onClick={() => setGraphDisplayMode('nodes')} className={`px-3 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${graphDisplayMode === 'nodes' ? 'bg-pink-500 text-white' : 'bg-white/5 text-slate-400 hover:bg-white/10'}`}>Node View</button>
                  <button onClick={() => setGraphDisplayMode('books')} className={`px-3 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${graphDisplayMode === 'books' ? 'bg-pink-500 text-white' : 'bg-white/5 text-slate-400 hover:bg-white/10'}`}>Book View</button>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 pointer-events-auto">
            <button
              onClick={toggleAddMode}
              className={`px-4 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-all ${rightPanelMode === 'add'
                ? 'bg-gradient-to-r from-cyan-500 to-purple-500 text-white shadow-lg shadow-cyan-500/30'
                : 'bg-white/5 border border-cyan-500/30 text-cyan-400 hover:bg-white/10 hover:border-cyan-500/50'
                }`}
            >
              <Plus size={16} /> Add Knowledge
            </button>
            <button
              onClick={toggleChatMode}
              className={`px-4 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-all ${rightPanelMode === 'chat'
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg shadow-purple-500/30'
                : 'bg-white/5 border border-purple-500/30 text-purple-400 hover:bg-white/10 hover:border-purple-500/50'
                }`}
            >
              <MessageSquare size={16} /> Query AI
            </button>
            <button
              onClick={() => {
                setQuizMode(!quizMode);
                if (!quizMode) {
                  setQuizDashboardMode('home');
                  setRightPanelMode('quiz');
                  loadQuizData();
                } else {
                  setRightPanelMode('none');
                  setQuizDashboardMode('home');
                }
              }}
              className={`px-4 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-all ${quizMode
                ? 'bg-gradient-to-r from-green-500 to-teal-500 text-white shadow-lg shadow-green-500/30'
                : 'bg-white/5 border border-green-500/30 text-green-400 hover:bg-white/10 hover:border-green-500/50'
                }`}
            >
              <Sparkles size={16} /> Quiz Mode
            </button>
            {reviewQueue.length > 0 && (
              <button
                onClick={() => setShowReviewPanel(!showReviewPanel)}
                className="px-3 py-2.5 rounded-xl text-xs font-bold bg-yellow-500/20 border border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/30 transition-all flex items-center gap-2"
                title="Spaced Repetition Review"
              >
                📚 Review ({reviewQueue.length})
              </button>
            )}
          </div>
        </div>

        {/* Row 2: Search & Filters */}
        <div className="flex items-center gap-3 px-6 py-2.5">
          {/* Search Box */}
          <div className="relative pointer-events-auto flex-1 max-w-md">
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Search nodes..."
                className="w-full bg-white/5 border border-white/10 rounded-lg py-2 px-3 pl-9 text-xs text-white placeholder:text-slate-500 focus:border-cyan-500/50 focus:bg-white/10 outline-none transition-all"
              />
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            </div>
            {showSearchDropdown && searchResults.length > 0 && (
              <div className="absolute top-full left-0 mt-2 w-full bg-black/95 backdrop-blur-xl border border-cyan-500/30 rounded-xl shadow-2xl overflow-hidden z-50 max-h-80 overflow-y-auto">
                {searchResults.map(node => (
                  <div
                    key={node.id}
                    onClick={() => jumpToNode(node)}
                    className="px-4 py-2.5 hover:bg-cyan-500/20 cursor-pointer transition-all border-b border-white/5 last:border-0 flex items-center gap-3"
                  >
                    <span className="px-2 py-0.5 bg-cyan-500/10 rounded text-[10px] font-bold text-cyan-400">{node.type}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-white font-bold text-xs truncate">{node.label}</div>
                        {node.created_at && (
                          <span className="text-[9px] text-slate-600 whitespace-nowrap">
                            {new Date(node.created_at).toLocaleDateString('th-TH', { month: 'short', day: 'numeric' })}
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-400 truncate">{node.content}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Date Range Filters */}
          <div className="flex items-center gap-2 pointer-events-auto">
            <input
              type="date"
              value={dateRangeFrom}
              onChange={(e) => setDateRangeFrom(e.target.value)}
              className="px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-white outline-none focus:border-cyan-500/50 cursor-pointer hover:bg-white/10 transition-all"
              placeholder="From"
            />
            <span className="text-slate-500 text-xs">to</span>
            <input
              type="date"
              value={dateRangeTo}
              onChange={(e) => setDateRangeTo(e.target.value)}
              className="px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-white outline-none focus:border-cyan-500/50 cursor-pointer hover:bg-white/10 transition-all"
              placeholder="To"
            />
          </div>

          {/* Type Filter */}
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-white outline-none focus:border-cyan-500/50 cursor-pointer hover:bg-white/10 transition-all pointer-events-auto"
          >
            <option value="all">All Types</option>
            <option value="Concept">Concept</option>
            <option value="Company">Company</option>
            <option value="Person">Person</option>
            <option value="Organization">Organization</option>
            <option value="Product">Product</option>
            <option value="Technology">Technology</option>
            <option value="Event">Event</option>
            <option value="Location">Location</option>
          </select>

          {/* Isolated Toggle */}
          <button
            onClick={() => setHideIsolated(!hideIsolated)}
            className={`px-3 py-2 rounded-lg text-xs font-bold transition-all pointer-events-auto whitespace-nowrap ${hideIsolated
              ? 'bg-cyan-500 text-black'
              : 'bg-white/5 text-slate-400 hover:bg-white/10'
              }`}
            title="Toggle isolated nodes"
          >
            {hideIsolated ? '🔗 Connected' : '🔗 All'}
          </button>

          {/* Clear Filters */}
          {(searchQuery || dateRangeFrom || dateRangeTo || filterType !== 'all' || hideIsolated) && (
            <button
              onClick={() => {
                setSearchQuery('');
                setDateRangeFrom('');
                setDateRangeTo('');
                setFilterType('all');
                setHideIsolated(false);
                setShowSearchDropdown(false);
              }}
              className="px-3 py-2 rounded-lg text-xs font-bold bg-white/5 text-red-400 hover:bg-red-500/20 transition-all pointer-events-auto whitespace-nowrap"
            >
              ✕ Clear
            </button>
          )}
        </div>
      </header>

      <main className="flex w-full flex-1 relative z-10 overflow-hidden">
        {/* Graph View - Always rendered as background */}
        <div
          className="h-full relative flex-shrink-0 absolute inset-0"
          style={{
            width: rightPanelMode !== 'none' ? `${100 - rightPanelWidth}%` : '100%',
            transition: isResizing ? 'none' : 'width 500ms ease-in-out',
            zIndex: view === 'graph' ? 20 : 1,
            pointerEvents: view === 'graph' ? 'auto' : 'none'
          }}
        >
          <div ref={containerRef} className="absolute inset-0 w-full h-full" />

          {/* AI Terminal Logs */}
          {(activeChatFocus || aiStatusMessage) && (
            <div className="absolute top-32 left-10 w-80 bg-black/80 backdrop-blur-md border border-cyan-500/30 rounded-2xl p-5 animate-in fade-in shadow-2xl pointer-events-none z-50 flex flex-col gap-4">
              <div className="flex items-center gap-4">
                <div className="relative">
                  <div className="w-3 h-3 bg-cyan-400 rounded-full animate-ping absolute opacity-70"></div>
                  <div className="w-3 h-3 bg-cyan-400 rounded-full relative"></div>
                </div>
                <div className="text-left">
                  <div className="text-[9px] text-cyan-400 font-bold uppercase tracking-widest mb-0.5">Backend Simulator</div>
                  <div className="text-sm text-white font-bold truncate">{aiStatusMessage || "Running..."}</div>
                </div>
              </div>

              {engineLogs.length > 0 && (
                <div className="pt-3 border-t border-white/10 flex flex-col gap-2">
                  {engineLogs.map((log, i) => (
                    <div key={i} className="text-[10px] font-mono text-slate-400 leading-tight">
                      {'>'} {log}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Notebook View - Enhanced Reading Experience with Graph Background */}
        <div
          className="h-full overflow-y-auto px-20 py-16 scrollbar-hide absolute inset-0"
          style={{
            width: rightPanelMode !== 'none' ? `${100 - rightPanelWidth}%` : '100%',
            transition: isResizing ? 'none' : 'width 500ms ease-in-out',
            background: 'linear-gradient(to bottom, rgba(3,3,5,0.85) 0%, rgba(3,3,5,0.92) 50%, rgba(3,3,5,0.85) 100%)',
            backdropFilter: 'blur(8px)',
            zIndex: view === 'notebook' ? 20 : 1,
            pointerEvents: view === 'notebook' ? 'auto' : 'none',
            opacity: view === 'notebook' ? 1 : 0
          }}
        >
          <div className="max-w-6xl mx-auto">
            <h1 className="text-6xl font-black text-white tracking-tighter mb-3">📚 Knowledge Notebook</h1>
            <p className="text-slate-400 text-lg mb-12">
              อ่านความรู้แบบเนื้อหาต่อเนื่อง - {filteredGraphData.nodes.length} of {graphData.nodes.length} nodes
              {(filterType !== 'all' || dateRangeFrom || dateRangeTo || hideIsolated) && (
                <span className="ml-3 text-cyan-400 text-sm">
                  ({[
                    filterType !== 'all' ? `Type: ${filterType}` : '',
                    dateRangeFrom || dateRangeTo ? `Date: ${dateRangeFrom || '...'} to ${dateRangeTo || '...'}` : '',
                    hideIsolated ? 'Connected only' : ''
                  ].filter(Boolean).join(', ')})
                </span>
              )}
            </p>

            {/* Book Shelf */}
            <div className="mb-10 bg-white/5 border border-white/10 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-black uppercase tracking-wider text-cyan-400">Book Shelf</h3>
                {isPersistingMemory && (
                  <div className="text-xs text-yellow-300 animate-pulse">กำลังประมวลผลและบันทึกความจำ...</div>
                )}
              </div>
              {bookClusters.edges.length > 0 && (
                <div className="mb-4 p-3 rounded-xl bg-purple-500/10 border border-purple-500/20">
                  <div className="text-[11px] text-purple-300 font-bold mb-2 uppercase tracking-wider">Book Intersections</div>
                  <div className="flex flex-wrap gap-2">
                    {bookClusters.edges.slice(0, 8).map((e, idx) => {
                      const s = bookClusters.nodes.find(n => n.id === e.source)?.title || 'Book A';
                      const t = bookClusters.nodes.find(n => n.id === e.target)?.title || 'Book B';
                      return (
                        <span key={idx} className="px-2 py-1 rounded-md text-xs bg-purple-400/10 border border-purple-400/20 text-purple-200">
                          {s} ∩ {t} ({e.shared_count})
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}
              {books.length === 0 ? (
                <div className="text-sm text-slate-500">ยังไม่มีหนังสือ ลองอัปโหลดเอกสารหรือข้อความ แล้วกดยืนยันบันทึก</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {books.map((book) => (
                    <button
                      key={book.id}
                      onClick={async () => {
                        try {
                          const full = await api.getBook(book.id);
                          setActiveCitationTerms([]);
                          setSelectedBook(full);
                        } catch (e) {
                          console.error('Failed to load book detail:', e);
                        }
                      }}
                      className={`text-left p-4 rounded-xl border transition-all ${selectedBook?.id === book.id ? 'border-cyan-500 bg-cyan-500/10' : 'border-white/10 bg-white/5 hover:bg-white/10'}`}
                    >
                      <div className="text-white font-bold truncate">📘 {book.title || 'Untitled Book'}</div>
                      <div className="text-xs text-slate-400 mt-1">{book.source_type || 'text'} • {(book.node_ids || []).length} nodes</div>
                      <div className="text-xs text-slate-500 mt-2 line-clamp-2">{book.preview || ''}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {selectedBook && (
              <div className="mb-12 bg-gradient-to-b from-white/5 to-transparent border border-cyan-500/20 rounded-3xl p-8">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-3xl font-black text-white">{selectedBook.title || 'Untitled Book'}</h2>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setIsEditingBook(v => !v)}
                      className="px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 text-xs"
                    >
                      {isEditingBook ? 'ยกเลิกแก้ไข' : 'แก้ไขหนังสือ'}
                    </button>
                    <button
                      onClick={handleDeleteBook}
                      className="px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 text-xs"
                    >
                      ลบทั้งเล่ม
                    </button>
                    <button
                      onClick={() => setSelectedBook(null)}
                      className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs"
                    >
                      ปิดเล่มนี้
                    </button>
                  </div>
                </div>

                <div className="text-xs text-slate-400 mb-5">
                  {(selectedBook.node_refs || []).length} highlighted nodes • {(selectedBook.intersections || []).length} intersections
                </div>

                {(selectedBook.intersections || []).length > 0 && (
                  <div className="mb-6 flex flex-wrap gap-2">
                    {selectedBook.intersections.slice(0, 8).map((x, idx) => (
                      <span key={idx} className="px-2 py-1 rounded-md text-xs bg-purple-500/15 text-purple-300 border border-purple-500/20">
                        ∩ {x.title} ({x.shared_count})
                      </span>
                    ))}
                  </div>
                )}

                {isEditingBook ? (
                  <div className="space-y-3">
                    <input
                      value={bookEditForm.title}
                      onChange={(e) => setBookEditForm(prev => ({ ...prev, title: e.target.value }))}
                      className="w-full bg-black/30 border border-white/10 rounded-xl p-3 text-white"
                      placeholder="ชื่อหนังสือ"
                    />
                    <textarea
                      value={bookEditForm.full_text}
                      onChange={(e) => setBookEditForm(prev => ({ ...prev, full_text: e.target.value }))}
                      className="w-full min-h-[320px] bg-black/30 border border-white/10 rounded-xl p-4 text-slate-200"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleSaveBookEdit}
                        disabled={isPersistingMemory}
                        className="px-4 py-2 rounded-lg bg-green-500/30 hover:bg-green-500/40 text-green-200 text-sm disabled:opacity-50"
                      >
                        {isPersistingMemory ? 'กำลังซิงก์...' : 'บันทึกและซิงก์โหนด'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <article className="whitespace-pre-wrap leading-8 text-slate-200 text-base bg-black/20 rounded-2xl p-6 border border-white/10 max-h-[65vh] overflow-y-auto">
                    {renderHighlightedText(selectedBook.full_text || '', selectedBook.node_refs || [], activeCitationTerms)}
                  </article>
                )}
              </div>
            )}

            {/* Group nodes by type - Dynamic categories */}
            {!selectedBook && (() => {
              // Get unique types from actual data
              const uniqueTypes = [...new Set(filteredGraphData.nodes.map(n => n.type || 'Uncategorized'))];

              // Sort with priority order
              const priorityTypes = ['Hub', 'Concept', 'Entity', 'Process', 'Chemical', 'Animal', 'Crisis', 'Event'];
              const sortedTypes = uniqueTypes.sort((a, b) => {
                const aIndex = priorityTypes.indexOf(a);
                const bIndex = priorityTypes.indexOf(b);
                if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
                if (aIndex !== -1) return -1;
                if (bIndex !== -1) return 1;
                return a.localeCompare(b);
              });

              // Emoji mapping
              const getTypeEmoji = (type) => {
                const emojiMap = {
                  'Hub': '🌐', 'Concept': '💡', 'Entity': '🏛', 'Process': '⚡',
                  'Chemical': '✨', 'Animal': '🐠', 'Crisis': '🔥', 'Event': '📅',
                  'Person': '👤', 'Location': '📍', 'Organization': '🏢', 'Technology': '💻',
                  'Theory': '🧠', 'Method': '🔬', 'Tool': '🛠', 'Resource': '📦'
                };
                return emojiMap[type] || '📄';
              };

              return sortedTypes.map(type => {
                const nodesOfType = filteredGraphData.nodes.filter(n => (n.type || 'Uncategorized') === type);
                if (nodesOfType.length === 0) return null;

                return (
                  <div key={type} className="mb-16">
                    <div className="flex items-center gap-3 mb-6">
                      <span className="text-3xl">{getTypeEmoji(type)}</span>
                      <h2 className="text-3xl font-black text-white uppercase tracking-tight">{type}</h2>
                      <span className="px-3 py-1 bg-cyan-500/10 rounded-full text-xs font-bold text-cyan-400">{nodesOfType.length}</span>
                    </div>

                    {/* Timeline/Reading Flow Layout */}
                    <div className="space-y-6">
                      {nodesOfType.map((node, idx) => {
                        // Get related nodes
                        const relatedLinks = filteredGraphData.links.filter(e => {
                          const sId = typeof e.source === 'object' ? e.source.id : e.source;
                          const tId = typeof e.target === 'object' ? e.target.id : e.target;
                          return String(sId) === String(node.id) || String(tId) === String(node.id);
                        });

                        return (
                          <div key={node.id} className="relative">
                            {/* Connection Line */}
                            {idx < nodesOfType.length - 1 && (
                              <div className="absolute left-8 top-full h-6 w-0.5 bg-gradient-to-b from-cyan-500/50 to-transparent"></div>
                            )}

                            <div
                              className="bg-white/5 rounded-2xl p-8 border border-white/10 hover:border-cyan-500/30 transition-all cursor-pointer group relative backdrop-blur-sm"
                              onClick={() => {
                                setSelectedNodeData(node);
                                setRightPanelMode('node');
                                // Stay in notebook view
                              }}
                            >
                              {/* Reading indicator */}
                              <div className="absolute left-0 top-0 bottom-0 w-1 bg-cyan-500/30 group-hover:bg-cyan-500 transition-all rounded-l-2xl"></div>

                              <div className="flex items-start justify-between mb-4">
                                <h3 className="text-2xl font-bold text-white group-hover:text-cyan-400 transition-colors flex-1">{node.label}</h3>
                                {node.created_at && (
                                  <span className="text-xs text-slate-500 ml-3 whitespace-nowrap">
                                    {new Date(node.created_at).toLocaleDateString('th-TH', { year: 'numeric', month: 'short', day: 'numeric' })}
                                  </span>
                                )}
                              </div>
                              <p className="text-slate-300 text-lg leading-relaxed mb-6">{node.content || 'ไม่มีเนื้อหา'}</p>

                              {/* Related nodes - for context */}
                              {relatedLinks.length > 0 && (
                                <div className="mt-6 pt-6 border-t border-white/10">
                                  <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">🔗 เชื่อมโยงกับ ({relatedLinks.length})</div>
                                  <div className="flex flex-wrap gap-2">
                                    {relatedLinks.slice(0, expandedNodeLinks.has(node.id) ? relatedLinks.length : 4).map((rel, i) => {
                                      const sId = String(typeof rel.source === 'object' ? rel.source.id : rel.source);
                                      const isOut = sId === String(node.id);
                                      const targetId = isOut ? String(typeof rel.target === 'object' ? rel.target.id : rel.target) : sId;
                                      const related = filteredGraphData.nodes.find(n => String(n.id) === targetId);
                                      if (!related) return null;

                                      return (
                                        <button
                                          key={i}
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setSelectedNodeData(related);
                                            setRightPanelMode('node');
                                            // Stay in notebook view
                                          }}
                                          className="px-3 py-1.5 bg-white/5 hover:bg-cyan-500/20 border border-white/10 hover:border-cyan-500/50 rounded-lg text-xs text-slate-300 hover:text-cyan-400 transition-all"
                                        >
                                          {isOut ? '→' : '←'} {related.label}
                                        </button>
                                      );
                                    })}
                                    {relatedLinks.length > 4 && !expandedNodeLinks.has(node.id) && (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setExpandedNodeLinks(prev => new Set([...prev, node.id]));
                                        }}
                                        className="px-3 py-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-bold cursor-pointer hover:underline"
                                      >
                                        +{relatedLinks.length - 4} more →
                                      </button>
                                    )}
                                    {expandedNodeLinks.has(node.id) && relatedLinks.length > 4 && (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setExpandedNodeLinks(prev => {
                                            const next = new Set(prev);
                                            next.delete(node.id);
                                            return next;
                                          });
                                        }}
                                        className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-400 font-bold cursor-pointer hover:underline"
                                      >
                                        ← Show less
                                      </button>
                                    )}
                                  </div>
                                </div>
                              )}

                              <div className="flex gap-3 mt-6">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setRightPanelMode('chat');
                                    setChatInput(`@${node.label} `);
                                  }}
                                  className="px-4 py-2 bg-purple-500/10 rounded-xl text-purple-400 text-xs font-bold uppercase tracking-wider hover:bg-purple-500/20 transition-all"
                                >
                                  💬 Ask AI
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setView('graph');
                                    handleNodeClick(node);
                                    flyToNode(node);
                                  }}
                                  className="px-4 py-2 bg-cyan-500/10 rounded-xl text-cyan-400 text-xs font-bold uppercase tracking-wider hover:bg-cyan-500/20 transition-all"
                                >
                                  🌐 Jump to Graph
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              });
            })()}
          </div>
        </div>

        {/* Right Panel */}
        <div
          className={`h-full bg-[#050507] border-l border-white/5 shadow-[-20px_0_50px_rgba(0,0,0,0.5)] flex flex-col ${rightPanelMode !== 'none' ? 'translate-x-0 opacity-100' : 'w-0 translate-x-full opacity-0'} relative`}
          style={{
            width: rightPanelMode !== 'none' ? `${rightPanelWidth}%` : '0%',
            transition: isResizing ? 'none' : 'width 500ms ease-in-out, opacity 500ms ease-in-out, transform 500ms ease-in-out'
          }}
        >
          {/* Resize Handle */}
          {rightPanelMode !== 'none' && (
            <div
              className="absolute left-0 top-0 bottom-0 w-1 bg-transparent hover:bg-cyan-500/50 cursor-col-resize z-50 group"
              onMouseDown={handleResizeStart}
            >
              <div className="absolute left-[-2px] top-0 bottom-0 w-1 bg-cyan-500/0 group-hover:bg-cyan-500/30 transition-colors"></div>
            </div>
          )}

          {rightPanelMode === 'node' && selectedNodeData && (
            <div className="p-6 flex items-center justify-between border-b border-white/5 shrink-0 relative z-50 bg-[#050507]">
              <div className="flex items-center gap-3">
                <span className="px-5 py-2 bg-cyan-500/10 rounded-full text-[10px] font-black text-cyan-400 uppercase tracking-widest">{selectedNodeData.type}</span>
                {selectedNodeData.created_at && (
                  <span className="text-xs text-slate-500">
                    📅 {new Date(selectedNodeData.created_at).toLocaleDateString('th-TH', { year: 'numeric', month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>
              <button
                onClick={closeRightPanel}
                className="p-3 bg-white/5 hover:bg-red-500/20 rounded-full text-slate-500 hover:text-red-400 transition-all cursor-pointer"
                title="ปิดแถบข้าง"
              >
                <X size={24} />
              </button>
            </div>
          )}

          <div className="flex-1 flex flex-col overflow-hidden relative">
            {rightPanelMode === 'node' && selectedNodeData && (
              <div className="flex-1 overflow-y-auto p-16 scrollbar-hide text-left flex flex-col h-full">
                {!isEditingMode ? (
                  <>
                    <h2 className="text-6xl font-black text-white mb-8 tracking-tighter leading-[1.1]">{selectedNodeData.label}</h2>
                    <div className="w-20 h-1.5 bg-cyan-500 mb-10 rounded-full shadow-[0_0_20px_#06b6d4]"></div>
                    <p className="text-2xl text-slate-300 leading-relaxed font-medium mb-12">{selectedNodeData.content}</p>

                    {/* Edit & Delete Buttons */}
                    <div className="flex gap-3 mb-12">
                      <button
                        onClick={() => setIsEditingMode(true)}
                        className="px-6 py-3 bg-cyan-500/10 rounded-xl text-cyan-400 text-sm font-bold uppercase tracking-wider hover:bg-cyan-500/20 transition-all"
                      >
                        ✏️ Edit Node
                      </button>
                      <button
                        onClick={handleDeleteNode}
                        className="px-6 py-3 bg-red-500/10 rounded-xl text-red-400 text-sm font-bold uppercase tracking-wider hover:bg-red-500/20 transition-all"
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="space-y-6 mb-12">
                    <h3 className="text-3xl font-black text-white mb-6">Edit Node</h3>

                    <div>
                      <label className="block text-sm font-bold text-slate-400 mb-2">Label</label>
                      <input
                        type="text"
                        value={editForm.label}
                        onChange={e => setEditForm({ ...editForm, label: e.target.value })}
                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-bold text-slate-400 mb-2">Type</label>
                      <select
                        value={editForm.type || selectedNodeData.type}
                        onChange={e => setEditForm({ ...editForm, type: e.target.value })}
                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:border-cyan-500 focus:outline-none"
                      >
                        <option value="Concept">💡 Concept</option>
                        <option value="Entity">🏛 Entity</option>
                        <option value="Process">⚡ Process</option>
                        <option value="Chemical">✨ Chemical</option>
                        <option value="Animal">🐠 Animal</option>
                        <option value="Hub">🌐 Hub</option>
                        <option value="Crisis">🔥 Crisis</option>
                        <option value="Event">📅 Event</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-bold text-slate-400 mb-2">Content</label>
                      <textarea
                        value={editForm.content}
                        onChange={e => setEditForm({ ...editForm, content: e.target.value })}
                        rows={6}
                        className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:border-cyan-500 focus:outline-none resize-none"
                      />
                    </div>

                    <div className="flex gap-3">
                      <button
                        onClick={handleUpdateNode}
                        className="px-6 py-3 bg-cyan-500 rounded-xl text-black text-sm font-bold uppercase tracking-wider hover:bg-cyan-400 transition-all"
                      >
                        💾 Save Changes
                      </button>
                      <button
                        onClick={() => setIsEditingMode(false)}
                        className="px-6 py-3 bg-white/5 rounded-xl text-slate-400 text-sm font-bold uppercase tracking-wider hover:bg-white/10 transition-all"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                <div className="mt-auto border-t border-white/5 pt-10">
                  <div className="mb-8">
                    <div className="text-xs font-black uppercase tracking-widest text-slate-500 mb-3">Books Referencing This Node</div>
                    {nodeRelatedBooks.length === 0 ? (
                      <div className="text-xs text-slate-600">ยังไม่มีหนังสือที่อ้างโหนดนี้</div>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {nodeRelatedBooks.map((b) => (
                          <button
                            key={b.id}
                            onClick={async () => {
                              try {
                                const full = await api.getBook(b.id);
                                setActiveCitationTerms([]);
                                setSelectedBook(full);
                                setView('notebook');
                                setRightPanelMode('none');
                              } catch (e) {
                                console.error('Failed to open related book:', e);
                              }
                            }}
                            className="px-3 py-1.5 rounded-lg bg-purple-500/15 border border-purple-500/20 text-purple-200 text-xs hover:bg-purple-500/25"
                          >
                            📘 {b.title}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 gap-4 pb-10">
                    {graphData.links.filter(e => {
                      const sId = typeof e.source === 'object' ? e.source.id : e.source;
                      const tId = typeof e.target === 'object' ? e.target.id : e.target;
                      return String(sId) === String(selectedNodeData.id) || String(tId) === String(selectedNodeData.id);
                    }).map((rel, i) => {
                      const sId = String(typeof rel.source === 'object' ? rel.source.id : rel.source);
                      const isOut = sId === String(selectedNodeData.id);
                      const targetId = isOut ? String(typeof rel.target === 'object' ? rel.target.id : rel.target) : sId;
                      const related = graphData.nodes.find(n => String(n.id) === targetId);
                      if (!related) return null;
                      const displayVerb = isOut ? rel.label : (rel.labelReverse || rel.label);
                      return (
                        <div key={i} className="group p-5 bg-white/5 border border-white/5 rounded-3xl hover:bg-white/10 transition-all flex items-center cursor-pointer relative overflow-hidden" onClick={() => handleNodeClick(related)}>
                          <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${isOut ? 'bg-cyan-500' : 'bg-pink-500'}`}></div>
                          <div className="flex flex-col flex-1 pl-2">
                            <div className="flex items-center gap-2 mb-1.5">
                              <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-wider ${isOut ? 'bg-cyan-500/20 text-cyan-400' : 'bg-pink-500/20 text-pink-400'}`}>
                                {isOut ? 'OUT' : 'IN'}
                              </span>
                              <span className="text-[11px] font-bold text-slate-400">{isOut ? `─ ${displayVerb} →` : `← ${displayVerb} ─`}</span>
                            </div>
                            <span className="text-white font-bold text-lg group-hover:text-cyan-300 transition-colors">{related.label}</span>
                          </div>
                          <ArrowRight size={18} className="text-slate-500 group-hover:text-white group-hover:translate-x-1 transition-all opacity-0 group-hover:opacity-100 absolute right-6" />
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {rightPanelMode === 'chat' && (
              <div className="flex flex-col h-full relative">
                <div className="flex-1 overflow-y-auto p-12 pt-8 space-y-8 scrollbar-hide text-left pb-40">
                  {chatMessages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] p-6 rounded-[32px] text-base leading-relaxed ${msg.role === 'user' ? 'bg-cyan-600 text-white rounded-tr-none shadow-xl' : 'bg-white/5 border border-white/10 text-slate-300 rounded-tl-none'}`}>
                        {msg.isThinking ? (
                          <div className="flex items-center gap-3">
                            <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
                            Processing via GraphRAG...
                          </div>
                        ) : (
                          <div className="space-y-4 text-left">
                            <p>{String(msg.text)}</p>
                            {Array.isArray(msg.sources) && msg.sources.length > 0 && (
                              <div className="pt-4 border-t border-white/10 flex flex-wrap gap-2 items-center">
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest w-full mb-1">Citations:</span>
                                {msg.sources.map((src, i) => {
                                  const refNode = graphData.nodes.find(n => n.label === src);
                                  return (
                                    <React.Fragment key={i}>
                                      <button onClick={() => refNode && handleNodeClick(refNode)} className="px-3 py-1.5 bg-black/40 hover:bg-cyan-500/20 cursor-pointer rounded-lg text-[10px] font-bold text-cyan-400 border border-white/5 hover:border-cyan-500/50 shadow-inner transition-all flex items-center gap-2">
                                        <Eye size={12} /> {src}
                                      </button>
                                      {i < msg.sources.length - 1 && <ArrowRight size={10} className="text-slate-600" />}
                                    </React.Fragment>
                                  );
                                })}

                                <span className="text-[10px] font-bold text-purple-300 uppercase tracking-widest w-full mt-3 mb-1">Book Citations:</span>
                                {[...new Set(msg.sources.flatMap((src) => {
                                  const refNode = graphData.nodes.find(n => n.label === src);
                                  if (!refNode) return [];
                                  return books.filter(b => (b.node_ids || []).includes(refNode.id)).map(b => b.id);
                                }))].slice(0, 6).map((bookId) => {
                                  const b = books.find(x => x.id === bookId);
                                  if (!b) return null;
                                  return (
                                    <button
                                      key={bookId}
                                      onClick={async () => {
                                        try {
                                          const full = await api.getBook(bookId);
                                          setActiveCitationTerms(msg.sources || []);
                                          setSelectedBook(full);
                                          setView('notebook');
                                        } catch (e) {
                                          console.error('Failed to open cited book:', e);
                                        }
                                      }}
                                      className="px-3 py-1.5 bg-purple-500/15 hover:bg-purple-500/25 rounded-lg text-[10px] font-bold text-purple-200 border border-purple-500/20"
                                    >
                                      📘 {b.title}
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="absolute bottom-0 left-0 w-full p-10 bg-gradient-to-t from-[#050507] via-[#050507] to-transparent z-20">
                  <div className="relative">
                    {/* @ Mention Suggestions Dropdown */}
                    {showMentionSuggestions && mentionSuggestions.length > 0 && (
                      <div className="absolute bottom-full left-0 mb-2 w-full max-h-80 bg-black/95 backdrop-blur-xl border border-cyan-500/30 rounded-2xl shadow-2xl overflow-y-auto">
                        {mentionSuggestions.map((node, idx) => (
                          <div
                            key={node.id}
                            className={`px-6 py-4 cursor-pointer transition-all flex items-center gap-3 ${idx === selectedSuggestionIndex
                              ? 'bg-cyan-500/20 border-l-4 border-cyan-500'
                              : 'hover:bg-white/5'
                              }`}
                            onClick={() => selectMention(node)}
                          >
                            <span className="text-2xl">{node.type === 'Hub' ? '🌐' : node.type === 'Concept' ? '💡' : node.type === 'Entity' ? '🏛' : node.type === 'Process' ? '⚡' : node.type === 'Chemical' ? '✨' : node.type === 'Animal' ? '🐠' : node.type === 'Crisis' ? '🔥' : '📅'}</span>
                            <div className="flex-1">
                              <div className="text-white font-bold">{node.label}</div>
                              <div className="text-xs text-slate-400 truncate">{node.content}</div>
                            </div>
                            <span className="text-xs text-cyan-400 font-bold px-2 py-1 bg-cyan-500/10 rounded">{node.type}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <input
                      id="chatInput"
                      value={chatInput}
                      onChange={handleChatInputChange}
                      onKeyDown={(e) => {
                        handleMentionKeyDown(e);
                        if (e.key === 'Enter' && !isAiThinking && !showMentionSuggestions) {
                          handleQuery();
                        }
                      }}
                      placeholder='พิมพ์ @ เพื่อเลือกโหนด หรือพิมพ์คำถามตรงเลย...'
                      className="w-full bg-black/80 backdrop-blur-xl border border-white/10 rounded-[30px] py-6 px-8 pr-20 text-sm focus:border-cyan-500/50 outline-none text-white placeholder:text-slate-500 shadow-2xl transition-all"
                      disabled={isAiThinking}
                    />
                    <button onClick={handleQuery} className={`absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-2xl shadow-xl transition-all ${isAiThinking ? 'bg-slate-700 text-slate-500' : 'bg-cyan-500 text-black hover:bg-cyan-400'}`} disabled={isAiThinking}><Send size={20} /></button>
                  </div>
                </div>
              </div>
            )}

            {rightPanelMode === 'add' && (
              <div className="flex flex-col h-full relative">
                <div className="flex-1 overflow-y-auto p-12 pt-8 space-y-8 scrollbar-hide text-left">
                  {/* Tab Selector */}
                  <div className="flex gap-3 mb-6">
                    <button
                      onClick={() => setAiModalMode('manual')}
                      className={`flex-1 py-4 px-6 rounded-2xl text-sm font-bold uppercase tracking-wider transition-all ${aiModalMode === 'manual'
                        ? 'bg-cyan-500 text-black'
                        : 'bg-white/5 text-slate-400 hover:bg-white/10'
                        }`}
                    >
                      ✏️ Manual
                    </button>
                    <button
                      onClick={() => setAiModalMode('text')}
                      className={`flex-1 py-4 px-6 rounded-2xl text-sm font-bold uppercase tracking-wider transition-all ${aiModalMode === 'text'
                        ? 'bg-cyan-500 text-black'
                        : 'bg-white/5 text-slate-400 hover:bg-white/10'
                        }`}
                    >
                      📝 Text Extract
                    </button>
                    <button
                      onClick={() => setAiModalMode('document')}
                      className={`flex-1 py-4 px-6 rounded-2xl text-sm font-bold uppercase tracking-wider transition-all ${aiModalMode === 'document'
                        ? 'bg-cyan-500 text-black'
                        : 'bg-white/5 text-slate-400 hover:bg-white/10'
                        }`}
                    >
                      📄 Document
                    </button>
                  </div>

                  {/* Content Area */}
                  <div className="space-y-6">
                    {aiModalMode === 'text' ? (
                      <div>
                        <label className="text-[10px] font-black uppercase text-slate-500 mb-3 block pl-2">Input Source Text</label>
                        <textarea
                          value={aiInputText}
                          onChange={e => setAiInputText(e.target.value)}
                          placeholder="วางบทความยาวๆ เพื่อสกัด Entity ผ่าน AI..."
                          className="w-full h-96 bg-white/5 border border-white/10 p-6 rounded-3xl text-lg text-slate-300 outline-none focus:border-cyan-500/50 resize-none transition-colors"
                        />
                      </div>
                    ) : aiModalMode === 'document' ? (
                      <div>
                        <label className="text-[10px] font-black uppercase text-slate-500 mb-3 block pl-2">Upload Document</label>
                        <div
                          className="w-full h-96 bg-white/5 border-2 border-dashed border-white/10 rounded-3xl flex flex-col items-center justify-center cursor-pointer hover:border-cyan-500/50 hover:bg-white/10 transition-all"
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault();
                            const file = e.dataTransfer.files[0];
                            if (file && (file.type === 'application/pdf' || file.name.endsWith('.docx'))) {
                              setUploadedFile(file);
                            }
                          }}
                          onClick={() => document.getElementById('fileInput')?.click()}
                        >
                          <input
                            id="fileInput"
                            type="file"
                            accept=".pdf,.docx"
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files[0];
                              if (file) setUploadedFile(file);
                            }}
                          />
                          {uploadedFile ? (
                            <div className="text-center">
                              <div className="text-6xl mb-4">📄</div>
                              <div className="text-white font-bold text-xl mb-2">{uploadedFile.name}</div>
                              <div className="text-slate-400 text-sm">{(uploadedFile.size / 1024).toFixed(1)} KB</div>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setUploadedFile(null);
                                }}
                                className="mt-4 px-4 py-2 bg-red-500/20 text-red-400 rounded-xl text-xs font-bold hover:bg-red-500/30 transition-all"
                              >
                                Remove
                              </button>
                            </div>
                          ) : (
                            <div className="text-center">
                              <div className="text-6xl mb-4">📎</div>
                              <div className="text-white font-bold text-xl mb-2">Drop file here</div>
                              <div className="text-slate-400 text-sm">or click to browse</div>
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <>
                        <div>
                          <label className="text-[10px] font-black text-slate-500 uppercase mb-2 block pl-2">Label (ชื่อโหนด)</label>
                          <input
                            value={newNodeForm.label}
                            onChange={e => setNewNodeForm({ ...newNodeForm, label: e.target.value })}
                            placeholder="ชื่อโหนด"
                            className="w-full bg-white/5 border border-white/10 p-5 rounded-3xl text-xl font-bold text-white outline-none focus:border-cyan-500/50"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] font-black text-slate-500 uppercase mb-2 block pl-2">Type</label>
                          <select
                            value={newNodeForm.type}
                            onChange={e => setNewNodeForm({ ...newNodeForm, type: e.target.value })}
                            className="w-full bg-white/5 border border-white/10 p-5 rounded-3xl text-lg text-white outline-none focus:border-cyan-500/50"
                          >
                            <option value="Concept">💡 Concept</option>
                            <option value="Entity">🏛 Entity</option>
                            <option value="Process">⚡ Process</option>
                            <option value="Chemical">✨ Chemical</option>
                            <option value="Animal">🐠 Animal</option>
                            <option value="Hub">🌐 Hub</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-[10px] font-black text-slate-500 uppercase mb-2 block pl-2">Content</label>
                          <textarea
                            value={newNodeForm.content}
                            onChange={e => setNewNodeForm({ ...newNodeForm, content: e.target.value })}
                            placeholder="เนื้อหา..."
                            className="w-full h-48 bg-white/5 border border-white/10 p-6 rounded-3xl text-lg text-slate-300 outline-none focus:border-cyan-500/50 resize-none"
                          />
                        </div>

                        {/* AI Suggested Connections */}
                        {(isLoadingSuggestions || suggestedConnections.length > 0) && (
                          <div className="bg-gradient-to-br from-purple-500/10 to-cyan-500/10 border border-purple-500/20 rounded-2xl p-5">
                            <div className="flex items-center gap-2 mb-3">
                              <Sparkles size={16} className="text-purple-400" />
                              <h4 className="text-xs font-bold uppercase text-purple-400 tracking-wider">
                                AI Suggested Connections
                              </h4>
                              {isLoadingSuggestions && (
                                <div className="ml-auto w-3 h-3 border-2 border-purple-400 border-t-transparent rounded-full animate-spin"></div>
                              )}
                            </div>
                            {isLoadingSuggestions ? (
                              <div className="text-xs text-slate-400">Searching similar nodes...</div>
                            ) : suggestedConnections.length > 0 ? (
                              <div className="space-y-2">
                                {suggestedConnections.map(node => (
                                  <div
                                    key={node.id}
                                    className="bg-white/5 rounded-xl p-3 flex items-start justify-between gap-3 hover:bg-white/10 transition-all group"
                                  >
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="px-2 py-0.5 bg-purple-500/20 rounded text-[9px] font-bold text-purple-400">{node.type}</span>
                                        <div className="text-sm font-bold text-white truncate">{node.label}</div>
                                      </div>
                                      <div className="text-xs text-slate-400 truncate">{node.content}</div>
                                    </div>
                                    <div className="flex gap-1.5 shrink-0">
                                      <button
                                        onClick={() => {
                                          setSelectedNodeData(node);
                                          setRightPanelMode('node');
                                        }}
                                        className="px-2 py-1 bg-cyan-500/20 hover:bg-cyan-500/30 rounded text-[10px] font-bold text-cyan-400 transition-all whitespace-nowrap"
                                        title="View node"
                                      >
                                        <Eye size={12} className="inline" />
                                      </button>
                                      <button
                                        onClick={() => {
                                          setNewNodeForm({ ...newNodeForm, linkTarget: node.id });
                                        }}
                                        className="px-2 py-1 bg-purple-500/20 hover:bg-purple-500/30 rounded text-[10px] font-bold text-purple-400 transition-all whitespace-nowrap"
                                        title="Link to this node"
                                      >
                                        <LinkIcon size={12} className="inline" />
                                      </button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        )}

                        {/* Link to existing node */}
                        <div>
                          <label className="text-[10px] font-black text-slate-500 uppercase mb-2 block pl-2">เชื่อมโยงกับ (Optional)</label>
                          <select
                            value={newNodeForm.linkTarget}
                            onChange={e => setNewNodeForm({ ...newNodeForm, linkTarget: e.target.value })}
                            className="w-full bg-white/5 border border-white/10 p-4 rounded-2xl text-slate-300 outline-none focus:border-cyan-500/50 mb-3"
                          >
                            <option value="">-- ไม่เชื่อมโยง --</option>
                            {graphData.nodes.map(n => (
                              <option key={n.id} value={n.id}>{n.label}</option>
                            ))}
                          </select>
                          {newNodeForm.linkTarget && (
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className="text-[8px] font-bold text-cyan-500 uppercase mb-1 block pl-2">กริยาขาไป →</label>
                                <input
                                  value={newNodeForm.forwardLabel}
                                  onChange={e => setNewNodeForm({ ...newNodeForm, forwardLabel: e.target.value })}
                                  placeholder="เช่น เป็นส่วนหนึ่งของ"
                                  list="forward-relations"
                                  className="w-full bg-white/5 border border-white/10 p-3 rounded-xl text-sm text-white outline-none focus:border-cyan-500"
                                />
                              </div>
                              <div>
                                <label className="text-[8px] font-bold text-pink-500 uppercase mb-1 block pl-2">กริยาขากลับ ←</label>
                                <input
                                  value={newNodeForm.backwardLabel}
                                  onChange={e => setNewNodeForm({ ...newNodeForm, backwardLabel: e.target.value })}
                                  placeholder="เช่น ประกอบด้วย"
                                  list="backward-relations"
                                  className="w-full bg-white/5 border border-white/10 p-3 rounded-xl text-sm text-white outline-none focus:border-pink-500"
                                />
                              </div>
                              <datalist id="forward-relations">
                                <option value="เกี่ยวข้องกับ" />
                                <option value="เป็นส่วนหนึ่งของ" />
                                <option value="ใช้" />
                                <option value="สนับสนุน" />
                                <option value="อธิบาย" />
                                <option value="ขัดแย้งกับ" />
                              </datalist>
                              <datalist id="backward-relations">
                                <option value="เกี่ยวข้องกับ" />
                                <option value="ประกอบด้วย" />
                                <option value="ถูกใช้โดย" />
                                <option value="ได้รับการสนับสนุนจาก" />
                                <option value="ถูกอธิบายโดย" />
                                <option value="ถูกโต้แย้งโดย" />
                              </datalist>
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>

                  {/* Post-creation: Smart Connection Suggestions */}
                  {lastCreatedNode && postCreationSuggestions.length > 0 && (
                    <div className="mt-6 bg-gradient-to-br from-green-500/10 to-cyan-500/10 border border-green-500/30 rounded-2xl p-5 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Zap size={16} className="text-green-400" />
                          <h4 className="text-xs font-black uppercase text-green-400 tracking-wider">
                            ✅ โหนด "{lastCreatedNode.label}" ถูกสร้างแล้ว
                          </h4>
                        </div>
                        <button
                          onClick={() => { setLastCreatedNode(null); setPostCreationSuggestions([]); setRightPanelMode('none'); }}
                          className="text-slate-500 hover:text-white transition-colors"
                        >
                          <X size={14} />
                        </button>
                      </div>
                      <p className="text-xs text-slate-400">พบโหนดที่เกี่ยวข้องในกราฟ — คลิก Connect เพื่อเชื่อมโยง:</p>
                      <div className="space-y-2">
                        {postCreationSuggestions.map(s => (
                          <div key={s.id} className="bg-white/5 rounded-xl p-3 flex items-start justify-between gap-3 hover:bg-white/10 transition-all">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="px-2 py-0.5 bg-cyan-500/20 rounded text-[9px] font-bold text-cyan-400">{s.type}</span>
                                <span className="text-[9px] text-slate-500">{Math.round(s.similarity * 100)}% match</span>
                                {typeof s.inference_confidence === 'number' && s.inference_confidence > 0 && (
                                  <span className="text-[9px] text-emerald-400">AI {Math.round(s.inference_confidence * 100)}%</span>
                                )}
                                <div className="text-sm font-bold text-white truncate">{s.label}</div>
                              </div>
                              <div className="text-[11px] text-emerald-300 mb-1">
                                Suggested relation: {s.suggested_label || 'เกี่ยวข้องกับ'}
                              </div>
                              {s.inference_reason && (
                                <div className="text-[11px] text-slate-500 line-clamp-2 mb-1">{s.inference_reason}</div>
                              )}
                              <div className="text-xs text-slate-400 truncate">{s.content}</div>
                            </div>
                            <button
                              onClick={() => handleConnectSuggested(s)}
                              disabled={isConnectingSuggestion}
                              className="shrink-0 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/40 rounded-lg text-[10px] font-bold text-green-400 transition-all disabled:opacity-50 flex items-center gap-1 whitespace-nowrap"
                            >
                              <LinkIcon size={10} /> Connect
                            </button>
                          </div>
                        ))}
                      </div>
                      <button
                        onClick={() => { setLastCreatedNode(null); setPostCreationSuggestions([]); setRightPanelMode('none'); }}
                        className="w-full py-2 text-xs text-slate-400 hover:text-white transition-colors"
                      >
                        ข้ามทั้งหมด →
                      </button>
                    </div>
                  )}

                  {/* Action Button */}
                  {!lastCreatedNode && (
                  <div className="pt-6">
                    <button
                      onClick={aiModalMode === 'manual' ? handleAddNode : handleAIProcess}
                      disabled={isAiThinking}
                      className="w-full py-6 bg-cyan-500 text-black rounded-3xl text-sm font-black uppercase tracking-widest hover:bg-cyan-400 transition-all shadow-2xl disabled:opacity-50"
                    >
                      {isAiThinking ? "⚡ Processing..." : (aiModalMode === 'manual' ? "💾 Add Node" : "🤖 Extract Entities")}
                    </button>
                  </div>
                  )}
                </div>
              </div>
            )}

            {/* Quiz Panel */}
            {rightPanelMode === 'quiz' && (
              <div className="flex flex-col h-full relative">
                <div className="flex-1 overflow-y-auto p-10 pt-6 scrollbar-hide text-left">
                  
                  {/* Dashboard Home */}
                  {quizDashboardMode === 'home' && (
                    <div className="space-y-8">
                      {/* Header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="p-4 bg-gradient-to-br from-green-500/20 to-teal-500/20 rounded-2xl">
                            <Sparkles size={40} className="text-green-400" />
                          </div>
                          <div>
                            <h2 className="text-4xl font-black text-white">Quiz Center</h2>
                            <p className="text-slate-400 text-sm mt-1">เรียนรู้ผ่านคำถาม AI สร้างอัตโนมัติ</p>
                          </div>
                        </div>
                      </div>

                      {/* Stats Cards */}
                      {quizStats && (
                        <div className="grid grid-cols-3 gap-4">
                          <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20 rounded-2xl p-6">
                            <div className="text-4xl font-black text-blue-400">{quizStats.total_attempts || 0}</div>
                            <div className="text-xs text-slate-400 uppercase tracking-wider mt-2">Total Attempts</div>
                          </div>
                          <div className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 border border-green-500/20 rounded-2xl p-6">
                            <div className="text-4xl font-black text-green-400">{Math.round(quizStats.accuracy || 0)}%</div>
                            <div className="text-xs text-slate-400 uppercase tracking-wider mt-2">Accuracy</div>
                          </div>
                          <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-2xl p-6">
                            <div className="text-4xl font-black text-purple-400">{quizStats.correct_count || 0}</div>
                            <div className="text-xs text-slate-400 uppercase tracking-wider mt-2">Correct Answers</div>
                          </div>
                        </div>
                      )}

                      {/* Category Selection */}
                      <div className="space-y-4">
                        <h3 className="text-xl font-bold text-white">เลือกหมวดหมู่</h3>
                        <div className="flex flex-wrap gap-3">
                          <button
                            onClick={() => setSelectedQuizCategory('all')}
                            className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                              selectedQuizCategory === 'all'
                                ? 'bg-green-500 text-white'
                                : 'bg-white/5 text-slate-400 hover:bg-white/10'
                            }`}
                          >
                            🌟 All Topics
                          </button>
                          {quizCategories.map((cat) => (
                            <button
                              key={cat.type}
                              onClick={() => setSelectedQuizCategory(cat.type)}
                              className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                                selectedQuizCategory === cat.type
                                  ? 'bg-green-500 text-white'
                                  : 'bg-white/5 text-slate-400 hover:bg-white/10'
                              }`}
                            >
                              {cat.type} ({cat.count})
                            </button>
                          ))}
                        </div>
                        <div className="pt-3">
                          <label className="text-xs text-slate-500 block mb-2">หรือเลือกควิซจากหนังสือ</label>
                          <select
                            value={selectedQuizBookId}
                            onChange={(e) => setSelectedQuizBookId(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm text-white"
                          >
                            <option value="">สุ่มจากโหนดทั้งหมด</option>
                            {quizBooks.map((b) => (
                              <option key={b.id} value={b.id}>{b.title} ({b.node_count})</option>
                            ))}
                          </select>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="grid grid-cols-2 gap-4 pt-4">
                        <button
                          onClick={() => {
                            setQuizDashboardMode('playing');
                            generateQuiz();
                          }}
                          className="py-6 bg-gradient-to-r from-green-500 to-teal-500 hover:from-green-600 hover:to-teal-600 rounded-2xl text-white font-black text-lg shadow-xl shadow-green-500/20 transition-all flex items-center justify-center gap-3"
                        >
                          <Zap size={24} />
                          เริ่มควิซใหม่
                        </button>
                        <button
                          onClick={() => setQuizDashboardMode('history')}
                          className="py-6 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-white font-bold text-lg transition-all flex items-center justify-center gap-3"
                        >
                          📚 ดูประวัติ
                        </button>
                      </div>

                      {/* Recent Activity Preview */}
                      {quizHistory.length > 0 && (
                        <div className="space-y-4">
                          <h3 className="text-xl font-bold text-white">กิจกรรมล่าสุด</h3>
                          <div className="space-y-2">
                            {quizHistory.slice(0, 3).map((attempt, idx) => (
                              <div key={idx} className="bg-white/5 border border-white/10 rounded-xl p-4 flex items-center gap-4">
                                <div className={`text-2xl ${attempt.is_correct ? '✅' : '❌'}`}>
                                  {attempt.is_correct ? '✅' : '❌'}
                                </div>
                                <div className="flex-1">
                                  <div className="text-sm font-bold text-white">{attempt.question}</div>
                                  <div className="text-xs text-slate-400 mt-1">{attempt.node_label} • {attempt.node_type}</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Playing Mode */}
                  {quizDashboardMode === 'playing' && (
                    <div className="space-y-6">
                      {/* Back Button */}
                      <button
                        onClick={() => setQuizDashboardMode('home')}
                        className="text-slate-400 hover:text-white transition-all text-sm flex items-center gap-2"
                      >
                        ← กลับหน้าหลัก
                      </button>

                      {isGeneratingQuiz ? (
                        <div className="flex flex-col items-center justify-center py-20">
                          <div className="w-16 h-16 border-4 border-green-400 border-t-transparent rounded-full animate-spin mb-6"></div>
                          <div className="text-slate-400">กำลังสร้างคำถาม...</div>
                          <div className="text-xs text-slate-500 mt-2">AI กำลังวิเคราะห์ความรู้ของคุณ</div>
                        </div>
                      ) : currentQuiz ? (
                        <div className="space-y-6">
                          {/* Question Card */}
                          <div className="bg-gradient-to-br from-green-500/20 to-teal-500/20 border-2 border-green-500/30 rounded-3xl p-8">
                            <div className="flex items-center gap-2 mb-4">
                              <div className="px-3 py-1 bg-green-500/20 rounded-full text-xs font-bold text-green-400">
                                {currentQuiz.nodeLabel}
                              </div>
                              <div className="text-xs text-slate-400">• จากโหนด</div>
                            </div>
                            <div className="text-2xl font-bold text-white leading-relaxed">{currentQuiz.question}</div>
                            {currentQuiz.hint && !quizResult && (
                              <div className="mt-6 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl">
                                <div className="text-xs font-bold text-yellow-400 mb-1">💡 คำใบ้</div>
                                <div className="text-sm text-slate-300">{currentQuiz.hint}</div>
                              </div>
                            )}
                          </div>

                          {/* Answer Input or Result */}
                          {!quizResult ? (
                            <div className="space-y-4">
                              <textarea
                                value={quizAnswer}
                                onChange={(e) => setQuizAnswer(e.target.value)}
                                placeholder="พิมพ์คำตอบของคุณที่นี่..."
                                className="w-full h-40 bg-white/5 border-2 border-white/10 focus:border-green-500/50 rounded-2xl p-6 text-lg text-white outline-none resize-none transition-all"
                                autoFocus
                              />
                              <button
                                onClick={checkQuizAnswer}
                                disabled={!quizAnswer.trim()}
                                className="w-full py-5 bg-gradient-to-r from-green-500 to-teal-500 hover:from-green-600 hover:to-teal-600 text-white font-black text-lg rounded-2xl transition-all disabled:opacity-30 disabled:cursor-not-allowed shadow-xl shadow-green-500/20"
                              >
                                ส่งคำตอบ →
                              </button>
                            </div>
                          ) : (
                            <div className={`rounded-3xl p-8 border-2 transition-all ${
                              quizResult.correct
                                ? 'bg-green-500/20 border-green-500/50'
                                : 'bg-red-500/20 border-red-500/50'
                            }`}>
                              <div className="text-6xl mb-4">{quizResult.correct ? '🎉' : '😅'}</div>
                              <div className="text-2xl font-black text-white mb-3">
                                {quizResult.correct ? 'ยอดเยี่ยม!' : '  ยังไม่ถูกนะ'}
                              </div>
                              <div className="text-lg text-slate-200 mb-6 leading-relaxed">{quizResult.feedback}</div>
                              
                              {!quizResult.correct && (
                                <div className="bg-black/30 rounded-2xl p-5 mb-6 border border-white/10">
                                  <div className="text-xs font-bold text-slate-400 uppercase mb-2">คำตอบที่ถูกต้อง:</div>
                                  <div className="text-xl text-white font-bold">{currentQuiz.answer}</div>
                                </div>
                              )}
                              
                              <div className="grid grid-cols-2 gap-3">
                                <button
                                  onClick={() => {
                                    generateQuiz();
                                    setQuizAnswer('');
                                    setQuizResult(null);
                                  }}
                                  className="py-4 bg-gradient-to-r from-green-500 to-teal-500 hover:from-green-600 hover:to-teal-600 text-white font-bold rounded-xl transition-all"
                                >
                                  คำถามถัดไป →
                                </button>
                                <button
                                  onClick={() => setQuizDashboardMode('home')}
                                  className="py-4 bg-white/10 hover:bg-white/20 text-white font-bold rounded-xl transition-all"
                                >
                                  กลับหน้าหลัก
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-center py-20 text-slate-400">
                          ไม่มีโหนดในกราฟ กรุณาเพิ่มข้อมูลก่อน
                        </div>
                      )}
                    </div>
                  )}

                  {/* History Mode */}
                  {quizDashboardMode === 'history' && (
                    <div className="space-y-6">
                      {/* Back Button */}
                      <button
                        onClick={() => setQuizDashboardMode('home')}
                        className="text-slate-400 hover:text-white transition-all text-sm flex items-center gap-2"
                      >
                        ← กลับหน้าหลัก
                      </button>

                      <div className="flex items-center gap-4 mb-4">
                        <div className="p-3 bg-purple-500/20 rounded-2xl">
                          📚
                        </div>
                        <h2 className="text-3xl font-black text-white">ประวัติการทำควิซ</h2>
                      </div>

                      {/* Stats Summary */}
                      {quizStats && (
                        <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-2xl p-6">
                          <div className="grid grid-cols-4 gap-4 text-center">
                            <div>
                              <div className="text-3xl font-black text-purple-400">{quizStats.total_attempts}</div>
                              <div className="text-xs text-slate-400 mt-1">Attempts</div>
                            </div>
                            <div>
                              <div className="text-3xl font-black text-green-400">{quizStats.correct_count}</div>
                              <div className="text-xs text-slate-400 mt-1">Correct</div>
                            </div>
                            <div>
                              <div className="text-3xl font-black text-red-400">{quizStats.incorrect_count}</div>
                              <div className="text-xs text-slate-400 mt-1">Incorrect</div>
                            </div>
                            <div>
                              <div className="text-3xl font-black text-cyan-400">{Math.round(quizStats.accuracy)}%</div>
                              <div className="text-xs text-slate-400 mt-1">Accuracy</div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* History List */}
                      {quizHistory.length > 0 ? (
                        <div className="space-y-3">
                          {quizHistory.map((attempt, idx) => (
                            <div
                              key={idx}
                              className={`p-5 rounded-2xl border-2 transition-all ${
                                attempt.is_correct
                                  ? 'bg-green-500/5 border-green-500/20'
                                  : 'bg-red-500/5 border-red-500/20'
                              }`}
                            >
                              <div className="flex items-start gap-4">
                                <div className="text-3xl">{attempt.is_correct ? '✅' : '❌'}</div>
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-2">
                                    <div className={`px-2 py-1 rounded text-xs font-bold ${
                                      attempt.is_correct ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                                    }`}>
                                      {attempt.is_correct ? 'ถูก' : 'ผิด'}
                                    </div>
                                    <div className="px-2 py-1 bg-white/5 rounded text-xs text-slate-400">
                                      {attempt.node_type}
                                    </div>
                                  </div>
                                  <div className="text-base font-bold text-white mb-2">{attempt.question}</div>
                                  <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                      <div className="text-xs text-slate-500">คำตอบของคุณ:</div>
                                      <div className="text-slate-300">{attempt.user_answer}</div>
                                    </div>
                                    {!attempt.is_correct && (
                                      <div>
                                        <div className="text-xs text-slate-500">คำตอบที่ถูก:</div>
                                        <div className="text-green-400 font-bold">{attempt.correct_answer}</div>
                                      </div>
                                    )}
                                  </div>
                                  <div className="text-xs text-slate-500 mt-3">
                                    📍 {attempt.node_label} • {new Date(attempt.created_at).toLocaleDateString('th-TH', {
                                      year: 'numeric',
                                      month: 'short',
                                      day: 'numeric',
                                      hour: '2-digit',
                                      minute: '2-digit'
                                    })}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-20">
                          <div className="text-6xl mb-4">📝</div>
                          <div className="text-slate-400">ยังไม่มีประวัติการทำควิซ</div>
                          <button
                            onClick={() => {
                              setQuizDashboardMode('playing');
                              generateQuiz();
                            }}
                            className="mt-6 px-6 py-3 bg-green-500 hover:bg-green-600 text-white font-bold rounded-xl transition-all"
                          >
                            เริ่มทำควิซเลย!
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Review Panel (Spaced Repetition) */}
      {showReviewPanel && (
        <div className="fixed right-6 bottom-6 w-96 max-h-[60vh] bg-black/95 backdrop-blur-xl border border-yellow-500/30 rounded-2xl shadow-2xl z-50 flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-white/10">
            <div className="flex items-center gap-2">
              <span className="text-xl">📚</span>
              <h3 className="font-bold text-white">Review Queue</h3>
            </div>
            <button onClick={() => setShowReviewPanel(false)} className="p-1 hover:bg-white/10 rounded text-slate-400">
              <X size={16} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {reviewQueue.map(node => {
              const daysUntilReview = Math.ceil((node.reviewDate - Date.now()) / (24 * 60 * 60 * 1000));
              return (
                <div key={node.id} className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <span className="px-2 py-1 bg-yellow-500/20 rounded text-xs font-bold text-yellow-400">{node.type}</span>
                    <span className="text-xs text-slate-500">
                      {daysUntilReview > 0 ? `in ${daysUntilReview}d` : 'Ready'}
                    </span>
                  </div>
                  <div className="font-bold text-white mb-2">{node.label}</div>
                  <div className="text-xs text-slate-400 truncate">{node.content}</div>
                  <button
                    onClick={() => {
                      setSelectedNodeData(node);
                      setRightPanelMode('node');
                      setShowReviewPanel(false);
                    }}
                    className="mt-3 w-full py-2 bg-yellow-500/20 hover:bg-yellow-500/30 rounded text-xs font-bold text-yellow-400 transition-all"
                  >
                    Review Now
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* --- REVIEW MODAL (Keep for confirmation) --- */}
      {pendingAIData && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center p-8 bg-black/95 backdrop-blur-3xl animate-in zoom-in duration-300">
          <div className="w-full max-w-4xl max-h-full bg-[#0a0a0c] border border-cyan-500/30 rounded-[50px] p-12 shadow-[0_0_50px_rgba(6,182,212,0.15)] relative flex flex-col">
            <div className="flex items-center gap-4 mb-8 shrink-0">
              <div className="p-3 bg-cyan-500/20 rounded-2xl text-cyan-400"><Network size={24} /></div>
              <div>
                <h2 className="text-3xl font-black text-white uppercase tracking-tight">Entity Resolution Preview</h2>
                <p className="text-sm text-slate-400">ตรวจสอบความเชื่อมโยงก่อนบันทึก</p>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto pr-4 scrollbar-hide space-y-10 text-left">
              <div>
                <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-4 border-b border-white/10 pb-2">New Nodes</h3>
                <div className="space-y-4">
                  {pendingAIData.nodes.map((node) => (
                    <div key={node.id} className="bg-white/5 p-6 rounded-3xl border border-white/5 flex flex-col gap-3">
                      <div className="flex gap-4">
                        <div className="flex-1">
                          <label className="text-[10px] font-bold text-cyan-500 uppercase mb-1 block">Label</label>
                          <input value={node.label} onChange={(e) => setPendingAIData(prev => ({ ...prev, nodes: prev.nodes.map(n => n.id === node.id ? { ...n, label: e.target.value } : n) }))} className="w-full bg-black/40 border border-white/10 p-3 rounded-xl text-white font-bold outline-none focus:border-cyan-500" />
                        </div>
                        <div className="w-32">
                          <label className="text-[10px] font-bold text-slate-500 uppercase mb-1 block">Type</label>
                          <input value={node.type} onChange={(e) => setPendingAIData(prev => ({ ...prev, nodes: prev.nodes.map(n => n.id === node.id ? { ...n, type: e.target.value } : n) }))} className="w-full bg-black/40 border border-white/10 p-3 rounded-xl text-slate-300 text-sm outline-none focus:border-cyan-500" />
                        </div>
                      </div>
                      <div><label className="text-[10px] font-bold text-slate-500 uppercase mb-1 block">Content</label><textarea value={node.content} onChange={(e) => setPendingAIData(prev => ({ ...prev, nodes: prev.nodes.map(n => n.id === node.id ? { ...n, content: e.target.value } : n) }))} className="w-full bg-black/40 border border-white/10 p-3 rounded-xl text-slate-300 text-sm outline-none focus:border-cyan-500 resize-none h-20" /></div>
                    </div>
                  ))}
                </div>
              </div>

              {pendingAIData.links && pendingAIData.links.length > 0 && (
                <div>
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 mb-4 border-b border-white/10 pb-2">New Relations</h3>
                  <div className="space-y-3">
                    {pendingAIData.links.map((link) => {
                      const sNode = pendingAIData.nodes.find(n => n.id === link.source) || graphData.nodes.find(n => n.id === link.source);
                      const tNode = pendingAIData.nodes.find(n => n.id === link.target) || graphData.nodes.find(n => n.id === link.target);
                      return (
                        <div key={link.id} className="bg-white/5 p-4 rounded-2xl border border-white/5 flex items-center gap-4">
                          <div className="flex-1 text-right text-xs font-bold text-white truncate px-2">{sNode?.label || link.source}</div>
                          <div className="flex-[1.5] flex gap-2">
                            <input value={link.label} onChange={(e) => setPendingAIData(prev => ({ ...prev, links: prev.links.map(l => l.id === link.id ? { ...l, label: e.target.value } : l) }))} className="w-full text-center bg-black/40 border border-cyan-500/30 p-2 rounded-lg text-cyan-400 text-[10px] font-black uppercase outline-none focus:border-cyan-500" title="Forward" />
                            <input value={link.labelReverse} onChange={(e) => setPendingAIData(prev => ({ ...prev, links: prev.links.map(l => l.id === link.id ? { ...l, labelReverse: e.target.value } : l) }))} className="w-full text-center bg-black/40 border border-pink-500/30 p-2 rounded-lg text-pink-400 text-[10px] font-black uppercase outline-none focus:border-pink-500" title="Reverse" />
                          </div>
                          <div className="flex-1 text-left text-xs font-bold text-white truncate px-2">{tNode?.label || link.target}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <div className="flex gap-4 mt-8 pt-6 border-t border-white/10 shrink-0">
              <button onClick={() => { setPendingAIData(null); setPendingBookDraft(null); }} className="flex-1 py-5 bg-white/5 hover:bg-red-500/20 text-slate-400 hover:text-red-400 rounded-[24px] text-sm font-bold uppercase tracking-widest transition-all">ยกเลิก</button>
              <button onClick={handleConfirmAIData} disabled={isAiThinking || isPersistingMemory} className="flex-[2] py-5 bg-cyan-500 text-black shadow-[0_0_30px_rgba(6,182,212,0.3)] hover:scale-[1.02] rounded-[24px] text-sm font-black uppercase tracking-widest transition-all flex items-center justify-center gap-2 disabled:opacity-50">{isPersistingMemory ? '🧠 กำลังเชื่อมโยงความจำ...' : <><Check size={18} /> ยืนยันและบันทึก</>}</button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Link Modal */}
      {linkSetupModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 backdrop-blur-md animate-in fade-in">
          <form onSubmit={handleCreateManualLink} className="bg-[#0a0a0c] border border-white/10 p-12 rounded-[50px] shadow-2xl w-[600px]">
            <div className="flex items-center gap-4 mb-8"><div className="p-3 bg-pink-500/20 rounded-2xl text-pink-500"><LinkIcon size={24} /></div><h3 className="text-3xl font-black text-white uppercase tracking-tight">สร้างความสัมพันธ์</h3></div>
            <div className="mb-8"><label className="text-[10px] font-bold uppercase text-slate-500 block pl-2 mb-2">จาก (Source)</label><div className="w-full bg-white/5 border border-white/10 p-4 rounded-2xl text-lg text-slate-400">{linkSetupModal.source.label}</div></div>
            <div className="mb-8"><label className="text-[10px] font-bold uppercase text-cyan-400 block pl-2 mb-2">ไปที่ (Target)</label><select required name="targetId" defaultValue="" className="w-full bg-white/5 border border-white/10 p-4 rounded-2xl text-white outline-none focus:border-cyan-500 font-bold italic"><option value="" disabled>-- โปรดเลือกโหนดปลายทาง --</option>{graphData.nodes.filter(n => String(n.id) !== String(linkSetupModal.source.id)).map(n => (<option key={n.id} value={n.id}>{n.label}</option>))}</select></div>
            <div className="space-y-6 mb-10"><div><label className="text-[10px] font-bold uppercase text-cyan-500 block pl-2 mb-2">กริยาขาไป</label><input required name="forward" placeholder="เช่น ส่งผลต่อ" className="w-full bg-white/5 border border-white/10 p-5 rounded-2xl text-lg text-white outline-none focus:border-cyan-500" /></div><div><label className="text-[10px] font-bold uppercase text-pink-500 block pl-2 mb-2">กริยาขากลับ</label><input required name="backward" placeholder="เช่น ได้รับผลจาก" className="w-full bg-white/5 border border-white/10 p-5 rounded-2xl text-lg text-white outline-none focus:border-pink-500" /></div></div>
            <div className="flex gap-4"><button type="button" onClick={() => setLinkSetupModal(null)} className="flex-1 py-5 bg-white/5 rounded-[24px] text-sm font-bold text-slate-400">ยกเลิก</button><button type="submit" className="flex-1 py-5 bg-pink-500 text-white shadow-xl rounded-[24px] text-sm font-black uppercase">บันทึก</button></div>
          </form>
        </div>
      )}

    </div>
  );
};

export default App;
