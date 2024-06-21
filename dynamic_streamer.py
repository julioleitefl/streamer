import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import time
import os 
from threading import Thread

# class DynamicStreamer(Thread):
class DynamicStreamer():
    def __init__(self, srt_source_uri: str, srt_sink_uri: str, srt_sink_uri_web: str):
        super().__init__()
        print("DynamicStreamer initialization...")
        self.srt_source_uri = srt_source_uri
        self.srt_sink_uri_web = srt_sink_uri_web
        self.srt_sink_uri = srt_sink_uri
        # config = self.read_config()
        # self.kafka_producer = Producer(config)
        # os.environ["GST_DEBUG"] = "3"
        # os.environ["GST_DEBUG"] = "*TRACE*:7"
        # os.environ["GST_TRACERS"] = "interlatency"
        Gst.init(None)
        self.loop = GLib.MainLoop()
        self.pipeline = Gst.Pipeline.new("dynamic-streamer-pipeline")
        self.configure_pipeline()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)
        self.frame_count = 0
        self.encoding_time_sum = 0
        self.sending_time_sum = 0
        self.start_time = time.time() 
        self.last_print_time = time.time()
        os.environ["GST_DEBUG_DUMP_DOT_DIR"] = "/tmp/"
        print("Dot files will be saved to the current directory.")

    def on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
        elif t == Gst.MessageType.EOS:
            print("End-Of-Stream reached.")
            self.stop_streaming()
            self.loop = GLib.MainLoop()
            self.pipeline = Gst.Pipeline.new("dynamic-streamer-pipeline")
            self.configure_pipeline()
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            self.start_streaming()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                print(f"Pipeline state changed from {old_state.value_nick} to {new_state.value_nick}.")
                # Generate DOT file for visualization
                Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "dynamic-streamer-pipeline")
                # Print the entire pipeline to the console
                # print("\nPipeline:")
                # print(self.pipeline)

    def configure_pipeline(self):
        print("Configuring pipeline...")
        #prod sem tee e sem queues
        # pipeline_string = (
        #     f"srtsrc uri={self.srt_source_uri} ! queue leaky=2 max-size-time=500000000  ! "
        #     f"tsdemux latency=0 ! h265parse ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvv4l2decoder ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! "
        #     f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
        #     f"nvinfer config-file-path=/home/ubuntu/api/models/onnx/coco/nvinfer_config.txt ! "
        #     f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
        #     f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! "
        #     f"nvmultistreamtiler rows=1 columns=1 width=1920 height=1080 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! "
        #     f"nvdsosd ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvv4l2h264enc tuning-info-id=2 bitrate=2000000 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
        #     f"srtsink uri={self.srt_sink_uri} "
        # )
        
        # prod sem tee com queues e copiado de uum pipeline de duas semanas atras
        
        pipeline_string = (
    f"srtsrc uri={self.srt_source_uri} ! queue leaky=2 max-size-time=500000000 ! "
    f"tsdemux latency=0 ! h265parse ! queue leaky=2 max-size-time=500000000 ! "
    f"nvv4l2decoder ! queue leaky=2 max-size-time=500000000 ! "
    f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1280,height=720,format=NV12 ! queue leaky=2 max-size-time=500000000 ! "
    f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1280 height=720 live-source=1 ! "
    f"nvinfer config-file-path=/home/ubuntu/api/models/onnx/coco/nvinfer_config.txt ! queue leaky=2 max-size-time=500000000 ! "
    f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
    f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue leaky=2 max-size-time=500000000 ! "
    f"nvmultistreamtiler rows=1 columns=1 width=1280 height=720 ! queue leaky=2 max-size-time=500000000 ! "
    f"nvvideoconvert ! queue leaky=2 max-size-time=500000000 ! "
    f"nvdsosd ! queue leaky=2 max-size-time=500000000 ! "
    f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue leaky=2 max-size-time=500000000 ! "
    f"nvv4l2h264enc name=enc tuning-info-id=3 ! queue leaky=2 max-size-time=500000000 ! "
    f"mpegtsmux ! queue leaky=2 max-size-time=500000000 ! "
    f"srtsink uri={self.srt_sink_uri}"
)   

        # #prod sem tee
        # pipeline_string = (
        #     f"srtsrc uri={self.srt_source_uri} ! queue leaky=2 max-size-time=500000000  ! "
        #     f"tsdemux latency=0 ! h265parse ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvv4l2decoder ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
        #     f"nvinfer config-file-path=/home/ubuntu/api/models/onnx/coco/nvinfer_config.txt ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
        #     f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvmultistreamtiler rows=1 columns=1 width=1920 height=1080 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvdsosd ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvv4l2h264enc tuning-info-id=2 bitrate=2000000 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
        #     f"srtsink uri={self.srt_sink_uri} "
        # )
        
        
        #prod com tee
        # pipeline_string = (
        #     f"srtsrc uri={self.srt_source_uri} ! queue leaky=2 max-size-time=500000000  ! "
        #     f"tsdemux latency=0 ! h265parse ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvv4l2decoder ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
        #     f"nvinfer config-file-path=/home/ubuntu/api/models/onnx/coco/nvinfer_config.txt ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
        #     f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvmultistreamtiler rows=1 columns=1 width=1920 height=1080 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvdsosd ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"tee name=t ! queue ! nvv4l2h265enc ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
        #     f"srtsink uri={self.srt_sink_uri} t. ! "
        #     f"queue ! nvv4l2h264enc ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
        #     f"srtsink uri={self.srt_sink_uri_web} "
        # )
        
        #mvp test
        # pipeline_string = (
        #     f"srtsrc uri={self.srt_source_uri} ! queue leaky=2 max-size-time=500000000  ! "
        #     f"tsdemux latency=0 ! h265parse ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvv4l2decoder ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
        #     f"nvinfer config-file-path=/app/nomachine/mvp_ds_py/models/onnx/coco/nvinfer_config.txt ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
        #     f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvmultistreamtiler rows=1 columns=1 width=1920 height=1080 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvdsosd ! queue leaky=2 max-size-time=500000000  ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue leaky=2 max-size-time=500000000  ! "
        #     f"tee name=t ! queue ! nvv4l2h265enc ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
        #     f"srtsink uri={self.srt_sink_uri} t. ! "
        #     f"queue ! nvv4l2h265enc ! queue leaky=2 max-size-time=500000000  ! "
        #     f"mpegtsmux ! queue leaky=2 max-size-time=500000000  ! "
        #     f"srtsink uri={self.srt_sink_uri_web} "
        # )

        # pipeline_string = (
        #     f"srtsrc uri={self.srt_source_uri} ! queue ! "
        #     f"tsdemux latency=0 ! h265parse ! queue ! "
        #     f"nvv4l2decoder ! queue ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue ! "
        #     f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
        #     f"nvinfer config-file-path=/app/nomachine/mvp_ds_py/models/onnx/coco/nvinfer_config.txt ! queue ! "
        #     f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
        #     f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue ! "
        #     f"nvmultistreamtiler rows=1 columns=1 width=1920 height=1080 ! queue ! "
        #     f"nvvideoconvert ! queue ! "
        #     f"nvdsosd ! queue ! "
        #     f"tee name=t ! queue ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue ! "
        #     f"queue ! nvv4l2h264enc name=enc264 tuning-info-id=3 ! queue ! "
        #     f"mpegtsmux name=mux1 ! queue ! "
        #     f"srtsink uri={self.srt_sink_uri_web} "
        #     f"t. ! queue ! nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue ! "
        #     f"nvv4l2h265enc name=enc265 tuning-info-id=3 ! queue ! "
        #     f"mpegtsmux name=mux2 ! queue ! "
        #     f"srtsink uri={self.srt_sink_uri}"
        # )
        
        # pipeline_string = (
        #     f"rtspsrc location={self.srt_source_uri} ! queue ! "
        #     f"nvh265dec ! queue ! "
        #     f"nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue ! "
        #     f"mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
        #     f"nvinfer config-file-path=/app/nomachine/mvp_ds_py/nvinfer_config.txt ! queue ! "
        #     f"nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
        #     f"ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue ! "
        #     f"nvmultistreamtiler rows=1 columns=1 width=1280 height=720 ! queue ! "
        #     f"nvvideoconvert ! queue ! "
        #     f"nvdsosd ! queue ! "
        #     f"nvvideoconvert ! video/x-raw,format=I420 ! "
        #     f"nvh265enc name=enc ! "
        #     f"fakesink"
        # )

        self.pipeline = Gst.parse_launch(pipeline_string)


        # enc = self.pipeline.get_by_name("enc")
        # enc_pad = enc.get_static_pad("sink")
        # enc_pad.add_probe(Gst.PadProbeType.BUFFER, self.kafka_probe_callback, None) 

    def delivery_report(self, err, msg):
        """ Callback called once message delivered or failed to deliver """
        if err:
            print(f"Message delivery failed: {err}")
        else:
            print(f"Message delivered to {msg.topic()} [{msg.partition()}]")
    
    def on_source_pad_added(self, src, new_pad, nvstreammux):
        print("Received new pad '%s' from '%s':" % (new_pad.get_name(), src.get_name()))
        new_pad_caps = new_pad.get_current_caps()
        new_pad_struct = new_pad_caps.get_structure(0)
        new_pad_type = new_pad_struct.get_name()
        if new_pad_type.startswith("video/x-raw"):
            mux_pad_template = nvstreammux.get_pad_template("sink_%u")
            mux_pad = nvstreammux.request_pad(mux_pad_template, None, None)
            if mux_pad:
                new_pad.link(mux_pad)
    
    def on_decoder_pad_added(self, decodebin, pad):
        if not pad.has_current_caps():
            print("Pad '{}' has no caps, can't link".format(pad.name))
            return

        caps = pad.get_current_caps()
        name = caps.to_string()
        if 'video' in name:  # Check if this is a video pad
            videoconvert_for_sink = self.pipeline.get_by_name("videoconvert_for_sink")
            if videoconvert_for_sink:
                sink_pad = videoconvert_for_sink.get_static_pad("sink")
                pad.link(sink_pad)
            else:
                print("Videoconvert for sink not found")
        else:
            print("Pad '{}' is not a video pad".format(pad.name))
    
    def run(self):
        self._start_streaming()
        
    def _start_streaming(self):
        print("Starting streaming...")
        self.pipeline.set_state(Gst.State.PLAYING)
        try:
            self.loop.run()
        except KeyboardInterrupt:
            print("Streaming stopped by user.")
            self.stop_streaming()
    
    def start_streaming(self):
        print("Starting streaming...")
        self.pipeline.set_state(Gst.State.PLAYING)
        try:
            self.loop.run()
        except KeyboardInterrupt:
            print("Streaming stopped by user.")
            self.stop_streaming()

    def stop_streaming(self):
        print("Stopping streaming...")
        self.pipeline.set_state(Gst.State.NULL)
        self.loop.quit()

    pass