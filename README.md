# News Digest Bot (VPS 1GB RAM + Docker + Local RSSHub cho X & Threads)

Bot tổng hợp tin tức tự động gửi về Telegram, chạy gọn trong Docker Compose trên **VPS 1GB RAM** kèm **RSSHub localhost** (`127.0.0.1:1200`) và **Redis** (cache).

## Kiến trúc dịch vụ (tối ưu cho VPS 1GB RAM)

- `rsshub` (`mem_limit: 420m`, heap Node giới hạn `320MB`): Server RSS nội bộ (`127.0.0.1:1200`), chuyển tài khoản/List X & Threads thành RSS feed.
- `redis` (`mem_limit: 96m`, `--maxmemory 64mb`): Cache kết quả của RSSHub (mặc định 30 phút) để hạn chế gửi request lặp lên X/Threads.
- `news-bot` (`mem_limit: 160m`): Container Python tích hợp sẵn lịch chạy cron (`scheduler.py`), tự nạp lại `feeds.json` mỗi phiên chạy và lưu lịch sử bài đã đọc vào `./data/seen_links.json`.
- `browserless` *(tắt mặc định, nằm ở profile `browser`)*: Chỉ bật khi thực sự cần render route JS nặng.

> Tổng RAM mặc định chỉ khoảng **300–450 MB**, chạy thoải mái trên VPS 1GB RAM.

## Hướng dẫn triển khai trên VPS 1GB RAM

### 0. Tạo 2GB Swap (khuyến nghị mạnh cho VPS 1GB RAM)

Giúp VPS không bao giờ bị treo hay tự kill container khi build Docker hoặc đột biến RAM:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

### 1. Tạo file cấu hình `.env`

```bash
cp .env.example .env
nano .env
```

Điền tối thiểu các biến:
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `GEMINI_API_KEY` (và tùy chọn `OPENROUTER_API_KEY`)
- `TWITTER_AUTH_TOKEN`: cookie `auth_token` của tài khoản X **phụ**

#### Cách lấy `TWITTER_AUTH_TOKEN`
1. Đăng nhập tài khoản **X phụ** trên cửa sổ ẩn danh của trình duyệt, sau đó đóng tab luôn (**không bấm Log out** để cookie sống lâu).
2. Mở DevTools (`F12`) -> tab **Application** (Chrome/Edge) hoặc **Storage** (Firefox) -> **Cookies** -> `https://x.com`.
3. Copy giá trị của cookie `auth_token` dán vào `TWITTER_AUTH_TOKEN`.
4. *(Tùy chọn)* Nhập nhiều token cách nhau bằng dấu phẩy (`token1,token2`) để RSSHub tự xoay vòng.

### 2. Chọn tài khoản X & Threads cần theo dõi trong `feeds.json`

Mở `feeds.json`, thay username mẫu bằng tài khoản bạn muốn và đổi `"enabled": false` thành `"enabled": true`:

```json
{
  "name": "X - OpenAI",
  "url": "{RSSHUB_BASE_URL}/twitter/user/OpenAI",
  "platform": "x",
  "category": "social",
  "limit": 5,
  "skip_retweets": true,
  "enabled": true
}
```

Các mẫu URL RSSHub hỗ trợ:
- User X: `{RSSHUB_BASE_URL}/twitter/user/<username>`
- Twitter List *(khuyến nghị gom nhiều tài khoản vào 1 List)*: `{RSSHUB_BASE_URL}/twitter/list/<list_id>`
- Từ khóa X: `{RSSHUB_BASE_URL}/twitter/keyword/<tu_khoa>`
- User Threads: `{RSSHUB_BASE_URL}/threads/<username>`

> `feeds.json` được mount trực tiếp vào container nên mỗi khi thêm/bớt nguồn bạn chỉ cần sửa file này — **không cần build lại Docker**.

### 3. Khởi chạy hệ thống

```bash
mkdir -p data
# (Tùy chọn) Giữ lại lịch sử tin đã đọc trước đó nếu có:
[ -f seen_links.json ] && cp seen_links.json data/seen_links.json

docker compose up -d --build
```

### 4. Kiểm tra & chạy thử ngay lập tức

```bash
# Kiểm tra trạng thái 3 container (đợi rsshub chuyển sang healthy)
docker compose ps

# Test nhanh RSSHub localhost trên VPS
curl -I http://127.0.0.1:1200/healthz
curl -s http://127.0.0.1:1200/threads/zuck | head -n 20

# Ép bot chạy thử ngay 1 phiên mà không cần đợi đến giờ cron
docker compose exec news-bot python bot.py

# Xem log scheduler & các phiên chạy
docker compose logs -f news-bot
```

> Nếu sau này test route Threads thấy RSSHub báo cần browser, bạn đã có sẵn 2GB Swap ở bước 0 — chỉ cần bỏ comment 2 dòng `BROWSERLESS_TOKEN` & `PLAYWRIGHT_CDP_ENDPOINT` trong `.env` rồi chạy `docker compose --profile browser up -d`.

### 5. Khi nhận cảnh báo token X hết hạn trên Telegram

Chỉ cần dán `TWITTER_AUTH_TOKEN` mới vào `.env` rồi nạp lại đúng container `rsshub`:

```bash
nano .env
docker compose up -d rsshub
```
