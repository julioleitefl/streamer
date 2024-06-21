#include <gst/gst.h>
#include <cstdio>

int main(int argc, char *argv[]){
    gst_init(&argc, &argv);

    GstElement *pipeline = gst_parse_launch("srtsrc uri=srt://:9710 ! application/x-rtp, media=(string)video, encoding-name=(string)H265 ! rtph265depay ! decodebin ! videoconvert ! queue ! timeoverlay deltay=30 ! autovideosink", NULL);
    // GstElement *pipeline = gst_parse_launch("srtsrc uri=srt://:9710 ! tee ! queue ! kafka ! decodebin ! queue ! autovideosink", NULL);

    gst_element_set_state(pipeline, GST_STATE_PLAYING);

    getchar();

    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    gst_deinit();

    return 0;
}