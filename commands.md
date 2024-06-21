# Test airsim2srt
local pc:
```
./AirSimNH.sh -ResX=640 -ResY=480 -windowed
```

# Pipelines:
## Producer:
### Camera:
```
gst-launch-1.0 \
rtspsrc latency=0 tcp-timeout=200000 drop-on-latency=true location=rtsp://admin:admin.123!@192.168.1.110:554 ! \
decodebin ! videoconvert ! mfh265enc low-latency=true ! \
rtph265pay mtu=1316 ! \
srtsink uri=srt://34.230.172.138:9711
```

### Sim:
```
airsim2srt.py
```

## Server:
### Simple:
```
GST_DEBUG=3 gst-launch-1.0 -v \
srtsrc uri="srt://:9717" ! \
srtsink uri="srt://:9718" sync=false
```

### Enc-Dec:
- software:
```
GST_DEBUG=*TRACE*:9 \
GST_TRACERS="interlatency" \
gst-launch-1.0 -v \
srtsrc uri="srt://:9717" ! \
"application/x-rtp,media=video,encoding-name=H265" ! rtph265depay ! h265parse ! \
avdec_h265 ! \
videoconvert ! \
x265enc ! h265parse ! \
rtph265pay mtu=1316 ! \
srtsink uri="srt://:9718" sync=false
```

- hardware:
```
GST_DEBUG=*TRACE*:9 \
GST_TRACERS="interlatency" \
gst-launch-1.0 -v \
srtsrc uri="srt://:9717" ! \
"application/x-rtp,media=video,encoding-name=H265" ! rtph265depay ! h265parse ! \
nvv4l2decoder ! \
nvvideoconvert ! \
nvv4l2h265enc ! h265parse ! \
rtph265pay mtu=1316 ! \
srtsink uri="srt://:9718" sync=false
```

### AI-Deepstream: -> nao funciona com o tablet
```
GST_DEBUG=*TRACE*:9 \
GST_TRACERS="interlatency" \
gst-launch-1.0  \
srtsrc uri="srt://:9717" passphrase="spyskytech123456" ! queue ! \
'application/x-rtp, media=(string)video, encoding-name=(string)H265' ! rtph265depay ! h265parse ! queue ! \
nvv4l2decoder ! queue ! \
nvvideoconvert ! "video/x-raw(memory:NVMM), width=1080, height=720, format=NV12" ! queue ! \
m.sink_0 nvstreammux name=m batch-size=1 width=1080 height=720 ! \
nvinfer config-file-path=/opt/nvidia/deepstream/deepstream/sources/apps/sample_apps/deepstream-test1/dstest1_pgie_config.txt ! queue ! \
nvtracker ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so ! queue ! \
nvmultistreamtiler rows=1 columns=1 width=1080 height=720 ! queue ! \
nvvideoconvert ! \
nvdsosd ! \
nvvideoconvert ! \
nvv4l2h265enc  ! \
h265parse ! rtph265pay mtu=1316 ! \
srtsink uri="srt://:9718" passphrase="spyskytech123456" latency=0 sync=false
```


## AI-Deepstream MPEGTSMUX E TSDEMUX -> funciona com o tablet
```
GST_DEBUG=3 gst-launch-1.0 \
    srtsrc uri="srt://:9711?mode=listener" ! queue ! \
    tsdemux latency=0 ! h265parse ! queue ! \
    avdec_h265 ! videoconvert ! "video/x-raw, format=NV12" ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12" ! queue ! \
    mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! \
    nvinfer config-file-path=/app/nomachine/mvp_ds_py/nvinfer_config.txt ! queue ! \
    nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml \
    ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue ! \
    nvmultistreamtiler rows=1 columns=1 width=1280 height=720 ! queue ! \
    nvvideoconvert ! queue ! \
    nvdsosd ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), format=I420" ! queue ! \
    nvv4l2h265enc tuning-info-id=3 ! queue ! \
    mpegtsmux ! queue ! \
    srtsink uri="srt://:9710"
```

## Viewer:
```
GST_DEBUG=*TRACE*:9 \
GST_TRACERS="interlatency" \
gst-launch-1.0 -v \
srtsrc uri="srt://18.230.120.119:9718" ! \
"application/x-rtp,media=video,encoding-name=H265" ! rtph265depay ! h265parse ! \
decodebin ! \
videoconvert ! \
autovideosink
```
```
srtViewer.py
```

* rtph265pay -> mpegtsmux
* rtph265depay -> tsdemux

---
# helpers:
```
scp -i key user@ip:/home/user/file.ext ./
```
```
ffmpeg -re -stream_loop -1 -i /home/jaco/sst/eco.mp4 \
-c:v libx265 -preset ultrafast -tune zerolatency \
-x265-params "keyint=50:min-keyint=50:no-scenecut=1" \
-c:a aac -b:a 128k -ar 48000 \
-f mpegts "srt://34.230.172.138:9711?pkt_size=1316&mode=caller"
```
```
ffmpeg -re -stream_loop -1 -i "C:\Users\vitor\Videos\2024-03-22 17-04-06.mp4" \
    -c:v libx265 -preset ultrafast -tune zerolatency \
    -x265-params "keyint=50:min-keyint=50:no-scenecut=1" \
    -c:a aac -b:a 128k -ar 48000 -f mpegts \
    "srt://34.230.172.138:9711?mode=caller&passphrase=1234567890"
```

    ffmpeg -re -stream_loop -1 -i "C:\Users\vitor\OneDrive\Documentos\Emprego\eco-rodovias-v1.mp4" -c:v libx265 -preset ultrafast -tune zerolatency -x265-params "keyint=50:min-keyint=50:no-scenecut=1" -c:a aac -b:a 128k -ar 48000 -f mpegts "srt://3.84.245.85:10000?mode=caller

ffmpeg -re -stream_loop -1 -i "C:\Users\vitor\OneDrive\Documentos\Emprego\eco-rodovias-v2.mp4" -c:v libx265 -preset ultrafast -tune zerolatency -x265-params "keyint=50:min-keyint=50:no-scenecut=1" -c:a aac -b:a 128k -ar 48000 -f mpegts "srt://34.230.172.138:9712?mode=caller

```
ffmpeg -f dshow -i video="Chicony USB2.0 Camera" \
    -c:v libx265 -preset ultrafast -tune zerolatency \
    -x265-params "keyint=15:min-keyint=15:no-scenecut=1" \
    -r 15 -fflags nobuffer -an -f mpegts \
    "srt://34.230.172.138:9711?mode=caller"

```

ffmpeg -f dshow -i video="Chicony USB2.0 Camera" -c:v libx265 -preset ultrafast -tune zerolatency -x265-params "keyint=15:min-keyint=15:no-scenecut=1" -r 15 -fflags nobuffer -an -f mpegts "srt://34.230.172.138:9711?mode=caller"


## AI-Deepstream MPEGTSMUX E TSDEMUX -> multistream em portas diferentes e video junto
```
GST_DEBUG=3 gst-launch-1.0 \
    srtsrc uri="srt://:9711?mode=listener" ! queue ! \
    tsdemux latency=0 ! h265parse ! queue ! \
    avdec_h265 ! videoconvert ! "video/x-raw, format=NV12" ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12" ! queue ! \
    mux.sink_0 srtsrc uri="srt://:9712?mode=listener" ! queue ! \
    tsdemux latency=0 ! h265parse ! queue ! \
    avdec_h265 ! videoconvert ! "video/x-raw, format=NV12" ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12" ! queue ! \
    mux.sink_1 nvstreammux name=mux batch-size=2 width=1920 height=1080 live-source=1 ! \
    nvinfer config-file-path=/app/nomachine/mvp_ds_py/nvinfer_config.txt ! queue ! \
    nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml \
    ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue ! \
    nvmultistreamtiler rows=1 columns=2 width=1280 height=720 ! queue ! \
    nvvideoconvert ! queue ! \
    nvdsosd ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), format=I420" ! queue ! \
    nvv4l2h265enc tuning-info-id=3 ! queue ! \
    mpegtsmux ! queue ! \
    srtsink uri="srt://:9710"
```

## AI-Deepstream MPEGTSMUX E TSDEMUX -> multistream em portas diferentes e video separado
```
GST_DEBUG=3 gst-launch-1.0 \
    srtsrc uri="srt://:9711?mode=listener" ! queue ! \
    tsdemux latency=0 ! h265parse ! queue ! \
    avdec_h265 ! videoconvert ! "video/x-raw, format=NV12" ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12" ! queue ! \
    mux.sink_0 srtsrc uri="srt://:9712?mode=listener" ! queue ! \
    tsdemux latency=0 ! h265parse ! queue ! \
    avdec_h265 ! videoconvert ! "video/x-raw, format=NV12" ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12" ! queue ! \
    mux.sink_1 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! \
    nvinfer config-file-path=/app/nomachine/mvp_ds_py/nvinfer_config.txt ! queue ! \
    nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml \
    ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue ! \
    nvmultistreamtiler rows=1 columns=2 width=1280 height=720 ! queue ! \
    nvvideoconvert ! queue ! \
    nvdsosd ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), format=I420" ! queue ! \
    nvv4l2h265enc tuning-info-id=3 ! queue ! \
    muxts. nvinfer config-file-path=/app/nomachine/mvp_ds_py/nvinfer_config.txt ! queue ! \
    nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml \
    ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue ! \
    nvmultistreamtiler rows=1 columns=2 width=1280 height=720 ! queue ! \
    nvvideoconvert ! queue ! \
    nvdsosd ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), format=I420" ! queue ! \
    nvv4l2h265enc tuning-info-id=3 ! queue ! \
    muxts. mpegtsmux name=muxts ! queue ! \
    srtsink uri="srt://:9710"
```


## AI-Deepstream MPEGTSMUX E TSDEMUX -> multistream em portas diferentes e video junto
```
GST_DEBUG=3 gst-launch-1.0 \
    srtsrc uri="srt://:9711?mode=listener" ! queue ! \
    tsdemux latency=0 ! h265parse ! queue ! \
    avdec_h265 ! videoconvert ! "video/x-raw, format=NV12" ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12" ! queue ! \
    mux.sink_0 srtsrc uri="srt://:9712?mode=listener" ! queue ! \
    tsdemux latency=0 ! h265parse ! queue ! \
    avdec_h265 ! videoconvert ! "video/x-raw, format=NV12" ! queue ! \
    nvvideoconvert ! "video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12" ! queue ! \
    mux.sink_1 nvstreammux name=mux batch-size=2 width=1920 height=1080 live-source=1 ! \
    nvinfer config-file-path=/app/nomachine/mvp_ds_py/nvinfer_config.txt ! queue ! \
    nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml \
    ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue ! \
    nvmultistreamtiler rows=1 columns=2 width=1280 height=720 ! queue ! \
    nvvideoconvert ! queue ! \
    nvdsosd ! queue ! \
    nvvideoconvert ! "video/x-raw, format=I420" ! \
    jpegenc ! fakesink 
```

## AI-Deepstream MPEGTSMUX e TSDEMUX -> Inferencia na AWS prod -> sem kafka -> com tee postando H265 e H264
```
pipeline_string = (
    f"srtsrc uri={self.srt_source_uri} ! queue leaky=2 max-size-time=500000000  ! "
    f"tsdemux latency=0 ! h265parse ! queue leaky=2 max-size-time=500000000  ! "
    f"nvv4l2decoder ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue leaky=2 max-size-time=500000000  ! "
    f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
    f"nvinfer config-file-path=/app/nomachine/mvp_ds_py/models/onnx/coco/nvinfer_config.txt ! queue leaky=2 max-size-time=500000000  ! "
    f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
    f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue leaky=2 max-size-time=500000000  ! "
    f"nvmultistreamtiler rows=1 columns=1 width=1920 height=1080 ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! queue leaky=2 max-size-time=500000000  ! "
    f"nvdsosd ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue leaky=2 max-size-time=500000000  ! "
    f"tee name=t ! queue ! nvv4l2h265enc ! queue leaky=2 max-size-time=500000000  ! "
    f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
    f"srtsink uri={self.srt_sink_uri} t. ! "
    f"queue ! nvv4l2h265enc ! queue leaky=2 max-size-time=500000000  ! "
    f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
    f"srtsink uri={self.srt_sink_uri_web} "
 )
```

## AI-Deepstream MPEGTSMUX e TSDEMUX -> Inferencia na AWS mvp test -> sem kafka -> com tee postando H265 e H264
```
pipeline_string = (
    f"srtsrc uri={self.srt_source_uri} ! queue leaky=2 max-size-time=500000000  ! "
    f"tsdemux latency=0 ! h265parse ! queue leaky=2 max-size-time=500000000  ! "
    f"nvv4l2decoder ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue leaky=2 max-size-time=500000000  ! "
    f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
    f"nvinfer config-file-path=/app/nomachine/mvp_ds_py/models/onnx/coco/nvinfer_config.txt ! queue leaky=2 max-size-time=500000000  ! "
    f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
    f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue leaky=2 max-size-time=500000000  ! "
    f"nvmultistreamtiler rows=1 columns=1 width=1920 height=1080 ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! queue leaky=2 max-size-time=500000000  ! "
    f"nvdsosd ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue leaky=2 max-size-time=500000000  ! "
    f"tee name=t ! queue ! nvv4l2h265enc ! queue leaky=2 max-size-time=500000000  ! "
    f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
    f"srtsink uri={self.srt_sink_uri} t. ! "
    f"queue ! nvv4l2h265enc ! queue leaky=2 max-size-time=500000000  ! "
    f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
    f"srtsink uri={self.srt_sink_uri_web} "
 )
```

## AI-Deepstream MPEGTSMUX e TSDEMUX -> Inferencia na AWS prod -> sem kafka -> com tee postando H265 e H264
```
pipeline_string = (
    f"srtsrc uri={self.srt_source_uri} ! queue leaky=2 max-size-time=500000000  ! "
    f"tsdemux latency=0 ! h265parse ! queue leaky=2 max-size-time=500000000  ! "
    f"nvv4l2decoder ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue leaky=2 max-size-time=500000000  ! "
    f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
    f"nvinfer config-file-path=/home/ubuntu/api/models/onnx/coco/nvinfer_config.txt ! queue leaky=2 max-size-time=500000000  ! "
    f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
    f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue leaky=2 max-size-time=500000000  ! "
    f"nvmultistreamtiler rows=1 columns=1 width=1920 height=1080 ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! queue leaky=2 max-size-time=500000000  ! "
    f"nvdsosd ! queue leaky=2 max-size-time=500000000  ! "
    f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue leaky=2 max-size-time=500000000  ! "
    f"tee name=t ! queue ! nvv4l2h265enc ! queue leaky=2 max-size-time=500000000  ! "
    f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
    f"srtsink uri={self.srt_sink_uri} t. ! "
    f"queue ! nvv4l2h264enc ! queue leaky=2 max-size-time=500000000  ! "
    f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
    f"srtsink uri={self.srt_sink_uri_web} "
    )
```


## Conexao AWS prod 
# Abrir o cmd no diretorio em que a chave .pem estiver e rodar o seguinte comando
```
    ssh -i web-app.pem ubuntu@3.84.245.85
```

### Conectado na AWS -> quando a API não é um serviço 
## Quando vc entra na AWS, vc está no /home da maquina. Para rodar a api voce precisa entrar na pasta que o arquivo api.py está e precisa digitar o comando para rodar a aplicação
# Para entrar na pasta da API, basta digitar 
```
    cd api/
```

# Para rodar a API, basta digitar 
```
    nohup python3 api.py > api.log 2>&1 &
```

# Confira se a API rodou conforme o esperado, para isso digite -> isso irá mostrar os prints que a aplicação api.py deu no terminal
```
    tail -f api.log
```

## Para verificar quais são as portas abertas atualmente no pipeline
```
    cat stream_state.json
```

# Caso tenha tido algum erro, você precisará matar todos os processos criados pela api.py
```
    ps -ef
```

# Identifique os processos criados pela api.py, normalmente eles estarao juntos e identificados pelo arquivo api.py em algum lugar
# Mate todos os processos 
```
    kill -9 {PID_DO_PROCESSO}
```


## Gerar um JWT Token na API usando o terminal
# De outra maquina 
curl -X POST http://3.84.245.85:5000/login \
-H "Content-Type: application/json" \
-d '{"username":"admin", "password":"password"}'

# Na AWS que contém a API
curl -X POST http://localhost:5000/login \
-H "Content-Type: application/json" \
-d '{"username":"admin", "password":"password"}'

## Gerar uma requisição para abrir porta usando o terminal
curl -X POST http://3.84.245.85:5000/start_stream \
-H "Content-Type: application/json" \
-H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcxNTEwMDk4OCwianRpIjoiOTRlOTJlOTgtZDI1OC00ZTY1LTk5ZGUtZTk5NTMwM2Y0MjE5IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImFkbWluIiwibmJmIjoxNzE1MTAwOTg4LCJjc3JmIjoiNmRlYTM1MmUtNGQzYy00YWJlLWJjNDgtZWNmYTE4MzUwOTcwIiwiZXhwIjoxNzE1MTAxODg4fQ.tGQK3O4Z_Mm2opWrcMBvvqHeBv5Pp4FZ7kfRayIyudg" \
-d '{
    "port_transmit": "10501",
    "passphrase_envia": "senha_envio",
    "port_receive": "9501",
    "passphrase_recebe": "senha_recebimento",
    "streamid": "1dtpmYcA7jto5KnO1715100878662"
}'


## Gerar uma requisição para fechar uma porta usando o terminal
curl -X POST http://3.84.245.85:5000/stop_stream \
-H "Content-Type: application/json" \
-H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTcxNTEwMDk4OCwianRpIjoiOTRlOTJlOTgtZDI1OC00ZTY1LTk5ZGUtZTk5NTMwM2Y0MjE5IiwidHlwZSI6ImFjY2VzcyIsInN1YiI6ImFkbWluIiwibmJmIjoxNzE1MTAwOTg4LCJjc3JmIjoiNmRlYTM1MmUtNGQzYy00YWJlLWJjNDgtZWNmYTE4MzUwOTcwIiwiZXhwIjoxNzE1MTAxODg4fQ.tGQK3O4Z_Mm2opWrcMBvvqHeBv5Pp4FZ7kfRayIyudg" \
-d '{
    "port_transmit": "10501",
    "passphrase_envia": "senha_envio",
    "port_receive": "9501",
    "passphrase_recebe": "senha_recebimento",
    "streamid": "1dtpmYcA7jto5KnO1715100878662"
}'





















