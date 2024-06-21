#include <gst/gst.h>
#include <cstdio>

int main(int argc, char *argv[]) {
    // Inicializa o GStreamer
    gst_init(&argc, &argv);

    // Cria o pipeline
    GstElement *pipeline = gst_parse_launch("videotestsrc pattern=snow ! video/x-raw,width=640,height=480 ! x265enc ! rtph265pay mtu=1316 ! srtsink uri=srt://34.230.172.138:9710?mode=caller", NULL);

    // Inicia o pipeline
    gst_element_set_state(pipeline, GST_STATE_PLAYING);

    // Aguarda até que o usuário pressione Enter
    getchar();

    // Finaliza o pipeline
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    gst_deinit();

    return 0;
}
