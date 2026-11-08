
# Python里多进程的三种IPC方案（对应你问的 共享内存 unix信号 管道/socket）

> 区分 Linux 和 Windows 差异

## 1 Unix 信号 signal（仅Linux可用 Windows没有）

作用 只能发通知标记 不带音频数据 比如VAD进程切完一句话 发 SIGUSR1 给FunASR服务进程 FunASR进程注册信号回调 收到信号就去读数据 限制 信号回调里面不能做复杂业务 不能直接读大音频 信号容易丢失 连续快速发的时候会丢 一般搭配共享内存/命名管道一起用 信号只相当于喊一声 “数据准备好了” 示例极简骨架

```
# FunASR服务端 注册信号
import signal
ready_flag = False
def handler(signum, frame):
    global ready_flag
    ready_flag = True
signal.signal(signal.SIGUSR1, handler)

while True:
    if ready_flag:
        # 去共享内存或者fifo拿pcm
        ready_flag = False
    time.sleep(0.01)
```

不推荐单独拿它传语音 只做轻量通知

## 2 共享内存 shm（Python都能实现 两套接口）

Linux 用 `multiprocessing.shared_memory`（python3.8+自带） 或者 posix shm Windows 这个包也支持 底层对应 CreateFileMapping 逻辑是 1 VAD进程开辟一块共享内存 把PCM二进制写进去 2 VAD发信号 / 发一条简短消息 告诉ASR进程 分片起止位置 shm名字 3 ASR进程打开同一块shm 直接读音频 不需要拷贝整块音频 4 读完之后标记释放 循环复用 好处 大块音频几乎无拷贝 开销最低 坏处 需要自己做同步锁 自己管理缓冲区 防止读一半被覆盖 代码复杂度高 适合你后面压延迟的时候升级用 简单示意

```
# 发送方VAD
from multiprocessing import shared_memory
shm = shared_memory.SharedMemory(create=True, size=32000*2)
buf = shm.buf
buf[:len(pcm_data)] = pcm_data
# 发信号或者短消息通知ASR shm名字+长度

# ASR接收方 按名字打开shm读取
shm_remote = shared_memory.SharedMemory(name=shm.name)
pcm_recv = bytes(shm_remote.buf[:data_len])
```

## 3 Unix Domain Socket（Linux） / 命名管道（Windows）【推荐你现阶段首选】

用 `socket` 库原生写 Linux AF_UNIX 路径比如 `/tmp/vad_asr.sock` Windows不能稳定AF_UNIX 改用命名管道 或者回退到127.0.0.1 TCP 好处 代码好写 自带流式分包 自带边界 不用手动处理shm锁 Python标准库就能搞定 不用额外装包 数据直接带PCM+元信息 不需要再搭配信号 缺点 存在一次内核态拷贝 但几百ms的语音片段在你这个设备上完全感受不到压力

下面给你一套最小可跑的 Linux UDS 版本

- 服务端 FunASR 常驻 模型只加载一次
- 客户端 VAD进程 切完音频发送PCM
    
    > Windows版本只需要把socket部分改成命名管道或者TCP 模型推理代码不动
    

### 服务端 funasr_uds_server.py（Linux）

```
import socket
import struct
from funasr import AutoModel

# 全局只加载一次模型 不会反复冷启动
model = AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model=None,
    punc_model="ct-punc",
    device="cpu",
    disable_update=True
)

SOCK_PATH = "/tmp/vad_asr.sock"

# 清理旧socket文件
import os
if os.path.exists(SOCK_PATH):
    os.unlink(SOCK_PATH)

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(SOCK_PATH)
s.listen(1)

while True:
    conn, addr = s.accept()
    with conn:
        while True:
            # 先读4字节代表音频长度
            len_header = conn.recv(4)
            if not len_header:
                break
            data_len = struct.unpack("!I", len_header)[0]
            pcm_buf = b""
            while len(pcm_buf) < data_len:
                chunk = conn.recv(data_len - len(pcm_buf))
                if not chunk:
                    break
                pcm_buf += chunk
            # 调用识别
            res = model.generate(input=pcm_buf, use_itn=True)
            text = res[0]["text"]
            # 回传结果 先发4字节长度+文本bytes
            text_bytes = text.encode("utf-8")
            conn.sendall(struct.pack("!I", len(text_bytes)))
            conn.sendall(text_bytes)
```

### 客户端 vad_client.py（VAD进程里面调用）

```
import socket
import struct

SOCK_PATH = "/tmp/vad_asr.sock"

def send_audio_segment(pcm_bytes):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK_PATH)
    s.sendall(struct.pack("!I", len(pcm_bytes)))
    s.sendall(pcm_bytes)
    # 接收返回文本
    len_header = s.recv(4)
    text_len = struct.unpack("!I", len_header)[0]
    text_bytes = s.recv(text_len)
    s.close()
    return text_bytes.decode("utf-8")

# 示例 你VAD切出来的16k单通道pcm
# result = send_audio_segment(segment_pcm)
# print(result)
```

---

