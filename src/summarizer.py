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


def build_prompt(articles):
    raw_text = "\n\n".join(articles)
    return f"""
    Bạn là biên tập viên tin tức cá nhân. Dưới đây là danh sách các tin tức thô vừa thu thập:
    
    {raw_text}
    
    Hãy lọc và tổng hợp lại thành bản tin súc tích theo gu: Chính trị, Công nghệ, Tin nóng. Chia làm 3 phần:
    <b>🏛 CHÍNH TRỊ & THẾ GIỚI</b>
    <b>💻 CÔNG NGHỆ NỔI BẬT</b>
    <b>🔥 TIN NÓNG TRONG NƯỚC</b>
    
    Quy tắc định dạng BẮT BUỘC (chỉ dùng HTML cơ bản của Telegram):
    - Chỉ sử dụng các thẻ: <b>in đậm</b>, <i>in nghiêng</i>, <a href="URL">Đọc gốc</a>. Tuyệt đối KHÔNG dùng Markdown (*, #, ```).
    - Chọn 8-12 tin đắt giá nhất, bỏ qua tin rác/giật gân vô thưởng vô phạt.
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
                return text
            print(f"Model {model_name} trả về nội dung rỗng, đang chuyển sang model dự phòng...")
            last_error = RuntimeError(f"Model {model_name} trả về nội dung rỗng.")
        except errors.APIError as e:
            code = getattr(e, "code", None)
            if code in GEMINI_FALLBACK_CODES:
                print(f"Model {model_name} gặp lỗi {code}, đang chuyển sang model dự phòng...")
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
    print(f"Đã fallback thành công sang OpenRouter ({used_model}).")
    return clean_model_output(content)


def summarize_with_ai(articles):
    if not articles:
        return None

    prompt = build_prompt(articles)

    try:
        return summarize_with_gemini(prompt)
    except Exception as gemini_err:
        if not OPENROUTER_API_KEY:
            raise
        print(
            f"Tất cả model Gemini thất bại ({gemini_err}), "
            f"chuyển sang OpenRouter ({OPENROUTER_FREE_MODEL})..."
        )
        return summarize_with_openrouter(prompt)
