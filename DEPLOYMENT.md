# 🚀 Deployment Guide - Cloud Server

Hướng dẫn deploy bot lên server (VPS, Cybrancee, DigitalOcean, v.v.)

---

## 📋 Yêu cầu Server

| Yêu cầu | Minimum |
|---------|---------|
| RAM | 1GB (2GB recommended) |
| CPU | 1 vCPU |
| OS | Ubuntu 20.04+ / Debian 11+ |
| Docker | ✅ Cần cài |

---

## 🔧 Setup Server (1 lần)

### 1. SSH vào server
```bash
ssh your-user@your-server-ip
```

### 2. Cài Docker & Docker Compose
```bash
# Cài Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Logout và login lại để apply group
exit
ssh your-user@your-server-ip

# Verify
docker --version
docker compose version
```

### 3. Clone repo
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git discord-music-bot
cd discord-music-bot
```

### 4. Tạo file .env
```bash
cp .env.example .env
nano .env
# Điền DISCORD_TOKEN
```

### 5. Chạy lần đầu
```bash
docker-compose up -d
docker-compose logs -f  # Xem logs
```

---

## 🔄 Auto-Deploy từ GitHub (CI/CD)

Mỗi khi push code lên `main` → server tự động cập nhật!

### Setup GitHub Secrets

Vào repo GitHub → Settings → Secrets and variables → Actions → New repository secret

| Secret Name | Value |
|-------------|-------|
| `SERVER_HOST` | IP server (vd: 123.45.67.89) |
| `SERVER_USER` | Username SSH (vd: root, ubuntu) |
| `SERVER_SSH_KEY` | Private key SSH (cả block `-----BEGIN...END-----`) |
| `DISCORD_TOKEN` | Token bot (optional, nếu muốn inject từ CI) |

### Tạo SSH Key (nếu chưa có)
```bash
# Trên máy local
ssh-keygen -t ed25519 -C "github-deploy"

# Copy public key lên server
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@server

# Private key → paste vào GitHub Secret SERVER_SSH_KEY
cat ~/.ssh/id_ed25519
```

---

## 📦 Commands hữu ích trên server

```bash
# Xem status
docker-compose ps

# Xem logs
docker-compose logs -f
docker-compose logs bot --tail=50

# Restart
docker-compose restart

# Update code thủ công
git pull
docker-compose up -d --build

# Stop tất cả
docker-compose down
```

---

## 🔒 Security Tips

1. **Không commit file .env** - đã có trong .gitignore
2. **Dùng SSH key** thay vì password
3. **Firewall**: chỉ mở port SSH (22)
4. **Không expose Lavalink** ra internet (internal network only)

---

## 🐛 Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| Bot không connect Lavalink | Đợi 10-15s cho Lavalink khởi động xong |
| Permission denied | Chạy `sudo usermod -aG docker $USER` rồi logout/login |
| Out of memory | Tăng RAM hoặc thêm swap |
| Lavalink crash | Kiểm tra `docker-compose logs lavalink` |
