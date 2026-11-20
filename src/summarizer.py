import logging
import re

from google import genai
from google.genai import errors
from openrouter import OpenRouter

from src.config import (
    GEMINI_API_KEY,
    GEMINI_FALLBACK_CODES,
    GEMINI_MODELS,
    OPENROUTER_API_KEY,
    OPENROUTER_FREE_MODEL,
)

logger = logging.getLogger(__name__)


def build_prompt(articles, mode="all"):
    raw_text = "\n\n".join(articles)

    if mode == "news":
        return f"""
    Bạn là biên tập viên tin tức cá nhân. Dưới đây là danh sách các tin tức thô vừa thu thập:

    {raw_text}

    Hãy lọc và tổng hợp lại thành bản tin súc tích theo gu: Chính trị, Công nghệ, Tin nóng. Chia làm 3 phần:
    <b>🏛 CHÍNH TRỊ &amp; THẾ GIỚI</b>
    <b>💻 CÔNG NGHỆ NỔI BẬT</b>
    <b>🔥 TIN NÓNG TRONG NƯỚC</b>

    Quy tắc định dạng BẮT BUỘC (chỉ dùng HTML cơ bản của Telegram):
    - Chỉ sử dụng các thẻ: <b>in đậm</b>, <i>in nghiêng</i>, <a href="URL">Đọc gốc</a>. Tuyệt đối KHÔNG dùng Markdown (*, #, ```).
    - Chọn 8-12 tin đắt giá nhất, bỏ qua tin rác/giật gân vô thưởng vô phạt.
    - Nếu một mục không có tin phù hợp, bỏ qua luôn tiêu đề mục đó (không bịa tin).
    - Mỗi tin gồm tiêu đề in đậm, 2 gạch đầu dòng tóm tắt cốt lõi (số liệu, tác động chính) và link <a href="link">Đọc gốc</a> ở cuối.
    - Dịch tin tiếng Anh sang tiếng Việt tự nhiên, chuẩn thuật ngữ công nghệ/chính trị.
    """

    if mode == "social":
        return f"""
    Bạn là biên tập viên tổng hợp tin mạng xã hội cá nhân. Dưới đây là các bài đăng mới thu thập từ X (Twitter) và Threads:

    {raw_text}

    Hãy lọc và tổng hợp thành bản tin buổi sáng ngắn gọn với đúng 1 mục tiêu đề ở đầu:
    <b>💬 ĐIỂM NÓNG X &amp; THREADS SÁNG NAY</b>

    Quy tắc định dạng BẮT BUỘC (chỉ dùng HTML cơ bản của Telegram):
    - Chỉ sử dụng các thẻ: <b>in đậm</b>, <i>in nghiêng</i>, <a href="URL">Đọc gốc</a>. Tuyệt đối KHÔNG dùng Markdown (*, #, ```).
    - Chọn 6-10 bài/chủ đề đáng chú ý nhất (tin công nghệ, chính trị, góc nhìn chuyên gia, tin nóng), bỏ qua bài xã giao, quảng cáo hoặc bài thiếu thông tin cốt lõi.
    - Mỗi mục gồm tiêu đề in đậm (kèm tên tài khoản & nền tảng X/Threads), 1-2 gạch đầu dòng tóm tắt ý chính/bối cảnh và link <a href="link">Đọc gốc</a> ở cuối.
    - Dịch tiếng Anh sang tiếng Việt tự nhiên, giữ đúng tên riêng và thuật ngữ công nghệ/chính trị.
    """

    return f"""
    Bạn là biên tập viên tin tức cá nhân. Dưới đây là danh sách các tin tức thô vừa thu thập (nhãn NEWS là báo chí/diễn đàn, nhãn SOCIAL là bài đăng từ X và Threads):

    {raw_text}

    Hãy lọc và tổng hợp lại thành bản tin súc tích theo gu: Chính trị, Công nghệ, Tin nóng, và Mạng xã hội (X & Threads). Chia làm 4 phần:
    <b>🏛 CHÍNH TRỊ &amp; THẾ GIỚI</b>
    <b>💻 CÔNG NGHỆ NỔI BẬT</b>
    <b>🔥 TIN NÓNG TRONG NƯỚC</b>
    <b>💬 ĐIỂM NÓNG X &amp; THREADS</b>

    Quy tắc định dạng BẮT BUỘC (chỉ dùng HTML cơ bản của Telegram):
    - Chỉ sử dụng các thẻ: <b>in đậm</b>, <i>in nghiêng</i>, <a href="URL">Đọc gốc</a>. Tuyệt đối KHÔNG dùng Markdown (*, #, ```).
    - Chọn 10-15 tin đắt giá nhất, bỏ qua tin rác/giật gân vô thưởng vô phạt hoặc các bài mạng xã hội thiếu thông tin cốt lõi.
    - Các bài có nhãn SOCIAL (từ X hoặc Threads) ưu tiên đưa vào mục <b>💬 ĐIỂM NÓNG X &amp; THREADS</b>, ghi rõ tài khoản/nguồn đăng và bối cảnh chính.
    - Nếu một mục không có tin nào phù hợp trong danh sách đầu vào, hãy bỏ qua luôn tiêu đề mục đó (không bịa tin, không ghi "Không có tin").
    - Mỗi tin gồm tiêu đề in đậm, 2 gạch đầu dòng tóm tắt cốt lõi (số liệu, tác động chính) và link <a href="link">Đọc gốc</a> ở cuối.
    - Dịch tin tiếng Anh sang tiếng Việt tự nhiên, chuẩn thuật ngữ công nghệ/chính trị.
    """


def clean_model_output(text):
    """Loại bỏ cặp code fence nếu model lỡ bọc kết quả trong ```html ... ```."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:html)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return cleaned.strip()


def summarize_with_gemini(prompt):
    if not GEMINI_API_KEY:
        raise RuntimeError("Thiếu GEMINI_API_KEY.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    last_error = None

    for model_name in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = clean_model_output(response.text)
            if text:
                logger.info("Đã tóm tắt thành công bằng Gemini (%s).", model_name)
                return text
            logger.warning(
                "Model %s trả về nội dung rỗng, đang chuyển sang model dự phòng...",
                model_name,
            )
            last_error = RuntimeError(f"Model {model_name} trả về nội dung rỗng.")
        except errors.APIError as e:
            code = getattr(e, "code", None)
            if code in GEMINI_FALLBACK_CODES:
                logger.warning(
                    "Model %s gặp lỗi %s, đang chuyển sang model dự phòng...",
                    model_name,
                    code,
                )
                last_error = e
                continue
            raise

    raise last_error


def summarize_with_openrouter(prompt):
    with OpenRouter(api_key=OPENROUTER_API_KEY) as open_router:
        res = open_router.chat.send(
            model=OPENROUTER_FREE_MODEL,
            messages=[
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )

    if not res.choices:
        raise RuntimeError("OpenRouter không trả về lựa chọn nào.")

    content = res.choices[0].message.content
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else getattr(part, "text", "")
            for part in content
        )

    used_model = getattr(res, "model", OPENROUTER_FREE_MODEL)
    logger.info("Đã fallback thành công sang OpenRouter (%s).", used_model)
    return clean_model_output(content)


def summarize_with_ai(articles, mode="all"):
    if not articles:
        return None

    prompt = build_prompt(articles, mode=mode)

    try:
        return summarize_with_gemini(prompt)
    except Exception as gemini_err:
        if not OPENROUTER_API_KEY:
            raise
        logger.warning(
            "Tất cả model Gemini thất bại (%s), chuyển sang OpenRouter (%s)...",
            gemini_err,
            OPENROUTER_FREE_MODEL,
        )
        return summarize_with_openrouter(prompt)
