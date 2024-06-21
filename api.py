import subprocess
import json
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import psutil
import time
from signal import signal, SIGINT, SIGTERM, SIGKILL
from sys import exit

host = os.environ.get("Host", "0.0.0.0")
port = os.environ.get("PORT", 5000)
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your_secret_key'
jwt = JWTManager(app)

def load_state(filename="stream_state.json"):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_state(pids, filename="stream_state.json"):
    try:
        with open(filename, 'w') as f:
            json.dump(pids, f)
            print(f'save state: {pids}')
    except FileNotFoundError:
        print(f'file not found: {pids}')
        return("No file found")

def setup_monitoring_logging():
    log_dir = 'home/ubuntu/logs/pipelines/mem_consumption'
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'memory_monitor.log')
    handler = RotatingFileHandler(log_file, maxBytes=20*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
    handler.setFormatter(formatter)
    monitoring_logger = logging.getLogger('monitoring_logger')
    monitoring_logger.setLevel(logging.INFO)
    monitoring_logger.addHandler(handler)
    return monitoring_logger

monitoring_logger = setup_monitoring_logging()

def monitor_processes(pids, interval=5, logger=None):
    while True:
        if pids:
            for pid, port_send, port_receive in pids:
                try:
                    process = psutil.Process(pid)
                    memory_usage = process.memory_info().rss / (1024 * 1024)
                    if logger:
                        logger.info(f"PID {pid} [Send: {port_send}, Receive: {port_receive}]: {memory_usage:.2f} MB")
                except psutil.NoSuchProcess:
                    if logger:
                        logger.info(f"Process {pid} terminated. Removing from monitoring list.")
                    pids.remove((pid, port_send, port_receive))
            time.sleep(interval)

def start_monitor():
    monitor_process = subprocess.Popen(["python3", "monitor_processes.py"])
    return monitor_process

def shutdown_handler(signal_received, frame):
    try:
        os.remove("stream_state.json")
        print('SIGINT or CTRL-C detected. Exiting gracefully')
        exit(0)
    except FileNotFoundError:
        print('SIGINT or CTRL-C detected. Exiting gracefully')
        exit(0)

@app.route("/login", methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400
    
    json_data = request.data
    data = json.loads(json_data)
    username = data['username']
    password = data['password']
    if username != 'admin' or password != 'password':
        return jsonify({"msg": "Bad username or password"}), 401
    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200

@app.route("/start_stream", methods=['POST'])
@jwt_required()
def new_stream():
    pids = load_state()
    json_data = request.data
    data = json.loads(json_data)
    port_transmit = data['port_transmit']
    port_receive = data['port_receive']
    port_receive_web = str(int(port_receive) + 2000)
    streamid = data['streamid']
    input_uri_auth = f"srt://:{port_transmit}"
    output_uri_auth = f"srt://:{port_receive}?streamid={streamid}"
    print(output_uri_auth)
    output_uri_auth_web = f"srt://:{port_receive_web}?streamid={streamid}"
    for pid, port_to_send, port_to_receive in pids:
        if port_to_send == port_transmit and port_to_receive == port_receive:
            return jsonify(message="Pipeline already exists"),200 
    
    pipeline_subprocess = subprocess.Popen(["python3", "start_dynamic_streamer.py", input_uri_auth, output_uri_auth, output_uri_auth_web])
    pids.append((pipeline_subprocess.pid, port_transmit, port_receive))
    print(pipeline_subprocess.pid, port_transmit, port_receive)
    save_state(pids)
    return jsonify(message="Streaming started."), 200

@app.route("/stop_stream", methods=['POST'])
@jwt_required()
def stop_stream():
    pids = load_state()
    json_data = request.data
    data = json.loads(json_data)
    port_transmit = data['port_transmit']
    port_receive = data['port_receive']
    i = 0
    for pid, port_to_send, port_to_receive in pids:
        if port_to_send == port_transmit and port_to_receive == port_receive:
            pids.pop(i)
            os.kill(pid, SIGKILL)
            return jsonify(message="Streaming stopped."), 200 
        i+=1
    save_state(pids)
    return jsonify(message="Pipeline not found"),404 

if __name__ == "__main__":
    try:
        os.remove("stream_state.json")
    except FileNotFoundError: 
        pass
    app.run(host=host, port=port, debug=True)