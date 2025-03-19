import multiprocessing
import os
import platform

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes - adjust for Windows
if platform.system().lower() == 'windows':
    # Windows performs better with fewer workers
    workers = 2
    # Use threads on Windows instead of processes
    worker_class = 'gthread'
    threads = multiprocessing.cpu_count() * 2
else:
    workers = multiprocessing.cpu_count() * 2 + 1
    worker_class = 'sync'
    threads = 1

# Connection handling
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

# Process naming
proc_name = 'press_clippings'

# Logging
errorlog = os.path.join('logs', 'error.log')
accesslog = os.path.join('logs', 'access.log')
loglevel = 'info'
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# SSL (disabled by default)
keyfile = None
certfile = None

# Process management
daemon = False
pidfile = None
umask = 0
user = None
group = None

# Temp directory handling
if platform.system().lower() == 'windows':
    # Use regular temp directory on Windows
    worker_tmp_dir = None
else:
    # Use RAM disk on Unix systems
    worker_tmp_dir = '/dev/shm'

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190