#!/usr/bin/env python3
import argparse
import os
import sys
import logging
import platform
import time
import signal
import psutil
import subprocess
from dotenv import load_dotenv
from waitress import serve
from wsgi import app

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/manage.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def is_windows():
    return platform.system().lower() == 'windows'

def find_server_process():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if any(x in str(proc.info['cmdline']) for x in ['waitress', 'gunicorn']):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def start_service():
    try:
        if is_windows():
            logger.info("Starting Waitress server...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            startup_script = (
                'import sys, os; '
                'sys.path.insert(0, os.getcwd()); '
                'from waitress import serve; '
                'from wsgi import app; '
                'serve(app, host="127.0.0.1", port=8000, threads=4)'
            )
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(
                [sys.executable, '-c', startup_script],
                cwd=script_dir,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            time.sleep(2)
            if process.poll() is None and find_server_process():
                logger.info("Service started successfully")
                return True
            else:
                logger.error("Service failed to start")
                return False
        else:
            print("Starting Gunicorn server...")
            subprocess.Popen(['gunicorn', '--config', 'gunicorn_config.py', 'wsgi:app'])
            time.sleep(2)
            if find_server_process():
                print("Service started successfully")
                return True
            else:
                print("Service failed to start")
                return False
    except Exception as e:
        logger.error(f"Error starting service: {e}")
        return False

def stop_service():
    proc = find_server_process()
    if not proc:
        logger.info("Service is not running")
        return True
    try:
        if is_windows():
            proc.terminate()
        else:
            proc.terminate()
        gone, alive = psutil.wait_procs([proc], timeout=3)
        if alive:
            for p in alive:
                p.kill()
        logger.info("Service stopped successfully")
        return True
    except Exception as e:
        logger.error(f"Error stopping service: {e}")
        return False

def restart_service():
    stop_service()
    time.sleep(1)
    return start_service()

def check_status():
    proc = find_server_process()
    if proc:
        server_type = "Waitress" if is_windows() else "Gunicorn"
        print(f"{server_type} server is running (PID: {proc.info['pid']})")
        return True
    else:
        print("Service is not running")
        return False

def main():
    parser = argparse.ArgumentParser(description='Press Clippings Service Management')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status'],
                      help='Action to perform on the service')
    args = parser.parse_args()
    actions = {
        'start': start_service,
        'stop': stop_service,
        'restart': restart_service,
        'status': check_status
    }
    success = actions[args.action]()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
