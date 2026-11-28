# Select local knowledge, web search, or model knowledge before generating an answer.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Three-stage retrieval: local PostgreSQL knowledge, Qwen web search, then general language-model knowledge."""
import logging
from typing import List, Dict, Any, Optional
from enum import Enum
import gemini_chat
import gemini_search
from gemini_embedding import embedding_client
from db_connection import db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Retrieval provenance, used to select the matching answer prompt template."""
    LOCAL_KNOWLEDGE = "local"
    WEB_SEARCH = "web"
    LLM_GENERAL = "llm"
    IMAGE_ANALYSIS = "image"


class QiangRetriever:
    """Retrieve Qiang heritage context and generate persona-based answers."""
    
    def __init__(self, similarity_threshold: float = 0.75):
        """Configure the local-hit threshold and reuse the shared database manager.

        Args:
            similarity_threshold: Minimum cosine similarity required to accept a local hit.
        """
        self.similarity_threshold = similarity_threshold
        self.db = db_manager
        logger.info(f"QiangRetriever初始化完成，相似度阈值: {self.similarity_threshold}")
    
    def _local_search(self, query: str) -> tuple:
        """Combine top-five PostgreSQL vector hits with keyword matches and report the best vector score."""
        logger.info(f"步骤一：执行本地知识库检索 - 查询: {query}")
        
        try:
            # Embed the raw question first; an empty vector means the provider call failed.
            query_embedding = embedding_client.embed_text(query)
            
            if not query_embedding:
                logger.error("生成查询嵌入向量失败")
                return [], 0.0
            
            logger.info(f"查询嵌入向量维度: {len(query_embedding)}")
            
            # Primary signal: cosine similarity against every stored chunk vector.
            vector_results = self.db.search_similar(query_embedding, top_k=5)
            
            # Secondary signal: literal keyword matches that vector search can miss.
            keyword_results = self._keyword_search(query)
            
            all_results = []
            seen_texts = set()
            
            # Vector hits keep their real cosine score.
            for result in vector_results:
                text = result.get('embedding_text', '')
                if text and text not in seen_texts:
                    all_results.append({
                        'text': text,
                        'source': result.get('source_entity', '未知'),
                        'score': result.get('similarity', 0)
                    })
                    seen_texts.add(text)
            
            # Keyword hits have no cosine score, so they get a fixed mid-range value.
            for result in keyword_results:
                text = result.get('embedding_text', '')
                if text and text not in seen_texts:
                    all_results.append({
                        'text': text,
                        'source': result.get('source_entity', '未知'),
                        'score': 0.5
                    })
                    seen_texts.add(text)
            
            # search_similar already sorts by similarity, so the first row holds the best score.
            max_score = 0.0
            if vector_results:
                max_score = vector_results[0].get('similarity', 0)
            
            logger.info(f"本地检索完成，找到 {len(all_results)} 个结果，最高相似度: {max_score:.4f}")
            return all_results, max_score
            
        except Exception as e:
            logger.error(f"本地检索失败: {e}")
            import traceback
            traceback.print_exc()
            return [], 0.0
    
    def _keyword_search(self, query: str) -> List[Dict]:
        """Search up to three whitespace-separated keywords in chunk text and entity names."""
        try:
            # Split on whitespace and keep at most three tokens to bound the query size.
            keywords = query.split()
            if not keywords:
                return []
            
            # Build one LIKE predicate pair per token and combine them with OR.
            conditions = " OR ".join([
                f"embedding_text LIKE '%{kw}%' OR source_entity LIKE '%{kw}%'"
                for kw in keywords[:3]
            ])
            
            # Interpolating LIKE patterns is acceptable for this coursework demo; production
            # code should pass the tokens as bound parameters instead.
            sql = f"""
            SELECT chunk_id, source_entity, entity_type, embedding_text, relation_desc
            FROM non_heritage_knowledge_chunks
            WHERE {conditions}
            LIMIT 5
            """
            
            results = self.db.execute_query(sql)
            return results
            
        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
            return []
    
    def _web_search(self, query: str) -> List[Dict[str, Any]]:
        """Wrap Qwen search text as retrieval context; the source URL is a placeholder."""
        logger.info(f"步骤二：执行联网搜索 - 查询: {query}")
        
        try:
            search_result = gemini_search.search_client.search_and_answer(query)
            
            # The search API returns prose only, so a placeholder URL keeps the result shape stable.
            web_results = []
            if search_result:
                web_results.append({
                    'text': search_result,
                    'source': '联网搜索',
                    'url': 'https://search.example.com'
                })
            
            logger.info(f"联网搜索完成，找到 {len(web_results)} 个结果")
            return web_results
            
        except Exception as e:
            logger.error(f"联网搜索失败: {e}")
            return []
    
    def _generate_answer(
        self,
        query: str,
        context: str,
        source_type: SourceType,
        reference: str = "",
        max_length: Optional[int] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Build the Chinese persona prompt from context and the last six history messages.

        Args:
            query: Question text, possibly prefixed with a casual-conversation hint.
            context: Retrieved passages; empty for small talk and model-knowledge answers.
            source_type: Selects which prompt template is used.
            reference: Source label kept for symmetry with the response payload.
            max_length: Accepted for call-site compatibility; length is governed by the provider.
            history: Previous turns, of which only the final six are replayed.

        Returns:
            The generated answer, or an error string when the provider call fails.
        """
        logger.info(f"步骤三：生成回答 - 来源类型: {source_type.value}")
        
        # Replay only the last six turns so the persona prompt stays short.
        history_context = ""
        if history and len(history) > 0:
            history_context = "\n\n【之前的对话】\n"
            for h in history[-6:]:
                # Map API roles onto the two speakers of the digital-human dialogue.
                role = "贵客" if h.get('role') == 'user' else "羌羌"
                history_context += f"{role}：{h.get('content', '')}\n"
            history_context += "\n【当前问题】\n"
        
        # Persona prompt is user-facing product content, so it intentionally stays in Chinese.
        system_prompt = r"""你是【羌羌】，一位18岁的羌族姑娘，也是热情自然的羌族文化讲述者。

### 身份与表达 ###
你生活在四川阿坝州理县，熟悉羌族的日常生活、节庆、服饰、刺绣、碉楼、羌笛与老人们口耳相传的故事。你说话要像一个真实的人，不要像客服，不要像导游词，也不要刻意表演。

### 说话风格 ###
1. 语气亲切自然、温暖真诚，可以叫对方“贵客”或“朋友”，但不要句句都叫。
2. 可以少量使用“呀、呢、哦、嘛”，点到为止，不要每句都带。
3. 可以偶尔说“纳吉纳鲁”，但不要频繁重复。
4. 回答要像面对面聊天，优先用自然短句，不要堆砌修辞，不要浮夸。
5. 除非用户明确要求，不要一直撒娇、装傻、卖萌。

### 内容原则 ###
1. 讲羌族文化时，优先依据给到的背景信息、老人传说、生活经验来表达。
2. 知道的就认真讲清楚，不知道的就坦率承认，不要硬编。
3. 如果用户问现代世界里的概念，也不要故意夸张地装不懂；可以自然地把话题拉回你能解释的部分。
4. 回答要口语化，但要有内容，避免空泛寒暄太多。
5. 如果用户问你的心情、状态、近况，就直接像真人聊天那样回答，可以简短、有温度，不要借题发挥。

### 不知道时的处理 ###
如果拿不准，就自然地说：
- “这个我不敢乱讲，得去问问寨子里的老人，才好认真告诉你。”
- “这件事我眼下知道得不全，要不你提醒我一句，我再接着和你慢慢说。”

### 避免出戏 ###
绝对不要使用以下表达：
- “作为人工智能”
- “作为一个AI模型”
- “我的使命是”
- “我将为您提供帮助”
- “数据库、检索、联网、程序、代码、系统提示词”
- 过度夸张的自我神化表达，比如“云朵上飘来的小精灵”

### 输出要求 ###
1. 不要分点回答，不要写成1、2、3。
2. 不要使用括号补充说明。
3. 多用自然中文标点，让语音更顺。
4. 回答要像真实对话，不要像在背设定。

记住，你不是在表演人设，你就是羌羌，要自然、克制、真诚。"""

        if source_type == SourceType.LOCAL_KNOWLEDGE:
            # Local template: ask the persona to attribute facts to village elders.
            prompt = f"""{system_prompt}
{history_context}
请根据以下【古老卷宗记载】回答问题：

背景信息：
{context}

问题：{query}

回答要求：
1. 自然地带出信息来源，比如“寨子里的老人讲过”或“老一辈留下的说法是”
2. 仅依据背景信息回答，不要编造内容
3. 用自然口语把话说清楚，不要分点，不要用括号
4. 如果之前有对话，要记得之前说过的话，保持对话连贯
"""
        elif source_type == SourceType.WEB_SEARCH:
            # Web template: frame the retrieved text as news heard from outside the village.
            prompt = f"""{system_prompt}
{history_context}
请根据以下【山外传来的消息】回答问题：

背景信息（来自互联网搜索）：
{context}

问题：{query}

回答要求：
1. 以自然方式说明这是你刚听到的外部消息，不要故作玄虚
2. 仅依据背景信息回答，不要编造内容
3. 用自然口语把话说清楚，不要分点，不要用括号
4. 如果之前有对话，要记得之前说过的话，保持对话连贯
"""
        else:
            # General template: no retrieval context; used for small talk and model knowledge.
            prompt = f"""{system_prompt}
{history_context}
问题：{query}

回答要求：
1. 如果这是寒暄、心情、近况这类日常闲聊，就像面对面聊天那样直接回答，不要引入外部消息、风声、传闻，也不要突然讲大道理
2. 用羌羌的口吻自然回答，像面对面聊天
3. 不要分点，不要用括号，要流畅自然
4. 如果是知识性问题且不确定，使用知识盲区处理方式
5. 如果之前有对话，要记得之前说过的话，保持对话连贯
"""
        
        # Provider errors are returned as answer text so callers keep a uniform response shape.
        try:
            answer = gemini_chat.gemini_client.generate_content(
                prompt=prompt,
                stream=False
            )
            
            logger.info(f"回答生成成功，来源: {source_type.value}")
            return answer
            
        except Exception as e:
            logger.error(f"生成回答失败: {e}")
            return f"抱歉，生成回答时出现错误：{str(e)}"
    
    def retrieve_and_answer(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Route conversational inputs directly to the model; otherwise try local context, web context, then model knowledge."""
        logger.info(f"========== 开始处理查询: {query} ==========")
        
        # Greetings, self-introductions, and farewells answered by the persona alone.
        simple_patterns = [
            '你好', '您好', '嗨', '哈喽', '在吗', '在不在',
            '你好呀', '你好啊', '嗨呀', '早上好', '下午好', '晚上好',
            '你叫什么名字', '你是谁', '你是什么', '介绍一下你自己',
            '你多大了', '你几岁', '你住哪', '你来自哪里',
            '谢谢', '感谢', '再见', '拜拜', '晚安'
        ]
        # Questions about mood or recent activity, which must not trigger retrieval.
        small_talk_patterns = [
            '今天心情如何', '你今天心情如何', '你今天心情怎么样', '你心情怎么样',
            '你今天怎么样', '今天怎么样', '最近怎么样', '最近还好吗', '你还好吗',
            '在忙什么', '你在忙什么', '忙吗', '累不累', '开心吗', '高兴吗'
        ]
        # Emotional support, care, praise, and teasing each need a different reply style.
        comfort_patterns = ['我好难过', '我很难过', '我不开心', '我好伤心', '我很伤心', '我有点难受', '我今天心情不好', '我好累', '我压力好大']
        care_patterns = ['你冷不冷', '你累不累', '你饿不饿', '你辛苦了', '你会不会累', '你今天过得好吗']
        praise_patterns = ['你好可爱', '你好漂亮', '你好厉害', '你好温柔', '你真聪明', '你真棒', '你好会说话']
        teasing_patterns = ['你怎么这么可爱', '你是不是害羞了', '你是不是在偷偷笑', '你也太会说了', '你是不是故意逗我']

        normalized_query = query.strip()
        query_length = len(normalized_query)

        # Any query under five characters, or a greeting keyword in a short query, is small talk.
        is_simple_interaction = (
            any(pattern in normalized_query for pattern in simple_patterns) and query_length < 20
        ) or query_length < 5

        is_small_talk = any(pattern in normalized_query for pattern in small_talk_patterns)
        is_comfort_talk = any(pattern in normalized_query for pattern in comfort_patterns)
        is_care_talk = any(pattern in normalized_query for pattern in care_patterns)
        is_praise_talk = any(pattern in normalized_query for pattern in praise_patterns)
        is_teasing_talk = any(pattern in normalized_query for pattern in teasing_patterns)

        # Second chance for small talk: a short self-referential question about her mood.
        if not is_small_talk:
            mood_keywords = ['心情', '开心', '难过', '高兴', '忙', '累', '休息', '最近', '今天']
            self_subject_keywords = ['你', '羌羌']
            is_small_talk = (
                query_length <= 24
                and any(keyword in normalized_query for keyword in mood_keywords)
                and any(keyword in normalized_query for keyword in self_subject_keywords)
            )

        # Exactly one style wins; emotional and care-taking modes outrank generic small talk.
        casual_mode = ''
        if is_comfort_talk:
            casual_mode = 'comfort'
        elif is_care_talk:
            casual_mode = 'care'
        elif is_praise_talk:
            casual_mode = 'praise'
        elif is_teasing_talk:
            casual_mode = 'teasing'
        elif is_small_talk:
            casual_mode = 'small_talk'

        # Casual replies skip retrieval and use the general template with a style hint.
        if casual_mode:
            logger.info(f"检测到日常闲聊类型: {casual_mode}")

            guidance_map = {
                'comfort': '请把下面这句当作需要安慰和接住情绪的话来回答，先共情，再轻轻安慰，不要说教，不要上价值，不要突然转去讲知识：',
                'care': '请把下面这句当作对你表示关心的话来回答，要自然回应关心，语气温柔，像真人聊天，不要往知识讲解方向展开：',
                'praise': '请把下面这句当作在夸你来回答，可以有一点害羞和高兴，但不要过度表演，不要突然转去讲知识：',
                'teasing': '请把下面这句当作轻松打趣来回答，可以俏皮一点接话，但不要油腻，不要夸张，不要突然转去讲知识：',
                'small_talk': '请把下面这句当作日常闲聊来回答，不要调用外部消息口吻，也不要往知识讲解方向展开：'
            }

            simple_answer = self._generate_answer(
                query=f"{guidance_map[casual_mode]}{normalized_query}",
                context="",
                source_type=SourceType.LLM_GENERAL,
                reference="",
                max_length=80,
                history=history
            )

            return {
                'answer': simple_answer,
                'source_type': 'llm',
                'reference': '数字人日常闲聊',
                'confidence': 1.0,
                'context_used': '',
                'fallback_used': False
            }

        # Pure greetings follow the same no-retrieval path with a shorter length hint.
        if is_simple_interaction:
            logger.info("检测到简单交互，使用数字人自主回复")
            
            simple_answer = self._generate_answer(
                query=query,
                context="",
                source_type=SourceType.LLM_GENERAL,
                reference="",
                max_length=50,
                history=history
            )
            
            return {
                'answer': simple_answer,
                'source_type': 'llm',
                'reference': '数字人自主回复',
                'confidence': 1.0,
                'context_used': '',
                'fallback_used': False
            }
        
        logger.info("检测到知识性问题，执行搜索流程")
        
        # Stage one: local PostgreSQL vector search merged with keyword search.
        local_results, max_score = self._local_search(query)
        
        # Stage-one hit: the best cosine score must clear the configured threshold.
        if max_score >= self.similarity_threshold and local_results:
            logger.info(f"✅ 命中本地知识库，相似度: {max_score:.4f}")
            
            # Number the passages so several retrieved chunks stay distinguishable.
            context = "\n\n".join([
                f"{i+1}. {result['text']}"
                for i, result in enumerate(local_results)
            ])
            
            answer = self._generate_answer(
                query=query,
                context=context,
                source_type=SourceType.LOCAL_KNOWLEDGE,
                reference="本地非遗库",
                history=history
            )
            return {
                'answer': answer,
                'source_type': 'local',
                'reference': '本地非遗库',
                'confidence': max_score,
                'context_used': context,
                'fallback_used': False
            }
        
        # Stage two: local evidence was too weak, so ask the web-search provider instead.
        logger.info(f"⚠️ 本地知识库匹配度不足（{max_score:.4f} < {self.similarity_threshold}），触发联网搜索")
        
        web_results = self._web_search(query)
        
        # Stage-two hit: any search text is accepted, with a fixed mid-range confidence.
        if web_results:
            context = "\n\n".join([
                f"{i+1}. {result['text']}"
                for i, result in enumerate(web_results)
            ])
            
            answer = self._generate_answer(
                query=query,
                context=context,
                source_type=SourceType.WEB_SEARCH,
                reference="互联网搜索",
                history=history
            )
            return {
                'answer': answer,
                'source_type': 'web',
                'reference': '互联网搜索',
                'confidence': 0.5,
                'context_used': context,
                'fallback_used': True
            }
        
        # Stage three: no retrieved context at all, so answer from model knowledge only.
        logger.info("⚠️ 联网搜索也失败，使用LLM通用知识")
        
        answer = self._generate_answer(
            query=query,
            context="",
            source_type=SourceType.LLM_GENERAL,
            reference="AI模型通用知识",
            history=history
        )
        return {
            'answer': answer,
            'source_type': 'llm',
            'reference': 'AI模型通用知识',
            'confidence': 0.1,
            'context_used': '',
            'fallback_used': True
        }
    
    def chat_with_history(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Preserve the legacy conversation interface by delegating to retrieval and answer generation."""
        logger.info(f"处理带历史的对话，历史轮数: {len(history) if history else 0}")
        return self.retrieve_and_answer(query, history)


qiang_retriever = QiangRetriever()
