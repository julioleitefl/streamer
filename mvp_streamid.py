import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
from confluent_kafka import Producer
import time
import os 
import numpy as np

class DynamicStreamer:
    def __init__(self, srt_source_uri: str, srt_sink_uri: str,  kafka_bootstrap_servers: str, kafka_topic: str, use_h265: bool = False):
        print("DynamicStreamer initialization...")
        self.srt_source_uri = srt_source_uri
        self.srt_sink_uri = srt_sink_uri
        self.kafka_bootstrap_server = kafka_bootstrap_servers
        self.kafka_topic = kafka_topic
        self.use_h265 = use_h265
        config = self.read_config()
        self.kafka_producer = Producer(config)
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
        os.environ["GST_DEBUG_DUMP_DOT_DIR"] = "/home/nomachine"
        print("Dot files will be saved to the current directory.")

    def on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
        elif t == Gst.MessageType.EOS:
            print("End-Of-Stream reached.")
            self.loop.quit()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                print(f"Pipeline state changed from {old_state.value_nick} to {new_state.value_nick}.")
                # Generate DOT file for visualization
                Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "dynamic-streamer-pipeline")
                # Print the entire pipeline to the console
                print("\nPipeline:")
                print(self.pipeline)

    def configure_pipeline(self):
        print("Configuring pipeline...")

        # Initialize elements
        pipeline_string = (
    "srtsrc uri=\"srt://:9711?mode=listener\" ! queue ! "
    "tsdemux latency=0 ! h265parse ! queue ! "
    "avdec_h265 ! videoconvert ! video/x-raw,format=NV12 ! queue ! "
    "nvvideoconvert ! video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12 ! queue ! "
    "mux.sink_0 nvstreammux name=mux batch-size=1 width=1920 height=1080 live-source=1 ! "
    "nvinfer config-file-path=/app/nomachine/mvp_ds_py/nvinfer_config.txt ! queue ! "
    "nvtracker ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_max_perf.yml "
    "ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so compute-hw=1 user-meta-pool-size=1000 ! queue ! "
    "nvmultistreamtiler rows=1 columns=1 width=1280 height=720 ! queue ! "
    "nvvideoconvert ! queue ! "
    "nvdsosd ! queue ! "
    "nvvideoconvert ! video/x-raw(memory:NVMM),format=I420 ! queue ! "
    "nvv4l2h265enc name=enc tuning-info-id=3 ! queue ! "
    "mpegtsmux ! queue ! "
    "srtsink uri=\"srt://:9710\""
)
        self.pipeline = Gst.parse_launch(pipeline_string)


        enc = self.pipeline.get_by_name("enc")
        enc_pad = enc.get_static_pad("sink")
        enc_pad.add_probe(Gst.PadProbeType.BUFFER, self.kafka_probe_callback, None) 

    def pad_probe_callback(self, pad, info, data):
        buffer = info.get_buffer()
        if buffer:
            pts = buffer.pts
            if pts == Gst.CLOCK_TIME_NONE:
                return Gst.PadProbeReturn.OK

            real_time_timestamp_ns = pts
            clock = Gst.SystemClock.obtain()
            element = pad.get_parent()
            while element and not isinstance(element, Gst.Pipeline):
                element = element.get_parent()
            if not element:
                print("Error: Failed to find the pipeline.")
                return Gst.PadProbeReturn.OK
            pipeline = element
            current_time_ns = clock.get_time() - pipeline.get_base_time()
            latency_ns = current_time_ns - real_time_timestamp_ns
            latency_ms = latency_ns / 1_000
            print(f"Current Latency: {latency_ms} ms")
        return Gst.PadProbeReturn.OK
    
    def kafka_probe_callback(self, pad, info, user_data):
        buffer = info.get_buffer()
        if buffer:
            encoding_start_time = time.time()
            # gst_memory = buffer.peek_memory(0)
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                try:
                    send_start_time = time.time()
                    frame = bytes(map_info.data)
                    self.kafka_producer.produce(self.kafka_topic, frame)
                    self.kafka_producer.poll(0)  # Adjusted for non-blocking
                    self.sending_time_sum += time.time() - send_start_time
                    buffer.unmap(map_info)
                except Exception as e:
                    print(f"Exception while producing message: {e}")
                finally:
                    buffer.unmap(map_info)
                
                encoding_time = time.time() - encoding_start_time
                self.encoding_time_sum += encoding_time
                
                self.frame_count += 1
                current_time = time.time()
                elapsed_time_since_last_print = current_time - self.last_print_time
                if elapsed_time_since_last_print >= 2:
                    average_encoding_speed = self.encoding_time_sum / self.frame_count
                    average_sending_speed = self.sending_time_sum / self.frame_count
                    print(f"Average Encoding Speed: {average_encoding_speed:.4f} seconds/frame, Average Sending Speed: {average_sending_speed:.4f} seconds/message")
                    self.last_print_time = current_time
                    self.encoding_time_sum = 0
                    self.sending_time_sum = 0
                    self.frame_count = 0
            else:
                print("Failed to map GstBuffer for reading.")
        else:
            print("Buffer is None.")
        return Gst.PadProbeReturn.OK
    
    
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
    
    def read_config(self):
        # reads the client configuration from client.properties
        # and returns it as a key-value map
        config = {}
        with open("client.properties") as fh:
            for line in fh:
                line = line.strip()
                if len(line) != 0 and line[0] != "#":
                    parameter, value = line.strip().split('=', 1)
                    config[parameter] = value.strip()
        return config

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

if __name__ == "__main__":
    SOURCE_URI = "srt://:9711"
    SINK_URI = "srt://:9710"
    KAFKA_BOOTSTRAP_SERVERS = '127.0.0.1:9092'
    KAFKA_TOPIC = 'raw_frames'
    streamer = DynamicStreamer(SOURCE_URI, SINK_URI, KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, use_h265=True)
    streamer.start_streaming()
