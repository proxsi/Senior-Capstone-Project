/* Browse chunks and review structured extraction before database upload.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import React, { useState, useEffect } from 'react';
import { X, Upload, Book, Search, Loader2, FileText, Sparkles, Check, Edit2, Trash2 } from 'lucide-react';

/** A chunk as returned by GET /knowledge-base/chunks (already embedded and stored). */
interface KnowledgeChunk {
  chunk_id: string;
  source_entity: string;
  entity_type: string;
  topic_tag: string;
  embedding_text: string;
  relation_desc: string;
  source_url: string;
  created_at: string;
}

/**
 * A chunk produced by POST /knowledge-base/preview.
 * Identical to KnowledgeChunk minus the server-assigned id and timestamp, because it only
 * exists in the browser until the user confirms the batch upload.
 */
interface PreviewChunk {
  source_entity: string;
  entity_type: string;
  topic_tag: string;
  embedding_text: string;
  relation_desc: string;
  source_url: string;
}

interface KnowledgeBaseModalProps {
  /** Controls rendering; the component returns null while false. */
  isOpen: boolean;
  /** Invoked by the header close button; App flips the visibility flag. */
  onClose: () => void;
}

const KnowledgeBaseModal: React.FC<KnowledgeBaseModalProps> = ({ isOpen, onClose }) => {
  /** Which of the three upload/browse modes is visible. */
  const [activeTab, setActiveTab] = useState<'browse' | 'upload' | 'bulk'>('browse');
  /** Client-side substring filter applied to the loaded chunks. */
  const [searchQuery, setSearchQuery] = useState('');
  /** Server-side chunks currently loaded in the browse tab. */
  const [knowledgeChunks, setKnowledgeChunks] = useState<KnowledgeChunk[]>([]);
  /** True during the initial list fetch (browse spinner only). */
  const [loading, setLoading] = useState(false);
  /** Controlled state for the single-chunk upload form. */
  const [uploadForm, setUploadForm] = useState({
    source_entity: '',
    entity_type: '非遗项目',
    topic_tag: '定义概述',
    embedding_text: '',
    relation_desc: '',
    source_url: ''
  });
  /** Raw pasted text for the AI-assisted bulk import. */
  const [bulkText, setBulkText] = useState('');
  /** True while any of the three network operations is running; disables action buttons. */
  const [uploading, setUploading] = useState(false);
  /** Result banner shown under the bulk text box. */
  const [bulkResult, setBulkResult] = useState<{success: boolean; message: string} | null>(null);
  /** Result banner shown under the single upload form. */
  const [uploadResult, setUploadResult] = useState<{success: boolean; message: string} | null>(null);
  
  // State for bulk upload and preview editing.
  /** Chunks returned by /preview and editable in the confirmation table. */
  const [previewChunks, setPreviewChunks] = useState<PreviewChunk[]>([]);
  /** Toggles between the paste view and the editable preview table. */
  const [showPreview, setShowPreview] = useState(false);
  /** Coarse 0-100 progress used only for visual feedback during long AI calls. */
  const [progress, setProgress] = useState(0);
  /** Caption paired with `progress`. */
  const [progressStatus, setProgressStatus] = useState('');
  /** Row currently in edit mode, or null when the table is read-only. */
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  /** Closed enumerations shared by the form and the editable table. */
  const entityTypes = ['非遗项目', '传承人', '节日', '地点', '技艺', '其他'];
  const topicTags = ['定义概述', '历史渊源', '工艺流程', '文化价值', '代表作品', '传承人信息', '地域特色', '其他'];

  /**
   * Reload the chunk list whenever the modal opens or the browse tab becomes active.
   * Deliberately not fetching on every keystroke: filtering is done in memory below.
   */
  useEffect(() => {
    if (isOpen && activeTab === 'browse') {
      fetchKnowledge();
    }
  }, [isOpen, activeTab]);

  /**
   * Load stored chunks.
   * On failure the list is cleared rather than left stale, and the error is logged so a
   * missing backend is visible in the console while the UI keeps working.
   */
  const fetchKnowledge = async () => {
    setLoading(true);
    try {
      const response = await fetch('/knowledge-base/chunks');
      const data = await response.json();
      setKnowledgeChunks(data.items || []);
    } catch (error) {
      console.error('获取知识库失败:', error);
      setKnowledgeChunks([]);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Submit one structured chunk for server-side embedding and persistence.
   * Required fields are `source_entity` and `embedding_text`; the `required` attributes on the
   * inputs enforce this, and the early return mirrors that guard for programmatic submits.
   * On success the form is reset and the modal switches to browse after a short delay so the
   * user can read the result banner first.
   */
  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadForm.source_entity || !uploadForm.embedding_text) return;

    setUploading(true);
    setUploadResult(null);
    try {
      const response = await fetch('/knowledge-base/single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(uploadForm)
      });
      
      const data = await response.json();
      setUploadResult({
        success: data.success,
        message: data.message
      });
      
      if (data.success) {
        setUploadForm({
          source_entity: '',
          entity_type: '非遗项目',
          topic_tag: '定义概述',
          embedding_text: '',
          relation_desc: '',
          source_url: ''
        });
        setTimeout(() => {
          setActiveTab('browse');
          fetchKnowledge();
        }, 1500);
      }
    } catch (error) {
      // Network or JSON-parse failure: show a localised message instead of throwing.
      console.error('上传失败:', error);
      setUploadResult({
        success: false,
        message: '上传失败，请稍后重试'
      });
    } finally {
      setUploading(false);
    }
  };

  /**
   * Preview structured extraction before saving.
   * This call is read-only on the server: it asks the LLM to split the pasted text into
   * chunk objects. Nothing is written to the database until handleConfirmUpload succeeds.
   *
   * The progress values are hand-picked milestones rather than server-reported events,
   * because /preview is a single blocking request.
   */
  const handlePreview = async () => {
    if (!bulkText.trim()) return;
    
    setUploading(true);
    setProgress(10);
    setProgressStatus('正在发送文本给AI...');
    
    try {
      setProgress(20);
      setProgressStatus('AI正在识别数据条数...');
      
      const response = await fetch('/knowledge-base/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: bulkText })
      });
      
      setProgress(60);
      setProgressStatus('AI正在整理知识切片...');
      
      const data = await response.json();
      
      setProgress(90);
      
      // An empty chunk list means the extraction produced nothing usable; stay on the paste
      // view and surface the server message so the user can fix the input.
      if (data.success && data.chunks && data.chunks.length > 0) {
        setProgressStatus(`成功识别 ${data.data_count} 条数据，生成 ${data.chunks.length} 个知识切片`);
        setPreviewChunks(data.chunks);
        setShowPreview(true);
      } else {
        setProgressStatus('提取失败');
        setBulkResult({
          success: false,
          message: data.message || '未能提取知识切片，请检查文本格式'
        });
      }
      
      setProgress(100);
      
    } catch (error) {
      console.error('预览失败:', error);
      setBulkResult({
        success: false,
        message: '预览失败：' + (error instanceof Error ? error.message : '请稍后重试')
      });
    } finally {
      // Reset the bar after a short pause so the user can read the final percentage.
      setUploading(false);
      setTimeout(() => {
        setProgress(0);
        setProgressStatus('');
      }, 1500);
    }
  };

  /**
   * Edit a previewed knowledge chunk in place.
   * A shallow copy of the array plus a spread of the edited row gives React a new identity
   * for both levels, which is what makes the table re-render.
   */
  const handleEditChunk = (index: number, field: string, value: string) => {
    const newChunks = [...previewChunks];
    newChunks[index] = { ...newChunks[index], [field]: value };
    setPreviewChunks(newChunks);
  };

  /** Remove a chunk from the preview by position; it is never sent to the server. */
  const handleDeleteChunk = (index: number) => {
    const newChunks = previewChunks.filter((_, i) => i !== index);
    setPreviewChunks(newChunks);
  };

  /**
   * Confirm and upload the reviewed chunks.
   * This is the only bulk path that writes to the database: the edited preview array is
   * posted verbatim, so whatever the user changed is exactly what gets embedded.
   * Progress is again a coarse client-side estimate; the success branch clears the staging
   * state and returns to browse so the new rows are visible immediately.
   */
  const handleConfirmUpload = async () => {
    if (previewChunks.length === 0) return;
    
    setUploading(true);
    setProgress(10);
    setProgressStatus('正在生成向量嵌入...');
    
    try {
      setProgress(30);
      setProgressStatus('正在保存到数据库...');
      
      const response = await fetch('/knowledge-base/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chunks: previewChunks })
      });
      
      setProgress(80);
      
      const data = await response.json();
      
      setProgress(100);
      setProgressStatus(data.message);
      
      if (data.success) {
        setBulkResult({
          success: true,
          message: data.message
        });
        setTimeout(() => {
          setPreviewChunks([]);
          setShowPreview(false);
          setBulkText('');
          setActiveTab('browse');
          fetchKnowledge();
        }, 1500);
      }
    } catch (error) {
      console.error('确认上传失败:', error);
      setBulkResult({
        success: false,
        message: '上传失败，请稍后重试'
      });
    } finally {
      setUploading(false);
      setTimeout(() => {
        setProgress(0);
        setProgressStatus('');
      }, 1000);
    }
  };

  /**
   * Client-side filter over the loaded chunks.
   * Matching is case-sensitive `includes` across the entity name, the vectorised text, and
   * the topic tag; with the dataset sizes here a full scan is cheaper than an index.
   */
  const filteredChunks = knowledgeChunks.filter(item =>
    item.source_entity.includes(searchQuery) ||
    item.embedding_text.includes(searchQuery) ||
    item.topic_tag.includes(searchQuery)
  );

  if (!isOpen) return null;

  return (
    // Fixed full-screen backdrop; the dialog is centred and capped at 85% of the viewport
    // height, with only the inner content area scrolling so the header and tabs stay put.
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-lg w-full max-w-5xl max-h-[85vh] flex flex-col">
        {/* Modal header. */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Book className="w-6 h-6" />
            羌族文化知识库
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation tabs. */}
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => setActiveTab('browse')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'browse'
                ? 'text-qiangRed border-b-2 border-qiangRed'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            浏览知识
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'upload'
                ? 'text-qiangRed border-b-2 border-qiangRed'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            上传知识
          </button>
          <button
            onClick={() => setActiveTab('bulk')}
            className={`px-6 py-3 text-sm font-medium transition-colors flex items-center gap-1 ${
              activeTab === 'bulk'
                ? 'text-qiangRed border-b-2 border-qiangRed'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            批量上传
          </button>
        </div>

        {/* Tab content. */}
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === 'browse' ? (
            <>
              {/* Search input. */}
              <div className="mb-4 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="搜索知识..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-gray-800 text-white rounded-lg pl-10 pr-4 py-2 focus:outline-none focus:ring-2 focus:ring-qiangRed"
                />
              </div>

              {/* Knowledge list. */}
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-qiangRed" />
                </div>
              ) : filteredChunks.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <Book className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>暂无知识数据</p>
                  <p className="text-sm mt-2">点击"批量上传"添加羌族文化知识</p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {filteredChunks.map((item) => (
                    <div
                      key={item.chunk_id}
                      className="bg-gray-800 rounded-lg p-4 hover:bg-gray-750 transition-colors"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="font-semibold text-white">{item.source_entity}</h3>
                        <div className="flex gap-2">
                          <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-1 rounded">
                            {item.entity_type}
                          </span>
                          <span className="text-xs bg-qiangRed/20 text-qiangRed px-2 py-1 rounded">
                            {item.topic_tag}
                          </span>
                        </div>
                      </div>
                      <p className="text-gray-400 text-sm line-clamp-3">{item.embedding_text}</p>
                      {item.source_url && (
                        <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:underline mt-2 block">
                          来源: {item.source_url}
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : activeTab === 'upload' ? (
            /* Single-chunk upload form. */
            <form onSubmit={handleUpload} className="max-w-2xl mx-auto">
              <div className="space-y-4">
                <div className="bg-gray-800 rounded-lg p-4 mb-4">
                  <p className="text-gray-400 text-sm">
                    填写知识切片信息，数据将存入向量数据库，支持语义检索。
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      主体名称 <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={uploadForm.source_entity}
                      onChange={(e) => setUploadForm({ ...uploadForm, source_entity: e.target.value })}
                      placeholder="如：羌族刺绣、李兴秀"
                      className="w-full bg-gray-800 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-qiangRed"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      实体类型
                    </label>
                    <select
                      value={uploadForm.entity_type}
                      onChange={(e) => setUploadForm({ ...uploadForm, entity_type: e.target.value })}
                      className="w-full bg-gray-800 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-qiangRed"
                    >
                      {entityTypes.map((type) => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    主题标签
                  </label>
                  <select
                    value={uploadForm.topic_tag}
                    onChange={(e) => setUploadForm({ ...uploadForm, topic_tag: e.target.value })}
                    className="w-full bg-gray-800 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-qiangRed"
                  >
                    {topicTags.map((tag) => (
                      <option key={tag} value={tag}>{tag}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    向量化文本 <span className="text-red-400">*</span>
                  </label>
                  <textarea
                    value={uploadForm.embedding_text}
                    onChange={(e) => setUploadForm({ ...uploadForm, embedding_text: e.target.value })}
                    placeholder="语义完整的描述，必须包含主体名称。如：羌族刺绣是流行于四川省阿坝州羌族地区的一种传统民间工艺，主要用于装饰服饰和鞋垫，具有极高的艺术价值。"
                    rows={5}
                    className="w-full bg-gray-800 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-qiangRed resize-none"
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">提示：文本需语义完整，包含"谁/什么"在"什么方面"怎么样</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    关联关系
                  </label>
                  <input
                    type="text"
                    value={uploadForm.relation_desc}
                    onChange={(e) => setUploadForm({ ...uploadForm, relation_desc: e.target.value })}
                    placeholder="如：地区：阿坝州；传承人：李兴秀；级别：国家级"
                    className="w-full bg-gray-800 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-qiangRed"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    来源网址 <span className="text-gray-500">(选填)</span>
                  </label>
                  <input
                    type="url"
                    value={uploadForm.source_url}
                    onChange={(e) => setUploadForm({ ...uploadForm, source_url: e.target.value })}
                    placeholder="如：https://example.com/article/123"
                    className="w-full bg-gray-800 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-qiangRed"
                  />
                  <p className="text-xs text-gray-500 mt-1">如有原始数据来源网址，请填写，将在对话中展示</p>
                </div>

                {uploadResult && (
                  <div className={`p-4 rounded-lg ${uploadResult.success ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    {uploadResult.message}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={uploading}
                  className="w-full bg-qiangRed hover:bg-qiangRed/80 disabled:bg-gray-600 text-white py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      上传中...
                    </>
                  ) : (
                    <>
                      <Upload className="w-5 h-5" />
                      上传知识切片
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : (
            /* Bulk upload. */
            <div className="max-w-4xl mx-auto">
              {!showPreview ? (
                /* Text input view. */
                <div className="space-y-4">
                  <div className="bg-gray-800 rounded-lg p-4 mb-4">
                    <div className="flex items-center gap-2 text-yellow-400 mb-2">
                      <Sparkles className="w-5 h-5" />
                      <span className="font-medium">AI智能整理</span>
                    </div>
                    <p className="text-gray-400 text-sm">
                      粘贴大段文字内容，AI将自动识别实体、提取关键信息，并整理成结构化的知识切片。
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      <FileText className="w-4 h-4 inline mr-1" />
                      粘贴文本内容
                    </label>
                    <textarea
                      value={bulkText}
                      onChange={(e) => setBulkText(e.target.value)}
                      placeholder="请粘贴大段文字内容..."
                      rows={12}
                      className="w-full bg-gray-800 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-qiangRed resize-none"
                    />
                  </div>

                  {bulkResult && (
                    <div className={`p-4 rounded-lg ${bulkResult.success ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                      {bulkResult.message}
                    </div>
                  )}

                  <button
                    onClick={handlePreview}
                    disabled={uploading || !bulkText.trim()}
                    className="w-full bg-qiangRed hover:bg-qiangRed/80 disabled:bg-gray-600 text-white py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        正在整理...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-5 h-5" />
                        智能整理预览
                      </>
                    )}
                  </button>
                </div>
              ) : (
                /* Preview and edit view. */
                <div className="space-y-4">
                  {/* Progress bar driven by the hand-set milestone values rather than events. */}
                  {progress > 0 && (
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-gray-400 mb-1">
                        <span>{progressStatus}</span>
                        <span>{progress}%</span>
                      </div>
                      <div className="w-full bg-gray-700 rounded-full h-2">
                        <div 
                          className="bg-qiangRed h-2 rounded-full transition-all duration-300"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-white">
                      整理结果 ({previewChunks.length} 个知识切片)
                    </h3>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setShowPreview(false);
                          setPreviewChunks([]);
                        }}
                        className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                      >
                        返回修改
                      </button>
                      <button
                        onClick={handleConfirmUpload}
                        disabled={uploading || previewChunks.length === 0}
                        className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white rounded-lg transition-colors flex items-center gap-2"
                      >
                        {uploading ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            上传中...
                          </>
                        ) : (
                          <>
                            <Check className="w-4 h-4" />
                            确认上传
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Editable chunk table. */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-800 text-gray-300">
                        <tr>
                          <th className="px-3 py-2 text-left">主体名称</th>
                          <th className="px-3 py-2 text-left">类型</th>
                          <th className="px-3 py-2 text-left">标签</th>
                          <th className="px-3 py-2 text-left">向量化文本</th>
                          <th className="px-3 py-2 text-left">关联</th>
                          <th className="px-3 py-2 text-left">来源</th>
                          <th className="px-3 py-2 text-center">操作</th>
                        </tr>
                      </thead>
                      <tbody className="text-gray-400">
                        {previewChunks.map((chunk, index) => (
                          <tr key={index} className="border-b border-gray-700 hover:bg-gray-800/50">
                            <td className="px-3 py-2">
                              {editingIndex === index ? (
                                <input
                                  type="text"
                                  value={chunk.source_entity}
                                  onChange={(e) => handleEditChunk(index, 'source_entity', e.target.value)}
                                  className="w-full bg-gray-700 text-white px-2 py-1 rounded"
                                />
                              ) : (
                                chunk.source_entity
                              )}
                            </td>
                            <td className="px-3 py-2">
                              {editingIndex === index ? (
                                <select
                                  value={chunk.entity_type}
                                  onChange={(e) => handleEditChunk(index, 'entity_type', e.target.value)}
                                  className="bg-gray-700 text-white px-2 py-1 rounded"
                                >
                                  {entityTypes.map((t) => <option key={t} value={t}>{t}</option>)}
                                </select>
                              ) : (
                                <span className="bg-blue-500/20 text-blue-400 px-2 py-1 rounded text-xs">
                                  {chunk.entity_type}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2">
                              {editingIndex === index ? (
                                <select
                                  value={chunk.topic_tag}
                                  onChange={(e) => handleEditChunk(index, 'topic_tag', e.target.value)}
                                  className="bg-gray-700 text-white px-2 py-1 rounded"
                                >
                                  {topicTags.map((t) => <option key={t} value={t}>{t}</option>)}
                                </select>
                              ) : (
                                <span className="bg-qiangRed/20 text-qiangRed px-2 py-1 rounded text-xs">
                                  {chunk.topic_tag}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2 max-w-xs">
                              {editingIndex === index ? (
                                <textarea
                                  value={chunk.embedding_text}
                                  onChange={(e) => handleEditChunk(index, 'embedding_text', e.target.value)}
                                  className="w-full bg-gray-700 text-white px-2 py-1 rounded text-xs"
                                  rows={3}
                                />
                              ) : (
                                <p className="text-xs line-clamp-3">{chunk.embedding_text}</p>
                              )}
                            </td>
                            <td className="px-3 py-2">
                              {editingIndex === index ? (
                                <input
                                  type="text"
                                  value={chunk.relation_desc}
                                  onChange={(e) => handleEditChunk(index, 'relation_desc', e.target.value)}
                                  className="w-full bg-gray-700 text-white px-2 py-1 rounded text-xs"
                                />
                              ) : (
                                <span className="text-xs">{chunk.relation_desc || '-'}</span>
                              )}
                            </td>
                            <td className="px-3 py-2">
                              {editingIndex === index ? (
                                <input
                                  type="text"
                                  value={chunk.source_url}
                                  onChange={(e) => handleEditChunk(index, 'source_url', e.target.value)}
                                  className="w-full bg-gray-700 text-white px-2 py-1 rounded text-xs"
                                  placeholder="来源网址"
                                />
                              ) : (
                                <span className="text-xs text-blue-400">{chunk.source_url || '-'}</span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <div className="flex gap-1 justify-center">
                                <button
                                  onClick={() => setEditingIndex(editingIndex === index ? null : index)}
                                  className="p-1 hover:bg-gray-600 rounded"
                                >
                                  <Edit2 className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => handleDeleteChunk(index)}
                                  className="p-1 hover:bg-red-600 rounded"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBaseModal;
