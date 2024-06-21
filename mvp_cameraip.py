import gi # type: ignore
import platform
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib # type: ignore
import time
import os 

# Ensure the GST_DEBUG_DUMP_DOT_DIR is set before Gst is initialized
# dot_dir = "/app/nomachine/mvp_ds_py"
# os.makedirs(dot_dir, exist_ok=True)  # Create the directory if it doesn't exist
# os.environ["GST_DEBUG_DUMP_DOT_DIR"] = dot_dir
# print(f"Dot files will be saved to {dot_dir}.")

class DynamicStreamer: 
    def __init__(self, rtsp_source_uri: str, srt_sink_uri, latency: int, tcp_timeout: int, drop_on_latency: bool, low_latency: bool, mtu: int, use_h265: bool = False):
        print("DynamicStreamer initialization...")
        self.rtsp_source_uri = rtsp_source_uri
        self.srt_sink_uri = srt_sink_uri
        self.latency = latency
        self.tcp_timeout = tcp_timeout
        self.drop_on_latency = drop_on_latency
        self.low_latency = low_latency
        self.mtu = mtu
        self.use_h265 = use_h265
        self.system_platform = platform.system() 
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

    def is_deepstream_available(self):
        # Attempt to create a DeepStream-specific element to check availability
        test_element = Gst.ElementFactory.make("nvv4l2decoder", None)
        return test_element is not None

    def configure_pipeline(self):
        print("Configuring pipeline...")
        #deepstream_available = self.is_deepstream_available()

        # Inicializa os elementos
        # Captura a stream de video transmitida pela camera IP via RTSP
        source = Gst.ElementFactory.make("rtspsrc", "source")
        source.set_property("location", self.rtsp_source_uri)
        source.set_property("tcp-timeout", self.tcp_timeout)
        source.set_property("drop-on-latency", self.drop_on_latency)
        

        # Faz o decode da stream capturada - ela ja eh transmitida pela camera ip com encode h264
        #decoder = Gst.ElementFactory.make("nvv4l2decoder" if deepstream_available else "decodebin", "decoder")
        decoder = Gst.ElementFactory.make("decodebin", "decoder")
        

        # Faz a escolha do encoder h265 dependendo do sistema operacional
        # Implementar a logica de encoder utilizando o deepstream dependendo do sistema operacional
        encoding_name_encoder = "265" if self.use_h265 else "264"
        if self.system_platform == "Windows":
            encoder = Gst.ElementFactory.make(f"mpf{encoding_name_encoder}enc", "encoder")
            encoder.set_property("low-latency", self.low_latency)
        elif self.system_platform == "Linux":
            encoder = Gst.ElementFactory.make(f"x{encoding_name_encoder}enc", "encoder")


        # Verifica se eh possivel usar o plugin de videoconvert do deepstream. 
        # Se possivel utilizaremos ele, caso contrario, utilizaremos o videoconvert.
        # videoconverter = Gst.ElementFactory.make("nvvideoconvert" if deepstream_available else "videoconvert", videoconverter)
        videoconverter = Gst.ElementFactory.make("videoconvert", "videoconverter")
        # Encapsula o frame de video encodados h265 em pacotes RTP - particiona o frame em varios pacotes RTP
        pay = Gst.ElementFactory.make("rtph265pay", "pay")
        pay.set_property("mtu", self.mtu)


        # Envia o dado para a AWS
        sink = Gst.ElementFactory.make("srtsink", "sink")
        sink.set_property("uri", self.srt_sink_uri)

        # Adiciona os elementos ao pipeline
        elements = [source, decoder, encoder, videoconverter, pay, sink]
        for element in elements:
            self.pipeline.add(element)

        # Link elements
        source.link(decoder)
        decoder.link(encoder)
        encoder.link(videoconverter)
        videoconverter.link(pay)
        pay.link(sink)
        # Probe para fazer o calculo da latencia
        #src_pad = decoder.get_static_pad("src")
        #src_pad.add_probe(Gst.PadProbeType.BUFFER, self.pad_probe_callback, None)

    # Calcula a latencia do pipeline    
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
    SOURCE_URI = "rtsp://admin:admin123@192.168.1.108:554"
    SINK_URI = "srt://34.230.172.138:9710"
    LATENCY = 0
    TCP_TIMEOUT = 200000
    DROP_ON_LATENCY = True
    LOW_LATENCY = True
    MTU = 1316
    streamer = DynamicStreamer(SOURCE_URI, SINK_URI, LATENCY, TCP_TIMEOUT, DROP_ON_LATENCY, LOW_LATENCY, MTU, use_h265=True)
    streamer.start_streaming()
