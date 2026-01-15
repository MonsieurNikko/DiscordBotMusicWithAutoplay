# Discord Music Bot 🎵

Bot phát nhạc YouTube trong Discord với **Autoplay thông minh**.

---

## ✨ Tính Năng

- 🎵 Phát nhạc từ YouTube (URL hoặc search)
- 🔄 **Autoplay thông minh** - Tự tìm bài tiếp theo dựa trên sở thích
- 📋 Queue management (add, remove, shuffle, clear)
- 🔁 Loop modes (track, queue, off)
- 🎚️ Volume control
- 📊 Now playing với progress bar

---

## 📁 Cấu trúc Project

```
ytb/
├── bot/                    # Source code
│   ├── main.py             # Entry point
│   ├── config.py           # Cấu hình tập trung
│   ├── recommender.py      # AI gợi ý đơn giản
│   ├── filters.py          # Filter shorts/live/mix
│   ├── utils.py            # Helper functions
│   └── cogs/
│       └── music.py        # Tất cả commands
│
├── lavalink/
│   └── application.yml     # Lavalink config
│
├── start.bat               # ▶️ Chạy bot (Windows)
├── start-lavalink.bat      # ▶️ Chạy Lavalink (Windows)
├── docker-compose.yml      # 🐳 Chạy bằng Docker
├── Dockerfile
├── requirements.txt
├── .env.example            # Template biến môi trường
└── .gitignore
```

---

## 🚀 Cách chạy

### Bước 1: Chuẩn bị

```bash
# 1. Clone repo
git clone https://github.com/your-username/discord-music-bot.git
cd discord-music-bot

# 2. Tạo file .env
cp .env.example .env
# Sửa DISCORD_TOKEN trong .env

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Download Lavalink.jar
# Từ: https://github.com/lavalink-devs/Lavalink/releases
# Đặt vào thư mục gốc

# 5. Tạo thư mục plugins và download youtube-plugin
mkdir plugins
# Download từ: https://github.com/lavalink-devs/youtube-source/releases
# Đặt file .jar vào thư mục plugins/
```

### Bước 2: Setup YouTube OAuth (QUAN TRỌNG!)

YouTube yêu cầu OAuth để phát nhạc. Làm theo các bước:

1. Chạy Lavalink:
   ```bash
   java -jar Lavalink.jar
   ```

2. Xem logs, sẽ có dòng như:
   ```
   OAUTH INTEGRATION: go to https://www.google.com/device and enter code XXX-XXX-XXXX
   ```

3. Mở link, nhập code, đăng nhập bằng **tài khoản Google PHỤ** (không dùng tài khoản chính!)

4. Copy refresh token từ logs và thêm vào `lavalink/application.yml`:
   ```yaml
   oauth:
     enabled: true
     refreshToken: "YOUR_TOKEN_HERE"
     skipInitialization: true
   ```

### Bước 3: Chạy

**Windows:**
```powershell
# Terminal 1
.\start-lavalink.bat

# Terminal 2
.\start.bat
```

**Docker:**
```bash
docker-compose up -d
```

---

## 🎮 Commands

| Command | Mô tả |
|---------|-------|
| `pplay <url\|keywords>` | Phát hoặc thêm vào queue |
| `pskip` | Skip bài hiện tại |
| `ppause` / `presume` | Tạm dừng / Tiếp tục |
| `pstop` | Dừng + xóa queue |
| `pqueue` | Xem queue |
| `premove <index>` | Xóa bài khỏi queue |
| `pclear` | Xóa toàn bộ queue |
| `pshuffle` | Trộn queue |
| `pnowplaying` | Bài đang phát + progress |
| `ploop <off\|track\|queue>` | Lặp |
| `pautoplay <on\|off>` | Bật/tắt autoplay |
| `precommend [n]` | Xem n gợi ý |
| `paddrec <index>` | Thêm gợi ý vào queue |
| `pvolume [0-100]` | Âm lượng |
| `psettings` | Xem cấu hình |
| `pmusichelp` | Xem hướng dẫn |

> 💡 Commands **case-insensitive**: `PPLAY`, `pPlAy`, `pplay` đều OK!

---

## ⚙️ Cấu hình (.env)

```bash
# Copy template
cp .env.example .env
```

| Biến | Mô tả | Bắt buộc |
|------|-------|----------|
| `DISCORD_TOKEN` | Token từ Discord Developer Portal | ✅ |
| `LAVALINK_HOST` | Host của Lavalink (default: localhost) | ❌ |
| `LAVALINK_PORT` | Port (default: 2333) | ❌ |
| `LAVALINK_PASSWORD` | Password (default: youshallnotpass) | ❌ |

---

## 🔧 Tùy chỉnh (config.py)

| Setting | Default | Mô tả |
|---------|---------|-------|
| `MAX_DURATION_SECONDS` | 5400 (90 phút) | Video dài hơn sẽ bị chặn |
| `IDLE_TIMEOUT_SECONDS` | 300 (5 phút) | Rời voice sau N giây idle |
| `HISTORY_LIMIT` | 10 | Số bài để "học" gợi ý |
| `ANTI_REPEAT_LIMIT` | 20 | Không lặp N bài gần nhất |
| `BLOCKED_KEYWORDS` | shorts, mix, live... | Keywords bị chặn |

---

## 🐳 Docker

```bash
# Chạy cả Lavalink + Bot
docker-compose up -d

# Xem logs
docker-compose logs -f

# Dừng
docker-compose down
```

**Lưu ý Docker:**
- Cần setup OAuth trước (xem Bước 2)
- Thêm refresh token vào `lavalink/application.yml`
- File này được mount vào container

---

## ❓ Troubleshooting

### "loadFailed" / "Please sign in"
- YouTube yêu cầu OAuth → Xem Bước 2

### "No results found"
- Kiểm tra OAuth đã setup đúng
- Thử search bằng URL thay vì keywords

### Bot không join voice
- Kiểm tra bot có quyền Connect + Speak

### Lavalink không start
- Cần Java 17+ (`java --version`)
- Kiểm tra port 2333 không bị chiếm

---

## 📝 License

MIT
