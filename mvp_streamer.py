import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
from confluent_kafka import Producer
import time
import os 

# Ensure the GST_DEBUG_DUMP_DOT_DIR is set before Gst is initialized
# dot_dir = "/app/nomachine/mvp_ds_py"
# os.makedirs(dot_dir, exist_ok=True)  # Create the directory if it doesn't exist
# os.environ["GST_DEBUG_DUMP_DOT_DIR"] = dot_dir
# print(f"Dot files will be saved to {dot_dir}.")

class DynamicStreamer:
    def __init__(self, srt_source_uri: str, kafka_bootstrap_servers: str, kafka_topic: str, use_h265: bool = False):
        print("DynamicStreamer initialization...")
        self.srt_source_uri = srt_source_uri
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.kafka_topic = kafka_topic
        self.use_h265 = use_h265
        self.kafka_producer = Producer({'bootstrap.servers': kafka_bootstrap_servers})
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
        deepstream_available = self.is_deepstream_available()

        # Initialize elements
        source = Gst.ElementFactory.make("srtsrc", "source")
        source.set_property("uri", self.srt_source_uri)
        
        capsfilter = Gst.ElementFactory.make("capsfilter", "capsfilter")
        encoding_name = "H265" if self.use_h265 else "H264"
        caps = Gst.Caps.from_string(f"application/x-rtp, media=(string)video, encoding-name=(string){encoding_name}")
        capsfilter.set_property("caps", caps)
        
        depay = Gst.ElementFactory.make(f"rtp{encoding_name.lower()}depay", "depay")
        decoder = Gst.ElementFactory.make("nvv4l2decoder" if deepstream_available else "decodebin", "decoder")
        if not deepstream_available:
            decoder.connect("pad-added", self.on_decoder_pad_added)

        videoconvert_deepstream = Gst.ElementFactory.make("nvvideoconvert", "videoconvert_deepstream") if deepstream_available else None
        capsfilter_nvmm_to_system = None
        if deepstream_available:
            caps_nvmm_to_system = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=(string)RGBA")
            capsfilter_nvmm_to_system = Gst.ElementFactory.make("capsfilter", "capsfilter_nvmm_to_system")
            capsfilter_nvmm_to_system.set_property("caps", caps_nvmm_to_system)

        videoconvert_for_sink = Gst.ElementFactory.make("videoconvert", "videoconvert_for_sink")
        caps_to_sink = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=(string)RGBA")
        capsfilter_to_sink = Gst.ElementFactory.make("capsfilter", "capsfilter_to_sink")
        capsfilter_to_sink.set_property("caps", caps_to_sink)

        # Setup display and encoding branches
        tee = Gst.ElementFactory.make("tee", "tee")
        queue_display = Gst.ElementFactory.make("queue", "queue_display")
        display_sink = Gst.ElementFactory.make("fakesink", "fakesink")
        queue_encode = Gst.ElementFactory.make("queue", "queue_encode")
        jpegenc = Gst.ElementFactory.make("jpegenc", "jpegenc")
        queue_jpeg = Gst.ElementFactory.make("queue", "queue_jpeg")
        fakesink = Gst.ElementFactory.make("fakesink", "fakesink")

        # Add elements to the pipeline
        elements = [source, capsfilter, depay, decoder, videoconvert_for_sink, capsfilter_to_sink, tee, queue_display, display_sink, queue_encode, jpegenc, queue_jpeg, fakesink]
        if deepstream_available:
            elements.extend([videoconvert_deepstream, capsfilter_nvmm_to_system])
        for element in elements:
            self.pipeline.add(element)

        # Link elements
        source.link(capsfilter)
        capsfilter.link(depay)
        depay.link(decoder)

        if deepstream_available:
            decoder.link(videoconvert_deepstream)
            videoconvert_deepstream.link(capsfilter_nvmm_to_system)
            capsfilter_nvmm_to_system.link(videoconvert_for_sink)
        else:
            # For pure GStreamer pipeline, 'decoder' is 'decodebin' and should be linked in on_decoder_pad_added
            pass

        videoconvert_for_sink.link(capsfilter_to_sink)
        capsfilter_to_sink.link(tee)

        tee.link(queue_display)
        queue_display.link(display_sink)
        tee.link(queue_encode)
        queue_encode.link(jpegenc)
        jpegenc.link(queue_jpeg)
        queue_jpeg.link(fakesink)
        # Add a probe on the sink pad of jpegenc to capture frames for Kafka
        sink_pad = queue_encode.get_static_pad("sink")
        sink_pad.add_probe(Gst.PadProbeType.BUFFER, self.kafka_probe_callback, None)
        src_pad = depay.get_static_pad("src")
        src_pad.add_probe(Gst.PadProbeType.BUFFER, self.pad_probe_callback, None)
        
    # def pad_probe_callback(self, pad, info, data):
    #     buffer = info.get_buffer()
    #     if buffer:
    #         rtp_timestamp = buffer.pts
    #         print(f'rtp_timestamp? {rtp_timestamp}')
    #         system_clock = Gst.SystemClock.obtain()
    #         current_time_gst = system_clock.get_time()
    #         print(f'current_time_gst? {current_time_gst}')
    #         clock_rate = 90000
    #         real_time_timestamp_ns = (rtp_timestamp * Gst.SECOND) // clock_rate
    #         print(f'real_time_timestamp_ns? {real_time_timestamp_ns}')
    #         latency_ns = current_time_gst - real_time_timestamp_ns
    #         latency_ms = latency_ns / 1_000_000
             
    #         print(f"Current Latency: {latency_ms} ms")
    #     return Gst.PadProbeReturn.OK
        
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
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if success:
                try:
                    send_start_time = time.time()
                    # self.kafka_producer.produce(self.kafka_topic, map_info.data)
                    # self.kafka_producer.poll(0)  # Adjusted for non-blocking
                    self.sending_time_sum += time.time() - send_start_time
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
    SOURCE_URI = "srt://:9710?mode=listener"
    KAFKA_BOOTSTRAP_SERVERS = 'broker0:29092,broker1:29093,broker2:29094'
    KAFKA_TOPIC = 'raw_frames'
    streamer = DynamicStreamer(SOURCE_URI, KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, use_h265=True)
    streamer.start_streaming()
