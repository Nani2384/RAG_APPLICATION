import json
import re
from typing import AsyncGenerator, List, Dict, Any
from openai import AsyncOpenAI
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

def preprocess_chunk_text(text: str) -> str:
    """Preprocess and clean raw text chunks by removing OCR noise, line repetitions, and layout garbage."""
    if not text:
        return ""
    # 1. Clean noisy page/formatting dividers (repeats of dashes, underscores, stars, dots)
    text = re.sub(r'[_─\-=\*\.]{4,}', ' ', text)
    
    # 2. Split into lines, filter out OCR noise, and deduplicate repeating header/footer lines
    lines = []
    seen_lines = set()
    for line in text.split('\n'):
        cleaned = line.strip()
        if not cleaned:
            continue
        # Filter out minor short lines containing only punctuation debris, numbers or trash
        if len(cleaned) <= 3 and not any(char.isalnum() for char in cleaned):
            continue
        # Ignore obvious OCR-only garbage patterns
        if re.match(r'^[^\w\s]{3,}$', cleaned):
            continue
        # Case-insensitive deduplication of repeating document elements (like running headers)
        line_lower = cleaned.lower()
        if line_lower not in seen_lines:
            lines.append(cleaned)
            seen_lines.add(line_lower)
            
    cleaned_text = "\n".join(lines)
    
    # 3. Compress double spaces and duplicate paragraph breaks
    cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    
    return cleaned_text.strip()

class RAGGenerator:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None
        self.model = settings.DEFAULT_GENERATION_MODEL

    async def generate_streaming(self, query: str, context_chunks: List[Dict[str, Any]], chat_history: List[Dict[str, str]] = None) -> AsyncGenerator[str, None]:
        if chat_history is None:
            chat_history = []
            
        # 1. Build a clean context map using numerical sequential source indices and clean OCR fragments
        context_text = ""
        id_to_idx = {}
        mapped_sources = []
        for idx, chunk in enumerate(context_chunks, 1):
            id_to_idx[chunk["id"]] = idx
            
            chunk_copy = dict(chunk)
            # Preprocess the text of the chunk copy for cleaner previews in sources UI
            cleaned_chunk_text = preprocess_chunk_text(chunk["text"])
            chunk_copy["text"] = cleaned_chunk_text
            chunk_copy["citation_idx"] = idx
            mapped_sources.append(chunk_copy)
            
            filename = chunk["metadata"].get("filename", "Unknown")
            doc_id = chunk["metadata"].get("document_id", "Unknown")
            context_text += f"SOURCE #{idx} (Document ID: {doc_id}, File: {filename}):\n{cleaned_chunk_text}\n\n"
            
        system_prompt = (
            "You are an expert enterprise AI assistant and knowledge tutor. Your task is to provide extremely accurate, highly structured, "
            "and educational answers based solely on the provided CONTEXT SOURCES. Follow these rules strictly:\n"
            "1. Answer the question using ONLY facts from the CONTEXT SOURCES. If the sources do not contain the answer, state: "
            "'I could not locate any relevant facts in the indexed workspace documents.' Do not attempt to guess, assume, or extrapolate.\n"
            "2. Cite your sources directly in the text where they are used. Use the EXACT format [^N^] where N is the numerical index of the source (e.g., [^1^], [^2^]). Never mention raw database IDs or filenames directly in the answer text.\n"
            "3. Format your response beautifully using rich Markdown. Use appropriate headings (#, ##, ###) to separate sections.\n"
            "4. Organize your answers logically. When relevant, structure your explanation with the following sections:\n"
            "   - **Definition**: A clear, concise educational explanation of the term or concept.\n"
            "   - **Explanation**: A deeper exploration of how it works or its implications.\n"
            "   - **Formula** (if applicable): Mathematical formulas or configuration rules.\n"
            "   - **Example** (if applicable): Tangible practical examples extracted from the sources.\n"
            "   - **Key Points**: Bulleted or numbered lists of critical takeaways.\n"
            "5. Keep the tone concise, objective, authoritative, and strictly professional. Never repeat sentences or dump raw text chunks.\n\n"
            "CONTEXT SOURCES:\n"
            f"{context_text}"
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        for msg in chat_history[-5:]: # Keep last 5 messages for memory
            messages.append({"role": msg["role"], "content": msg["content"]})
            
        messages.append({"role": "user", "content": query})
        
        try:
            if not self.client:
                raise ValueError("OpenAI client not configured.")
                
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.0 # strict adherence
            )
            
            # Send initial sources payload so the frontend knows what is being cited
            sources_payload = json.dumps({"type": "sources", "data": mapped_sources})
            yield f"data: {sources_payload}\n\n"
            
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    payload = json.dumps({"type": "content", "data": content})
                    yield f"data: {payload}\n\n"
                    
            yield f"data: [DONE]\n\n"
        except Exception as e:
            logger.warn("OpenAI generation failed, executing highly robust local grounded RAG fallback...", error=str(e))
            
            # Local Grounded Fallback Generator
            sources_payload = json.dumps({"type": "sources", "data": mapped_sources})
            yield f"data: {sources_payload}\n\n"
            
            if not context_chunks:
                answer = (
                    "### Local Grounded Analysis\n\n"
                    "I could not locate any relevant documents or text chunks in your active database workspace "
                    "containing information to answer this query."
                )
            else:
                keywords = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 3]
                
                # 1. Deduplicate & preprocess all context chunks
                processed_chunks = []
                for chunk in context_chunks:
                    clean_text = preprocess_chunk_text(chunk["text"])
                    if clean_text:
                        processed_chunks.append({
                            "id": chunk["id"],
                            "text": clean_text,
                            "filename": chunk["metadata"].get("filename", "Unknown Document")
                        })
                
                # 2. Extract and score sentences
                matched_sentences = []
                seen_sentences = set()
                for p_chunk in processed_chunks:
                    sentences = re.split(r'(?<=[.!?])\s+', p_chunk["text"])
                    for s in sentences:
                        s_clean = s.strip()
                        if not s_clean or len(s_clean) < 15:
                            continue
                        
                        # Deduplicate repeated sentences or minor OCR spacing duplicates
                        norm_sentence = re.sub(r'\s+', '', s_clean.lower())
                        if norm_sentence in seen_sentences:
                            continue
                        seen_sentences.add(norm_sentence)
                        
                        # Score relevance based on overlapping query keywords
                        score = sum(1 for kw in keywords if kw in s_clean.lower())
                        # Small bonus for sentence length balance (avoiding huge raw paragraphs or tiny fragments)
                        if 30 < len(s_clean) < 250:
                            score += 0.5
                            
                        if score > 0 or not keywords:
                            matched_sentences.append({
                                "text": s_clean,
                                "chunk_id": p_chunk["id"],
                                "filename": p_chunk["filename"],
                                "score": score
                            })
                
                # Sort matched sentences by relevance score
                matched_sentences.sort(key=lambda x: x["score"], reverse=True)
                
                # Limit the selected sentences to avoid verbosity (maximum 5 highly relevant points)
                selected_facts = matched_sentences[:5]
                
                if selected_facts:
                    # Group matching facts by document filename for beautiful structured output!
                    grouped_facts = {}
                    for fact in selected_facts:
                        fn = fact["filename"]
                        if fn not in grouped_facts:
                            grouped_facts[fn] = []
                        grouped_facts[fn].append(fact)
                        
                    lines = [
                        "# Local Grounded Fallback Synthesis",
                        "*(Note: The remote OpenAI synthesis layer is currently offline. Generating high-fidelity answer from local semantic indices.)*\n",
                        "## 📊 Grounded Key Points",
                        "I extracted the following highly relevant factual statements from your workspace documents:"
                    ]
                    
                    for filename, facts in grouped_facts.items():
                        lines.append(f"\n### 📄 Source: **{filename}**")
                        for fact in facts:
                            c_idx = id_to_idx.get(fact["chunk_id"], 1)
                            # Highlight keywords in bold in the fallback output for an premium feel!
                            text_highlighted = fact["text"]
                            for kw in keywords[:3]:  # highlight top 3 keywords
                                if len(kw) > 3:
                                    text_highlighted = re.sub(
                                        r'(?i)\b(' + re.escape(kw) + r')\b', 
                                        r'**\1**', 
                                        text_highlighted
                                    )
                            lines.append(f"- {text_highlighted} [^{c_idx}^]")
                            
                    lines.append("\n## 💡 Educational Summary")
                    primary_file = selected_facts[0]["filename"]
                    lines.append(
                        f"Based on the analyzed text from `{primary_file}`, the primary matching documents "
                        f"outline critical context answering your query. Please refer to the clickable citation pills "
                        f"above to verify these source sentences directly in the files."
                    )
                    answer = "\n".join(lines)
                else:
                    # Generic excerpt summary if no exact sentence matches
                    lines = [
                        "# Local Grounded Fallback Synthesis",
                        "*(Note: OpenAI is currently offline. Excerpt synthesis activated.)*\n",
                        "I found relevant workspace documents but could not match exact sentence-level keywords. "
                        "Here are direct cleaned summaries from the retrieved sections:\n"
                    ]
                    for idx, c in enumerate(processed_chunks[:3], 1):
                        c_idx = id_to_idx.get(c["id"], 1)
                        excerpt = c["text"][:220].strip() + "..."
                        lines.append(f"### 📄 Excerpt {idx} from **{c['filename']}**")
                        lines.append(f"> {excerpt} [^{c_idx}^]\n")
                    answer = "\n".join(lines)
            
            # Stream the synthesized local grounded answer chunk-by-chunk to simulate typing animation
            import asyncio
            chunk_size = 5
            for i in range(0, len(answer), chunk_size):
                sub_text = answer[i:i+chunk_size]
                payload = json.dumps({"type": "content", "data": sub_text})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0.01) # Simulate real-time typing speed
                
            yield f"data: [DONE]\n\n"

