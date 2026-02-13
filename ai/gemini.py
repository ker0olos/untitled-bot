"""Gemini LLM integration and message utilities for AI replies."""
import os
from typing import List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from ai.rules import SYSTEM_PROMPT, DEFAULT_PERSONALITY

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=1,
)


def get_media_urls_from_message(message) -> List[str]:
    """Collect attachment URLs and embed image/thumbnail/video URLs from a message."""
    urls: List[str] = []
    for att in message.attachments:
        urls.append(att.url)
    for embed in message.embeds:
        if getattr(embed.image, "url", None):
            urls.append(embed.image.url)
        if getattr(embed.thumbnail, "url", None):
            urls.append(embed.thumbnail.url)
        if getattr(getattr(embed, "video", None), "url", None):
            urls.append(embed.video.url)
    return urls


def build_context_from_messages(messages: List) -> str:
    """Format last N messages as context for the model (text + attachment/embed URLs)."""
    lines = []
    for msg in messages:
        author = msg.author.display_name if hasattr(msg.author, 'display_name') else str(msg.author)
        content = (msg.content or "(no text)").strip()
        if not content and (msg.attachments or msg.embeds):
            content = "(media)"
        extra: List[str] = []
        for att in msg.attachments:
            extra.append(att.url)
        for embed in msg.embeds:
            img_url = getattr(embed.image, "url", None)
            if img_url:
                extra.append(img_url)
            thumb_url = getattr(embed.thumbnail, "url", None)
            if thumb_url:
                extra.append(thumb_url)
            video_url = getattr(getattr(embed, "video", None), "url", None)
            if video_url:
                extra.append(video_url)
        if extra:
            content = f"{content} [media: {' '.join(extra)}]"
        lines.append(f"{author}: {content}")
    return "\n".join(lines) if lines else "(no previous messages)"


def get_gemini_reply(
    user_message: str,
    context: str,
    media_urls: Optional[List[str]] = None,
    personality: Optional[str] = None,
    name: str = "Untitled",
) -> Optional[str]:
    """Call Gemini with system prompt, context, and optional attachment/embed URLs; return reply text or None."""
    personality_text = (personality or DEFAULT_PERSONALITY).strip()
    display_name = (name or "Untitled").strip() or "Untitled"
    system_text = SYSTEM_PROMPT.format(context=context, personality=personality_text, name=display_name)
    if media_urls:
        content_parts: List = [
            {"type": "text", "text": user_message}
        ]
        for url in media_urls:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": url, "detail": "auto"}
            })
        human_content = content_parts
    else:
        human_content = user_message
    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=human_content),
    ]
    try:
        response = llm.invoke(messages)
        if response and hasattr(response, "content") and response.content:
            if isinstance(response.content, str):
                return response.content.strip()
            elif isinstance(response.content, list):
                text_parts = []
                for part in response.content:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                return " ".join(text_parts).strip() if text_parts else None
            else:
                return str(response.content).strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        import traceback
        traceback.print_exc()
    return None
