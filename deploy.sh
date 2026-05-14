#!/bin/bash
# ============================================================
# 开明向阳 - 一键部署脚本
# 适用于：腾讯云轻量应用服务器 / CVM
# 系统要求：Ubuntu 22.04 / 20.04
# 用法：
#   1. 将整个项目上传到服务器 /opt/kaimin
#   2. chmod +x deploy.sh
#   3. sudo ./deploy.sh
# ============================================================

set -e

# ---------- 颜色输出 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${BLUE}============================================${NC}"; echo -e "${BLUE}[STEP]${NC} $1"; echo -e "${BLUE}============================================${NC}"; }

# ---------- 配置变量（按需修改） ----------
PROJECT_DIR="/root/kaimin/kaimin"
BACKEND_DIR="${PROJECT_DIR}/backend"
ADMIN_DIR="${PROJECT_DIR}/admin-web"
VENV_DIR="${PROJECT_DIR}/venv"
SERVICE_NAME="kaimin"
DOMAIN=""  # 留空则跳过 HTTPS，填写域名则自动申请证书

# 数据库配置
DB_NAME="kaimin"
DB_USER="kaimin"
DB_PASSWORD=""  # 留空则自动生成随机密码

# ---------- 检查 root ----------
if [ "$EUID" -ne 0 ]; then
    log_error "请使用 root 用户运行: sudo ./deploy.sh"
    exit 1
fi

# ---------- 检查项目目录 ----------
if [ ! -f "${BACKEND_DIR}/requirements.txt" ]; then
    log_error "未找到 ${BACKEND_DIR}/requirements.txt，请确保项目已上传到 ${PROJECT_DIR}"
    exit 1
fi

# ============================================================
log_step "1/8  更新系统包"
# ============================================================
apt update && apt upgrade -y
log_info "系统包更新完成"

# ============================================================
log_step "2/8  安装基础依赖"
# ============================================================

# 基础包（不含 MySQL）
CORE_PACKAGES="python3 python3-pip python3-venv nginx git curl"

# 检测 MySQL 是否已安装
if command -v mysql &>/dev/null; then
    log_info "MySQL 已安装，跳过 mysql-server 安装"
    apt install -y ${CORE_PACKAGES}
else
    log_info "未检测到 MySQL，将一并安装"
    apt install -y ${CORE_PACKAGES} mysql-server
fi

# 确保 pip 最新
python3 -m pip install --upgrade pip -q
log_info "基础依赖安装完成"

# ============================================================
log_step "3/8  配置 MySQL"
# ============================================================

# 生成随机密码（满足 MySQL 密码策略：大小写+数字+特殊字符）
if [ -z "$DB_PASSWORD" ]; then
    DB_PASSWORD="Km@$(openssl rand -hex 8)"
fi

# 启动 MySQL
systemctl start mysql 2>/dev/null || service mysql start 2>/dev/null
systemctl enable mysql 2>/dev/null || true

# 创建数据库和用户（兼容首次和重复执行）
SQL_STMTS=$(cat <<SQLEOF
CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQLEOF
)

if echo "$SQL_STMTS" | mysql -u root 2>/dev/null; then
    log_info "数据库创建成功（无密码方式）"
elif echo "$SQL_STMTS" | mysql -u root -p'' 2>/dev/null; then
    log_info "数据库创建成功（空密码方式）"
else
    log_warn "MySQL root 密码已设置，请手动输入 root 密码："
    echo "$SQL_STMTS" | mysql -u root -p
fi

log_info "MySQL 配置完成 (数据库: ${DB_NAME}, 用户: ${DB_USER})"

# ============================================================
log_step "4/8  配置 Python 虚拟环境"
# ============================================================

# 创建虚拟环境
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv ${VENV_DIR}
    log_info "虚拟环境已创建: ${VENV_DIR}"
else
    log_info "虚拟环境已存在，跳过创建"
fi

# 安装依赖
${VENV_DIR}/bin/pip install --upgrade pip -q
${VENV_DIR}/bin/pip install -r ${BACKEND_DIR}/requirements.txt
${VENV_DIR}/bin/pip install gunicorn
log_info "Python 依赖安装完成"

# ============================================================
log_step "5/8  生成环境变量配置"
# ============================================================

JWT_SECRET=$(openssl rand -hex 32)

cat > ${BACKEND_DIR}/.env << ENVEOF
# ===== 应用配置 =====
DEBUG=false
APP_NAME=开明向阳 - 掌上民进之家
APP_VERSION=1.0.0

# ===== 数据库 =====
DB_HOST=localhost
DB_PORT=3306
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=${DB_NAME}

# ===== JWT =====
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# ===== 微信小程序 =====
WECHAT_APPID=请填写你的微信AppID
WECHAT_SECRET=请填写你的微信Secret

# ===== 邮件通知 =====
SMTP_HOST=
SMTP_PORT=465
SMTP_USER=
SMTP_PASSWORD=
EMAIL_TARGET=

# ===== 腾讯云 COS（文件存储） =====
# 如 ap-guangzhou, ap-shanghai
COS_REGION=
# 格式: bucketname-1234567890
COS_BUCKET=
COS_SECRET_ID=
COS_SECRET_KEY=
ENVEOF

log_info ".env 配置文件已生成"
log_warn "请编辑 ${BACKEND_DIR}/.env 填写微信、邮箱、COS 等配置！"

# ============================================================
log_step "6/8  创建 Systemd 服务"
# ============================================================

# 确保日志目录存在
mkdir -p ${BACKEND_DIR}/logs

cat > /etc/systemd/system/${SERVICE_NAME}.service << UNITEOF
[Unit]
Description=Kaimin FastAPI Service
After=network.target mysql.service
Wants=mysql.service

[Service]
User=root
Group=root
WorkingDirectory=${BACKEND_DIR}
Environment="PATH=${VENV_DIR}/bin"
ExecStart=${VENV_DIR}/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 --access-logfile ${BACKEND_DIR}/logs/kaimin-access.log --error-logfile ${BACKEND_DIR}/logs/kaimin-error.log app.main:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

log_info "Systemd 服务已创建并启动"

## ============================================================
#log_step "7/8  配置 Nginx 反向代理"
## ============================================================
#
## 检测 Nginx 配置目录结构
#if [ -d "/etc/nginx/sites-available" ]; then
#    NGINX_AVAILABLE="/etc/nginx/sites-available"
#    NGINX_ENABLED="/etc/nginx/sites-enabled"
#else
#    NGINX_AVAILABLE="/etc/nginx/conf.d"
#    NGINX_ENABLED="/etc/nginx/conf.d"
#fi
#
#cat > ${NGINX_AVAILABLE}/${SERVICE_NAME} << 'NGINXEOF'
#server {
#    listen 80;
#    server_name _;
#
#    client_max_body_size 50M;
#
#    # 健康检查
#    location /health {
#        proxy_pass http://127.0.0.1:8000/health;
#        proxy_set_header Host $host;
#        proxy_set_header X-Real-IP $remote_addr;
#        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#        proxy_set_header X-Forwarded-Proto $scheme;
#    }
#
#    # API 接口
#    location / {
#        proxy_pass http://127.0.0.1:8000;
#        proxy_set_header Host $host;
#        proxy_set_header X-Real-IP $remote_addr;
#        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#        proxy_set_header X-Forwarded-Proto $scheme;
#        proxy_read_timeout 120s;
#    }
#
#    # 管理后台静态文件
#    location /admin {
#        alias /opt/kaimin/admin-web;
#        index index.html;
#        try_files $uri $uri/ /admin/index.html;
#    }
#}
#NGINXEOF
#
## 启用站点（仅 sites-available 模式需要）
#if [ "${NGINX_AVAILABLE}" != "${NGINX_ENABLED}" ]; then
#    ln -sf ${NGINX_AVAILABLE}/${SERVICE_NAME} ${NGINX_ENABLED}/${SERVICE_NAME}
#    rm -f ${NGINX_ENABLED}/default
#fi
#
## 测试配置并重载
#nginx -t && systemctl restart nginx
#log_info "Nginx 配置完成"

## ============================================================
#log_step "8/8  验证部署"
## ============================================================
#
#sleep 2
#
#echo ""
#echo "============================================"
#echo "  健康检查"
#echo "============================================"
#
## 本地测试
#HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo "000")
#
#if [ "$HTTP_CODE" = "200" ]; then
#    log_info "FastAPI 服务运行正常 (127.0.0.1:8000)"
#else
#    log_error "FastAPI 服务异常 (HTTP ${HTTP_CODE})，请检查日志: journalctl -u ${SERVICE_NAME} -n 50"
#fi
#
## Nginx 测试
#NGINX_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/health 2>/dev/null || echo "000")
#if [ "$NGINX_CODE" = "200" ]; then
#    log_info "Nginx 反向代理正常 (127.0.0.1)"
#else
#    log_warn "Nginx 代理可能异常 (HTTP ${NGINX_CODE})，请检查: nginx -t"
#fi
#
## 获取公网 IP
#PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ip.sb 2>/dev/null || echo "未知")
#
#echo ""
#echo "============================================"
#echo "  部署完成！"
#echo "============================================"
#echo ""
#echo -e "  ${GREEN}公网访问地址:${NC}  http://${PUBLIC_IP}"
#echo -e "  ${GREEN}健康检查:${NC}      http://${PUBLIC_IP}/health"
#echo -e "  ${GREEN}API 文档:${NC}      http://${PUBLIC_IP}/docs  (需 DEBUG=true)"
#echo -e "  ${GREEN}管理后台:${NC}      http://${PUBLIC_IP}/admin"
#echo ""
#echo -e "  ${YELLOW}数据库密码:${NC}    ${DB_PASSWORD}  (请妥善保存！)"
#echo -e "  ${YELLOW}JWT 密钥:${NC}      ${JWT_SECRET}"
#echo ""
#echo -e "  ${YELLOW}⚠ 请立即编辑 .env 填写微信/邮箱/OSS 配置：${NC}"
#echo -e "  ${YELLOW}  vi ${BACKEND_DIR}/.env${NC}"
#echo -e "  ${YELLOW}  systemctl restart ${SERVICE_NAME}${NC}"
#echo ""
#echo -e "  ${BLUE}常用命令:${NC}"
#echo -e "  ${BLUE}  查看日志:${NC}      journalctl -u ${SERVICE_NAME} -f"
#echo -e "  ${BLUE}  重启服务:${NC}      systemctl restart ${SERVICE_NAME}"
#echo -e "  ${BLUE}  查看状态:${NC}      systemctl status ${SERVICE_NAME}"
#echo -e "  ${BLUE}  Nginx日志:${NC}     tail -f /var/log/nginx/access.log"
#echo ""
#
## 如果有域名，提示 HTTPS
#if [ -n "$DOMAIN" ]; then
#    log_info "检测到域名配置: ${DOMAIN}"
#    echo "  如需 HTTPS，请执行:"
#    echo "    apt install -y certbot python3-certbot-nginx"
#    echo "    certbot --nginx -d ${DOMAIN}"
#fi