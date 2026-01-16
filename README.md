# Discord Music Bot 🎵

Bot phát nhạc YouTube trong Discord với **Autoplay thông minh** sử dụng YouTube Mix.

---

## ✨ Tính Năng

- 🎵 **Phát nhạc** từ YouTube (URL, search, hoặc playlist)
- 📋 **Playlist support** - Load toàn bộ playlist vào queue
- 🔄 **Smart Autoplay** - Tự tìm bài tiếp theo bằng YouTube Mix
- ⏭️ **Jump to track** - Nhảy đến bài bất kỳ trong queue
- 🔁 **Loop modes** (track, queue, off)
- 🎚️ **Volume control** (0-100%)
- 📊 **Now playing** với progress bar
- 👋 **Auto disconnect** - Rời khi idle hoặc không còn ai trong voice
- 🚫 **Smart filtering** - Lọc shorts, live, quá dài, và hạn chế MV

---

## 📁 Cấu trúc Project

```
discord-music-bot/
├── bot/                    # Source code
│   ├── main.py             # Entry point
│   ├── config.py           # Cấu hình tập trung
│   ├── filters.py          # Filter tracks (shorts/live/MV)
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
git clone https://github.com/MonsieurNikko/DiscordBotMusicWithAutoplay.git
cd DiscordBotMusicWithAutoplay

# 2. Tạo file .env
cp .env.example .env
# Sửa DISCORD_TOKEN trong .env

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Download Lavalink.jar
# Từ: https://github.com/lavalink-devs/Lavalink/releases
# Đặt vào thư mục gốc
```

### Bước 2: Setup YouTube OAuth (QUAN TRỌNG!)

YouTube yêu cầu OAuth để phát nhạc:

1. Chạy Lavalink:
   ```bash
   java -jar Lavalink.jar
   ```

2. Xem logs, sẽ có dòng:
   ```
   OAUTH INTEGRATION: go to https://www.google.com/device and enter code XXX-XXX-XXXX
   ```

3. Mở link, nhập code, đăng nhập bằng **tài khoản Google PHỤ**

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

### Phát nhạc
| Command | Mô tả |
|---------|-------|
| `pplay <url\|keywords>` | Phát hoặc thêm vào queue |
| `pplay <playlist_url>` | Load **toàn bộ** playlist vào queue |
| `pskip` | Skip bài hiện tại |
| `ppause` / `presume` | Tạm dừng / Tiếp tục |
| `pstop` | Dừng + xóa queue + rời voice |

### Queue Management
| Command | Mô tả |
|---------|-------|
| `pqueue` | Xem danh sách queue |
| `pjump <số>` | Nhảy đến bài ở vị trí chỉ định |
| `premove <số>` | Xóa bài khỏi queue |
| `pclear` | Xóa toàn bộ queue |
| `pshuffle` | Trộn ngẫu nhiên queue |

### Thông tin & Cài đặt
| Command | Mô tả |
|---------|-------|
| `pnowplaying` | Bài đang phát + progress bar |
| `ploop <off\|track\|queue>` | Chế độ lặp |
| `pautoplay <on\|off>` | Bật/tắt autoplay (YouTube Mix) |
| `pvolume [0-100]` | Điều chỉnh âm lượng |
| `psettings` | Xem cấu hình hiện tại |
| `pmusichelp` | Xem hướng dẫn |

> 💡 **Prefix:** `p` (ví dụ: `pplay`, `pskip`)
> 
> 💡 **Aliases:** `pj` = `pjump`, `ps` = `pskip`, `pq` = `pqueue`, `pnp` = `pnowplaying`

---

## 🔄 Autoplay (YouTube Mix)

Bot sử dụng **YouTube Radio Mix** để tìm bài tiếp theo:
- Dựa trên thuật toán gợi ý của YouTube
- Ưu tiên bài audio (hạn chế MV/Official Music Video)
- Hiển thị bài tiếp theo khi ở bài cuối queue
- Cả skip và kết thúc tự nhiên đều chuyển sang bài autoplay

---

## ⚙️ Cấu hình

### .env
| Biến | Mô tả | Bắt buộc |
|------|-------|----------|
| `DISCORD_TOKEN` | Token từ Discord Developer Portal | ✅ |
| `LAVALINK_HOST` | Host của Lavalink (default: localhost) | ❌ |
| `LAVALINK_PORT` | Port (default: 2333) | ❌ |
| `LAVALINK_PASSWORD` | Password (default: youshallnotpass) | ❌ |

### config.py
| Setting | Default | Mô tả |
|---------|---------|-------|
| `MAX_DURATION_SECONDS` | 5400 (90 phút) | Video dài hơn sẽ bị chặn |
| `IDLE_TIMEOUT_SECONDS` | 300 (5 phút) | Rời voice sau N giây không phát |
| `ANTI_REPEAT_LIMIT` | 20 | Không lặp lại 20 bài gần nhất |
| `BLOCKED_KEYWORDS` | shorts, compilation, live... | Keywords bị block hoàn toàn |
| `MV_KEYWORDS` | mv, official music video... | Hạn chế trong autoplay |

---

## 👋 Auto Disconnect

Bot tự động rời voice channel khi:
- **Idle 5 phút**: Không phát nhạc trong 5 phút
- **Không còn ai**: Rời sau 30 giây khi không còn ai trong voice (trừ bot)

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

**Lưu ý:** Setup OAuth trước (Bước 2) và thêm refresh token vào `lavalink/application.yml`.

---

## ❓ Troubleshooting

### "loadFailed" / "Please sign in"
- YouTube yêu cầu OAuth → Xem Bước 2

### "Không tìm thấy kết quả"
- Kiểm tra OAuth đã setup đúng
- Thử dùng URL thay vì keywords

### Bot không join voice
- Kiểm tra bot có quyền Connect + Speak

### Lavalink không start
- Cần Java 17+ (`java --version`)
- Port 2333 không bị chiếm

---

## 📝 License

MIT
