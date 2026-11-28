# HTTP API for chat, speech, knowledge ingestion, and production frontend assets.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""FastAPI endpoints for Qiang heritage chat, simulated streaming, speech, and knowledge management."""
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import base64
import uvicorn
import json
import asyncio
from datetime import datetime

import config
from rag_core import qiang_retriever, SourceType
from gemini_chat import gemini_client
from tts_service import tts_client
from knowledge_processor import knowledge_processor
from db_connection import db_manager

# Configure logging.
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create the FastAPI application.
app = FastAPI(
    title="羌智传承非遗问答系统API",
    description="基于知识图谱的羌智传承非遗问答系统，支持本地知识库、联网搜索和AI通用知识三级回退机制",
    version="1.0.0"
)

# Mount built frontend assets.
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
WELCOME_AUDIO_FILE = FRONTEND_DIST / "welcome.mp3"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    logger.info(f"前端静态文件已挂载: {FRONTEND_DIST}")


# ============================================
# Request and response schemas.
# ============================================

class ChatRequest(BaseModel):
    """Validated chat input with optional history and image data."""
    query: str = Field(..., description="用户问题", min_length=1, max_length=500)
    history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="对话历史，格式为 [{'role': 'user', 'content': '...'}, ...]"
    )
    image_base64: Optional[str] = Field(default=None, description="base64编码图片")
    image_mime_type: Optional[str] = Field(default=None, description="图片MIME类型")
    stream: Optional[bool] = Field(default=False, description="是否使用流式输出")


class ChatResponse(BaseModel):
    """Answer text and retrieval provenance returned to the client."""
    answer: str = Field(..., description="AI生成的回答")
    source_type: str = Field(..., description="来源类型: local/web/llm")
    reference: str = Field(..., description="引用信息")
    confidence: float = Field(..., description="置信度分数 (0-1)")
    fallback_used: bool = Field(..., description="是否使用了回退机制")
    timestamp: str = Field(..., description="响应时间戳")


class HealthResponse(BaseModel):
    """Service health response; does not probe external dependencies."""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="API版本")
    timestamp: str = Field(..., description="检查时间")


class StatsResponse(BaseModel):
    """Process-local query counters."""
    total_queries: int = Field(..., description="总查询次数")
    local_hits: int = Field(..., description="本地知识库命中次数")
    web_searches: int = Field(..., description="联网搜索次数")
    llm_fallbacks: int = Field(..., description="LLM兜底次数")


class TTSRequest(BaseModel):
    """Text input for speech synthesis."""
    text: str = Field(..., description="要合成的文本", min_length=1, max_length=1000)


class TTSResponse(BaseModel):
    """Base64-encoded audio response."""
    audio: str = Field(..., description="base64编码的音频数据")
    format: str = Field(default="mp3", description="音频格式")


class KnowledgeItem(BaseModel):
    """JSON-backed knowledge entry."""
    id: Optional[str] = None
    title: str = Field(..., description="知识标题")
    content: str = Field(..., description="知识内容")
    category: str = Field(default="其他", description="知识分类")
    created_at: Optional[str] = None


class KnowledgeListResponse(BaseModel):
    """Knowledge entries and their total count."""
    items: List[KnowledgeItem] = Field(default=[], description="知识列表")
    total: int = Field(default=0, description="总数")


# ============================================
# Process-local statistics.
# ============================================

class QueryStats:
    """Track query counts by retrieval source for this process."""
    def __init__(self):
        """Start every counter at zero."""
        self.total_queries = 0
        self.local_hits = 0
        self.web_searches = 0
        self.llm_fallbacks = 0
    
    def record_query(self, source_type: str):
        """Increment the total and matching source counter."""
        self.total_queries += 1
        if source_type == 'local':
            self.local_hits += 1
        elif source_type == 'web':
            self.web_searches += 1
        elif source_type == 'llm':
            self.llm_fallbacks += 1


stats = QueryStats()

# Persona instruction used only for image questions; user-facing text stays in Chinese.
IMAGE_ANALYSIS_SYSTEM_PROMPT = """你是羌羌，一位自然、真诚、懂羌族文化的姑娘。用户会上传一张图片给你看。
如果图里和羌族文化、非遗、服饰、建筑、器物、纹样、节庆、刺绣、乐器有关，就优先认真描述你看到的内容，并结合羌族文化角度给出解释。
如果和羌族文化没有明显关系，也要先清楚描述画面内容，再自然回应用户的问题，不要硬往羌族文化上套。
不要分点，不要写成报告，要像面对面聊天那样自然回答。
如果图片里有不确定的地方，要明确说你只是大致判断，不要乱编。"""


def build_image_data_url(image_base64: str, image_mime_type: Optional[str]) -> str:
    """Wrap base64 image bytes in a data URL, defaulting to JPEG when the MIME type is absent."""
    mime_type = image_mime_type or 'image/jpeg'
    return f"data:{mime_type};base64,{image_base64}"


# ============================================
# API endpoints.
# ============================================

@app.get("/", response_class=FileResponse)
async def root():
    """Return the built frontend page when available, otherwise API metadata."""
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "message": "羌智传承非遗问答系统API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Return service status, version, and current timestamp."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.get("/welcome.mp3", response_class=FileResponse)
async def welcome_audio():
    """Serve the welcome audio from the frontend build directory."""
    if WELCOME_AUDIO_FILE.exists():
        return FileResponse(WELCOME_AUDIO_FILE, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="welcome.mp3 not found")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Answer a validated chat request and return answer text with source metadata."""
    try:
        logger.info(f"收到聊天请求: {request.query}")

        if request.image_base64:
            # Vision path bypasses retrieval: the uploaded picture is the grounding context.
            logger.info("检测到图片分析请求")
            image_data_url = build_image_data_url(request.image_base64, request.image_mime_type)
            prompt = f"用户的问题是：{request.query}。请先看图，再结合问题自然回答。"
            answer = gemini_chat.gemini_client.describe_image(
                prompt=prompt,
                image_data_url=image_data_url,
                system_instruction=IMAGE_ANALYSIS_SYSTEM_PROMPT
            )

            response = ChatResponse(
                answer=answer,
                source_type='image',
                reference='图片解析',
                confidence=1.0,
                fallback_used=False,
                timestamp=datetime.now().isoformat()
            )
            logger.info("图片分析请求处理完成")
            return response
        
        # Call the retrieval engine.
        result = qiang_retriever.chat_with_history(
            query=request.query,
            history=request.history
        )
        
        # Record query statistics.
        stats.record_query(result['source_type'])
        
        # Build the response.
        response = ChatResponse(
            answer=result['answer'],
            source_type=result['source_type'],
            reference=result['reference'],
            confidence=result['confidence'],
            fallback_used=result['fallback_used'],
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"聊天请求处理完成，来源类型: {result['source_type']}")
        return response
        
    except Exception as e:
        # Unexpected retrieval or provider failures become HTTP 500 with the original message.
        logger.error(f"处理聊天请求时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Retrieve the complete answer, then emit metadata, character chunks, and completion as SSE."""
    try:
        logger.info(f"收到流式聊天请求: {request.query}")
        
        # Call the retrieval engine.
        result = qiang_retriever.chat_with_history(
            query=request.query,
            history=request.history
        )
        
        # Record query statistics.
        stats.record_query(result['source_type'])
        
        async def generate():
            """Emit answer metadata, individual characters, and a completion timestamp."""
            # Send provenance metadata first.
            metadata = {
                "type": "metadata",
                "source_type": result['source_type'],
                "reference": result['reference'],
                "confidence": result['confidence'],
                "fallback_used": result['fallback_used']
            }
            # Each SSE frame is `data: <json>` plus a blank line, which marks the event boundary.
            yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
            
            # Simulate streaming by sending the completed answer one character at a time.
            answer = result['answer']
            for i, char in enumerate(answer):
                chunk = {
                    "type": "chunk",
                    "content": char,
                    "index": i
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)  # Simulate the typing effect.
            
            # Send the completion event.
            done = {
                "type": "done",
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
        
        logger.info(f"流式聊天请求处理完成，来源类型: {result['source_type']}")
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        # Errors raised before streaming begins are still reported as a normal HTTP 500.
        logger.error(f"处理流式聊天请求时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Return the current process-local query statistics."""
    return StatsResponse(
        total_queries=stats.total_queries,
        local_hits=stats.local_hits,
        web_searches=stats.web_searches,
        llm_fallbacks=stats.llm_fallbacks
    )


@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(request: TTSRequest):
    """Synthesize request.text and return base64-encoded MP3 audio; report synthesis failure as HTTP 500."""
    try:
        logger.info(f"收到TTS请求，文本长度: {len(request.text)}")
        
        audio_base64 = tts_client.synthesize_to_base64(request.text)
        
        if not audio_base64:
            raise HTTPException(status_code=500, detail="语音合成失败")
        
        return TTSResponse(
            audio=audio_base64,
            format="mp3"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理TTS请求时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset-stats")
async def reset_stats():
    """Reset all query counters and return a confirmation message."""
    stats.total_queries = 0
    stats.local_hits = 0
    stats.web_searches = 0
    stats.llm_fallbacks = 0
    
    logger.info("统计信息已重置")
    return {"message": "统计信息已重置"}


KNOWLEDGE_FILE = Path(__file__).parent.parent / "data" / "knowledge_base.json"

def load_knowledge() -> List[Dict]:
    """Read the JSON knowledge file; return an empty list when the file does not exist yet."""
    if KNOWLEDGE_FILE.exists():
        with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_knowledge(items: List[Dict]):
    """Write all knowledge entries as readable UTF-8 JSON, creating the data directory first."""
    KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


@app.get("/knowledge-base", response_model=KnowledgeListResponse)
async def get_knowledge_base():
    """Read JSON-backed knowledge entries and return the list with its count."""
    items = load_knowledge()
    return KnowledgeListResponse(
        items=[KnowledgeItem(**item) for item in items],
        total=len(items)
    )


@app.post("/knowledge-base", response_model=KnowledgeItem)
async def add_knowledge(item: KnowledgeItem):
    """Assign an ID and creation time to item, persist it in JSON, and return the stored entry."""
    items = load_knowledge()
    
    new_item = {
        "id": f"kb_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(items)}",
        "title": item.title,
        "content": item.content,
        "category": item.category,
        "created_at": datetime.now().isoformat()
    }
    
    items.append(new_item)
    save_knowledge(items)
    
    logger.info(f"添加知识: {item.title}")
    return KnowledgeItem(**new_item)


class BulkUploadRequest(BaseModel):
    """Unstructured text submitted for bulk extraction."""
    text: str = Field(..., description="要处理的文本内容", min_length=10)


class SingleUploadRequest(BaseModel):
    """Structured fields for a single knowledge chunk."""
    source_entity: str = Field(..., description="主体名称")
    entity_type: str = Field(default="非遗项目", description="实体类型")
    topic_tag: str = Field(default="定义概述", description="主题标签")
    embedding_text: str = Field(..., description="向量化文本")
    relation_desc: str = Field(default="", description="关联关系")
    source_url: str = Field(default="", description="来源网址")


class SingleUploadResponse(BaseModel):
    """Single-upload status with an optional chunk identifier."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="处理结果消息")
    chunk_id: Optional[str] = Field(default=None, description="知识切片ID")


class BulkUploadResponse(BaseModel):
    """Bulk extraction and persistence counts with optional extracted chunks."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="处理结果消息")
    chunks_count: int = Field(default=0, description="提取的知识切片数量")
    saved_count: int = Field(default=0, description="保存的知识切片数量")
    chunks: Optional[List[Dict[str, Any]]] = Field(default=None, description="提取的知识切片列表")


class PreviewRequest(BaseModel):
    """Text to structure without saving it."""
    text: str = Field(..., description="要处理的文本内容", min_length=10)


class PreviewChunkItem(BaseModel):
    """Editable structured chunk shown in the preview."""
    source_entity: str
    entity_type: str
    topic_tag: str
    embedding_text: str
    relation_desc: str = ""
    source_url: str = ""


class PreviewResponse(BaseModel):
    """Preview result with extracted chunks and their count."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="处理结果消息")
    chunks: List[PreviewChunkItem] = Field(default=[], description="提取的知识切片列表")
    data_count: int = Field(default=0, description="识别出的数据条数")


class ConfirmUploadRequest(BaseModel):
    """User-confirmed chunks to embed and persist."""
    chunks: List[PreviewChunkItem] = Field(..., description="确认上传的知识切片列表")


class ConfirmUploadResponse(BaseModel):
    """Confirmation result and successfully saved count."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="处理结果消息")
    saved_count: int = Field(default=0, description="保存的知识切片数量")


class KnowledgeChunkItem(BaseModel):
    """Stored knowledge chunk with source and timestamp metadata."""
    chunk_id: str
    source_entity: str
    entity_type: str
    topic_tag: str
    embedding_text: str
    relation_desc: Optional[str] = None
    source_url: Optional[str] = None
    created_at: Optional[str] = None


class KnowledgeChunksResponse(BaseModel):
    """Paginated chunk records and total database count."""
    items: List[KnowledgeChunkItem] = Field(default=[], description="知识切片列表")
    total: int = Field(default=0, description="总数")


@app.post("/knowledge-base/bulk", response_model=BulkUploadResponse)
async def bulk_upload_knowledge(request: BulkUploadRequest):
    """Extract structured chunks from request.text, embed and save them, and return processing counts."""
    try:
        logger.info(f"收到批量上传请求，文本长度: {len(request.text)}")
        
        result = knowledge_processor.process_and_save(request.text)
        
        return BulkUploadResponse(
            success=result['success'],
            message=result['message'],
            chunks_count=result['chunks_count'],
            saved_count=result['saved_count'],
            chunks=result.get('chunks')
        )
        
    except Exception as e:
        logger.error(f"批量上传处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge-base/preview", response_model=PreviewResponse)
async def preview_knowledge(request: PreviewRequest):
    """Extract structured chunks without database writes and return an editable preview."""
    try:
        logger.info(f"收到预览请求，文本长度: {len(request.text)}")
        
        chunks = knowledge_processor.process_bulk_text(request.text)
        
        if not chunks:
            return PreviewResponse(
                success=False,
                message="未能从文本中提取知识切片，请检查文本格式或稍后重试",
                chunks=[],
                data_count=0
            )
        
        preview_chunks = [PreviewChunkItem(**chunk) for chunk in chunks]
        
        return PreviewResponse(
            success=True,
            message=f"成功识别并提取 {len(chunks)} 个知识切片",
            chunks=preview_chunks,
            data_count=len(chunks)
        )
        
    except Exception as e:
        logger.error(f"预览处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge-base/confirm", response_model=ConfirmUploadResponse)
async def confirm_upload_knowledge(request: ConfirmUploadRequest):
    """Embed confirmed chunks, save each independently, and report the successful save count."""
    try:
        logger.info(f"收到确认上传请求，切片数量: {len(request.chunks)}")
        
        from embedding_service import embedding_client
        
        saved_count = 0
        # Each chunk is embedded and inserted independently so one failure cannot abort the batch.
        for chunk in request.chunks:
            try:
                chunk_id = f"QX_{datetime.now().strftime('%Y%m%d%H%M%S')}_{knowledge_processor.chunk_counter:04d}"
                knowledge_processor.chunk_counter += 1
                
                embedding = embedding_client.get_embedding(chunk.embedding_text)
                
                success = db_manager.insert_knowledge_chunk(
                    chunk_id=chunk_id,
                    source_entity=chunk.source_entity,
                    entity_type=chunk.entity_type,
                    topic_tag=chunk.topic_tag,
                    embedding_text=chunk.embedding_text,
                    relation_desc=chunk.relation_desc,
                    source_url=chunk.source_url,
                    embedding=embedding
                )
                
                if success:
                    saved_count += 1
                    
            except Exception as e:
                # Failed chunks are logged and skipped; the response counts successful inserts only.
                logger.error(f"保存知识切片失败: {e}")
        
        return ConfirmUploadResponse(
            success=True,
            message=f"成功保存 {saved_count}/{len(request.chunks)} 个知识切片",
            saved_count=saved_count
        )
        
    except Exception as e:
        logger.error(f"确认上传处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge-base/single", response_model=SingleUploadResponse)
async def single_upload_knowledge(request: SingleUploadRequest):
    """Embed one structured request and insert it into the knowledge chunk table."""
    try:
        logger.info(f"收到单条上传请求: {request.source_entity}")
        
        from embedding_service import embedding_client
        
        chunk_id = f"QX_{datetime.now().strftime('%Y%m%d%H%M%S')}_{knowledge_processor.chunk_counter:04d}"
        knowledge_processor.chunk_counter += 1
        
        # Vectorize exactly the text that is stored, so query and insert share one representation.
        embedding = embedding_client.get_embedding(request.embedding_text)
        
        success = db_manager.insert_knowledge_chunk(
            chunk_id=chunk_id,
            source_entity=request.source_entity,
            entity_type=request.entity_type,
            topic_tag=request.topic_tag,
            embedding_text=request.embedding_text,
            relation_desc=request.relation_desc,
            source_url=request.source_url,
            embedding=embedding
        )
        
        if success:
            return SingleUploadResponse(
                success=True,
                message=f"知识切片上传成功：{request.source_entity}",
                chunk_id=chunk_id
            )
        else:
            return SingleUploadResponse(
                success=False,
                message="知识切片上传失败，请稍后重试"
            )
        
    except Exception as e:
        logger.error(f"单条上传处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/knowledge-base/chunks", response_model=KnowledgeChunksResponse)
async def get_knowledge_chunks(limit: int = 50, offset: int = 0):
    """Return stored chunks using limit and offset, together with the unpaginated total."""
    try:
        chunks = db_manager.get_all_chunks(limit=limit, offset=offset)
        # The total spans all rows, so it is counted separately from the paginated page.
        total = db_manager.get_chunk_count()
        
        return KnowledgeChunksResponse(
            items=[KnowledgeChunkItem(**chunk) for chunk in chunks],
            total=total
        )
        
    except Exception as e:
        logger.error(f"获取知识切片失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Initialize the knowledge table during application startup."""
    try:
        # A missing database must not stop the HTTP service from starting.
        db_manager.init_knowledge_table()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化警告: {e}")


# ============================================
# Server entry point.
# ============================================

def start_server():
    """Start Uvicorn with the configured address, port, reload flag, and log level."""
    uvicorn.run(
        "api_server.server:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD,
        log_level=config.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    start_server()
