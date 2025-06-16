import subprocess
import threading
import queue
import uuid

_job_queue = queue.Queue()
_output_queues = {}
_started = False


def _worker():
    while True:
        job_id, cmd = _job_queue.get()
        out_q = _output_queues[job_id]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(process.stdout.readline, ''):
            out_q.put(line.rstrip())
        process.wait()
        out_q.put(None)
        _job_queue.task_done()


def start_worker():
    global _started
    if not _started:
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        _started = True


def enqueue(cmd):
    start_worker()
    job_id = str(uuid.uuid4())
    _output_queues[job_id] = queue.Queue()
    _job_queue.put((job_id, cmd))
    return job_id


def stream(job_id):
    q = _output_queues.get(job_id)
    if q is None:
        return
    while True:
        line = q.get()
        if line is None:
            del _output_queues[job_id]
            break
        yield line
